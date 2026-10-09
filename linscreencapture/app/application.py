"""Adw.Application: single instance, actions, accelerators, --capture activation."""
from __future__ import annotations
from gi.repository import Adw, Gio, GLib, Gtk

import logging
import time

from .. import APP_ID
from ..services import icon_loader
from . import logging_setup

LOG = logging.getLogger("linscreencapture.app")

APP_PLACEHOLDERS = {"capture-scrolling": 6, "pin": 6, "preferences": 6}
CAPTURE_ACTIONS = {"capture": None, "capture-region": "region", "capture-window": "window",
                   "capture-screen": "screen", "capture-delayed": "delayed"}
ACCELS = {
    "app.quit": ["<Control>q"],
    "app.preferences": ["<Control>comma"],
    "app.capture": ["<Control>n"],
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
        self.add_main_option("debug", ord("d"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Verbose logging of start-up, toolkits and captures (also LSC_DEBUG=1)", None)
        self._capture_on_start = False
        self.settings = None  # a Settings instance to use instead of Settings.load() (tests, snapshots)
        self.capture_controller = None
        self.connect("handle-local-options", self._local_options)

    # -- lifecycle ---------------------------------------------------------
    def _local_options(self, _app, options: GLib.VariantDict) -> int:
        debug = logging_setup.setup(True if options.contains("debug") else None)
        if debug:
            for k, v in logging_setup.describe_environment().items():
                LOG.debug("%-11s %s", k, v)
        if options.contains("capture"):
            self.register(None)
            if self.get_is_remote():
                self.activate_action("capture-region", None)
                return 0
            self._capture_on_start = True
        return -1

    def do_startup(self) -> None:
        t0 = time.monotonic()
        Adw.Application.do_startup(self)
        LOG.debug("startup: primary instance, app id %s", APP_ID)
        icon_loader.install()
        LOG.debug("resources: %s (%d icons)", icon_loader.resource_path(), len(icon_loader.icon_names()))
        icon_loader.install_css()
        LOG.debug("stylesheet: style.css loaded at USER priority; dark scheme forced")
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        if self.settings is None:
            from ..model.settings import Settings
            self.settings = Settings.load()
        s = self.settings
        LOG.debug("settings: %s%s", s.path, " (exists)" if s.path.is_file() else " (defaults)")
        if s.migrated_from:
            LOG.info("settings migrated from %s", s.migrated_from)
        LOG.debug("settings: save folder %s · prefix %s · %s · %s · backend %s · window %dx%d%s",
                  s.screenshot_path, s.prefix, s.numbering, s.format, s.backend, s.window_width, s.window_height,
                  " maximized" if s.window_maximized else "")
        from .capture_controller import CaptureController
        self.capture_controller = CaptureController(self)
        from ..services.capture_service import CaptureService
        svc = CaptureService(s.backend)
        self.capture_controller.service = svc
        LOG.debug("capture: session %s · backends in order: %s", svc.session,
                  ", ".join(b.name for b in svc.order()) or "none available")
        self._install_actions()
        for action, accels in ACCELS.items():
            self.set_accels_for_action(action, accels)
        LOG.debug("actions: %d app actions, %d accelerators", len(self.list_actions()), len(ACCELS))
        LOG.debug("startup done in %.0f ms", (time.monotonic() - t0) * 1000)

    def do_activate(self) -> None:
        from ..ui.studio_window import StudioWindow
        t0 = time.monotonic()
        existing = self.props.active_window
        win = existing or StudioWindow(self, self.settings)
        if existing is None:
            LOG.debug("window: built in %.0f ms (%d win actions, rails %s/%s)", (time.monotonic() - t0) * 1000,
                      len(win.list_actions()), "collapsed" if win.state.left_collapsed else "open",
                      "collapsed" if win.state.right_collapsed else "open")
        else:
            LOG.debug("activate: raising the existing window")
        if self._capture_on_start:
            self._capture_on_start = False
            self.capture_controller.capture("region")   # the window appears with the result
        else:
            win.present()

    # -- actions -----------------------------------------------------------
    def _install_actions(self) -> None:
        quit_ = Gio.SimpleAction.new("quit", None)
        quit_.connect("activate", lambda *_: self.quit())
        self.add_action(quit_)
        for name, phase in APP_PLACEHOLDERS.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, n=name, p=phase: self._placeholder(n, p))
            self.add_action(a)
        for name, mode in CAPTURE_ACTIONS.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, m=mode: self.capture_controller.capture(m))
            self.add_action(a)

    def _placeholder(self, name: str, phase: int) -> None:
        win = self.props.active_window
        if win is not None and hasattr(win, "toast"):
            label = "Settings" if name == "preferences" else name.replace("-", " ").capitalize()
            win.toast(f"{label} arrives in Phase {phase}")
