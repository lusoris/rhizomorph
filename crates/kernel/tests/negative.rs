// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Negative integration tests for `kernel`.

use kernel::{
    AssetId, AssetRevision, Capacities, CapacityKind, Kernel, KernelError, LeaseId, Millis,
    PointId, Priority, Revision, RevisionError, Value, ValueKind,
};

/// Exit check, negative: NaN and infinities are refused at telemetry, command and relinquish
/// default.
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

/// Exit check, negative: `Priority` 0 and 17 are refused.
#[test]
fn priority_zero_and_seventeen_refused() {
    assert_eq!(Priority::new(0), Err(KernelError::InvalidPriority));
    assert_eq!(Priority::new(17), Err(KernelError::InvalidPriority));
    assert_eq!(Priority::new(u8::MAX), Err(KernelError::InvalidPriority));
}

/// Exit check, negative: level 6 (Minimum On/Off) is refused for every external writer.
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

/// Exit check, negative: a lease cannot relinquish a slot another lease holds.
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

/// A command under a revoked lease is refused.
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

/// A second revoke and a revoke of a never-issued id change nothing and fire nothing.
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

/// Exit check, negative: a negative or non-finite deadband is refused at registration.
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

/// A deadband on a boolean input is refused at registration.
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

/// Exit check, negative: an `i64` and an `f64` of equal magnitude are not equal.
#[test]
fn different_value_kinds_never_equal_i64_not_equal_f64() {
    assert_ne!(Value::I64(1), Value::F64(1.0));
    assert_ne!(Value::I64(0), Value::F64(0.0));
    assert_ne!(Value::U16(1), Value::I64(1));
    assert_ne!(Value::Bool(true), Value::I64(1));
}

/// Registration past the points capacity is refused.
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

/// Issuing a lease past the leases capacity is refused.
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

/// A command to an input, telemetry for an output, a wrong value kind and an unknown point are each
/// refused.
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

/// D4: a zero ttl and a deadline past `u64::MAX` are refused.
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

/// D4: renewing an expired or an unknown lease is refused.
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

/// A panicking sink during revocation leaves no output commanded by the revoked lease.
#[test]
fn revocation_finishes_state_before_panicking_sink() {
    let mut k = kernel::Kernel::new(kernel::Capacities {
        points: 3,
        leases: 2,
        points_per_lease: 3,
    });
    let points: Vec<_> = (0..3)
        .map(|_| k.register_output(kernel::Value::I64(0)).unwrap())
        .collect();
    let lease = k
        .issue_lease(kernel::Millis(100), kernel::Millis(0))
        .unwrap();
    for &point in &points {
        k.command(
            lease,
            point,
            kernel::Priority::MANUAL_OPERATOR,
            kernel::Value::I64(1),
            kernel::Millis(0),
            &mut |_| {},
        )
        .unwrap();
    }
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        k.revoke(lease, &mut |_| panic!("sink")).unwrap();
    }));
    assert!(result.is_err());
    assert_eq!(
        k.lease_point_count(lease),
        Err(kernel::KernelError::UnknownLease)
    );
    let next = k
        .issue_lease(kernel::Millis(100), kernel::Millis(0))
        .unwrap();
    for point in points {
        assert_eq!(k.present_value(point), Ok(Some(kernel::Value::I64(0))));
        k.command(
            next,
            point,
            kernel::Priority::MANUAL_OPERATOR,
            kernel::Value::I64(2),
            kernel::Millis(0),
            &mut |_| {},
        )
        .unwrap();
    }
}

/// Exit check, negative: zero is not a valid revision.
#[test]
fn revision_zero_is_rejected() {
    assert_eq!(Revision::new(0), Err(RevisionError::Zero));
}

/// Exit check, negative: supersession requires the same subject and a higher revision.
#[test]
fn revision_supersession_requires_same_subject_and_higher_revision() {
    let first = AssetRevision::first(AssetId(1));
    let third = AssetRevision::new(AssetId(1), Revision::new(3).unwrap());
    let other = AssetRevision::first(AssetId(2));
    assert!(!first.supersedes(first));
    assert!(!first.supersedes(third));
    assert!(!third.supersedes(other));
}

/// Exit check, negative: revision errors have distinct nonempty descriptions.
#[test]
fn revision_error_descriptions_are_distinct() {
    let zero = RevisionError::Zero.to_string();
    let exhausted = RevisionError::Exhausted.to_string();
    assert_ne!(zero, "");
    assert_ne!(exhausted, "");
    assert_ne!(zero, exhausted);
}
