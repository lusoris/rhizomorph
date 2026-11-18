<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0006: User interface stack

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

The README names a SvelteKit interface for the engine. A sibling public
project in the same ecosystem, `golusoris/sveltesentio`, offers a
composable SvelteKit framework. The UI must not weaken the isolation that
[ADR-0001](0001-tier-model.md) sets up. This record restates a design input
by the operator.

## Decision

- The UI is a SvelteKit application built on `golusoris/sveltesentio`:
  public, EUPL-1.2, release `ui-v0.9.0` (2026-10-26), head a4b69b8b547e,
  Svelte 5 runes, checked 2026-11-18.
- **The UI talks to the daemon API only, never to the kernel.** The kernel
  has no network and no serialization dependency. The daemon API is the one
  place that authenticates a UI session and gives it a lease
  ([ADR-0002](0002-priority-array-and-leases.md)); a UI session therefore
  writes at the priorities the daemon allows it, and its commands end with
  its lease.
- The API protocol and its schema are not decided here; they are a P4 task.
  The UI phase P5 builds on the P4 API.

## Consequences

- **Positive**: The UI can fail, restart or be replaced without touching the
  kernel; a closed browser session releases its commands.
- **Negative**: `sveltesentio` is at version 0.9.0, so its interface can
  still change. The daemon API becomes a contract that needs its own
  versioning and tests.

## References

- Design input by the operator, restated; no document is quoted.
- `golusoris/sveltesentio`, release `ui-v0.9.0`, head a4b69b8b547e, checked
  2026-11-18.
- [`README.md`](../../README.md): the SvelteKit interface.
- [`docs/plan/phases.md`](../plan/phases.md), phases P4 and P5.
