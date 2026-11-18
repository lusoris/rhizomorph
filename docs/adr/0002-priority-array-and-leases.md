<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0002: Priority array and leases

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

Several writers can command one output at the same time: a schedule, a
safety function, a user, a plugin. "Last writer wins" lets a routine writer
override an urgent one. Building automation solves this with a priority
array per commandable object, as BACnet defines it. A second problem is
cleanup: when a writer fails, its commands must not stay in force. This
record restates a design input by the operator and corrects the defects
found in the reference design ([`plan/design-defects.md`](../plan/design-defects.md)).

## Decision

### Points

- A point is an **input** or a **commandable output**. Telemetry writes an
  input's present value directly. An output's present value is resolved from
  its priority array.
- Non-finite floats are refused at ingress.
- Points are addressed by dense numeric ids inside the kernel.

### The priority array

- Each commandable point has 16 slots. A slot is empty or holds a lease id
  and a value. The lowest level number wins; resolution scans level 1 to 16.
- A slot is cleared only by the lease that set it or by the kernel.
- `Priority` is a newtype over `u8`, validated to 1..=16. Constants name the
  assigned levels. The reference design used an enum that covered 7 of 16
  levels.

Levels, from ANSI/ASHRAE Standard 135, Clause 19.2, Table 19-1. The standard
text is paywalled and was not read; the names come from NISTIR 6392 and from
the `rusty-bacnet` source (`crates/bacnet-ops/src/write/priority.rs`,
`write/policy.rs`), which agree. Clause numbering against the current
edition is not verified.

| Level | Standard name | Status | Rhizomorph use |
| :--- | :--- | :--- | :--- |
| 1 | Manual-Life Safety | assigned by the standard | Never taken by a guest ([ADR-0003](0003-wit-contract-push-model.md)) |
| 2 | Automatic-Life Safety | assigned by the standard | Writers beyond guests not yet decided; whether a plugin may take it is open in ADR-0003 |
| 3, 4 | Available | free | Unassigned |
| 5 | Critical Equipment Control | assigned by the standard | Not yet decided; whether a plugin may take it is open in ADR-0003 |
| 6 | Minimum On/Off | assigned by the standard | Reserved for the minimum on and off time algorithm of an object; never taken by plugins or schedules |
| 7 | Available | free | Unassigned |
| 8 | Manual Operator | assigned by the standard | Proposed for user commands |
| 9 | Available | free | Unassigned |
| 10 | Available | free | Control loops; a project convention, not a standard name |
| 11 | Available | free | Unassigned |
| 12 | Available | free | Schedules; a project convention, not a standard name |
| 13 to 15 | Available | free | Unassigned |
| 16 | Available | free | Fallback writer; a project convention, not a standard name |

The standard assigns exactly levels 1, 2, 5, 6 and 8. The names that the
design input gave to levels 10, 12 and 16 are conventions on free levels.
Level 6 is reserved for the minimum on/off algorithm of an object (Clause
19.2.3, per the sources above); the open `bacnet-stack` source refuses
writes at 6 for the same reason. The kernel refuses a plugin or schedule
write at level 6.

### Leases

- Every writer (worker, plugin, UI session, sidecar) holds a host-assigned
  lease id. A lease id never leaves the host side ([ADR-0003](0003-wit-contract-push-model.md)).
- When a lease is lost (plugin trap, memory overrun, missed deadline, socket
  close, worker restart), the kernel **revokes** it: every slot it holds is
  cleared, each affected present value falls back to the next occupied slot,
  and COV events fire for every value that changed.

### The real bound of revoke

The reference design kept a 64-bit mask indexed by `lease % 64` and claimed
constant-time revoke. Leases 64 and above collide with lower ones, and revoke
still scanned every point, so the claim is false.

- **With a per-lease point index** (decision): revoke visits only the points
  that lease holds. The bound is the number of points held by that lease, each
  with a scan of at most 16 slots.
- **Without the index**: revoke visits all points, so the bound is all points
  times 16 slots.

The index is part of the kernel. The kernel test suite checks the bound with
a lease that holds few points among many.

### Layout measurement

A scratch program (not committed; rustc 1.98.1, x86_64, edition 2024,
release build) measured these types: `Value` is an enum of bool, i64, f64
and u16; `LeaseId(u32)`; `PriorityArray` holds `[Option<(LeaseId, Value)>; 16]`.

| Type | Size | Alignment |
| :--- | :--- | :--- |
| `Value` | 16 bytes | 8 |
| `(LeaseId, Value)` | 24 bytes | 8 |
| `Option<(LeaseId, Value)>` | 24 bytes (niche in the enum tag) | 8 |
| `PriorityArray` | 384 bytes, exactly 6 cache lines of 64 bytes | 8 |

The limit: this is a property of one compiler and one target. Rust does not
guarantee the layout of these types. The kernel carries a size assertion as a
test, and the project does not promise the size on 32-bit targets.

### Relinquish default and the last relinquish

- Every commandable point has a **relinquish default**, a value of the
  point's kind, set when the point is registered and stored with the point
  definition ([ADR-0004](0004-storage-split.md)).
- When the last slot of a point is relinquished, or the last lease holding a
  slot is revoked, the present value becomes the relinquish default.
- A COV event fires whenever that changes the present value. The reference
  design left the value empty and sent no event.

### Equality and deadband (to be fixed by tests first)

Proposed definitions that phase P1 turns into tests before code:

- Values of different kinds are never equal; an `i64` is not equal to an
  `f64` of the same magnitude.
- A deadband is an absolute threshold, finite and not negative, checked at
  registration. A telemetry update whose difference from the last reported
  value is smaller than the threshold is dropped and fires no COV event.
  With a threshold of 0.0, every update that differs from the last reported
  value fires, and an identical value never does.
- NaN and infinities never reach the comparison; they are refused at ingress.

## Consequences

- **Positive**: Urgent writers override routine ones; failed writers release
  their commands automatically; revoke has a stated, testable bound.
- **Negative**: The per-lease index costs memory and must be kept in step
  with the slots. Levels 3, 4, 7, 9, 11 and 13 to 15 are unassigned and need a
  use before anyone takes them. The 384-byte layout is an observation, not a
  guarantee.

## References

- Design input by the operator, restated; no document is quoted.
- ANSI/ASHRAE Standard 135, Clause 19.2, Table 19-1: text not read
  (paywalled).
- NISTIR 6392, GSA Guide to Specifying Interoperable Building Automation and
  Control Systems Using ANSI/ASHRAE Standard 135-1995, hosted at bacnet.org.
- `jscott3201/rusty-bacnet`, `crates/bacnet-ops/src/write/priority.rs` and
  `write/policy.rs`, read 2026-11-18.
- [`docs/plan/design-defects.md`](../plan/design-defects.md), defects 3, 5, 6
  and 7.
