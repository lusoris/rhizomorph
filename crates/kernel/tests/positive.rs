// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Positive integration tests for `kernel`.

use kernel::{
    Capacities, CovEvent, Kernel, KernelError, LeaseId, Millis, PointId, Priority, Value, ValueKind,
};

/// Exit check, positive: the lowest level number holding a value wins.
#[test]
fn lowest_priority_level_wins() {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_a,
        out,
        Priority::SCHEDULE,
        Value::I64(120),
        Millis(10),
        &mut |e| events.push(e),
    )
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(120)));

    k.command(
        lease_b,
        out,
        Priority::MANUAL_OPERATOR,
        Value::I64(80),
        Millis(20),
        &mut |e| events.push(e),
    )
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(80)));
    assert_eq!(
        events,
        vec![
            CovEvent {
                point: out,
                value: Value::I64(120)
            },
            CovEvent {
                point: out,
                value: Value::I64(80)
            },
        ]
    );
}

/// Exit check, positive: relinquishing the winning slot falls back to the next held slot.
#[test]
fn relinquish_winning_slot_falls_back_to_next_slot() {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_a,
        out,
        Priority::SCHEDULE,
        Value::I64(120),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    k.command(
        lease_b,
        out,
        Priority::MANUAL_OPERATOR,
        Value::I64(80),
        Millis(20),
        &mut |_| {},
    )
    .unwrap();

    k.relinquish(
        lease_b,
        out,
        Priority::MANUAL_OPERATOR,
        Millis(30),
        &mut |e| events.push(e),
    )
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(120)));
    assert_eq!(
        events,
        vec![CovEvent {
            point: out,
            value: Value::I64(120)
        }]
    );
}

/// Exit check, positive: an update inside the deadband sets the present value and fires no COV
/// event; one at or past it fires.
#[test]
fn deadband_below_threshold_fires_nothing_at_and_above_fires() {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let inp = k.register_input(ValueKind::F64, Some(2.0)).unwrap();

    k.telemetry(inp, Value::F64(20.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(inp, Value::F64(21.5), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(21.5)));

    k.telemetry(inp, Value::F64(22.0), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(events.len(), 2);
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(22.0)));

    k.telemetry(inp, Value::F64(19.0), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(events.len(), 3);
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(19.0)));
}

/// Updates below the deadband set the present value without firing COV, and later updates compare
/// against the last reported value.
#[test]
fn deadband_sets_present_value_and_compares_against_last_reported() {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let inp = k.register_input(ValueKind::F64, Some(1.0)).unwrap();

    k.telemetry(inp, Value::F64(0.0), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(0.0)));
    assert_eq!(events.len(), 1);

    k.telemetry(inp, Value::F64(0.5), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(0.5)));
    assert_eq!(events.len(), 1);

    k.telemetry(inp, Value::F64(1.2), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(1.2)));
    assert_eq!(events.len(), 2);

    k.telemetry(inp, Value::F64(1.5), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(k.present_value(inp).unwrap(), Some(Value::F64(1.5)));
    assert_eq!(
        events,
        vec![
            CovEvent {
                point: inp,
                value: Value::F64(0.0)
            },
            CovEvent {
                point: inp,
                value: Value::F64(1.2)
            },
        ]
    );
}

