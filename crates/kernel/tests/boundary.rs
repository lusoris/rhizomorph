// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Boundary integration tests for `kernel`.

use core::mem::size_of;
use kernel::{
    Capacities, CapacityKind, CovEvent, Kernel, KernelError, LeaseId, Millis, Priority,
    PriorityArray, Value, ValueKind,
};

/// Exit check, boundary: `Priority` 1 and 16 are accepted and arbitrate.
#[test]
fn priority_one_and_sixteen_accepted() {
    let p1 = Priority::new(1).unwrap();
    let p16 = Priority::new(16).unwrap();
    assert_eq!(p1, Priority::MANUAL_LIFE_SAFETY);
    assert_eq!(p16, Priority::FALLBACK);

    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(lease, out, p16, Value::I64(16), Millis(10), &mut |_| {})
        .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(16)));

    k.command(lease, out, p1, Value::I64(1), Millis(20), &mut |_| {})
        .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(1)));
}

/// Exit check, boundary: lease ids 63, 64 and 65 are revoked independently, without collision.
#[test]
fn lease_ids_63_64_65_revoked_independently_without_collision() {
    let mut k = Kernel::new(Capacities {
        points: 8,
        leases: 70,
        points_per_lease: 4,
    });
    let out63 = k.register_output(Value::I64(0)).unwrap();
    let out64 = k.register_output(Value::I64(0)).unwrap();
    let out65 = k.register_output(Value::I64(0)).unwrap();

    for _ in 1..63 {
        k.issue_lease(Millis(1000), Millis(0)).unwrap();
    }
    let l63 = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let l64 = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let l65 = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    assert_eq!((l63.0, l64.0, l65.0), (63, 64, 65));

    let prio = Priority::MANUAL_OPERATOR;
    let now = Millis(10);
    k.command(l63, out63, prio, Value::I64(63), now, &mut |_| {})
        .unwrap();
    k.command(l64, out64, prio, Value::I64(64), now, &mut |_| {})
        .unwrap();
    k.command(l65, out65, prio, Value::I64(65), now, &mut |_| {})
        .unwrap();

    k.revoke(l64, &mut |_| {}).unwrap();
    assert_eq!(k.present_value(out63).unwrap(), Some(Value::I64(63)));
    assert_eq!(k.present_value(out64).unwrap(), Some(Value::I64(0)));
    assert_eq!(k.present_value(out65).unwrap(), Some(Value::I64(65)));
}

