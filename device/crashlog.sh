#!/system/bin/sh
# Crash-safe logging on the machine (survives hangs and power loss because it is in flash):
#   logcat.txt*   Android log (main/system/crash/events), rotated 4 x 512 KB
#   dmesg.txt     kernel messages (dmesg -c, appended every minute), max. 2 x 2 MB
#   heartbeat.txt every minute: uptime, load, free RAM, CPU temperature, online cores, Wi-Fi address
# Started by host/mcc-watchdog.sh if it is not running.
D=/data/local/tmp/crashlog
mkdir -p $D
logcat -v time -b main -b system -b crash -b events -f $D/logcat.txt -r 512 -n 4 &
size() { toybox stat -c %s "$1" 2>/dev/null || echo 0; }
while true; do
  H=$D/heartbeat.txt; [ "$(size $H)" -gt 1048576 ] && mv $H $H.1
  K=$D/dmesg.txt;     [ "$(size $K)" -gt 2097152 ] && mv $K $K.1
  { echo "=== $(date '+%F %T') up $(cut -d' ' -f1 /proc/uptime) load $(cat /proc/loadavg)"
    grep MemAvailable /proc/meminfo
    echo "cpu $(cat /sys/class/thermal/thermal_zone0/temp) online $(cat /sys/devices/system/cpu/online)"
    ip -o -4 addr show wlan0 2>/dev/null | head -1; } >> $H
  dmesg -c >> $K 2>/dev/null
  sync
  sleep 60
done
