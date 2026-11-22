#!/usr/bin/env python3
"""
mcc_ha.py - MQTT / Home Assistant integration for the MCC serial mux (entry point on the machine).

Adds to mcc_mux.py:
  - MQTT connection (paho-mqtt) to your broker, settings from mcc.json
  - Home Assistant MQTT discovery: entities appear under one device "Monsieur Cuisine Connect"
  - cooking "sessions": the serial protocol has no timer, so this daemon runs the timer itself,
    repeats the command (keepalive) and sends STOP at the end / on stop / lid open / e-stop.

Topics (<base> = "mqtt_base_topic", default "mcc"):
  state     (retained)  <base>/state           JSON from decode_rx
  available (retained)  <base>/avail           online | offline (last will)
  settings  (retained)  <base>/set/program     Standard | Knead | Sear | Steam
                        <base>/set/speed       0..10
                        <base>/set/temp        0..130 (rounded down to a controller level)
                        <base>/set/direction   Forward | Reverse
                        <base>/set/timer       minutes  } sum = run time,
                        <base>/set/timer_s     seconds  } 0 + 0 = run until stopped
  time left (retained)  <base>/remaining       seconds (0 = no timed session)
  command               <base>/cmd             start | stop | tare
"""
import json
import subprocess
import threading
import time

import paho.mqtt.client as mqtt

from mcc_mux import CFG, Mux, READ_ONLY, overlay_remaining

MQTT_HOST = CFG.get("mqtt_host", "homeassistant.local")
MQTT_PORT = int(CFG.get("mqtt_port", 1883))
MQTT_USER = CFG.get("mqtt_user", "")
MQTT_PASS = CFG.get("mqtt_password", "")
BASE = CFG.get("mqtt_base_topic", "mcc")
DISCOVERY = CFG.get("discovery_prefix", "homeassistant")
DEVICE_ID = CFG.get("device_id", "mcc_skmc1200")      # also used by host/mcc-watchdog.sh and host/mcc-screen.py

# HA option -> protocol operation
PROGRAMS = {"Standard": "STANDARD", "Knead": "KNEAD", "Sear": "TOAST", "Steam": "STEAM"}
DIRECTIONS = ["Forward", "Reverse"]                    # Reverse = counter-clockwise ("gentle stir")

RESEND_S = 1.0          # keepalive interval of the session thread (must be < watchdog_s)
DEV = {
    "identifiers": [DEVICE_ID],
    "name": CFG.get("device_name", "Monsieur Cuisine Connect"),
    "manufacturer": "Lidl / SilverCrest",
    "model": "SKMC 1200",
}


def discovery(client):
    def pub(comp, oid, cfg):
        cfg.update({"device": DEV, "unique_id": "%s_%s" % (DEVICE_ID, oid),
                    "default_entity_id": "%s.mcc_%s" % (comp, oid),
                    "availability_topic": BASE + "/avail"})
        client.publish("%s/%s/%s/%s/config" % (DISCOVERY, comp, DEVICE_ID, oid), json.dumps(cfg), retain=True)

    st = BASE + "/state"
    temp = {"unit_of_measurement": "°C", "device_class": "temperature", "state_class": "measurement"}
    pub("sensor", "actual_temperature", dict(temp, name="Actual temperature", state_topic=st,
        value_template="{{ value_json.temp_actual_c }}"))
    pub("sensor", "target_temperature", dict(temp, name="Target temperature", state_topic=st,
        value_template="{{ value_json.target_temp_c }}"))
    pub("sensor", "heater_temperature", dict(temp, name="Heating element temperature", state_topic=st,
        value_template="{{ value_json.heater_temp_c }}"))
    pub("sensor", "weight", {"name": "Weight", "state_topic": st, "unit_of_measurement": "g",
        "device_class": "weight", "value_template": "{{ value_json.weight_g }}"})
    pub("sensor", "speed", {"name": "Speed", "state_topic": st, "icon": "mdi:fan",
        "value_template": "{{ value_json.speed_target }}"})
    pub("sensor", "target_rpm", {"name": "Target RPM", "state_topic": st, "unit_of_measurement": "rpm",
        "value_template": "{{ value_json.rpm_target }}"})
    for oid, name, cls, key in (("running", "Running", "running", "running"),
                                ("lid_open", "Lid open", "opening", "lid_open"),
                                ("error", "Error", "problem", "error")):
        pub("binary_sensor", oid, {"name": name, "state_topic": st, "device_class": cls,
            "payload_on": "true", "payload_off": "false",
            "value_template": "{{ value_json.%s | lower }}" % key})

    if READ_ONLY:
        return   # no control entities in read-only mode (no dead buttons in HA)

    s = BASE + "/set/"
    pub("number", "speed", {"name": "Speed setting", "command_topic": s + "speed", "state_topic": s + "speed",
        "min": 0, "max": 10, "step": 1, "icon": "mdi:fan"})
    pub("number", "target_temperature", {"name": "Temperature setting", "command_topic": s + "temp",
        "state_topic": s + "temp", "min": 0, "max": 130, "step": 5, "unit_of_measurement": "°C"})
    pub("number", "timer_minutes", {"name": "Timer minutes", "command_topic": s + "timer",
        "state_topic": s + "timer", "min": 0, "max": 90, "step": 1, "unit_of_measurement": "min"})
    pub("number", "timer_seconds", {"name": "Timer seconds", "command_topic": s + "timer_s",
        "state_topic": s + "timer_s", "min": 0, "max": 59, "step": 1, "unit_of_measurement": "s"})
    pub("sensor", "time_left", {"name": "Time left", "state_topic": BASE + "/remaining",
        "unit_of_measurement": "s", "device_class": "duration"})
    pub("select", "program", {"name": "Program", "command_topic": s + "program", "state_topic": s + "program",
        "options": list(PROGRAMS)})
    pub("select", "direction", {"name": "Direction", "command_topic": s + "direction",
        "state_topic": s + "direction", "options": DIRECTIONS})
    for oid, name in (("start", "Start"), ("stop", "Stop"), ("tare", "Tare")):
        pub("button", oid, {"name": name, "command_topic": BASE + "/cmd", "payload_press": oid})


