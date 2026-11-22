#!/usr/bin/env python3
"""
mcc_mux.py - serial man-in-the-middle for the Monsieur Cuisine Connect (SKMC 1200).

Runs on the rooted machine (Magisk on the stock ROM) as real root.

    stock app --> /dev/ttyMT0   (a PTY created by us and bind-mounted over the device node)
                       |
                  this daemon  <-->  /dev/ttyMT0_real  (the real motor/heater controller)
                       |
                  MQTT  <-->  Home Assistant   (see mcc_ha.py)

The stock app keeps working normally: everything it sends is forwarded to the controller and every
controller frame is forwarded back. Only during a remote-control session ("control mode") the app's
frames are suppressed and this daemon sends its own frames instead.

SAFETY: this code switches a heating element and a blade. Start with "read_only": true in mcc.json,
compare the logged frames with docs/protocol.md and only then enable control.
"""

import ctypes
import itertools
import json
import os
import pty
import select
import struct
import subprocess
import termios
import threading
import time

# ------------------------------------------------------------------ configuration
CONFIG_PATH = os.environ.get("MCC_CONFIG", "/data/mcc/mcc.json")
DEFAULTS = {
    "read_only": True,                      # True = only listen and publish state, never send
    "real_port": "/dev/ttyMT0_real",        # real controller node (moved there by mccctl.sh)
    "fake_port": "/dev/ttyMT0",             # where the app expects the controller
    "watchdog_s": 5.0,                      # no new command for this long during control -> STOP
    "overlay_package": "io.mccha.overlay",  # e-stop overlay app (overlay/)
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        print("[cfg] %s not found, using defaults" % CONFIG_PATH, flush=True)
    return cfg


CFG = load_config()
READ_ONLY = bool(CFG["read_only"])
REAL_PORT = CFG["real_port"]
FAKE_LINK = CFG["fake_port"]
WATCHDOG_S = float(CFG["watchdog_s"])
BAUD = termios.B4800
OVERLAY_PKG = CFG["overlay_package"]
OVERLAY_SVC = OVERLAY_PKG + "/.OverlayService"
OVERLAY_DIR = "/data/data/%s/files" % OVERLAY_PKG
ESTOP_FILE = OVERLAY_DIR + "/estop"          # written by the overlay's STOP button
REMAIN_FILE = OVERLAY_DIR + "/remaining"     # remaining seconds for the overlay (-1 = no timer)


def overlay_file(path, text):
    """Write a file for the overlay app (text None = delete it). The file gets owner and SELinux label of the
    app's files directory, otherwise the app cannot read it while SELinux is enforcing."""
    try:
        if text is None:
            if os.path.exists(path):
                os.remove(path)
            return
        new = not os.path.exists(path)
        with open(path, "w") as f:
            f.write(text)
        if new:
            d = os.path.dirname(path)
            st = os.stat(d)
            os.chown(path, st.st_uid, st.st_gid)
            os.chmod(path, 0o644)
            os.setxattr(path, "security.selinux", os.getxattr(d, "security.selinux"))
    except OSError as e:
        print("[ovl] %s: %s" % (os.path.basename(path), e), flush=True)


def overlay_remaining(sec):
    """Remaining time for the e-stop overlay (seconds, -1 = no timer, None = remove)."""
    overlay_file(REMAIN_FILE, None if sec is None else str(int(sec)))


def knob_counts():
    """Interrupt counters of the rotary knob (knod-key = press, forward/backward = turn); None on error.
    The knob is not wired through the controller board but to the app (/dev/knob), so we cannot see it on the
    serial line. The kernel counts its interrupts in /proc/interrupts though."""
    try:
        with open("/proc/interrupts") as f:
            # sum all CPU columns: with several cores online the interrupt does not always land on CPU0
            return tuple(sum(int(x) for x in itertools.takewhile(str.isdigit, line.split()[1:]))
                         for line in f if line.rstrip().endswith((" knod-key", " forward", " backward")))
    except (OSError, ValueError, IndexError):
        return None


# ---- real bind mount via libc.mount() (needs real root; proot cannot do this) ----
_libc = ctypes.CDLL("libc.so.6", use_errno=True)
MS_BIND = 4096


def _bind_mount(src, dst):
    if _libc.mount(src.encode(), dst.encode(), None, MS_BIND, None) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), "bind %s->%s" % (src, dst))


# ----------------------------------------------------------------------- protocol
HDR, TERM = 0x55, 0xAA
TX_LEN, RX_LEN = 0x0F, 0x1B
TX_TYPE, RX_TYPE = 0xA1, 0xB1
OPS = {"STOP": 0x00, "STANDARD": 0x01, "STEAM": 0x03, "TOAST": 0x04,
       "KNEAD": 0x05, "SLEEP": 0x0F, "TURBO": 0xC6}
