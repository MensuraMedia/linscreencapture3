#!/usr/bin/env python3
"""Render the capture overlay (with a preset selection) to screenshots/dev/overlay.png, then cancel it."""
from __future__ import annotations
import pathlib, sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Graphene  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from linscreencapture.services import icon_loader  # noqa: E402
from linscreencapture.services.capture_service import CaptureService  # noqa: E402
from linscreencapture.services.selection import Selection  # noqa: E402
from linscreencapture.ui.capture_overlay import OverlaySession  # noqa: E402

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots/dev")


def main() -> int:
    app = Adw.Application(application_id="com.mensuramedia.LinScreenCapture.OverlaySnapshot")

    def activate(a):
        icon_loader.install(); icon_loader.install_css()
        svc = CaptureService("auto")

        def got(surface, err):
            if surface is None:
                print("capture failed:", err); a.quit(); return
            session = OverlaySession(surface, "region", svc.list_windows(), lambda rect: (print("done", rect), a.quit()))
            w, h = surface.get_width(), surface.get_height()
            session.selection = Selection(w * 0.22, h * 0.2, w * 0.78, h * 0.76)
            session.pointer = (w * 0.78, h * 0.76)
            session.show()

            def shoot():
                ow = session.overlays[0]
                W, H = ow.get_width(), ow.get_height()
                paintable = Gtk.WidgetPaintable.new(ow)
                snap = Gtk.Snapshot(); paintable.snapshot(snap, W, H)
                tex = ow.get_native().get_renderer().render_texture(snap.to_node(), Graphene.Rect().init(0, 0, W, H))
                OUT.mkdir(parents=True, exist_ok=True)
                tex.save_to_png(str(OUT / "overlay.png")); print("wrote", OUT / "overlay.png", f"{W}x{H}")
                session.cancel()
                return False
            GLib.timeout_add(900, shoot)
        svc.capture_screen(got)
        hold = Gtk.Window(application=a)  # keeps the app alive until the overlay closes
        hold.set_visible(False)
    app.connect("activate", activate)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
