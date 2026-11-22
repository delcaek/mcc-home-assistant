#!/bin/bash
# Installs / updates everything on the rooted machine over ADB.
#   scripts/deploy.sh              runtime + code + config + overlay APK (if built), then start the interpose
#   scripts/deploy.sh --code-only  only device/*.py|*.sh and mcc.json (fast update)
#   scripts/deploy.sh --no-start   do not (re)start the interpose afterwards
# Layout on the machine: /data/mcc/{rootfs,python,code,mcc.json,run.sh,mccctl.sh,crashlog.sh}
set -euo pipefail
. "$(dirname "$0")/lib.sh"
CODE_ONLY=0; START=1
for a in "$@"; do case $a in --code-only) CODE_ONLY=1;; --no-start) START=0;; *) echo "unknown option $a"; exit 2;; esac; done

[ -f "$REPO/config/mcc.json" ] || { echo "create config/mcc.json from config/mcc.example.json first"; exit 1; }
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$REPO/config/mcc.json"
adb_connect || { echo "machine not reachable via adb at $ADB_ADDR"; exit 1; }
su_ id | grep -q 'uid=0' || { echo "no root (su) on the machine - see docs/rooting.md"; exit 1; }

touch "$STATE_DIR/.pause"; trap 'rm -f "$STATE_DIR/.pause"' EXIT     # keep the host watchdog out of the way
TMP=/data/local/tmp/mcc-deploy                                        # adb shell (uid 2000) can only write here
adb_ shell "rm -rf $TMP; mkdir -p $TMP"

echo "== stopping interpose (if running)"
su_ "[ -f /data/mcc/mccctl.sh ] && sh /data/mcc/mccctl.sh stop || true"

if [ $CODE_ONLY = 0 ]; then
  [ -f "$REPO/build/mcc-runtime.tar" ] || { echo "run scripts/build-runtime.sh first"; exit 1; }
  echo "== uploading runtime (takes a while over Wi-Fi)"
  adb_ push "$REPO/build/mcc-runtime.tar" $TMP/ >/dev/null
  su_ "mkdir -p /data/mcc && cd /data/mcc && rm -rf rootfs python code/paho && tar -xf $TMP/mcc-runtime.tar && rm $TMP/mcc-runtime.tar && chmod 700 /data/mcc"
fi

echo "== uploading code and config"
for f in "$REPO"/device/*.py "$REPO"/device/*.sh "$REPO/config/mcc.json"; do adb_ push "$f" $TMP/ >/dev/null; done
su_ "mkdir -p /data/mcc/code && cp $TMP/*.py /data/mcc/code/ && cp $TMP/*.sh $TMP/mcc.json /data/mcc/ && chmod 755 /data/mcc/*.sh && chmod 600 /data/mcc/mcc.json && rm -rf $TMP"

if [ $CODE_ONLY = 0 ] && [ -f "$REPO/build/overlay.apk" ]; then
  echo "== installing e-stop overlay"
  adb_ install -r "$REPO/build/overlay.apk"
elif [ $CODE_ONLY = 0 ]; then
  echo "!! build/overlay.apk not found - remote control will work but without the on-screen STOP overlay (overlay/build.sh)"
fi

if [ $START = 1 ]; then
  echo "== starting interpose"
  su_ "sh /data/mcc/mccctl.sh start"
  sleep 6
  su_ "sh /data/mcc/mccctl.sh status; tail -5 /data/local/tmp/mcc2.log"
fi
echo "done. Log on the machine: /data/local/tmp/mcc2.log"