TEMP_TABLE = [0, 37, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110,
              115, 120, 125, 130]                       # level index -> degrees Celsius


def temp_to_level(celsius: int) -> int:
    """Highest level whose temperature does not exceed the requested one (never round up)."""
    lvl = 0
    for i, t in enumerate(TEMP_TABLE):
        if t <= celsius:
            lvl = i
    return lvl


def checksum(b: bytes, end: int) -> int:
    return sum(b[:end]) & 0xFF


def encode_tx(operation="STANDARD", speed=0, temp_c=0, ccw=False, tare=False):
    if not 0 <= speed <= 10:
        raise ValueError("speed 0..10")
    f = bytearray(15)
    f[0], f[1], f[2] = HDR, TX_LEN, TX_TYPE
    f[3] = OPS[operation]
    f[4] = 0xA9 if tare else 0x00
    f[5] = speed
    f[6] = temp_to_level(temp_c)
    f[11] = 1 if ccw else 0
    f[13] = checksum(f, 13)
    f[14] = TERM
    return bytes(f)


def decode_rx(f: bytes) -> dict:
    if len(f) != 27 or f[0] != HDR or f[2] != RX_TYPE or f[26] != TERM:
        raise ValueError("bad RX frame")
    if checksum(f, 25) != f[25]:
        raise ValueError("bad checksum")
    st = f[3]
    return {
        "lid_open":      bool(st & 0x80),
        "ntc_bowl":      bool(st & 0x40),
        "over_temp":     bool(st & 0x20),
        "error":         bool(st & 0x10),
        "scale_stable":  bool(st & 0x04),
        "motor_heat":    st & 0x03,
        "running":       bool(st & 0x03),
        "error_code":    f[5],
        "speed_target":  f[6],
        "target_temp_c": TEMP_TABLE[f[11]] if f[11] < len(TEMP_TABLE) else 0,  # level byte
        "rpm_target":    struct.unpack(">H", f[7:9])[0],
        "rpm_actual":    struct.unpack(">H", f[9:11])[0],    # always 0 on the tested unit
        "heater_temp_c": struct.unpack(">H", f[12:14])[0],   # fast heating element temperature
        "temp_actual_c": struct.unpack(">H", f[14:16])[0],   # content temperature
        "weight_g":      struct.unpack(">i", f[16:20])[0],
        "firmware":      struct.unpack(">H", f[20:22])[0],
    }


