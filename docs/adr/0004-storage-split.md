<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0004: Storage split between redb and fjall

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

The daemon keeps two kinds of data. **State** is small and must be exact:
point definitions, mappings, default priority values, and credentials. It is
read at boot to rebuild the in-memory arena. **Telemetry** is the stream of
COV events: large, append-heavy and tolerant of loss at a crash. One engine
rarely suits both. This record restates a design input by the operator.

## Decision

- **redb** holds state: point definitions, mappings, relinquish defaults
  and default priority values ([ADR-0002](0002-priority-array-and-leases.md)),
  and credentials. The daemon reads it at boot to rebuild the arena.
- **fjall** takes the COV telemetry stream through an asynchronous pipeline
  fed by the broadcast channel of the kernel. The kernel never waits for it.

Versions checked on 2026-11-18 through the crates.io API: redb 4.6.0
(2026-11-13, MIT OR Apache-2.0, MSRV 1.90); fjall 3.1.13 (2026-10-25,
MIT OR Apache-2.0, MSRV 1.90.0).

### Benchmark evidence, and its limit

The evidence is the redb README, the redb author's benchmark on the author's
hardware: a Ryzen 9950X3D with a Samsung 9100 PRO NVMe drive. The benchmark
source is `crates/redb-bench-compare/benches/lmdb_benchmark.rs`.

- At commit a11e7ef089bb (2026-11-18T00:48:05Z) the README reports durations.
  Individual writes: redb 920 ms, fjall 3488 ms. `len()`: redb 0 ms, fjall
  1181 ms. Bulk load: 17063 ms. Uncompacted size: 4.00 GiB. The design input
  figures match this revision exactly.
- At commit b3e8ab8ecfe0, the same night, the README reports rates instead.
  Individual writes: redb 1.11K txn/s, fjall 414. Small batch writes: fjall
  254K key/s, redb 79.2K. Writes without sync: fjall 595K, redb 88.9K.
  `len()`: redb 0 ms, fjall 972 ms. Bulk load: redb 608K, fjall 390K.
- Both revisions support the same split: redb leads on durable single
  transactions and `len()`, fjall leads on batched and unsynced writes.

These are the author's numbers. Nothing was measured on project hardware. An
**own benchmark on target hardware gates the final decision**: phase P4
carries it as a gate, and this record stays Proposed until the result is
written into it.

## Consequences

- **Positive**: Each workload gets the engine that the evidence favours; a
  slow telemetry write cannot delay a state transaction or the kernel.
- **Negative**: Two engines mean two file formats, two recovery paths and two
  upgrade paths. Telemetry still in the pipeline can be lost at a crash. How
  credentials are protected at rest in redb is not decided. The decision may
  change after the P4 benchmark.

## References

- Design input by the operator, restated; no document is quoted.
- redb README, repository `cberner/redb`, commits a11e7ef089bb and
  b3e8ab8ecfe0, checked 2026-11-18.
- crates.io API, `https://crates.io/api/v1/crates/redb` and
  `https://crates.io/api/v1/crates/fjall`, checked 2026-11-18T03:28:19+01:00.
- [`docs/plan/phases.md`](../plan/phases.md), phase P4.
