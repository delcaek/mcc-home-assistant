#!/usr/bin/env python3
"""Generates a Home Assistant dashboard (sections view, built-in cards only) for the MCC.

    python3 homeassistant/dashboard/gen_dashboard.py [--power sensor.x_power] [--energy sensor.x_energy] [-o file]

Writes mcc-dashboard.yaml (default). In Home Assistant: Settings -> Dashboards -> Add dashboard -> open it ->
three dots -> Edit dashboard -> three dots -> Raw configuration editor -> paste the file content.
Entity ids follow the default_entity_id values published by device/mcc_ha.py (sensor.mcc_*, button.mcc_* ...).
The preset tiles expect the scripts from homeassistant/scripts.yaml.
"""
import argparse
import json

ap = argparse.ArgumentParser()
ap.add_argument("--power", help="power sensor of a smart plug the machine is connected to (optional)")
ap.add_argument("--energy", help="energy sensor of that plug (optional)")
ap.add_argument("-o", "--output", default="mcc-dashboard.yaml")
args = ap.parse_args()

S, B = "sensor.mcc_", "binary_sensor.mcc_"


def tile(e, name, icon=None, cols=6, **kw):
    c = {"type": "tile", "entity": e, "name": name, "grid_options": {"columns": cols}}
    if icon:
        c["icon"] = icon
    c.update(kw)
    return c


def press(e, name, icon, color, confirm=None, cols=4):
    act = {"action": "perform-action", "perform_action": "button.press", "target": {"entity_id": e}}
    if confirm:
        act["confirmation"] = {"text": confirm}
    return tile(e, name, icon, cols, color=color, hide_state=True, vertical=True,
                tap_action=act, icon_tap_action=act, hold_action={"action": "none"})


def alert(e, text, icon):
    return tile(e, text, icon, 12, color="red", visibility=[{"condition": "state", "entity": e, "state": "on"}])


def preset(script, name, icon, info):
    act = {"action": "perform-action", "perform_action": "script.turn_on", "target": {"entity_id": script},
           "confirmation": {"text": "Start %s? (%s) Lid closed, bowl inserted?" % (name, info)}}
    return tile(script, name, icon, 6, color="green", hide_state=True, tap_action=act, icon_tap_action=act,
                hold_action={"action": "more-info"})


def numeric(e, name, icon, cols=12, pos="inline"):
    return tile(e, name, icon, cols, features=[{"type": "numeric-input", "style": "buttons"}], features_position=pos)


status = [
    {"type": "heading", "heading": "Status", "heading_style": "title", "icon": "mdi:pot-steam-outline",
     "badges": [{"type": "entity", "entity": B + "running", "show_name": True, "name": "Running", "color": "amber"}]},
    alert(B + "lid_open", "Lid open - operation blocked", "mdi:pot-outline"),
    alert(B + "error", "Error reported", "mdi:alert-circle"),
    tile(S + "actual_temperature", "Content", "mdi:thermometer", 4, color="deep-orange", vertical=True),
    tile(S + "heater_temperature", "Heater", "mdi:heat-wave", 4, color="red", vertical=True),
    tile(S + "target_temperature", "Target", "mdi:thermometer-check", 4, vertical=True),
    tile(S + "speed", "Speed", "mdi:fan", 4, vertical=True),
    # the machine only reports the target rpm, and it keeps its last value after stopping -> show only while running
    tile(B + "lid_open", "Lid", "mdi:pot-outline", 4, vertical=True,
         visibility=[{"condition": "state", "entity": B + "running", "state_not": "on"}]),
    tile(S + "target_rpm", "Target RPM", "mdi:rotate-right", 4, vertical=True,
         visibility=[{"condition": "state", "entity": B + "running", "state": "on"}]),
    tile(S + "weight", "Scale", "mdi:scale", 4, color="teal", vertical=True),
    tile(S + "time_left", "Time left", "mdi:timer-sand", 12, color="amber",
         visibility=[{"condition": "numeric_state", "entity": S + "time_left", "above": 0}]),
]
if args.power:
    status.append(tile(args.power, "Power", "mdi:flash", 6, color="yellow"))
if args.energy:
    status.append(tile(args.energy, "Energy", "mdi:lightning-bolt", 6, color="yellow"))

control = [
    {"type": "heading", "heading": "Control", "heading_style": "title", "icon": "mdi:tune-variant"},
    tile("select.mcc_program", "Program", "mdi:chef-hat", 12,
         features=[{"type": "select-options"}], features_position="inline"),
    numeric("number.mcc_speed", "Speed", "mdi:fan"),
    numeric("number.mcc_target_temperature", "Temperature", "mdi:thermometer"),
    numeric("number.mcc_timer_minutes", "Minutes", "mdi:timer-outline", 6, "bottom"),
    numeric("number.mcc_timer_seconds", "Seconds", "mdi:timer-sand", 6, "bottom"),
    tile("select.mcc_direction", "Direction", "mdi:rotate-left", 12,
         features=[{"type": "select-options"}], features_position="inline"),
    press("button.mcc_start", "Start", "mdi:play", "green",
          confirm="Start the Monsieur Cuisine now? Lid closed, bowl inserted?"),
    press("button.mcc_stop", "Stop", "mdi:stop", "red"),
    press("button.mcc_tare", "Tare", "mdi:scale-balance", "teal"),
]

presets = [
    {"type": "heading", "heading": "Presets", "heading_style": "title", "icon": "mdi:lightning-bolt"},
    preset("script.mcc_chop", "Chop", "mdi:knife", "speed 5, 5 s"),
    preset("script.mcc_puree", "Purée", "mdi:blender", "speed 8, 30 s"),
    preset("script.mcc_saute", "Sauté", "mdi:pot-steam", "120 °C, speed 1 reverse, 3 min"),
    preset("script.mcc_keep_warm", "Keep warm", "mdi:thermometer-low", "60 °C, speed 1 reverse, 30 min"),
]

display = [
    {"type": "heading", "heading": "Display", "heading_style": "title", "icon": "mdi:tablet-dashboard"},
    {"type": "picture-entity", "entity": "camera.mcc_display", "camera_view": "auto", "show_name": False,
     "show_state": False, "tap_action": {"action": "more-info"}, "grid_options": {"columns": 12}},
]

graph = lambda ents: {"type": "history-graph", "hours_to_show": 2, "grid_options": {"columns": 12},
                      "entities": [{"entity": e, "name": n} for e, n in ents]}
history = [
    {"type": "heading", "heading": "History", "heading_style": "title", "icon": "mdi:chart-line"},
    graph([(S + "actual_temperature", "Content"), (S + "heater_temperature", "Heater"),
           (S + "target_temperature", "Target")]),
    graph([(S + "speed", "Speed"), (B + "running", "Running"), (B + "lid_open", "Lid open")]),
]
if args.power:
    history.append(graph([(args.power, "Power")]))

view = {"title": "Kitchen machine", "path": "mcc", "type": "sections", "max_columns": 4,
        "sections": [{"type": "grid", "cards": c} for c in (status, control, presets, display, history)]}
cfg = {"title": "Kitchen machine", "views": [view]}
with open(args.output, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)   # JSON is valid YAML for the raw editor
print("written", args.output)
