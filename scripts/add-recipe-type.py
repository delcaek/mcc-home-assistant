#!/usr/bin/env python3
"""Adds your own recipe type (default "custom") to the stock app preference RECIPES_IMPORTED_TYPE so recipes of
that type become visible. Needed once (and again if an app update empties the preference).

    python3 scripts/add-recipe-type.py [type]

The value is a newline-separated list, e.g. "default\\nlive" -> "default\\nlive\\ncustom".
Editing shared_prefs is delicate (see docs/operations.md), this script therefore:
  - builds the new file on the host and validates it as XML (no NUL bytes),
  - backs up the original on the machine (/data/local/tmp/PREFERENCES_MC2.xml.bak-<time>),
  - force-stops the app, writes the file, force-stops again (the app is the HOME launcher and restarts at once;
    a fresh process may already have loaded the old file and would write it back), then shows the result.
"""
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = "de.silpion.mc2"
PREFS = "/data/data/%s/shared_prefs/PREFERENCES_MC2.xml" % APP
KEY = "RECIPES_IMPORTED_TYPE"


def env():
    path = os.environ.get("MCC_ENV", os.path.join(REPO, "config", "config.env"))
    out = subprocess.run(["bash", "-c", 'set -a; . "$1"; env -0', "_", path], capture_output=True, check=True)
    return dict(kv.split("=", 1) for kv in out.stdout.decode().split("\0") if "=" in kv)


C = env()
ADB = C.get("ADB", "adb").split() + ["-s", C["ADB_ADDR"]]


def adb(*a, **kw):
    return subprocess.run(ADB + list(a), capture_output=True, check=True, **kw).stdout


rtype = sys.argv[1] if len(sys.argv) > 1 else "custom"
if rtype in ("default", "live", "beta"):
    sys.exit("use your own type name, the app deletes default/live/beta recipes it does not know")
orig = adb("exec-out", "su -c 'cat %s'" % PREFS).decode("utf-8")
root = ET.fromstring(orig.encode())
el = [e for e in root if e.get("name") == KEY]
if not el:
    sys.exit("%s not found in the preferences - start the app once and let it import its recipes" % KEY)
types = (el[0].text or "").replace("\r", "").split("\n")
if rtype in types:
    print("already present:", types)
    sys.exit(0)
old = '<string name="%s">%s</string>' % (KEY, el[0].text)
if orig.count(old) != 1:
    sys.exit("unexpected file layout, aborting (nothing changed)")
new = orig.replace(old, '<string name="%s">%s\n%s</string>' % (KEY, el[0].text, rtype))
ET.fromstring(new.encode())                       # must still be valid XML
assert "\0" not in new
with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
    f.write(new)
adb("push", f.name, "/data/local/tmp/prefs-new.xml")
os.unlink(f.name)
stamp = time.strftime("%Y%m%d-%H%M%S")
script = ("P=%s; cp $P /data/local/tmp/PREFERENCES_MC2.xml.bak-%s; am force-stop %s; cat /data/local/tmp/prefs-new.xml > $P;"
          " am force-stop %s; rm /data/local/tmp/prefs-new.xml; sleep 8; grep -A3 %s $P" % (PREFS, stamp, APP, APP, KEY))
print(adb("shell", "su -c '%s'" % script).decode())
