"""The Studio window: header (title bar), tool rail, stage, panel rail."""
from __future__ import annotations
from gi.repository import Adw, Gio, GLib, Gtk

from .header_bar import HeaderBar
from .tool_rail import ToolRail
from .panel_rail import PanelRail
from .stage import Stage
from ..app.view_state import ViewState, TOOLS
from ..model.settings import Settings
from ..model.captures_index import CapturesIndex

MIN_WIDTH, MIN_HEIGHT = 960, 600
AUTO_COLLAPSE_BELOW = 1100
CAPTURE_MODES = ("region", "window", "screen", "scrolling", "delayed")

# action -> phase that implements it (placeholders show a toast until then)
PLACEHOLDERS = {
    "save": 5, "copy": 5, "discard": 5, "flatten": 5, "resize": 5, "rotate": 5, "adjust": 5,
    "duplicate-file": 5, "library-open": 5, "library-delete": 5, "undo": 4, "redo": 4, "eyedropper": 4,
    "custom-colour": 4,
}


class StudioWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, settings: Settings | None = None):
        super().__init__(application=app, title="LinScreenCapture")
        self.add_css_class("studio")
        self.settings = settings or Settings.load()
        self.state = ViewState()
        self.state.left_collapsed = self.settings.left_collapsed
        self.state.right_collapsed = self.settings.right_collapsed
        self.captures = CapturesIndex(self.settings.screenshot_path)

        self.set_default_size(max(self.settings.window_width, MIN_WIDTH), max(self.settings.window_height, MIN_HEIGHT))
        self.set_size_request(MIN_WIDTH, MIN_HEIGHT)
        if self.settings.window_maximized:
            self.maximize()

        self.header = HeaderBar(self.state)
        self.set_titlebar(self.header)

        self.toasts = Adw.ToastOverlay()
        self.breakpoint_bin = Adw.BreakpointBin()
        self.breakpoint_bin.set_size_request(MIN_WIDTH, MIN_HEIGHT)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.tool_rail = ToolRail(self.state)
        self.stage = Stage(self.state, self.captures)
        self.panel_rail = PanelRail(self.state)
        body.append(self.tool_rail)
        body.append(self.stage)
        body.append(self.panel_rail)
        self.breakpoint_bin.set_child(body)
        self.toasts.set_child(self.breakpoint_bin)
        self.set_child(self.toasts)

        self.breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {AUTO_COLLAPSE_BELOW}px"))
        self.breakpoint.connect("apply", self._bp_apply)
        self.breakpoint.connect("unapply", self._bp_unapply)
        self.breakpoint_bin.add_breakpoint(self.breakpoint)

        self._install_actions()
        self.connect("close-request", self._on_close)
        self.captures.scan()

    # -- actions -----------------------------------------------------------
    def _install_actions(self) -> None:
        tool = self._stateful("tool", self.state.tool, TOOLS, lambda v: setattr(self.state, "tool", v))
        # programmatic state changes (tests, later phases) must move the toggles too
        self.state.connect("notify::tool", lambda s, _p: tool.set_state(GLib.Variant("s", s.tool)))
        self._stateful("capture-mode", "region", CAPTURE_MODES, lambda v: None)
        self._simple("toggle-left-rail", lambda: self.state.toggle_rail("left"))
        self._simple("toggle-right-rail", lambda: self.state.toggle_rail("right"))
        self._simple("zoom-in", lambda: self.state.zoom_step(+1))
        self._simple("zoom-out", lambda: self.state.zoom_step(-1))
        self._simple("zoom-fit", lambda: setattr(self.state, "zoom", 1.0))
        self._simple("zoom-actual", lambda: setattr(self.state, "zoom", 1.0))
        self._simple("library-refresh", self.captures.scan)
        lib = Gio.SimpleAction.new_stateful("library", None, GLib.Variant("b", False))
        lib.connect("change-state", self._library_change)
        lib.connect("activate", lambda a, _p: a.change_state(GLib.Variant("b", not a.get_state().get_boolean())))
        self.add_action(lib)
        self.state.connect("notify::library", lambda s, _p: lib.set_state(GLib.Variant("b", s.library)))
        for name, phase in PLACEHOLDERS.items():
            self._simple(name, lambda n=name, p=phase: self.toast(f"{n.replace('-', ' ').capitalize()} arrives in Phase {p}"))

    def _simple(self, name: str, cb) -> Gio.SimpleAction:
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", lambda *_: cb())
        self.add_action(a)
        return a

    def _stateful(self, name: str, initial: str, allowed, cb) -> Gio.SimpleAction:
        a = Gio.SimpleAction.new_stateful(name, GLib.VariantType.new("s"), GLib.Variant("s", initial))

        def change(action, value):
            v = value.get_string()
            if v in allowed:
                action.set_state(value)
                cb(v)
        a.connect("change-state", change)
        self.add_action(a)
        return a

    def _library_change(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        show = value.get_boolean()
        action.set_state(value)
        self.state.library = show
        self.state.title = "Library" if show else "LinScreenCapture"
        if show:
            self.captures.scan()

    # -- responsive rails --------------------------------------------------
    def _bp_apply(self, *_a) -> None:
        if not self.state.left_manual:
            self.state.left_collapsed = True
        if not self.state.right_manual:
            self.state.right_collapsed = True

    def _bp_unapply(self, *_a) -> None:
        if not self.state.left_manual:
            self.state.left_collapsed = False
        if not self.state.right_manual:
            self.state.right_collapsed = False

    # -- helpers -----------------------------------------------------------
    def toast(self, text: str, timeout: int = 3) -> None:
        t = Adw.Toast.new(text)
        t.set_timeout(timeout)
        self.toasts.add_toast(t)

    def _on_close(self, *_a) -> bool:
        s = self.settings
        s.window_maximized = self.is_maximized()
        if not s.window_maximized and self.get_width() > 0 and self.get_height() > 0:
            s.window_width, s.window_height = self.get_width(), self.get_height()
        s.left_collapsed = self.state.left_collapsed
        s.right_collapsed = self.state.right_collapsed
        try:
            s.save()
        except Exception as exc:  # never block closing on a settings write
            print(f"settings not saved: {exc}")
        return False
