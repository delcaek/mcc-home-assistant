# E-stop overlay and knob e-stop

## Overlay app (`overlay/`)

A tiny Android app (package `io.mccha.overlay`, no activity) with one service:

- `OverlayService` – full-screen system overlay shown while Home Assistant controls the machine: translucent
  black centre (the cooking UI shows through), opaque red/black striped frame, robot icon,
  **"REMOTE CONTROL ACTIVE"**, the remaining time ("4:59 left" / "no timer") and a large **STOP** button.
  It wakes the screen and beeps when it appears.

The daemon shows/hides it with `am startservice -n io.mccha.overlay/.OverlayService --es action SHOW|HIDE`.
Data is exchanged through files in the app's `files/` directory:

| file | written by | meaning |
|---|---|---|
| `estop` | app (STOP button) | daemon sees it within ~0.2 s, forces STOP, ends the session, returns control |
| `remaining` | daemon | seconds left, `-1` = no timer; polled every 0.5 s |

Files written by the daemon (root) get the owner and **SELinux label** of the app directory, otherwise the app
cannot read them (SELinux is enforcing). A stale `estop` file is deleted at the start of every session.

`targetSdkVersion 22` makes Android 6 grant `SYSTEM_ALERT_WINDOW` automatically; the overlay uses
`TYPE_SYSTEM_ERROR` so it stays above the kiosk-style stock app.

Build: `overlay/build.sh` (JDK 17, Android SDK platform 23, build-tools 34.0.0) or the Docker image in
`overlay/Dockerfile`. The APK is signed with a locally generated key (`build/overlay-debug.keystore`); keep it,
updates signed with another key need `adb uninstall io.mccha.overlay` first. After `adb install -r` the overlay
works immediately (it is started on demand, no autostart needed).

## Knob e-stop

The rotary knob does not go through the controller board, so the serial line never shows it. It is handled by a
kernel driver (`/dev/knob`, misc 10:35) read by the app. Its interrupts are counted in `/proc/interrupts` as
`knod-key` (press), `forward` and `backward` (turn). During a remote session the daemon samples these counters
every 0.2 s (summing all CPU columns – with several cores online the interrupt is not always on CPU0); any change
after the first second triggers the e-stop. Without this, turning the knob during a remote session would do
nothing, because the app's frames are suppressed then.

The input device `mtk-kpd` / `event0` stays silent for the knob on this machine – do not rely on `getevent`.
