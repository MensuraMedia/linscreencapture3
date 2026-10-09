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
            win.state.panel = "props"
            win.state.tool = "blur"
            GLib.timeout_add(700, step4)
            return False

        def step4():
            render(win, OUT / "shell_props.png")
            a.quit()
            return False
        GLib.timeout_add(900, step1)

    app.connect_after("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
