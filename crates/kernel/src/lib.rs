// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Tier-0 `no_std` arbitration kernel: point arena, 16-level priority arrays,
//! time-bounded writer leases, deadband filtering, and change-of-value (COV) emission.

#![no_std]

extern crate alloc;

use alloc::vec::Vec;
use core::fmt;

/// Default maximum number of points in the kernel arena.
pub const DEFAULT_POINTS: usize = 4096;

/// Default maximum number of concurrent active writer leases.
pub const DEFAULT_LEASES: usize = 256;

/// Default maximum number of points indexed per active lease.
pub const DEFAULT_POINTS_PER_LEASE: usize = 1024;

/// Constant `2^64` as `f64`; no `u64` difference can reach or exceed this bound.
const TWO_POW_64: f64 = 18_446_744_073_709_551_616.0;

/// Monotonic time in milliseconds passed into the kernel by the caller.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Millis(pub u64);

impl Millis {
    /// Creates a monotonic millisecond value.
    #[must_use]
    pub const fn new(ms: u64) -> Self {
        Self(ms)
    }

    /// Returns the raw millisecond count.
    #[must_use]
    pub const fn as_u64(self) -> u64 {
        self.0
    }
}

/// Dense identifier for a registered point in the arena.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PointId(pub u32);

impl PointId {
    /// Returns the raw numeric identifier.
    #[must_use]
    pub const fn as_u32(self) -> u32 {
        self.0
    }
}

/// Host-assigned lease identifier for a writer.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct LeaseId(pub u32);

impl LeaseId {
    /// Returns the raw numeric identifier.
    #[must_use]
    pub const fn as_u32(self) -> u32 {
        self.0
    }
}

/// Discriminant for [`Value`] variants.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ValueKind {
    /// Boolean state (`bool`).
    Bool,
    /// Signed 64-bit integer (`i64`).
    I64,
    /// IEEE 754 double-precision float (`f64`), restricted to finite values.
    F64,
    /// Unsigned 16-bit integer (`u16`).
    U16,
}

/// Point value carried by telemetry, priority slots, and COV events.
///
/// Values of different kinds are never equal (`Value::I64(1) != Value::F64(1.0)`).
/// Floating-point values follow IEEE 754 equality (`-0.0 == 0.0`); `NaN` and
/// infinities are refused at every ingress and never stored.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Value {
    /// Boolean value.
    Bool(bool),
    /// Signed 64-bit integer value.
    I64(i64),
    /// Finite 64-bit floating-point value.
    F64(f64),
    /// Unsigned 16-bit integer value.
    U16(u16),
}

impl Value {
    /// Returns the [`ValueKind`] of this value.
    #[must_use]
    pub const fn kind(self) -> ValueKind {
        match self {
            Self::Bool(_) => ValueKind::Bool,
            Self::I64(_) => ValueKind::I64,
            Self::F64(_) => ValueKind::F64,
            Self::U16(_) => ValueKind::U16,
        }
    }

    /// Returns `true` if the value is allowed at ingress (all non-float values,
    /// and finite `f64` values).
    #[must_use]
    pub fn is_valid(self) -> bool {
        match self {
            Self::F64(v) => v.is_finite(),
            Self::Bool(_) | Self::I64(_) | Self::U16(_) => true,
        }
    }
}

/// Validated priority level in `1..=16` (lowest level number wins).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Priority(u8);

impl Priority {
    /// Level 1: Manual-Life Safety (ASHRAE 135 Clause 19.2 Table 19-1 standard name).
    pub const MANUAL_LIFE_SAFETY: Self = Self(1);

    /// Level 2: Automatic-Life Safety (ASHRAE 135 Clause 19.2 Table 19-1 standard name).
    pub const AUTOMATIC_LIFE_SAFETY: Self = Self(2);

    /// Level 5: Critical Equipment Control (ASHRAE 135 Clause 19.2 Table 19-1 standard name).
    pub const CRITICAL_EQUIPMENT_CONTROL: Self = Self(5);

    /// Level 6: Minimum On/Off (ASHRAE 135 Clause 19.2 Table 19-1 standard name).
    /// Reserved for the kernel minimum on/off algorithm; refused for external callers.
    pub const MINIMUM_ON_OFF: Self = Self(6);

