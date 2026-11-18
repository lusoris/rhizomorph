// SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
// SPDX-License-Identifier: EUPL-1.2

//! Standard-library adapter for [`kernel::Kernel`], supplying `std::sync::Mutex`
//! synchronization and monotonic `std::time::Instant` timestamps for lease operations.

use std::fmt;
use std::sync::{Mutex, MutexGuard};
use std::time::Instant;

pub use kernel::{
    Capacities, CapacityKind, CovEvent, DEFAULT_LEASES, DEFAULT_POINTS, DEFAULT_POINTS_PER_LEASE,
    Kernel, KernelError, LeaseId, Millis, PointId, Priority, PriorityArray, Value, ValueKind,
};

/// Error returned by [`SharedKernel`] operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AdapterError {
    /// The internal mutex was poisoned by a panic during a previous call.
    Poisoned {
        /// Name of the operation that encountered the poisoned mutex.
        op: &'static str,
    },
    /// The inner [`Kernel`] refused the operation.
    Kernel {
        /// Name of the operation that failed.
        op: &'static str,
        /// Underlying kernel refusal reason.
        source: KernelError,
    },
}

impl fmt::Display for AdapterError {
    /// Describes the failed operation and its cause.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Poisoned { op } => write!(f, "kernel mutex poisoned during {op}"),
            Self::Kernel { op, source } => write!(f, "kernel operation {op} failed: {source}"),
        }
    }
}

impl std::error::Error for AdapterError {
    /// Returns the kernel refusal of a `Kernel` error; a poisoned mutex has no source.
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Poisoned { .. } => None,
            Self::Kernel { source, .. } => Some(source),
        }
    }
}

/// Thread-safe adapter wrapping [`Kernel`] in a [`Mutex`] with a monotonic start [`Instant`].
#[derive(Debug)]
pub struct SharedKernel {
    inner: Mutex<Kernel>,
    start: Instant,
}

impl Default for SharedKernel {
    /// Builds an adapter with the default kernel capacities.
    fn default() -> Self {
        Self::new(Capacities::default())
    }
}

impl SharedKernel {
    /// Creates a new [`SharedKernel`] with pre-allocated `capacities` and captures
    /// the monotonic start instant.
    #[must_use]
    pub fn new(capacities: Capacities) -> Self {
        Self {
            inner: Mutex::new(Kernel::new(capacities)),
            start: Instant::now(),
        }
    }

    /// Wraps an already-constructed [`Kernel`] and captures the monotonic start instant.
    #[must_use]
    pub fn from_kernel(kernel: Kernel) -> Self {
        Self {
            inner: Mutex::new(kernel),
            start: Instant::now(),
        }
    }

    /// Registers a telemetry input point (no clock read).
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses registration.
    pub fn register_input(
        &self,
        kind: ValueKind,
        deadband: Option<f64>,
    ) -> Result<PointId, AdapterError> {
        const OP: &str = "register_input";
        let mut guard = self.lock(OP)?;
        guard
            .register_input(kind, deadband)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Registers a commandable output point initialized to `relinquish_default` (no clock read).
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses registration.
    pub fn register_output(&self, relinquish_default: Value) -> Result<PointId, AdapterError> {
        const OP: &str = "register_output";
        let mut guard = self.lock(OP)?;
        guard
            .register_output(relinquish_default)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Ingests a telemetry update for an input point without reading the system clock.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses the update.
    pub fn telemetry(
        &self,
        point: PointId,
        value: Value,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), AdapterError> {
        const OP: &str = "telemetry";
        let mut guard = self.lock(OP)?;
        guard
            .telemetry(point, value, sink)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Issues a new writer lease with time-to-live `ttl` using the adapter's monotonic clock.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses lease issuance.
    pub fn issue_lease(&self, ttl: Millis) -> Result<LeaseId, AdapterError> {
        const OP: &str = "issue_lease";
        let mut guard = self.lock(OP)?;
        let now = self.now_millis();
        guard
            .issue_lease(ttl, now)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Renews `lease` using the adapter's monotonic clock.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the lease is unknown, expired, or overflows.
    pub fn renew(&self, lease: LeaseId) -> Result<(), AdapterError> {
        const OP: &str = "renew";
        let mut guard = self.lock(OP)?;
        let now = self.now_millis();
        guard
            .renew(lease, now)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Revokes `lease` immediately and forwards any resulting [`CovEvent`]s to `sink`.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the lease is unknown or already revoked.
    pub fn revoke(
        &self,
        lease: LeaseId,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<usize, AdapterError> {
        const OP: &str = "revoke";
        let mut guard = self.lock(OP)?;
        guard
            .revoke(lease, sink)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Revokes all leases that have expired at the current monotonic clock reading.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned.
    pub fn expire(&self, sink: &mut impl FnMut(CovEvent)) -> Result<usize, AdapterError> {
        const OP: &str = "expire";
        let mut guard = self.lock(OP)?;
        let now = self.now_millis();
        Ok(guard.expire(now, sink))
    }

    /// Commands an output `point` at `priority` under `lease` using the monotonic clock.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses the command.
    pub fn command(
        &self,
        lease: LeaseId,
        point: PointId,
        priority: Priority,
        value: Value,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), AdapterError> {
        const OP: &str = "command";
        let mut guard = self.lock(OP)?;
        let now = self.now_millis();
        guard
            .command(lease, point, priority, value, now, sink)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Relinquishes `priority` on `point` under `lease` using the monotonic clock.
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if the kernel refuses the relinquish.
    pub fn relinquish(
        &self,
        lease: LeaseId,
        point: PointId,
        priority: Priority,
        sink: &mut impl FnMut(CovEvent),
    ) -> Result<(), AdapterError> {
        const OP: &str = "relinquish";
        let mut guard = self.lock(OP)?;
        let now = self.now_millis();
        guard
            .relinquish(lease, point, priority, now, sink)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Reads the current present value of `point` (no clock read).
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if `point` is unknown.
    pub fn present_value(&self, point: PointId) -> Result<Option<Value>, AdapterError> {
        const OP: &str = "present_value";
        let guard = self.lock(OP)?;
        guard
            .present_value(point)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Returns the number of points currently indexed under `lease` (no clock read).
    ///
    /// # Errors
    ///
    /// Returns [`AdapterError::Poisoned`] if the lock is poisoned, or
    /// [`AdapterError::Kernel`] if `lease` is unknown.
    pub fn lease_point_count(&self, lease: LeaseId) -> Result<usize, AdapterError> {
        const OP: &str = "lease_point_count";
        let guard = self.lock(OP)?;
        guard
            .lease_point_count(lease)
            .map_err(|source| AdapterError::Kernel { op: OP, source })
    }

    /// Locks the kernel mutex, mapping poisoning to `AdapterError::Poisoned` for `op`.
    fn lock(&self, op: &'static str) -> Result<MutexGuard<'_, Kernel>, AdapterError> {
        self.inner.lock().map_err(|_| AdapterError::Poisoned { op })
    }

    /// Milliseconds since construction, saturating at `u64::MAX`.
    fn now_millis(&self) -> Millis {
        let elapsed = self.start.elapsed().as_millis();
        let ms = u64::try_from(elapsed).unwrap_or(u64::MAX);
        Millis(ms)
    }
}
