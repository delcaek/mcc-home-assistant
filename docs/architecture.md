# Architecture

## Components

| part | runs on | purpose |
|---|---|---|
| `device/mcc_mux.py` | machine | serial MITM: PTY + bind mount, frame codec, safety gates, e-stop, knob watch |
| `device/mcc_ha.py` | machine | entry point: MQTT, HA discovery, cooking sessions with timer, tare |
| `device/run.sh` | machine | starts the glibc Python through the glibc loader |
| `device/mccctl.sh` | machine | `start` / `stop` / `status` of the interpose in the right order |
| `device/crashlog.sh` | machine | crash-safe logcat/dmesg/heartbeat in flash |
| `overlay/` | machine | Android app: full-screen e-stop overlay with remaining time |
| `host/mcc-watchdog.sh` | host (cron) | ADB state to MQTT, keeps interpose/crashlog running, CPU cores, wakelock |
| `host/mcc-screen.py` | host (systemd) | screenshots → MQTT camera |
| `scripts/` | host | build runtime, deploy, uninstall, recipe type helper |
| `homeassistant/` | HA | dashboard generator, preset scripts, power-cycle blueprint |
| `recipes/` | host + machine | recipe import tooling |

## Why the interpose is built this way

- The app opens `/dev/ttyMT0` (4800 baud) to talk to the controller board. `mccctl.sh start` moves the real node
  to `/dev/ttyMT0_real`, starts the daemon, which creates a PTY and **bind-mounts the PTY slave onto
  `/dev/ttyMT0`** (`mount(MS_BIND)` via libc). Then the app is force-stopped and relaunched so it opens our PTY.
  Binding first and restarting the app afterwards avoids a race in which the app opens the real port first.
- A real bind mount needs real root. proot-based environments (Termux etc.) cannot do this, so the daemon runs
  as root with its own runtime.
- **Runtime:** Android uses bionic libc. We ship the glibc from an Ubuntu 22.04 armhf base image (only as a
  library source, nothing is chrooted) and an ARMv7 CPython from python-build-standalone, and start Python
  through the explicit loader `rootfs/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 --library-path …`.
  `PYTHONHOME` must be set, otherwise Python cannot find its standard library when started through the loader.
- **No Magisk boot scripts:** on the tested unit Magisk executed none of `post-fs-data.d`, module scripts or
  `service.d`. Instead `host/mcc-watchdog.sh` (cron, every 2 min) checks over ADB and starts the interpose. Once
  started, everything runs on the machine; the host is only needed for (re)starts and as MQTT broker location.

## Control mode

Normally every app frame is forwarded unchanged. When HA starts a session, `mcc_ha.py` sets the first command
and switches the mux to **control mode**: app frames are dropped (logged as `[app-x]`) and the mux sends its
own frame every 100 ms. Every second the session thread renews the command (watchdog). At the end of the timer,
on stop, lid open, error, overlay STOP or knob use the mux sends STOP for one second and gives the line back
to the app. The app does not notice; its UI simply shows the machine's status.

## Files on the machine

```
/data/mcc/
  rootfs/              glibc from ubuntu-base 22.04 armhf
  python/              CPython 3.12 (python-build-standalone, armv7)
  code/                mcc_mux.py, mcc_ha.py, paho/
  mcc.json             configuration (0600)
  run.sh mccctl.sh crashlog.sh
/data/local/tmp/mcc2.log          daemon log (frames, MQTT, e-stop)
/data/local/tmp/crashlog/         crash-safe logs
/data/data/io.mccha.overlay/files/{estop,remaining}   overlay exchange files
```
