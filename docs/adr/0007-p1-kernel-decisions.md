<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0007: Phase P1 kernel implementation decisions

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

[ADR-0001](0001-tier-model.md) and [ADR-0002](0002-priority-array-and-leases.md)
define the Tier-0 arbitration model (`no_std` core crate `kernel` and `std`
adapter `kernel-std`) and leave concrete P1 operational rules to be fixed by
tests and implementation: how monotonic time enters the core, what happens when
a lease writes a priority slot held by another lease, how a hanging writer is
bounded, how capacities are allocated, how change-of-value (COV) events leave
the kernel in P1, how lease identifiers are issued, and whether input telemetry
requires a lease in P1.

## Decision

### Time representation and clock boundary (D2)

- The `no_std` core (`crates/kernel/src/lib.rs`) never reads a clock. Time is
  `Millis(u64)`, representing monotonic milliseconds passed in by the caller on
  lease calls (`issue_lease`, `renew`, `command`, `relinquish`, `expire`).
- `telemetry` takes no time value.
- `SharedKernel` (`crates/kernel-std/src/lib.rs`) computes `Millis` as elapsed
  milliseconds since its construction `std::time::Instant`, saturating at
  `u64::MAX`. Wrapping an existing kernel requires its clock origin
  (`crates/kernel-std/tests/adapter.rs`).
- **Reason**: Keeping clock reads out of the core preserves deterministic
  `no_std` testing (`crates/kernel/tests/positive.rs`) and removes a system
  clock read from the hot telemetry ingress path
  (`crates/kernel-std/examples/ingress_cost.rs`).
- **Revisit when**: Sub-millisecond lease deadlines are required by a fieldbus
  worker or Wasm host timer.

### Command on a slot held by another lease (D3)

- A `command` by lease B at a priority level where lease A holds the slot
  replaces A's entry at that level, following BACnet priority-array write
  semantics.
- Lease A's per-lease point index entry for that point is removed if and only
  if A then holds no other slot on that point (`crates/kernel/tests/positive.rs`).
- A subsequent `relinquish` by A at that level is refused with
  `KernelError::SlotNotHeld`.
- **Reason**: BACnet priority levels arbitrate between writer classes by level
  number rather than exclusive per-level locks, while keeping the per-lease
  point index exact avoids stale visits during `revoke`.
- **Revisit when**: A writer class needs exclusive ownership of a level.

### Lease time-to-live and hanging writers (D4)

- Every lease is issued with a non-zero `ttl: Millis` (`ttl == 0` or `now + ttl`
  overflow is refused with `KernelError::InvalidTtl`). Its deadline is
  `now + ttl`.
- A lease is live while `now < deadline`; at `now == deadline` and after, it is
  expired and refused on `command`, `relinquish`, and `renew` with
  `KernelError::LeaseExpired` (`crates/kernel/tests/positive.rs`,
  `crates/kernel/tests/negative.rs`).
- `renew(lease, now)` on a live lease advances its deadline to `now + ttl`.
- `expire(now, sink)` revokes every expired lease within the bounded lease
  table using the same slot-clearing and COV resolution path as `revoke`.
- The host calls `expire` at a bounded interval; release is bounded by ttl plus
  the host sweep interval (`crates/kernel/tests/positive.rs`).
- **Reason**: This bounds how long a stalled writer retains its priority overrides
  (HISS-02).
- **Revisit when**: A writer class cannot renew within its ttl, or renew cost
  shows in the P1 measurement.

### Pre-allocated capacities (D5)

- `Kernel::new` takes `Capacities { points, leases, points_per_lease }` with
  named defaults `DEFAULT_POINTS = 4096`, `DEFAULT_LEASES = 256`, and
  `DEFAULT_POINTS_PER_LEASE = 1024` (`crates/kernel/src/lib.rs`).
- All arena, lease table, and per-lease index vectors are allocated once in
  `Kernel::new` via `Vec::with_capacity`; operations past any bound return
  `KernelError::CapacityExceeded` without allocating (`crates/kernel/tests/boundary.rs`).
- **Reason**: Pre-allocation eliminates heap allocation after initialization
  (HISS-03) and bounds worst-case iteration across points and leases (HISS-02).
- **Revisit when**: A deployment exceeds a default.

### Change-of-value sink and broadcast deferral (D6)

- Core and adapter mutations that can change a present value (`telemetry`,
  `command`, `relinquish`, `revoke`, `expire`) accept a caller sink
  `&mut impl FnMut(CovEvent)` where `CovEvent { point: PointId, value: Value }`.
- `SharedKernel` passes the caller's sink through under the mutex guard; re-entry
  into a held adapter returns `Reentrant` (`crates/kernel-std/tests/adapter.rs`).
- Revocation completes state changes before calling the sink
  (`crates/kernel/tests/negative.rs`).
- The asynchronous broadcast channel and its slow-consumer loss policy
  ([ADR-0001](0001-tier-model.md), [ADR-0004](0004-storage-split.md)) are
  deferred to phase P4 (`docs/plan/phases.md`).
