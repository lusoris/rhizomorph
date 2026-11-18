<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# Rhizomorph concept

This document explains what rhizomorph is meant to be, what was checked
before the design was written down, and what is still unproven. Start with
[Concept](#concept) and [Best current solution](#best-current-solution); the
rest is reference. The architecture ideas are design input by the operator;
this document and the records under [`docs/adr/`](adr/README.md) restate
them and correct them against the sources checked on 2026-11-18.

## Concept

Rhizomorph is a local-first smart-home and building-automation engine. It
runs on your own hardware, keeps working without a cloud account, and reads
and commands devices such as heating controllers, meters, lights and
sensors. The core is written in Rust; the user interface is a SvelteKit
application that talks to the engine over an API. Every commandable output
has a 16-level priority array, as building automation uses, so an urgent
writer overrides a routine one instead of "last writer wins"; inputs take
telemetry directly ([ADR-0002](adr/0002-priority-array-and-leases.md)). Integrations run in
four isolation tiers so that a faulty plugin cannot take the engine down
([ADR-0001](adr/0001-tier-model.md)).

The name: a **rhizomorph** is a root-like cord of bundled fungal hyphae that
carries water and nutrients over long distances. It comes from Greek *rhiza*
(root) and *morphe* (form) and is pronounced RY-zo-morf. The project borrows
the picture of a network that grows where it is used and keeps working when
one branch is damaged; [`fungal-mapping.md`](fungal-mapping.md) lists which
parts of that picture map to which component, all as analogy. The
[`README.md`](../README.md#name) gives the same explanation.

Status: there is no engine code and no release. The plan is in
[`plan/phases.md`](plan/phases.md).

## Research

What was checked, all on 2026-11-18 between 03:28 and 03:32 CET:

- Crate versions, licences and minimum supported Rust versions (MSRV)
  through the crates.io API, `https://crates.io/api/v1/crates/<name>`.
- Prior-art repositories through the forge API, `gh api repos/<owner>/<name>`.
- The Wasmtime guest-limit documentation in tag v50.0.2
  (`crates/wasmtime/src/config.rs`, `crates/wasmtime/src/runtime/limits.rs`).
- The BACnet priority levels from two open sources, NISTIR 6392 and the
  `rusty-bacnet` source. The ANSI/ASHRAE Standard 135 text is paywalled and
  was not read.
- The redb README benchmark at two commits.
- The memory layout of the priority array, in a scratch program that is not
  committed.

Prior art:

| Project | Version | Licence | Language | Checked | Note |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Home Assistant (`home-assistant/core`) | 2026.11.2 (2026-11-16) | Apache-2.0 | Python | 2026-11-18 | 92451 stars; head d4a49f97eef7 |
| openHAB (`openhab/openhab-distro`, `openhab-core`) | 5.2.4 (2026-11-08) | EPL-2.0 | Java | 2026-11-18 | openhab-core head 42f4d365914e |
| homeCore (`homeCore-io/homeCore`) | no release | Apache-2.0 | Rust | 2026-11-18 | 4 stars, active; head d189a77a9240 |
| litehouse (`arlyon/litehouse`) | v0.3.1 (2024-06-12) | no licence file detected by the forge | Rust 263925 bytes, TypeScript 240012, MDX 28040 | 2026-11-18 | 40 stars; no release for 17 months; head 5415d9eeb465 (2025-12-13) |
| aimdb (`aimdb-dev/aimdb`) | v3.0.0 (2026-11-03) | Apache-2.0 | Rust | 2026-11-18 | 103 stars; head 2036ae1c944f |
| Niagara Framework (Tridium) | 4.15 line; exact build not verified | proprietary, licensed per station | Java | 2026-11-18 | closed source |
| Desigo CC (Siemens) | not verified | proprietary | not verified | 2026-11-18 | closed source |

Crates:

| Crate | Newest stable | Released | Licence | MSRV | Checked | Role in the plan |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| redb | 4.6.0 | 2026-11-13 | MIT OR Apache-2.0 | 1.90 | 2026-11-18 | state store ([ADR-0004](adr/0004-storage-split.md)) |
| fjall | 3.1.13 | 2026-10-25 | MIT OR Apache-2.0 | 1.90.0 | 2026-11-18 | telemetry store |
| wasmtime | 50.0.2 | 2026-11-16 | Apache-2.0 WITH LLVM-exception | 1.97.0 | 2026-11-18 | plugin host |
| wasmtime-wasi | 50.0.2 | 2026-11-16 | Apache-2.0 WITH LLVM-exception | 1.97.0 | 2026-11-18 | WASI 0.2 host side |
| wasmtime-wasi-http | 50.0.2 | 2026-11-16 | Apache-2.0 WITH LLVM-exception | 1.97.0 | 2026-11-18 | outbound HTTP for plugins, later; not verified ([ADR-0003](adr/0003-wit-contract-push-model.md#capabilities)) |
| wit-bindgen | 0.63.0 | 2026-10-14 | Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT | not recorded | 2026-11-18 | guest bindings |
| tokio-modbus | 0.17.0 | 2025-10-22 | MIT OR Apache-2.0 | 1.76 | 2026-11-18 | Modbus worker |
| voltage_modbus | 1.1.0 | 2026-10-09 | MIT | 1.85.0 | 2026-11-18 | alternative Modbus crate, not selected; 3338 downloads in total |
| rusty-bacnet | not on crates.io (HTTP 404) | v0.15.0 on GitHub, 2026-10-29 | MIT | rust-version 1.95 | 2026-11-18 | BACnet worker, later |
| aimdb-knx-connector | 0.6.0 | 2026-11-03 | Apache-2.0 | 1.98.0 | 2026-11-18 | KNX worker, later; 149 downloads in total |
| aimdb-core | 3.0.0 | 2026-11-03 | Apache-2.0 | 1.98.0 | 2026-11-18 | same name prefix as aimdb-knx-connector; relation and use not verified |
| rs-matter | 0.4.1 | 2026-09-17 | Apache-2.0 | 1.87 | 2026-11-18 | Matter worker, later |
| rumqttc | 0.25.1 | 2025-11-21 | Apache-2.0 | 1.64.0 | 2026-11-18 | MQTT worker, later |
| rumqttd | 0.20.0 | 2025-09-29 | Apache-2.0 | 1.70.0 | 2026-11-18 | MQTT, later; role not decided |
| progenitor | 0.16.1 | 2026-11-15 | MPL-2.0 | 1.88 | 2026-11-18 | plugin generation from OpenAPI, later; not verified for `wasm32-wasip2` |
| progenitor-client | 0.16.1 | 2026-11-15 | MPL-2.0 | 1.88 | 2026-11-18 | runtime crate of the code that `progenitor` generates |
| solar-positioning | 0.7.2 | 2026-10-19 | MIT | 1.85 | 2026-11-18 | listed in the check; use not decided |

Notes on the table:

- The rows were read at 03:28 CET and read again at 08:43 CET. The second
  read corrected the wasmtime MSRV (1.97.0, not 1.95.0) and filled the
  release dates and MSRVs that the first read did not record.
- The newest published wasmtime row is the 48.0.9 backport of 2026-11-16;
  the newest stable line is 50.0.2.
- The name `rhizomorph` is free on crates.io (HTTP 404 at the same check).
- rs-matter states support for Matter Specification version 1.6 at README
  line 65, head c86233d31090. It has no GitHub release; the version above
  comes from crates.io.
- `rusty-bacnet` is a workspace of many crates (`bacnet-bip-codec`,
  `bacnet-bip-core`, `bacnet-client`, `bacnet-encoding`, `bacnet-mstp-*`,
  `bacnet-network`, `bacnet-npdu`, `bacnet-objects`, `bacnet-ops` and more),
  edition 2024, default branch `dev`.

## Gain and cost

What the design is meant to gain over prior art. These are design
properties, not measured results.

- **Fault isolation by tier.** A plugin trap, memory overrun or missed
  deadline ends that plugin and releases what it wrote; kernel state stays.
  The README states the fault in typical hubs (one shared process); this
  was not verified for each product listed below.
- **Arbitration by priority.** A priority array per commandable point lets a
  safety writer override a schedule, and a lease makes the override end when
  its owner fails ([ADR-0002](adr/0002-priority-array-and-leases.md)).
- **A small, testable kernel.** A `no_std` core with explicit bounds, written
  against the HISS invariants in [`AGENTS.md`](../AGENTS.md).

What it costs:

- **Young dependencies.** `aimdb-knx-connector` has 149 downloads in total;
  `rs-matter` is at 0.4.1; `voltage_modbus` has 3338 downloads in total.
  Dependencies that are young can change their interface or stop being
  maintained.
- **A BACnet stack outside crates.io.** `rusty-bacnet` is a git dependency
  until a crates.io release exists; the choice is made in the fieldbus phase.
- **A wide MSRV spread.** From 1.64.0 (rumqttc) to 1.98.0
  (aimdb-knx-connector, aimdb-core). The layout scratch program used rustc 1.98.1. The
  workspace toolchain is not yet chosen.
- **No numbers on own hardware.** The storage benchmark figures are the redb
  author's, on the author's hardware. Nothing about latency, memory use or
  throughput of rhizomorph has been measured.
- **No engine code.** Every competitor below ships; this repository does not.

## Market and prior art

Only facts in the tables above are used. Feature comparisons beyond them
were not made and are marked as such.

**Home Assistant.** Apache-2.0, Python, release 2026.11.2 of 2026-11-16, and
92451 stars: by that measure the largest community among the projects
checked. Where rhizomorph differs: it targets a priority array and lease
model and tier isolation, which this check did not look for in Home
Assistant. Whether Home Assistant lacks them is not verified.

**openHAB.** EPL-2.0, Java, release 5.2.4 of 2026-11-08. Its feature set
was not read for this document. Where rhizomorph differs: Rust instead of Java, and EUPL-1.2 instead of
EPL-2.0 ([ADR-0005](adr/0005-licence.md)).

**homeCore.** Apache-2.0, Rust, active, 4 stars, no release. It is
one of three Rust projects in the table, with aimdb and litehouse. What it
implements was not read for this document; a design comparison is a task
before the kernel phase ends.

**litehouse.** No licence file detected by the forge, so it is read for
ideas only and no code is copied. v0.3.1 of 2024-06-12 and no release for
17 months; the head dates from 2025-12-13. About 45 % of its counted
bytes are TypeScript, so it is not a Rust-only project. Where rhizomorph
differs: it has a declared licence and a plan; litehouse has code.

**aimdb.** Apache-2.0, Rust, v3.0.0 of 2026-11-03, 103 stars. The KNX connector
crate shares its name prefix; the exact relation was not verified. The design
input named v1.1.0; that was stale. What aimdb implements was not read, so
how far its model overlaps with the priority and lease semantics is not
verified.

**Niagara Framework (Tridium).** Commercial, proprietary, licensed per
station, Java. The 4.15 line is current by a distributor note naming update
4.15u6, and the vendor timeline announces Niagara 5 on Java 25. The exact
current build is not verified: no public version feed exists. Where
rhizomorph differs: open source, no per-station licence. It does not match
Niagara's installed base or integrator ecosystem.

**Desigo CC (Siemens).** Commercial, proprietary. The product version is not
verified. Siemens data sheet A6V11993473, dated 2026-10-30, states BACnet
revision 1.23 and BTL certification as B-XAWS and B-AWS. Where rhizomorph
differs: it has no BACnet certification and no BACnet stack yet.

## Best current solution

For a home today, pick **Home Assistant**. It is Apache-2.0, released on
2026-11-16 and has the largest community of the projects checked (92451
stars). **openHAB** is the alternative if a Java platform is preferred.
This pick rests on licence, release date and community size only; no
feature comparison was made.

For a commercial building today, pick an established building-automation
product: **Niagara Framework** or **Desigo CC**. Desigo CC carries BTL
certification for BACnet per the Siemens data sheet named above; certified
BACnet interoperability and vendor support are what a building operator
needs and what rhizomorph cannot offer. Which of the two fits a given
building depends on facts this document did not verify, such as product
version and price.

Why rhizomorph is still worth building: it aims at one engine that spans both
worlds, with a priority-array model, isolated tiers for third-party code
and a small Rust core under the HISS invariants. That gain is unproven until
the kernel phase tests pass and a benchmark runs on target hardware. Until
then, treat the project as a design, not as an alternative to use.

## Ecosystem edges

- **`golusoris/sveltesentio`:** public, EUPL-1.2, release `ui-v0.9.0`
  (2026-10-26), head a4b69b8b547e. A composable SvelteKit framework on
  Svelte 5 runes. The UI phase builds on it ([ADR-0006](adr/0006-ui-stack.md)).
- **`cordanaLLM/20-watts-was-enough`:** public research repository, head
  a40c862c (2026-11-17). Source of the fungal-network analysis used in
  [`fungal-mapping.md`](fungal-mapping.md).
- **`plurano/amussis`:** public sibling project in Rust, with the same
  engine gates.
- **`cordanaLLM/praetor`:** public standards engine that writes the gates of
  this repository.
- **Cluster deployment (Kubernetes) and the shared design system:** named as
  later edges. No artefact exists in this repository yet.

## Open and unverified

Unverified:

- Exact current Niagara build; no public version feed.
- Desigo CC product version.
- BACnet clause numbering against the current edition of Standard 135. The
  text is paywalled and was not read; the level names rest on NISTIR 6392
  (135-1995) and the `rusty-bacnet` source, which agree on the five assigned
  names.
- Whether the priority-array layout of 384 bytes holds on other compilers or
  targets. Rust does not guarantee it.
- Storage performance on target hardware.
- Feature overlap with homeCore, aimdb, Home Assistant and openHAB.
- Versions of crates not listed in the tables, including the async runtime.
- How credentials stored in redb are protected at rest.
- Whether a client generated by `progenitor` builds for `wasm32-wasip2` and
  reaches the network through `wasmtime-wasi-http`.

Stale or corrected design claims:

- `rusty-bacnet` v0.13.0 with 17 crates: stale. The release is v0.15.0 and
  the workspace holds more crates; it is not on crates.io.
- aimdb v1.1.0: stale. The release is v3.0.0.
- Guest limits named as one metering that combines epochs and fuel
  (paraphrased; design input, 2026-11-18, guest limits): a conflation of two
  Wasmtime mechanisms, corrected in
  [ADR-0003](adr/0003-wit-contract-push-model.md).
- Revoke claimed to take constant time (paraphrased; design input,
  2026-11-18, revoke bound): false for the reference design; see
  [`plan/design-defects.md`](plan/design-defects.md) and
  [ADR-0002](adr/0002-priority-array-and-leases.md).
- The redb benchmark figures in the design input match the README at commit
  a11e7ef089bb; the README changed the same night to rates at commit
  b3e8ab8ecfe0. Both are the author's numbers.
- The fungal pre-registration is ordered in the research repository but not
  yet on its default branch.
