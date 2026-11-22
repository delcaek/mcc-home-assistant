# Changelog / status

## 0.1.0 – first public version (Nov 2026)

Extracted from a working private installation on one SKMC 1200 and generalised for publication.

### Verified on real hardware (one SKMC 1200, stock ROM, Magisk v31)
- Serial interpose via PTY bind mount, stock app keeps working (guided recipes, scale, knob)
- Protocol: TX/RX frame layout, checksum, temperature level table, weight, lid bit, target rpm, heater temperature
- Remote sessions: speeds 1–5 tested with water, heating to 50 °C, timer auto-stop, tare (also with lid open)
- 10 frames/s send rate requirement (at 4/s the controller stops after ~2 s)
- E-stop overlay (STOP button, remaining time), knob e-stop via /proc/interrupts
- Host watchdog (restart after reboot, ADB state, wakelock, CPU cores), display camera
- Recipe import with a custom recipe type (32 recipes imported, visible under "new")
- Runtime: Ubuntu 22.04 armhf glibc + python-build-standalone 3.12.16 (20261026, stripped) + paho-mqtt 2.1.0

### Changed during generalisation – NOT yet tested on hardware
- All settings moved to `config/mcc.json` / `config/config.env` (previously constants)
- English entity names and `default_entity_id` (`sensor.mcc_*` …); option values `Knead/Sear/Steam`,
  direction `Forward/Reverse` (previously German); `soll_temp_c` renamed to `target_temp_c` in the state JSON
- `read_only` defaults to `true`; MQTT connects asynchronously (retries if the broker is down at start)
- `mccctl.sh start` restores the original node if the PTY could not be bound
- Overlay package renamed to `io.mccha.overlay`, English UI texts; info strip overlay removed
- Watchdog/camera read the retained MQTT state instead of the HA REST API (no token needed)
- `scripts/build-runtime.sh`, `scripts/deploy.sh`, `scripts/uninstall.sh`, `scripts/add-recipe-type.py`,
  `overlay/build.sh` (+ Dockerfile), dashboard generator output as file, power-cycle blueprint
- Recipe insert: language, recipe type and unit strings configurable per recipe (were fixed German values)

The overlay build script and the runtime build script were run successfully on an x86_64 Linux host
(runtime from cached downloads with matching checksums; download URLs checked). Deployment to a fresh machine
with these scripts has not been done yet – please report results.

### Open
- Only one unit tested; firmware variants and other models unknown
- Parity/stop bits: 8N1 works, never measured with a logic analyser
- Some status bits (`ntc_bowl`, `over_temp`) and bytes 4, 22–24 of the status frame are not understood
- "Heat without stirring" (speed 0 with temperature) not tested
- Magisk boot scripts did not run on the tested unit; the host watchdog is the workaround
