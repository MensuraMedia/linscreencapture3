import pathlib
from gi.repository import Gdk, Gtk, Graphene

from tests.conftest import pump, ROOT


def test_every_listed_icon_is_in_the_bundle(gtk):
    from linscreencapture.services import icon_loader
    names = [n.strip() for n in (ROOT / "data/icons/icons.txt").read_text().splitlines() if n.strip()]
    bundled = set(icon_loader.icon_names())
    missing = [n for n in names if n not in bundled]
    assert not missing, missing
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    assert all(theme.has_icon(icon_loader.icon_name(n)) for n in names)


def test_symbolic_icon_takes_css_colour(gtk, app, tmp_path):
    """A Phosphor glyph must be recoloured from the widget's CSS `color`."""
    from linscreencapture.services import icon_loader
    app.register(None)
    win = Gtk.Window(application=app)
    img = icon_loader.icon("square", 48)  # filled square outline — thick enough to sample
    css = Gtk.CssProvider()
    css.load_from_string("image.probe { color: #4c9dff; -gtk-icon-size: 48px; }")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
    img.add_css_class("probe")
    win.set_child(img)
    win.set_default_size(64, 64)
    win.present()
    pump(300)
    paintable = Gtk.WidgetPaintable.new(img)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, 48, 48)
    node = snap.to_node()
    tex = win.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, 48, 48))
    out = tmp_path / "glyph.png"
    tex.save_to_png(str(out))
    win.destroy()
    from PIL import Image
    im = Image.open(out).convert("RGBA")
    opaque = [im.getpixel((x, y)) for x in range(48) for y in range(48) if im.getpixel((x, y))[3] > 200]
    assert opaque, "glyph did not render"
    r, g, b, _a = opaque[0]
    assert (r, g, b) == (0x4c, 0x9d, 0xff), (r, g, b)
