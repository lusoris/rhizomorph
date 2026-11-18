// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Integration tests for `kernel-std` adapter (`SharedKernel` and `AdapterError`).

use std::error::Error;
use std::panic::{AssertUnwindSafe, catch_unwind};

use kernel_std::{
    AdapterError, Capacities, CovEvent, KernelError, LeaseId, Millis, PointId, Priority,
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
