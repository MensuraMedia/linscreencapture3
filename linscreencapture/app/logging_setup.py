"""Application logging. Quiet by default; ``--debug`` or ``LSC_DEBUG=1`` turns on timestamped detail.

GLib/GTK messages are routed into Python logging so one stream shows the app and the toolkit.
"""
from __future__ import annotations
import logging
import os
import sys
import time

from gi.repository import GLib

LOG = logging.getLogger("linscreencapture")
_T0 = time.monotonic()


class _Elapsed(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.elapsed = f"{(time.monotonic() - _T0) * 1000:7.1f} ms"
        return super().format(record)


def setup(debug: bool | None = None) -> bool:
    if debug is None:
        debug = os.environ.get("LSC_DEBUG", "") not in ("", "0", "false")
    level = logging.DEBUG if debug else logging.WARNING
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Elapsed("%(elapsed)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    if debug:
        _route_glib()
    return debug


_GLIB_LEVELS = {
    GLib.LogLevelFlags.LEVEL_ERROR: logging.CRITICAL, GLib.LogLevelFlags.LEVEL_CRITICAL: logging.ERROR,
    GLib.LogLevelFlags.LEVEL_WARNING: logging.WARNING, GLib.LogLevelFlags.LEVEL_MESSAGE: logging.INFO,
    GLib.LogLevelFlags.LEVEL_INFO: logging.INFO, GLib.LogLevelFlags.LEVEL_DEBUG: logging.DEBUG,
}


def _route_glib() -> None:
    """Send GLib structured log messages (Gtk-WARNING, Adwaita-CRITICAL, …) through Python logging."""
    import re
    prefix = re.compile(r"^\([^)]*\):\s*")          # "(process:1234): " / "(__main__.py:1234): "
    stamp = re.compile(r"\*\*:\s*\d\d:\d\d:\d\d\.\d+:\s*")  # "**: 01:02:03.456: "

    def writer(level, fields, _n, _user):
        try:
            text = GLib.log_writer_format_fields(level, fields, False)
        except Exception:  # noqa: BLE001
            return GLib.LogWriterOutput.UNHANDLED
        text = stamp.sub(": ", prefix.sub("", text.strip()))
        domain = text.split("-", 1)[0] if "-" in text.split(":", 1)[0] else "glib"
        is_debug = bool(level & GLib.LogLevelFlags.LEVEL_DEBUG)
        if is_debug and domain in ("GLib", "dconf", "GLib-GIO") and ("GIO" in text or "dconf" in text):
            return GLib.LogWriterOutput.HANDLED       # backend discovery chatter
        py_level = logging.DEBUG
        for flag, lv in _GLIB_LEVELS.items():
            if level & flag:
                py_level = lv
                break
        logging.getLogger("toolkit").log(py_level, text)
        return GLib.LogWriterOutput.HANDLED
    try:
        GLib.log_set_writer_func(writer, None)
    except Exception as exc:  # noqa: BLE001 - older bindings
        LOG.debug("GLib log routing unavailable: %s", exc)


def describe_environment() -> dict[str, str]:
    import gi
    from gi.repository import Gtk, Adw
    from .. import __version__
    return {
        "app": f"LinScreenCapture {__version__}",
        "python": sys.version.split()[0],
        "pygobject": ".".join(map(str, gi.version_info)),
        "gtk": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        "libadwaita": f"{Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
        "session": os.environ.get("XDG_SESSION_TYPE", "?"),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "?"),
        "display": os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "?",
    }
