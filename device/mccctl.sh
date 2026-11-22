#!/system/bin/sh
# Start/stop the serial interpose on the machine (run as root):  sh /data/mcc/mccctl.sh start|stop|status
# Notes for this Android 6 / toybox environment:
#  - pkill -f does not work and `pidof <name>` returns ALL pids (killing them reboots the device),
#    so processes are found by grepping /proc/*/cmdline for "code/mcc_".
#  - Order matters: bind the PTY first, then restart the app, otherwise the app may open the real port first.
APP=de.silpion.mc2                 # stock cooking app (it is also the HOME launcher)
LOG=/data/local/tmp/mcc2.log
pids() { for p in /proc/[0-9]*; do grep -qa code/mcc_ "$p/cmdline" 2>/dev/null && echo "${p##*/}"; done; }
km() { for p in $(pids); do kill -9 "$p"; done; }
rst() { am force-stop $APP; sleep 1; umount -l /dev/ttyMT0 2>/dev/null; sleep 1
        [ -e /dev/ttyMT0_real ] && { rm -f /dev/ttyMT0; mv /dev/ttyMT0_real /dev/ttyMT0; }; }
launch() { monkey -p $APP -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; }
case "$1" in
 stop)  km; sleep 1; rst; launch; echo stopped;;
 start) km; sleep 1; rst
        mv /dev/ttyMT0 /dev/ttyMT0_real; : > $LOG
        setsid sh /data/mcc/run.sh >> $LOG 2>&1 &
        n=0; while [ $n -lt 100 ]; do grep -q " /dev/ttyMT0 " /proc/mounts && break; sleep 0.1; n=$((n+1)); done
        if grep -q " /dev/ttyMT0 " /proc/mounts; then echo "PTY bound after ${n}00 ms"
        else echo "PTY NOT bound - restoring original node"; km; rst; launch; exit 1; fi
        am force-stop $APP; sleep 1; launch; echo started;;
 status) r=$(pids); [ -n "$r" ] && echo "RUNNING $r" || echo "NOT RUNNING"; ls -l /dev/ttyMT0;;
 *) echo "usage: $0 start|stop|status"; exit 2;;
esac
