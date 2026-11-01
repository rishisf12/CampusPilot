# AdaptAir — Full Physical Working Prototype: Phase-Wise Engineering Plan

**Project:** AdaptAir — Dual-Node ESP32-S3 Air-Quality Monitoring & Active Ventilation Control  
**Author role:** Principal Systems Engineer (30+ yrs, mechatronics/embedded/systems)  
**BOM basis:** Your listed hardware (ESP32-S3-DevKitC-1-N8R8 ×2, SEN66, SPS30, SDP810-500Pa, INA228, Noctua NF-F12 PWM ×2, Mean Well LRS-50-12, LM2596 buck, custom 2-layer PCB, SimbaLux acrylic, Numakers PETG)  
**MCP stack:** All 7 MCP servers configured globally in OpenCode (filesystem, git, esp-arduino, electronics-i2c, kicad, fusion, csv-sqlite)

---

## Target System Specification (derived from BOM)

| Subsystem | Key Parts | Function |
|-----------|-----------|----------|
| Compute | ESP32-S3-DevKitC-1-N8R8 ×2 (Node 1 & Node 2) | Dual-core sensing node + control node, Wi-Fi/BLE, dual USB-UART |
| Air quality | Sensirion SEN66 (0x6B) | PM1-10, VOC, NOx, CO₂ |
| Particulate | Sensirion SPS30 (0x69) | Certified PM1/2.5/10 |
| Pressure | Sensirion SDP810-500Pa (0x25) | Differential pressure across filter/duct |
| Power | INA228 (0x40) | Shunt + bus voltage, energy-aware optimization |
| Fans | Noctua NF-F12 industrialPPC-3000 PWM ×2 | 25 kHz PWM intake/exhaust |
| PSU | Mean Well LRS-50-12 (12 V, 4.2 A) + LM2596 buck (3.3 V) | 12 V rail + 3.3 V logic rail |
| PCB | Custom 2-layer (KiCad) | All sensors, fans, power, ESP32-S3 interconnnect |
| Enclosure | SimbaLux acrylic sheets + Numakers PETG prints | Panels, fan shrouds, sensor mounts, air-path ducting |
| Storage | 16 GB microSD | Runtime logs + walk-forward ML datasets |
| MCP | 7 servers (see opencode.jsonc) | Firmware/git/flash/I²C/PCB/CAD/telemetry |

---

## Phase-Wise Plan (17 weeks, gate-reviewed)

### Phase 0 — Requirements, Architecture & Risk Retirement (Week 1)
**Owner:** Systems Engineer  
**Deliverables:**
- System requirements specification (SRS) — functional + non-functional
- Block diagram: Node 1 (sensing) ↔ Node 2 (control/fan/PWR) ↔ dashboard
- Interface control document (ICD): I²C addresses, UART, PWM, power rails
- FMEA / risk register (power budget 4.2 A @ 12 V, 3.3 V logic translation, I²C address collisions)
- MCP environment validation: all 7 servers respond to `tools/list`

**Exit criteria (Gate 0):** SRS signed off; BOM validated against mechanical fit; MCP servers reachable.

### Phase 1 — Electronics Design & Custom 2-Layer PCB (Weeks 2–4)
**Owner:** Hardware Engineer  
**MCP used:** `adaptair-kicad` (KiCAD-MCP-Server), `adaptair-electronics-i2c`

**Activities:**
1. Schematic capture in KiCad: ESP32-S3 ×2, SEN66, SPS30, SDP810, INA228, fan drivers, LM2596 3.3 V, Mean Well input, microSD, level-shifters (3.3↔5 V where needed)
2. Run `i2c_device_list` / `i2c_bus_scan` simulation to confirm no address collisions (0x6B, 0x69, 0x25, 0x40)
3. Validate 3.3 V logic translation & level shifters via `i2c_check_level_shifter`
4. PCB layout: 2-layer, ground plane, separate analog/digital return, fan PWM traces routed away from I²C
5. Run KiCad DRC via `adaptair-kicad`; fix all errors/warnings
6. Generate Gerbers + BOM (CSV) + pick-and-place centroid
7. Order PCBs & components

**Exit criteria (Gate 1):** DRC-clean KiCad project; Gerbers released to fab; BOM costed.

### Phase 2 — Firmware & ESP32-S3 Bring-up (Weeks 5–8)
**Owner:** Embedded Firmware Engineer  
**MCP used:** `adaptair-esp-arduino`, `adaptair-electronics-i2c`, `adaptair-filesystem`, `adaptair-git`

**Activities:**
1. ESP-IDF + Arduino CLI pre-flight via `esp_preflight`
2. Node 1 firmware: I²C master reads SEN66/SPS30/SDP810 at 100 kHz, INA228 shunt/bus, microSD logging, UART telemetry to Node 2
3. Node 2 firmware: 25 kHz PWM fan control (Noctua NF-F12), closed-loop based on pressure differential (SDP810) + air-quality thresholds, UART to Node 1, Wi-Fi to dashboard
4. Pre-flight checks before every flash; flash binaries over USB via `esp_flash`
5. Live serial telemetry capture via `esp_serial_read` (baud 115200)
6. Multitasking logic verification (FreeRTOS tasks: sensing, control, logging, comms)
7. Commit all source to git via `adaptair-git`

