// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Integration tests for `kernel-std` adapter (`SharedKernel` and `AdapterError`).

use std::error::Error;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::{Arc, mpsc};
use std::thread;
use std::time::Duration;

use kernel_std::{
    AdapterError, Capacities, CovEvent, Kernel, KernelError, LeaseId, Millis, PointId, Priority,
    SharedKernel, Value, ValueKind,
};

/// The adapter forwards each kernel operation and passes COV events to the caller's sink.
#[test]
fn adapter_forwards_operations_and_cov_events() {
    let shared = SharedKernel::new(Capacities {
        points: 8,
        leases: 4,
        points_per_lease: 4,
    });
    let inp = shared.register_input(ValueKind::I64, Some(2.0)).unwrap();
    let out = shared.register_output(Value::I64(0)).unwrap();
    let lease = shared.issue_lease(Millis(60_000)).unwrap();

    let mut events = Vec::new();
    shared
        .telemetry(inp, Value::I64(10), &mut |e| events.push(e))
        .unwrap();
    shared
        .command(
            lease,
            out,
            Priority::MANUAL_OPERATOR,
            Value::I64(42),
            &mut |e| events.push(e),
        )
        .unwrap();
    assert_eq!(shared.lease_point_count(lease).unwrap(), 1);
    shared.renew(lease).unwrap();
    shared
        .relinquish(lease, out, Priority::MANUAL_OPERATOR, &mut |e| {
            events.push(e);
        })
        .unwrap();
    assert_eq!(shared.revoke(lease, &mut |_| {}).unwrap(), 0);
    assert_eq!(shared.expire(&mut |_| {}).unwrap(), 0);
    assert_eq!(
        events,
        vec![
            CovEvent {
                point: inp,
                value: Value::I64(10)
            },
            CovEvent {
                point: out,
                value: Value::I64(42)
            },
            CovEvent {
                point: out,
                value: Value::I64(0)
            },
        ]
    );
}

/// Asserts that `res` is `AdapterError::Poisoned` for `expected_op`.
#[expect(
    clippy::needless_pass_by_value,
    reason = "the helper takes each call result by value as the call returns it"
)]
fn assert_poisoned<T: std::fmt::Debug + PartialEq>(
    res: Result<T, AdapterError>,
    expected_op: &'static str,
) {
    assert_eq!(res, Err(AdapterError::Poisoned { op: expected_op }));
}

/// A panicking sink poisons the mutex, and every later call returns `AdapterError::Poisoned`.
#[test]
fn adapter_panic_in_sink_poisons_mutex_and_next_call_returns_poisoned() {
    let shared = SharedKernel::new(Capacities::default());
    let inp = shared.register_input(ValueKind::I64, None).unwrap();

    let caught = catch_unwind(AssertUnwindSafe(|| {
        let _ = shared.telemetry(inp, Value::I64(1), &mut |_| {
            panic!("sink panic under lock");
        });
    }));
    assert!(caught.is_err());

    let prio = Priority::MANUAL_OPERATOR;
    assert_poisoned(shared.present_value(inp), "present_value");
    assert_poisoned(
        shared.telemetry(inp, Value::I64(2), &mut |_| {}),
        "telemetry",
    );
    assert_poisoned(
        shared.register_input(ValueKind::Bool, None),
        "register_input",
    );
    assert_poisoned(
        shared.register_output(Value::Bool(false)),
        "register_output",
    );
    assert_poisoned(shared.issue_lease(Millis(100)), "issue_lease");
    assert_poisoned(shared.renew(LeaseId(1)), "renew");
    assert_poisoned(shared.revoke(LeaseId(1), &mut |_| {}), "revoke");
    assert_poisoned(shared.expire(&mut |_| {}), "expire");
    assert_poisoned(
        shared.command(LeaseId(1), inp, prio, Value::I64(1), &mut |_| {}),
        "command",
    );
    assert_poisoned(
        shared.relinquish(LeaseId(1), inp, prio, &mut |_| {}),
        "relinquish",
    );
}

/// A kernel refusal comes back as `AdapterError::Kernel` with the operation name and the source.
#[test]
fn adapter_surfaces_kernel_error_with_op_and_source() {
    let shared = SharedKernel::new(Capacities::default());
    let err = shared.present_value(PointId(77)).unwrap_err();
    assert_eq!(
        err,
        AdapterError::Kernel {
            op: "present_value",
            source: KernelError::UnknownPoint,
        }
    );
    assert!(err.source().is_some());
    assert!(err.to_string().contains("present_value"));
}

