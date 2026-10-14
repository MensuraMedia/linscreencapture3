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


def render_widget(widget: Gtk.Widget, path: pathlib.Path, renderer) -> None:
    """Render one widget with ``renderer`` (popover contents live on a surface without a renderer of their own)."""
    w, h = widget.get_width(), widget.get_height()
    paintable = Gtk.WidgetPaintable.new(widget)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, w, h)
    node = snap.to_node()
    if node is None or w == 0 or h == 0:
        print("skipped", path, "(widget not drawable on this display)")
        return
    tex = renderer.render_texture(node, Graphene.Rect().init(0, 0, w, h))
    path.parent.mkdir(parents=True, exist_ok=True)
    tex.save_to_png(str(path))
    print("wrote", path, f"{w}x{h}")


def main() -> int:
    app = Application(non_unique=True)   # a running LinScreenCapture must not swallow the snapshot run
    settings = Settings.load(root=str(OUT / "_cfg"))  # isolated config: read but nothing persisted to ~

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
            # annotate programmatically: arrow, box, step numbers, text, pixelate; select the box
            from linscreencapture.model.undo import AddLayer
            from linscreencapture.model.annotations import Annotation
            ed = win.editor
            st = lambda t: ed.style_for(t)
            ed._commit(AddLayer(Annotation("arrow", 560, 520, 800, 430, style=st("arrow"))))
            win.state.colour = "#ffb224"
            ed._commit(AddLayer(Annotation("box", 240, 180, 640, 320, style=st("box"))))
            win.state.colour = "#0091ff"
            ed._commit(AddLayer(Annotation("step", 275, 240, style=st("step"), number=1)))
            ed._commit(AddLayer(Annotation("step", 275, 300, style=st("step"), number=2)))
            win.state.colour = "#e5484d"
            ed._commit(AddLayer(Annotation("text", 300, 120, style=st("text"), text="Studio editor")))
            ed._commit(AddLayer(Annotation("pixelate", 980, 260, 1120, 300, style=st("pixelate"))))
            ed._commit(AddLayer(Annotation("callout", 850, 560, 1040, 640, style=st("callout"), text="Settings live here")))
            win.state.tool = "select"
            ed.select(win.document.layers[1].id)
            GLib.timeout_add(700, step5b)
            return False

        def step5b():
            render(win, OUT / "shell_annotated.png")
            # a pending crop rectangle (veil + accent frame) with the Crop strip in the header
            win.editor.select(None)
            win.state.tool = "crop"
            win.editor.crop_rect = (200, 140, 900, 520)
            win.stage.canvas.queue_draw()
            GLib.timeout_add(700, step5c)
            return False

        def step5c():
            render(win, OUT / "shell_crop.png")
            win.editor.cancel_crop()
            win.state.tool = "select"
            win.activate_action("win.adjust", None)   # Brightness popover with its live preview
            GLib.timeout_add(500, step5d)
            return False

        def step5d():
            pop = win._popovers.get("adjust")
            if pop is not None:
                pop.brightness.set_value(35); pop.gray.set_active(True)
            GLib.timeout_add(700, step5e)
            return False

        def step5e():
            render(win, OUT / "shell_adjust.png")
            pop = win._popovers.get("adjust")
            if pop is not None:
                pop._cancel()
            win.state.zoom = 2.0
            GLib.timeout_add(700, step5f)
            return False

        def step5f():
            render(win, OUT / "shell_document_zoomed.png")
            win.state.zoom = 1.0
            # review round 2: Ctrl+A marks every layer; Ctrl+C fills the clipboard tray (three copies kept)
            ed = win.editor
            win.activate_action("win.copy", None)
            ed.select(win.document.layers[0].id)
            from linscreencapture.model.undo import SetVisible
            ed._commit(SetVisible(win.document.layers[1], False), select_new=False)
            win.activate_action("win.copy", None)
            ed._commit(SetVisible(win.document.layers[1], True), select_new=False)
            ed._commit(SetVisible(win.document.layers[0], False), select_new=False)
            win.activate_action("win.copy", None)
            ed._commit(SetVisible(win.document.layers[0], True), select_new=False)
            win.activate_action("win.select-all", None)
            GLib.timeout_add(700, step5g)
            return False

        def step5g():
            render(win, OUT / "shell_select_all_tray.png")
            tray = win.tool_rail.tray
            tray.slots[0].popup()
            GLib.timeout_add(600, step5h)
            return False

        def step5h():
            tray = win.tool_rail.tray
            render_widget(tray.preview.get_child(), OUT / "shell_clip_preview.png", win.get_native().get_renderer())
            tray.preview.popdown()
            # the eraser clears to transparent: the stage checkerboard shows through
            from linscreencapture.model.undo import AddLayer
            from linscreencapture.model.annotations import Annotation
            ed = win.editor
            st = ed.style_for("eraser")
            ed._commit(AddLayer(Annotation("eraser", style=st, points=[(120, 650), (260, 600), (420, 660), (600, 610)])))
            win.state.tool = "eraser"
            GLib.timeout_add(700, step5i)
            return False

        def step5i():
            render(win, OUT / "shell_eraser.png")
            # the Area tool: a closed point chain around the mock window's sidebar
            from linscreencapture.model.annotations import Annotation
            win.state.tool = "area_points"
            win.editor.set_area(Annotation("cutout", 600, 330, 780, 720, shape="points",
                                           points=[(610, 330), (770, 330), (780, 520), (700, 720), (600, 640)]))
            GLib.timeout_add(700, step5i2)
            return False

        def step5i2():
            render(win, OUT / "shell_area_chain.png")
            win.editor.cancel_area()
            win.state.tool = "select"
            win.activate_action("win.library", None)
            GLib.timeout_add(900, step5j)
            return False

        def step5j():
            win.activate_action("win.library-select-all", None)
            GLib.timeout_add(500, step5k)
            return False

        def step5k():
            render(win, OUT / "shell_library_multiselect.png")
            win.activate_action("win.library", None)
            GLib.timeout_add(700, step6)
            return False

        def step6():
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
