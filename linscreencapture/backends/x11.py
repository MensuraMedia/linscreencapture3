"""X11 backend: one GetImage of the root window, copied in bulk into an ARGB32 surface."""
from __future__ import annotations
import os
from typing import Callable

import cairo

from .base import WindowInfo, CaptureError


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
        import numpy as np
        from Xlib import X, display
        d = display.Display()
        try:
            root = d.screen().root
            geo = root.get_geometry()
            w, h = geo.width, geo.height
            img = root.get_image(0, 0, w, h, X.ZPixmap, 0xFFFFFFFF)
            data = img.data
            if len(data) != w * h * 4:
                raise CaptureError(f"unsupported X visual: depth {getattr(img, 'depth', '?')}, {len(data)} bytes for {w}x{h}")
            buf = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4).copy()  # BGRX, one bulk copy
            buf[:, :, 3] = 255
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            stride = surf.get_stride()
            dst = np.ndarray((h, stride // 4, 4), dtype=np.uint8, buffer=surf.get_data())
            dst[:, :w, :] = buf
            surf.mark_dirty()
            return surf
        finally:
            d.close()

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