**Exit criteria (Gate 2):** Both nodes boot, sensors read valid values, fans spin under PWM control, serial logs clean.

### Phase 3 — Mechanical Enclosure & 3D Prints (Weeks 9–11)
**Owner:** Mechanical Engineer  
**MCP used:** `adaptair-fusion` (Autodesk Fusion MCP, HTTP 127.0.0.1:27182)

**Activities:**
1. Parametric enclosure panels (SimbaLux acrylic) in Fusion 360 via `adaptair-fusion`
2. Custom mounting brackets + fan shrouds + sensor mounts (Numakers PETG)
3. Air-path ducting geometry: intake → filter → SEN66/SPS30 → SDP810 pressure tap → exhaust fan
4. Fit-check: PCB standoffs, fan mounting holes (Noctua NF-F12 120 mm), sensor port locations, microSD access
5. Export STL/STEP for 3D printing; export DXF for acrylic laser cutting
6. Print PETG brackets/shrouds; laser-cut acrylic panels

**Exit criteria (Gate 3):** All printed/cut parts fit PCB + fans + sensors; airflow path unobstructed.

### Phase 4 — System Integration & Bring-up (Weeks 12–13)
**Owner:** Systems Integration Engineer  
**MCP used:** all 7 (esp-arduino, electronics-i2c, filesystem, git, csv-sqlite)

**Activities:**
1. Populate custom 2-layer PCB; solder ESP32-S3, sensors, fans, power
2. Verify 3.3 V & 12 V rails with INA228 via `i2c_register_read` (0x40)
3. Confirm I²C device presence via `i2c_bus_scan` / `i2c_validate_address`
4. Mechanical assembly: PCB into enclosure, fans in shrouds, sensors ducted
5. Power-on sequence: Mean Well 12 V → LM2596 3.3 V → ESP32-S3 nodes → sensors → fans
6. Verify PWM 25 kHz on fan tach/control; monitor 4.2 A rail budget via INA228
7. End-to-end: Node 1 senses → Node 2 adjusts fans → dashboard receives telemetry

**Exit criteria (Gate 4):** Full prototype powers up; all subsystems communicate; no rail over-current.

### Phase 5 — Calibration, Validation & ML Dataset (Weeks 14–15)
**Owner:** Test & Data Engineer  
**MCP used:** `adaptair-csv-sqlite`, `adaptair-filesystem`

**Activities:**
1. Calibrate SEN66/SPS30 against reference PM/VOC/CO₂ source
2. Calibrate SDP810 pressure vs. flow (manometer reference)
3. Calibrate INA228 shunt gain; verify energy-aware fan throttling
4. Log 16 GB microSD runtime data; walk-forward ML validation on fan-speed vs. air-quality model
5. Parse logs via `csv_sqlite_mcp` (sqlite_query, csv_query, ml_validation_summary)
6. Document accuracy, repeatability, response time

**Exit criteria (Gate 5):** Sensors within ±5% of reference; ML model validates on held-out data.

### Phase 6 — Interactive Dashboard & End-to-End Verification (Weeks 16–17)
**Owner:** Full-Stack / Systems Engineer  
**MCP used:** all 7 + dashboard (see `/dashboard`)

**Activities:**
1. Deploy interactive dashboard (single-file HTML + local Python bridge)
2. Connect dashboard to Node 2 Wi-Fi telemetry (REST/WebSocket fallback to serial bridge)
3. Live gauges: PM1/2.5/10, VOC, NOx, CO₂, differential pressure, shunt/bus voltage, fan PWM %, rail current
4. Manual + automatic fan control (25 kHz PWM setpoint)
5. End-to-end test: inject known air-quality step → confirm fan response → confirm dashboard reflects change
6. Verify all 7 MCP servers still healthy; commit final firmware/config

**Exit criteria (Gate 6):** End-to-end loop closed; dashboard responsive; all requirements traceable.

### Phase 7 — Final Review, Documentation & Handoff (Week 17)
**Owner:** Project Lead  
**Deliverables:**
- As-built KiCad project + Gerbers
- Firmware repo (git) + flashed binaries
- Fusion 360 models + STL/STEP/DXF exports
- Test report & calibration certificates
- User manual & MCP server runbook

---

## MCP Usage Map (per phase)

| Phase | Primary MCP Servers | What They Do |
|-------|--------------------|--------------|
| 0 | filesystem, git | SRS/version control |
| 1 | kicad, electronics-i2c | PCB DRC, I²C address validation |
| 2 | esp-arduino, filesystem, git | Compile/flash/serial + source control |
| 3 | fusion | Parametric enclosure/CAD |
| 4 | esp-arduino, electronics-i2c, filesystem | Bring-up, I²C verify, power check |
| 5 | csv-sqlite, filesystem | Log parsing, ML validation |
| 6 | csv-sqlite, esp-arduino | Dashboard telemetry bridge, E2E test |

---

## Immediate Next Step
Review Phase 0 deliverables and confirm the exact ESP32-S3 serial port (`ESP_PORT`, e.g. `COM3`) and whether you'll use ESP-IDF or Arduino CLI for flashing. I can then generate the KiCad netlist/BOM, the Fusion 360 parametric script, and the dashboard below.