/// A wrapped kernel keeps its lease deadlines: the caller's clock origin decides whether a lease is live.
#[test]
fn wrapped_kernel_uses_caller_clock_origin() {
    for (origin, expected) in [
        (10_000, Ok(())),
        (70_000, Err(KernelError::LeaseExpired)),
        (u64::MAX, Err(KernelError::LeaseExpired)),
    ] {
        let mut kernel = Kernel::new(Capacities::default());
        let point = kernel.register_output(Value::I64(0)).unwrap();
        let lease = kernel.issue_lease(Millis(60_000), Millis(10_000)).unwrap();
        let shared = SharedKernel::from_kernel(kernel, Millis(origin));
        let result = shared.command(
            lease,
            point,
            Priority::MANUAL_OPERATOR,
            Value::I64(1),
            &mut |_| {},
        );
        assert_eq!(
            result,
            expected.map_err(|source| AdapterError::Kernel {
                op: "command",
                source
            })
        );
    }
}

/// A sink re-entering its own adapter gets `Reentrant`, a different adapter still works, and the guard is restored afterwards.
#[test]
fn callbacks_reject_reentry_but_allow_other_adapter_and_restore_guard() {
    let first = SharedKernel::new(Capacities::default());
    let second = SharedKernel::new(Capacities::default());
    let a = first.register_input(ValueKind::I64, None).unwrap();
    let b = second.register_input(ValueKind::I64, None).unwrap();
    first
        .telemetry(a, Value::I64(1), &mut |_| {
            assert_eq!(
                first.telemetry(a, Value::I64(2), &mut |_| {}),
                Err(AdapterError::Reentrant { op: "telemetry" })
            );
            second
                .telemetry(b, Value::I64(2), &mut |_| {
                    assert_eq!(
                        first.present_value(a),
                        Err(AdapterError::Reentrant {
                            op: "present_value"
                        })
                    );
                })
                .unwrap();
        })
        .unwrap();
    assert_eq!(first.present_value(a), Ok(Some(Value::I64(1))));
}

/// Cross-adapter callbacks fail promptly while both outer calls hold their locks.
#[test]
fn cross_adapter_sinks_on_two_threads_get_contended() {
    let a = Arc::new(SharedKernel::default());
    let b = Arc::new(SharedKernel::default());
    let pa = a.register_input(ValueKind::I64, None).unwrap();
    let pb = b.register_input(ValueKind::I64, None).unwrap();
    let (ready_tx, ready_rx) = mpsc::channel();
    let (nested_tx, nested_rx) = mpsc::channel();
    let (outer_tx, outer_rx) = mpsc::channel();
    let (go_a, start_a) = mpsc::channel();
    let (go_b, start_b) = mpsc::channel();
    let (release_a, wait_a) = mpsc::channel();
    let (release_b, wait_b) = mpsc::channel();
    for (outer, inner, point, other_point, start, release) in [
        (Arc::clone(&a), Arc::clone(&b), pa, pb, start_a, wait_a),
        (Arc::clone(&b), Arc::clone(&a), pb, pa, start_b, wait_b),
    ] {
        let ready_tx = ready_tx.clone();
        let nested_tx = nested_tx.clone();
        let outer_tx = outer_tx.clone();
        thread::spawn(move || {
            let result = outer.telemetry(point, Value::I64(1), &mut |_| {
                ready_tx.send(()).unwrap();
                start.recv_timeout(Duration::from_secs(10)).unwrap();
                nested_tx.send(inner.present_value(other_point)).unwrap();
                release.recv_timeout(Duration::from_secs(10)).unwrap();
            });
            outer_tx.send(result).unwrap();
        });
    }
    for _ in 0..2 {
        ready_rx.recv_timeout(Duration::from_secs(10)).unwrap();
    }
    go_a.send(()).unwrap();
    go_b.send(()).unwrap();
    for _ in 0..2 {
        let result = nested_rx
            .recv_timeout(Duration::from_secs(10))
            .expect("deadlock");
        assert_eq!(
            result,
            Err(AdapterError::Contended {
                op: "present_value"
            })
        );
    }
    release_a.send(()).unwrap();
    release_b.send(()).unwrap();
    for _ in 0..2 {
        assert_eq!(
            outer_rx.recv_timeout(Duration::from_secs(10)).unwrap(),
            Ok(())
        );
    }
    assert_eq!(a.present_value(pa), Ok(Some(Value::I64(1))));
    assert_eq!(b.present_value(pb), Ok(Some(Value::I64(1))));
}

