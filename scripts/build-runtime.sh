#!/bin/bash
# Builds the on-device runtime: Ubuntu 22.04 armhf base (only for glibc + loader), python-build-standalone
# CPython 3.12 for armv7 and paho-mqtt. Output: build/mcc-runtime.tar (UNcompressed - toybox tar on the machine
# has no gzip). Runs on any Linux/macOS host with bash, curl, tar, sha256sum (or shasum) and python3 + pip.
# Nothing is executed for ARM, so no qemu is needed.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=build/runtime
DL=build/downloads
mkdir -p "$DL"; rm -rf "$OUT"; mkdir -p "$OUT/rootfs" "$OUT/code"

# Pinned artifacts (the versions verified on a real SKMC 1200 in Nov 2026)
UBUNTU_URL=https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04-base-armhf.tar.gz
UBUNTU_SHA=fdf4dba0bfa22c80453cc6f40185195ad7dff765f598b14cce9604b9c7cb8c83
PBS_TAG=20261026
PBS_FILE=cpython-3.12.16+${PBS_TAG}-armv7-unknown-linux-gnueabihf-install_only_stripped.tar.gz
PBS_URL=https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${PBS_FILE//+/%2B}
PBS_SHA=8ebcbfd83290fe028acd4de8af54b973332895d5aab3cb6382610437e35896cd
PAHO_URL=https://files.pythonhosted.org/packages/c4/cb/00451c3cf31790287768bb12c6bec834f5d292eaf3022afc88e14b8afc94/paho_mqtt-2.1.0-py3-none-any.whl
PAHO_SHA=6db9ba9b34ed5bc6b6e3812718c7e06e2fd7444540df2455d2c51bd58808feee

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
fetch() { # url sha file
  local f="$DL/$3"
  [ -f "$f" ] && [ "$(sha "$f")" = "$2" ] && return
  echo "downloading $3"; curl -fL --retry 3 -o "$f.part" "$1"; mv "$f.part" "$f"
  [ "$(sha "$f")" = "$2" ] || { echo "CHECKSUM MISMATCH for $3" >&2; exit 1; }
}
fetch "$UBUNTU_URL" "$UBUNTU_SHA" ubuntu-base-armhf.tar.gz
fetch "$PBS_URL" "$PBS_SHA" python-armv7.tar.gz
fetch "$PAHO_URL" "$PAHO_SHA" paho_mqtt-2.1.0-py3-none-any.whl

echo "unpacking"
# device nodes in the base image cannot be created without root and are not needed
tar -xzf "$DL/ubuntu-base-armhf.tar.gz" -C "$OUT/rootfs" --exclude='./dev/*' --exclude='dev/*' 2>/dev/null || true
[ -e "$OUT/rootfs/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3" ] || { echo "rootfs incomplete" >&2; exit 1; }
tar -xzf "$DL/python-armv7.tar.gz" -C "$OUT"            # -> $OUT/python
python3 - "$DL/paho_mqtt-2.1.0-py3-none-any.whl" "$OUT/code" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for n in z.namelist():                       # keep the package and its license files
    if n.startswith("paho/") or "LICENSE" in n or n.endswith((".txt",)) and "dist-info" in n:
        z.extract(n, sys.argv[2])
PY

# slim the rootfs: only glibc and friends are used (keeps the upload ~30 MB smaller)
rm -rf "$OUT/rootfs/usr/share/doc" "$OUT/rootfs/usr/share/man" "$OUT/rootfs/usr/share/locale" \
       "$OUT/rootfs/var/cache/apt" "$OUT/rootfs/var/lib/apt/lists"
rm -rf "$OUT/python/lib/python3.12/test" "$OUT/python/lib/python3.12/idlelib" "$OUT/python/lib/python3.12/tkinter"

cat > "$OUT/VERSIONS.txt" <<VER
ubuntu-base 22.04 armhf  $UBUNTU_SHA
$PBS_FILE  $PBS_SHA
paho-mqtt 2.1.0  $PAHO_SHA
built $(date -u +%FT%TZ)
VER
tar -cf build/mcc-runtime.tar -C "$OUT" rootfs python code VERSIONS.txt
ls -lh build/mcc-runtime.tar
echo "next: scripts/deploy.sh"
