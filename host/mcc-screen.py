#!/usr/bin/env python3
"""Screen of the Monsieur Cuisine Connect as a Home Assistant camera (MQTT discovery, image topic <base>/screen).

Runs on the host (systemd unit host/systemd/mcc-screen.service). Takes screenshots with `adb exec-out screencap -p`
(~1.7 s on the MT6580):
  - machine running (from the retained <base>/state): every SCREEN_RUNNING_S seconds
  - otherwise only while the display is on: every SCREEN_IDLE_S seconds
  - display off: no new image (the last one stays)
Settings come from config/config.env (or the file named in $MCC_ENV). Needs adb and mosquitto clients."""
import json
import os
import shlex
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.environ.get("MCC_ENV", os.path.join(REPO, "config", "config.env"))


def load_env(path):
    """Evaluate the shell-style config with bash so $HOME etc. expand exactly like in the scripts."""
    out = subprocess.run(["bash", "-c", 'set -a; . "$1"; env -0', "_", path], capture_output=True, check=True)
    return dict(kv.split("=", 1) for kv in out.stdout.decode().split("\0") if "=" in kv)


C = load_env(ENV)
ADB = shlex.split(C.get("ADB", "adb"))
ADDR = C["ADB_ADDR"]
BASE = C.get("MQTT_BASE_TOPIC", "mcc")
DEV_ID = C.get("DEVICE_ID", "mcc_skmc1200")
RUN_S = int(C.get("SCREEN_RUNNING_S", 5))
IDLE_S = int(C.get("SCREEN_IDLE_S", 60))
MQ = ["-h", C["MQTT_HOST"], "-p", C.get("MQTT_PORT", "1883")]
if C.get("MQTT_USER"):
    MQ += ["-u", C["MQTT_USER"], "-P", C.get("MQTT_PASSWORD", "")]
PUB = shlex.split(C.get("MOSQUITTO_PUB", "mosquitto_pub")) + MQ
SUB = shlex.split(C.get("MOSQUITTO_SUB", "mosquitto_sub")) + MQ


def mqtt(topic, payload: bytes):
    subprocess.run(PUB + ["-r", "-t", topic, "-s"], input=payload, capture_output=True, timeout=30)


def adb(*args, timeout=20):
    return subprocess.run(ADB + ["-s", ADDR, *args], capture_output=True, timeout=timeout)


def running():
    try:
        r = subprocess.run(SUB + ["-t", BASE + "/state", "-C", "1", "-W", "3"], capture_output=True, timeout=10)
        return bool(json.loads(r.stdout or b"{}").get("running"))
    except Exception:
        return False


def display_on():
    return b"Awake" in adb("shell", "dumpsys power | grep mWakefulness=").stdout


mqtt("%s/camera/%s/screen/config" % (C.get("DISCOVERY_PREFIX", "homeassistant"), DEV_ID), json.dumps({
    "name": "Display", "unique_id": DEV_ID + "_screen", "default_entity_id": "camera.mcc_display",
    "topic": BASE + "/screen", "icon": "mdi:tablet-dashboard", "device": {"identifiers": [DEV_ID]}}).encode())

while True:
    pause = IDLE_S
    try:
        subprocess.run(ADB + ["connect", ADDR], capture_output=True, timeout=10)
        if running():
            pause = RUN_S
        if pause == RUN_S or display_on():
            png = adb("exec-out", "screencap", "-p").stdout
            if png.startswith(b"\x89PNG"):
                mqtt(BASE + "/screen", png)
    except Exception as e:
        print("error:", e, file=sys.stderr, flush=True)
    time.sleep(pause)
