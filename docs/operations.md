# Operations – lessons learned on this Android 6 / toybox system

## Processes

- **Never use `pidof <name>` on the machine.** toybox `pidof` returned *all* PIDs; `kill -9 $(pidof …)` killed
  everything and the machine rebooted. Find processes by grepping `/proc/*/cmdline` (as `mccctl.sh` does) and
  make sure the pattern does not match your own shell (e.g. `crashlog.s[h]`).
- `pkill -f` does not work (toybox). `comm` of our Python shows `ld-linux-armhf.` (started through the loader).
- `adb shell` runs as uid 2000: push files to `/data/local/tmp` first, then copy them as root (`su -c cp …`).
- toybox `tar` has no gzip – transfer uncompressed tar files (that is why `mcc-runtime.tar` is not compressed).

## Editing the app's shared preferences

`/data/data/de.silpion.mc2/shared_prefs/PREFERENCES_MC2.xml` – be careful:

1. Never edit it with `sed`/quoting inside `adb shell`. One attempt wrote a NUL byte into the file; the app then
   reset *all* preferences (login, language, privacy settings).
2. The app is the HOME launcher and restarts immediately after `am force-stop`; a fresh process may already have
   loaded the old file and writes it back later.

Proven procedure: build and validate the new file on the host, push it to `/data/local/tmp`, then as root
`am force-stop de.silpion.mc2; cat new.xml > PREFERENCES_MC2.xml; am force-stop de.silpion.mc2`
(force-stop twice) and check the content afterwards. `scripts/add-recipe-type.py` follows this procedure.

## Terms-of-use dialog after every restart

After each `mccctl.sh start` the app showed its "terms of use" dialog again, because the background process
`de.silpion.mc2:mc.machine_service` kept writing back its old copy of the preferences
(`KEY_ACCEPTED_TERMS_OF_USE_VERSION` stayed 0). Setting that key to the current version with the procedure above
fixed it on the tested unit. Do not click through such dialogs remotely on behalf of other users.

## Deep sleep and MQTT drops

Android suspended the SoC for long periods (24 of 79 minutes in one measurement). The daemon froze, heartbeats
stopped and the broker dropped the connection repeatedly. A kernel wakelock (`echo mcc > /sys/power/wake_lock`,
set idempotently by the watchdog because it is lost at reboot) stopped this completely; the display still turns
off. Extra consumption is estimated at 0.3–0.5 W. Disabling Wi-Fi power save did not work on this device
(`wpa_cli DRIVER POWERMODE` timed out); ping times of up to ~200 ms remain but do not matter for MQTT.
MQTT keepalive is 60 s – with 30 s the first PINGREQ sometimes arrived only after ~37 s.

## CPU cores (MediaTek hotplug)

The MT6580 has 4 cores but the MediaTek hotplug kept only cpu0 online, so the UI and recipe search were sluggish.
`echo 4 > /proc/hps/num_base_perf_serv` keeps all four online; it resets on reboot, so the watchdog sets it.
1 GB RAM is not a bottleneck (~600 MB free). A load average around 9 is normal (MediaTek kernel threads in D
state, e.g. the knob driver's `knob_thread_kth`).

## Stuck controller after an Android-only restart

After `adb reboot` (Android only) the app once hung in its login state (TX op `0x0F`, byte 12 = 1), the scale
showed −480 g and some garbage frames arrived. **Switching the machine off at the mains switch** (board and
Android together) fixed it. `adb reboot` does not reset the controller. The power-cycle blueprint uses a smart
plug for the same reason.

## Updates and unused stock apps (optional, all reversible with `pm enable <package>`)

On the tested machine (with the owner's consent):

- `pm disable de.silpion.mcupdater` – stock updater. Whether the cooking app updates itself through another path
  is unknown.
- disabled to save RAM/CPU: `com.adups.tgifota` (FOTA), `com.vdiscovery.uploadexceptionapp` (also needed
  `pm hide`, it restarted otherwise), `com.example.endurancetest`, calendar apps and providers, deskclock,
  gallery3d, browser, exchange, live wallpapers and dreams.
- **Do not disable** thermalmanager, the keyboard (`inputmethod.latin`), WebView, settings, systemui or
  `providers.*`.

## Updating the code

`scripts/deploy.sh --code-only` (it pauses the host watchdog during the update via `$STATE_DIR/.pause`).
Manual work on the machine: `touch $STATE_DIR/.pause` first, otherwise the watchdog may restart the interpose
in the middle of your work; delete the file afterwards.

## Logs

- `/data/local/tmp/mcc2.log` – daemon: frames (`[app>]`, `[app-x]`, `[rx>]`, `[we>]`), MQTT, e-stop
- `/data/local/tmp/crashlog/` – logcat, dmesg and heartbeat, survives crashes and power loss
- `$STATE_DIR/watchdog.log` on the host – watchdog restarts
- Screenshots: `adb exec-out screencap -p > screen.png`
