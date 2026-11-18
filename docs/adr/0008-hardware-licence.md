<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-0008: Hardware licence

- **Status**: Accepted
- **Date**: 2026-11-18
- **Authors**: rhizomorph maintainers

## Context

Start with [Decision](#decision) for the chosen licence and firmware boundary;
[Consequences](#consequences) and [References](#references) give the clause-level
obligations and sources.

All software and first-party firmware in `lusoris/rhizomorph` are licensed under
**`EUPL-1.2`** ([ADR-0005](0005-licence.md), [`LICENSE`](../../LICENSE)).
`EUPL-1.2` is written for software works; physical carrier boards (`H2`) and
mechanical enclosures (`H3`) in the hardware track
([`docs/plan/hardware.md`](../plan/hardware.md#stages)) require a hardware
licence that defines physical `Products`, off-the-shelf electronic parts and
pre-certified radio modules (`Available Components`), fabrication outputs, and
electrical or mechanical interfaces between a board and separately licensed
firmware or sub-assemblies.

The three OSI-approved CERN Open Hardware Licence Version 2.0 variants
(`CERN-OHL-S-2.0`, `CERN-OHL-W-2.0`, and `CERN-OHL-P-2.0`) were compared clause
by clause in
[`docs/plan/hardware.md`](../plan/hardware.md#hardware-licence-options). Earlier
revisions (`CERN-OHL-1.1`, `CERN-OHL-1.2`) and `TAPR-OHL-1.0` are not
OSI-approved and were excluded. This record states the licence decision made by
the owner on 2026-11-18 (paraphrased) and gives no legal conclusion beyond what
the licence text states.

## Decision

Decided by the owner on 2026-11-18 (paraphrased):

1. **`CERN-OHL-W-2.0` for boards and cases:** First-party `H2` carrier board
   designs and `H3` enclosure models are licensed under **`CERN-OHL-W-2.0`**
   (CERN Open Hardware Licence Version 2 – Weakly Reciprocal;
   [`docs/plan/hardware.md`](../plan/hardware.md#hardware-licence-options)).
2. **First-party firmware stays `EUPL-1.2` as `External Material`:** All
   first-party firmware remains licensed solely under **`EUPL-1.2`**
   ([ADR-0005](0005-licence.md)); there is no dual licence. Relative to the
   `CERN-OHL-W-2.0` hardware designs, firmware is treated as `External Material`
   under `CERN-OHL-W-2.0` section 1.8 (lines 71–79 of the SPDX text) and section
   4.2 (lines 184–187).
3. **Documented firmware interface in `Covered Source`:** Section 1.8 defines
   `External Material` as material that interfaces with `Covered Source`
   (section 1.4, lines 42–43) only through a documented interface described in
   the `Covered Source` (section 1.8(a), lines 73–75), and that is not a
   derivative of `Covered Source` beyond what that interfacing needs (section
   1.8(b), lines 77–79). Every `H2` carrier board design therefore documents its
   firmware interface (pin map, bus protocol, and connector assignments) in the
   `Covered Source`
   ([`docs/plan/hardware.md`](../plan/hardware.md#design-flow-steps)).
4. **Licence files and `REUSE` headers:** This ADR lives in
   `lusoris/rhizomorph` under `EUPL-1.2` ([`REUSE.toml`](../../REUSE.toml)). The
   `CERN-OHL-W-2.0` full text (`LICENSES/CERN-OHL-W-2.0.txt`) and `REUSE`
   licence headers for `CERN-OHL-W-2.0` live in the hardware repository
   `lusoris/sporocarp` ([ADR-0009](0009-hardware-repository.md)).

## Consequences

- **Positive**:
  - **Modified board or case designs stay open (section 3.3, lines 149–169):**
    A recipient who modifies and conveys `Covered Source` must retain notices
    (sections 3.2 and 3.3(a), lines 138–152), add a modification notice with
    date and description (section 3.3(b), lines 154–156), add a `Source
    Location` notice (section 1.10, lines 95–98; section 3.3(c), lines 158–160)
    if the recipient does not receive a copy directly, and license the modified
    `Covered Source` as a whole under `CERN-OHL-W-2.0`, excluding `Available
    Components` and interfaced `External Material` (section 3.3(d), lines
    162–169).
  - **Every physical `Product` points at its source (section 4.1, lines
    174–182):** Anyone who makes and conveys a physical `Product` (section 1.5, lines 45–47) must
    either provide each recipient with a copy of the `Complete Source` (section
    1.9, lines 81–93) or notify each recipient of a three-year `Source Location`
    (section 1.10, lines 95–98; section 4.1, lines 174–177), displaying the
    `Source Location` on the product, packaging, or documentation when a notice
    requires it (section 4.1, lines 179–182).
  - **What stays excluded from board copyleft (sections 1.7–1.9, 4.2, 4.3):**
    `Complete Source` need not include the internal design of `Available
    Components` such as off-the-shelf ICs and pre-certified radio modules so
    long as sourcing and interface information is included (section 1.7, lines
    53–69; section 1.9, lines 89–93), nor the source of `External Material` such
    as `EUPL-1.2` firmware or daughterboards connected over documented
    interfaces (section 1.8, lines 71–79; section 4.2, lines 184–187). Under
    section 4.3 (lines 189–191), `Products` may be licensed on terms of the
    distributor's choice provided those terms do not restrict recipients' rights
    under `CERN-OHL-W-2.0` to the `Covered Source`.
  - **Partner sale stays an idea only:** Selling hardware through partners
    remains a noted idea only, not a plan or a decision
    ([`docs/plan/hardware.md`](../plan/hardware.md#purpose-and-scope)).
- **Negative**:
  - **Interface boundary risk:** As recorded in the primary-risk row for
    `CERN-OHL-W-2.0` in
    [`docs/plan/hardware.md`](../plan/hardware.md#hardware-licence-options),
    disputes can arise over whether an addition interfaces via a documented
    interface as `External Material` (section 1.8, lines 71–79) or modifies the
    `Covered Source` directly (section 3.2, lines 138–143; section 3.3(d), lines
    162–169).
  - **Documentation upkeep:** Each `H2` board must keep its documented pin map,
    bus protocol, and connector specification complete in the `Covered Source`
    to satisfy section 1.8(a) (lines 73–75).

## References

- Owner decision of 2026-11-18, paraphrased (`rhizomorph-hardware-licence`).
- [`docs/plan/hardware.md`](../plan/hardware.md#hardware-licence-options):
  comparison of `CERN-OHL-S-2.0`, `CERN-OHL-W-2.0`, and `CERN-OHL-P-2.0`.
- [ADR-0005](0005-licence.md): `EUPL-1.2` licence for software and firmware.
- [ADR-0009](0009-hardware-repository.md): hardware repository placement in
  `lusoris/sporocarp`.
- `CERN-OHL-W-2.0` SPDX text (`sha256` prefix `c1432111d0ae`):
  <https://raw.githubusercontent.com/spdx/license-list-data/main/text/CERN-OHL-W-2.0.txt>,
  read 2026-11-18 (s. 1.4 lines 42–43, s. 1.5 lines 45–47, s. 1.7 lines 53–69,
  s. 1.8 lines 71–79, s. 1.9 lines 81–93, s. 1.10 lines 95–98, s. 3.2 lines
  138–147, s. 3.3 lines 149–169, s. 4.1 lines 174–182, s. 4.2 lines 184–187,
  s. 4.3 lines 189–191).
