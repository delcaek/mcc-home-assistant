# Serial protocol (app ⇄ controller)

Line: `/dev/ttyMT0`, **4800 baud, 8N1, raw**. The app sends ~7–8 frames per second; the controller answers
continuously with status frames. Values below were confirmed on one SKMC 1200 (controller firmware `0x133a`)
by logging the app's frames and comparing them with the display, unless marked otherwise.

## Checksum

Sum of all bytes before the checksum byte, modulo 256.

## TX frame (app → controller), 15 bytes

| byte | meaning |
|---|---|
| 0 | `0x55` header |
| 1 | `0x0F` length (15) |
| 2 | `0xA1` type |
| 3 | operation: `00` STOP, `01` STANDARD, `03` STEAM, `04` TOAST (sear), `05` KNEAD, `0F` SLEEP/login, `C6` TURBO |
| 4 | `0xA9` = tare the scale, otherwise `00` |
| 5 | speed 0..10 |
| 6 | temperature **level** index (table below) |
| 7–10 | `00` |
| 11 | direction: `01` = counter-clockwise ("reverse", gentle stir), `00` = clockwise |
| 12 | `00` (seen as `01` together with op `0F` while the app is in its login/sleep state) |
| 13 | checksum over bytes 0–12 |
| 14 | `0xAA` terminator |

Idle frame of the app: `55 0f a1 00 00 00 00 00 00 00 00 00 00 05 aa`
Running, speed 3, 60 °C: `55 0f a1 01 00 03 05 00 00 00 00 00 00 0e aa`
When the scale view is opened the app sends a tare frame (byte 4 = `A9`).

## RX frame (controller → app), 27 bytes

| byte | meaning |
|---|---|
| 0, 1, 2 | `0x55`, `0x1B` (27), `0xB1` |
| 3 | status bits: `0x80` lid open, `0x40` NTC bowl (?), `0x20` over-temperature (?), `0x10` error, `0x04` scale stable / ready (changes 4→5 when running), `0x03` motor/heat (1 = running, 3 = turbo; turbo also shows `0x07`) |
| 4 | constant on the tested unit |
| 5 | error code |
| 6 | current speed setting |
| 7–8 | target rpm (big endian) – speed 1 = 559, 2 = 1010, 3 = 1440, 5 = 6020; keeps its value after stopping |
| 9–10 | "actual rpm" – **always 0** on the tested unit (no real rpm feedback) |
| 11 | target temperature level (same table) |
| 12–13 | heating element temperature °C (big endian, reacts fast – use it to see that heating is engaged) |
| 14–15 | content temperature °C (big endian) |
| 16–19 | weight in g, **signed** int32 big endian (exact, e.g. 440 / −440) |
| 20–21 | firmware (`0x133a`) |
| 22–24 | unknown, constant |
| 25 | checksum over bytes 0–24 |
| 26 | `0xAA` |

Status bit 1 is not "heater on" – heating is only visible through the rising element temperature.
The scale does not measure while the motor runs and fluctuates for ~3 s after a stop (sloshing).
Occasionally frames with a correct checksum but absurd values arrive (1000 °C, −2·10⁹ g); the daemon drops them.

## Temperature levels

| level | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| °C | off | 37 | 45 | 50 | 55 | 60 | 65 | 70 | 75 | 80 | 85 | 90 | 95 | 100 | 105 | 110 | 115 | 120 | 125 | 130 |

The daemon rounds a requested temperature **down** to the next level (never hotter than requested).

## Timing

- There is **no timer in the protocol**; the app (and our daemon) times the run and sends STOP.
- The controller stops the motor if frames do not arrive often enough. **Send ~10 frames/s**; at 4 frames/s it
  stopped after ~2 s.
- The rotary knob is not part of this protocol – it is read by the app directly (`/dev/knob`). See
  [overlay.md](overlay.md) for how the daemon still notices knob use.

## Verifying on your machine

Keep `"read_only": true`, cook a known setting with the app (e.g. 60 °C, speed 3, 2 min, then turbo) and read
`/data/local/tmp/mcc2.log`:

```
12:00:01 [app>] 550fa1010003050000000000000eaa    <- what the app sends
12:00:01 [rx>] 551bb105...                             <- controller status (only changes are logged)
12:00:01 [rx ] {"lid_open": false, "speed_target": 3, "target_temp_c": 60, ...}
```

The bytes must match the tables above before you enable control. During a remote session `[app-x]` marks
suppressed app frames and `[we>]` our frames.
