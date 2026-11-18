// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Negative integration tests for `kernel`.

use kernel::{
    Capacities, CapacityKind, Kernel, KernelError, LeaseId, Millis, PointId, Priority, Value,
    ValueKind,
};

#[test]
fn nan_and_infinities_refused_at_telemetry_command_and_relinquish_default() {
    let mut k = Kernel::new(Capacities::default());
    let inp = k.register_input(ValueKind::F64, None).unwrap();
    let out = k.register_output(Value::F64(0.0)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    for bad in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(
            k.register_output(Value::F64(bad)),
            Err(KernelError::NonFinite)
        );
        assert_eq!(
            k.telemetry(inp, Value::F64(bad), &mut |_| {}),
            Err(KernelError::NonFinite)
        );
        assert_eq!(
            k.command(
                lease,
                out,
                Priority::MANUAL_OPERATOR,
                Value::F64(bad),
                Millis(10),
                &mut |_| {}
            ),
            Err(KernelError::NonFinite)
        );
    }
}

#[test]
fn priority_zero_and_seventeen_refused() {
    assert_eq!(Priority::new(0), Err(KernelError::InvalidPriority));
    assert_eq!(Priority::new(17), Err(KernelError::InvalidPriority));
    assert_eq!(Priority::new(u8::MAX), Err(KernelError::InvalidPriority));
}

#[test]
fn priority_six_minimum_on_off_refused() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::Bool(false)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    assert_eq!(
        k.command(
            lease,
            out,
            Priority::MINIMUM_ON_OFF,
            Value::Bool(true),
            Millis(10),
            &mut |_| {}
        ),
        Err(KernelError::ReservedPriority)
    );
    assert_eq!(
        k.relinquish(
            lease,
            out,
            Priority::MINIMUM_ON_OFF,
            Millis(10),
            &mut |_| {}
        ),
        Err(KernelError::ReservedPriority)
    );
}

#[test]
fn lease_cannot_clear_another_leases_slot() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_a,
        out,
        Priority::MANUAL_OPERATOR,
        Value::I64(10),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    assert_eq!(
        k.relinquish(
            lease_b,
            out,
            Priority::MANUAL_OPERATOR,
            Millis(20),
            &mut |_| {}
        ),
        Err(KernelError::SlotNotHeld)
    );
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(10)));
}

#[test]
fn write_under_revoked_lease_refused() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    k.revoke(lease, &mut |_| {}).unwrap();

    assert_eq!(
        k.command(
            lease,
            out,
            Priority::MANUAL_OPERATOR,
            Value::I64(5),
            Millis(10),
            &mut |_| {}
        ),
        Err(KernelError::UnknownLease)
    );
    assert_eq!(
        k.relinquish(
            lease,
            out,
            Priority::MANUAL_OPERATOR,
            Millis(10),
            &mut |_| {}
        ),
        Err(KernelError::UnknownLease)
    );
}

#[test]
fn double_revoke_and_never_issued_id_change_nothing_and_fire_nothing() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_b,
        out,
        Priority::MANUAL_OPERATOR,
        Value::I64(77),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    k.revoke(lease_a, &mut |_| {}).unwrap();

    let mut events = Vec::new();
    assert_eq!(
        k.revoke(lease_a, &mut |e| events.push(e)),
        Err(KernelError::UnknownLease)
    );
    assert_eq!(
        k.revoke(LeaseId(999), &mut |e| events.push(e)),
        Err(KernelError::UnknownLease)
    );
    assert_eq!(events, Vec::new());
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(77)));
}

#[test]
fn negative_nan_and_infinite_deadband_refused() {
    let mut k = Kernel::new(Capacities::default());
    for bad in [-0.001, -1.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(
            k.register_input(ValueKind::F64, Some(bad)),
            Err(KernelError::InvalidDeadband)
        );
        assert_eq!(
            k.register_input(ValueKind::I64, Some(bad)),
            Err(KernelError::InvalidDeadband)
        );
    }
}

