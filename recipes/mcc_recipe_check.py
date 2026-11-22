"""Checks recipe JSON files against the rules in docs/recipes.md before they are inserted.

    python3 -I recipes/mcc_recipe_check.py recipes/examples/*.json
"""
import json
import sys

TEMPS = {0, 37} | set(range(40, 131, 5))
NUTRIENTS = ["joules", "calories", "protein", "carbohydrate", "fat"]
RESERVED_TYPES = {"default", "live", "beta"}          # deleted by the app's server sync


def check(path):
    err = []
    r = json.load(open(path, encoding="utf-8"))
    for k in ("id", "name", "complexity", "level", "duration", "duration_total", "yield", "image_name",
              "tags", "nutrients", "ingredients", "instructions", "steps"):
        if k not in r:
            err.append("missing field: " + k)
    if err:
        return r, err
    if r.get("recipe_type", "custom") in RESERVED_TYPES:
        err.append("recipe_type must not be default/live/beta (the app deletes those)")
    if r["level"] not in (1, 2, 3):
        err.append("level must be 1, 2 or 3")
    if not (0 < r["duration"] <= r["duration_total"]):
        err.append("duration must be > 0 and <= duration_total")
    if not r["image_name"]:
        err.append("image_name is empty")
    if [n[0] for n in r["nutrients"]] != NUTRIENTS or not all(str(n[2]).isdigit() for n in r["nutrients"]):
        err.append("nutrients: need joules, calories, protein, carbohydrate, fat (whole numbers as strings)")
    for i in r["ingredients"]:
        if len(i) != 3 or not all(isinstance(x, str) for x in i) or not i[2]:
            err.append("ingredient: %s" % i)
    for n, s in enumerate(r["steps"], 1):
        m = s.get("mode")
        if m == "instruction":
            ok = bool(s.get("text")) and set(s) <= {"mode", "text"}
        elif m == "scale":
            ok = isinstance(s.get("weight"), int) and s["weight"] > 0 and bool(s.get("text"))
        elif m == "cooking":
            ok = (1 <= s.get("speed", 0) <= 10 and s.get("temp", 0) in TEMPS and 0 < s.get("time", 0) <= 5940
                  and s.get("reverse", 0) in (0, 1) and not s.get("text"))
        elif m == "turbo":
            ok = 1 <= s.get("time", 0) <= 12
        elif m == "roasting":
            ok = s.get("temp") in (100, 110, 115, 120, 130) and 0 < s.get("time", 0) <= 840
        elif m == "steaming":
            ok = 0 < s.get("time", 0) <= 3600
        elif m == "kneading":
            ok = 0 < s.get("time", 0) <= 300
        else:
            ok = False
        if not ok:
            err.append("step %d: %s" % (n, s))
    if not any(s["mode"] not in ("instruction", "scale") for s in r["steps"]):
        err.append("no machine step")
    return r, err


bad = 0
ids = {}
for p in sys.argv[1:]:
    r, e = check(p)
    if r.get("id") in ids:
        e.append("duplicate id with %s" % ids[r["id"]])
    ids[r.get("id")] = p
    machine = sum(s.get("mode") not in ("instruction", "scale") for s in r.get("steps", []))
    print(("OK    " if not e else "ERROR ") + "%s %s - %d steps, %d machine steps"
          % (r.get("id"), r.get("name"), len(r.get("steps", [])), machine))
    for x in e:
        print("      ", x)
    bad += bool(e)
sys.exit(1 if bad else 0)