/// The first telemetry update of an input fires COV whatever its deadband.
#[test]
fn first_update_always_fires() {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let bool_pt = k.register_input(ValueKind::Bool, None).unwrap();
    let float_pt = k.register_input(ValueKind::F64, Some(1000.0)).unwrap();
    let signed_pt = k.register_input(ValueKind::I64, Some(500.0)).unwrap();
    let word_pt = k.register_input(ValueKind::U16, Some(100.0)).unwrap();

    k.telemetry(bool_pt, Value::Bool(false), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(float_pt, Value::F64(0.0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(signed_pt, Value::I64(0), &mut |e| events.push(e))
        .unwrap();
    k.telemetry(word_pt, Value::U16(0), &mut |e| events.push(e))
        .unwrap();
    assert_eq!(events.len(), 4);
}

/// Exit check, positive: revoke clears every slot of the lease and fires COV for each changed
/// value.
#[test]
fn revoke_clears_all_slots_of_lease_and_fires_cov_per_changed_value() {
    let mut k = Kernel::new(Capacities::default());
    let out1 = k.register_output(Value::I64(10)).unwrap();
    let out2 = k.register_output(Value::I64(20)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let p_op = Priority::MANUAL_OPERATOR;
    let p_sched = Priority::SCHEDULE;
    let now = Millis(10);

    k.command(lease_a, out1, p_op, Value::I64(100), now, &mut |_| {})
        .unwrap();
    k.command(lease_a, out1, p_sched, Value::I64(110), now, &mut |_| {})
        .unwrap();
    k.command(lease_a, out2, p_sched, Value::I64(200), now, &mut |_| {})
        .unwrap();
    k.command(lease_b, out2, p_op, Value::I64(250), now, &mut |_| {})
        .unwrap();

    let mut events = Vec::new();
    let visited = k.revoke(lease_a, &mut |e| events.push(e)).unwrap();
    assert_eq!(visited, 2);
    assert_eq!(k.present_value(out1).unwrap(), Some(Value::I64(10)));
    assert_eq!(k.present_value(out2).unwrap(), Some(Value::I64(250)));
    assert_eq!(
        events,
        vec![CovEvent {
            point: out1,
            value: Value::I64(10)
        }]
    );
}

/// Exit check, positive: the last relinquish sets the relinquish default and fires COV.
#[test]
fn last_relinquish_sets_relinquish_default_and_fires_cov() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::F64(18.5)).unwrap();
    let lease = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease,
        out,
        Priority::CONTROL_LOOP,
        Value::F64(21.0),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::F64(21.0)));

    let mut events = Vec::new();
    k.relinquish(lease, out, Priority::CONTROL_LOOP, Millis(20), &mut |e| {
        events.push(e);
    })
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::F64(18.5)));
    assert_eq!(
        events,
        vec![CovEvent {
            point: out,
            value: Value::F64(18.5)
        }]
    );
}

/// A write below the winning level fires nothing and leaves the present value unchanged.
#[test]
fn write_to_non_winning_slot_fires_nothing_and_leaves_present_value() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::U16(0)).unwrap();
    let lease_high = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_low = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_high,
        out,
        Priority::MANUAL_OPERATOR,
        Value::U16(50),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();

    let mut events = Vec::new();
    k.command(
        lease_low,
        out,
        Priority::FALLBACK,
        Value::U16(99),
        Millis(20),
        &mut |e| events.push(e),
    )
    .unwrap();
    assert_eq!(events, Vec::new());
    assert_eq!(k.present_value(out).unwrap(), Some(Value::U16(50)));
}

/// Runs one fixed lease sequence with every passed time shifted by `offset`.
fn run_timed_sequence(offset: u64) -> Result<(Vec<CovEvent>, Option<Value>), KernelError> {
    let mut k = Kernel::new(Capacities::default());
    let mut events = Vec::new();
    let out = k.register_output(Value::I64(0))?;
    let l1 = k.issue_lease(Millis(100), Millis(offset + 10))?;
    let l2 = k.issue_lease(Millis(200), Millis(offset + 10))?;

    k.command(
        l1,
        out,
        Priority::MANUAL_OPERATOR,
        Value::I64(1),
        Millis(offset + 50),
        &mut |e| events.push(e),
    )?;
    k.command(
        l2,
        out,
        Priority::SCHEDULE,
        Value::I64(2),
        Millis(offset + 60),
        &mut |e| events.push(e),
    )?;
    k.renew(l1, Millis(offset + 80))?;
    k.expire(Millis(offset + 180), &mut |e| events.push(e));
    Ok((events, k.present_value(out)?))
}

/// D2: shifting every passed time by one offset gives the same results, so the core reads no clock.
#[test]
fn core_takes_time_only_as_passed_value_offset_invariance() {
    let (events_a, val_a) = run_timed_sequence(0).unwrap();
    let (events_b, val_b) = run_timed_sequence(5_000_000).unwrap();
    assert_eq!(events_a, events_b);
    assert_eq!(val_a, val_b);
    assert_eq!(val_a, Some(Value::I64(2)));
}

