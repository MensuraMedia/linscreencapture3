"""Copy an image surface to the display clipboard, lossless, for every kind of paste target.

The clipboard offers two representations of the same pixels:

* ``image/png`` bytes: lossless and at the capture's native resolution (no scaling). This is what other applications
  (browsers, chat apps, ``xclip -selection clipboard -t image/png -o``, terminals and the Claude Code CLI) ask for.
* a ``GdkTexture`` value: for pastes inside this application, without a PNG round trip.

A provider built from the texture alone (``ContentProvider.new_for_value(memory_texture)``) advertises only the GType
``GdkMemoryTexture``. GDK has no serializer registered for that subclass, so X11 offered no image target at all and
pastes in other applications came up empty. Both representations are therefore spelled out explicitly.

After setting the content, the clipboard is handed to the desktop's clipboard manager (``store_async``; on Cinnamon,
``csd-clipboard``), so the image survives even if this process exits. That is the GTK 4 equivalent of the 1.4
``gtk_clipboard_store()`` fix.
"""
from __future__ import annotations
import logging

import cairo
from gi.repository import Gdk, GLib, GObject

LOG = logging.getLogger("linscreencapture.clipboard")
PNG = "image/png"


def texture_from_surface(surface: cairo.ImageSurface) -> Gdk.Texture:
    surface.flush()
    w, h, stride = surface.get_width(), surface.get_height(), surface.get_stride()
    return Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                 GLib.Bytes.new(bytes(surface.get_data())), stride)


def image_providers(surface: cairo.ImageSurface) -> list[Gdk.ContentProvider]:
    """The PNG bytes first (what other applications request), then the texture typed as ``GdkTexture``."""
    texture = texture_from_surface(surface)
    png = texture.save_to_png_bytes()
    value = GObject.Value(Gdk.Texture, texture)
    return [Gdk.ContentProvider.new_for_bytes(PNG, png), Gdk.ContentProvider.new_for_value(value)]


def set_providers(providers: list[Gdk.ContentProvider]) -> bool:
    display = Gdk.Display.get_default()
    if display is None:
        return False
    clip = display.get_clipboard()
    ok = clip.set_content(Gdk.ContentProvider.new_union(providers))
    if ok:
        clip.store_async(GLib.PRIORITY_DEFAULT, None, _stored)
    return ok


def _stored(clip: Gdk.Clipboard, result) -> None:
    try:
        clip.store_finish(result)
        LOG.debug("clipboard handed to the clipboard manager")
    except GLib.Error as exc:            # no clipboard manager: the agent keeps serving the data itself
        LOG.debug("clipboard manager did not store the image: %s", exc.message)


def copy_surface(surface: cairo.ImageSurface) -> bool:
    return set_providers(image_providers(surface))
