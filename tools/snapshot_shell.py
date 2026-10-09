#!/usr/bin/env python3
"""Render the Studio shell to PNGs for comparison with the mockups.

    xvfb-run -a -s "-screen 0 1600x1000x24" python3 tools/snapshot_shell.py [outdir]

Writes shell_open.png and shell_collapsed.png (1360x840 window content).
"""
from __future__ import annotations
import pathlib, sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gsk, Gtk, Graphene  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from linscreencapture.app.application import Application  # noqa: E402
from linscreencapture.model.settings import Settings  # noqa: E402

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots/dev")


def render(win: Gtk.Window, path: pathlib.Path) -> None:
    w, h = win.get_width(), win.get_height()
    paintable = Gtk.WidgetPaintable.new(win)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, w, h)
    node = snap.to_node()
    renderer = win.get_native().get_renderer()
    tex = renderer.render_texture(node, Graphene.Rect().init(0, 0, w, h))
    path.parent.mkdir(parents=True, exist_ok=True)
    tex.save_to_png(str(path))
    print("wrote", path, f"{w}x{h}")


def main() -> int:
    app = Application()
    settings = Settings(root=str(OUT / "_cfg"))  # isolated config: defaults, nothing persisted to ~

    app.settings = settings

    def on_activate(a):
        win = a.props.active_window
        win.set_default_size(1360, 840)

        def step0():
            render(win, OUT / "shell_default.png")      # first run: both rails collapsed
            win.state.left_collapsed = False
            win.state.right_collapsed = False
            GLib.timeout_add(700, step1)
            return False

        def step1():
            render(win, OUT / "shell_open.png")
            win.state.left_collapsed = True
            win.state.right_collapsed = True
            GLib.timeout_add(700, step2)
            return False

        def step2():
            render(win, OUT / "shell_collapsed.png")
            win.state.left_collapsed = False
            win.state.right_collapsed = False
            win.activate_action("win.library", None)
            GLib.timeout_add(900, step3)
            return False

        def step3():
            render(win, OUT / "shell_library.png")
            win.activate_action("win.library", None)
            win.state.tool = "text"
            GLib.timeout_add(700, step4)
            return False

        def step4():
            render(win, OUT / "shell_text_tool.png")
            win.state.tool = "arrow"
            from linscreencapture.model.document import Document
            win.load_document(Document.open("screenshots/01_studio_editor.png"))
            GLib.timeout_add(900, step5)
            return False

        def step5():
            render(win, OUT / "shell_document.png")
            win.state.zoom = 2.0
            GLib.timeout_add(700, step6)
            return False

        def step6():
            render(win, OUT / "shell_document_zoomed.png")
            a.activate_action("preferences", None)
            GLib.timeout_add(900, step7)
            return False

        def step7():
            # libadwaita presents the dialog as its own window when the parent is a plain GtkApplicationWindow
            dlg = getattr(a, "preferences_dialog", None)
            root = dlg.get_root() if dlg is not None else None
            target = root if isinstance(root, Gtk.Window) and root is not win else win
            print("settings dialog root:", type(root).__name__ if root else None)
            render(target, OUT / "shell_settings.png")
            a.quit()
            return False
        GLib.timeout_add(900, step0)

    app.connect_after("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