class MccHa:
    def __init__(self, mux: Mux):
        self.mux = mux
        self.set = {"program": "Standard", "speed": 0, "temp": 0,
                    "direction": "Forward", "timer": 0, "timer_s": 0}
        self.session = None
        self._stop = threading.Event()
        try:
            self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError:          # paho-mqtt < 2.0
            self.c = mqtt.Client()
        if MQTT_USER:
            self.c.username_pw_set(MQTT_USER, MQTT_PASS)
        self.c.will_set(BASE + "/avail", "offline", retain=True)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.on_disconnect = self._on_disconnect

    def start(self):
        # keepalive 60 s: with 30 s the first PINGREQ sometimes came after ~37 s and the broker dropped us
        self.c.connect_async(MQTT_HOST, MQTT_PORT, 60)
        self.c.loop_start()
        self.mux._publish = lambda s: self.c.publish(BASE + "/state", json.dumps(s), retain=True)

    def _on_connect(self, c, *_):
        print("%s [mqtt] connected" % time.strftime("%H:%M:%S"), flush=True)
        c.publish(BASE + "/avail", "online", retain=True)
        discovery(c)
        if READ_ONLY:
            return
        for t in ("program", "speed", "temp", "direction", "timer", "timer_s"):
            c.subscribe("%s/set/%s" % (BASE, t))
        c.subscribe(BASE + "/cmd")

    def _on_disconnect(self, c, u, rc):
        print("%s [mqtt] disconnected rc=%s" % (time.strftime("%H:%M:%S"), rc), flush=True)

    def _on_message(self, c, u, msg):
        p = msg.payload.decode(errors="replace")
        t = msg.topic.rsplit("/", 1)[-1]
        if msg.topic.startswith(BASE + "/set/"):
            try:
                self.set[t] = int(float(p)) if t in ("speed", "temp", "timer", "timer_s") else p
            except ValueError:
                print("[ha ] ignored %s=%r" % (msg.topic, p), flush=True)
        elif msg.topic == BASE + "/cmd" and not msg.retain:     # never act on a stale retained command
            {"start": self._start_session,
             "stop": self._stop_session,
             "tare": lambda: threading.Thread(target=self._tare, daemon=True).start(),
             }.get(p, lambda: None)()

    def _tare(self):
        # tare needs the line: take over for ~1 s while idle (no overlay), then hand back to the app.
        # Ignored during a cooking session (it would replace the session's command).
        if self.session and self.session.is_alive():
            print("[ha ] tare ignored during session", flush=True)
            return
        self.mux.silent = True
        try:
            self.mux.command(operation="STOP", tare=True)
            self.mux.control = True
            time.sleep(1.0)
            self.mux.stop()
            time.sleep(0.3)
        finally:
            self.mux.control = False
            self.mux.silent = False

    # ------------------------------------------------------------- session with timer
    def _start_session(self):
        self._stop_session()
        self.mux.clear_estop()
        self._stop.clear()
        self.session = threading.Thread(target=self._run_session, daemon=True)
        self.session.start()

    def _stop_session(self):
        self._stop.set()
        self.mux.stop()          # the session thread hands control back cleanly

    def _run_session(self):
        s = self.set
        op = PROGRAMS.get(s["program"], "STANDARD")
        ccw = s["direction"] == "Reverse"
        duration = s["timer"] * 60 + s["timer_s"]
        end = time.time() + duration if duration else None
        self.mux.command(operation=op, speed=s["speed"], temp_c=s["temp"], ccw=ccw)   # first command BEFORE takeover
        overlay_remaining(duration if duration else -1)
        self.mux.control = True                                                       # now suppress the app
        try:
            while not self._stop.is_set():
                st = self.mux.last_state
                if self.mux._estop or st.get("lid_open") or st.get("error"):
                    break
                if end:
                    rest = end - time.time()
                    self.c.publish(BASE + "/remaining", str(max(0, round(rest))), retain=True)
                    overlay_remaining(max(0, round(rest)))
                    if rest <= 0:
                        break
                self.mux.command(operation=op, speed=s["speed"], temp_c=s["temp"], ccw=ccw)
                time.sleep(min(RESEND_S, max(0.05, end - time.time())) if end else RESEND_S)
        finally:
            self.c.publish(BASE + "/remaining", "0", retain=True)
            overlay_remaining(None)
            self.mux.stop()
            time.sleep(1.0)              # flush STOP frames to the controller
            self.mux.control = False     # the app owns the line again


if __name__ == "__main__":
    mux = Mux()
    ha = MccHa(mux)
    ha.start()
    mux.run()
