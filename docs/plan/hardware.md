<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# Rhizomorph hardware plan

## Purpose and scope

Start with [Purpose and scope](#purpose-and-scope) and [Stages](#stages) for
the newcomer overview; the remaining sections are reference for the
[AI-assisted design flow](#ai-assisted-design-flow),
[Hardware licence options](#hardware-licence-options), and
[Market rules for anything sold or placed on the EU market](#market-rules-for-anything-sold-or-placed-on-the-eu-market).
This track covers how **rhizomorph** (Greek *rhiza*, root, and *morphe*, form,
pronounced RY-zo-morf; see [`README.md`](../../README.md#name)) reaches physical
building devices across every building type, including precise positioning
([`coverage-matrix.md`](coverage-matrix.md)): adopting off-the-shelf local-control
hardware first, running open firmware on off-the-shelf hardware and gateways
second, and designing open carrier boards around pre-certified radio modules and
open cases later and slowly. Life-safety devices (such as smoke, fire, and
carbon monoxide detectors) and medical devices stay out of first-party design
and are integrated only as certified off-the-shelf products via read-only or
auxiliary status interfaces: in the European Union, standalone smoke alarms
(`EN 14604`) and fire detection and fire alarm systems (`EN 54` series) require
harmonised third-party conformity assessment under the Construction Products
Regulation (`Regulation (EU) No 305/2011` and its successor `Regulation (EU)
2024/3110`), domestic carbon monoxide alarms are governed by `EN 50291-1`, and
medical devices require clinical conformity assessment under the Medical Devices
Regulation (`Regulation (EU) 2017/745`; see [Sources](#sources)). Selling
hardware through partners is a noted idea only, not a plan or a decision, and
project names for hardware artefacts, repository placement, and the hardware
licence remain open decisions of the project owner (direction of 2026-11-18,
paraphrased).

## Stages

The hardware track progresses through four stages (`H0` to `H3`). Software phase
identifiers (`P1` to `P10`) refer to [`phases.md`](phases.md); protocol crate
checks come from [`../concept.md`](../concept.md#research).

| Stage | Scope | Depends on in [`phases.md`](phases.md) | Entry condition | Exit check |
| :--- | :--- | :--- | :--- | :--- |
| `H0` | Off-the-shelf devices speaking a protocol with a planned worker, local control without cloud | `P2` (Modbus), `P6` (BACnet), `P7` (KNX), `P8` (Matter), `P9` (MQTT) | Target protocol worker passes its phase exit check in [`phases.md`](phases.md) | Declarative TOML device profile or endpoint mapping tested against a real device or protocol simulator with explicit I/O deadlines (HISS-02) and zero cloud account or internet path |
| `H1` | Open firmware on off-the-shelf hardware and protocol gateways | `P2` (Modbus) or `P9` (MQTT); `P8` (Matter) where Matter firmware is used | `H0` profile format exists and a gap in [`coverage-matrix.md`](coverage-matrix.md) is solvable by flashing open firmware onto available hardware or running an open gateway | Reproducible firmware or gateway configuration checked into version control, pinned by version and licence, verified on target hardware with lease revocation on disconnect ([ADR-0002](../adr/0002-priority-array-and-leases.md)) |
| `H2` | Own carrier boards around certified radio modules for remaining coverage gaps | `P2` or `P9`, plus `H1` gap confirmation in [`coverage-matrix.md`](coverage-matrix.md) | A device class or positioning role in [`coverage-matrix.md`](coverage-matrix.md) lacks an `H0` or `H1` local-control option, and the hardware licence decision ([Hardware licence options](#hardware-licence-options)) is recorded in an ADR | Electrical Rules Check (ERC) and Design Rules Check (DRC) pass with zero errors in CI via KiBot, human sign-off on fabrication outputs and bill of materials (BOM), and bring-up test passes on assembled prototype |
| `H3` | Own cases and mechanical mounts (parametric CAD now; `plurano/tornus` later) | `H2` board outline and mounting holes (or `H0`/`H1` gateway board dimensions) | Board mechanical envelope, connector keep-outs, thermal dissipation, and ingress or DIN-rail mounting requirements are fixed | Exported STEP and STL/3MF models pass OpenCASCADE (`OCCT`) Boolean solid interference (`volume == 0`), minimum-clearance, and manifold checks in CI (`build123d`, `CadQuery`, or `FreeCAD`) against the `H2` board STEP or purchased `H0`/`H1` board model/drawing, and a test print or machined sample passes physical fit check |

### H0: Off-the-shelf devices with local control

`H0` adopts unmodified off-the-shelf devices that communicate locally without a
vendor cloud account over the five protocols with planned workers in
[`../concept.md`](../concept.md#research) and [`phases.md`](phases.md):

- **Electricity, heat, and solar metering over Modbus RTU/TCP (`P2`,
  `tokio-modbus` 0.17.0):** DIN-rail energy meters with documented RS-485
  register maps (for example, Eastron `SDM630-Modbus`) and solar inverters or
  storage controllers implementing the open **SunSpec Modbus** information models
  (`sunspec/models`, Apache-2.0).
- **Commercial HVAC, chillers, and room controllers over BACnet/IP or MS/TP
  (`P6`, `rusty-bacnet` v0.15.0):** BACnet application-specific and advanced
  application controllers exposing standard BACnet objects and 16-level priority
  arrays per ANSI/ASHRAE Standard 135 (for example, routers and controllers
  tested against the open `bacnet-stack/bacnet-stack` reference implementation).
- **Wired building actuators, dimmers, blind controllers, and sensors over KNX
  (`P7`, `aimdb-knx-connector` 0.6.0):** KNX TP1 and KNXnet/IP devices under
  ISO/IEC 14543-3 / EN 50090, bridged via a local KNXnet/IP interface or `knxd`
  (`knxd/knxd`) without cloud dependencies (for example, documented open KNX
  hardware/application designs from `selfbus/hardware-merged` and
  `OpenKNX/OpenKNX`).
- **Thread and Wi-Fi plugs, lighting, thermostats, locks, and shades over Matter
  (`P8`, `rs-matter` 0.4.1):** IPv6 endpoints commissioned locally onto the
  owner's fabric under Matter 1.x without cloud accounts (for example, devices
  built on `espressif/esp-matter`, Apache-2.0).
- **DIN-rail and in-wall relays, dimmers, and environmental sensors over MQTT
  (`P9`, `rumqttc` 0.25.1):** Wi-Fi or Ethernet actuators and power meters that
  expose a documented local MQTT broker client and local HTTP/RPC configuration
  with cloud disabled (for example, Shelly Gen2/Gen3 devices documented at
  `shelly-api-docs.shelly.cloud`).

### H1: Open firmware on off-the-shelf hardware and gateways

Where vendor firmware requires a cloud account or speaks a protocol without a
native rhizomorph worker, `H1` replaces the firmware or deploys an open local
gateway that bridges the bus to a planned worker (`P2` Modbus, `P8` Matter, or
`P9` MQTT):

| Project | Licence | Target hardware | Protocols bridged into rhizomorph |
| :--- | :--- | :--- | :--- |
| `esphome/esphome` | MIT (tools) / GPL-3.0 (firmware) | ESP32, ESP8266, RP2040, BK72xx off-the-shelf relays, sensors, UART/RS-485 boards | Exposes **MQTT** (`P9`) and bridges **Modbus RTU** (`P2`), BLE sensors, and local I2C/SPI/UART peripherals |
| `arendst/Tasmota` | GPL-3.0 | ESP8266 and ESP32 smart plugs, switches, dimmers, energy monitors, serial bridges | Exposes **MQTT** (`P9`) and **Matter** (`P8`) over local IP |
| `openshwprojects/OpenBK7231T_App` (OpenBeken) | MIT | Off-the-shelf smart plugs and relays using Beken BK7231T/N, Bouffalo Lab BL602, or WinnerMicro W600/W800 chips | Exposes **MQTT** (`P9`) locally without vendor cloud |
| `Koenkk/zigbee2mqtt` | GPL-3.0 | IEEE 802.15.4 USB/Ethernet/PoE coordinators (TI CC2652P, Silicon Labs EFR32MG21) | Bridges **Zigbee 3.0** (`IEEE 802.15.4`) devices to **MQTT** (`P9`) |
| `emsesp/EMS-ESP32` | GPL-3.0 | ESP32 gateway interfaces connected to EMS / Buderus / Nefit / Bosch heating buses | Bridges boiler and heat-pump bus parameters to **MQTT** (`P9`) and **Modbus** (`P2`) |
| `wmbusmeters/wmbusmeters` | GPL-3.0 | RTL-SDR, IM871A, AMB8465, and CUL wireless/wired M-Bus receivers | Bridges **EN 13757** wired and wireless M-Bus water, heat, and gas meters to **MQTT** (`P9`) |
| `3cky/mbusd` | BSD-3-Clause | Linux host with RS-485 USB/UART transceiver | Bridges **Modbus RTU** serial lines to **Modbus TCP** (`P2`) |
| `Stefal/rtkbase` | AGPL-3.0 (a modified network service must offer Corresponding Source under Section 13) | Single-board computer with u-blox ZED-F9P or Unicore multi-band GNSS receiver | Serves **RTCM 3.x** (`RTCM 10403.3`) differential GNSS corrections over local **NTRIP** (`RTCM 10410.1`), TCP, serial/radio, or file logs (requires an additional bridge for **MQTT** `P9`) |

### H2: Own carrier boards around certified radio modules

`H2` designs custom carrier Printed Circuit Boards (PCBs) only when `H0` and
`H1` leave a functional or mechanical gap documented in
[`coverage-matrix.md`](coverage-matrix.md) (such as combined PoE + RS-485 + UWB
/ BLE Angle-of-Arrival ceiling anchors, multi-bus agricultural or marine
isolators, or compact DIN-rail sensor hubs).

- **Why pre-certified radio modules are required:** Designing a discrete radio
  front-end (custom RF trace layout, matching network, oscillator, and unshielded
  transceiver IC, such as a chip-down Qorvo `DW3000` with an external 38.4 MHz
  `TCXO` for `TDoA` anchors) requires full intentional-radiator radio spectrum
  testing under Article 3(2) of the EU Radio Equipment Directive (`Directive
  2014/53/EU`) and corresponding ETSI harmonised standards (such as `ETSI EN 300
  328` for 2.4 GHz wideband transmission or `ETSI EN 302 065` for
  Ultra-Wideband). By placing a shielded, pre-certified radio module (for
  example, an Espressif ESP32-S3/C6/H2 module, a Nordic nRF52833/nRF5340 module,
  a Qorvo DWM3000 UWB module with its internal 38.4 MHz crystal for `DS-TWR`, or
  a u-blox ZED-F9P GNSS module) on a carrier board and following the module
  vendor's reference antenna and keep-out layout guidelines strictly, the
  carrier board leverages the module's existing radio test reports and narrows
  board-level testing primarily to Electromagnetic Compatibility (EMC) and
  electrical safety integration checks ([Market rules](#market-rules-for-anything-sold-or-placed-on-the-eu-market)).

### H3: Own cases

`H3` provides printable or machinable mechanical enclosures (DIN-rail housings,
IP-rated outdoor/barn enclosures, ceiling anchor mounts) for `H1` gateways and
`H2` carrier boards:

- **Current toolchain:** Code-defined parametric B-Rep CAD in Python using
  `build123d` (`v0.13.0`, checked 2026-11-18) or `CadQuery` (`v2.8.0`, checked
  2026-11-18), and interactive inspection and STEP/B-Rep modelling in `FreeCAD`
  (`1.1.4`, checked 2026-11-18), all backed by the OpenCASCADE (`OCCT`) geometry
  kernel with native `STEP` import/export and Boolean solid interference checks.
  Constructive solid geometry in `OpenSCAD` (last tagged release
  `openscad-2021.01` of 2021-02-07; active default branch at commit of
  2026-11-18T03:51Z) supports triangle-mesh (`STL`, `3MF`, `OFF`, `AMF`) and 2D
  (`DXF`, `SVG`) import/export only (`src/import.cc` lines 101–107 and
  `src/export.cc` lines 52–85 at tag `openscad-2021.01`) and cannot import a
  board `STEP` model or export `STEP`; any `H3` `STEP` deliverable and 3D board
  fit check must therefore run in `build123d`, `CadQuery`, or `FreeCAD`.
- **Later Rust CAD kernel option (`plurano/tornus`):** **Tornus** (Latin
  *tornus*, a lathe or turner's wheel, from Greek *tornos*, pronounced TOR-noos;
  public repository `https://github.com/plurano/tornus`, licensed under
  `EUPL-1.2`, pushed 2026-11-15) is a geometric modelling kernel for CAD in Rust
  checked against a public conformance corpus. Its `README.md` status line on
  2026-11-18 reads: `"No code yet."` Tornus is therefore recorded as a later
  option for `H3` once it ships usable code, not a tool available today.

## AI-assisted design flow

Board and enclosure design uses open-source tools driven by text or Python APIs
so that an AI assistant can draft schematics, layouts, fabrication pipelines, and
parametric enclosures while deterministic checks and human engineers verify every
step.

**Hard operational rules:**

1. **Nothing is ordered without clean CI gates and human sign-off:**
   - **Orders with a project PCB (`H2`, or `H2` combined with `H3`):** No PCB
     may be sent to fabrication until Electrical Rules Check (`ERC=0`) and
     Design Rules Check (`DRC=0`) pass with zero errors in continuous
     integration (`KiBot` `v1.9.1`) and a human reviewer signs off on the
     rendered Gerber layers, drill files, interactive placement map
     (`InteractiveHtmlBom` `v2.12.0`), and bill of materials (BOM).
   - **Case-only orders (`H3`, including enclosures for purchased `H0`/`H1`
     boards that have no project KiCad schematic or PCB):** ERC and DRC do not
     apply to purchased boards; instead, no enclosure or mechanical mount may be
     sent to fabrication until automated CI checks in an OpenCASCADE (`OCCT`)
     tool (`build123d` `v0.13.0`, `CadQuery` `v2.8.0`, or `FreeCAD` `1.1.4`)
     pass B-Rep/mesh manifold validation, zero Boolean solid interference
     (`case.intersect(board).volume == 0`), and minimum clearance checks against
     either the `H2` board STEP model or the purchased `H0`/`H1` board's
     published 3D STEP model or dimension drawing (board outline, mounting-hole
     centres, component height keep-outs, and connector cutouts), and a human
     reviewer signs off on the dimensional drawings and physical fit check.
2. **Tool servers are pinned, licensed, and read-only by default.** Every Model
   Context Protocol (MCP) server or automation helper used with KiCad must be
   pinned to an exact commit hash, carry an OSI- or FSF-approved open-source
   licence, and run in read-only inspection mode by default. Write access to
   schematics or PCB layouts is enabled only per task in an isolated git
   worktree and reviewed via diff and `KiBot` ERC/DRC before merge. A tool
   server without a declared licence is not adoptable.

### Design flow steps

All tool versions below were checked via the GitHub releases API and PyPI on
2026-11-18 between 09:46 and 09:47 CET.

| Step | Tool and version (checked 2026-11-18) | What the AI drafts | What a human or a check must sign off |
| :--- | :--- | :--- | :--- |
| 1. Requirements | Markdown specification in git | Point list, bus isolation budget, power budget, connector pinout, mechanical envelope, target stage (`H2`/`H3`) | Human review of electrical ratings, creepage/clearance targets, and thermal budget |
| 2. Part choice | Component datasheets, distributor tables, KiCad symbol/footprint libraries (`KiCad 10.0.8`) | Candidate BOM with pre-certified radio modules, LDO/DC-DC converters, ESD protection, and stock alternatives | Human verification of every pin number, footprint pitch, voltage/current derating, and module certification validity |
| 3. Schematic | `KiCad 10.0.8` (2026-11-06) via IPC API Python binding `kicad-python` `0.8.0`, S-expression library `kicad-skip` `0.2.5`, or pinned licensed MCP server (`mixelpixx/KiCAD-MCP-Server` MIT, `oaslananka/kicad-mcp-pro` AGPL-3.0, `claynicholson/copper-kicad-mcp` MIT); or code-defined circuits via `SKiDL` `3.0.0` (2026-10-16), `atopile` `v0.12.5` (2026-01-20), or `tscircuit` (tag `v0.0.3231`, no GitHub release object) | Hierarchical schematic sheets, net labels, decoupling networks, bus termination, or code-defined netlists/circuits | Human schematic review against component reference designs (antenna keep-out, strap pins, reset timing, isolation barrier) |
| 4. ERC | `KiCad 10.0.8` `kicad-cli sch erc` and `KiBot` `v1.9.1` (2026-07-28) | Pin power-flag annotations and net-class fixes to resolve ERC violations | Automated CI gate: `KiBot` ERC run must exit `0` with zero unwaived errors or warnings |
| 5. Layout | `KiCad 10.0.8` PCB editor, IPC API `kicad-python` `0.8.0`, or pinned licensed MCP server | Initial component placement, courtyard grouping, net classes, differential-pair rules, and copper zones | Human layout placement review for RF module edge placement, antenna keep-out zones, high-voltage isolation slots, and thermal vias |
| 6. Autorouting | `Freerouting` `v2.5.0` (2026-10-05) over Specctra DSN/SES with `KiCad 10.0.8` | Non-critical digital signal routing passes under net-class width and clearance constraints | Human routing review; RF traces, crystal oscillators, switching-regulator loops, and differential buses must be hand-routed or verified by a human |
| 7. DRC | `KiCad 10.0.8` `kicad-cli pcb drc` and `KiBot` `v1.9.1` | Trace/via adjustments, silkscreen cleanup, and zone refills to clear DRC findings | Automated CI gate: `KiBot` DRC against the fabricator's design rules must exit `0` with zero errors |
| 8. Fabrication outputs and BOM | `KiBot` `v1.9.1` (2026-07-28) and `InteractiveHtmlBom` `v2.12.0` (2026-09-10) in CI | Reproducible `.kibot.yaml` pipeline generating Gerbers, Excellon drill files, pick-and-place CSV, STEP 3D board model, schematic PDF, and interactive HTML BOM | Automated CI build reproducibility check plus human inspection of every Gerber layer and `InteractiveHtmlBom` orientation |
| 9. Case model | STEP/B-Rep (`OCCT`): `build123d` `v0.13.0` (2026-09-21), `CadQuery` `v2.8.0` (2026-06-20), `FreeCAD` `1.1.4` (2026-09-28); mesh-only (`STL`/`3MF`, no `STEP` import/export): `OpenSCAD` (`openscad-2021.01` / default branch 2026-11-18T03:51Z); later `plurano/tornus` (`EUPL-1.2`, no code yet) | Parametric Python script (`build123d` / `CadQuery` / `FreeCAD`) importing the `H2` board `STEP` model from step 8 or a purchased `H0`/`H1` board's published `STEP` model / dimension envelope to generate `STEP` and `STL`/`3MF` enclosures (`OpenSCAD` generates `STL`/`3MF` meshes only) | Automated CI `STEP` and `STL`/`3MF` generation, B-Rep/mesh manifold check, and OpenCASCADE (`OCCT`) Boolean solid interference (`case.intersect(board).volume == 0`) and minimum-clearance check in `build123d`, `CadQuery`, or `FreeCAD` against the board 3D model or envelope solid, plus human mechanical review |
| 10. Review and order | Git pull request, `KiBot` and `OCCT` CAD CI artefacts, human checklist | Release archive summary and assembly / mechanical fit test procedure | Mandatory human sign-off checklist before any order is placed: for orders with a project PCB (`H2`), `ERC=0`, `DRC=0`, Gerber visual check, `InteractiveHtmlBom` placement, BOM part numbers, and footprint-to-datasheet check; for case-only orders (`H3`, including purchased `H0`/`H1` boards), `OCCT` Boolean interference = `0` and clearance check against the board's published model or dimension drawing, manifold check, and human sign-off on mechanical drawings and sample fit |

### KiCad MCP servers evaluated (2026-11-18)

A GitHub search for `"kicad mcp"` sorted by stars on 2026-11-18 returned five
repositories. Under the project rule that a tool server must be pinned,
licensed, and read-only by default:

- **`mixelpixx/KiCAD-MCP-Server`** (MIT, 3408 stars, pushed 2026-11-16):
  adoptable when pinned by commit SHA and restricted to read-only tools by
  default.
- **`oaslananka/kicad-mcp-pro`** (AGPL-3.0, 224 stars, pushed 2026-11-18;
  describes a human-gated release workflow): adoptable when pinned by commit SHA
  and run read-only by default.
- **`Seeed-Studio/kicad-mcp-server`** (no licence field detected, pushed
  2026-10-22): **not adoptable** because a tool server without a licence cannot
  be used.
- **`claynicholson/copper-kicad-mcp`** (MIT, pushed 2026-11-17): adoptable when
  pinned by commit SHA and restricted to read-only tools by default.
- **`lamaalrajih/kicad-mcp`** (MIT, last push 2025-10-17): stale (no push for
  13 months); prefer active MIT or AGPL-3.0 options above.

## Hardware licence options

Per the SPDX licence list data (`main` branch, version `ddf7382` of 2026-11-18)
and the Open Source Initiative (OSI) list:

- **`CERN-OHL-S-2.0`** (Strongly Reciprocal), **`CERN-OHL-W-2.0`** (Weakly
  Reciprocal), and **`CERN-OHL-P-2.0`** (Permissive) are OSI-approved and not
  deprecated.
- Earlier revisions (`CERN-OHL-1.1`, `CERN-OHL-1.2`) and `TAPR-OHL-1.0` are
  **not OSI-approved** and are excluded from consideration.
- All software and firmware in this repository remain under **`EUPL-1.2`**
  (OSI- and FSF-approved; see [ADR-0005](../adr/0005-licence.md) and
  [`LICENSE`](../../LICENSE)).

The table and per-licence analysis below cite the official CERN Open Hardware
Licence Version 2.0 texts (`cern-ohl.web.cern.ch` and `spdx/license-list-data`,
read 2026-11-18) by section number.

| Criterion | `CERN-OHL-S-2.0` (Strongly Reciprocal) | `CERN-OHL-W-2.0` (Weakly Reciprocal) | `CERN-OHL-P-2.0` (Permissive) |
| :--- | :--- | :--- | :--- |
| **Distributing modified design (`Covered Source`)** | Must retain Notices (ss. 3.2, 3.3(a)), add modification date/description (s. 3.3(b)), add Source Location if recipient gets no copy (s. 3.3(c)), and license the modified Covered Source **as a whole** under `CERN-OHL-S-2.0`, excluding only `Available Components` (s. 3.3(d)). Including Covered Source in a larger work makes the larger work modified Covered Source (s. 3.2). | Same notice and Source Location rules (ss. 3.2, 3.3(a)–(c)); modified Covered Source is licensed under `CERN-OHL-W-2.0`, excluding both `Available Components` and interfaced `External Material` (ss. 1.8, 3.3(d)). | Must retain Notices (ss. 3.2, 3.3(a)) and add modification date/description (s. 3.3(b)). Section 3.4 permits Conveying Covered Source or modified Covered Source under **different licence terms** (including proprietary terms) if s. 3.3 is met and a copy of `CERN-OHL-P-2.0` is provided. |
| **Distributing physical `Products`** | Section 4 sets an **either/or** obligation: the distributor must **either** provide each recipient directly with a copy of the `Complete Source` (s. 1.8) alongside the Product (in which case no 3-year `Source Location` is required under ss. 3.2 and 3.3(c)) **or** ensure that each recipient is notified of the `Source Location` (s. 1.9, where the Complete Source remains easily accessible for at least 3 years). In both cases s. 3.3 applies to that Complete Source, and if a Notice specifies it, the Product/packaging/documentation must visibly display the Source Location (s. 4). | Section 4.1 sets the same **either/or** obligation: the distributor must **either** provide each recipient with a copy of the `Complete Source` (s. 1.9) **or** ensure that each recipient is notified of its `Source Location` (s. 1.10, accessible for at least 3 years; ss. 3.2, 3.3(c), 4.1), displaying the Source Location on the Product/packaging/documentation if specified in a Notice (s. 4.1). Section 4.2 excludes Source for `External Material` (s. 1.8); section 4.3 allows licensing Products under terms of choice that do not restrict rights to the Covered Source. | Section 4 requires only ensuring that the recipient of the Product has access to any `Notices` (s. 1.6) applicable to the Product; there is **no obligation** to publish or provide `Complete Source` of a modified Product. |
| **Off-the-shelf parts and closed radio modules** | Handled via `Available Component` (s. 1.7): Complete Source need not include the internal design of any part available at first Conveyance **as a physical part** with sufficient rights and interface/configuration information to source and use it to Make the Product (ss. 1.7(b)(i), 1.8). | Handled via both `Available Component` (s. 1.7, which omits the `"as a physical part"` restriction of S s. 1.7(b)(i)) and `External Material` (s. 1.8: anything combined only over a documented interface described in the Covered Source). Closed radio modules and proprietary sub-assemblies are excluded from Complete Source (ss. 1.9, 3.3(d), 4.2). | No copyleft boundary: off-the-shelf ICs, closed radio modules, and proprietary sub-circuits can be combined without source disclosure obligations (ss. 3.4, 4). |
| **Fit with `EUPL-1.2` firmware** | **Requires explicit boundary or dual-licensing:** `CERN-OHL-S-2.0` s. 1.3 defines `Source` to include digital code applied to Make or prepare a Product, and s. 1.7(b)(i) limits non-compatibly-licensed `Available Components` to **physical parts**, apart from parts of a tool's normal distribution (s. 1.7(b)(ii)). `EUPL-1.2` Article 5 Appendix does not list `CERN-OHL-S-2.0` as a Compatible Licence. If `EUPL-1.2` firmware is treated as part of `Complete Source` rather than a separate work loaded onto a physical `Available Component`, s. 3.3(d) conflicts with `EUPL-1.2` Article 5 copyleft unless the project dual-licenses first-party firmware (`EUPL-1.2 OR CERN-OHL-S-2.0`). | **Clean separation by text:** First, s. 1.7(b)(i) defines `Available Component` to include any library or **code** available to prospective licensees with sufficient rights and interface data (no `"physical part"` restriction). Second, s. 1.8 defines `External Material` as anything (including Source) interfacing via a documented interface described in the Covered Source. Under ss. 3.3(d) and 4.2, `EUPL-1.2` firmware remains under `EUPL-1.2` without conflict. | **No conflict:** `CERN-OHL-P-2.0` imposes no reciprocal licence requirement on combined code or firmware (ss. 3.3, 3.4, 4); firmware stays under `EUPL-1.2` ([ADR-0005](../adr/0005-licence.md)). |
| **Fit with a possible partner sale (noted idea only)** | Every manufacturing or distribution partner who modifies the board or integrates it into a larger board must license the entire modified board's `Complete Source` under `CERN-OHL-S-2.0` (ss. 3.2, 3.3(d)) and, on Conveying physical Products, **either** provide a copy of that `Complete Source` to each recipient with the Product **or** notify each recipient of a 3-year `Source Location` (ss. 1.8, 1.9, 3.2, 3.3(c), 4). Contract R&D / testing partners are covered by the private R&D exemption in s. 5. | A partner who modifies the carrier board itself must license the modified Covered Source under `CERN-OHL-W-2.0` (s. 3.3(d)) and **either** provide a copy of the `Complete Source` to each recipient **or** notify each recipient of a 3-year `Source Location` (ss. 1.9, 1.10, 3.2, 3.3(c), 4.1), while attaching proprietary daughterboards, enclosures, or modules over documented interfaces as `External Material` without releasing their source (ss. 1.8, 4.2). Private contract R&D / testing is covered by s. 5. | A partner can manufacture, modify, and sell closed-source derivatives while providing only attribution and licence `Notices` (ss. 3.3, 3.4, 4). |
| **Primary risk** | Licence friction with `EUPL-1.2` firmware or non-physical vendor FPGA/MCU support libraries due to the `"as a physical part"` wording in s. 1.7(b)(i) and the absence of an `External Material` clause; may deter commercial partners who mix proprietary sub-assemblies on one PCB. | Boundary disputes over what qualifies as a `"documented interface"` for `External Material` (s. 1.8) versus a direct modification of the `Covered Source` (s. 3.2). | Third parties can take the project's board and case designs, make improvements, and sell closed hardware products without contributing any design changes back (ss. 3.4, 4). |

### Summary of section structure across the three variants

- **Definitions and compatibility:** `CERN-OHL-S-2.0` (ss. 1.1–1.13),
  `CERN-OHL-W-2.0` (ss. 1.1–1.14, adding `'External Material'` at s. 1.8), and
  `CERN-OHL-P-2.0` (ss. 1.1–1.9). Under `CERN-OHL-W-2.0` s. 8.3 paragraph 2,
  Covered Source licensed under `CERN-OHL-W` may be treated as licensed under
  `CERN-OHL-S` if and only if all referenced `Available Components` comply with
  the stricter `CERN-OHL-S` s. 1.7 definition.
- **Patents and termination:** All three variants grant a royalty-free patent
  licence with defensive patent-litigation termination (`CERN-OHL-S-2.0` s. 7,
  `CERN-OHL-W-2.0` s. 7, `CERN-OHL-P-2.0` s. 6). Both reciprocal variants
  include automatic termination on breach with a 30-day cure reinstatement
  window (`CERN-OHL-S-2.0` ss. 8.4–8.5, `CERN-OHL-W-2.0` ss. 8.4–8.5).
- **No endorsement:** All three forbid using the Licensor's or CERN's name or
  logo to suggest endorsement (`CERN-OHL-S-2.0` s. 8.2, `CERN-OHL-W-2.0` s. 8.2,
  `CERN-OHL-P-2.0` s. 7.2).

Decision open.

## Market rules for anything sold or placed on the EU market

> **Constraint for a later sale, not a plan:** Publishing open hardware source
> files in a public repository without monetisation or placing physical products
> on the market does not by itself make the project a manufacturer. However, if
> any entity (the owner or a partner, noted only as an idea) ever places an `H2`
> board or `H3` product on the European Union market—whether for payment or free
> of charge in the course of a commercial activity—the following EU acts apply as
> mandatory legal constraints.

| Instrument | Official reference and EUR-Lex ELI | Scope | What it means for `H2` (carrier boards) and `H3` (cases) |
| :--- | :--- | :--- | :--- |
| **Radio Equipment Directive (RED)** | `Directive 2014/53/EU` of 16 April 2014 (`OJ L 153, 22.5.2014, p. 62–106`; ELI: `https://eur-lex.europa.eu/eli/dir/2014/53/oj`) | Any electrical or electronic product that intentionally emits or receives radio waves for radio communication or radiodetermination (Article 2(1)(1)), covering Wi-Fi, Thread, Zigbee, BLE, LoRa, UWB, and GNSS receivers | Using a pre-certified radio module in `H2` avoids re-running standalone silicon RF conduction suites, but RED compliance is assessed on the **final radio product** as placed on the market: the manufacturer must still verify radiated spurious emissions, follow the module's antenna gain/trace integration conditions, compile the technical documentation (Article 21), issue an EU Declaration of Conformity (Article 18), and affix the CE marking (`H3` enclosure label, Article 20). |
| **RED Cybersecurity Delegated Regulation** | `Commission Delegated Regulation (EU) 2022/30` of 29 October 2021 (`OJ L 7, 12.1.2022, p. 6–10`; ELI: `https://eur-lex.europa.eu/eli/reg_del/2022/30/oj`), amended and corrected by `Commission Delegated Regulation (EU) 2023/2444` (`OJ L, 2023/2444, 27.10.2023`; ELI: `https://eur-lex.europa.eu/eli/reg_del/2023/2444/oj`; its Article 1 replaces Article 3 of `2022/30` so that `2022/30` applies from 1 August 2025, and its Article 2 corrects the wording of Article 1(2)) | Per Article 1: **RED Article 3(3)(d)** (network protection) applies to any radio equipment that can communicate itself over the internet, directly or via any other equipment (`'internet-connected radio equipment'`, Article 1(1)); **Article 3(3)(e)** (protection of personal data under `Regulation (EU) 2016/679` Article 4(1)–(2), or traffic data or location data under `Directive 2002/58/EC` Article 2(b)–(c)) applies **only** where the radio equipment is capable of processing such data **and** belongs to one of four categories in Article 1(2)(a)–(d): `(a)` internet-connected radio equipment, `(b)` radio equipment designed or intended exclusively for childcare, `(c)` toys covered by `Directive 2009/48/EC`, or `(d)` radio equipment designed or intended to be worn on, strapped to, or hung from any part of the human body or any clothing; **Article 3(3)(f)** (fraud protection) applies to internet-connected radio equipment enabling transfer of money, monetary value, or virtual currency (Article 1(3)); harmonised standards `EN 18031-1:2024`, `EN 18031-2:2024`, `EN 18031-3:2024` | A **fixed offline UWB, BLE AoA, or GNSS anchor** that operates solely on an isolated local fieldbus or air-gapped LAN (cannot communicate over the internet directly or via other equipment) and is not childcare equipment, a `2009/48/EC` toy, or body/clothing-worn is **not** covered by RED Article 3(3)(d), (e), or (f) merely because it processes location data (Article 1(1)–(2)). Conversely, any **wearable positioning tag or badge** (`Article 1(2)(d)`) processing personal or location data is covered by Article 3(3)(e) even offline, and any **networked `H2` gateway, controller, or anchor capable of communicating over the internet** directly or via another device (`'internet-connected radio equipment'`) must comply with Article 3(3)(d) (`EN 18031-1:2024`) and, when processing personal, traffic, or location data, Article 3(3)(e) (`EN 18031-2:2024`: no universal default passwords, authenticated firmware updates, access control, and protected transport). |
| **Low Voltage Directive (LVD)** | `Directive 2014/35/EU` of 26 February 2014 (`OJ L 96, 29.3.2014, p. 357–374`; ELI: `https://eur-lex.europa.eu/eli/dir/2014/35/oj`) | Electrical equipment operated at 50–1000 V AC or 75–1500 V DC (Article 1); for radio equipment under RED, RED Article 3(1)(a) applies the LVD health and safety objectives **with no lower voltage limit** | Every `H2` board—even a 5 V USB, 12–24 V DC, or 48 V PoE board if it contains a radio module under RED Article 3(1)(a)—must meet electrical, thermal, and fire safety standards (such as `EN IEC 62368-1` for ICT/control equipment or `EN 60730-1` for automatic electrical controls). `H3` cases covering mains or SELV/mains-adjacent terminals must meet flammability, creepage/clearance, and IP ingress protection ratings so live parts are inaccessible. |
| **Electromagnetic Compatibility (EMC) Directive** | `Directive 2014/30/EU` of 26 February 2014 (`OJ L 96, 29.3.2014, p. 79–106`; ELI: `https://eur-lex.europa.eu/eli/dir/2014/30/oj`) | Non-radio electrical equipment (for radio equipment, EMC is governed via RED Article 3(1)(b) and the `ETSI EN 301 489` series) | Wired-only `H2` boards (such as RS-485 Modbus, KNX TP1, M-Bus, or CAN gateways without radio) must pass conducted and radiated emissions and electrostatic discharge (ESD) / surge / fast-transient immunity testing (such as `EN IEC 61000-6-1/-6-2/-6-3` or `EN 50491-5` for HBES/BACS). This drives mandatory TVS diodes, common-mode chokes, and galvanic isolation in the `H2` schematic step. |
| **RoHS Directive** | `Directive 2011/65/EU` of 8 June 2011 (`OJ L 174, 1.7.2011, p. 88–110`; ELI: `https://eur-lex.europa.eu/eli/dir/2011/65/oj`), as amended by `Commission Delegated Directive (EU) 2015/863` (10 restricted substances: Pb, Hg, Cd, Cr(VI), PBB, PBDE, DEHP, BBP, DBP, DIBP) | All electrical and electronic equipment placed on the EU market | Every `H2` PCB finish (lead-free HASL or ENIG), solder paste, electronic component, and `H3` polymer filament, resin, or metal insert must have supplier RoHS declarations archived in the technical file (`EN IEC 63000:2018`). |
| **Cyber Resilience Act (CRA)** | `Regulation (EU) 2024/2847` of 23 October 2024 (`OJ L, 2024/2847, 20.11.2024`; ELI: `https://eur-lex.europa.eu/eli/reg/2024/2847/oj`; per Article 71(2), Chapter IV Articles 35–51 apply from 11 June 2026, Article 14 vulnerability and severe-incident reporting obligations apply from 11 September 2026, and full obligations apply from 11 December 2027) | Horizontal cybersecurity requirements for all `"products with digital elements"` (hardware and software connected directly or indirectly to a device or network, Article 2(1)) placed on the market in the course of a commercial activity (Recitals 18–21, Article 3) | Recital 18 treats the supply of free and open-source software that its manufacturer does not monetise as not a commercial activity; the recital names software only, so it gives open hardware designs no explicit carve-out. However, anyone commercially placing an `H2` device on the EU market becomes the CRA **manufacturer** (Article 13) and must provide a machine-readable Software Bill of Materials (SBOM, Annex I Part II point (1)), secure-by-default configuration (Annex I Part I point (2)(b)), vulnerability handling with security updates for a support period of at least five years, or the expected use time where that is shorter (Article 13(8)), and simultaneous notification via the single reporting platform (Article 16) to the coordinator CSIRT (Article 14(7)) and ENISA of both: (1) any **actively exploited vulnerability** (`Article 14(1)–(2)`: early warning within 24 hours of awareness under `Article 14(2)(a)`, vulnerability notification within 72 hours under `Article 14(2)(b)`, and final report within 14 days after a corrective or mitigating measure is available under `Article 14(2)(c)`) and (2) any **severe incident having an impact on the security of the product** (`Article 14(3)–(5)`: early warning within 24 hours of awareness under `Article 14(4)(a)`, incident notification within 72 hours under `Article 14(4)(b)`, and final report within 1 month of the incident notification under `Article 14(4)(c)`), plus informing impacted users (`Article 14(8)`). |

## Open questions

1. **Hardware licence selection:** Which of `CERN-OHL-S-2.0`, `CERN-OHL-W-2.0`,
   or `CERN-OHL-P-2.0` should govern `H2` carrier boards and `H3` enclosure
   models, and if `CERN-OHL-S-2.0` is chosen, should first-party microcontroller
   firmware be dual-licensed (`EUPL-1.2 OR CERN-OHL-S-2.0`) to avoid the
   section 1.7(b)(i) physical-part friction?
2. **Repository placement and naming:** Should `H1` profiles, `H2` KiCad
   projects, and `H3` CAD models live in subdirectories of `lusoris/rhizomorph`
   or in dedicated sibling repositories, and what naming scheme should hardware
   revisions use?
3. **KiCad circuit-as-code front-end:** Should `H2` schematics be authored
   directly in `KiCad 10.0.8` `.kicad_sch` files manipulated via `kicad-python`
   `0.8.0` / `kicad-skip` `0.2.5`, or compiled from `SKiDL` `3.0.0` or `atopile`
   `v0.12.5`?
4. **First `H2` carrier target:** After `P2` (Modbus) and `P9` (MQTT) land,
   which gap from [`coverage-matrix.md`](coverage-matrix.md) should be the first
   prototype carrier board?

## Sources

Every source below was checked on **2026-11-18**:

- **Repository design records and phase plan (read 2026-11-18):**
  - [`docs/concept.md`](../concept.md)
  - [`docs/plan/phases.md`](phases.md)
  - [`docs/adr/0001-tier-model.md`](../adr/0001-tier-model.md)
  - [`docs/adr/0002-priority-array-and-leases.md`](../adr/0002-priority-array-and-leases.md)
  - [`docs/adr/0005-licence.md`](../adr/0005-licence.md)
- **Hardware licences (fetched via HTTP 200 on 2026-11-18):**
  - `CERN-OHL-S-2.0` full text:
    <https://raw.githubusercontent.com/spdx/license-list-data/main/text/CERN-OHL-S-2.0.txt>
    (read 2026-11-18)
  - `CERN-OHL-W-2.0` full text:
    <https://raw.githubusercontent.com/spdx/license-list-data/main/text/CERN-OHL-W-2.0.txt>
    (read 2026-11-18)
  - `CERN-OHL-P-2.0` full text:
    <https://raw.githubusercontent.com/spdx/license-list-data/main/text/CERN-OHL-P-2.0.txt>
    (read 2026-11-18)
  - `EUPL-1.2` full text:
    <https://raw.githubusercontent.com/spdx/license-list-data/main/text/EUPL-1.2.txt>
    and [`LICENSE`](../../LICENSE) (read 2026-11-18)
  - CERN Open Hardware Licence portal:
    <https://cern-ohl.web.cern.ch/> (read 2026-11-18)
  - SPDX licence list data (`main` branch, commit `ddf7382`, checked 2026-11-18)
- **CAD, EDA, and MCP tools (checked via GitHub releases API / PyPI on
  2026-11-18):**
  - `plurano/tornus` README (`EUPL-1.2`, status `"No code yet."`):
    <https://raw.githubusercontent.com/plurano/tornus/main/README.md> (read
    2026-11-18)
  - `KiCad/kicad-source-mirror` (`10.0.8`, 2026-11-06), `kicad-python` (`0.8.0`
    on PyPI), `kicad-skip` (`0.2.5` on PyPI), `devbisme/skidl` (`3.0.0`,
    2026-10-16), `atopile` (`v0.12.5`, 2026-01-20), `tscircuit` (`v0.0.3231`),
    `INTI-CMNB/KiBot` (`v1.9.1`, 2026-07-28), `Freerouting` (`v2.5.0`,
    2026-10-05), `InteractiveHtmlBom` (`v2.12.0`, 2026-09-10), `build123d`
    (`v0.13.0`, 2026-09-21), `CadQuery` (`v2.8.0`, 2026-06-20), `FreeCAD`
    (`1.1.4`, 2026-09-28), `OpenSCAD` (`openscad-2021.01`, default branch commit
    2026-11-18T03:51Z; import/export formats verified in
    <https://raw.githubusercontent.com/openscad/openscad/openscad-2021.01/src/import.cc>
    and
    <https://raw.githubusercontent.com/openscad/openscad/openscad-2021.01/src/export.cc>,
    read 2026-11-18)
  - KiCad MCP servers: `mixelpixx/KiCAD-MCP-Server`,
    `oaslananka/kicad-mcp-pro`, `Seeed-Studio/kicad-mcp-server`,
    `claynicholson/copper-kicad-mcp`, `lamaalrajih/kicad-mcp` (checked
    2026-11-18)
- **Open firmware, gateways, and device documentation (fetched via HTTP 200 on
  2026-11-18):**
  - `esphome/esphome`:
    <https://raw.githubusercontent.com/esphome/esphome/dev/LICENSE> (read
    2026-11-18)
  - `arendst/Tasmota`:
    <https://raw.githubusercontent.com/arendst/Tasmota/development/LICENSE.txt>
    (read 2026-11-18)
  - `openshwprojects/OpenBK7231T_App`:
    <https://github.com/openshwprojects/OpenBK7231T_App> (read 2026-11-18)
  - `Koenkk/zigbee2mqtt`:
    <https://raw.githubusercontent.com/Koenkk/zigbee2mqtt/master/LICENSE> (read
    2026-11-18)
  - `emsesp/EMS-ESP32`:
    <https://raw.githubusercontent.com/emsesp/EMS-ESP32/main/LICENSE> (read
    2026-11-18)
  - `wmbusmeters/wmbusmeters`:
    <https://raw.githubusercontent.com/wmbusmeters/wmbusmeters/master/LICENSE>
    (read 2026-11-18)
  - `3cky/mbusd`:
    <https://raw.githubusercontent.com/3cky/mbusd/master/LICENSE> (read
    2026-11-18)
  - `Stefal/rtkbase` (`AGPL-3.0`):
    <https://raw.githubusercontent.com/Stefal/rtkbase/master/LICENSE> and
    <https://raw.githubusercontent.com/Stefal/rtkbase/master/README.md> (read
    2026-11-18)
  - `sunspec/models`:
    <https://raw.githubusercontent.com/sunspec/models/master/LICENSE> (read
    2026-11-18)
  - `bacnet-stack/bacnet-stack`:
    <https://github.com/bacnet-stack/bacnet-stack> (read 2026-11-18)
  - `selfbus/hardware-merged`:
    <https://github.com/selfbus/hardware-merged> (read 2026-11-18)
  - `OpenKNX/OpenKNX` and `OpenKNX/OGM-Common`:
    <https://github.com/OpenKNX/OpenKNX> and
    <https://raw.githubusercontent.com/OpenKNX/OGM-Common/main/LICENSE> (read
    2026-11-18)
  - `knxd/knxd`: <https://github.com/knxd/knxd> (read 2026-11-18)
  - `espressif/esp-matter`:
    <https://raw.githubusercontent.com/espressif/esp-matter/main/LICENSE> (read
    2026-11-18)
  - Shelly local API documentation: <https://shelly-api-docs.shelly.cloud/>
    (read 2026-11-18)
- **EU directives, regulations, and harmonised standards (verified on
  2026-11-18; direct HTTP fetch to `https://eur-lex.europa.eu/eli/...` returned
  HTTP 202 anti-bot challenge and was not bypassed; the English texts of
  `2022/30`, `2023/2444`, and `2024/2847` were read from the EU Publications
  Office Cellar by CELEX number, HTTP 200):**
  - Radio Equipment Directive `Directive 2014/53/EU`:
    <https://eur-lex.europa.eu/eli/dir/2014/53/oj> (verified via web search
    2026-11-18)
  - RED Cybersecurity Delegated Regulation `Commission Delegated Regulation (EU)
    2022/30` and amending `Commission Delegated Regulation (EU) 2023/2444`:
    <https://eur-lex.europa.eu/eli/reg_del/2022/30/oj>,
    <https://eur-lex.europa.eu/eli/reg_del/2023/2444/oj>,
    <https://publications.europa.eu/resource/celex/32022R0030>, and
    <https://publications.europa.eu/resource/celex/32023R2444> (Cellar, read 2026-11-18)
  - Low Voltage Directive `Directive 2014/35/EU`:
    <https://eur-lex.europa.eu/eli/dir/2014/35/oj> (verified via web search
    2026-11-18)
  - Electromagnetic Compatibility Directive `Directive 2014/30/EU`:
    <https://eur-lex.europa.eu/eli/dir/2014/30/oj> (verified via web search
    2026-11-18)
  - RoHS Directive `Directive 2011/65/EU`:
    <https://eur-lex.europa.eu/eli/dir/2011/65/oj> (verified via web search
    2026-11-18)
  - Cyber Resilience Act `Regulation (EU) 2024/2847`:
    <https://eur-lex.europa.eu/eli/reg/2024/2847/oj> and
    <https://publications.europa.eu/resource/celex/32024R2847> (Cellar, read 2026-11-18)
  - Construction Products Regulation `Regulation (EU) No 305/2011` and
    `Regulation (EU) 2024/3110` (harmonised framework for `EN 14604` smoke
    alarms and `EN 54` fire detection systems):
    <https://eur-lex.europa.eu/eli/reg/2011/305/oj> and
    <https://eur-lex.europa.eu/eli/reg/2024/3110/oj> (verified via web search
    2026-11-18)
  - Medical Devices Regulation `Regulation (EU) 2017/745`:
    <https://eur-lex.europa.eu/eli/reg/2017/745/oj> (verified via web search
    2026-11-18)
