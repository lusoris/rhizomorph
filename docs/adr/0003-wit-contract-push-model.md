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
  skipped. The host still validates every level against `Priority`, and
  against the manifest's level cap ([Priority cap](#priority-cap)).
- **Bounded guests.** The number of guest stores that run at once has a
  fixed upper bound, set in P3 (HISS-06).

### Guest limits

Four Wasmtime mechanisms bound a guest, and the design uses each for a
different job.

| Mechanism | Wasmtime item | Use in rhizomorph |
| :--- | :--- | :--- |
| Epoch interruption | `Config::epoch_interruption` (`config.rs` line 788): a global counter that the host increments | Wall-clock deadline of every guest call |
| Memory and count caps | `StoreLimitsBuilder` (`limits.rs`), attached with `Store::limiter`: `memory_size(bytes)` (line 238), `table_elements` (line 250), `instances` (line 260), `tables` (line 270), `memories` (line 280), `trap_on_grow_failure` (line 294) | A cap of a few MiB on each linear memory, a cap on table elements, and caps on the number of instances, tables and memories in a store, so the caps bound the linear memory and table space the instances of the store allocate; the values are set in P3 |
| Async host functions | Host functions that await | Blocking calls such as network access, with a host-side timeout |
| Fuel | `Config::consume_fuel` (`config.rs` line 643): instrumented code, deterministic, a store starts with no fuel | Only in replay tests that need a deterministic trap |

`memory_size` limits each linear memory on its own, so a guest with several
memories could otherwise use the cap several times over; the count caps
close that gap. By default a `memory.grow` past the cap returns -1 and the
guest keeps running. The host sets `trap_on_grow_failure(true)`, so a growth
past the cap traps and the host revokes the lease. The Wasmtime
documentation notes that this setting is not necessarily spec-compliant. The
caps cover only what the instances of the guest allocate, because the
Wasmtime documentation states that the bookkeeping of Wasmtime itself and
allocations made by the embedder are not tracked (`limits.rs` lines 21 to
25). Open, decided in P3: a budget for host-side allocations a guest can
cause through host functions.

Reasons, from the Wasmtime documentation at v50.0.2:

- Epochs run faster than fuel: "in some measurements, up to 2-3x". Fuel is for
  cases that need deterministic yielding or trapping.
- Neither epochs nor fuel interrupt a guest that is blocked in a host call.
  The host therefore puts its own timeout on every async host function.
- The epoch counter keeps advancing while a host call runs, so time spent in
  a host call counts against the guest's wall-clock deadline. That deadline
  is absolute and is never reset after a host call; if P3 also keeps a
  budget of guest execution time that excludes host calls, it tracks that
  budget separately and under the absolute deadline
  ([`phases.md`](../plan/phases.md#p3-wasm-host)).
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

### Priority cap

The guest type allows levels 2 and 5, which the standard assigns to
Automatic-Life Safety and Critical Equipment Control. A manifest therefore
caps the levels its guest may take:

- **Declared cap.** Every plugin manifest declares the strongest level its
  guest may command, a number from 9 to 16. Without a declaration the cap is
  9, so the guest takes levels 9 to 16.
- **Grants for 2 and 5.** A plugin manifest may only request level 2 or
  level 5; it cannot grant either. The grant is a host-side record made by
  the installation administrator when the plugin is installed, bound to the
  plugin's content digest. One record covers one level: a record for 2 does
  not open 5, and the reverse.
- **Two host checks.** At load, the host refuses a cap outside 9 to 16, a
  level request for any level other than 2 or 5, or a request for level 2 or
  5 without a matching host record for that plugin's digest (fail closed; a
  record for one digest does not load another digest, so a new plugin build
  needs a new record). On every `command-point` and `relinquish-point` call,
  the level must be at or weaker than the cap, or be a requested level whose
  host record still exists; revoking the record refuses the next command at
  that level.
- **Levels 3, 4, 7 and 8.** The guest type can express them, but no cap and
  no grant opens them, so the host refuses them for every guest.
- **Level 1** stays outside the guest type, so no manifest can request it.

Publisher-signed grants are not accepted; a later decision may add them only
as an additional check after a stated key-handling design, never as a
replacement for the host record. P3 fixes the manifest syntax, the host
record format, and which digest algorithm covers which files, with the final
WIT file ([`phases.md`](../plan/phases.md#p3-wasm-host)).

Revoking a record also relinquishes every slot the guest holds at the
revoked level, through the per-lease point index of
[ADR-0002](0002-priority-array-and-leases.md#the-real-bound-of-revoke), and
fires COV as a lease revoke does; its slots at other levels stay. An
administrator who wants such a value kept commands it at that level as a
writer outside the guest; ADR-0002 lists those writers as not yet decided.

## Consequences

- **Positive**: A guest cannot hold, leak or guess a lease. Time and memory
  are bounded by separate mechanisms with stated limits. The corrected
  wording avoids a configuration that never enabled fuel.
- **Negative**: The deadline protects against code running, not against a
  guest blocked in a host call; every host function needs its own timeout.
  Epoch interruption excludes the Winch compiler. A guest without level 1 can
  never perform a manual life-safety override. The priority cap adds one
  manifest field, level requests, a host record per plugin build made by the
  administrator, and two host checks; a plugin that needs level 2 or 5 must
  request it and needs its record at every new build.

## References

- Design input by the operator, restated; no document is quoted.
- Priority cap: owner decision (paraphrased; decision, 2026-11-18, guest
  priority cap), restated in [Priority cap](#priority-cap).
- Grant provenance: derived from the priority cap decision (paraphrased;
  decision, 2026-11-18, guest grant provenance), restated in
  [Priority cap](#priority-cap).
- Wasmtime tag v50.0.2, `crates/wasmtime/src/config.rs` (sha256
  fa5c06563662) and `crates/wasmtime/src/runtime/limits.rs` (sha256
  07d25368279a), checked 2026-11-18.
- [`docs/concept.md`](../concept.md): wasmtime 50.0.2, wasmtime-wasi 50.0.2,
  wit-bindgen 0.63.0, progenitor 0.16.1.
- crates.io API, `wasmtime-wasi-http` 50.0.2 (2026-11-16, Apache-2.0 WITH
  LLVM-exception) and `progenitor-client` 0.16.1 (2026-11-15, MPL-2.0),
  checked 2026-11-18T08:39:59+01:00.
- [`docs/plan/design-defects.md`](../plan/design-defects.md), defect 8.