    /// Level 8: Manual Operator (ASHRAE 135 Clause 19.2 Table 19-1 standard name).
    pub const MANUAL_OPERATOR: Self = Self(8);

    /// Level 10: Feedback controller priority; project convention on a free level,
    /// not an ASHRAE 135 standard name.
    pub const CONTROL_LOOP: Self = Self(10);

    /// Level 12: Schedule priority; project convention on a free level,
    /// not an ASHRAE 135 standard name.
    pub const SCHEDULE: Self = Self(12);

    /// Level 16: Fallback writer priority; project convention on a free level,
    /// not an ASHRAE 135 standard name.
    pub const FALLBACK: Self = Self(16);

    /// Validates that `level` is in `1..=16`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::InvalidPriority`] if `level` is `0` or greater than `16`.
    pub const fn new(level: u8) -> Result<Self, KernelError> {
        if level >= 1 && level <= 16 {
            Ok(Self(level))
        } else {
            Err(KernelError::InvalidPriority)
        }
    }

    /// Returns the numeric priority level in `1..=16`.
    #[must_use]
    pub const fn get(self) -> u8 {
        self.0
    }

    #[must_use]
    const fn slot_index(self) -> usize {
        (self.0 - 1) as usize
    }
}

/// 16-level BACnet-style priority array for a commandable output point.
#[derive(Debug, Clone, PartialEq)]
pub struct PriorityArray([Option<(LeaseId, Value)>; 16]);

impl Default for PriorityArray {
    fn default() -> Self {
        Self::new()
    }
}

impl PriorityArray {
    /// Creates an empty 16-slot priority array.
    #[must_use]
    pub const fn new() -> Self {
        Self([None; 16])
    }

    /// Returns a reference to the 16 underlying slots (index 0 is level 1).
    #[must_use]
    pub const fn slots(&self) -> &[Option<(LeaseId, Value)>; 16] {
        &self.0
    }

    /// Returns the occupant of the given priority slot.
    #[must_use]
    pub fn slot(&self, priority: Priority) -> Option<(LeaseId, Value)> {
        self.0.get(priority.slot_index()).copied().flatten()
    }

    /// Resolves the winning `(LeaseId, Value)` by scanning levels 1 through 16.
    #[must_use]
    pub fn resolve(&self) -> Option<(LeaseId, Value)> {
        for slot in &self.0 {
            if let Some(entry) = *slot {
                return Some(entry);
            }
        }
        None
    }

    /// Resolves the effective present value, falling back to `relinquish_default`
    /// when all 16 slots are empty.
    #[must_use]
    pub fn resolve_value(&self, relinquish_default: Value) -> Value {
        self.resolve().map_or(relinquish_default, |(_, v)| v)
    }

    fn set_slot(&mut self, priority: Priority, entry: Option<(LeaseId, Value)>) {
        if let Some(slot) = self.0.get_mut(priority.slot_index()) {
            *slot = entry;
        }
    }

    fn lease_holds_any(&self, lease: LeaseId) -> bool {
        for slot in &self.0 {
            if let Some((holder, _)) = *slot
                && holder == lease
            {
                return true;
            }
        }
        false
    }

    fn clear_lease_slots(&mut self, lease: LeaseId) {
        for slot in &mut self.0 {
            if let Some((holder, _)) = *slot
                && holder == lease
            {
                *slot = None;
            }
        }
    }
}

/// Change-of-value notification emitted when a point's present value changes.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CovEvent {
    /// Identifier of the point that changed.
    pub point: PointId,
    /// New present value of the point.
    pub value: Value,
}

/// Pre-allocated arena and lease capacities for [`Kernel::new`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Capacities {
    /// Maximum number of points (`register_input` + `register_output`).
    pub points: usize,
    /// Maximum number of concurrent active leases.
    pub leases: usize,
    /// Maximum number of points a single lease may hold simultaneously.
    pub points_per_lease: usize,
}

