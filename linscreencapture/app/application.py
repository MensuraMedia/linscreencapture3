"""Adw.Application: single instance, actions, accelerators, --capture activation."""
from __future__ import annotations
from gi.repository import Adw, Gio, GLib, Gtk

from .. import APP_ID
from ..services import icon_loader

APP_PLACEHOLDERS = {
    "capture-region": 3, "capture-window": 3, "capture-screen": 3, "capture-scrolling": 6,
    "capture-delayed": 6, "pin": 6, "preferences": 6,
}
ACCELS = {
    "app.quit": ["<Control>q"],
    "app.preferences": ["<Control>comma"],
    "app.capture-region": ["<Control>n"],
    "app.capture-screen": ["<Control><Shift>n"],
    "win.save": ["<Control>s"],
    "win.copy": ["<Control>c"],
    "win.undo": ["<Control>z"],
    "win.redo": ["<Control><Shift>z"],
    "win.library": ["<Control>l"],
    "win.toggle-left-rail": ["<Control>bracketleft"],
    "win.toggle-right-rail": ["<Control>bracketright"],
    "win.zoom-in": ["<Control>plus", "<Control>equal"],
    "win.zoom-out": ["<Control>minus"],
    "win.zoom-fit": ["<Control>0"],
    "win.zoom-actual": ["<Control>1"],
    "win.tool::select": ["v"], "win.tool::arrow": ["a"], "win.tool::line": ["l"], "win.tool::box": ["b"],
    "win.tool::circle": ["c"], "win.tool::text": ["t"], "win.tool::pen": ["p"], "win.tool::marker": ["m"],
    "win.tool::blur": ["u"], "win.tool::pixelate": ["x"], "win.tool::step": ["n"], "win.tool::crop": ["k"],
}


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.add_main_option("capture", ord("c"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Capture a region immediately", None)
        self._capture_on_start = False
        self.settings = None  # a Settings instance to use instead of Settings.load() (tests, snapshots)
        self.connect("handle-local-options", self._local_options)

    # -- lifecycle ---------------------------------------------------------
    def _local_options(self, _app, options: GLib.VariantDict) -> int:
        if options.contains("capture"):
            self.register(None)
            if self.get_is_remote():
                self.activate_action("capture-region", None)
                return 0
            self._capture_on_start = True
        return -1

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        icon_loader.install()
        icon_loader.install_css()
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._install_actions()
        for action, accels in ACCELS.items():
            self.set_accels_for_action(action, accels)

    def do_activate(self) -> None:
        from ..ui.studio_window import StudioWindow
        win = self.props.active_window or StudioWindow(self, self.settings)
        win.present()
        if self._capture_on_start:
            self._capture_on_start = False
            self.activate_action("capture-region", None)

    # -- actions -----------------------------------------------------------
    def _install_actions(self) -> None:
        quit_ = Gio.SimpleAction.new("quit", None)
        quit_.connect("activate", lambda *_: self.quit())
        self.add_action(quit_)
        for name, phase in APP_PLACEHOLDERS.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, n=name, p=phase: self._placeholder(n, p))
            self.add_action(a)

    def _placeholder(self, name: str, phase: int) -> None:
        win = self.props.active_window
        if win is not None and hasattr(win, "toast"):
            label = "Settings" if name == "preferences" else name.replace("-", " ").capitalize()
            win.toast(f"{label} arrives in Phase {phase}")
