# Home Assistant

## MQTT

All entities are created by MQTT discovery under one device ("Monsieur Cuisine Connect", identifier from
`device_id`). `<base>` is `mqtt_base_topic` (default `mcc`).

| topic | dir | retained | content |
|---|---|---|---|
| `<base>/avail` | machine → | yes | `online` / `offline` (last will) |
| `<base>/state` | machine → | yes | JSON: `temp_actual_c`, `heater_temp_c`, `target_temp_c`, `weight_g`, `speed_target`, `rpm_target`, `rpm_actual`, `running`, `lid_open`, `error`, `error_code`, `scale_stable`, `motor_heat`, `firmware`, … |
| `<base>/set/program` | → machine | yes | `Standard`, `Knead`, `Sear`, `Steam` |
| `<base>/set/speed` | → machine | yes | 0–10 |
| `<base>/set/temp` | → machine | yes | 0–130 °C |
| `<base>/set/direction` | → machine | yes | `Forward`, `Reverse` |
| `<base>/set/timer`, `<base>/set/timer_s` | → machine | yes | minutes + seconds; 0 + 0 = until stopped |
| `<base>/cmd` | → machine | **no** | `start`, `stop`, `tare` |
| `<base>/remaining` | machine → | yes | seconds left (0 = none) |
| `<base>/adb` | host → | yes | `online` / `offline` (watchdog) |
| `<base>/screen` | host → | yes | PNG screenshot (camera) |

**Order matters:** set the values first (retained), then send `start`. A session uses the values present at start.

## Entities (default entity ids)

Read-only (always): `sensor.mcc_actual_temperature`, `sensor.mcc_target_temperature`,
`sensor.mcc_heater_temperature`, `sensor.mcc_weight`, `sensor.mcc_speed`, `sensor.mcc_target_rpm`,
`binary_sensor.mcc_running`, `binary_sensor.mcc_lid_open`, `binary_sensor.mcc_error`.

Control (only with `"read_only": false`): `select.mcc_program`, `select.mcc_direction`, `number.mcc_speed`,
`number.mcc_target_temperature`, `number.mcc_timer_minutes`, `number.mcc_timer_seconds`, `sensor.mcc_time_left`,
`button.mcc_start`, `button.mcc_stop`, `button.mcc_tare`.

From the host: `binary_sensor.mcc_adb_connection` (watchdog, expires after 10 min without updates),
`camera.mcc_display` (screen service).

Tare works while idle, also with the lid open (the daemon takes the line for one second without overlay);
it is ignored during a session.

## Dashboard

```bash
python3 homeassistant/dashboard/gen_dashboard.py --power sensor.my_plug_power --energy sensor.my_plug_energy
```

writes `mcc-dashboard.yaml`. Create a new dashboard in HA, open the raw configuration editor and paste it.
Built-in cards only (tile, heading, history graph, picture entity). The start tile asks for confirmation.

## Preset scripts

`homeassistant/scripts.yaml` contains four presets (chop, purée, sauté, keep warm). Each sets all values, waits
one second so the retained values reach the machine, checks that the lid is closed and presses start.

## Power-cycle blueprint

`homeassistant/blueprints/mcc_power_cycle.yaml` – if ADB has been unreachable for 5 minutes and the machine is
switched on but idle (power between 1 W and 10 W; idle was ~2.7 W on the tested unit), it switches the smart
plug off for 15 s and on again, at most once per hour. Import it via *Settings → Automations → Blueprints →
Import* (from your fork's raw URL) or copy it to `config/blueprints/automation/mcc/`.
A mains power cycle resets both the Android board and the controller; `adb reboot` only restarts Android.

## Display camera

`host/mcc-screen.py` publishes screenshots every 5 s while the machine runs and every 60 s while the screen
is on. Install `host/systemd/mcc-screen.service` (edit user and path).