/// D3: a command over another lease's slot replaces it and drops that lease's index entry when it
/// holds no other slot on the point.
#[test]
fn d3_command_replaces_other_lease_slot_drops_index_when_none_left() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_a,
        out,
        Priority::CONTROL_LOOP,
        Value::I64(10),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    assert_eq!(k.lease_point_count(lease_a).unwrap(), 1);

    k.command(
        lease_b,
        out,
        Priority::CONTROL_LOOP,
        Value::I64(20),
        Millis(20),
        &mut |_| {},
    )
    .unwrap();
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(20)));
    assert_eq!(k.lease_point_count(lease_a).unwrap(), 0);
    assert_eq!(k.lease_point_count(lease_b).unwrap(), 1);

    let err = k
        .relinquish(
            lease_a,
            out,
            Priority::CONTROL_LOOP,
            Millis(30),
            &mut |_| {},
        )
        .unwrap_err();
    assert_eq!(err, KernelError::SlotNotHeld);
    assert_eq!(k.revoke(lease_a, &mut |_| {}).unwrap(), 0);
}

/// D3: the displaced lease keeps its index entry while it still holds another slot on the point.
#[test]
fn d3_command_replaces_other_lease_slot_keeps_index_when_other_slot_held() {
    let mut k = Kernel::new(Capacities::default());
    let out = k.register_output(Value::I64(0)).unwrap();
    let lease_a: LeaseId = k.issue_lease(Millis(1000), Millis(0)).unwrap();
    let lease_b: LeaseId = k.issue_lease(Millis(1000), Millis(0)).unwrap();

    k.command(
        lease_a,
        out,
        Priority::CONTROL_LOOP,
        Value::I64(10),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    k.command(
        lease_a,
        out,
        Priority::SCHEDULE,
        Value::I64(12),
        Millis(10),
        &mut |_| {},
    )
    .unwrap();
    k.command(
        lease_b,
        out,
        Priority::CONTROL_LOOP,
        Value::I64(20),
        Millis(20),
        &mut |_| {},
    )
    .unwrap();

    assert_eq!(k.lease_point_count(lease_a).unwrap(), 1);
    assert_eq!(
        k.relinquish(
            lease_a,
            out,
            Priority::CONTROL_LOOP,
            Millis(30),
            &mut |_| {}
        ),
        Err(KernelError::SlotNotHeld)
    );
    k.relinquish(lease_a, out, Priority::SCHEDULE, Millis(30), &mut |_| {})
        .unwrap();
    assert_eq!(k.lease_point_count(lease_a).unwrap(), 0);
}

/// Registers one output and issues one lease with ttl 100 at time 1000.
fn setup_expiry_check(k: &mut Kernel) -> Result<(PointId, LeaseId), KernelError> {
    let out = k.register_output(Value::I64(0))?;
    let lease = k.issue_lease(Millis(100), Millis(1000))?;
    Ok((out, lease))
}

/// D4: a lease is live before its deadline and expired at it; renew extends it and expire revokes
/// it.
#[test]
fn d4_lease_expiry_live_and_expired_boundaries_renew_and_expire() {
    let mut k = Kernel::new(Capacities::default());
    let (out, lease) = setup_expiry_check(&mut k).unwrap();
    let prio = Priority::MANUAL_OPERATOR;

    k.command(lease, out, prio, Value::I64(42), Millis(1099), &mut |_| {})
        .unwrap();
    assert_eq!(
        k.command(lease, out, prio, Value::I64(43), Millis(1100), &mut |_| {}),
        Err(KernelError::LeaseExpired)
    );
    assert_eq!(
        k.relinquish(lease, out, prio, Millis(1101), &mut |_| {}),
        Err(KernelError::LeaseExpired)
    );

    k.renew(lease, Millis(1050)).unwrap();
    k.command(lease, out, prio, Value::I64(55), Millis(1149), &mut |_| {})
        .unwrap();

    let mut events = Vec::new();
    assert_eq!(k.expire(Millis(1150), &mut |e| events.push(e)), 1);
    assert_eq!(k.present_value(out).unwrap(), Some(Value::I64(0)));
    assert_eq!(
        events,
        vec![CovEvent {
            point: out,
            value: Value::I64(0)
        }]
    );
}

/// Revocation emits one COV event per changed output, in point index order.
#[test]
fn revoke_emits_changed_points_in_index_order() {
    let mut k = kernel::Kernel::new(kernel::Capacities {
        points: 3,
        leases: 1,
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
    let mut events = Vec::new();
    k.revoke(lease, &mut |event| events.push(event.point))
        .unwrap();
    assert_eq!(events, points);
}
