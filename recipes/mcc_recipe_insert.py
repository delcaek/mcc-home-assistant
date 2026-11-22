"""Insert one recipe into the recipe database of the MCC stock app (package de.silpion.mc2).

Runs ON THE MACHINE with the bundled Python from /data/mcc (as root); push-recipes.sh does that for you:
    mcc_recipe_insert.py <recipe.json> [<database>]
An existing recipe with the same id is removed first (idempotent). JSON format: see docs/recipes.md.

RECIPE_TYPE must not be one of the app's own types (default/live/beta): on every start the app deletes recipes of
those types that its server does not know. The type you use must be listed in the app preference
RECIPES_IMPORTED_TYPE, otherwise the recipes stay invisible (scripts/add-recipe-type.py).
"""
import json
import sqlite3
import sys
import time

DB = sys.argv[2] if len(sys.argv) > 2 else "/data/data/de.silpion.mc2/databases/Recipes"


def delete_recipe(c, rid):
    for led, mv, ms in c.execute("select LED_ID, MACHINE_VALUES_ID, MEASUREMENT_ID from STEP where RECIPE_ID=?",
                                 (rid,)).fetchall():
        c.execute("delete from LED where _id=?", (led,))
        c.execute("delete from MACHINE_VALUES where _id=?", (mv,))
        c.execute("delete from MEASUREMENT where _id=?", (ms,))
    c.execute("delete from STEP where RECIPE_ID=?", (rid,))
    for (bid,) in c.execute("select _id from INGREDIENTS_BASE where RECIPE_ID=?", (rid,)).fetchall():
        c.execute("delete from INGREDIENT where INGREDIENTS_BASE_ID=?", (bid,))
    c.execute("delete from INGREDIENTS_BASE where RECIPE_ID=?", (rid,))
    c.execute("delete from NUTRIENT where RECIPE_ID=?", (rid,))
    c.execute("delete from TAG where RECIPE_ID=?", (rid,))
    c.execute("delete from RECIPE where _id=?", (rid,))


def insert_recipe(c, r):
    rid = r["id"]
    c.execute(
        "insert into RECIPE (_id, COMPLEXITY, DURATION, DURATION_TOTAL, IMAGE_BASE, IMAGE_NAME, RECIPE_TYPE,"
        " INSTRUCTIONS, IS_FAVORITE, LANGUAGE, LEVEL, MACHINE_TYPE, MACHINE_VERSION, NAME, PREPARATIONS,"
        " SCHEME_VERSION, UNIT, UPDATED, VALID_FROM, VALID_TO, VERSION, YIELD, YIELD_UNIT)"
        " values (?,?,?,?,?,?,?,?,0,?,?,'mc2',2.0,?,'',1,?,?,NULL,NULL,1,?,?)",
        (rid, r["complexity"], r["duration"], r["duration_total"], r.get("image_base", ""), r["image_name"],
         r.get("recipe_type", "custom"), r["instructions"], r.get("language", "de"), r["level"], r["name"],
         # unit defaults are the labels used by the German app ("per serving" / "servings")
        r.get("nutrient_unit", "Pro Portion"), int(time.time() * 1000), r["yield"],
         r.get("yield_unit", "Portionen")))
    for t in r["tags"]:
        c.execute("insert into TAG (CATEGORY, NAME, RECIPE_ID) values ('other', ?, ?)", (t, rid))
    for typ, unit, amount in r["nutrients"]:
        c.execute("insert into NUTRIENT (AMOUNT, RECIPE_ID, TYPE, UNIT) values (?,?,?,?)", (amount, rid, typ, unit))
    base = c.execute("insert into INGREDIENTS_BASE (NAME, RECIPE_ID) values ('', ?)", (rid,)).lastrowid
    for amount, unit, name in r["ingredients"]:
        c.execute("insert into INGREDIENT (AMOUNT, INGREDIENTS_BASE_ID, NAME, UNIT) values (?,?,?,?)",
                  (amount, base, name, unit))
    for n, s in enumerate(r["steps"], 1):
        mode = s["mode"]
        # REVERSE=1 means counter-clockwise; the app uses 1 as default for scale/instruction/steaming steps
        rev = s.get("reverse", 1 if mode in ("scale", "instruction", "steaming") else 0)
        spd, temp, tm, wt = s.get("speed", 0), s.get("temp", 0), s.get("time", 0), s.get("weight", 0)
        led = c.execute("insert into LED (ACTION, COLOR) values ('steady', 'green')").lastrowid
        mv = c.execute("insert into MACHINE_VALUES (REVERSE, SPEED, TEMP, TIME, WEIGHT) values (?,?,?,?,?)",
                       (rev, spd, temp, tm, wt)).lastrowid
        ms = c.execute("insert into MEASUREMENT (LID, SPEED, TEMP, WEIGHT) values (0,?,?,?)",
                       (spd, temp, wt)).lastrowid
        c.execute("insert into STEP (LED_ID, MACHINE_VALUES_ID, MEASUREMENT_ID, MODE, RECIPE_ID, STEP, TEXT)"
                  " values (?,?,?,?,?,?,?)", (led, mv, ms, mode, rid, n, s.get("text", "")))


def main():
    r = json.load(open(sys.argv[1], encoding="utf-8"))
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("begin immediate")
    try:
        delete_recipe(c, r["id"])
        insert_recipe(c, r)
        c.execute("commit")
    except Exception:
        c.execute("rollback")
        raise
    n = c.execute("select count(*) from STEP where RECIPE_ID=?", (r["id"],)).fetchone()[0]
    print("ok", r["id"], r["name"], n, "steps")


main()
