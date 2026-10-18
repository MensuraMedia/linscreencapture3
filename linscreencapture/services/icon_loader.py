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

from .. import APP_ID, RESOURCE_PREFIX  # noqa: E402

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


def app_icon_file() -> pathlib.Path:
    """The application icon's SVG source (also bundled in the resource as ``scalable/apps/<APP_ID>.svg``)."""
    return pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"


def install_app_icon() -> None:
    """Every window carries the application icon (``_NET_WM_ICON`` on X11): Alt+Tab, the window list and the
    task bar show it even when the icon is not installed in the system theme."""
    Gtk.Window.set_default_icon_name(APP_ID)


def install_css() -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_resource(f"{RESOURCE_PREFIX}/style.css")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_USER)
    return provider


_cursors: dict = {}


def eyedropper_cursor() -> Gdk.Cursor:
    """A 28 px eyedropper pointer: the bundled glyph in black with a white outline (it shows on any picture), its
    hotspot on the tip (bottom left). Falls back to the crosshair where cursors from textures are unsupported."""
    if "eyedropper" not in _cursors:
        try:
            import io
            import numpy as np
            from PIL import Image, ImageFilter
            from gi.repository import GdkPixbuf
            data = Gio.resources_lookup_data(f"{RESOURCE_PREFIX}/icons/scalable/actions/{icon_name('eyedropper')}.svg",
                                             Gio.ResourceLookupFlags.NONE).get_data()
            loader = GdkPixbuf.PixbufLoader()
            loader.set_size(22, 22)
            loader.write(data)
            loader.close()
            glyph = Image.open(io.BytesIO(loader.get_pixbuf().save_to_bufferv("png", [], [])[1])).convert("RGBA")
            alpha = Image.new("L", (28, 28)); alpha.paste(glyph.getchannel("A"), (3, 3))
            halo = alpha.filter(ImageFilter.MaxFilter(5))           # a 2 px white outline around the black glyph
            out = Image.new("RGBA", (28, 28), (255, 255, 255, 0))
            out.putalpha(halo)
            black = Image.new("RGBA", (28, 28), (0, 0, 0, 255)); black.putalpha(alpha)
            out.alpha_composite(black)
            buf = io.BytesIO(); out.save(buf, "PNG")
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
            # the tip of Phosphor's eyedropper sits at about (36, 219) of 256
            hot_x, hot_y = 3 + round(36 / 256 * 22), 3 + round(219 / 256 * 22)
            _cursors["eyedropper"] = Gdk.Cursor.new_from_texture(texture, hot_x, hot_y,
                                                                 Gdk.Cursor.new_from_name("crosshair"))
        except Exception:  # noqa: BLE001 — never let a cursor break the eyedropper
            _cursors["eyedropper"] = Gdk.Cursor.new_from_name("crosshair")
    return _cursors["eyedropper"]


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
