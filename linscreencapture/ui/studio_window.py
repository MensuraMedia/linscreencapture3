"""The Studio window: header (title bar), tool rail, stage, panel rail."""
from __future__ import annotations
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .header_bar import HeaderBar
from .tool_rail import ToolRail
from .panel_rail import PanelRail
from .stage import Stage
from ..app.view_state import ViewState, TOOLS
from ..model.settings import Settings
from ..model.captures_index import CapturesIndex
from ..model.document import Document
from ..services import clipboard
from ..model.undo import UndoStack
from ..app.editor_controller import EditorController

MIN_WIDTH, MIN_HEIGHT = 960, 600
AUTO_COLLAPSE_BELOW = 1100
CAPTURE_MODES = ("region", "window", "screen", "scrolling", "delayed")

# action -> phase that implements it (placeholders show a toast until then)
PLACEHOLDERS = {
    "save": 5, "flatten": 5, "resize": 5, "rotate": 5, "adjust": 5,
    "duplicate-file": 5, "library-delete": 5, "eyedropper": 4,
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
        self.document: Document | None = None

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
        self.panel_rail.attach_stage(self.stage)
        self.undo: UndoStack | None = None
        self.editor = EditorController(self)
        self.panel_rail.bind_editor(self.editor)
        self.header.props.bind(self.settings, self.editor)
        self.toasts.set_child(self.breakpoint_bin)
        self.set_child(self.toasts)

        self.breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {AUTO_COLLAPSE_BELOW}px"))
        self.breakpoint.connect("apply", self._bp_apply)
        self.breakpoint.connect("unapply", self._bp_unapply)
        self.breakpoint_bin.add_breakpoint(self.breakpoint)

        self._install_actions()
        self.connect("close-request", self._on_close)
        self.captures.scan()
        self.state.colour = self.settings.tools["arrow"].colour
        self.state.connect("notify::colour", self._persist_colour)

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
        self._simple("zoom-fit", lambda: setattr(self.state, "zoom", self.stage.fit_zoom()))
        self._simple("zoom-actual", lambda: setattr(self.state, "zoom", 1.0))
        self._simple("library-refresh", self.captures.scan)
        self._simple("library-open", self._library_open)
        self._simple("copy", self._copy)
        self._simple("discard", self._discard)
        self._simple("undo", self._undo)
        self._simple("redo", self._redo)
        self._simple("delete-layer", lambda: self.editor.delete_selected() or self.toast("Select a layer first"))
        self._simple("duplicate-layer", lambda: self.editor.duplicate_selected() or self.toast("Select a layer first"))
        self._simple("custom-colour", self._custom_colour)
        self.lookup_action("undo").set_enabled(False)
        self.lookup_action("redo").set_enabled(False)
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

    # -- document ----------------------------------------------------------
    def load_document(self, doc: Document) -> None:
        self.document = doc
        self.undo = UndoStack(doc, on_change=self._undo_changed)
        self.editor.selected_id = None
        self.stage.set_document(doc)
        self.panel_rail.set_document(doc)
        self._undo_changed()
        self.state.title = doc.name
        self.state.subtitle = doc.summary()
        if self.state.library:
            self.state.library = False
            self.lookup_action("library").set_state(GLib.Variant("b", False))
            self.state.title = doc.name
        GLib.idle_add(lambda: (setattr(self.state, "zoom", self.stage.fit_zoom()), False)[1])

    def clear_document(self) -> None:
        self.document = None
        self.undo = None
        self.editor.selected_id = None
        self._undo_changed()
        self.stage.set_document(None)
        self.panel_rail.set_document(None)
        self.state.title = "LinScreenCapture"
        self.state.subtitle = ""
        self.state.zoom = 1.0

    def settings_changed(self, field: str, value) -> None:
        """Live reactions to the Settings dialog (the dialog already saved the file)."""
        if field == "screenshot_path":
            self.captures.folder = value
            self.captures.scan()
        elif field in ("left_collapsed", "right_collapsed"):
            self.state.set_property(field, bool(value))
            self.state.set_property(field.replace("collapsed", "manual"), True)

    def refresh_document(self) -> None:
        """After an edit: re-composite the stage, refresh the subtitle and the layer list."""
        self.stage.refresh()
        if self.document is not None:
            self.state.subtitle = self.document.summary()
            self.panel_rail.set_document(self.document, self.editor.selected_id)

    def _undo_changed(self) -> None:
        u = self.undo
        self.lookup_action("undo").set_enabled(bool(u and u.can_undo))
        self.lookup_action("redo").set_enabled(bool(u and u.can_redo))

    def _undo(self) -> None:
        if self.undo and self.undo.can_undo:
            label = self.undo.undo_label
            self.undo.undo()
            if self.editor.selected_layer() is None:
                self.editor.selected_id = None
            self.refresh_document()
            self.toast(f"Undo {label.lower()}", timeout=2)

    def _redo(self) -> None:
        if self.undo and self.undo.can_redo:
            self.undo.redo()
            self.refresh_document()

    def _custom_colour(self) -> None:
        dialog = Gtk.ColorDialog(title="Custom colour", with_alpha=False)
        rgba = Gdk.RGBA()
        rgba.parse(self.state.colour)
        dialog.choose_rgba(self, rgba, None, self._custom_colour_done)

    def _custom_colour_done(self, dialog: Gtk.ColorDialog, result) -> None:
        try:
            rgba = dialog.choose_rgba_finish(result)
        except GLib.Error:
            return
        self.state.colour = "#%02x%02x%02x" % (round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))

    def _library_open(self) -> None:
        entry = self.stage.library.selected
        if entry is None:
            self.toast("Select a screenshot first")
            return
        try:
            doc = Document.open(entry.path)
        except Exception as exc:  # noqa: BLE001
            self.toast(f"Could not open {entry.name}: {exc}", timeout=5)
            return
        self.load_document(doc)

    def _copy(self) -> None:
        if self.document is None or self.document.empty:
            self.toast("Nothing to copy yet")
            return
        if clipboard.copy_surface(self.document.flatten()):
            self.toast(f"Copied {self.document.name} to clipboard")
        else:
            self.toast("Clipboard not available", timeout=5)

    def _discard(self) -> None:
        if self.document is None:
            return
        # Phase 5 adds the unsaved-changes prompt; captures are saved on disk already
        self.clear_document()
        self.toast("Stage cleared")

    # -- responsive rails --------------------------------------------------
    def _bp_apply(self, *_a) -> None:
        """Narrow window: collapse both rails, remembering what to restore when it widens again."""
        self._before_breakpoint = (self.state.left_collapsed, self.state.right_collapsed)
        if not self.state.left_manual:
            self.state.left_collapsed = True
        if not self.state.right_manual:
            self.state.right_collapsed = True

    def _bp_unapply(self, *_a) -> None:
        left, right = getattr(self, "_before_breakpoint", (self.state.left_collapsed, self.state.right_collapsed))
        if not self.state.left_manual:
            self.state.left_collapsed = left
        if not self.state.right_manual:
            self.state.right_collapsed = right

    # -- helpers -----------------------------------------------------------
    def toast(self, text: str, timeout: int = 3) -> None:
        t = Adw.Toast.new(text)
        t.set_timeout(timeout)
        self.toasts.add_toast(t)

    def _persist_colour(self, s, _p) -> None:
        for ts in self.settings.tools.values():
            ts.colour = s.colour
        try:
            self.settings.save()
        except Exception:  # noqa: BLE001
            pass

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
