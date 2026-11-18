<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# Fungal mapping

The name links the project to fungal networks. A **rhizomorph** is a
root-like cord of fungal hyphae that transports water and nutrients over
long distances ([`README.md`](../README.md#name)). This document lists where
that picture lines up with a rhizomorph component. **Every row is an
analogy.** It explains the design; it is not evidence that the design works.

## Boundary

The source is the audit
`research/audits/2026-08-05-fungal-networks-resource-allocation.md` in the
public repository `cordanaLLM/20-watts-was-enough` (head a40c862c,
2026-11-17). Its executive result says the fungal evidence supports a
growing transport network whose load, inventory, topology and repair state
cannot be separated. It is not evidence for a hidden optimizer.

- **No measured gain is claimed** here, for any row.
- The audit names two candidate experiments:
  `experiments/candidates/001-adaptive-topology.md` and
  `experiments/candidates/013-deficit-capability-routing.md`. This document
  does not claim which candidate covers which row.
- A fungal Kubernetes pre-registration is ordered in that repository and is
  **pending**: it was not on the default branch at the check of 2026-11-18.

## Mapping

| Fungal concept | Rhizomorph component | Status | Kind |
| :--- | :--- | :--- | :--- |
| Branching: a network grows out to reach more sources | Reach of the fieldbus workers: a new protocol worker adds a branch to the engine ([ADR-0001](adr/0001-tier-model.md), tier 1) | Planned from P2 | Analogy |
| Anastomosis: hyphae fuse into alternative paths | Alternative paths between a point and its writers or sources; fallback paths | Not designed; no component exists | Analogy |
| Cord thickening on use and regression of low-value regions | An adaptive topology that favours used paths and drops idle ones; candidate `001-adaptive-topology.md` | Not designed; no component exists | Analogy |
| Damage plugging: a damaged part is sealed off | Lease revoke and tier isolation: a failed plugin's slots are cleared and the fault stays in its tier ([ADR-0001](adr/0001-tier-model.md), [ADR-0002](adr/0002-priority-array-and-leases.md)) | Planned in P1 and P3 | Analogy |
| Later bypass: flow finds a way around a blocked part | Fallback to the next priority slot when a slot is cleared ([ADR-0002](adr/0002-priority-array-and-leases.md)) | Planned in P1 | Analogy |

Three of five rows describe components that are already part of the plan.
The two rows marked "not designed" are placeholders; no decision record or
phase covers them yet.

## Source and check

- Audit and candidates: `cordanaLLM/20-watts-was-enough`, head a40c862c,
  checked 2026-11-18.
- Biology of the name: the Wikipedia articles "Mycelial cord" and
  "Armillaria", read 2026-11-18, as the README states.
