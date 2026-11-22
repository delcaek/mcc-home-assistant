#!/bin/bash
# Inserts recipes into the MCC stock app:   recipes/push-recipes.sh recipes/examples/900001-tomato-soup.json [...]
# Optional images next to the JSON files in recipes/img/: <id>-large.jpg (1024x426) and <id>-small.jpg (254x373).
# Prerequisite (once): your recipe type is listed in RECIPES_IMPORTED_TYPE (scripts/add-recipe-type.py).
# Every run first copies the database to /data/local/tmp/Recipes.bak-<timestamp> on the machine.
set -euo pipefail
. "$(dirname "$0")/../scripts/lib.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"
D=/data/data/de.silpion.mc2
adb_connect || { echo "machine not reachable"; exit 1; }
python3 -I "$HERE/mcc_recipe_check.py" "$@"
touch "$STATE_DIR/.pause"; trap 'rm -f "$STATE_DIR/.pause"' EXIT
adb_ push "$HERE/mcc_recipe_insert.py" /data/local/tmp/ >/dev/null
su_ "cp $D/databases/Recipes /data/local/tmp/Recipes.bak-\$(date +%Y%m%d-%H%M%S)"
PY='B=/data/mcc; R=$B/rootfs; L=$R/usr/lib/arm-linux-gnueabihf:$R/lib/arm-linux-gnueabihf:$B/python/lib; PYTHONHOME=$B/python LD_LIBRARY_PATH=$L $R/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 --library-path $L $B/python/bin/python3.12 -I'
for j in "$@"; do
  id=$(python3 -I -c "import json,sys;print(json.load(open(sys.argv[1]))['id'])" "$j")
  img=$(python3 -I -c "import json,sys;print(json.load(open(sys.argv[1]))['image_name'])" "$j")
  adb_ push "$j" /data/local/tmp/recipe.json >/dev/null
  adb_ shell "su -c '$PY /data/local/tmp/mcc_recipe_insert.py /data/local/tmp/recipe.json'"
  for p in large small; do
    f="$HERE/img/$id-$p.jpg"; [ -f "$f" ] || continue
    adb_ push "$f" /data/local/tmp/img.jpg >/dev/null
    t=$D/files/recipe_images/$p-$img
    su_ "cp /data/local/tmp/img.jpg $t; chown system:system $t; chmod 600 $t; chcon u:object_r:system_app_data_file:s0 $t"
  done
done
su_ "rm -f /data/local/tmp/recipe.json /data/local/tmp/img.jpg /data/local/tmp/mcc_recipe_insert.py; am force-stop de.silpion.mc2"
echo "done - app restarted"