- **Reason**: A synchronous callback keeps `kernel` and `kernel-std` free of
  async runtime dependencies and channel allocation until the P4 daemon
  telemetry pipeline is built.
- **Revisit when**: Phase P4 wires the daemon broadcast channel and fjall
  telemetry pipeline ([ADR-0004](0004-storage-split.md)).

### Monotonic lease identifiers without reuse (D7)

- `LeaseId(u32)` is issued from a monotonic counter starting at `1` and is
  never reused after revocation or expiry.
- The last identifier ever issued is `u32::MAX`; every subsequent `issue_lease`
  call is refused with `KernelError::LeaseIdsExhausted` without wrapping
  (`crates/kernel/tests/boundary.rs`).
- Issuance checks invalid ttl, identifier exhaustion, then capacity, in that
  order (`crates/kernel/tests/boundary.rs`).
- The hidden test helper `Kernel::with_next_lease_id` only moves the counter
  forward and leaves an exhausted counter exhausted, so it cannot make the
  kernel issue an identifier twice (`crates/kernel/tests/boundary.rs`).
- **Reason**: Never reusing identifiers prevents a stale handle from matching a
  newly issued lease slot without widening `LeaseId` beyond 32 bits, preserving
  the 24-byte `Option<(LeaseId, Value)>` and 384-byte `PriorityArray` layout on
  `x86_64` ([ADR-0002](0002-priority-array-and-leases.md)).
- **Revisit when**: Long-lived deployments issue enough leases to approach
  `u32::MAX` over a daemon uptime cycle.

### Telemetry ingress cost (defect 4)

Defect 4 of [`design-defects.md`](../plan/design-defects.md) asks for finer
locking and a time value passed into the core, with the choice measured in
P1. The measurement runs with this command:

```sh
cargo run --release -p kernel-std --example ingress_cost --locked
```

Three runs on 2026-11-18 at 10:13, AMD Ryzen 9 9950X3D (32 threads), rustc
1.100.0, host load average 28.9, 2,000,000 updates per shape. Values are
nanoseconds per update, lowest to highest of the three runs; `RwLock` is
`RwLock<Vec<Value>>` and `SharedKernel` holds one `Mutex`:

| Shape | 1 thread | 4 threads |
| :--- | ---: | ---: |
| (a) reference: `RwLock` write, `Instant::now()` | 29.0-31.4 | 87.5-92.7 |
| (b) `RwLock` write, no clock read | 9.1-9.3 | 42.4-47.8 |
| (c) `SharedKernel::telemetry`, no clock read | 14.6-16.0 | 74.7-79.4 |

- Passing time in as a value removes the clock read from ingress:
  `telemetry` takes no time at all (D2), and (a) against (b) puts the clock
  read at about 20 ns of the reference code's 30 ns.
- Locking stays one `Mutex` around the whole kernel in P1. Shape (c) still
  serialises every writer, as the 4-thread column shows; the extra cost of
  (c) over (b) also includes the kind check and the deadband filter.
- Finer locking, such as one lock per point or a lock-free ingress queue,
  is not built in P1. One writer task per fieldbus worker feeds ingress in
  P2, so the contention shown at 4 threads is not the P2 load.
- The host was loaded during the runs, so the figures are comparable with
  each other, not absolute.
- **Revisit when**: the P4 telemetry pipeline measures ingress, or a
  deployment runs more than one writer thread against the kernel.

### Input telemetry lease policy in P1 (D8)

- `telemetry(point, value, sink)` requires no lease in P1 because input points
  have no priority array.
- Which fieldbus worker may report telemetry for which registered input is
  left to phase P2 (`docs/plan/phases.md`).
- **Reason**: Input points have a single source rather than 16-level
  arbitration, so writer ownership of inputs belongs to P2 worker registration.
- **Revisit when**: Phase P2 introduces fieldbus worker registration and
  per-worker input ownership.

## Consequences

- **Positive**: `kernel` compiles unconditionally under `#![no_std]` for
  `thumbv7em-none-eabihf`, allocates only in `Kernel::new`, and has
  deterministic positive, negative, and boundary test coverage
  (`cargo test --workspace --locked`).
- **Negative**: Holding the `SharedKernel` mutex across the `CovEvent` sink
  means a panicking sink poisons the mutex (`AdapterError::Poisoned`, tested in
  `crates/kernel-std/tests/adapter.rs`), and callers must keep sink callbacks
  short until P4 introduces the broadcast channel.

## References

- [ADR-0001](0001-tier-model.md), [ADR-0002](0002-priority-array-and-leases.md),
  [ADR-0004](0004-storage-split.md), and [ADR-0005](0005-licence.md).
- [`docs/plan/phases.md`](../plan/phases.md) and
  [`docs/plan/design-defects.md`](../plan/design-defects.md).
- [`crates/kernel/src/lib.rs`](../../crates/kernel/src/lib.rs),
  [`crates/kernel-std/src/lib.rs`](../../crates/kernel-std/src/lib.rs), and
  [`crates/kernel-std/examples/ingress_cost.rs`](../../crates/kernel-std/examples/ingress_cost.rs).
