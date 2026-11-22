# Rooting and ADB over Wi-Fi

This repository does **not** contain any boot images, recovery images, flashing tools or Magisk binaries.
Follow the upstream guides and get the tools from their official sources:

- Rooting guide: [Wuki60/MrCuisineVibeConnect](https://github.com/Wuki60/MrCuisineVibeConnect) – `docs/INSTALLATION.md`
  (SP Flash Tool, TWRP recovery, Magisk boot image patch)
- TWRP recovery image for this device: from the Monsieur Cuisine Connect repository of
  [EliasKotlyar](https://github.com/EliasKotlyar) as referenced in the guide above
- [Magisk](https://github.com/topjohnwu/Magisk) (tested: v31.0)
- SP Flash Tool (tested: v5.1924) – MediaTek flashing tool, use a trustworthy source

## What we did differently from the upstream guide

1. **Only root + ADB over Wi-Fi.** Read back and keep `boot-original.img` and `recovery-original.img` first,
   then patch the boot image with Magisk and flash it, keep the stock ROM.
2. **Do NOT run the guide's "install" step** of the upstream project. It disables the stock motor/machine service
   of the app; afterwards neither the app nor this project can control the machine.
3. Use only the **right USB port ("Android USB")**. The left one (3.3 V) destroys the board.

## After rooting

- Enable ADB over TCP (port 5555) as described in the guide and give the machine a **fixed DHCP lease**.
- Authorise your host's ADB key once (`adb connect <ip>:5555`, accept the prompt on the screen).
- In Magisk, allow root for the shell (uid 2000). Optional: disable the superuser toast/notification for the
  shell, otherwise a toast appears every time the watchdog runs (Magisk → Superuser → Shell).
- Check: `adb -s <ip>:5555 shell "su -c id"` must print `uid=0(root)`.

## Optional hardening of the stock system (all reversible with `pm enable`)

Done on the tested machine, not required by this project – see [operations.md](operations.md):

- `pm disable de.silpion.mcupdater` – the stock updater (an app update may change the protocol or wipe custom
  recipe settings)
- disabling the FOTA client and unused stock apps to free RAM/CPU
