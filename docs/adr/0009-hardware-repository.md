<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0009: Hardware repository

- **Status**: Accepted
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

Start with [Decision](#decision) for what stays in `lusoris/rhizomorph`, what
goes into `lusoris/sporocarp`, and what `sporocarp` means;
[Consequences](#consequences) and [References](#references) cover cross-repo
maintenance and sources.

[`docs/plan/hardware.md`](../plan/hardware.md#open-questions) (question 2) asked
whether `H1` open-firmware configurations, `H2` KiCad carrier board projects,
and `H3` parametric enclosure models should live in subdirectories of
`lusoris/rhizomorph` or in a dedicated sibling repository
([`docs/plan/hardware.md`](../plan/hardware.md#stages)).

`H0` off-the-shelf device profiles and `H1` open-firmware and gateway
configurations are declarative TOML maps and software bridge configurations that
pair directly with the `EUPL-1.2` fieldbus workers in `lusoris/rhizomorph`
([ADR-0001](0001-tier-model.md), [ADR-0005](0005-licence.md)). By contrast, `H2`
carrier board schematics and PCB layouts and `H3` 3D enclosure models are
licensed under `CERN-OHL-W-2.0` ([ADR-0008](0008-hardware-licence.md)), run
heavy EDA and CAD verification pipelines (`KiCad`, `KiBot`, `build123d`,
`CadQuery`, `FreeCAD`), and release on physical hardware revision cycles. This
record states the placement and naming decision made by the owner on 2026-11-18
(paraphrased).

## Decision

Decided by the owner on 2026-11-18 (paraphrased):

1. **Repository split:**
   - **`lusoris/rhizomorph`** retains all `H0` declarative device profiles and
     `H1` open-firmware and gateway configurations under `EUPL-1.2`
     ([ADR-0005](0005-licence.md),
     [`docs/plan/hardware.md`](../plan/hardware.md#stages)).
   - **`lusoris/sporocarp`** is the dedicated sibling repository for all `H2`
     KiCad carrier board designs and `H3` enclosure CAD models under
     `CERN-OHL-W-2.0` ([ADR-0008](0008-hardware-licence.md),
     [`docs/plan/hardware.md`](../plan/hardware.md#stages)).
2. **Name (`sporocarp`):**
   - **Meaning:** The fruiting body of a fungus—the multicellular structure on
     which spore-producing structures (such as basidia or asci) are borne
     ([References](#references)).
   - **Origin:** English `sporo-` (from `spore`, from Ancient Greek *spora*,
     seed, sowing) + `-carp` (from Ancient Greek *karpos*, fruit).
   - **Pronunciation:** Three syllables, said **SPOR-oh-karp**.
   - **Fit with `rhizomorph`:** Where a **rhizomorph**
     ([`README.md`](../../README.md#name),
     [`docs/fungal-mapping.md`](../fungal-mapping.md)) is the root-like cord of
     fungal hyphae that transports nutrients across the network, a **sporocarp**
     is the physical fruiting structure that emerges from the mycelium,
     matching physical carrier boards and enclosures mounted in a building.
3. **Creation order and initial contents:**
   - `lusoris/sporocarp` is **not created yet**. Creating the repository is the
     first step of stage `H2`
     ([`docs/plan/hardware.md`](../plan/hardware.md#stages)) and happens only
     after [ADR-0008](0008-hardware-licence.md) has landed on `main` in
     `lusoris/rhizomorph`.
   - When `lusoris/sporocarp` is created at the start of `H2`, its initial setup
     carries:
     1. Praetor governance adoption (`praetorctl`).
     2. A `README.md` that explains the name `sporocarp` (meaning, Greek origin,
        pronunciation, and relation to `rhizomorph`).
     3. `REUSE` compliance (`REUSE.toml` and `reuse lint`) carrying the
        `CERN-OHL-W-2.0` licence text (`LICENSES/CERN-OHL-W-2.0.txt`,
        [ADR-0008](0008-hardware-licence.md)).

## Consequences

- **Positive**: `lusoris/rhizomorph` stays focused on the `EUPL-1.2` Rust
  engine, protocol workers, and `H0`/`H1` device profiles
  ([ADR-0005](0005-licence.md)), while `lusoris/sporocarp` isolates the
  `CERN-OHL-W-2.0` `H2`/`H3` hardware designs
  ([ADR-0008](0008-hardware-licence.md)) and `KiBot`/`OCCT` CAD CI gates. No
  empty hardware repository is created before `H2` work starts.
- **Negative**: Two repositories must be kept in step wherever `H0`/`H1` device
  profiles or firmware interfaces in `lusoris/rhizomorph` and `H2`/`H3` board or
  enclosure designs in `lusoris/sporocarp` refer to each other (such as the
  documented pin maps, bus protocols, and connector definitions required by
  [ADR-0008](0008-hardware-licence.md)). Releases, version tags, and changelogs
  are managed per repository.

## References

- Owner decision of 2026-11-18, paraphrased
  (`rhizomorph-hardware-repo-placement`).
- [`docs/plan/hardware.md`](../plan/hardware.md): stages `H0`–`H3` and open
  question 2.
- [ADR-0008](0008-hardware-licence.md): `CERN-OHL-W-2.0` hardware licence and
  documented firmware interface rule.
- [`README.md`](../../README.md#name) and
  [`docs/fungal-mapping.md`](../fungal-mapping.md): fungal naming of
  `rhizomorph`.
- Wikipedia, "Sporocarp (fungi)",
  <https://en.wikipedia.org/wiki/Sporocarp_(fungi)>, read 2026-11-18.
- Wiktionary, "sporocarp" (<https://en.wiktionary.org/wiki/sporocarp>),
  "sporo-" (<https://en.wiktionary.org/wiki/sporo->), "spore"
  (<https://en.wiktionary.org/wiki/spore>), and "-carp"
  (<https://en.wiktionary.org/wiki/-carp>), read 2026-11-18.
