# Safety, warranty and backups

**Read this completely before rooting or deploying anything.**

## Risks

- **Mains voltage, ~1000 W heating, a blade at up to ~6000 rpm.** Software from this project can switch the
  heater and the motor. A bug, a misconfigured automation or someone pressing "Start" in Home Assistant while
  another person has a hand in the bowl can cause burns or cuts. Never start the machine remotely unless you
  know that nobody is working at it, the lid is closed and the bowl is correctly inserted.
- **Rooting voids the warranty** and may violate the terms of use of the stock app. Flashing can brick the
  Android board. You need the original boot and recovery images to go back.
- **The left USB port is a 3.3 V port – connecting it to a computer destroys the board.** Only the right port
  ("Android USB") is the device port used for flashing and ADB over USB.
- **Do not leave the machine unattended** while a remote session runs, just like with the stock app.
- The serial protocol was reverse engineered; it is not documented by the manufacturer. Unknown firmware versions
  may behave differently. Always start in `read_only` mode and verify (see [protocol.md](protocol.md)).
- Power-cycling through a smart plug resets the machine; make sure the plug is rated for the load
  (the machine draws up to ~1.2 kW).

## Safety mechanisms in this project

| mechanism | where |
|---|---|
| `read_only: true` by default – no frames are sent, no control entities exist | `config/mcc.json`, `device/mcc_mux.py` |
| motor and heater are forced to STOP while the lid is open or the controller reports an error (only pure STOP/tare frames pass) | `Mux._maybe_inject` |
| command watchdog: no fresh command for `watchdog_s` (5 s) → STOP | `Mux._maybe_inject` |
| e-stop overlay on the machine's screen with a big STOP button whenever HA is in control | `overlay/` |
| turning or pressing the knob during a remote session → STOP | `Mux.run`, `knob_counts()` |
| session timer runs in the daemon; at the end STOP is sent and control is returned to the app | `MccHa._run_session` |
| implausible status frames (> 200 °C, > 20 kg …) are dropped before they reach the gates or HA | `Mux.run` |
| retained `cmd` messages are ignored (no surprise start after a reconnect) | `MccHa._on_message` |
| preset scripts and dashboard ask for confirmation and check the lid | `homeassistant/` |

None of these replaces your attention. The stock app's own interlocks remain in place in the controller as far as
they are implemented there (lid switch), but they have not been audited.

## Backups to keep

- `boot-original.img` and `recovery-original.img` read back before flashing anything – the only way back to stock
- the app's preferences file before you edit it (scripts in this repository make a copy in `/data/local/tmp`)
- the recipe database before importing recipes (`recipes/push-recipes.sh` makes a copy on every run)
