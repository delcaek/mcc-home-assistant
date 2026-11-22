# Monsieur Cuisine Connect → Home Assistant

Monitor and control a **Lidl Monsieur Cuisine Connect (SilverCrest SKMC 1200)** from Home Assistant while the
stock cooking app with all its guided recipes keeps working on the machine.

- Live temperatures (content and heating element), scale, speed, lid, running and error state in Home Assistant
- Remote cooking sessions with timer: program, speed, temperature, direction, start / stop / tare
- On-screen e-stop overlay on the machine whenever Home Assistant is in control (plus: the knob stops it, too)
- Display of the machine as a Home Assistant camera
- Import your own recipes into the stock app's recipe database
- Host watchdog that (re)starts everything and an optional power-cycle automation

> [!CAUTION]
> **Read [docs/safety.md](docs/safety.md) before you start.** This project roots a mains-powered kitchen
> appliance with a heating element and a rotating blade and lets software switch both. Rooting voids the warranty,
> mistakes can brick the board, and on this machine **the left USB port (3.3 V) destroys the board** if you connect
> it to a computer. You do all of this at your own risk.

## How it works

```
 stock app ──▶ /dev/ttyMT0  (PTY created by us, bind-mounted over the real node)
                    │
              mcc_ha.py / mcc_mux.py  (glibc Python on the machine, real root)
                    │                          │
 controller ◀── /dev/ttyMT0_real          MQTT ◀──▶ Home Assistant (discovery)
                                               ▲
 host (any Linux box): mcc-watchdog.sh, mcc-screen.py ── ADB over Wi-Fi
```

The machine is an Android 6 tablet (MediaTek MT6580, ARMv7) that talks to a motor/heater controller over a
4800 baud serial line. A daemon on the rooted tablet places itself between app and controller, forwards everything
and decodes the controller's status frames to MQTT. For a remote session it temporarily suppresses the app's frames
and sends its own. Details: [docs/architecture.md](docs/architecture.md), [docs/protocol.md](docs/protocol.md).

## Requirements

- Monsieur Cuisine Connect **SKMC 1200** (other models: unknown, the protocol may differ)
- Root on the machine (Magisk) and ADB over Wi-Fi → [docs/rooting.md](docs/rooting.md)
- Home Assistant with the MQTT integration and a broker (e.g. Mosquitto)
- A Linux host on the same network with `adb` (Android platform-tools), `mosquitto-clients`, `python3`, `curl`
  (a Raspberry Pi or the machine that runs Home Assistant is fine)
- For the e-stop overlay: JDK 17 + Android SDK, or Docker ([overlay/build.sh](overlay/build.sh))

## Quick start

```bash
git clone https://github.com/delcaek/mcc-home-assistant.git mcc-ha && cd mcc-ha
cp config/config.example.env config/config.env   # host side: ADB address, MQTT broker
cp config/mcc.example.json   config/mcc.json     # machine side: MQTT broker, read_only
$EDITOR config/config.env config/mcc.json

scripts/build-runtime.sh          # downloads pinned Ubuntu base + Python + paho-mqtt, builds build/mcc-runtime.tar
overlay/build.sh                  # optional but recommended: build/overlay.apk (or the Docker variant)
scripts/deploy.sh                 # installs everything on the machine and starts the interpose
crontab -e                        # add: */2 * * * * /path/to/mcc-ha/host/mcc-watchdog.sh
```

The machine now appears in Home Assistant as device **Monsieur Cuisine Connect** with read-only sensors.
Cook something with the app and compare the log (`/data/local/tmp/mcc2.log` on the machine) with
[docs/protocol.md](docs/protocol.md). Only then set `"read_only": false` in `config/mcc.json` and run
`scripts/deploy.sh --code-only`; the control entities (program, speed, temperature, timer, start/stop/tare) appear.
**Test the first remote run with an empty or water-filled bowl.**

Then optionally:

- dashboard: `python3 homeassistant/dashboard/gen_dashboard.py` → [docs/home-assistant.md](docs/home-assistant.md)
- preset scripts: [homeassistant/scripts.yaml](homeassistant/scripts.yaml)
- display camera: [host/mcc-screen.py](host/mcc-screen.py) as a systemd service
- power-cycle blueprint (needs a smart plug): [homeassistant/blueprints/mcc_power_cycle.yaml](homeassistant/blueprints/mcc_power_cycle.yaml)
- your own recipes in the stock app: [docs/recipes.md](docs/recipes.md)

## Documentation

| | |
|---|---|
| [docs/safety.md](docs/safety.md) | risks, safety mechanisms, what to keep as backup |
| [docs/rooting.md](docs/rooting.md) | getting root and ADB over Wi-Fi (upstream guides + our deviations) |
| [docs/architecture.md](docs/architecture.md) | components, runtime, start sequence, files on the machine |
| [docs/protocol.md](docs/protocol.md) | serial protocol: frames, checksum, temperature levels, observations |
| [docs/home-assistant.md](docs/home-assistant.md) | MQTT topics, entities, dashboard, scripts, blueprint, camera |
| [docs/overlay.md](docs/overlay.md) | e-stop overlay app and knob e-stop |
| [docs/recipes.md](docs/recipes.md) | recipe database, JSON format, import, conversion guidelines |
| [docs/operations.md](docs/operations.md) | lessons learned on this Android 6 / toybox system |
| [docs/troubleshooting.md](docs/troubleshooting.md) | symptoms and fixes |
| [CHANGELOG.md](CHANGELOG.md) | status: what is verified on hardware and what is not |

## Credits and related projects

- [Wuki60/MrCuisineVibeConnect ("Toque")](https://github.com/Wuki60/MrCuisineVibeConnect) – rooting guide and
  protocol knowledge this work builds on
- [EliasKotlyar](https://github.com/EliasKotlyar) – earlier Monsieur Cuisine Connect hacking, TWRP recovery image
- [python-build-standalone](https://github.com/astral-sh/python-build-standalone), Ubuntu base images,
  [paho-mqtt](https://github.com/eclipse-paho/paho.mqtt.python) (EPL-2.0 / EDL-1.0, downloaded at build time)

This is an independent hobby project. It is not affiliated with or endorsed by Lidl, SilverCrest, the app vendor
or Vorwerk. Product names are trademarks of their owners. No vendor software, firmware or recipe content is
included in this repository.

## License

MIT, see [LICENSE](LICENSE).
