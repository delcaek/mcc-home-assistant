# Own recipes in the stock app

The stock app (package `de.silpion.mc2`) keeps its recipes in an SQLite database (greenDAO):
`/data/data/de.silpion.mc2/databases/Recipes`. With root you can add your own guided recipes. **Only import
recipes you wrote yourself or are allowed to use** – recipes, texts and photos from other platforms are usually
copyrighted.

## The recipe type pitfall

On every start the app syncs with its server and **deletes recipes of type `default`, `live` and `beta` whose id
the server does not know**. Use your own type (this repository uses `custom`). The app only shows types listed in
the preference `RECIPES_IMPORTED_TYPE` (newline-separated, e.g. `default\nlive`), so add yours once:

```bash
python3 scripts/add-recipe-type.py custom
```

After an app version change the app may reset this preference – your recipes are then hidden, not deleted;
run the script again.

## Import

```bash
python3 -I recipes/mcc_recipe_check.py recipes/examples/*.json
recipes/push-recipes.sh recipes/examples/900001-tomato-soup.json
```

`push-recipes.sh` backs up the database to `/data/local/tmp/Recipes.bak-<time>`, runs `mcc_recipe_insert.py` on
the machine (with the bundled Python, so `deploy.sh` must have run), copies images and restarts the app.
Inserting is idempotent: a recipe with the same id is replaced. Use ids ≥ 900000 to stay clear of the
vendor's ids.

Images (optional): `recipes/img/<id>-large.jpg` (1024×426) and `recipes/img/<id>-small.jpg` (254×373); they are
copied to `files/recipe_images/{large,small}-<image_name>`.

## JSON format

| field | meaning |
|---|---|
| `id` | integer, unique (≥ 900000 recommended) |
| `name` | title shown in the app |
| `recipe_type` | default `custom`; never `default`/`live`/`beta` |
| `language` | language code stored with the recipe (default `de`; use the one of your stock recipes) |
| `complexity`, `level` | label shown in the app and 1/2/3 (easy/medium/hard) |
| `duration`, `duration_total` | active and total minutes |
| `yield`, `yield_unit`, `nutrient_unit` | servings, the unit label and the nutrient reference label shown by the app |
| `image_base`, `image_name` | image file name (and an optional base URL) |
| `tags` | category names; tag category is `other`. A tag equal to the app's "new" category name (German app: `Neu`) makes the recipe appear there with a corner badge |
| `nutrients` | `[type, unit, amount]` for `joules`, `calories`, `protein`, `carbohydrate`, `fat`, amounts as strings |
| `ingredients` | `[amount, unit, name]` strings (amount may be empty) |
| `instructions` | short overview text |
| `steps` | list, see below |

Step modes (stored in table `STEP`, values in `MACHINE_VALUES`):

| mode | fields | notes |
|---|---|---|
| `instruction` | `text` | anything without the machine |
| `scale` | `weight` (g), `text` | one weighed ingredient per step (liquids in g) |
| `cooking` | `speed` 1–10, `temp` 0 or 37–130 in 5 °C steps, `time` s, `reverse` 0/1 | no `text`; `reverse` 1 = counter-clockwise |
| `turbo` | `time` 1–12 s | |
| `roasting` | `speed` 1, `temp` 100–130, `time` ≤ 840 s, `reverse` 1 | sear function; remove the measuring cup before |
| `steaming` | `time` s | steamer attachment |
| `kneading` | `time` ≤ 300 s | dough |

`mcc_recipe_check.py` enforces these rules.

## Converting recipes from other kitchen machines (general guidelines)

- Speeds map roughly 1:1; half speeds round down; slow stir / reverse symbol → `speed 1, reverse 1`.
  Chopping "x s / speed 5" stays the same (do not lengthen – the MCC turns faster at the same speed).
- Temperatures: round to the allowed steps (98 °C → 100 °C); a "steam" temperature in the bowl → 120 °C;
  dishes cooked in a steamer on top → `steaming`.
- Browning modes of other machines (e.g. 160 °C) → `roasting` at 130 °C.
- "Cook according to the packet" → put a concrete time and add a check step plus an optional extra step.
- The MCC bowl holds 3 l; quantities can usually be kept.
- Never invent quantities; record your assumptions in a `notes` list in the JSON (ignored by the importer).
