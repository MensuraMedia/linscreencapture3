"""GResource installation and icon lookup.

Icons are Phosphor SVGs compiled into ``linscreencapture.gresource`` under
``<prefix>/icons/scalable/actions/lsc-<name>-symbolic.svg``; GTK recolours them
from the widget's CSS ``color``.
"""
from __future__ import annotations
import pathlib
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk, GLib  # noqa: E402

from .. import RESOURCE_PREFIX  # noqa: E402

_installed = False


def resource_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "linscreencapture.gresource"


def install() -> None:
    """Register the resource bundle and add it to the icon theme (idempotent)."""
    global _installed
    if _installed:
        return
    path = resource_path()
    if not path.is_file():
        raise FileNotFoundError(f"{path} missing — run `make resources`")
    Gio.Resource.load(str(path))._register()
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.IconTheme.get_for_display(display).add_resource_path(f"{RESOURCE_PREFIX}/icons")
    _installed = True


def install_css() -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_resource(f"{RESOURCE_PREFIX}/style.css")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_USER)
    return provider


def icon_name(name: str) -> str:
    return f"lsc-{name}-symbolic"


def icon(name: str, size: int = 18) -> Gtk.Image:
    img = Gtk.Image.new_from_icon_name(icon_name(name))
    img.set_pixel_size(size)
    return img


def icon_names() -> list[str]:
    """Names listed in the bundle, without prefix/suffix (for tests)."""
    children = Gio.resources_enumerate_children(f"{RESOURCE_PREFIX}/icons/scalable/actions", 0)
    return sorted(c[len("lsc-"):-len("-symbolic.svg")] for c in children if c.endswith("-symbolic.svg"))
