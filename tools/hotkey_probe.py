#!/usr/bin/env python3
"""Live end-to-end check of the capture hotkey on X11 (docs/CAPTURE.md §10). Moves the real pointer.

    python3 tools/hotkey_probe.py                     # Print, drag 400,300 → 700,500
    python3 tools/hotkey_probe.py --key Control_L+Print --box 400 300 700 500

Presses the hotkey through XTest, waits for the overlay, drags a box (Region captures on release), then reads the
clipboard with ``xclip`` and reports the image/png target and the image size. Needs python3-xlib and xclip, and a
running agent with the hotkey bound. Exit status 0 = a PNG of the expected size is on the clipboard.
"""
from __future__ import annotations
import argparse
import struct
import subprocess
import sys
import time

from Xlib import X, XK, display
from Xlib.ext import xtest


def chord(d, keys: list[str]) -> None:
    codes = [d.keysym_to_keycode(XK.string_to_keysym(k)) for k in keys]
    for c in codes:
        xtest.fake_input(d, X.KeyPress, c); d.sync()
    time.sleep(0.05)
    for c in reversed(codes):
        xtest.fake_input(d, X.KeyRelease, c); d.sync()


def drag(d, x1: int, y1: int, x2: int, y2: int) -> None:
    xtest.fake_input(d, X.MotionNotify, x=x1, y=y1); d.sync(); time.sleep(0.15)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.1)
    for i in range(1, 11):
        xtest.fake_input(d, X.MotionNotify, x=x1 + (x2 - x1) * i // 10, y=y1 + (y2 - y1) * i // 10); d.sync()
        time.sleep(0.03)
    time.sleep(0.1)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", default="Print", help="keysyms joined by +, e.g. Control_L+Print")
    ap.add_argument("--box", nargs=4, type=int, default=[400, 300, 700, 500], metavar=("X1", "Y1", "X2", "Y2"))
    ap.add_argument("--wait", type=float, default=1.2, help="seconds between the key and the drag")
    a = ap.parse_args()
    d = display.Display()
    chord(d, a.key.split("+"))
    time.sleep(a.wait)
    drag(d, *a.box)
    time.sleep(1.0)
    targets = subprocess.run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                             capture_output=True, text=True, timeout=3).stdout.split()
    png = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                         capture_output=True, timeout=3).stdout
    want = (abs(a.box[2] - a.box[0]), abs(a.box[3] - a.box[1]))
    size = struct.unpack(">II", png[16:24]) if png[:8] == b"\x89PNG\r\n\x1a\n" else None
    print(f"image/png offered: {'image/png' in targets} · PNG on clipboard: {size} · expected {want}")
    return 0 if size == want else 1


if __name__ == "__main__":
    sys.exit(main())
