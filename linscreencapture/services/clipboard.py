"""Copy an image surface to the display clipboard (GTK 4 owns the data; no helper process)."""
from __future__ import annotations
import cairo
from gi.repository import Gdk, GLib


def texture_from_surface(surface: cairo.ImageSurface) -> Gdk.Texture:
    surface.flush()
    w, h, stride = surface.get_width(), surface.get_height(), surface.get_stride()
    return Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                 GLib.Bytes.new(bytes(surface.get_data())), stride)


def copy_surface(surface: cairo.ImageSurface) -> bool:
    display = Gdk.Display.get_default()
    if display is None:
        return False
    texture = texture_from_surface(surface)
    provider = Gdk.ContentProvider.new_for_value(texture)
    return display.get_clipboard().set_content(provider)
