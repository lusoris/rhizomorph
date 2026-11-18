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
design input by the operator also named the guest limits as a single
metering that combines epochs and fuel (paraphrased; design input,
2026-11-18, guest limits). Epochs and fuel are two separate Wasmtime
mechanisms; this record corrects the design from the Wasmtime source at tag
v50.0.2.

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
- **Point access is a capability.** Capabilities are deny by default (see
  [Capabilities](#capabilities)), and using a point is one of them: a guest
  may subscribe to, report or command only the points its manifest lists.
  The host refuses a subscription from `init` and a `command-point`,
  `relinquish-point` or `report-telemetry` call for any other point id. The
  manifest syntax for the list is written in P3.
- **The priority type excludes level 1 on purpose.** The enum offered to
  guests leaves out Manual-Life Safety. Guests never take level 1. The type
  also leaves out level 6, which no external writer takes
  ([ADR-0002](0002-priority-array-and-leases.md)). A request for a level the
  type cannot express is impossible to write, so no runtime check can be
  skipped. The host still validates every level against `Priority`. Whether
  it also checks a level cap from the manifest is the
  [open question](#open-question) below.
- **Bounded guests.** The number of guest stores that run at once has a
  fixed upper bound, set in P3 (HISS-06).

### Guest limits

Four Wasmtime mechanisms bound a guest, and the design uses each for a
different job.

| Mechanism | Wasmtime item | Use in rhizomorph |
| :--- | :--- | :--- |
| Epoch interruption | `Config::epoch_interruption` (`config.rs` line 788): a global counter that the host increments | Wall-clock deadline of every guest call |
| Memory and count caps | `StoreLimitsBuilder` (`limits.rs`), attached with `Store::limiter`: `memory_size(bytes)` (line 238), `table_elements` (line 250), `instances` (line 260), `tables` (line 270), `memories` (line 280), `trap_on_grow_failure` (line 294) | A cap of a few MiB on each linear memory, a cap on table elements, and caps on the number of instances, tables and memories in a store, so a store's total memory is bounded; the values are set in P3 |
| Async host functions | Host functions that await | Blocking calls such as network access, with a host-side timeout |
| Fuel | `Config::consume_fuel` (`config.rs` line 643): instrumented code, deterministic, a store starts with no fuel | Only in replay tests that need a deterministic trap |

`memory_size` limits each linear memory on its own, so a guest with several
memories could otherwise use the cap several times over; the count caps
close that gap. By default a `memory.grow` past the cap returns -1 and the
guest keeps running. The host sets `trap_on_grow_failure(true)`, so a growth
past the cap traps and the host revokes the lease. The Wasmtime
documentation notes that this setting is not necessarily spec-compliant.

Reasons, from the Wasmtime documentation at v50.0.2:

- Epochs run faster than fuel: "in some measurements, up to 2-3x". Fuel is for
  cases that need deterministic yielding or trapping.
- Neither epochs nor fuel interrupt a guest that is blocked in a host call.
  The host therefore puts its own timeout on every async host function.
- The epoch counter keeps advancing while a host call runs, so time spent in
  a slow host call counts against the guest's deadline unless the host
  resets the deadline after the call. P3 decides which and tests it.
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
outbound HTTP to one named host, or the points a guest may use. Generating
cloud API plugins from OpenAPI definitions with `progenitor` plus
`wit-bindgen` is a later node, not part of P3. Whether that route works is
not verified: no source was found showing a `progenitor` client (which
depends on `progenitor-client` 0.16.1, MPL-2.0) built for `wasm32-wasip2`
and reaching the network through `wasmtime-wasi-http` 50.0.2.

### Open question

Must a plugin manifest also cap the highest level a guest may take? The
guest type allows levels 2 and 5, which the standard assigns to life safety
and critical equipment. With a cap, a plugin takes those levels only with an
explicit grant, at the cost of one more manifest field and host check.
Without one, the guest type alone bounds the levels. Not decided; it blocks
the final WIT file in P3.

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
- crates.io API, `wasmtime-wasi-http` 50.0.2 (2026-11-16, Apache-2.0 WITH
  LLVM-exception) and `progenitor-client` 0.16.1 (2026-11-15, MPL-2.0),
  checked 2026-11-18T08:39:59+01:00.
- [`docs/plan/design-defects.md`](../plan/design-defects.md), defect 8.
