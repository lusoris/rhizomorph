---
description: Local-first smart-home and building-automation engine.
---
<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>
SPDX-License-Identifier: EUPL-1.2
-->

# rhizomorph

rhizomorph is a planned local-first smart-home and building-automation engine:
a Rust core with a SvelteKit interface ([concept](concept.md)).

**Status: design.** There is no engine code and no release yet. Code follows
the [phase plan](plan/phases.md), starting with P1.

## The name

A **rhizomorph** is a root-like cord of bundled fungal hyphae. A fungus grows
these cords to carry nutrients over long distances and to explore for new
food away from the place it already feeds on.

- **Origin:** Greek *rhiza* (root) and *morphe* (form): "root-form".
- **Pronunciation:** RY-zo-morf.
- **The honey fungus:** *Armillaria*, the honey fungus, spreads from tree to
  tree through the soil along its rhizomorphs. One *Armillaria ostoyae* in
  Oregon covers more than 8.8 square kilometres.
- **Why this name:** an analogy, not a claim: like a fungal network, the
  engine grows by adding small isolated parts and falls back to another path
  when one fails. [Name and analogy](fungal-mapping.md) lists each part
  of the analogy and which ones have no component yet.

Source for the biology: the Wikipedia articles "Mycelial cord" and
"Armillaria", read 2026-11-18.

## Where to start

| Page | What it covers |
| :--- | :--- |
| [Concept](concept.md) | Design, research, prior art and unverified points. |
| [Phase plan](plan/phases.md) | Order of work and exit checks. |
| [Hardware plan](plan/hardware.md) | Stages H0 to H3, entry conditions and exit checks. |
| [Decision records](adr/README.md) | Architectural decisions and their status. |
| [Contributing](../CONTRIBUTING.md) | Standards, testing and local verification. |
