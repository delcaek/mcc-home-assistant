# Troubleshooting

| symptom | cause / fix |
|---|---|
| `deploy.sh`: "no root (su)" | allow root for the shell in Magisk; check `adb shell "su -c id"` |
| entities do not appear in HA | check broker address/credentials in `config/mcc.json`; on the machine `tail /data/local/tmp/mcc2.log` must show `[mqtt] connected`; MQTT discovery prefix must match HA (`homeassistant`) |
| only sensors, no buttons/numbers | `"read_only": true` – intended until you verified the protocol |
| `mccctl.sh status` says NOT RUNNING after a reboot | expected: the host watchdog starts it within 2 minutes (cron entry present? `$STATE_DIR/.pause` left over?) |
| "PTY NOT bound" | the daemon failed to start – run `sh /data/mcc/run.sh` as root by hand and read the Python error (missing runtime, broken config JSON) |
| app shows no machine status / scale 0 while interpose runs | app opened the real node before the bind mount – `mccctl.sh start` again (it restarts the app after binding) |
| motor stops after ~2 s in a remote session | frames sent too slowly; `SEND_INTERVAL` must stay at 0.1 s; check CPU load / deep sleep (wakelock) |
| session starts with old values | values must be set (retained) before `start`; the preset scripts wait one second |
| overlay does not appear | `build/overlay.apk` not installed or `overlay_package` in `mcc.json` differs; test with `am startservice -n io.mccha.overlay/.OverlayService --es action SHOW` |
| overlay STOP has no effect | the daemon cannot see `files/estop`: package name mismatch, or the files directory does not exist yet (open the overlay once with SHOW) |
| MQTT availability flaps every ~1 min | deep sleep (enable `WAKELOCK=1`) or keepalive too short |
| garbage values (1000 °C, −2·10⁹ g), app in login state, scale −480 g | controller stuck – switch off at the mains switch (or let the power-cycle blueprint do it) |
| own recipes vanished | not deleted: app update reset `RECIPES_IMPORTED_TYPE` → `scripts/add-recipe-type.py` |
| own recipes deleted | recipe type was `default`/`live`/`beta` – use your own type and re-import |
| long words in recipe tiles break mid-word | app layout limitation – shorten the name |
| `adb: error: closed` for every shell command although `adb devices` lists the machine | adbd on the machine is in a bad state – toggle ADB/Wi-Fi debugging or power-cycle the machine |
| the whole machine rebooted after a kill command | you used `pidof` – see [operations.md](operations.md) |
