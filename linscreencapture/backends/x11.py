"""X11 backend: one XGetImage of the root window through libX11 (ctypes), copied in bulk into ARGB32.

python-xlib's pure-Python ``get_image`` parses the 11 MB reply of a 2560×1080 screen in ~3.5 s, which
users saw as a mysterious "capture delay". libX11's ``XGetImage`` does the same in ~50 ms, so the grab
goes through ctypes and python-xlib stays only for the window list (small replies, fast enough).
"""
from __future__ import annotations
import ctypes
import ctypes.util
import os
from typing import Callable

import cairo

from .base import WindowInfo, CaptureError

ZPIXMAP = 2
ALL_PLANES = 0xFFFFFFFF


class _XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int), ("format", ctypes.c_int),
                ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int), ("bitmap_unit", ctypes.c_int),
                ("bitmap_bit_order", ctypes.c_int), ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int),
                ("bytes_per_line", ctypes.c_int), ("bits_per_pixel", ctypes.c_int),
                ("red_mask", ctypes.c_ulong), ("green_mask", ctypes.c_ulong), ("blue_mask", ctypes.c_ulong),
                ("obdata", ctypes.c_void_p), ("create_image", ctypes.c_void_p),
                ("destroy_image", ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)),
                ("get_pixel", ctypes.c_void_p), ("put_pixel", ctypes.c_void_p), ("sub_image", ctypes.c_void_p),
                ("add_pixel", ctypes.c_void_p)]


_lib = None


def _libx11():
    global _lib
    if _lib is None:
        x = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XDefaultScreen.argtypes = [ctypes.c_void_p]
        x.XRootWindow.restype = ctypes.c_ulong
        x.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XGetImage.restype = ctypes.POINTER(_XImage)
        x.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                                ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        _lib = x
    return _lib


def grab_root_libx11() -> cairo.ImageSurface:
    """The whole root window as an opaque ARGB32 surface (BGRX in memory, one bulk copy)."""
    import numpy as np
    x = _libx11()
    d = x.XOpenDisplay(None)
    if not d:
        raise CaptureError("XOpenDisplay failed")
    try:
        scr = x.XDefaultScreen(d)
        root = x.XRootWindow(d, scr)
        w, h = x.XDisplayWidth(d, scr), x.XDisplayHeight(d, scr)
        img = x.XGetImage(d, root, 0, 0, w, h, ALL_PLANES, ZPIXMAP)
        if not img:
            raise CaptureError("XGetImage failed")
        try:
            im = img.contents
            if im.bits_per_pixel != 32:
                raise CaptureError(f"unsupported X visual: depth {im.depth}, {im.bits_per_pixel} bpp")
            raw = ctypes.string_at(im.data, im.bytes_per_line * h)
            src = np.frombuffer(raw, dtype=np.uint8).reshape(h, im.bytes_per_line // 4, 4)[:, :w, :]
        finally:
            im.destroy_image(ctypes.cast(img, ctypes.c_void_p))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        dst = np.ndarray((h, surf.get_stride() // 4, 4), dtype=np.uint8, buffer=surf.get_data())
        dst[:, :w, :] = src
        dst[:, :w, 3] = 255
        surf.mark_dirty()
        return surf
    finally:
        x.XCloseDisplay(d)


def grab_root_xlib() -> cairo.ImageSurface:
    """Fallback through python-xlib (slow: pure-Python reply parsing)."""
    import numpy as np
    from Xlib import X, display
    d = display.Display()
    try:
        root = d.screen().root
        geo = root.get_geometry()
        w, h = geo.width, geo.height
        img = root.get_image(0, 0, w, h, X.ZPixmap, ALL_PLANES)
        data = img.data
        if len(data) != w * h * 4:
            raise CaptureError(f"unsupported X visual: depth {getattr(img, 'depth', '?')}, {len(data)} bytes for {w}x{h}")
        buf = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4).copy()
        buf[:, :, 3] = 255
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        dst = np.ndarray((h, surf.get_stride() // 4, 4), dtype=np.uint8, buffer=surf.get_data())
        dst[:, :w, :] = buf
        surf.mark_dirty()
        return surf
    finally:
        d.close()


class X11Backend:
    name = "x11"
    is_async = False

    def available(self) -> bool:
        if not os.environ.get("DISPLAY"):
            return False
        try:
            import Xlib.display  # noqa: F401
        except ImportError:
            return False
        return True

    def capture_screen(self) -> cairo.ImageSurface:
        try:
            return grab_root_libx11()
        except (OSError, AttributeError) as exc:   # no libX11 to load: the slow pure-Python path still works
            import logging
            logging.getLogger("linscreencapture.capture").warning("libX11 grab unavailable (%s); using python-xlib", exc)
            return grab_root_xlib()

    def capture_screen_async(self, on_done: Callable) -> None:  # pragma: no cover - sync backend
        try:
            on_done(self.capture_screen(), None)
        except Exception as exc:  # noqa: BLE001
            on_done(None, exc)

    def list_windows(self) -> list[WindowInfo]:
        """Top-level viewable windows, topmost first, with frame geometry in root coordinates."""
        from Xlib import X, display, Xatom
        d = display.Display()
        out: list[WindowInfo] = []
        try:
            root = d.screen().root
            atom = lambda n: d.intern_atom(n)  # noqa: E731
            prop = root.get_full_property(atom("_NET_CLIENT_LIST_STACKING"), Xatom.WINDOW)
            ids = list(prop.value) if prop else []
            skip_types = {atom(n) for n in ("_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK")}
            for wid in reversed(ids):  # stacking list is bottom to top
                try:
                    win = d.create_resource_object("window", wid)
                    if win.get_attributes().map_state != X.IsViewable:
                        continue
                    types = win.get_full_property(atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM)
                    if types and set(types.value) & skip_types:
                        continue
                    name_p = win.get_full_property(atom("_NET_WM_NAME"), atom("UTF8_STRING")) or win.get_full_property(Xatom.WM_NAME, Xatom.STRING)
                    title = name_p.value.decode("utf-8", "replace") if name_p and isinstance(name_p.value, bytes) else (str(name_p.value) if name_p else "")
                    geo = win.get_geometry()
                    pos = win.translate_coords(root, 0, 0)
                    x, y, w, h = -pos.x, -pos.y, geo.width, geo.height
                    ext = win.get_full_property(atom("_NET_FRAME_EXTENTS"), Xatom.CARDINAL)
                    if ext and len(ext.value) == 4:
                        l, r, t, b = ext.value
                        x, y, w, h = x - l, y - t, w + l + r, h + t + b
                    if w > 1 and h > 1:
                        out.append(WindowInfo(wid, title, x, y, w, h))
                except Exception:  # noqa: BLE001 - a window may vanish while we walk the list
                    continue
        finally:
            d.close()
        return out