/// Exit check, boundary: deadband 0.0 fires on any change and drops identical values.
#[test]
fn deadband_zero_fires_on_change_and_drops_identical() {
    let mut k = Kernel::new(Capacities::default());
    let float_pt = k.register_input(ValueKind::F64, Some(0.0)).unwrap();
    let signed_pt = k.register_input(ValueKind::I64, Some(0.0)).unwrap();
    let mut events = Vec::new();

    k.telemetry(float_pt, Value::F64(1.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(float_pt, Value::F64(1.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(float_pt, Value::F64(1.0 + f64::EPSILON), &mut |e| {
        events.push(e);
    })
    .unwrap();

    k.telemetry(signed_pt, Value::I64(10), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(signed_pt, Value::I64(10), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(signed_pt, Value::I64(11), &mut |e| events.push(e))
        .unwrap();

    assert_eq!(events.len(), 4);
}

/// A difference exactly equal to the deadband fires, for `f64` and for `i64`.
#[test]
fn difference_exactly_equal_to_threshold_fires_f64_and_i64() {
    let mut k = Kernel::new(Capacities::default());
    let float_pt = k.register_input(ValueKind::F64, Some(5.0)).unwrap();
    let signed_pt = k.register_input(ValueKind::I64, Some(5.0)).unwrap();
    let mut events = Vec::new();

    k.telemetry(float_pt, Value::F64(10.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(float_pt, Value::F64(15.0), &mut |e| events.push(e))
        .unwrap();

    k.telemetry(signed_pt, Value::I64(10), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(signed_pt, Value::I64(14), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(signed_pt, Value::I64(15), &mut |e| events.push(e))
        .unwrap();

    assert_eq!(
        events,
        vec![
            CovEvent {
                point: float_pt,
                value: Value::F64(10.0)
            },
            CovEvent {
                point: float_pt,
                value: Value::F64(15.0)
            },
            CovEvent {
                point: signed_pt,
                value: Value::I64(10)
            },
            CovEvent {
                point: signed_pt,
                value: Value::I64(15)
            },
        ]
    );
}

/// An `i64` update one below the deadband sets the present value and fires nothing.
#[test]
fn i64_update_one_below_threshold_sets_present_value_and_fires_nothing() {
    let mut k = Kernel::new(Capacities::default());
    let signed_pt = k.register_input(ValueKind::I64, Some(5.0)).unwrap();
    let mut events = Vec::new();

    k.telemetry(signed_pt, Value::I64(10), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(signed_pt).unwrap(), Some(Value::I64(10)));
    assert_eq!(events.len(), 1);

    k.telemetry(signed_pt, Value::I64(14), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(signed_pt).unwrap(), Some(Value::I64(14)));
    assert_eq!(events.len(), 1);
}

/// -0.0 after 0.0 fires nothing, because the two compare equal.
#[test]
fn negative_zero_after_positive_zero_fires_nothing() {
    let mut k = Kernel::new(Capacities::default());
    let inp_none = k.register_input(ValueKind::F64, None).unwrap();
    let inp_zero = k.register_input(ValueKind::F64, Some(0.0)).unwrap();
    let mut events = Vec::new();

    k.telemetry(inp_none, Value::F64(0.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(inp_none, Value::F64(-0.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(inp_zero, Value::F64(0.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(inp_zero, Value::F64(-0.0), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(events.len(), 2);
}

/// The `i64::MIN` to `i64::MAX` difference compares exactly against deadbands of 0, 2^63 and 2^64.
#[test]
#[expect(
    clippy::cast_precision_loss,
    reason = "the test builds deadbands from integer bounds on purpose"
)]
fn i64_min_to_max_exact_deadband_comparison() {
    let mut k = Kernel::new(Capacities::default());
    let p_zero = k.register_input(ValueKind::I64, Some(0.0)).unwrap();
    let p_2p63 = k
        .register_input(ValueKind::I64, Some(9_223_372_036_854_775_808.0))
        .unwrap();
    let threshold_2p64 = u64::MAX as f64;
    let p_2p64 = k
        .register_input(ValueKind::I64, Some(threshold_2p64))
        .unwrap();

    for p in [p_zero, p_2p63, p_2p64] {
        k.telemetry(p, Value::I64(i64::MIN), &mut |_| {}).unwrap();
    }

    let mut events = Vec::new();
    k.telemetry(p_zero, Value::I64(i64::MAX), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(p_2p63, Value::I64(i64::MAX), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(p_2p64, Value::I64(i64::MAX), &mut |e| events.push(e))
        .unwrap();

    assert_eq!(
        events,
        vec![
            CovEvent {
                point: p_zero,
                value: Value::I64(i64::MAX)
            },
            CovEvent {
                point: p_2p63,
                value: Value::I64(i64::MAX)
            },
        ]
    );
}

/// D5: points, leases and the per-lease index fill to capacity, then refuse without changing state.
#[test]
fn arena_lease_table_and_per_lease_index_filled_to_capacity_then_refused() {
    let caps = Capacities {
        points: 3,
        leases: 2,
        points_per_lease: 2,
    };
    let mut k = Kernel::new(caps);
    let p0 = k.register_output(Value::I64(0)).unwrap();
    let p1 = k.register_output(Value::I64(0)).unwrap();
    let p2 = k.register_output(Value::I64(0)).unwrap();
    assert_eq!(
        k.register_output(Value::I64(0)),
        Err(KernelError::CapacityExceeded(CapacityKind::Points))
    );

    let l1 = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let _l2 = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    assert_eq!(
        k.issue_lease(Millis(1000), Millis(0)),
        Err(KernelError::CapacityExceeded(CapacityKind::Leases))
    );

    let prio = Priority::MANUAL_OPERATOR;
    let now = Millis(10);
    k.command(l1, p0, prio, Value::I64(1), now, &mut |_| {})
        .unwrap();
    k.command(l1, p1, prio, Value::I64(2), now, &mut |_| {})
        .unwrap();
    k.command(l1, p1, Priority::SCHEDULE, Value::I64(3), now, &mut |_| {})
        .unwrap();
    assert_eq!(
        k.command(l1, p2, prio, Value::I64(4), now, &mut |_| {}),
        Err(KernelError::CapacityExceeded(CapacityKind::PointsPerLease))
    );
    assert_eq!(k.present_value(p2).unwrap(), Some(Value::I64(0)));
}

/// D7: `u32::MAX` is the last lease id; the next issue is refused without wrapping.
#[test]
fn lease_id_exhaustion_at_u32_max() {
    let mut k = Kernel::new(Capacities {
        points: 2,
        leases: 4,
        points_per_lease: 2,
    })
    .with_next_lease_id(u32::MAX - 1);

    let id1 = k.issue_lease(Millis(100), Millis(0)).unwrap();
    let id2 = k.issue_lease(Millis(100), Millis(0)).unwrap();
    assert_eq!(id1, LeaseId(u32::MAX - 1));
    assert_eq!(id2, LeaseId(u32::MAX));
    assert_eq!(
        k.issue_lease(Millis(100), Millis(0)),
        Err(KernelError::LeaseIdsExhausted)
    );
}

/// D7: the test helper `with_next_lease_id` never moves the lease counter backward.
#[test]
fn lease_counter_helper_never_moves_backward() {
    let mut k = Kernel::new(Capacities {
        points: 2,
        leases: 4,
        points_per_lease: 2,
    });
    let first = k.issue_lease(Millis(100), Millis(0)).unwrap();
    assert_eq!(first, LeaseId(1));

    let mut k = k.with_next_lease_id(1);
    let second = k.issue_lease(Millis(100), Millis(0)).unwrap();
    assert_eq!(second, LeaseId(2));

    let mut k = k.with_next_lease_id(0);
    let third = k.issue_lease(Millis(100), Millis(0)).unwrap();
    assert_eq!(third, LeaseId(3));
}

/// D7: an exhausted lease counter stays exhausted under the test helper.
#[test]
fn exhausted_lease_counter_stays_exhausted() {
    let mut k = Kernel::new(Capacities {
        points: 2,
        leases: 4,
        points_per_lease: 2,
    })
    .with_next_lease_id(u32::MAX);
    assert_eq!(k.issue_lease(Millis(100), Millis(0)), Ok(LeaseId(u32::MAX)));

    let mut k = k.with_next_lease_id(1);
    assert_eq!(
        k.issue_lease(Millis(100), Millis(0)),
        Err(KernelError::LeaseIdsExhausted)
    );
}

/// Exit check, boundary: `PriorityArray` is 384 bytes on `x86_64`.
#[cfg(target_arch = "x86_64")]
#[test]
fn priority_array_size_is_384_bytes_on_x86_64() {
    assert_eq!(size_of::<Value>(), 16);
    assert_eq!(size_of::<Option<(LeaseId, Value)>>(), 24);
    assert_eq!(size_of::<PriorityArray>(), 384);
}

/// Exit check, boundary: revoking a lease that holds one point among many visits only that point.
#[test]
fn revoke_of_lease_holding_one_point_among_many_visits_only_that_point() {
    let mut k = Kernel::new(Capacities {
        points: 128,
        leases: 4,
        points_per_lease: 8,
    });
    let mut target = None;
    for idx in 0..64 {
        let p = k.register_output(Value::I64(0)).unwrap();
        if idx == 37 {
            target = Some(p);
        }
    }
    let chosen = target.unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    k.command(
        lease,
        chosen,
        Priority::MANUAL_OPERATOR,
        Value::I64(99),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();

    let visited = k.revoke(lease, &mut |_| {}).unwrap();
    assert_eq!(visited, 1);
}