impl Default for Capacities {
    fn default() -> Self {
        Self {
            points: DEFAULT_POINTS,
            leases: DEFAULT_LEASES,
            points_per_lease: DEFAULT_POINTS_PER_LEASE,
        }
    }
}

/// Identifies which pre-allocated capacity limit was reached.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CapacityKind {
    /// Point arena capacity (`Capacities::points`).
    Points,
    /// Active lease table capacity (`Capacities::leases`).
    Leases,
    /// Per-lease point index capacity (`Capacities::points_per_lease`).
    PointsPerLease,
}

impl fmt::Display for CapacityKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Points => f.write_str("points"),
            Self::Leases => f.write_str("leases"),
            Self::PointsPerLease => f.write_str("points_per_lease"),
        }
    }
}

/// Reason a [`Kernel`] operation was refused.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum KernelError {
    /// The given [`PointId`] does not exist in the arena.
    UnknownPoint,
    /// Command targeted an input point, or telemetry targeted an output point.
    WrongPointType,
    /// Value kind does not match the registered kind of the point.
    KindMismatch,
    /// Floating-point value is `NaN` or infinite.
    NonFinite,
    /// Priority number is outside `1..=16`.
    InvalidPriority,
    /// Priority level 6 (`MINIMUM_ON_OFF`) is reserved for the kernel algorithm.
    ReservedPriority,
    /// The [`LeaseId`] was never issued or has already been revoked.
    UnknownLease,
    /// The lease has reached or passed its deadline (`now >= deadline`).
    LeaseExpired,
    /// The lease does not hold the target priority slot on this point.
    SlotNotHeld,
    /// Deadband is negative, non-finite, or specified for a `Bool` input.
    InvalidDeadband,
    /// Lease time-to-live is zero or `now + ttl` overflows `u64`.
    InvalidTtl,
    /// Operation would exceed the pre-allocated [`CapacityKind`] bound.
    CapacityExceeded(CapacityKind),
    /// All `u32` lease identifiers (`1..=u32::MAX`) have been exhausted.
    LeaseIdsExhausted,
}

impl fmt::Display for KernelError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownPoint => f.write_str("unknown point id"),
            Self::WrongPointType => f.write_str("wrong point type for operation"),
            Self::KindMismatch => f.write_str("value kind does not match point kind"),
            Self::NonFinite => f.write_str("non-finite floating-point value refused"),
            Self::InvalidPriority => f.write_str("priority level must be in 1..=16"),
            Self::ReservedPriority => f.write_str("priority level 6 is reserved for kernel use"),
            Self::UnknownLease => f.write_str("unknown or revoked lease id"),
            Self::LeaseExpired => f.write_str("lease has expired"),
            Self::SlotNotHeld => f.write_str("priority slot is not held by caller lease"),
            Self::InvalidDeadband => f.write_str("invalid deadband configuration"),
            Self::InvalidTtl => f.write_str("invalid or overflowing lease ttl"),
            Self::CapacityExceeded(kind) => write!(f, "capacity exceeded: {kind}"),
            Self::LeaseIdsExhausted => f.write_str("lease id counter exhausted at u32::MAX"),
        }
    }
}

impl core::error::Error for KernelError {}

#[derive(Debug, Clone)]
struct InputPoint {
    kind: ValueKind,
    deadband: Option<f64>,
    last_reported: Option<Value>,
}

#[derive(Debug, Clone)]
struct OutputPoint {
    kind: ValueKind,
    relinquish_default: Value,
    priority_array: PriorityArray,
    present_value: Value,
}

#[derive(Debug, Clone)]
#[expect(
    clippy::large_enum_variant,
    reason = "arena slots are allocated once in Kernel::new; boxing outputs would allocate per point"
)]
enum Point {
    Input(InputPoint),
    Output(OutputPoint),
}

#[derive(Debug, Clone, Copy)]
struct ActiveLease {
    id: LeaseId,
    ttl: Millis,
    deadline: Millis,
}

#[derive(Debug, Clone)]
struct LeaseSlot {
    state: Option<ActiveLease>,
    points: Vec<PointId>,
}

impl LeaseSlot {
    fn remove_point(&mut self, point: PointId) {
        if let Some(pos) = self.points.iter().position(|&p| p == point) {
            self.points.swap_remove(pos);
        }
    }
}

