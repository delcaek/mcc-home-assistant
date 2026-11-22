#!/system/bin/sh
# Starts mcc_ha.py with the bundled glibc Python (no proot, no chroot): Android uses bionic libc, so we call the
# glibc dynamic loader from the Ubuntu base rootfs explicitly and point it at the right library directories.
B=/data/mcc
ROOT=$B/rootfs
LD=$ROOT/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3
LIBS=$ROOT/usr/lib/arm-linux-gnueabihf:$ROOT/lib/arm-linux-gnueabihf:$B/python/lib
export PYTHONHOME=$B/python            # otherwise Python loses its home when started through the loader
export PYTHONPATH=$B/code              # mcc_mux.py, mcc_ha.py, paho/
export LD_LIBRARY_PATH=$LIBS           # also needed for dlopen() of C extensions
export MCC_CONFIG=$B/mcc.json
cd $B/code
exec "$LD" --library-path "$LIBS" "$B/python/bin/python3.12" "$B/code/mcc_ha.py"
