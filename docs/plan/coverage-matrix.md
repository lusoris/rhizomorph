<!--
SPDX-FileCopyrightText: 2026 Lusoris <lusoris@pm.me>

SPDX-License-Identifier: EUPL-1.2
-->
# Rhizomorph device and building coverage matrix

Start with [Building coverage matrix](#building-coverage-matrix) and
[Protocols and worker status per device class](#protocols-and-worker-status-per-device-class)
for the overview; the remaining sections provide the reference details for
[Precise positioning](#precise-positioning), [Gaps](#gaps),
[Open questions](#open-questions), and [Sources](#sources).

This document maps the 19 device classes targeted by **rhizomorph** (Greek
*rhiza*, root, and *morphe*, form, pronounced RY-zo-morf; see
[`README.md`](../../README.md#name)) across 10 building and environment types.
It distinguishes between **rhizomorph protocol worker gaps** (protocols that lack
a planned Tier 1 worker in [`../concept.md`](../concept.md#research) and
[`phases.md`](phases.md)) and **hardware gaps** (device classes or positioning
roles that lack an off-the-shelf local-control device, open firmware, or an open
carrier board design; see [`hardware.md`](hardware.md)).

## Building coverage matrix

Cell values indicate how often a device class is required in that building type:

- **`core`**: needed in nearly every deployment of that building type.
- **`often`**: common in that building type, depending on site equipment.
- **`rare`**: uncommon or specialised in that building type.
- **`n/a`**: not applicable to that building type.

To keep the matrix readable, the 10 building types are split across two tables
of five columns each with identical device-class rows.

### Table 1A: Residential, commercial, and institutional buildings

| # | Device class | House | Flat | Office | School | Hospital |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Heating and cooling control (thermostats, valve actuators, boilers and heat pumps) | `core` | `core` | `core` | `core` | `core` |
| 2 | Ventilation and air quality | `often` | `often` | `core` | `core` | `core` |
| 3 | Lighting | `core` | `core` | `core` | `core` | `core` |
| 4 | Shading and blinds | `often` | `often` | `core` | `core` | `often` |
| 5 | Electricity metering and sub-metering | `core` | `core` | `core` | `core` | `core` |
| 6 | Heat, water and gas metering | `core` | `core` | `core` | `core` | `core` |
| 7 | Solar, battery and EV charging | `often` | `rare` | `often` | `often` | `often` |
| 8 | Access and door state | `core` | `core` | `core` | `core` | `core` |
| 9 | Presence and occupancy | `often` | `often` | `core` | `core` | `core` |
| 10 | Environment sensing (temperature, humidity, light) | `core` | `core` | `core` | `core` | `core` |
| 11 | Leak and water shut-off | `often` | `often` | `often` | `often` | `core` |
| 12 | Alarm and security | `often` | `often` | `core` | `core` | `core` |
| 13 | Life safety (smoke, fire, CO) | `core` | `core` | `core` | `core` | `core` |
| 14 | Irrigation and weather | `often` | `rare` | `rare` | `often` | `rare` |
| 15 | Livestock and barn climate | `n/a` | `n/a` | `n/a` | `n/a` | `n/a` |
| 16 | Workshop and industrial machines | `rare` | `n/a` | `n/a` | `often` | `often` |
| 17 | Data room power and cooling (PDU, UPS, cooling units) | `rare` | `n/a` | `often` | `often` | `core` |
| 18 | Vehicle and boat systems | `n/a` | `n/a` | `n/a` | `n/a` | `n/a` |
| 19 | Precise positioning (RTK GNSS base and rover antennas, UWB, BLE direction finding) | `rare` | `rare` | `often` | `rare` | `core` |

### Table 1B: Agricultural, industrial, technical, outdoor, and mobile environments

| # | Device class | Farm and barn | Workshop and industrial | Data room | Outdoor and garden | Vehicles and boats |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Heating and cooling control (thermostats, valve actuators, boilers and heat pumps) | `often` | `core` | `core` | `n/a` | `core` |
| 2 | Ventilation and air quality | `core` | `core` | `often` | `n/a` | `often` |
| 3 | Lighting | `core` | `core` | `core` | `core` | `core` |
| 4 | Shading and blinds | `often` | `rare` | `n/a` | `often` | `rare` |
| 5 | Electricity metering and sub-metering | `core` | `core` | `core` | `often` | `core` |
| 6 | Heat, water and gas metering | `core` | `core` | `often` | `often` | `often` |
| 7 | Solar, battery and EV charging | `core` | `often` | `rare` | `often` | `core` |
| 8 | Access and door state | `core` | `core` | `core` | `core` | `core` |
| 9 | Presence and occupancy | `often` | `core` | `core` | `often` | `often` |
| 10 | Environment sensing (temperature, humidity, light) | `core` | `core` | `core` | `core` | `core` |
| 11 | Leak and water shut-off | `core` | `core` | `core` | `core` | `core` |
| 12 | Alarm and security | `core` | `core` | `core` | `often` | `core` |
| 13 | Life safety (smoke, fire, CO) | `core` | `core` | `core` | `n/a` | `core` |
| 14 | Irrigation and weather | `core` | `rare` | `n/a` | `core` | `often` |
| 15 | Livestock and barn climate | `core` | `n/a` | `n/a` | `rare` | `n/a` |
| 16 | Workshop and industrial machines | `often` | `core` | `n/a` | `rare` | `often` |
| 17 | Data room power and cooling (PDU, UPS, cooling units) | `rare` | `often` | `core` | `n/a` | `rare` |
| 18 | Vehicle and boat systems | `often` | `rare` | `n/a` | `n/a` | `core` |
| 19 | Precise positioning (RTK GNSS base and rover antennas, UWB, BLE direction finding) | `core` | `core` | `rare` | `core` | `core` |

## Protocols and worker status per device class

Planned rhizomorph Tier 1 workers from [`../concept.md`](../concept.md#research)
and [`phases.md`](phases.md) are:

- **Modbus** (`P2`, `tokio-modbus` `0.17.0`)
- **BACnet** (`P6`, `rusty-bacnet` `v0.15.0`)
- **KNX** (`P7`, `aimdb-knx-connector` `0.6.0`)
- **Matter** (`P8`, `rs-matter` `0.4.1`, targeting Matter Specification `1.6`)
- **MQTT** (`P9`, `rumqttc` `0.25.1`)

Any protocol outside those five has **no planned native worker** and requires
either a new worker phase, a Tier 2/3 plugin or sidecar ([ADR-0001](../adr/0001-tier-model.md)),
or an `H1` bridge to Modbus or MQTT ([`hardware.md`](hardware.md#stages)).

| # | Device class | Protocols needed (standard or specification and revision) | Planned rhizomorph worker (`docs/concept.md`) | Off-the-shelf local-control status (`H0`–`H2`) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Heating and cooling control (thermostats, valve actuators, boilers and heat pumps) | **Modbus RTU/TCP** (`Modbus Application Protocol V1.1b3` / `IEC 61158`); **BACnet/IP and MS/TP** (`ANSI/ASHRAE Standard 135` / `ISO 16484-5`); **KNX TP1 / KNXnet/IP** (`ISO/IEC 14543-3` / `EN 50090`); **Matter** (`Matter 1.4 / 1.6` over **Thread** `1.3.0 / 1.4` or Wi-Fi); **Zigbee** (`Zigbee 3.0 / PRO 2023`, `IEEE 802.15.4-2020`); **OpenTherm** (`OpenTherm Protocol Specification v2.2 / v4.2`); **EMS / eBUS** (vendor boiler buses); **EEBus** (`EEBus SPINE 1.3 / SHIP 1.0`, `VDE-AR-E 2829-6`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native OpenTherm, eBUS/EMS, Zigbee, or EEBus ([Gap 1](#gaps), [Gap 2](#gaps), [Gap 5](#gaps)). | `H0` commercial heat pumps and HVAC controllers over Modbus, BACnet, KNX, and Matter; `H1` bridges for OpenTherm (`ihormelnyk/opentherm_library` + ESPHome), EMS (`emsesp/EMS-ESP32`), and Zigbee TRVs (`Koenkk/zigbee2mqtt`) into MQTT (`P9`). |
| 2 | Ventilation and air quality | **Modbus RTU/TCP** (`V1.1b3`); **BACnet/IP and MS/TP** (`ASHRAE 135` / `ISO 16484-5`); **KNX** (`ISO/IEC 14543-3`); **Matter** (`1.4 / 1.6`); **MQTT** (`OASIS MQTT v3.1.1 / v5.0`, `ISO/IEC 20922`); **Zigbee 3.0** (`IEEE 802.15.4-2020`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native Zigbee ([Gap 1](#gaps)). | `H0` heat-recovery ventilation units (MVHR) and damper actuators over Modbus RTU/TCP, BACnet, and KNX; `H1` ESPHome / Tasmota CO2, VOC, and particulate (`PM2.5`) sensors over MQTT (`P9`). |
| 3 | Lighting | **DALI / DALI-2** (`IEC 62386-101/-102/-2xx`); **KNX TP1 / KNXnet/IP** (`ISO/IEC 14543-3` / `EN 50090`); **BACnet** (`ASHRAE 135`); **Matter** (`1.4 / 1.6`); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **DMX512-A** (`ANSI E1.11` / `Art-Net 4` / `ANSI E1.31 sACN`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **KNX** (`P7`), **BACnet** (`P6`), **Matter** (`P8`), **Modbus** (`P2`), and **MQTT** (`P9`). **No worker** for native **DALI IEC 62386**, Zigbee, or DMX512/sACN ([Gap 1](#gaps), [Gap 3](#gaps)). | `H0` KNX dimmers, Matter bulbs/switches, and Shelly MQTT relays/dimmers; `H0` DALI-to-KNX or DALI-to-Modbus/BACnet commercial gateways; `H2` candidate for an open DALI-2 master-to-MQTT/Modbus DIN-rail interface ([Gap 3](#gaps)). |
| 4 | Shading and blinds | **KNX TP1 / KNXnet/IP** (`ISO/IEC 14543-3`); **BACnet** (`ASHRAE 135`); **Modbus RTU** (`V1.1b3`); **Matter** (`1.4 / 1.6` Window Covering cluster); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native Zigbee ([Gap 1](#gaps)) or proprietary rolling-code 433/868 MHz RF motors ([Gap 14](#gaps)). | `H0` wired tubular motors controlled via KNX blind actuators, Shelly 2PM MQTT relays, or Modbus motor controllers; `H1` Tasmota / ESPHome / Zigbee2MQTT bridges. |
| 5 | Electricity metering and sub-metering | **Modbus RTU/TCP** (`V1.1b3`); **SunSpec Modbus** (`SunSpec Information Model Specification`); **M-Bus** (`EN 13757-2/-3/-4`); **DLMS/COSEM** (`IEC 62056-21 / -53 / -61 / -62`, DSMR P1 / HAN port); **BACnet** (`ASHRAE 135`); **KNX** (`ISO/IEC 14543-3`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), and **MQTT** (`P9`). **No worker** for native **M-Bus EN 13757** or **DLMS/COSEM IEC 62056** ([Gap 4](#gaps)). | `H0` MID-certified DIN-rail RS-485 Modbus meters (such as Eastron `SDM630-Modbus`) and Shelly Pro EM MQTT meters; `H1` ESPHome / `wmbusmeters` bridges for utility HAN/P1 ports to MQTT (`P9`). |
| 6 | Heat, water and gas metering | **Wired M-Bus** (`EN 13757-2` physical/link, `EN 13757-3` application) and **Wireless M-Bus** (`EN 13757-4` RF modes S, T, C at 868 MHz, `EN 13757-7` security); **LoRaWAN** (`LoRaWAN L2 1.0.4 / 1.1 TS001`); **Modbus RTU** (`V1.1b3`); pulse outputs (`SO` / reed contact) | Covered for **Modbus** (`P2`) and **MQTT** (`P9`). **No worker** for native **M-Bus EN 13757** or **LoRaWAN** ([Gap 4](#gaps), [Gap 8](#gaps)). | `H0` ultrasonic heat and flow meters with RS-485 Modbus modules; `H1` `wmbusmeters/wmbusmeters` (GPL-3.0) with 868 MHz receiver or PW250/M-Bus level converter bridging `EN 13757` to MQTT (`P9`). |
| 7 | Solar, battery and EV charging | **SunSpec Modbus** (`SunSpec Modbus` / `IEEE 1547-2018`); **Modbus RTU/TCP** (`V1.1b3`); **OCPP** (`OCPP 1.6J` and `OCPP 2.0.1 / 2.1`, `IEC 63584`); **ISO 15118** (`ISO 15118-2:2014` and `ISO 15118-20:2022` over `ISO 15118-3` HomePlug Green PHY PLC); **EEBus** (`EEBus SPINE / SHIP`, `VDE-AR-E 2829-6`); **CAN** (`ISO 11898-1:2024` for battery BMS); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`) and **MQTT** (`P9`). **No worker** for **OCPP**, **ISO 15118**, **EEBus**, or **CAN** ([Gap 5](#gaps), [Gap 9](#gaps)). | `H0` solar inverters and hybrid batteries supporting SunSpec Modbus TCP/RTU; `H1` open EV charger stacks such as `EVerest/everest-core` (Apache-2.0) bridging ISO 15118 and OCPP to MQTT (`P9`) or Modbus (`P2`). |
| 8 | Access and door state | **OSDP** (`SIA OSDP v2.2.2` / `IEC 60839-11-5` over RS-485 with AES-128 Secure Channel); **BACnet** (`ASHRAE 135` Access Door/Zone objects); **KNX** (`ISO/IEC 14543-3`); **Matter** (`1.4 / 1.6` Door Lock cluster over Thread/Wi-Fi); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), **Modbus** (`P2`), and **MQTT** (`P9`). **No worker** for **OSDP IEC 60839-11-5** ([Gap 6](#gaps)) or Zigbee ([Gap 1](#gaps)). | `H0` wired reed contacts on Modbus/KNX digital inputs and Matter-over-Thread smart locks; `H1`/`H2` gap for an open OSDP v2.2.2 door controller bridging `goToMain/libosdp` (Apache-2.0) to MQTT/Modbus ([Gap 6](#gaps)). |
| 9 | Presence and occupancy | **KNX** (`ISO/IEC 14543-3`); **BACnet** (`ASHRAE 135`); **DALI-2** (`IEC 62386-303` occupancy sensors); **Matter** (`1.4 / 1.6` Occupancy Sensing cluster); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **Bluetooth Low Energy** (`Bluetooth Core Specification 5.1 / 5.4`); **MQTT** (`v3.1.1 / v5.0`, including 24/60 GHz mmWave radar over ESPHome) | Covered for **KNX** (`P7`), **BACnet** (`P6`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native Zigbee, BLE, or DALI-2 ([Gap 1](#gaps), [Gap 3](#gaps)). | `H0` KNX PIR/presence detectors and Matter occupancy sensors; `H1` ESPHome 24 GHz mmWave + PIR nodes and Zigbee2MQTT occupancy sensors over MQTT (`P9`). |
| 10 | Environment sensing (temperature, humidity, light) | **Modbus RTU/TCP** (`V1.1b3`); **BACnet** (`ASHRAE 135`); **KNX** (`ISO/IEC 14543-3`); **Matter** (`1.4 / 1.6`); **Thread** (`1.3.0 / 1.4`); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **BLE** (`Bluetooth 5.x` advertisements); **LoRaWAN** (`1.0.4 / 1.1`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native Zigbee, BLE, or LoRaWAN ([Gap 1](#gaps), [Gap 8](#gaps)). | `H0` RS-485 Modbus, KNX, and Matter sensors; `H1` ESPHome, Tasmota, Zigbee2MQTT, and ChirpStack LoRaWAN-to-MQTT bridges (`P9`). |
| 11 | Leak and water shut-off | **Modbus RTU** (`V1.1b3`); **KNX** (`ISO/IEC 14543-3`); **Matter** (`1.4 / 1.6` Water Freeze/Leak Detector and Valve Configuration and Control clusters); **Zigbee 3.0** (`IEEE 802.15.4-2020`); **LoRaWAN** (`1.0.4 / 1.1`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for native Zigbee or LoRaWAN ([Gap 1](#gaps), [Gap 8](#gaps)). | `H0` motorized brass ball valves with local dry-contact / Modbus / Shelly MQTT control; `H1` Zigbee2MQTT and LoRaWAN battery leak probes bridged to MQTT (`P9`). |
| 12 | Alarm and security | **Modbus RTU/TCP** (`V1.1b3`); **BACnet** (`ASHRAE 135`); **KNX** (`ISO/IEC 14543-3`); **OSDP** (`IEC 60839-11-5`); **SNMPv3** (`IETF STD 62` / `RFC 3411–3418`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), and **MQTT** (`P9`). **No worker** for **OSDP** ([Gap 6](#gaps)), **SNMPv3** ([Gap 11](#gaps)), or `EN 50131` intrusion panel buses. | `H0` supervised dry-contact zone inputs on Modbus/KNX I/O modules; `H1` ESPHome / MQTT bridges for legacy panel serial buses. |
| 13 | Life safety (smoke, fire, CO) | **EN 14604** (standalone smoke alarms); **EN 54** series (commercial fire detection and fire alarm systems); **EN 50291-1** (domestic CO alarms); auxiliary read-only telemetry via **BACnet/IP or MS/TP** (`ASHRAE 135` Life Safety Point/Zone), **Modbus RTU/TCP** (`V1.1b3`), **KNX** (`ISO/IEC 14543-3`), **Zigbee 3.0**, or dry-contact relay bases | Covered for read-only status ingestion into input points over **Modbus** (`P2`), **BACnet** (`P6`), **KNX** (`P7`), **Matter** (`P8`), and **MQTT** (`P9`). Priority levels 1 and 2 (`Manual-Life Safety`, `Automatic-Life Safety`) in [ADR-0002](../adr/0002-priority-array-and-leases.md) apply only to commandable outputs (writers for level 2 remain open). | **Certified off-the-shelf (`H0`) only; never an own `H2` design** ([`hardware.md`](hardware.md#purpose-and-scope)). Commercial `EN 54` fire panels expose read-only BACnet or Modbus gateways; residential `EN 14604` / `EN 50291-1` alarms expose certified relay bases or Zigbee/KNX status modules ([Gap 7](#gaps)). |
| 14 | Irrigation and weather | **Modbus RTU** (`V1.1b3`, RS-485 soil moisture/EC/temperature probes and ultrasonic anemometers); **LoRaWAN** (`LoRaWAN L2 1.0.4 / 1.1`); **SDI-12** (`SDI-12 v1.4` environmental sensors); **MQTT** (`v3.1.1 / v5.0`); **Matter** (`1.4 / 1.6`) | Covered for **Modbus** (`P2`), **Matter** (`P8`), and **MQTT** (`P9`). **No worker** for **LoRaWAN** or **SDI-12** ([Gap 8](#gaps)). | `H0` RS-485 Modbus weather stations, soil probes, and 24 V AC solenoid valve manifolds on Modbus/MQTT relays; `H1` LoRaWAN-to-MQTT gateway for long-range field valves and probes. |
| 15 | Livestock and barn climate | **Modbus RTU/TCP** (`V1.1b3` for ammonia $\text{NH}_3$, $\text{CO}_2$, $\text{H}_2\text{S}$ electrochemical/NDIR transmitters, variable-frequency fan drives, curtain actuators); **LoRaWAN** (`1.0.4 / 1.1`); **ISOBUS** (`ISO 11783` / **SAE J1939** over **CAN** `ISO 11898-1`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`) and **MQTT** (`P9`). **No worker** for **LoRaWAN** ([Gap 8](#gaps)) or **CAN / SAE J1939 / ISO 11783** ([Gap 9](#gaps)). | `H0` industrial IP65+ RS-485 Modbus ammonia/climate transmitters and VFDs; `H2` candidate for a ruggedised IP65+ PoE/RS-485/CAN barn controller carrier board ([Gap 13](#gaps)). |
| 16 | Workshop and industrial machines | **OPC UA** (`IEC 62541` series); **Modbus RTU/TCP** (`V1.1b3`); **CAN / CANopen** (`ISO 11898-1` / `CiA 301`); **MQTT** / **Sparkplug B** (`OASIS MQTT v3.1.1 / v5.0`, `ISO/IEC 20922`) | Covered for **Modbus** (`P2`) and **MQTT** (`P9`). **No worker** for **OPC UA IEC 62541** ([Gap 10](#gaps)) or **CAN** ([Gap 9](#gaps)). | `H0` PLCs, CNC controllers, VFD spindle/pump drives, and compressed-air meters supporting Modbus TCP/RTU; native OPC UA requires a new worker or Tier 3 sidecar ([Gap 10](#gaps)). |
| 17 | Data room power and cooling (PDU, UPS, cooling units) | **SNMP** (`SNMPv3`, `IETF STD 62` / `RFC 3411–3418`); **Modbus RTU/TCP** (`V1.1b3`); **BACnet/IP** (`ASHRAE 135`); **Redfish** (`DMTF DSP0266`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`), **BACnet** (`P6`), and **MQTT** (`P9`). **No worker** for **SNMPv3** ([Gap 11](#gaps)) or Redfish. | `H0` rack PDUs, precision CRAC/in-row cooling units, and commercial UPS units with Modbus TCP or BACnet/IP cards; `H1` Network UPS Tools (`networkupstools/nut`, GPL-2.0+) bridging USB/SNMP UPS state to MQTT (`P9`). |
| 18 | Vehicle and boat systems | **CAN** (`ISO 11898-1:2024` / `ISO 11898-2:2024`); **SAE J1939** (heavy vehicles/generators over 29-bit CAN); **NMEA 2000** (`IEC 61162-3` over CAN); **NMEA 0183** (`IEC 61162-1` serial ASCII); **Signal K** (`Signal K Specification v1.7.0` JSON over HTTP/WebSocket); **Victron VE.Direct / Modbus TCP** (`V1.1b3`); **MQTT** (`v3.1.1 / v5.0`) | Covered for **Modbus** (`P2`) and **MQTT** (`P9`). **No worker** for **CAN**, **SAE J1939**, **NMEA 2000 IEC 61162-3**, **NMEA 0183 IEC 61162-1**, or **Signal K** ([Gap 9](#gaps)). | `H0` marine/RV inverter-chargers exposing Modbus TCP; `H1` open Signal K server (`SignalK/signalk-server`, Apache-2.0, implementing `SignalK/specification`, CC-BY-SA-2.0) on Linux with isolated SocketCAN adaptor bridging NMEA 2000, NMEA 0183, and J1939 to MQTT (`P9`). |
| 19 | Precise positioning (RTK GNSS base and rover antennas, UWB, BLE direction finding) | **RTCM 3.x** (`RTCM 10403.3 / 10403.4`) over **NTRIP v2.0** (`RTCM 10410.1`) and **NMEA 0183** (`IEC 61162-1`); **UWB** (`IEEE Std 802.15.4z-2020` HRP/LRP PHY/MAC and **FiRa Consortium** `PHY/MAC Technical Specification 2.0`); **Bluetooth 5.1+ Direction Finding** (`Bluetooth Core Specification v5.1+`, Constant Tone Extension `CTE` for **AoA** and **AoD**); **MQTT** (`v3.1.1 / v5.0`) | Covered only after positioning engines publish coordinates or ranges to **MQTT** (`P9`) or **Modbus** (`P2`). **No worker** for **RTCM 3.x / NTRIP**, **NMEA 0183**, **IEEE 802.15.4z / FiRa UWB**, or **Bluetooth 5.1 AoA/AoD** IQ processing ([Gap 12](#gaps)). | `H0`/`H1` RTK GNSS base stations via `Stefal/rtkbase` (AGPL-3.0; modified network services carry a Section 13 Corresponding Source offer) with u-blox `ZED-F9P` modules plus an NTRIP/TCP-to-MQTT bridge; `H1`/`H2` `DS-TWR` UWB boards using Qorvo `DWM3000` (internal 38.4 MHz crystal) or `TDoA` anchors using `DW3000` with a 38.4 MHz TCXO; `H2` gap for open PoE ceiling anchors combining UWB and BLE AoA antenna arrays ([Gap 12](#gaps)). |

## Precise positioning

Row 19 spans outdoor centimetre-level satellite navigation and indoor decimetre-
to sub-metre radio location. Because no single radio physics works both outdoors
under open sky and indoors through reinforced concrete, three complementary
technologies are required.

### Summary comparison of positioning technologies

| Attribute | RTK GNSS (`RTCM 10403.3 / 10403.4` + `NTRIP 10410.1`) | Ultra-Wideband (`IEEE 802.15.4z-2020` + `FiRa 2.0`) | BLE Direction Finding (`Bluetooth 5.1+` `AoA` / `AoD`) |
| :--- | :--- | :--- | :--- |
| **Primary measurement principle** | Dual/multi-band carrier-phase differential satellite ranging against a stationary local base station | Picosecond Time-of-Flight (ToF) via Two-Way Ranging (`SS-TWR` / `DS-TWR`), Time Difference of Arrival (`TDoA`), or Phase Difference of Arrival (`PDoA`) | Phase difference of a 2.4 GHz Constant Tone Extension (`CTE`) across a multi-antenna RF switch array (`AoA` at locator, `AoD` at tag) |
| **Accuracy class and required conditions** | **$0.01\text{ m} + 1\text{ ppm}$ CEP horizontal and $0.01\text{ m} + 1\text{ ppm}$ CEP vertical** in RTK mode (u-blox `ZED-F9P-01B` Data sheet `UBX-17051259 - R09`, Table 2); requires unobstructed sky view (`HDOP < 3.0`), multi-constellation L1/L2 or L1/L5 carrier lock, low multipath, and a base-to-rover baseline below the receiver's long-baseline warning (above 100 km; 50 km with firmware `HPG 1.12`; `ZED-F9P` Integration manual `UBX-18010802 - R16`, Section 3.1.5.4.2 and footnote 9) | **$\pm 0.06\text{ m}$ typical calibrated ranging accuracy** ($\pm 0.10\text{ m}$ module specification; $\pm 10^\circ$ PDoA / $\pm 5^\circ$ computed AoA on PDoA variants; Qorvo `DW3000` Datasheet `v1.1` Table 14 and `DWM3000` Data Sheet `Rev B` p. 1); requires line-of-sight on UWB Channel 5 (`6489.6 MHz`) or Channel 9 (`7987.2 MHz`) and per-board antenna delay calibration | **"A couple of degrees" angular accuracy and $\approx 0.5\text{ m}$ positioning accuracy** (Silicon Labs `Bluetooth Direction Finding Fundamentals` `v0.1`, p. 5/13; Nordic `nRF52833` `v1.3` / `nRF5340` `v1.2` and Silicon Labs `EFR32BG22` `Rev. 1.0` specifications); requires line-of-sight to ceiling/wall antenna arrays and multipath filtering (such as spatial smoothing with MUSIC or ESPRIT) |
| **Indoor / outdoor limits** | **Outdoor only.** The data sheet states its acquisition figures for satellites received at $-130\text{ dBm}$ (`UBX-17051259 - R09` Table 1, note 3); roofs, concrete floors, and metal barn/workshop siding block line-of-sight or induce severe carrier-phase multipath, losing RTK Fix indoors. | **Indoor and short-range outdoor.** Wideband `499.2–500 MHz` pulses (`DW3000` `v1.1` Table 11, `DWM3000` `Rev B` Table 6) resolve direct paths from wall reflections; requires **3 non-collinear anchors per room** for 2D position or **4 non-coplanar anchors per room** for 3D position. | **Indoor room and corridor scale.** Multi-year coin-cell tag life in `AoA` mode; requires multi-element antenna arrays ($\le \lambda/2 \approx 0.0625\text{ m} = 62.5\text{ mm}$ spacing at 2.4 GHz, `Bluetooth Direction Finding Fundamentals` `v0.1` p. 4/13) and **1 locator per zone** (bearing/presence) or **multiple locators per room** (triangulated 2D/3D coordinates, p. 11/13). |
| **Building types where it applies** | `Farm and barn` (outdoor yards, autonomous tractors, pasture virtual fencing), `outdoor and garden` (robotic mowers, boundary survey, irrigation mapping), `vehicles and boats` (vessel position, docking, attitude/heading), `house` / `office` / `workshop` (roof-mounted stationary RTK base station) | `Hospital` (infusion pump, crash cart, and bed tracking), `workshop and industrial` (forklift/AGV safety zones, torque-tool localisation), `farm and barn` (indoor robotic scraper/feeder navigation and livestock stall tracking), `office` (secure zone access) | `Hospital` (high-volume disposable/coin-cell asset and patient/staff badges), `office` and `school` (asset tracking and indoor wayfinding), `workshop and industrial` (pallet, tote, and tool crib tracking), `farm and barn` (ear-tag livestock zone presence) |
| **Protocols** | `RTCM 10403.3 / 10403.4` (messages 1005/1006, MSM4/MSM7 1074/1077, 1084/1087, 1094/1097, 1124/1127, 1230), `NTRIP v2.0` (`RTCM 10410.1`), `NMEA 0183` (`IEC 61162-1`), u-blox `UBX`, bridged to `MQTT` (`P9`) | `IEEE Std 802.15.4z-2020` (BPRF/HPRF modes with scrambled timestamp sequence `STS`), `FiRa Consortium PHY/MAC 2.0`, bridged over Ethernet/Wi-Fi to `MQTT` (`P9`) | `Bluetooth Core Specification v5.1+` Connectionless or Connection-Oriented `CTE` (`AoA`/`AoD`), Zephyr Bluetooth Direction Finding API, bridged to `MQTT` (`P9`) |
| **Documented modules and open designs** | Module: u-blox `ZED-F9P` (multi-band L1/L2 or L1/L5 RTK receiver). Open base station software/design: `Stefal/rtkbase` (AGPL-3.0; modified network services carry a Section 13 source offer) running on a single-board computer with a roof survey antenna. | Module/IC: Qorvo `DWM3000` (certified module around `DW3110` IC with internal 38.4 MHz crystal for `TWR`) and Qorvo `DW3000` (`DW3110`/`DW3120` IC supporting an external 38.4 MHz `TCXO` for `TDoA` anchors). Open hardware reference: `Makerfabs/Makerfabs-ESP32-UWB-DW3000`. | SoCs/modules: Nordic `nRF52833`, `nRF5340` (with Zephyr RTOS `direction_finding` samples) and Silicon Labs `EFR32BG22` (reference $4 \times 4$ patch array `BRD4185A`). |

### 1. RTK GNSS (Real-Time Kinematic Global Navigation Satellite System)

- **Base station and rover antenna types:**
  - **Base station:** Requires a fixed, vibration-free roof or mast mount with
    an unobstructed sky view (`HDOP < 3.0` as in the go/no-go test of
    `UBX-18010802 - R16` Section 3.19.2, and a configurable minimum satellite
    elevation mask `CFG-NAVSPG-INFIL_MINELEV`, Section 3.1.8.2) and a
    multi-band (L1/L2/L5) Right-Hand Circularly Polarised (RHCP) geodetic
    survey antenna, choke-ring antenna, or survey-grade patch antenna with an
    integrated ground plane ($\ge 100\text{--}150\text{ mm}$ diameter for patch
    elements, Section 4.8.4) to reject multipath.
  - **Rover:** Uses a multi-band active patch antenna over a metal vehicle/robot
    roof ground plane or a multi-band helical antenna on handheld or small
    robotic rovers. Dual-antenna moving-baseline rovers provide true GNSS
    heading on boats and agricultural tractors even while stationary.
- **Correction transport:** The stationary base station runs a survey-in or uses
  known geodetic coordinates, generates `RTCM 10403.3 / 10403.4` differential
  carrier-phase observation streams (Station ARP message `1005`/`1006` and
  Multiple Signal Messages `MSM4`/`MSM7`: GPS `1074`/`1077`, GLONASS
  `1084`/`1087` + `1230`, Galileo `1094`/`1097`, BeiDou `1124`/`1127`), and
  serves them through `Stefal/rtkbase` (`AGPL-3.0`; under Section 13 of the
  licence, any modified version operated as a network service must offer its
  Corresponding Source to remote users). `Stefal/rtkbase` (`README.md` lines
  13 and 260–275) provides RTKLIB `str2str` services for an external NTRIP
  caster client, a local `NTRIP v2.0` (`RTCM 10410.1`) caster, a TCP `RTCM`
  server, a serial/radio `RTCM` link, raw file logging, and `gpsd` NMEA
  forwarding, without needing a paid external cloud NTRIP service.
- **Gaps:** Rhizomorph has no native NTRIP caster/client or `NMEA 0183` /
  `RTCM 3.x` worker, and `Stefal/rtkbase` does not include an MQTT publisher;
  connecting base-station status or rover `NMEA 0183` / `UBX` fixes to `MQTT`
  (`P9`) therefore requires an additional `NTRIP`/TCP/`gpsd`-to-`MQTT` bridge
  ([Gap 12](#gaps)).

### 2. Ultra-Wideband (UWB, `IEEE 802.15.4z-2020` and `FiRa 2.0`)

- **Ranging modes (`TWR` vs `TDoA`):**
  - **Two-Way Ranging (`SS-TWR` / `DS-TWR`):** A mobile tag exchanges timestamped
    frames sequentially with each fixed room anchor. Double-Sided TWR cancels
    first-order crystal clock offset errors without requiring wired clock
    synchronisation between anchors, making it straightforward to deploy in
    workshops, barns, and small hospitals for moderate tag counts (tens of tags
    per room).
  - **Time Difference of Arrival (`TDoA`):** Fixed anchors share a synchronised
    timebase (via wired clock distribution or wireless master-anchor sync
    beacons), and mobile tags transmit short blink frames. Because tags only
    transmit brief blinks rather than multi-message exchanges with every anchor,
    `TDoA` scales to hundreds or thousands of coin-cell tags per building at lower
    tag energy cost, at the expense of strict anchor clock synchronisation
    (requiring low-drift TCXOs or wired sync on anchors).
- **Anchor count per room:** 2D horizontal positioning at Fixed Tag Height
  requires at least **3 non-collinear anchors** with clear line-of-sight in the
  room; full 3D positioning requires at least **4 non-coplanar anchors**. Rooms
  with heavy metallic obstructions (industrial machine bays, hospital imaging
  suites, steel livestock stalls) require 4 to 6 anchors per zone so at least 3
  anchors maintain line-of-sight (`LoS`) simultaneously.
- **Gaps:** Development boards (`Makerfabs/Makerfabs-ESP32-UWB-DW3000`) use the
  Qorvo `DWM3000` module (`Rev B`, Section 1.1 and Table 2), which seals an
  internal 38.4 MHz crystal under its RF shield and exposes no external clock
  input pin, making it suitable for `DS-TWR` but not external-TCXO `TDoA`
  anchors; there is no open-hardware PoE ceiling anchor with a 38.4 MHz
  `TCXO`-clocked `DW3000` IC (`DW3000` Datasheet `v1.1`, Table 10) and wired or
  wireless clock sync, nor an open `TWR`/`TDoA`-to-MQTT solver ready for `H1`
  adoption ([Gap 12](#gaps)).

### 3. Bluetooth 5.1+ Direction Finding (`AoA` and `AoD`)

- **Angle of Arrival (`AoA`) vs Angle of Departure (`AoD`):**
  - **`AoA` (asset tracking):** A low-cost mobile tag with a single antenna
    transmits standard BLE packets appended with a Constant Tone Extension
    (`CTE`, an unmodulated carrier tone of 16 to 160 $\mu\text{s}$). A fixed
    ceiling or wall locator connected to a multi-antenna array switches across
    its antenna elements during the `CTE` via an RF switch and captures
    in-phase and quadrature (`I/Q`) samples. A locator or edge sidecar computes
    azimuth and elevation angles from the phase differences across the array.
  - **`AoD` (indoor navigation and robotics):** Fixed ceiling locators transmit
    `CTE` packets while switching across their multi-antenna arrays and
    broadcasting their antenna array coordinates; mobile rovers or handsets with
    a single antenna sample `I/Q` locally and compute their own position
    privately without transmitting location beacons.
- **Antenna arrays:** Require $N$-element patch or dipole arrays (such as a
  $4 \times 4$ uniform rectangular array or circular array) with inter-element
  spacing $\le \lambda/2$ at 2.4 GHz ($\approx 0.0625\text{ m} = 62.5\text{ mm}$,
  `Bluetooth Direction Finding Fundamentals` `v0.1` p. 4/13), controlled by
  GPIO RF switches defined in the MCU DeviceTree (Nordic `nRF52833` / `nRF5340`
  under Zephyr RTOS or Silicon Labs `EFR32BG22`).
- **Gaps:** No open-source, calibrated 2.4 GHz $4 \times 4$ patch antenna array
  KiCad design paired with an open `I/Q`-to-angle solver (such as MUSIC/ESPRIT
  in Rust) and `MQTT` output exists in the repository or ready off the shelf
  without vendor-locked RTLS appliances ([Gap 12](#gaps)).

## Gaps

Every gap listed below identifies whether the missing piece is a **rhizomorph
protocol worker**, an **off-the-shelf local-control device (`H0`)**, an **open
firmware or gateway (`H1`)**, or an **open carrier board / antenna design
(`H2`)**, names the affected matrix cells, and cites its verified source.

1. **No native Zigbee (`IEEE 802.15.4-2020` / Zigbee 3.0) worker in rhizomorph.**
   - **What is missing:** Rhizomorph worker (or official `H1` bridge contract).
     [`../concept.md`](../concept.md#research) plans workers for Modbus, BACnet,
     KNX, Matter, and MQTT, but no native Zigbee stack.
   - **Affected cells:** Classes 1–4, 8–13 across `house`, `flat`, `office`, and
     `school` where battery Zigbee TRVs, window sensors, and buttons are
     deployed.
   - **Mitigation / stage:** `H1` bridge via `Koenkk/zigbee2mqtt` (GPL-3.0) into
     the `P9` MQTT worker (`rumqttc`).
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and
     <https://raw.githubusercontent.com/Koenkk/zigbee2mqtt/master/LICENSE> (read
     2026-11-18).

2. **No native OpenTherm (`v2.2 / v4.2`) or boiler bus (`EMS` / `eBUS`) worker or
   certified `H0` local Modbus bridge.**
   - **What is missing:** Rhizomorph worker and `H2` isolated DIN-rail boiler
     interface carrier board (`H1` open firmware exists).
   - **Affected cells:** Class 1 (Heating and cooling control) in `house`,
     `flat`, `office`, and `school`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84;
     <https://raw.githubusercontent.com/ihormelnyk/opentherm_library/master/LICENSE>
     and <https://raw.githubusercontent.com/emsesp/EMS-ESP32/main/LICENSE> (read
     2026-11-18).

3. **No native DALI / DALI-2 (`IEC 62386`) worker or open-hardware DIN-rail
   DALI-2 master gateway.**
   - **What is missing:** Rhizomorph worker and an `H2` electrically isolated
     16 V DALI bus power/transceiver carrier board bridging `IEC 62386` to
     Modbus (`P2`) or MQTT (`P9`) for installations that do not already have a
     commercial DALI-to-KNX (`P7`) or DALI-to-BACnet (`P6`) gateway.
   - **Affected cells:** Class 3 (Lighting) and Class 9 (Presence and occupancy)
     in `office`, `school`, `hospital`, and `workshop and industrial`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and DALI
     Alliance specification overview <https://www.dali-alliance.org/dali/> (read
     2026-11-18).

4. **No native M-Bus (`EN 13757-2/-3/-4`) or DLMS/COSEM (`IEC 62056`) worker.**
   - **What is missing:** Rhizomorph worker for wired/wireless M-Bus (`EN 13757`)
     and utility smart-meter HAN/P1 ports (`IEC 62056`), plus an `H2` isolated
     36 V wired M-Bus master carrier board (`H1` wireless M-Bus reception is
     covered by `wmbusmeters/wmbusmeters` over MQTT `P9`).
   - **Affected cells:** Class 5 (Electricity metering) and Class 6 (Heat, water
     and gas metering) across `house`, `flat`, `office`, `school`, `hospital`,
     `farm and barn`, and `workshop and industrial`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and
     <https://raw.githubusercontent.com/wmbusmeters/wmbusmeters/master/LICENSE>
     (read 2026-11-18).

5. **No native EV charging and grid-flexibility workers (`OCPP 1.6J / 2.0.1`
   `IEC 63584`, `ISO 15118-2:2014 / -20:2022`, `EEBus SPINE/SHIP`).**
   - **What is missing:** Rhizomorph worker or Tier 2/3 integration with open
     EV charging and grid controllers (`EVerest/everest-core`, `enbility/spine-go`).
   - **Affected cells:** Class 1 (Heating and cooling heat pumps) and Class 7
     (Solar, battery and EV charging) in `house`, `flat`, `office`, `school`,
     `hospital`, `farm and barn`, `workshop and industrial`, and `vehicles and
     boats`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84; Open Charge
     Alliance <https://openchargealliance.org/protocols/open-charge-point-protocol/>;
     EEBus <https://www.eebus.org/>;
     <https://raw.githubusercontent.com/EVerest/everest-core/main/LICENSE>;
     <https://raw.githubusercontent.com/enbility/spine-go/main/LICENSE> (all
     read 2026-11-18).

6. **No native OSDP (`SIA OSDP v2.2.2` / `IEC 60839-11-5`) access-control worker
   or open `H2` OSDP door controller board.**
   - **What is missing:** Rhizomorph worker for RS-485 OSDP Secure Channel door
     readers and an `H2` PoE/RS-485 dual-reader access controller carrier board
     (open C/C++ protocol stack exists in `goToMain/libosdp`).
   - **Affected cells:** Class 8 (Access and door state) and Class 12 (Alarm and
     security) in `office`, `school`, `hospital`, `workshop and industrial`, and
     `data room`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and
     <https://raw.githubusercontent.com/goToMain/libosdp/master/LICENSE> (read
     2026-11-18).

7. **Life-safety devices (`EN 14604`, `EN 54`, `EN 50291-1`) prohibit first-party
   `H2` hardware and require certified read-only auxiliary interfaces.**
   - **What is missing:** Standardised `H0` TOML device profiles for commercial
     `EN 54` fire alarm panel BACnet/Modbus status gateways and residential
     `EN 14604` / `EN 50291-1` relay/Zigbee status bases, mapped to read-only
     input points (whose present value is written directly by telemetry under
     [ADR-0002](../adr/0002-priority-array-and-leases.md)). Any interlock that
     commands a separate commandable output point at `Automatic-Life Safety`
     priority level 2 is a separate design decision, as priority arrays belong
     only to commandable outputs and writers for level 2 remain open in
     [ADR-0002](../adr/0002-priority-array-and-leases.md).
   - **Affected cells:** Class 13 (Life safety) across all building types except
     `outdoor and garden`.
   - **Source:** [`docs/adr/0002-priority-array-and-leases.md`](../adr/0002-priority-array-and-leases.md)
     lines 26–35 and 47–68, and EU Construction Products Regulation `Regulation
     (EU) No 305/2011` / `EN 14604` / `EN 54` (verified via web search
     2026-11-18).

8. **No native LoRaWAN (`LoRaWAN L2 1.0.4 / 1.1`) or `SDI-12` (`v1.4`) worker.**
   - **What is missing:** Rhizomorph worker or `H1` local LoRaWAN network server
     (such as ChirpStack) to MQTT (`P9`) profile contract, plus an `H2`
     low-power `SDI-12`-to-LoRaWAN/Modbus field sensor carrier board.
   - **Affected cells:** Classes 6, 10, 11, 14, and 15 in `farm and barn` and
     `outdoor and garden`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and LoRa
     Alliance <https://lora-alliance.org/about-lorawan/> (read 2026-11-18).

9. **No native CAN (`ISO 11898-1`), `SAE J1939` / `ISOBUS` (`ISO 11783`), `NMEA
   2000` (`IEC 61162-3`), `NMEA 0183` (`IEC 61162-1`), or `Signal K` (`v1.7.0`)
   worker.**
   - **What is missing:** Rhizomorph Tier 1 SocketCAN / NMEA / Signal K worker
     and an `H2` galvanically isolated dual-CAN + RS-485 carrier board for 12/24
     V vehicle, tractor, and marine power systems.
   - **Affected cells:** Class 7 (Battery BMS), Class 15 (Livestock and barn
     climate), Class 16 (Workshop and industrial machines), and Class 18
     (Vehicle and boat systems) in `farm and barn`, `workshop and industrial`,
     and `vehicles and boats`.
   - **Source:** [`docs/concept.md`](../concept.md) lines 69–84;
     <https://raw.githubusercontent.com/SignalK/specification/master/LICENSE>
     (`CC-BY-SA-2.0`); and
     <https://raw.githubusercontent.com/SignalK/signalk-server/master/LICENSE>
     (`Apache-2.0`, all read 2026-11-18).

10. **No native OPC UA (`IEC 62541`) worker.**
    - **What is missing:** Rhizomorph Tier 1 worker or Tier 3 sidecar
      ([ADR-0001](../adr/0001-tier-model.md)) for `IEC 62541` OPC UA binary/TCP
      client subscriptions and method calls.
    - **Affected cells:** Class 16 (Workshop and industrial machines) in
      `workshop and industrial`, `school`, `hospital`, and `farm and barn`.
    - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and OPC
      Foundation <https://opcfoundation.org/about/opc-technologies/opc-ua/>
      (read 2026-11-18).

11. **No native SNMPv3 (`IETF STD 62` / `RFC 3411–3418`) or NUT (`networkupstools/nut`)
    worker.**
    - **What is missing:** Rhizomorph worker for `SNMPv3` and Network UPS Tools
      (`NUT`) TCP protocol to poll and command rack PDUs, ATS switches, and UPS
      systems that do not expose Modbus TCP (`P2`) or BACnet/IP (`P6`).
    - **Affected cells:** Class 12 (Alarm and security) and Class 17 (Data room
      power and cooling) in `data room`, `office`, `school`, `hospital`, and
      `workshop and industrial`.
    - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and
      <https://github.com/networkupstools/nut> (read 2026-11-18).

12. **No native precise-positioning worker (`RTCM 10403.3 / 10403.4` over
    `NTRIP 10410.1`, `IEEE 802.15.4z` / `FiRa 2.0` UWB, `Bluetooth 5.1+ AoA/AoD`)
    and no open PoE UWB + BLE AoA ceiling anchor design.**
    - **What is missing:**
      1. Rhizomorph Tier 1/3 positioning ingestion and coordinate-frame worker
         handling `RTCM 3.x` / `NTRIP v2.0` health, `NMEA 0183` / `UBX` fix
         quality, UWB `TWR`/`TDoA` multilateration, and BLE `AoA`/`AoD` angle
         triangulation, plus an `H1` bridge from `Stefal/rtkbase` (`NTRIP` /
         TCP `RTCM` / `gpsd` streams, as `rtkbase` has no built-in MQTT
         publisher) into `MQTT` (`P9`).
      2. An `H2` open-hardware PoE ceiling anchor board combining UWB ranging
         and a Nordic `nRF52833` / `nRF5340` or Silicon Labs `EFR32BG22` BLE
         5.1+ Direction Finding receiver with a calibrated 2.4 GHz $4 \times 4$
         patch antenna array: either a pre-certified Qorvo `DWM3000` module
         (which uses a sealed internal 38.4 MHz crystal and has no external
         clock input pin, limiting the board to `DS-TWR` or crystal-trimmed
         operation) or a chip-down Qorvo `DW3000` (`DW3110`/`DW3120`) transceiver
         driven by an AC-coupled 38.4 MHz `TCXO` (`DW3000` Datasheet `v1.1`,
         Table 10) with wired or wireless anchor clock synchronisation for
         `TDoA` (requiring full RED Article 3(2) radio testing).
    - **Affected cells:** Class 19 (Precise positioning) across `office`,
      `hospital`, `farm and barn`, `workshop and industrial`, `outdoor and
      garden`, and `vehicles and boats`.
    - **Source:** [`docs/concept.md`](../concept.md) lines 69–84;
      <https://raw.githubusercontent.com/Stefal/rtkbase/master/LICENSE>
      (`AGPL-3.0`);
      <https://raw.githubusercontent.com/Stefal/rtkbase/master/README.md>
      (lines 13 and 260–275);
      <https://download.mikroe.com/documents/datasheets/DWM3000_datasheet.pdf>
      (`Rev B`, May 2021; third-party copy; vendor site refused CLI fetch on
      2026-11-18);
      <https://datasheet.lcsc.com/datasheet/pdf/e06f26519d4502e7d7a9bf99fdb1e852.pdf?productCode=C3294486>
      (`DW3000` Datasheet `v1.1`, 24 March 2021; third-party copy; vendor site
      refused CLI fetch on 2026-11-18);
      <https://forum.qorvo.com/t/dwm3000-tdoa-example/11432>;
      <https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000>;
      <https://www.firaconsortium.org/>;
      <https://www.bluetooth.com/learn-about-bluetooth/feature-enhancements/direction-finding/>
      (all read 2026-11-18).

13. **Harsh-environment (`H2`/`H3`) barn and outdoor enclosure and bus-isolation
    gap.**
    - **What is missing:** `H2` galvanically isolated RS-485/CAN/PoE sensor hub
      and `H3` ammonia-resistant (`\text{NH}_3`), UV-stabilised IP65+ enclosure
      design for corrosive livestock barns and outdoor field edges. Standard
      indoor consumer sensors corrode or fail condensation tests in barn air.
    - **Affected cells:** Classes 10, 14, 15, and 19 in `farm and barn` and
      `outdoor and garden`.
    - **Source:** [`docs/plan/hardware.md`](hardware.md#stages) (`H2` and `H3`
      stage definitions) and `plurano/tornus` README (`"No code yet."`,
      <https://raw.githubusercontent.com/plurano/tornus/main/README.md>, read
      2026-11-18).

14. **Proprietary 433 MHz / 868 MHz tubular blind and gate motor protocols.**
    - **What is missing:** Many retrofit residential and commercial tubular shade
      and gate motors use closed rolling-code sub-GHz RF remotes without local
      wired or documented bus control; reliable local integration requires
      selecting wired four-wire AC or RS-485 motors (`H0`) paired with KNX (`P7`),
      Modbus (`P2`), Matter (`P8`), or Shelly MQTT (`P9`) actuators.
    - **Affected cells:** Class 4 (Shading and blinds) and Class 8 (Access and
      door state) in `house`, `flat`, `office`, and `outdoor and garden`.
    - **Source:** [`docs/concept.md`](../concept.md) lines 69–84 and Shelly
      local API documentation <https://shelly-api-docs.shelly.cloud/> (read
      2026-11-18).

## Open questions

1. **Positioning coordinate representation in the kernel:** Because `Value` in
   [ADR-0002](../adr/0002-priority-array-and-leases.md) is a scalar enum of
   `bool`, `i64`, `f64`, and `u16`, should a 3D position fix (`x`, `y`, `z` or
   `lat`, `lon`, `alt`, plus accuracy radius and fix-quality enum) be registered
   as separate scalar points per rover or should a structured telemetry payload
    run in Tier 3 ([ADR-0001](../adr/0001-tier-model.md))?
2. **Bridge vs native worker boundary:** Which of the missing protocols in
   [Gaps](#gaps) (`DALI IEC 62386`, `M-Bus EN 13757`, `OCPP 2.0.1`, `OPC UA IEC
   62541`, `SNMPv3`, `CAN / NMEA 2000 / Signal K`) warrant a dedicated Tier 1
   Rust worker crate in [`phases.md`](phases.md) after `P10`, and which should
   permanently stay behind `H1` MQTT/Modbus bridges?
3. **Rust crate maturity for missing protocols:** Crate availability, MSRV, and
   maintenance state on `crates.io` for `OPC UA`, `SNMPv3`, `SocketCAN / J1939 /
   NMEA 2000`, `OCPP`, and `M-Bus` were not queried against the `crates.io` API
   in this pass and need the same check recorded in
   [`../concept.md`](../concept.md#research) before any new worker phase is
   scheduled.

## Sources

Every source below was checked on **2026-11-18**:

- **Repository design records (read 2026-11-18):**
  - [`docs/concept.md`](../concept.md)
  - [`docs/plan/phases.md`](phases.md)
  - [`docs/plan/hardware.md`](hardware.md)
  - [`docs/adr/0001-tier-model.md`](../adr/0001-tier-model.md)
  - [`docs/adr/0002-priority-array-and-leases.md`](../adr/0002-priority-array-and-leases.md)
- **Protocol specifications, alliances, and open stacks (fetched via HTTP 200 on
  2026-11-18):**
  - DALI Alliance (`IEC 62386` / DALI-2): <https://www.dali-alliance.org/dali/>
    (read 2026-11-18)
  - Open Charge Alliance (`OCPP 1.6J / 2.0.1 / 2.1`):
    <https://openchargealliance.org/protocols/open-charge-point-protocol/> (read
    2026-11-18)
  - Linux Foundation Energy `EVerest` (`ISO 15118-2/-20`, `OCPP`, `SunSpec
    Modbus`): <https://raw.githubusercontent.com/EVerest/everest-core/main/LICENSE>
    (read 2026-11-18)
  - EEBus Initiative (`SPINE` / `SHIP`) and `enbility/spine-go`:
    <https://www.eebus.org/> and
    <https://raw.githubusercontent.com/enbility/spine-go/main/LICENSE> (read
    2026-11-18)
  - SunSpec Modbus Information Models (`sunspec/models`):
    <https://raw.githubusercontent.com/sunspec/models/master/LICENSE> (read
    2026-11-18)
  - Connectivity Standards Alliance Matter (`Matter 1.x`):
    <https://csa-iot.org/all-solutions/matter/> (read 2026-11-18)
  - LoRa Alliance (`LoRaWAN L2 1.0.4 / 1.1`):
    <https://lora-alliance.org/about-lorawan/> (read 2026-11-18)
  - OPC Foundation (`OPC UA IEC 62541`):
    <https://opcfoundation.org/about/opc-technologies/opc-ua/> (read 2026-11-18)
  - Open Supervised Device Protocol (`IEC 60839-11-5`, `goToMain/libosdp`):
    <https://raw.githubusercontent.com/goToMain/libosdp/master/LICENSE> (read
    2026-11-18)
  - Signal K marine specification (`SignalK/specification`, `CC-BY-SA-2.0`) and
    server (`SignalK/signalk-server`, `Apache-2.0`):
    <https://raw.githubusercontent.com/SignalK/specification/master/LICENSE> and
    <https://raw.githubusercontent.com/SignalK/signalk-server/master/LICENSE>
    (read 2026-11-18)
  - Network UPS Tools (`networkupstools/nut`):
    <https://github.com/networkupstools/nut> (read 2026-11-18)
  - OpenTherm library (`ihormelnyk/opentherm_library`):
    <https://raw.githubusercontent.com/ihormelnyk/opentherm_library/master/LICENSE>
    (read 2026-11-18)
  - EMS-ESP boiler gateway (`emsesp/EMS-ESP32`):
    <https://raw.githubusercontent.com/emsesp/EMS-ESP32/main/LICENSE> (read
    2026-11-18)
  - Wireless/wired M-Bus gateway (`wmbusmeters/wmbusmeters`, `EN 13757`):
    <https://raw.githubusercontent.com/wmbusmeters/wmbusmeters/master/LICENSE>
    (read 2026-11-18)
  - Zigbee2MQTT (`Koenkk/zigbee2mqtt`, `IEEE 802.15.4` / Zigbee 3.0):
    <https://raw.githubusercontent.com/Koenkk/zigbee2mqtt/master/LICENSE> (read
    2026-11-18)
  - Shelly local API documentation: <https://shelly-api-docs.shelly.cloud/>
    (read 2026-11-18)
- **Precise positioning specifications, modules, and open designs (fetched via
  HTTP 200 on 2026-11-18):**
  - `Stefal/rtkbase` open GNSS RTK base station (`AGPL-3.0`, `RTCM 10403.3` /
    `NTRIP 10410.1`):
    <https://raw.githubusercontent.com/Stefal/rtkbase/master/LICENSE> and
    <https://raw.githubusercontent.com/Stefal/rtkbase/master/README.md> (read
    2026-11-18)
  - FiRa Consortium (`IEEE 802.15.4z` UWB PHY/MAC):
    <https://www.firaconsortium.org/> (read 2026-11-18)
  - Open ESP32 + Qorvo `DWM3000` UWB hardware reference:
    <https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000> (read 2026-11-18)
  - Bluetooth SIG Direction Finding (`Bluetooth 5.1+ AoA / AoD`):
    <https://www.bluetooth.com/learn-about-bluetooth/feature-enhancements/direction-finding/>
    (read 2026-11-18)
  - u-blox `ZED-F9P-01B Data sheet` (`UBX-17051259 - R09`, 24 March 2023):
    <https://content.u-blox.com/sites/default/files/documents/ZED-F9P-01B_DataSheet_UBX-17051259.pdf>
    (read 2026-11-18)
  - u-blox `ZED-F9P Integration manual` (`UBX-18010802 - R16`, 30 October 2024):
    <https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf>
    (read 2026-11-18)
  - Qorvo `DW3000 Datasheet` (`Version 1.1`, 24 March 2021; third-party copy;
    vendor site refused CLI fetch on 2026-11-18):
    <https://datasheet.lcsc.com/datasheet/pdf/e06f26519d4502e7d7a9bf99fdb1e852.pdf?productCode=C3294486>
    (read 2026-11-18)
  - Qorvo `DWM3000 Data Sheet` (`Rev B`, May 2021) and Qorvo Tech Forum `TDoA`
    clock guidance (post #3, 4 January 2022); the data sheet link is a
    third-party copy; vendor site refused CLI fetch on 2026-11-18:
    <https://download.mikroe.com/documents/datasheets/DWM3000_datasheet.pdf> and
    <https://forum.qorvo.com/t/dwm3000-tdoa-example/11432> (read 2026-11-18)
  - Nordic Semiconductor `nRF52833 Product Specification` (`v1.3`, document
    `4452_021 v1.3`, 7 August 2020; third-party copy; vendor site refused CLI fetch on 2026-11-18):
    <https://fgcoca.github.io/Guia-de-trabajo-para-microbit/datasheet/nRF52833.pdf>
    (read 2026-11-18)
  - Nordic Semiconductor `nRF5340 Product Specification` (`v1.2`, document
    `4406_640 v1.2`, 30 September 2021; third-party copy; vendor site refused CLI fetch on 2026-11-18):
    <https://datasheet.lcsc.com/datasheet/pdf/6efcc39a770f71ab97f60efc3494de83.pdf?productCode=C3606967>
    (read 2026-11-18)
  - Silicon Labs `EFR32BG22 Wireless Gecko SoC Family Data Sheet` (`Rev. 1.0`;
    third-party copy; vendor site refused CLI fetch on 2026-11-18):
    <https://datasheet.lcsc.com/datasheet/pdf/841f42e0d4c7698aab75a7c0ae34fc4f.pdf?productCode=C1015249>
    (read 2026-11-18)
  - Silicon Labs `Bluetooth Direction Finding Fundamentals` (`v0.1`, replacing
    `UG103.18`) and `Bluetooth Location Services / RTL Library` (`v11.1.2`):
    <https://docs.silabs.com/bluetooth-direction-finding-fundamentals/0.1/bluetooth-direction-finding-fundamentals.pdf>
    and <https://docs.silabs.com/rtl-lib/11.1.2/rtl-lib.pdf> (read 2026-11-18)