/// Fixed-capacity `no_std` arbitration kernel.
#[derive(Debug)]
pub struct Kernel {
    capacities: Capacities,
    points: Vec<Point>,
    leases: Vec<LeaseSlot>,
    next_lease_id: Option<u32>,
}

impl Kernel {
    /// Allocates a new kernel with all arena, lease, and per-lease index storage
    /// pre-allocated up front. No heap allocation occurs after `new`.
    #[must_use]
    pub fn new(capacities: Capacities) -> Self {
        let points = Vec::with_capacity(capacities.points);
        let mut leases = Vec::with_capacity(capacities.leases);
        for _ in 0..capacities.leases {
            leases.push(LeaseSlot {
                state: None,
                points: Vec::with_capacity(capacities.points_per_lease),
            });
        }
        Self {
            capacities,
            points,
            leases,
            next_lease_id: Some(1),
        }
    }

    /// Test helper to position the lease counter near `u32::MAX`.
    ///
    /// The counter only moves forward: a `next_id` at or below the current
    /// counter is ignored, and an exhausted counter stays exhausted, so no
    /// identifier is ever issued twice (D7).
    #[doc(hidden)]
    #[must_use]
    pub fn with_next_lease_id(mut self, next_id: u32) -> Self {
        self.next_lease_id = self.next_lease_id.map(|current| current.max(next_id));
        self
    }

    /// Returns the configured capacities of this kernel.
    #[must_use]
    pub const fn capacities(&self) -> Capacities {
        self.capacities
    }

