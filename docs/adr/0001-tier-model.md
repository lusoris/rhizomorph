<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0001: Four-tier isolation model

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

A home or building controller runs code of very different trust and cost:
a small arbitration core, protocol drivers that must poll hardware in real
time, third-party integrations such as cloud APIs, and heavy work such as
video or local language models. The README names the fault of a typical hub:
every integration shares one process, so one fault stops all of them
([`README.md`](../../README.md#what-it-is-meant-to-become)). This record
restates a design input by the operator and fixes what runs where.

## Decision

Rhizomorph has four tiers. Each tier has one trust level and one failure
rule.

| Tier | What runs there | Isolation | Trust | Failure handling |
| :--- | :--- | :--- | :--- | :--- |
| 0 Kernel | Point arena, priority arrays, leases, deadband, change-of-value (COV) fan-out | None; it is the daemon core | Trusted, first-party | A kernel fault is a daemon fault. The kernel therefore has no network, no serialization and no plugin code |
| 1 Native fieldbus workers | One async task per protocol: Modbus first; BACnet, KNX, Matter, MQTT later | Task boundary inside the daemon process | Trusted, first-party or reviewed dependencies | A panic ends the task; the supervisor restarts it. Its lease is revoked and the new task takes a new lease. Kernel state stays intact |
| 2 WASI 0.2 component plugins | WebAssembly components built for `wasm32-wasip2`, run on Wasmtime | Wasmtime sandbox, deny by default | Untrusted | A trap, memory overrun or missed deadline ends the call; the host revokes the plugin's lease ([ADR-0003](0003-wit-contract-push-model.md)) |
| 3 Unix-domain-socket sidecars | Separate processes for heavy work: video, voice, local language models | Operating-system process | Untrusted, own resources | The socket closes; the daemon revokes the sidecar's lease. A sidecar crash never touches the daemon |

### What runs where, and why

- **Tier 0** holds only what must be correct and fast: an in-memory arena of
  points addressed by dense numeric ids. It is split into a `no_std` core
  crate and a separate `std` adapter that supplies the clock, locking and the
  broadcast channel. The channel has a fixed capacity (HISS-06); what a
  subscriber that lags behind loses is decided and tested in P4
  ([ADR-0004](0004-storage-split.md)). The reference design declared
  `no_std` and still imported `std`
  ([`plan/design-defects.md`](../plan/design-defects.md), defect 1).
- **Tier 1** runs native because fieldbus work needs low overhead and
  direct socket access. Device profiles are declarative TOML register maps.
  At start a worker registers each point with its deadband and writability,
  receives a point id and interns the string key once.
- **Tier 2** is for code that the project does not review: cloud API
  plugins and user scripts. Capabilities are declared in a manifest, for
  example outbound HTTP to one named host. Generating plugins from OpenAPI
  definitions with `progenitor` (MPL-2.0) and `wit-bindgen` is a later node
  and not verified ([ADR-0003](0003-wit-contract-push-model.md#capabilities)).
- **Tier 3** is for work whose memory and CPU use would harm the daemon. The
  first transport is a Unix domain socket. Shared memory is named in the
  design input and is not decided here. A sidecar runs as its own process,
  but no limit on its memory or CPU is decided yet; phase P10 decides it.

### Trust boundary

- Tiers 0 and 1 share one address space. A memory-safety fault or abort in
  a worker can end the daemon; only a panic is contained, and only while the
  release profile unwinds rather than aborts. Phase P2 carries a test that a
  worker panic leaves kernel state intact ([`plan/phases.md`](../plan/phases.md)).
- Tier 2 is separated by the Wasmtime sandbox. Its limits are in
  ADR-0003.
- Tier 3 is separated by the operating system. The daemon treats every
  message from a sidecar as untrusted input and puts an explicit deadline
  on every socket call (HISS-02).
- Every writer in every tier holds a host-assigned lease; no tier writes a
  priority-array slot without one ([ADR-0002](0002-priority-array-and-leases.md)).

## Consequences

- **Positive**: A fault in a plugin or sidecar is contained and its writes are
  released automatically. The kernel can be tested without any network.
- **Negative**: Four tiers mean four failure modes to test and document.
  Tier 1 gives no memory isolation. The `std` adapter is one more crate to
  keep in step with the core. The sidecar protocol, its message format and
  its resource limits are not yet designed.

## References

- Design input by the operator, restated; no document is quoted.
- [`README.md`](../../README.md): the faults the tiers answer.
- [`docs/concept.md`](../concept.md): crates checked on 2026-11-18, including
  wasmtime 50.0.2 and progenitor 0.16.1.
- [`AGENTS.md`](../../AGENTS.md): HISS-02 (explicit deadline on every I/O call).
