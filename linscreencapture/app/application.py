"""Adw.Application: single instance, actions, accelerators, --capture activation, background agent.

The primary instance is the agent. With ``Settings.keep_running`` it holds itself alive with no window (closing the
studio only hides it) and starts the status-icon helper (``linscreencapture.tray``). ``--background`` starts the agent
without a window; ``--capture`` (the PrintScreen binding) runs a hotkey capture: region, saved and copied to the
clipboard, the studio left as it was, unless ``Settings.hotkey_opens_editor`` asks for the editor.
"""
from __future__ import annotations
from gi.repository import Adw, Gio, GLib, Gtk

import logging
import os
import sys
import time

from .. import APP_ID
from ..services import icon_loader
from . import logging_setup

LOG = logging.getLogger("linscreencapture.app")

APP_PLACEHOLDERS = {"capture-scrolling": 6, "pin": 6}
CAPTURE_ACTIONS = {"capture": None, "capture-region": "region", "capture-window": "window",
                   "capture-screen": "screen", "capture-delayed": "delayed"}
ACCELS = {
    # Global chords only. Tool letters and editing keys (Ctrl+C/V/Z/Y/D, Delete, Escape) are routed by
    # app/shortcuts.py in the bubble phase so they never steal keystrokes from a text field.
    "app.quit": ["<Control>q"],
    "app.preferences": ["<Control>comma"],
    "app.capture": ["<Control>n"],
    "app.capture-screen": ["<Control><Shift>n"],
    "win.save": ["<Control>s"],
    "win.save-as": ["<Control><Shift>s"],
    "win.library": ["<Control>l"],
    "win.toggle-left-rail": ["<Control>bracketleft"],
    "win.toggle-right-rail": ["<Control>bracketright"],
    "win.zoom-in": ["<Control>plus", "<Control>equal"],
    "win.zoom-out": ["<Control>minus"],
    "win.zoom-fit": ["<Control>0"],
    "win.zoom-actual": ["<Control>1"],
}


class Application(Adw.Application):
    def __init__(self, non_unique: bool = False):
        # non_unique: tools (snapshots, probes) must never activate a running instance instead of starting
        flags = Gio.ApplicationFlags.NON_UNIQUE if non_unique else Gio.ApplicationFlags.DEFAULT_FLAGS
        super().__init__(application_id=APP_ID, flags=flags)
        self.add_main_option("capture", ord("c"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Capture a region immediately", None)
        self.add_main_option("background", ord("b"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Run as the background agent: no window, tray icon, PrintScreen captures", None)
        self.add_main_option("debug", ord("d"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Verbose logging of start-up, toolkits and captures (also LSC_DEBUG=1)", None)
        self._capture_on_start = False
        self._background = False
        self._agent = False          # hold() taken: the instance outlives its window
        self._tray = None            # Gio.Subprocess of the status-icon helper
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
                self.activate_action("hotkey-capture", None)
                return 0
            self._capture_on_start = True
        if options.contains("background"):
            self.register(None)
            if self.get_is_remote():
                LOG.debug("background: an agent is already running")
                return 0
            self._background = True
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
        if s.keep_running or self._background or self._capture_on_start:
            self.become_agent()
        LOG.debug("startup done in %.0f ms", (time.monotonic() - t0) * 1000)

    def do_activate(self) -> None:
        if self._capture_on_start and not self.settings.hotkey_opens_editor:
            self._capture_on_start = False
            self._background = False
            self.hotkey_capture()                       # PrintScreen with no agent running: no window at all
            return
        if self._background:
            self._background = False
            LOG.debug("background: agent started without a window")
            return
        self.show_editor()

    def show_editor(self) -> None:
        from ..ui.studio_window import StudioWindow
        t0 = time.monotonic()
        existing = self.props.active_window
        win = existing or StudioWindow(self, self.settings)
        if existing is None and self._agent and self.settings.keep_running:
            win.set_hide_on_close(True)                 # the agent keeps the document; Quit ends it
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

    def hotkey_capture(self) -> None:
        """PrintScreen: a region to the clipboard and the save folder; the studio stays as it was."""
        if self.settings.hotkey_opens_editor:
            if self.props.active_window is None:
                self._capture_on_start = True
                self.show_editor()
            else:
                self.capture_controller.capture("region")
            return
        self.capture_controller.capture("region", quiet=True)

    # -- agent -------------------------------------------------------------
    def become_agent(self) -> None:
        if not self._agent:
            self._agent = True
            self.hold()
            LOG.debug("agent: holding the application (keep running without a window)")
        self.update_tray()

    def update_tray(self) -> None:
        """Start or stop the status-icon helper to match ``Settings.tray_icon``."""
        want = self._agent and self.settings.tray_icon and os.environ.get("LSC_NO_TRAY") != "1"
        if want and self._tray is None:
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.NONE)
            pkg_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.environ.get("PYTHONPATH")
            launcher.setenv("PYTHONPATH", pkg_parent + (os.pathsep + path if path else ""), True)
            try:
                self._tray = launcher.spawnv([sys.executable, "-m", "linscreencapture.tray"])
                LOG.debug("agent: status icon helper started (pid %s)", self._tray.get_identifier())
            except GLib.Error as exc:
                LOG.warning("status icon unavailable: %s", exc.message)
        elif not want and self._tray is not None:
            self._tray.force_exit()
            self._tray = None

    def do_shutdown(self) -> None:
        if self._tray is not None:
            self._tray.force_exit()
            self._tray = None
        Adw.Application.do_shutdown(self)

    # -- actions -----------------------------------------------------------
    def _install_actions(self) -> None:
        quit_ = Gio.SimpleAction.new("quit", None)
        quit_.connect("activate", lambda *_: self.quit())
        self.add_action(quit_)
        for name, phase in APP_PLACEHOLDERS.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, n=name, p=phase: self._placeholder(n, p))
            self.add_action(a)
        prefs = Gio.SimpleAction.new("preferences", None)
        prefs.connect("activate", lambda *_: self._open_preferences())
        self.add_action(prefs)
        for name, mode in CAPTURE_ACTIONS.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, m=mode: self.capture_controller.capture(m))
            self.add_action(a)
        hotkey = Gio.SimpleAction.new("hotkey-capture", None)     # PrintScreen, --capture, the tray
        hotkey.connect("activate", lambda *_: self.hotkey_capture())
        self.add_action(hotkey)
        editor = Gio.SimpleAction.new("show-editor", None)        # the tray's Open editor
        editor.connect("activate", lambda *_: self.show_editor())
        self.add_action(editor)

    def _open_preferences(self) -> None:
        from ..ui.preferences import PreferencesDialog
        win = self.props.active_window
        if win is None:
            return
        def changed(field, value):
            win.settings_changed(field, value)
            if field in ("keep_running", "tray_icon"):
                if self.settings.keep_running:
                    self.become_agent()
                win.set_hide_on_close(bool(self.settings.keep_running and self._agent))
                self.update_tray()
        dialog = PreferencesDialog(self.settings, on_change=changed)
        self.preferences_dialog = dialog
        dialog.present(win)

    def _placeholder(self, name: str, phase: int) -> None:
        win = self.props.active_window
        if win is not None and hasattr(win, "toast"):
            label = "Settings" if name == "preferences" else name.replace("-", " ").capitalize()
            win.toast(f"{label} arrives in Phase {phase}")
