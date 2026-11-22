#!/bin/bash
# Removes the interpose from the machine and restores the original serial node.
#   scripts/uninstall.sh            stop + remove /data/mcc, overlay app, wakelock
#   scripts/uninstall.sh --keep     only stop the interpose (files stay)
# It does NOT unroot the machine and does not re-enable packages you disabled (see docs/operations.md).
set -euo pipefail
. "$(dirname "$0")/lib.sh"
adb_connect || { echo "machine not reachable via adb at $ADB_ADDR"; exit 1; }
touch "$STATE_DIR/.pause"
echo "watchdog paused ($STATE_DIR/.pause) - remove the cron entry, then delete that file"
su_ "[ -f /data/mcc/mccctl.sh ] && sh /data/mcc/mccctl.sh stop || true"
[ "${1:-}" = --keep ] && exit 0
OVL=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("overlay_package","io.mccha.overlay"))' \
      "$REPO/config/mcc.json" 2>/dev/null || echo io.mccha.overlay)
adb_ uninstall "$OVL" || true
su_ "echo mcc > /sys/power/wake_unlock 2>/dev/null; for p in /proc/[0-9]*; do grep -qa crashlog.s[h] \$p/cmdline 2>/dev/null && kill \${p##*/}; done; rm -rf /data/mcc /data/local/tmp/crashlog"
su_ "ls -l /dev/ttyMT0; grep ttyMT0 /proc/mounts || echo no bind mount left"
echo "removed. A full power cycle (mains switch) restores the MediaTek CPU hotplug default."
