# Rhizomorph

Local-first smart-home and building-automation engine: a Rust core with a
SvelteKit interface.

> **Status: founding.** This repository holds governance, licence and agent
> rules only. There is no engine code and no release yet. The plan documents
> and decision records arrive next under `docs/`; code follows them.

## Start here

1. Read [Name](#name) for what the project is called and why.
2. Read [What it is meant to become](#what-it-is-meant-to-become) for the
   goal and the three faults it sets out to avoid.
3. To contribute, read [`CONTRIBUTING.md`](CONTRIBUTING.md), then run the
   repository gate once:

   ```bash
   make verify-all
   ```

   The steps of that gate are in [`Makefile`](Makefile).

## Name

A **rhizomorph** is a root-like cord of bundled fungal hyphae. A fungus grows
these cords to carry nutrients over long distances and to explore for new
food away from the place it already feeds on.

- **Origin:** Greek *rhiza* (root) and *morphe* (form): "root-form".
- **Pronunciation:** RY-zo-morf.
- **The honey fungus:** *Armillaria*, the honey fungus, spreads from tree to
  tree through the soil along its rhizomorphs. One *Armillaria ostoyae* in
  Oregon covers more than 8.8 square kilometres.
- **Why this name:** the design borrows from fungal networks: sparse sensing,
  a mesh of small nodes, and routing decided locally instead of by one
  central process.

Source for the biology: the Wikipedia articles "Mycelial cord" and
"Armillaria", read 2026-11-18.

## What it is meant to become

A home and building controller that runs on your own hardware and keeps
working without a cloud account. It is meant as an alternative to existing
home-automation hubs, built to avoid three structural faults:

| Fault in a typical hub | Intended answer |
| :--- | :--- |
| Every integration shares one process, so one fault stops all of them | Isolated tiers: a small kernel, native fieldbus workers, sandboxed plugins, sidecars |
| The last writer to a point wins, whatever its importance | A priority array per point with leases, as building automation uses |
| Each device driver is written by hand | Drivers generated from typed interface contracts |

These are goals, not shipped behaviour. Each becomes a decision record under
[`docs/adr/`](docs/adr/README.md) before any code implements it.

The design input is by the operator; the documents in this repository are
written from it.

## Documentation

- [`docs/concept.md`](docs/concept.md): what rhizomorph is, the research behind
  it, prior art and what is still unverified.
- [`docs/adr/`](docs/adr/README.md): decision records, from the tier model to
  the UI stack.
- [`docs/plan/phases.md`](docs/plan/phases.md): the phase plan, with exit
  checks.
- [`docs/plan/design-defects.md`](docs/plan/design-defects.md): known defects
  of the design reference code and their fixes.
- [`docs/fungal-mapping.md`](docs/fungal-mapping.md): how the name maps to
  components, as analogy.

## Repository layout

| Path | Purpose |
| :--- | :--- |
| [`AGENTS.md`](AGENTS.md) | The one canonical rule file for coding agents; the per-client files are compiled from it |
| [`.standards.yaml`](.standards.yaml) | Declared governance policy of this repository |
| [`Makefile`](Makefile) | `make verify-all`, the repository gate |
| [`lefthook.yml`](lefthook.yml) | Local pre-commit and pre-push checks |
| [`.github/rulesets/main.json`](.github/rulesets/main.json) | Protection of the `main` branch, as applied on the forge |
| [`docs/adr/`](docs/adr/README.md) | Decision records |
| [`REUSE.toml`](REUSE.toml), [`LICENSES/`](LICENSES/) | Licence of every file |

## Related projects

- [Praetor](https://github.com/cordanaLLM/praetor): the governance engine that
  wrote the agent rules, hooks and gate in this repository.

## Licence

[EUPL-1.2](LICENSE). Every file states its licence in a header or through
[`REUSE.toml`](REUSE.toml); `reuse lint` checks that.

## Security

Report a vulnerability as [`SECURITY.md`](SECURITY.md) describes.

<!-- praetor:readme-governance:start -->
[![HISS Adopted][praetor-hiss-badge]][praetor-hiss-agents]

Praetor manages this repository's declared governance policy. This managed
block records adoption state; it is not a verification certificate.

**Verification**: `make verify-all` runs the repository's configured
verification cascade.

**HISS Audit**: `praetorctl audit` enforces policy, generated-surface
integrity, and the debt ratchet.

**Context Sync**: `praetorctl compile-context --verify` verifies every
generated agent context against `AGENTS.md`.

**Debt Baseline**: `.standards-baseline.json` anchors the debt ratchet at
0 recorded infractions; audit forbids growth.

[praetor-hiss-badge]: https://img.shields.io/badge/Standards-HISS%20Adopted-blue
[praetor-hiss-agents]: https://github.com/lusoris/rhizomorph/blob/HEAD/AGENTS.md
<!-- praetor:readme-governance:end -->
