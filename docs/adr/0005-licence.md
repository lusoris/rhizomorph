<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0005: Project licence and dependency licences

- **Status**: Proposed
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

The repository already ships [`LICENSE`](../../LICENSE) (EUPL-1.2) and checks
file licences with `reuse lint` through [`REUSE.toml`](../../REUSE.toml). The
planned dependencies carry several licence families, and one prior-art
project has no detected licence. This record states the project licence and
lists what the dependencies carry. It gives no legal conclusion.

## Decision

The project licence is **EUPL-1.2**. Every file states its licence in a
header or through `REUSE.toml`.

Dependency licences as checked on 2026-11-18, grouped by family. Every row
comes from the crates.io API except `rusty-bacnet`, which is not on
crates.io (HTTP 404) and was read from its GitHub repository and release:

| Family | Dependencies |
| :--- | :--- |
| MIT | `rusty-bacnet` (git, release v0.15.0); `voltage_modbus` 1.1.0 (not selected); `solar-positioning` 0.7.2 (use not decided) |
| MIT OR Apache-2.0 | `redb` 4.6.0; `fjall` 3.1.13; `tokio-modbus` 0.17.0 |
| Apache-2.0 | `aimdb-knx-connector` 0.6.0; `aimdb-core` 3.0.0 (use not decided); `rs-matter` 0.4.1; `rumqttc` 0.25.1; `rumqttd` 0.20.0 |
| MPL-2.0 | `progenitor` 0.16.1; `progenitor-client` 0.16.1 (runtime of generated code) |
| Apache-2.0 WITH LLVM-exception | `wasmtime` 50.0.2; `wasmtime-wasi` 50.0.2 |
| Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT | `wit-bindgen` 0.63.0 |
| EPL | None used. openHAB is EPL-2.0 prior art, not a dependency |

The UI framework `golusoris/sveltesentio` is EUPL-1.2 (release `ui-v0.9.0`),
read from its GitHub repository because it is not a crate
([ADR-0006](0006-ui-stack.md)).

Rules:

- A **dependency licence check in CI** is a phase task, not yet done. It
  appears in [`plan/phases.md`](../plan/phases.md) as part of the P1 exit
  check (`cargo deny check licenses`; `cargo-deny` 0.21.0, MIT OR
  Apache-2.0, checked 2026-11-18) and runs again whenever a dependency is
  added.
- **REUSE lint already runs** in CI (`.github/workflows/reuse.yml`, step
  `reuse lint`).
- **litehouse** has no licence file detected by the forge. It is read for
  ideas only; no code is copied. The same applies to the reference code of
  the design input ([`plan/design-defects.md`](../plan/design-defects.md)).
- No licence is changed or added by this record.

## Consequences

- **Positive**: One project licence, one checkable header rule, and a
  recorded list of what each planned dependency carries.
- **Negative**: The table is a snapshot; versions and licences can change at
  any release. Until the CI check exists, nothing enforces the list. Whether
  the combination of licences meets any obligation is not assessed here.

## References

- [`LICENSE`](../../LICENSE) and [`REUSE.toml`](../../REUSE.toml).
- crates.io API, `https://crates.io/api/v1/crates/<name>`, checked
  2026-11-18T03:28:19+01:00 and again at 08:43:29+01:00.
- `jscott3201/rusty-bacnet` on GitHub, release v0.15.0, checked 2026-11-18.
- `gh api repos/arlyon/litehouse`, checked 2026-11-18 03:28:59 CET.
- [`AGENTS.md`](../../AGENTS.md): HISS-11 (supply chain).
