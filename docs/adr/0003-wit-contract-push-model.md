<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0003: WIT contract and push model for plugins

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

Tier 2 plugins are WebAssembly components, WASI 0.2, built for
`wasm32-wasip2` and run on Wasmtime ([ADR-0001](0001-tier-model.md)). They
need a contract with the host that is small, typed and hard to misuse. The
design input by the operator also wrote "epoch fuel metering" for the
guest limits. That wording merges two separate Wasmtime mechanisms; this
record corrects it from the Wasmtime source at tag v50.0.2.

## Decision

### The contract

The contract is written in WIT, the component-model interface language. The
host **pushes** change-of-value (COV) events to guests; a guest never polls.

| Direction | Name | Purpose |
| :--- | :--- | :--- |
| Guest export | `init` | Called once; returns the point ids the guest subscribes to |
| Guest export | `on-cov` | Receives a COV event pushed by the host |
| Guest export | `on-tick` | Receives a periodic tick for time-based work |
| Guest import | `report-telemetry` | Writes an input value |
| Guest import | `command-point` | Writes an output at a priority |
| Guest import | `relinquish-point` | Clears the guest's own slot at a priority |

The table gives names only. Record fields and the exact WIT file are written
in phase P3 and checked by a positive, negative and boundary test.

Rules of the contract:

- **Lease ids never cross the boundary.** The host holds the lease of each
  store and applies it to every import call. A guest cannot name, forge or
  clear another lease's slot, because the contract has no way to express one.
- **Push, not poll.** A guest receives events only for points it returned
  from `init`. Queues are bounded per guest (HISS-06); the behaviour on
  overflow is decided and tested in P3.
- **The priority type excludes level 1 on purpose.** The enum offered to
  guests leaves out Manual-Life Safety. Guests never take level 1. The type
  also leaves out level 6, which no plugin or schedule takes
  ([ADR-0002](0002-priority-array-and-leases.md)). A request for a level the
  type cannot express is impossible to write, so no runtime check can be
  skipped. The host still validates every level against `Priority` and the
  manifest.

### Guest limits

Two separate Wasmtime mechanisms exist, and the design uses them for
different jobs.

| Mechanism | Wasmtime item | Use in rhizomorph |
| :--- | :--- | :--- |
| Epoch interruption | `Config::epoch_interruption` (`config.rs` line 788): a global counter that the host increments | Wall-clock deadline of every guest call |
| Memory cap | `StoreLimitsBuilder::memory_size(bytes)` (`limits.rs` line 238), attached with `Store::limiter` | Cap per store, a few MiB per instance; limits each linear memory individually |
| Async host functions | Host functions that await | Blocking calls such as network access, with a host-side timeout |
| Fuel | `Config::consume_fuel` (`config.rs` line 643): instrumented code, deterministic, a store starts with no fuel | Only in replay tests that need a deterministic trap |

Reasons, from the Wasmtime documentation at v50.0.2:

- Epochs run faster than fuel: "in some measurements, up to 2-3x". Fuel is for
  cases that need deterministic yielding or trapping.
- Neither epochs nor fuel interrupt a guest that is blocked in a host call.
  The host therefore puts its own timeout on every async host function.
- Bulk instructions such as `memory.copy` check the epoch once, at their
  start. The documentation recommends bounding store memory with a
  `ResourceLimiter` for strict time limits; `StoreLimits` is one.
- Epoch interruption is not compatible with the Winch compiler. The host
  does not use Winch.

On a trap, memory overrun or missed deadline, the host revokes the guest's
lease ([ADR-0002](0002-priority-array-and-leases.md)). The epoch tick period
and the deadline in ticks are set in P3.

### Capabilities

Capabilities are deny by default and declared in a manifest, for example
outbound HTTP to one named host. Cloud API plugins can be generated from
OpenAPI definitions with `progenitor` plus `wit-bindgen`; that is a later
node, not part of P3.

### Open question

Must a plugin manifest also cap the highest level a guest may take? The
guest type allows levels 2 and 5, which the standard assigns to life safety
and critical equipment. A manifest cap would stop an untrusted plugin from
overriding those levels without an explicit grant. Not decided; it blocks the
final WIT file in P3.

## Consequences

- **Positive**: A guest cannot hold, leak or guess a lease. Time and memory
  are bounded by separate mechanisms with stated limits. The corrected
  wording avoids a configuration that never enabled fuel.
- **Negative**: The deadline protects against code running, not against a
  guest blocked in a host call; every host function needs its own timeout.
  Epoch interruption excludes the Winch compiler. A guest without level 1 can
  never perform a manual life-safety override.

## References

- Design input by the operator, restated; no document is quoted.
- Wasmtime tag v50.0.2, `crates/wasmtime/src/config.rs` (sha256
  fa5c06563662) and `crates/wasmtime/src/runtime/limits.rs` (sha256
  07d25368279a), checked 2026-11-18.
- [`docs/concept.md`](../concept.md): wasmtime 50.0.2, wasmtime-wasi 50.0.2,
  wit-bindgen 0.63.0, progenitor 0.16.1.
- [`docs/plan/design-defects.md`](../plan/design-defects.md), defect 8.
