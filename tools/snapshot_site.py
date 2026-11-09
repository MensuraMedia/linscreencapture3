#!/usr/bin/env python3
"""Render the two promotional screenshots of the running studio (website, GitHub Pages, README).

    make site-shots            # or: xvfb-run -a -s "-screen 0 1600x1000x24" python3 tools/snapshot_site.py [outdir]

Writes to screenshots/dev/ (1430x890 window content):
  shell_studio_open.png       an annotated capture with both rails open and the box layer selected
  shell_library_collapsed.png the Library with both rails collapsed, two images selected, tags shown

The run is sandboxed: HOME, XDG_CONFIG_HOME and XDG_DATA_HOME point at a temporary folder, so the operator's
settings, tags, autostart entry and hotkey are never touched. The Library shows ~/Pictures/ScreenShots inside that
sandbox, seeded only with this repository's own synthetic renders and design artboards (privacy: no desktop captures).
"""
from __future__ import annotations
import datetime, json, os, pathlib, shutil, subprocess, sys, tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
SHOTS = REPO / "screenshots"
BASE = SHOTS / "03_capture_overlay.png"          # the synthetic sign-in page artboard is the capture we annotate
GALLERY = ["dev/shell_adjust", "dev/shell_crop", "dev/shell_eraser", "09_sidebar_anatomy", "08_control_system",
           "07_empty_state", "06_preferences", "05_props_redaction", "04_captures_annotations", "03_capture_overlay",
           "02_rails_collapsed", "01_studio_editor"]          # oldest first: LinScreenCapture_1 … _12
TAGS = {12: ["studio"], 10: ["capture"], 8: ["redaction", "review"], 6: ["settings"]}
W, H = 1440, 900
SANDBOX_ENV = "LSC_SITE_SANDBOX"


def seed_sandbox(root: pathlib.Path) -> pathlib.Path:
    """Fill <root>/home/Pictures/ScreenShots with the gallery and write the tags; return the folder."""
    folder = root / "home" / "Pictures" / "ScreenShots"
    folder.mkdir(parents=True)
    t0 = datetime.datetime(2026, 11, 9, 9, 0).timestamp()   # fixed local times, 7 minutes apart: a stable grid
    for n, name in enumerate(GALLERY, 1):
        dst = folder / f"LinScreenCapture_{n}.png"
        shutil.copyfile(SHOTS / f"{name}.png", dst)
        os.utime(dst, (t0 + n * 420, t0 + n * 420))
    data = root / "data" / "linscreencapture"
    data.mkdir(parents=True)
    (data / "tags.json").write_text(json.dumps({str(folder / f"LinScreenCapture_{n}.png"): t for n, t in TAGS.items()}))
    return folder


def outer(out: pathlib.Path) -> int:
    """Build the sandbox and run this script again inside it."""
    with tempfile.TemporaryDirectory(prefix="lsc-site-") as tmp:
        root = pathlib.Path(tmp)
        folder = seed_sandbox(root)
        env = dict(os.environ, HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_DATA_HOME=str(root / "data"), LSC_NO_TRAY="1", **{SANDBOX_ENV: str(folder)})
        return subprocess.call([sys.executable, __file__, str(out)], env=env, cwd=REPO)


def inner(out: pathlib.Path) -> int:
    import gi
    gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); gi.require_version("Graphene", "1.0")
    from gi.repository import GLib, Graphene, Gtk
    sys.path.insert(0, str(REPO))
    from linscreencapture.app.application import Application
    from linscreencapture.model.settings import Settings

    def render(win, path):
        w, h = win.get_width(), win.get_height()
        snap = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
        tex = win.get_native().get_renderer().render_texture(snap.to_node(), Graphene.Rect().init(0, 0, w, h))
        path.parent.mkdir(parents=True, exist_ok=True)
        tex.save_to_png(str(path))
        print("wrote", path, f"{w}x{h}")

    app = Application(non_unique=True)     # a running LinScreenCapture must not swallow the snapshot run
    settings = Settings.load()             # the sandbox's XDG_CONFIG_HOME: nothing reaches the real ~
    settings.screenshot_path = os.environ[SANDBOX_ENV]
    app.settings = settings

    def on_activate(a):
        win = a.props.active_window
        win.set_default_size(W, H)

        def library():
            win.state.left_collapsed = win.state.right_collapsed = True
            win.activate_action("win.library", None)
            GLib.timeout_add(1500, library_select)
            return False

        def library_select():
            sel = win.stage.library.selection
            sel.select_item(0, True); sel.select_item(2, False)
            GLib.timeout_add(1200, library_render)
            return False

        def library_render():
            render(win, out / "shell_library_collapsed.png")
            win.activate_action("win.library", None)
            GLib.timeout_add(600, studio)
            return False

        def studio():
            from linscreencapture.model.document import Document
            from linscreencapture.model.undo import AddLayer
            from linscreencapture.model.annotations import Annotation
            win.state.left_collapsed = win.state.right_collapsed = False
            win.load_document(Document.open(str(BASE)))
            ed = win.editor
            st = ed.style_for
            add = lambda ann: ed._commit(AddLayer(ann))
            win.state.colour = "#e5484d"
            add(Annotation("box", 318, 232, 742, 372, style=st("box")))                 # the sign-in form
            add(Annotation("arrow", 640, 470, 475, 352, style=st("arrow")))             # → the button
            win.state.colour = "#0091ff"
            add(Annotation("step", 300, 259, style=st("step"), number=1))
            add(Annotation("step", 300, 343, style=st("step"), number=2))
            win.state.colour = "#ffb224"
            add(Annotation("marker", style=st("marker"), points=[(336, 161), (655, 161)]))  # the page heading
            win.state.colour = "#e5484d"
            add(Annotation("text", 120, 50, style=st("text"), text="New sign-in page"))
            add(Annotation("pixelate", 770, 462, 1010, 520, style=st("pixelate")))     # the terminal output
            add(Annotation("blur", 190, 98, 330, 116, style=st("blur")))               # the address bar
            add(Annotation("callout", 985, 330, 900, 475, style=st("callout"), text="Hidden before sharing"))
            win.state.tool = "select"
            ed.select(win.document.layers[0].id)                                       # the box
            GLib.timeout_add(500, studio_fit)
            return False

        def studio_fit():
            win.activate_action("win.zoom-fit", None)
            GLib.timeout_add(1200, studio_render)
            return False

        def studio_render():
            render(win, out / "shell_studio_open.png")
            a.quit()
            return False

        GLib.timeout_add(1200, library)

    app.connect_after("activate", on_activate)
    return app.run([])


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else SHOTS / "dev").resolve()
    sys.exit(inner(out) if SANDBOX_ENV in os.environ else outer(out))