/// Returns the Linux caller's thread ID for its `/proc` state entry.
#[cfg(target_os = "linux")]
fn caller_tid() -> String {
    std::fs::read_link("/proc/thread-self")
        .unwrap_or_else(|error| panic!("cannot read caller thread ID: {error}"))
        .file_name()
        .unwrap_or_else(|| panic!("caller thread ID has no file name"))
        .to_string_lossy()
        .into_owned()
}

/// Returns an unused thread ID where thread state cannot be read portably.
#[cfg(not(target_os = "linux"))]
fn caller_tid() -> String {
    String::new()
}

/// Checks that the caller sleeps while the adapter lock is held.
///
/// Between sending its ID and its result, the caller has no blocking wait except
/// the adapter mutex, so state S with no result proves it waits for the lock.
/// An early return is caught here or by the final `Ok(Some)` assertion.
#[cfg(target_os = "linux")]
fn assert_caller_waits(tid: &str, value_rx: &mpsc::Receiver<Result<Option<Value>, AdapterError>>) {
    for _ in 0..1000 {
        match value_rx.try_recv() {
            Err(mpsc::TryRecvError::Empty) => {}
            result => panic!("caller returned or disconnected while lock held: {result:?}"),
        }
        let stat = std::fs::read_to_string(format!("/proc/self/task/{tid}/stat"))
            .unwrap_or_else(|error| panic!("cannot read caller thread state: {error}"));
        let fields = stat
            .rsplit_once(')')
            .unwrap_or_else(|| panic!("invalid caller thread stat: {stat}"))
            .1;
        let state = fields.split_whitespace().next();
        if state == Some("S") {
            return;
        }
        thread::sleep(Duration::from_millis(10));
    }
    panic!("caller did not sleep while waiting for the adapter lock");
}

/// Uses a bounded window because there is no portable thread-state read.
#[cfg(not(target_os = "linux"))]
fn assert_caller_waits(_tid: &str, value_rx: &mpsc::Receiver<Result<Option<Value>, AdapterError>>) {
    assert!(matches!(
        value_rx.recv_timeout(Duration::from_millis(500)),
        Err(mpsc::RecvTimeoutError::Timeout)
    ));
}

/// A top-level caller waits for another thread to release the adapter.
///
/// On Linux, observe the caller sleeping; elsewhere, check a bounded time window.
#[test]
fn top_level_call_waits_for_holder_instead_of_contended() {
    let adapter = Arc::new(SharedKernel::default());
    let point = adapter.register_input(ValueKind::I64, None).unwrap();
    let (holding_tx, holding_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let (result_tx, result_rx) = mpsc::channel();
    let holder = Arc::clone(&adapter);
    thread::spawn(move || {
        let result = holder.telemetry(point, Value::I64(1), &mut |_| {
            holding_tx.send(()).unwrap();
            release_rx.recv_timeout(Duration::from_secs(10)).unwrap();
        });
        result_tx.send(result).unwrap();
    });
    holding_rx.recv_timeout(Duration::from_secs(10)).unwrap();
    let (value_tx, value_rx) = mpsc::channel();
    let (started_tx, started_rx) = mpsc::channel();
    thread::spawn(move || {
        started_tx.send(caller_tid()).unwrap();
        value_tx.send(adapter.present_value(point)).unwrap();
    });
    let started = started_rx.recv_timeout(Duration::from_secs(10)).unwrap();
    assert_caller_waits(&started, &value_rx);
    release_tx.send(()).unwrap();
    assert_eq!(
        result_rx.recv_timeout(Duration::from_secs(10)).unwrap(),
        Ok(())
    );
    assert_eq!(
        value_rx.recv_timeout(Duration::from_secs(10)).unwrap(),
        Ok(Some(Value::I64(1)))
    );
}

/// A nested call into a different, poisoned adapter returns `Poisoned`, not `Contended`.
#[test]
fn nested_call_into_poisoned_other_adapter_returns_poisoned() {
    let first = SharedKernel::new(Capacities::default());
    let second = SharedKernel::new(Capacities::default());
    let a = first.register_input(ValueKind::I64, None).unwrap();
    let b = second.register_input(ValueKind::I64, None).unwrap();
    let caught = catch_unwind(AssertUnwindSafe(|| {
        let _ = second.telemetry(b, Value::I64(1), &mut |_| {
            panic!("sink panic under lock");
        });
    }));
    assert!(caught.is_err());
    first
        .telemetry(a, Value::I64(1), &mut |_| {
            assert_poisoned(second.present_value(b), "present_value");
        })
        .unwrap();
    assert_eq!(first.present_value(a), Ok(Some(Value::I64(1))));
}