    /// Returns the current present value of `point` (`None` if an input has not yet
    /// received its first telemetry update).
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::UnknownPoint`] if `point` was not registered.
    pub fn present_value(&self, point: PointId) -> Result<Option<Value>, KernelError> {
        let entry = self
            .points
            .get(point.0 as usize)
            .ok_or(KernelError::UnknownPoint)?;
        match entry {
            Point::Input(inp) => Ok(inp.last_reported),
            Point::Output(out) => Ok(Some(out.present_value)),
        }
    }

    /// Returns the number of points currently indexed under `lease`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::UnknownLease`] if `lease` is not active.
    pub fn lease_point_count(&self, lease: LeaseId) -> Result<usize, KernelError> {
        let idx = self.find_lease_slot(lease)?;
        let slot = self.leases.get(idx).ok_or(KernelError::UnknownLease)?;
        Ok(slot.points.len())
    }

    /// Registers a telemetry input point.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::InvalidDeadband`] if `deadband` is negative, non-finite,
    /// or provided for [`ValueKind::Bool`], or [`KernelError::CapacityExceeded`] if the
    /// point arena is full.
    pub fn register_input(
        &mut self,
        kind: ValueKind,
        deadband: Option<f64>,
    ) -> Result<PointId, KernelError> {
        if let Some(db) = deadband
            && (kind == ValueKind::Bool || !db.is_finite() || db < 0.0)
        {
            return Err(KernelError::InvalidDeadband);
        }
        self.push_point(Point::Input(InputPoint {
            kind,
            deadband,
            last_reported: None,
        }))
    }

    /// Registers a commandable output point initialized to `relinquish_default`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::NonFinite`] if `relinquish_default` is non-finite, or
    /// [`KernelError::CapacityExceeded`] if the point arena is full.
    pub fn register_output(&mut self, relinquish_default: Value) -> Result<PointId, KernelError> {
        if !relinquish_default.is_valid() {
            return Err(KernelError::NonFinite);
        }
        self.push_point(Point::Output(OutputPoint {
            kind: relinquish_default.kind(),
            relinquish_default,
            priority_array: PriorityArray::new(),
            present_value: relinquish_default,
        }))
    }

    /// Applies an input telemetry reading and emits [`CovEvent`] when the first
    /// value arrives or when the change reaches the configured deadband.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::NonFinite`], [`KernelError::UnknownPoint`],
    /// [`KernelError::WrongPointType`], or [`KernelError::KindMismatch`].
    pub fn telemetry(
        &mut self,
        point: PointId,
        value: Value,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), KernelError> {
        if !value.is_valid() {
            return Err(KernelError::NonFinite);
        }
        let entry = self
            .points
            .get_mut(point.0 as usize)
            .ok_or(KernelError::UnknownPoint)?;
        let Point::Input(inp) = entry else {
            return Err(KernelError::WrongPointType);
        };
        if inp.kind != value.kind() {
            return Err(KernelError::KindMismatch);
        }
        if should_emit_telemetry(inp.last_reported, value, inp.deadband) {
            inp.last_reported = Some(value);
            sink(CovEvent { point, value });
        }
        Ok(())
    }

    /// Issues a new writer lease with time-to-live `ttl` starting at `now`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::InvalidTtl`] if `ttl` is zero or `now + ttl` overflows,
    /// [`KernelError::CapacityExceeded`] if the lease table is full, or
    /// [`KernelError::LeaseIdsExhausted`] if `u32::MAX` was already issued.
    pub fn issue_lease(&mut self, ttl: Millis, now: Millis) -> Result<LeaseId, KernelError> {
        let deadline = compute_deadline(now, ttl)?;
        let free_idx = self
            .leases
            .iter()
            .position(|s| s.state.is_none())
            .ok_or(KernelError::CapacityExceeded(CapacityKind::Leases))?;
        let raw_id = self.next_lease_id.ok_or(KernelError::LeaseIdsExhausted)?;
        self.next_lease_id = raw_id.checked_add(1);
        let id = LeaseId(raw_id);
        if let Some(slot) = self.leases.get_mut(free_idx) {
            slot.points.clear();
            slot.state = Some(ActiveLease { id, ttl, deadline });
        }
        Ok(id)
    }

    /// Renews a live lease, advancing its deadline to `now + ttl`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::UnknownLease`] if unknown or revoked,
    /// [`KernelError::LeaseExpired`] if `now >= deadline`, or
    /// [`KernelError::InvalidTtl`] if `now + ttl` overflows.
    pub fn renew(&mut self, lease: LeaseId, now: Millis) -> Result<(), KernelError> {
        let idx = self.find_lease_slot(lease)?;
        let slot = self.leases.get_mut(idx).ok_or(KernelError::UnknownLease)?;
        let active = slot.state.as_mut().ok_or(KernelError::UnknownLease)?;
        if now.0 >= active.deadline.0 {
            return Err(KernelError::LeaseExpired);
        }
        active.deadline = compute_deadline(now, active.ttl)?;
        Ok(())
    }

    /// Revokes `lease`, clearing every slot it holds across the points in its
    /// per-lease index, re-resolving present values, and emitting [`CovEvent`]
    /// for each output whose present value changed. Returns the number of points
    /// visited in the lease's index.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::UnknownLease`] if `lease` was never issued or is already revoked.
    pub fn revoke(
        &mut self,
        lease: LeaseId,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<usize, KernelError> {
        let idx = self.find_lease_slot(lease)?;
        let slot = self.leases.get_mut(idx).ok_or(KernelError::UnknownLease)?;
        Ok(revoke_lease_slot(slot, &mut self.points, sink))
    }

    /// Revokes every lease whose deadline has been reached (`now >= deadline`),
    /// returning the number of expired leases revoked.
    pub fn expire(&mut self, now: Millis, sink: &mut impl FnMut(CovEvent)) -> usize {
        let mut expired_count: usize = 0;
        for slot in &mut self.leases {
            let is_expired = slot.state.is_some_and(|active| now.0 >= active.deadline.0);
            if is_expired {
                revoke_lease_slot(slot, &mut self.points, sink);
                expired_count = expired_count.saturating_add(1);
            }
        }
        expired_count
    }

    /// Commands `point` at `priority` with `value` under `lease` at timestamp `now`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::NonFinite`], [`KernelError::ReservedPriority`],
    /// [`KernelError::UnknownLease`], [`KernelError::LeaseExpired`],
    /// [`KernelError::UnknownPoint`], [`KernelError::WrongPointType`],
    /// [`KernelError::KindMismatch`], or [`KernelError::CapacityExceeded`].
    pub fn command(
        &mut self,
        lease: LeaseId,
        point: PointId,
        priority: Priority,
        value: Value,
        now: Millis,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), KernelError> {
        if !value.is_valid() {
            return Err(KernelError::NonFinite);
        }
        if priority == Priority::MINIMUM_ON_OFF {
            return Err(KernelError::ReservedPriority);
        }
        let lease_idx = self.find_live_lease_slot(lease, now)?;
        let already_indexed = self
            .leases
            .get(lease_idx)
            .is_some_and(|s| s.points.contains(&point));
        let index_len = self.leases.get(lease_idx).map_or(0, |s| s.points.len());
        if !already_indexed && index_len >= self.capacities.points_per_lease {
            return Err(KernelError::CapacityExceeded(CapacityKind::PointsPerLease));
        }
        let (prev_holder_gone, changed_val) =
            write_output_slot(&mut self.points, point, priority, lease, value)?;
        if !already_indexed && let Some(slot) = self.leases.get_mut(lease_idx) {
            slot.points.push(point);
        }
        if let Some(displaced_lease) = prev_holder_gone {
            self.drop_point_from_lease(displaced_lease, point);
        }
        if let Some(new_val) = changed_val {
            sink(CovEvent {
                point,
                value: new_val,
            });
        }
        Ok(())
    }

    /// Relinquishes the slot at `priority` on `point` held by `lease` at timestamp `now`.
    ///
    /// # Errors
    ///
    /// Returns [`KernelError::ReservedPriority`], [`KernelError::UnknownLease`],
    /// [`KernelError::LeaseExpired`], [`KernelError::UnknownPoint`],
    /// [`KernelError::WrongPointType`], or [`KernelError::SlotNotHeld`].
    pub fn relinquish(
        &mut self,
        lease: LeaseId,
        point: PointId,
        priority: Priority,
        now: Millis,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), KernelError> {
        if priority == Priority::MINIMUM_ON_OFF {
            return Err(KernelError::ReservedPriority);
        }
        let lease_idx = self.find_live_lease_slot(lease, now)?;
        let (still_holds_point, changed_val) =
            clear_output_slot(&mut self.points, point, priority, lease)?;
        if !still_holds_point && let Some(slot) = self.leases.get_mut(lease_idx) {
            slot.remove_point(point);
        }
        if let Some(new_val) = changed_val {
            sink(CovEvent {
                point,
                value: new_val,
            });
        }
        Ok(())
    }

    fn push_point(&mut self, point: Point) -> Result<PointId, KernelError> {
        if self.points.len() >= self.capacities.points {
            return Err(KernelError::CapacityExceeded(CapacityKind::Points));
        }
        let id_u32 = u32::try_from(self.points.len())
            .map_err(|_| KernelError::CapacityExceeded(CapacityKind::Points))?;
        self.points.push(point);
        Ok(PointId(id_u32))
    }

    fn find_lease_slot(&self, lease: LeaseId) -> Result<usize, KernelError> {
        self.leases
            .iter()
            .position(|s| s.state.is_some_and(|a| a.id == lease))
            .ok_or(KernelError::UnknownLease)
    }

    fn find_live_lease_slot(&self, lease: LeaseId, now: Millis) -> Result<usize, KernelError> {
        let idx = self.find_lease_slot(lease)?;
        let active = self
            .leases
            .get(idx)
            .and_then(|s| s.state)
            .ok_or(KernelError::UnknownLease)?;
        if now.0 >= active.deadline.0 {
            return Err(KernelError::LeaseExpired);
        }
        Ok(idx)
    }

    fn drop_point_from_lease(&mut self, lease: LeaseId, point: PointId) {
        if let Ok(idx) = self.find_lease_slot(lease)
            && let Some(slot) = self.leases.get_mut(idx)
        {
            slot.remove_point(point);
        }
    }
}