#[test]
fn deadband_on_bool_refused() {
    let mut k = Kernel::new(Capacities::default());
    assert_eq!(
        k.register_input(ValueKind::Bool, Some(0.0)),
        Err(KernelError::InvalidDeadband)
    );
    assert_eq!(
        k.register_input(ValueKind::Bool, Some(1.0)),
        Err(KernelError::InvalidDeadband)
    );
}

#[test]
fn different_value_kinds_never_equal_i64_not_equal_f64() {
    assert_ne!(Value::I64(1), Value::F64(1.0));
    assert_ne!(Value::I64(0), Value::F64(0.0));
    assert_ne!(Value::U16(1), Value::I64(1));
    assert_ne!(Value::Bool(true), Value::I64(1));
}

#[test]
fn registration_past_points_capacity_refused() {
    let mut k = Kernel::new(Capacities {
        points: 2,
        leases: 2,
        points_per_lease: 2,
    });
    k.register_input(ValueKind::I64, None).unwrap();
    k.register_output(Value::I64(0)).unwrap();

    assert_eq!(
        k.register_input(ValueKind::Bool, None),
        Err(KernelError::CapacityExceeded(CapacityKind::Points))
    );
    assert_eq!(
        k.register_output(Value::Bool(false)),
        Err(KernelError::CapacityExceeded(CapacityKind::Points))
    );
}

#[test]
fn lease_past_leases_capacity_refused() {
    let mut k = Kernel::new(Capacities {
        points: 2,
        leases: 2,
        points_per_lease: 2,
    });
    k.issue_lease(Millis(100), Millis(0)).unwrap();
    k.issue_lease(Millis(100), Millis(0)).unwrap();

    assert_eq!(
        k.issue_lease(Millis(100), Millis(0)),
        Err(KernelError::CapacityExceeded(CapacityKind::Leases))
    );
}

#[test]
fn command_to_input_telemetry_for_output_wrong_kind_and_unknown_point_refused() {
    let mut k = Kernel::new(Capacities::default());
    let inp = k.register_input(ValueKind::I64, None).unwrap();
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let prio = Priority::MANUAL_OPERATOR;
    let now = Millis(10);

    assert_eq!(
        k.command(lease, inp, prio, Value::I64(1), now, &mut |_| {}),
        Err(KernelError::WrongPointType)
    );
    assert_eq!(
        k.telemetry(out, Value::I64(1), &mut |_| {}),
        Err(KernelError::WrongPointType)
    );
    assert_eq!(
        k.telemetry(inp, Value::F64(1.0), &mut |_| {}),
        Err(KernelError::KindMismatch)
    );
    assert_eq!(
        k.command(lease, out, prio, Value::Bool(true), now, &mut |_| {}),
        Err(KernelError::KindMismatch)
    );
    assert_eq!(
        k.telemetry(PointId(99), Value::I64(1), &mut |_| {}),
        Err(KernelError::UnknownPoint)
    );
    assert_eq!(
        k.command(lease, PointId(99), prio, Value::I64(1), now, &mut |_| {}),
        Err(KernelError::UnknownPoint)
    );
}

#[test]
fn ttl_zero_and_deadline_overflow_refused() {
    let mut k = Kernel::new(Capacities::default());
    assert_eq!(
        k.issue_lease(Millis(0), Millis(100)),
        Err(KernelError::InvalidTtl)
    );
    assert_eq!(
        k.issue_lease(Millis(10), Millis(u64::MAX - 5)),
        Err(KernelError::InvalidTtl)
    );
}

#[test]
fn renew_of_expired_or_unknown_lease_refused() {
    let mut k = Kernel::new(Capacities::default());
    let lease = k.issue_lease(Millis(100), Millis(500)).unwrap();

    assert_eq!(k.renew(lease, Millis(600)), Err(KernelError::LeaseExpired));
    assert_eq!(k.renew(lease, Millis(601)), Err(KernelError::LeaseExpired));
    assert_eq!(
        k.renew(LeaseId(404), Millis(510)),
        Err(KernelError::UnknownLease)
    );
}
