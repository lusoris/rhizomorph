// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Telemetry ingress cost measurement for defect 4 (`docs/plan/design-defects.md`):
//! compares (a) `RwLock<Vec<Value>>` write lock + `Instant::now()` per update,
//! (b) `RwLock<Vec<Value>>` write lock without clock read, and
//! (c) `SharedKernel::telemetry` (`Mutex<Kernel>`, no clock read),
//! across 1 thread and 4 threads.

use std::env;
use std::error::Error;
use std::hint::black_box;
use std::sync::{Arc, RwLock};
use std::thread;
use std::time::Instant;

use kernel_std::{AdapterError, Capacities, SharedKernel, Value, ValueKind};

const DEFAULT_ITERATIONS: u64 = 2_000_000;
const THREAD_COUNT: u64 = 4;

/// Runs the three shapes at 1 and 4 threads and prints nanoseconds per update as a table.
fn main() -> Result<(), Box<dyn Error>> {
    let iterations = env::args()
        .nth(1)
        .and_then(|arg| arg.parse::<u64>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(DEFAULT_ITERATIONS);

    let ref_clock_1t = bench_rwlock_with_clock(iterations, 1);
    let ref_clock_4t = bench_rwlock_with_clock(iterations, THREAD_COUNT);
    let ref_noclock_1t = bench_rwlock_without_clock(iterations, 1);
    let ref_noclock_4t = bench_rwlock_without_clock(iterations, THREAD_COUNT);
    let shared_1t = bench_shared_kernel(iterations, 1)?;
    let shared_4t = bench_shared_kernel(iterations, THREAD_COUNT)?;

    println!("| Shape | 1 thread (ns/update) | 4 threads (ns/update) | Total updates |");
    println!("| :--- | ---: | ---: | ---: |");
    println!(
        "| (a) `RwLock<Vec<Value>>` write + `Instant::now()` | {ref_clock_1t:.1} | {ref_clock_4t:.1} | {iterations} |"
    );
    println!(
        "| (b) `RwLock<Vec<Value>>` write, no clock | {ref_noclock_1t:.1} | {ref_noclock_4t:.1} | {iterations} |"
    );
    println!(
        "| (c) `SharedKernel::telemetry` (`Mutex`, no clock) | {shared_1t:.1} | {shared_4t:.1} | {iterations} |"
    );
    Ok(())
}

/// Shape (a): an `RwLock<Vec<Value>>` write plus one `Instant::now()` per update.
fn bench_rwlock_with_clock(total_iterations: u64, threads: u64) -> f64 {
    let per_thread = total_iterations / threads;
    let remainder = total_iterations % threads;
    let state = Arc::new(RwLock::new(vec![Value::I64(0); 16]));
    let start = Instant::now();
    thread::scope(|scope| {
        for thread in 0..threads {
            let count = per_thread + u64::from(thread < remainder);
            let state_ref = Arc::clone(&state);
            scope.spawn(move || {
                for i in 0..count {
                    let now = Instant::now();
                    if let Ok(mut guard) = state_ref.write()
                        && let Some(slot) = guard.get_mut(0)
                    {
                        *slot = Value::I64(i64::try_from(i).unwrap_or(0));
                        black_box(now);
                    }
                }
            });
        }
    });
    mean_ns(start.elapsed().as_nanos(), total_iterations)
}

/// Shape (b): an `RwLock<Vec<Value>>` write without a clock read.
fn bench_rwlock_without_clock(total_iterations: u64, threads: u64) -> f64 {
    let per_thread = total_iterations / threads;
    let remainder = total_iterations % threads;
    let state = Arc::new(RwLock::new(vec![Value::I64(0); 16]));
    let start = Instant::now();
    thread::scope(|scope| {
        for thread in 0..threads {
            let count = per_thread + u64::from(thread < remainder);
            let state_ref = Arc::clone(&state);
            scope.spawn(move || {
                for i in 0..count {
                    if let Ok(mut guard) = state_ref.write()
                        && let Some(slot) = guard.get_mut(0)
                    {
                        *slot = Value::I64(i64::try_from(i).unwrap_or(0));
                    }
                }
            });
        }
    });
    mean_ns(start.elapsed().as_nanos(), total_iterations)
}

/// Shape (c): `SharedKernel::telemetry` under its one `Mutex`, without a clock read.
fn bench_shared_kernel(total_iterations: u64, threads: u64) -> Result<f64, Box<dyn Error>> {
    let per_thread = total_iterations / threads;
    let remainder = total_iterations % threads;
    let kernel = Arc::new(SharedKernel::new(Capacities {
        points: 16,
        leases: 4,
        points_per_lease: 16,
    }));
    let point = kernel.register_input(ValueKind::I64, Some(1.0))?;
    let start = Instant::now();
    let failures = thread::scope(|scope| {
        let mut handles = Vec::new();
        for thread in 0..threads {
            let count = per_thread + u64::from(thread < remainder);
            let kernel_ref = Arc::clone(&kernel);
            handles.push(scope.spawn(move || {
                let mut errors = 0_u64;
                let mut first: Option<AdapterError> = None;
                let mut sink = |ev| {
                    black_box(ev);
                };
                for i in 0..count {
                    let val = Value::I64(i64::try_from(i).unwrap_or(0));
                    if let Err(error) = kernel_ref.telemetry(point, val, &mut sink) {
                        errors += 1;
                        first.get_or_insert(error);
                    }
                }
                (errors, first)
            }));
        }
        handles
            .into_iter()
            .map(thread::ScopedJoinHandle::join)
            .collect::<Vec<_>>()
    });
    for result in failures {
        let (count, first) = result.map_err(|_| "telemetry worker panicked")?;
        if let Some(error) = first {
            return Err(format!("telemetry failed {count} times: {error}").into());
        }
    }
    Ok(mean_ns(start.elapsed().as_nanos(), total_iterations))
}

/// Mean nanoseconds per operation; zero operations give 0.0.
#[expect(
    clippy::cast_precision_loss,
    reason = "a mean in nanoseconds needs no more than f64 precision"
)]
fn mean_ns(elapsed_nanos: u128, operations: u64) -> f64 {
    if operations == 0 {
        return 0.0;
    }
    (elapsed_nanos as f64) / (operations as f64)
}