fn compute_deadline(now: Millis, ttl: Millis) -> Result<Millis, KernelError> {
    if ttl.0 == 0 {
        return Err(KernelError::InvalidTtl);
    }
    now.0
        .checked_add(ttl.0)
        .map(Millis)
        .ok_or(KernelError::InvalidTtl)
}

fn revoke_lease_slot(
    slot: &mut LeaseSlot,
    points: &mut [Point],
    sink: &mut impl FnMut(CovEvent),
) -> usize {
    let Some(active) = slot.state.take() else {
        return 0;
    };
    let visited = slot.points.len();
    for &point_id in &slot.points {
        if let Some(Point::Output(out)) = points.get_mut(point_id.0 as usize) {
            out.priority_array.clear_lease_slots(active.id);
            let resolved = out.priority_array.resolve_value(out.relinquish_default);
            if resolved != out.present_value {
                out.present_value = resolved;
                sink(CovEvent {
                    point: point_id,
                    value: resolved,
                });
            }
        }
    }
    slot.points.clear();
    visited
}

fn write_output_slot(
    points: &mut [Point],
    point: PointId,
    priority: Priority,
    lease: LeaseId,
    value: Value,
) -> Result<(Option<LeaseId>, Option<Value>), KernelError> {
    let entry = points
        .get_mut(point.0 as usize)
        .ok_or(KernelError::UnknownPoint)?;
    let Point::Output(out) = entry else {
        return Err(KernelError::WrongPointType);
    };
    if out.kind != value.kind() {
        return Err(KernelError::KindMismatch);
    }
    let prev = out.priority_array.slot(priority);
    out.priority_array.set_slot(priority, Some((lease, value)));
    let displaced = match prev {
        Some((prev_lease, _)) if prev_lease != lease => {
            if out.priority_array.lease_holds_any(prev_lease) {
                None
            } else {
                Some(prev_lease)
            }
        }
        _ => None,
    };
    let resolved = out.priority_array.resolve_value(out.relinquish_default);
    let changed = if resolved == out.present_value {
        None
    } else {
        out.present_value = resolved;
        Some(resolved)
    };
    Ok((displaced, changed))
}

