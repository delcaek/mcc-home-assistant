#!/bin/bash
# Builds build/overlay.apk without Gradle: javac -> d8 -> aapt2 -> zipalign -> apksigner.
# Needs JDK 17 and the Android SDK with "platforms;android-23" and "build-tools;34.0.0":
#   ANDROID_HOME=/path/to/android-sdk overlay/build.sh
# or use Docker (no local SDK needed):
#   docker build -t mcc-overlay-build overlay && docker run --rm -v "$PWD":/repo mcc-overlay-build
# A signing key is generated on first build in build/overlay-debug.keystore (not committed). Keep it: an update
# signed with a different key requires uninstalling the app first.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/android-sdk}}"
BT="$SDK/build-tools/34.0.0"; JAR="$SDK/platforms/android-23/android.jar"
[ -f "$JAR" ] && [ -x "$BT/d8" ] || { echo "Android SDK not found (need platforms;android-23 and build-tools;34.0.0 in $SDK)"; exit 1; }
OUT="$REPO/build/overlay"; rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex"
KS="$REPO/build/overlay-debug.keystore"; KSPASS="${OVERLAY_KS_PASS:-android}"

javac -source 8 -target 8 -bootclasspath "$JAR" -d "$OUT/classes" $(find "$HERE/src" -name '*.java') 2>&1 | grep -v "bootstrap class path\|^1 warning\|source value 8\|target value 8\|-Xlint:-options" || true
"$BT/d8" --min-api 22 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
"$BT/aapt2" link -o "$OUT/base.apk" --manifest "$HERE/AndroidManifest.xml" -I "$JAR" --min-sdk-version 22 --target-sdk-version 22
python3 - "$OUT/base.apk" "$OUT/dex/classes.dex" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "a", zipfile.ZIP_DEFLATED) as z:
    z.write(sys.argv[2], "classes.dex")
PY
"$BT/zipalign" -f 4 "$OUT/base.apk" "$OUT/aligned.apk"
[ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass "$KSPASS" -keypass "$KSPASS" -alias overlay \
                  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=MCC Overlay" >/dev/null
"$BT/apksigner" sign --ks "$KS" --ks-pass "pass:$KSPASS" --out "$REPO/build/overlay.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify "$REPO/build/overlay.apk" && ls -l "$REPO/build/overlay.apk"