class RxParser:
    """Resynchronises on 0x55 .. 0xAA and returns complete 27-byte frames."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(HDR)
            if i < 0:
                self.buf.clear()
                break
            if i:
                del self.buf[:i]
            if len(self.buf) < RX_LEN:
                break
            frame = bytes(self.buf[:RX_LEN])
            if frame[26] == TERM:
                out.append(frame)
                del self.buf[:RX_LEN]
            else:
                del self.buf[0]            # lost sync -> skip one byte
        return out


# ------------------------------------------------------------------------- mux core
class Mux:
    SEND_INTERVAL = 0.1    # ~10 frames/s. The app sends 7-8/s; at 4/s the controller stops after ~2 s.

    def __init__(self):
        self.real = self._open_real()
        self.master, self.slave = pty.openpty()
        self._set_baud(self.master)
        slave_path = os.ttyname(self.slave)
        print("[mux] PTY slave = %s -> bind mount on %s" % (slave_path, FAKE_LINK), flush=True)
        os.chmod(slave_path, 0o666)        # the original node is 0666; a pts is 0600 and the app could not open it
        if not os.path.exists(FAKE_LINK):  # mount target must exist (the real node was moved away)
            open(FAKE_LINK, "w").close()
        _bind_mount(slave_path, FAKE_LINK)
        self.parser = RxParser()
        self.last_state = {}
        self.control = False               # True = we send, app frames are suppressed
        self._cmd = encode_tx("STOP")      # command that is repeated while in control mode
        self._last_cmd_ts = 0.0
        self._last_send = 0.0
        self._last_we = None
        self._lock = threading.Lock()
        self._control_shown = False
        self.silent = False                # short takeovers (tare) without overlay/beep
        self._estop = False
        self._knob_base = None
        self._knob_t = 0.0
        self._knob_start = 0.0

    def clear_estop(self):
        self._estop = False
        try:
            os.remove(ESTOP_FILE)
        except OSError:
            pass

    def _overlay(self, action):            # SHOW/HIDE via am (as root)
        try:
            subprocess.run(["/system/bin/sh", "-c",
                            "am startservice -n %s --es action %s" % (OVERLAY_SVC, action)],
                           timeout=5, check=False)
        except Exception as e:
            print("[overlay] error: %s" % e, flush=True)

    def _open_real(self):
        fd = os.open(REAL_PORT, os.O_RDWR | os.O_NOCTTY)
        self._set_baud(fd)
        return fd

    def _set_baud(self, fd):
        a = termios.tcgetattr(fd)
        a[4] = a[5] = BAUD
        # raw 8N1 (works on the tested unit)
        a[2] = ((a[2] & ~termios.PARENB & ~termios.CSTOPB & ~termios.CSIZE)
                | termios.CS8 | termios.CLOCAL | termios.CREAD)
        a[0] = a[1] = a[3] = 0
        termios.tcsetattr(fd, termios.TCSANOW, a)

    # --- called by mcc_ha.py ----------------------------------------------------------
    def command(self, **kw):
        """kw: operation, speed, temp_c, ccw, tare - sets the frame that is repeated in control mode."""
        with self._lock:
            self._cmd = encode_tx(**kw)
            self._last_cmd_ts = time.time()

    def stop(self):
        with self._lock:
            self._cmd = encode_tx("STOP")
            self._last_cmd_ts = time.time()

    # --- main loop -----------------------------------------------------------------------
    def run(self):
        print("[mux] running, read_only=%s" % READ_ONLY, flush=True)
        last_rx = None
        while True:
            r, _, _ = select.select([self.real, self.master], [], [], 0.2)

            # app -> controller (forwarded unless we are in control) - logged as hex
            if self.master in r:
                data = os.read(self.master, 256)
                if not self.control:
                    os.write(self.real, data)
                if data:
                    tag = "[app-x]" if self.control else "[app>]"    # x = suppressed
                    print("%s %s %s" % (time.strftime("%H:%M:%S"), tag, data.hex()), flush=True)

            # controller -> app (always forwarded, decoded for MQTT)
            if self.real in r:
                data = os.read(self.real, 256)
                os.write(self.master, data)
                for frame in self.parser.feed(data):
                    h = frame.hex()
                    if h == last_rx:                 # only log changes
                        continue
                    last_rx = h
                    print("%s [rx>] %s" % (time.strftime("%H:%M:%S"), h), flush=True)
                    try:
                        st = decode_rx(frame)
                    except ValueError:
                        print("[rx!] decode error", flush=True)
                        continue
                    # occasionally frames with a valid checksum carry nonsense (1000 degC, -2e9 g): drop them so
                    # neither HA nor the safety gates ever see them
                    if st["temp_actual_c"] > 200 or st["heater_temp_c"] > 300 or abs(st["weight_g"]) > 20000:
                        print("[rx?] implausible, dropped", flush=True)
                        continue
                    self.last_state = st
                    self._publish(st)

            want = self.control and not self.silent
            if want != self._control_shown:
                self._control_shown = want
                self._overlay("SHOW" if want else "HIDE")
            if self.control and os.path.exists(ESTOP_FILE):
                try:
                    os.remove(ESTOP_FILE)
                except OSError:
                    pass
                self._estop = True
                print("[ESTOP] overlay STOP pressed", flush=True)
            # turning/pressing the knob on the machine during remote control = emergency stop
            if self.control:
                now = time.time()
                if now - self._knob_t >= 0.2:
                    self._knob_t = now
                    k = knob_counts()
                    if self._knob_base is None:
                        self._knob_start = now
                        self._knob_base = k
                    elif now - self._knob_start < 1.0:
                        self._knob_base = k          # first second: ignore a spurious start impulse
                    elif k and k != self._knob_base and not self._estop:
                        self._estop = True
                        print("[ESTOP] knob used %s -> %s" % (self._knob_base, k), flush=True)
            else:
                self._knob_base = None

            self._maybe_inject()

    def _maybe_inject(self):
        if READ_ONLY or not self.control:
            return
        now = time.time()
        if now - self._last_send < self.SEND_INTERVAL:
            return
        s = self.last_state
        with self._lock:
            frame = self._cmd
            # safety gates: e-stop / lid open / error / watchdog -> force STOP.
            # Pure STOP frames (byte 3 = 0), also with the tare byte, are allowed with the lid open
            # (you usually weigh with the lid off); motor and heater stay locked.
            if (self._estop or s.get("lid_open") or s.get("error")) and frame[3] != OPS["STOP"]:
                frame = encode_tx("STOP")
            elif self._last_cmd_ts and (now - self._last_cmd_ts) > WATCHDOG_S:
                frame = encode_tx("STOP")
            os.write(self.real, frame)
            self._last_send = now
            if frame != self._last_we:
                self._last_we = frame
                print("%s [we>] %s" % (time.strftime("%H:%M:%S"), frame.hex()), flush=True)

    def _publish(self, state):          # replaced by mcc_ha.py
        print("%s [rx ] %s" % (time.strftime("%H:%M:%S"), json.dumps(state)), flush=True)


if __name__ == "__main__":
    Mux().run()
