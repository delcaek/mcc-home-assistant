#!/bin/bash
# Host-side watchdog (cron, every 2 minutes). Replaces boot scripts: on the tested machine Magisk ran
# no boot scripts at all (post-fs-data.d, module scripts, service.d), so a host restarts the interpose instead.
# Each run:
#   1. publishes the ADB state to MQTT (binary_sensor.mcc_adb_connection, used by the power-cycle blueprint)
#   2. keeps all CPU cores online, holds a kernel wakelock, keeps device/crashlog.sh running (see config.env)
#   3. starts the interpose (mccctl.sh start) if it is not running
# Pause it during manual work:  touch "$STATE_DIR/.pause"
#   crontab -e:  */2 * * * * /path/to/repo/host/mcc-watchdog.sh
. "$(dirname "$0")/../scripts/lib.sh"
LOG="$STATE_DIR/watchdog.log"
ts() { date '+%F %T'; }
B=${MQTT_BASE_TOPIC:-mcc}; D=${DEVICE_ID:-mcc_skmc1200}

adbstate=offline; adb_connect && adbstate=online
# get-state can report "device" while every shell fails with "error: closed" (seen for two days on the
# tested setup). Check a real shell; if it fails, restart the local adb server once, otherwise report offline
# so the power-cycle blueprint can step in.
shell_ok() { [ "$(timeout 15 $ADB -s "$ADB_ADDR" shell echo ok 2>/dev/null | tr -d '\r')" = ok ]; }
if [ "$adbstate" = online ] && ! shell_ok; then
  echo "$(ts) adb shell fails -> restarting adb server" >> "$LOG"
  $ADB kill-server >/dev/null 2>&1; adb_connect; sleep 2
  shell_ok || { adbstate=offline; echo "$(ts) adb shell still failing -> reporting offline" >> "$LOG"; }
fi
# expire_after 600: if this watchdog stops running, the sensor becomes unavailable instead of "off"
DISC="$STATE_DIR/.adb-discovery-v1"
[ -e "$DISC" ] || mqtt_pub "${DISCOVERY_PREFIX:-homeassistant}/binary_sensor/$D/adb/config" \
  "{\"name\":\"ADB connection\",\"unique_id\":\"${D}_adb\",\"default_entity_id\":\"binary_sensor.mcc_adb_connection\",\"state_topic\":\"$B/adb\",\"payload_on\":\"online\",\"payload_off\":\"offline\",\"device_class\":\"connectivity\",\"entity_category\":\"diagnostic\",\"expire_after\":600,\"device\":{\"identifiers\":[\"$D\"]}}" \
  >/dev/null 2>&1 && touch "$DISC"
mqtt_pub "$B/adb" "$adbstate" >/dev/null 2>&1
[ "$adbstate" = online ] || exit 0
[ -e "$STATE_DIR/.pause" ] && exit 0

# MediaTek hotplug keeps only cpu0 online (sluggish UI); value resets on every boot
[ "${KEEP_ALL_CORES:-1}" = 1 ] && su_ "grep -q ^4 /proc/hps/num_base_perf_serv || echo 4 > /proc/hps/num_base_perf_serv" >/dev/null 2>&1
# prevent deep sleep (suspend freezes the daemon -> MQTT timeouts); the screen still turns off
[ "${WAKELOCK:-1}" = 1 ] && su_ "grep -qw mcc /sys/power/wake_lock || echo mcc > /sys/power/wake_lock" >/dev/null 2>&1
# crash-safe log; found via cmdline (never pidof on this device). Pattern "crashlog.s[h]" and the split path keep
# the checking shell from matching itself.
[ "${CRASHLOG:-1}" = 1 ] && su_ "S=/data/mcc/crash; for p in /proc/[0-9]*; do grep -qa crashlog.s[h] \$p/cmdline 2>/dev/null && exit 0; done; setsid sh \${S}log.sh >/dev/null 2>&1 &" >/dev/null 2>&1

su_ "sh /data/mcc/mccctl.sh status" 2>/dev/null | grep -q RUNNING && exit 0
echo "$(ts) interpose not running -> starting" >> "$LOG"
su_ "sh /data/mcc/mccctl.sh start" >> "$LOG" 2>&1