fn clear_output_slot(
    points: &mut [Point],
    point: PointId,
    priority: Priority,
    lease: LeaseId,
) -> Result<(bool, Option<Value>), KernelError> {
    let entry = points
        .get_mut(point.0 as usize)
        .ok_or(KernelError::UnknownPoint)?;
    let Point::Output(out) = entry else {
        return Err(KernelError::WrongPointType);
    };
    let Some((holder, _)) = out.priority_array.slot(priority) else {
        return Err(KernelError::SlotNotHeld);
    };
    if holder != lease {
        return Err(KernelError::SlotNotHeld);
    }
    out.priority_array.set_slot(priority, None);
    let still_holds = out.priority_array.lease_holds_any(lease);
    let resolved = out.priority_array.resolve_value(out.relinquish_default);
    let changed = if resolved == out.present_value {
        None
    } else {
        out.present_value = resolved;
        Some(resolved)
    };
    Ok((still_holds, changed))
}

fn should_emit_telemetry(last_reported: Option<Value>, next: Value, deadband: Option<f64>) -> bool {
    let Some(prev) = last_reported else {
        return true;
    };
    if prev == next {
        return false;
    }
    let Some(db) = deadband else {
        return true;
    };
    match (prev, next) {
        (Value::Bool(a), Value::Bool(b)) => a != b,
        (Value::I64(a), Value::I64(b)) => u64_reaches_deadband(a.abs_diff(b), db),
        (Value::U16(a), Value::U16(b)) => u64_reaches_deadband(u64::from(a.abs_diff(b)), db),
        (Value::F64(a), Value::F64(b)) => (a - b).abs() >= db,
        _ => false,
    }
}

#[expect(
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_precision_loss,
    reason = "deadband is finite, non-negative and below 2^64 here, so the casts are exact floors"
)]
fn u64_reaches_deadband(diff: u64, deadband: f64) -> bool {
    if deadband <= 0.0 {
        return diff > 0;
    }
    if deadband >= TWO_POW_64 {
        return false;
    }
    let floor_int = deadband as u64;
    let has_fraction = (floor_int as f64) < deadband;
    let min_diff = if has_fraction {
        floor_int.saturating_add(1)
    } else {
        floor_int
    };
    diff >= min_diff
}
