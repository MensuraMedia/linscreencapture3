"""XDG desktop portal backend (org.freedesktop.portal.Screenshot): works on Wayland and X11."""
from __future__ import annotations
import os
import itertools
from typing import Callable
from urllib.parse import urlparse, unquote

import cairo
from gi.repository import Gio, GLib

from .base import WindowInfo, CaptureError

_tokens = itertools.count(1)


class PortalBackend:
    name = "portal"
    is_async = True

    def __init__(self) -> None:
        self._proxy: Gio.DBusProxy | None = None

    def _get_proxy(self) -> Gio.DBusProxy | None:
        if self._proxy is None:
            try:
                self._proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Screenshot", None)
            except GLib.Error:
                return None
        return self._proxy

    def available(self) -> bool:
        proxy = self._get_proxy()
        return bool(proxy and proxy.get_cached_property("version") is not None)

    def capture_screen(self) -> cairo.ImageSurface:  # pragma: no cover - needs a main loop
        raise CaptureError("portal backend is asynchronous; use capture_screen_async")

    def capture_screen_async(self, on_done: Callable[[cairo.ImageSurface | None, Exception | None], None]) -> None:
        proxy = self._get_proxy()
        if proxy is None:
            on_done(None, CaptureError("portal not reachable"))
            return
        conn = proxy.get_connection()
        sender = conn.get_unique_name().lstrip(":").replace(".", "_")
        token = f"lsc{next(_tokens)}"
        request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        sub = {"id": 0}

        def on_response(_c, _s, _p, _i, _sig, params):
            conn.signal_unsubscribe(sub["id"])
            code, results = params.unpack()
            if code != 0:
                on_done(None, CaptureError("screenshot cancelled by the portal" if code == 1 else f"portal error {code}"))
                return
            uri = results.get("uri", "")
            path = unquote(urlparse(uri).path)
            try:
                from ..model.document import load_image
                surf = load_image(path)
            except Exception as exc:  # noqa: BLE001
                on_done(None, exc)
                return
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            on_done(surf, None)

        sub["id"] = conn.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response",
                                          request_path, None, Gio.DBusSignalFlags.NO_MATCH_RULE, on_response)
        options = {"handle_token": GLib.Variant("s", token), "interactive": GLib.Variant("b", False),
                   "modal": GLib.Variant("b", True)}
        try:
            proxy.call("Screenshot", GLib.Variant("(sa{sv})", ("", options)), Gio.DBusCallFlags.NONE, 30000, None,
                       lambda p, res: self._call_done(p, res, on_done, conn, sub))
        except GLib.Error as exc:
            conn.signal_unsubscribe(sub["id"])
            on_done(None, exc)

    @staticmethod
    def _call_done(proxy, res, on_done, conn, sub) -> None:
        try:
            proxy.call_finish(res)
        except GLib.Error as exc:
            conn.signal_unsubscribe(sub["id"])
            on_done(None, exc)

    def list_windows(self) -> list[WindowInfo]:
        return []
