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
from ..services.clip_history import ClipHistory
from ..services.file_store import duplicate_file
from ..services.tags import TagStore
from ..model.undo import UndoStack, ReplaceBase, TransformBase, AddLayer
from ..app import image_ops
from .popovers import ResizePopover, RotatePopover, AdjustPopover
import os
from ..app.editor_controller import EditorController
from ..app.shortcuts import ShortcutRouter

MIN_WIDTH, MIN_HEIGHT = 960, 600
AUTO_COLLAPSE_BELOW = 1100
CAPTURE_MODES = ("region", "region-plus", "window", "screen", "scrolling")

# action -> phase that implements it (placeholders show a toast until then)
PLACEHOLDERS = {"duplicate-file": 7}


class StudioWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, settings: Settings | None = None):
        super().__init__(application=app, title="LinScreenCapture")
        self.add_css_class("studio")
        self.settings = settings or Settings.load()
        self.state = ViewState()
        self.state.left_collapsed = self.settings.left_collapsed
        self.state.right_collapsed = self.settings.right_collapsed
        try:                                          # the save folder (default ~/Pictures/ScreenShots) exists from the start
            os.makedirs(os.path.expanduser(self.settings.screenshot_path), exist_ok=True)
        except OSError:
            pass
        self.captures = CapturesIndex(self.settings.screenshot_path)
        self.tags = TagStore.load(self.settings.root)     # Library tags (tags.json; under the test root in tests)
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
        self.clips = ClipHistory()                    # the last four copies, shown in the left rail's 2 × 2 tray
        self.tool_rail = ToolRail(self.state, self.clips, self._paste_clip)
        self.stage = Stage(self.state, self.captures, self.tags)
        self.panel_rail = PanelRail(self.state)
        body.append(self.tool_rail)
        body.append(self.stage)
        body.append(self.panel_rail)
        self.breakpoint_bin.set_child(body)
        self.panel_rail.attach_stage(self.stage)
        self.panel_rail.bind_library(self.stage.library, self.tags)
        self.undo: UndoStack | None = None
        self.editor = EditorController(self)
        self.panel_rail.bind_editor(self.editor)
        self.editor.on_selection.append(lambda _id: self._arrange_changed())
        self.editor.on_selection.append(lambda _id: self._shape_fill_sync())
        self.header.props.bind(self.settings, self.editor)
        self.shortcuts = ShortcutRouter(self)
        self._layer_clip = None                       # a copied layer, valid until the clipboard changes elsewhere
        display = Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().connect("changed", lambda *_: setattr(self, "_layer_clip", None))
        self.toasts.set_child(self.breakpoint_bin)
        self.set_child(self.toasts)

        self.breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {AUTO_COLLAPSE_BELOW}px"))
        self.breakpoint.connect("apply", self._bp_apply)
        self.breakpoint.connect("unapply", self._bp_unapply)
        self.breakpoint_bin.add_breakpoint(self.breakpoint)

        self._install_actions()
        self._undo_changed()                          # undo/redo, arrange and Page start disabled (no document)
        self.stage.set_stage_colour(self.settings.stage_colour)
        self.connect("close-request", self._on_close)
        # keyboard focus starts on the canvas, never on a rail button (Space/Enter would activate it)
        self.connect("map", lambda *_: GLib.idle_add(lambda: (self.stage.canvas.grab_focus(), False)[1]))
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
        self._simple("eyedropper", lambda: self.editor.start_eyedropper())
        self._simple("crop-apply", lambda: self.editor.apply_crop() or self.toast("Drag a crop rectangle first"))
        self._simple("crop-cancel", lambda: self.editor.cancel_crop())
        self._simple("flatten", self._flatten)
        self._simple("save", self._save)
        self._simple("save-as", self._save_as)
        self._simple("paste", self._paste)
        self._simple("library-delete", self._library_delete)
        self._simple("library-copy", self._library_copy)
        self._simple("library-duplicate", self._library_duplicate)
        self._simple("library-select-all", self._library_select_all)
        self._simple("library-clear", lambda: self.stage.library.clear_selection())
        self._simple("library-combine", self._library_combine)
        self._simple("library-rename", self._library_rename)
        self._simple("library-tag", self._library_tag)
        self._simple("library-show", self._library_show)
        self._simple("select-all", self._select_all)
        self._simple("resize", lambda: self._popover("resize"))
        self._simple("rotate", lambda: self._popover("rotate"))
        self._simple("adjust", lambda: self._popover("adjust"))
        self._simple("layer-rotate-left", lambda: self.editor.rotate_selected(-90) or self.toast("Select a pasted image first"))
        self._simple("layer-rotate-right", lambda: self.editor.rotate_selected(90) or self.toast("Select a pasted image first"))
        self._simple("page-settings", self._page_settings)
        self._stateful("shape-fill", "filled" if self.settings.tools["box"].fill else "outline", ("outline", "filled"),
                       self._shape_fill)
        for where in ("front", "forward", "backward", "back"):
            self._simple(f"layer-{where}", lambda w=where: self.editor.arrange_selected(w))
        self._popovers: dict = {}
        self.lookup_action("undo").set_enabled(False)
        self.lookup_action("redo").set_enabled(False)
        delayed = Gio.SimpleAction.new_stateful("capture-delayed", None, GLib.Variant("b", False))
        delayed.connect("change-state", self._delayed_change)
        delayed.connect("activate", lambda a, _p: a.change_state(GLib.Variant("b", not a.get_state().get_boolean())))
        self.add_action(delayed)
        lib = Gio.SimpleAction.new_stateful("library", None, GLib.Variant("b", False))
        lib.connect("change-state", self._library_change)
        lib.connect("activate", lambda a, _p: a.change_state(GLib.Variant("b", not a.get_state().get_boolean())))
        self.add_action(lib)
        self.state.connect("notify::library", lambda s, _p: lib.set_state(GLib.Variant("b", s.library)))
        for name, phase in PLACEHOLDERS.items():
            self._simple(name, lambda n=name, p=phase: self.toast(f"{n.replace('-', ' ').capitalize()} arrives in Phase {p}"))

    def _delayed_change(self, action, value) -> None:
        action.set_state(value)
        if value.get_boolean():
            if self.settings.delay_seconds <= 0:
                self.toast("Delayed capture on, but the delay is 0 s · set the seconds in Settings → Capture", timeout=5)
            else:
                self.toast(f"Delayed capture on · waits {self.settings.delay_seconds} s · click the timer again to turn it off")
        else:
            self.toast("Delayed capture off", timeout=2)

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
            # focus the grid, not the search field (the first focusable widget): tool letters, Esc, F2 and
            # Delete must reach the Library, and a click in the field is all it takes to type a filter
            GLib.idle_add(lambda: (self.stage.library.grid.grab_focus(), False)[1])

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
        # a new capture, an opened file, a paste or a Combine opens at 100 %, scrolled to the top-left corner. (It used to
        # fit on the next idle; after a capture the window is still hidden then, so the fit came out tiny.)
        self.state.zoom = 1.0
        self.stage.scroll_to_start()

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
        elif field == "selection_frame":
            self.stage.canvas.queue_draw()
        elif field in ("left_collapsed", "right_collapsed"):
            self.state.set_property(field, bool(value))
            self.state.set_property(field.replace("collapsed", "manual"), True)

    def refresh_document(self) -> None:
        """After an edit: re-composite the stage, refresh the subtitle and the layer list."""
        self.stage.refresh()
        if self.document is not None:
            self.state.subtitle = self.document.summary()
            self.panel_rail.set_document(self.document, self.editor.selected_id)
            self.header.props.reload()               # undo / redo: the strip shows the selected layer's values again
            self._shape_fill_sync()

    def _undo_changed(self) -> None:
        u = self.undo
        self.lookup_action("undo").set_enabled(bool(u and u.can_undo))
        self.lookup_action("redo").set_enabled(bool(u and u.can_redo))
        self._arrange_changed()
        action = self.lookup_action("page-settings")
        if action is not None:
            action.set_enabled(self.document is not None and not self.document.empty)

    # -- shape fill (right rail, under the colour swatches) -------------------------------
    SHAPES = ("box", "circle")

    def _shape_fill(self, value: str) -> None:
        """Outline or Filled: the selected box / circle changes (one undo step), and new boxes and circles follow."""
        filled = value == "filled"
        for tool in self.SHAPES:
            self.settings.tools[tool].fill = filled
        try:
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            print(f"settings not saved: {exc}")
        layer = self.editor.selected_layer()
        if layer is not None and layer.annotation.kind in self.SHAPES and layer.annotation.style.fill != filled:
            self.editor.apply_style({"fill": filled})

    def _shape_fill_sync(self) -> None:
        """Show the selected shape's fill, else the default for new shapes."""
        action = self.lookup_action("shape-fill")
        if action is None:
            return
        layer = self.editor.selected_layer() if self.document is not None else None
        filled = (layer.annotation.style.fill if layer is not None and layer.annotation.kind in self.SHAPES
                  else self.settings.tools["box"].fill)
        action.set_state(GLib.Variant("s", "filled" if filled else "outline"))

    def _page_settings(self) -> None:
        from .page_dialog import PageDialog
        if self.document is not None and not self.document.empty:
            self.page_dialog = PageDialog(self.editor)
            self.page_dialog.present(self)

    def _arrange_changed(self) -> None:
        """The four arrange actions are enabled only when the selected layer can move that way."""
        for where in ("front", "forward", "backward", "back"):
            action = self.lookup_action(f"layer-{where}")
            if action is not None:
                action.set_enabled(self.editor.can_arrange(where))

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
        lib = self.stage.library
        entry, lib.activated_entry = lib.activated_entry or lib.selected, None
        if entry is None:
            self.toast("Select a screenshot first")
            return
        self.confirm_discard(lambda: self._open_path(entry.path, entry.name))

    def _library_select_all(self) -> None:
        n = self.stage.library.select_all()
        self.toast(f"{n} selected · Ctrl+C copies, Ctrl+D duplicates, Delete trashes", timeout=3)

    def _library_copy(self) -> None:
        """One image: pixels + file on the clipboard (and in the tray). Several: the files (for file managers)."""
        entries = self.stage.library.selected_entries
        if not entries:
            self.toast("Select a screenshot first")
            return
        display = Gdk.Display.get_default()
        if display is None:
            self.toast("Clipboard not available", timeout=5)
            return
        files = Gdk.FileList.new_from_list([Gio.File.new_for_path(e.path) for e in entries])
        uris = "".join(f"file://{GLib.uri_escape_string(e.path, '/', True)}\r\n" for e in entries)
        providers = [Gdk.ContentProvider.new_for_value(files),
                    Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(uris.encode()))]
        if len(entries) == 1:
            try:
                from ..model.document import load_image
                surface = load_image(entries[0].path)
            except Exception as exc:  # noqa: BLE001
                self.toast(f"Could not read {entries[0].name}: {exc}", timeout=5)
                return
            clipboard.set_providers(clipboard.image_providers(surface) + providers)
            self.clips.push(surface, entries[0].name)
            self.toast(f"Copied {entries[0].name} to the clipboard")
        else:
            clipboard.set_providers(providers)
            self.toast(f"Copied {len(entries)} files to the clipboard (paste them in a file manager)")

    def _library_duplicate(self) -> None:
        entries = self.stage.library.selected_entries
        if not entries:
            self.toast("Select a screenshot first")
            return
        made = []
        for e in entries:
            try:
                copy = duplicate_file(e.path)
                self.tags.copy(e.path, copy)
                made.append(os.path.basename(copy))
            except OSError as exc:
                self.toast(f"Could not duplicate {e.name}: {exc}", timeout=5)
                break
        self.captures.scan()
        if len(made) == 1:
            self.toast(f"Duplicated as {made[0]}")
        elif made:
            self.toast(f"Duplicated {len(made)} files")

    # -- library: combine, rename, tag, show -------------------------------------------
    def _library_combine(self) -> None:
        """Tile the selected images on one new page, 10 px apart, each an image layer (``app/tiling.py``)."""
        entries = self.stage.library.selected_entries
        if len(entries) < 2:
            self.toast("Select two or more images to combine · Ctrl+click adds to the selection", timeout=3)
            return
        self.confirm_discard(lambda: self.combine([e.path for e in entries]))

    def combine(self, paths: list[str]) -> bool:
        import cairo
        from ..app.tiling import tile
        from ..model.annotations import Annotation
        from ..model.document import load_image, MAX_PAGE
        try:
            surfaces = [load_image(p) for p in paths]
        except Exception as exc:  # noqa: BLE001
            self.toast(f"Could not read an image: {exc}", timeout=5)
            return False
        sizes = [(s.get_width(), s.get_height()) for s in surfaces]
        width, height, places = tile(sizes)
        if width > MAX_PAGE or height > MAX_PAGE:
            self.toast(f"Too large to combine ({width} × {height} px; the page limit is {MAX_PAGE} px)", timeout=5)
            return False
        doc = Document(cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height))
        style = self.settings.tool_style("image")
        style.shadow = False                         # shadows would crowd the 10 px gaps
        for surf, (x, y), (w, h) in zip(surfaces, places, sizes):
            doc.add_layer(Annotation("image", x, y, x + w, y + h, style=style.copy(), surface=surf))
        doc.dirty = True
        self.load_document(doc)
        self.state.title = f"Combined · {len(paths)} images"
        self.toast(f"Combined {len(paths)} images · each is a layer you can move · Page sets a fill behind them", timeout=4)
        return True

    def _library_rename(self) -> None:
        entries = self.stage.library.selected_entries
        if len(entries) != 1:
            self.toast("Select one image to rename", timeout=2)
            return
        e = entries[0]
        stem, ext = os.path.splitext(e.name)
        entry = Gtk.Entry(text=stem, activates_default=True)
        dlg = Adw.AlertDialog(heading=f"Rename {e.name}", body=f"The extension {ext} is kept.")
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("rename", "Rename")
        dlg.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("rename")

        def done(_d, response):
            if response == "rename":
                self.rename_file(e.path, entry.get_text())
        dlg.connect("response", done)
        dlg.present(self)
        entry.grab_focus()

    def rename_file(self, path: str, new_stem: str) -> str | None:
        """Rename ``path`` to ``new_stem`` + its extension in the same folder; tags and an open document follow."""
        stem = new_stem.strip()
        if not stem or "/" in stem or stem in (".", ".."):
            self.toast("Not a valid file name", timeout=3)
            return None
        target = os.path.join(os.path.dirname(path), stem + os.path.splitext(path)[1])
        if target == path:
            return None
        if os.path.exists(target):
            self.toast(f"{os.path.basename(target)} already exists", timeout=3)
            return None
        try:
            os.rename(path, target)
        except OSError as exc:
            self.toast(f"Could not rename: {exc.strerror}", timeout=5)
            return None
        self.tags.rename(path, target)
        if self.document is not None and self.document.path == path:
            self.document.path = target
        self.captures.scan()
        self.toast(f"Renamed to {os.path.basename(target)}", timeout=2)
        return target

    def _library_tag(self) -> None:
        entries = self.stage.library.selected_entries
        if not entries:
            self.toast("Select a screenshot first")
            return
        entry = Gtk.Entry(placeholder_text="e.g. bug report", activates_default=True)
        known = self.tags.all_tags()
        dlg = Adw.AlertDialog(heading="Add a tag", body=(f"To {entries[0].name}" if len(entries) == 1 else f"To {len(entries)} images")
                              + (f"\nIn use: {', '.join(known[:8])}" if known else ""))
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("add", "Add")
        dlg.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("add")

        def done(_d, response):
            if response == "add" and self.tags.add([e.path for e in entries], entry.get_text()):
                self.stage.library.tags_changed()
        dlg.connect("response", done)
        dlg.present(self)
        entry.grab_focus()

    def _library_show(self) -> None:
        entries = self.stage.library.selected_entries
        if not entries:
            self.toast("Select a screenshot first")
            return
        Gtk.FileLauncher(file=Gio.File.new_for_path(entries[0].path)).open_containing_folder(self, None, None)

    def _open_path(self, path: str, name: str) -> None:
        try:
            doc = Document.open(path)
        except Exception as exc:  # noqa: BLE001
            self.toast(f"Could not open {name}: {exc}", timeout=5)
            return
        self.load_document(doc)

    def _library_delete(self) -> None:
        entries = self.stage.library.selected_entries
        if not entries:
            self.toast("Select a screenshot first")
            return
        entry = entries[0]
        heading = f"Move {entry.name} to the trash?" if len(entries) == 1 else f"Move {len(entries)} screenshots to the trash?"
        dlg = Adw.AlertDialog(heading=heading, body="You can restore them from the trash.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("trash", "Move to trash")
        dlg.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")

        def done(d, response):
            if response == "trash":
                n = 0
                for e in entries:
                    try:
                        Gio.File.new_for_path(e.path).trash(None)
                        self.tags.forget(e.path)
                        n += 1
                    except GLib.Error as exc:
                        self.toast(f"Could not trash {e.name}: {exc.message}", timeout=5)
                if n:
                    self.toast(f"Moved {entry.name} to the trash" if n == 1 else f"Moved {n} screenshots to the trash")
                self.captures.scan()
        dlg.connect("response", done)
        dlg.present(self)

    # -- discard / save ----------------------------------------------------
    def confirm_discard(self, then) -> None:
        """Run ``then`` now, or after the user chooses to save or discard unsaved changes."""
        doc = self.document
        if doc is None or not doc.dirty:
            then()
            return
        dlg = Adw.AlertDialog(heading=f"Save changes to {doc.name}?", body="Your annotations will be lost otherwise.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("discard", "Discard")
        dlg.add_response("save", "Save")
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("save")

        def done(d, response):
            if response == "discard":
                then()
            elif response == "save":
                self._save(then_=then)
        dlg.connect("response", done)
        dlg.present(self)

    def _save(self, then_=None) -> None:
        doc = self.document
        if doc is None or doc.empty:
            self.toast("Nothing to save yet")
            return
        if doc.path:
            try:
                doc.save(quality=self.settings.jpeg_quality)
            except Exception as exc:  # noqa: BLE001
                self.toast(f"Could not save: {exc}", timeout=5)
                return
            self.refresh_document()
            self.toast(f"Saved {doc.name}")
            self.captures.scan()
            if then_:
                then_()
        else:
            self._save_as(then_)

    def _save_as(self, then_=None) -> None:
        doc = self.document
        if doc is None or doc.empty:
            self.toast("Nothing to save yet")
            return
        dialog = Gtk.FileDialog(title="Save as…", modal=True)
        folder = os.path.expanduser(self.settings.screenshot_path)
        dialog.set_initial_folder(Gio.File.new_for_path(folder))
        dialog.set_initial_name(os.path.basename(doc.path) if doc.path else self.settings.next_filename())

        def done(d, result):
            try:
                f = d.save_finish(result)
            except GLib.Error:
                return
            try:
                doc.save(f.get_path(), quality=self.settings.jpeg_quality)
            except Exception as exc:  # noqa: BLE001
                self.toast(f"Could not save: {exc}", timeout=5)
                return
            self.state.title = doc.name
            self.refresh_document()
            self.captures.scan()
            self.toast(f"Saved {doc.name}")
            if then_:
                then_()
        dialog.save(self, None, done)

    # -- paste ---------------------------------------------------------------
    IMAGE_MIME = ("image/png", "image/jpeg", "image/bmp", "image/tiff", "image/webp", "image/gif")

    def _paste(self) -> None:
        """Ctrl+V: a layer copied in the app, else a clipboard image, else clipboard text as a text layer."""
        if self._layer_clip is not None and self.document is not None and not self.document.empty:
            self.paste_layer(self._layer_clip)
            return
        display = Gdk.Display.get_default()
        if display is None:
            self.toast("Clipboard not available", timeout=5)
            return
        clip = display.get_clipboard()
        if self._holds_image(clip.get_formats()):
            clip.read_texture_async(None, self._pasted)
        else:
            clip.read_text_async(None, self._pasted_text)

    @classmethod
    def _holds_image(cls, formats: Gdk.ContentFormats) -> bool:
        """Local textures are offered as a GType (a Gdk.Texture subclass); other apps offer image MIME types."""
        texture = Gdk.Texture.__gtype__
        if any(t.is_a(texture) for t in (formats.get_gtypes() or ())):
            return True
        return any(formats.contain_mime_type(m) for m in cls.IMAGE_MIME)

    def _pasted(self, clip, result) -> None:
        try:
            texture = clip.read_texture_finish(result)
        except GLib.Error:
            texture = None
        if texture is None:
            clip.read_text_async(None, self._pasted_text)
            return
        self.paste_texture(texture)

    def _pasted_text(self, clip, result) -> None:
        try:
            text = clip.read_text_finish(result)
        except GLib.Error:
            text = None
        if not text or not text.strip():
            self.toast("The clipboard holds nothing to paste (image or text)")
            return
        self.paste_text(text)

    MAX_PASTE_CHARS = 2000

    def paste_text(self, text: str) -> None:
        """Clipboard text (from a document, a web page…) becomes a Text layer centred on the image."""
        from ..model.annotations import Annotation, measure_text
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(text) > self.MAX_PASTE_CHARS:
            text = text[:self.MAX_PASTE_CHARS] + "…"
        doc = self.document
        if doc is None or doc.empty:
            self.toast("Capture or paste an image first · text pastes as a layer onto it", timeout=4)
            return
        style = self.editor.style_for("text")
        w, h = measure_text(text, style)
        x, y = max(0.0, (doc.width - w) / 2), max(0.0, (doc.height - h) / 2)
        a = Annotation("text", x, y, x + w, y + h, style=style, text=text)
        self.state.tool = "select"
        self.editor._commit(AddLayer(a))
        self.toast("Pasted text as a layer · drag to move, double-click to edit")

    def paste_layer(self, annotation) -> None:
        """Paste a copy of a layer copied with Ctrl+C, offset so it does not hide the original."""
        a = annotation.copy()
        a.move_by(12, 12)
        self._layer_clip = a.copy()           # repeated pastes cascade
        self.state.tool = "select"
        self.editor._commit(AddLayer(a))
        self.toast("Pasted layer", timeout=2)

    def paste_texture(self, texture: Gdk.Texture) -> None:
        # Gdk.Texture.download writes into a buffer PyGObject copies, so go through PNG bytes instead.
        import io
        from PIL import Image
        from ..model.document import surface_from_pil
        png = texture.save_to_png_bytes()
        with Image.open(io.BytesIO(png.get_data())) as img:
            img.load()
            surf = surface_from_pil(img)
        w, h = surf.get_width(), surf.get_height()
        if self.document is None or self.document.empty:
            self.load_document(Document(surf))
            self.state.subtitle = self.document.summary()
            self.toast("Pasted as a new image")
            return
        from ..model.annotations import Annotation
        doc = self.document
        # 1:1 and centred; if it reaches past the page, the page grows to hold it (EditorController._grow_page_for).
        # Fit in the header shrinks it into the page instead.
        x, y = round((doc.width - w) / 2), round((doc.height - h) / 2)
        a = Annotation("image", x, y, x + w, y + h, style=self.settings.tool_style("image"), surface=surf)
        self.state.tool = "select"
        self.editor._commit(AddLayer(a))
        self.toast("Pasted as a layer · drag it past the edge to enlarge the page · Fit shrinks it into the page")

    # -- image operations ----------------------------------------------------
    def image_op(self, op: str, *args) -> None:
        doc = self.document
        if doc is None or doc.empty or self.undo is None:
            self.toast("Capture or open an image first")
            return
        base = doc.base
        if op == "crop":
            new, mapper = image_ops.crop(base, *args); label = "Crop"
        elif op == "scale":
            new, mapper = image_ops.scale(base, *args); label = "Resize"
        elif op == "rotate":
            new, mapper = image_ops.rotate(base, args[0]); label = f"Rotate {args[0]}°"
        elif op == "flip":
            new, mapper = image_ops.flip(base, args[0]); label = "Flip"
        elif op == "adjust":
            new, mapper = image_ops.adjust(base, **args[0]), None; label = "Adjust colours"
        elif op == "crop-area":
            new, mapper = image_ops.crop_masked(base, args[0]); label = "Crop to area"
        else:
            return
        self.editor.select(None)
        self.undo.do(TransformBase(new, mapper, label=label))
        self.refresh_document()
        self.toast(label, timeout=2)
        if op in ("crop", "crop-area", "scale", "rotate"):
            GLib.idle_add(lambda: (setattr(self.state, "zoom", self.stage.fit_zoom()), False)[1])

    def preview_base(self, surface) -> None:
        """Temporarily show ``surface`` as the base (None restores the real one); used by Adjust."""
        doc = self.document
        if doc is None or doc.empty:
            return
        if surface is None:
            if getattr(self, "_real_base", None) is not None:
                doc.base, self._real_base = self._real_base, None
        else:
            if getattr(self, "_real_base", None) is None:
                self._real_base = doc.base
            doc.base = surface
        self.stage.refresh()

    def _flatten(self) -> None:
        doc = self.document
        if doc is None or doc.empty:
            self.toast("Nothing to flatten")
            return
        if not doc.layers:
            self.toast("No layers to flatten")
            return
        dlg = Adw.AlertDialog(heading="Flatten all layers?", body=f"{len(doc.layers)} layer(s) will be merged into the image. You can undo this.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("flatten", "Flatten")
        dlg.set_response_appearance("flatten", Adw.ResponseAppearance.SUGGESTED)

        def done(d, response):
            if response == "flatten":
                self.flatten_now()
        dlg.connect("response", done)
        dlg.present(self)

    def flatten_now(self) -> None:
        doc = self.document
        self.editor.select(None)
        self.undo.do(ReplaceBase(doc.flatten(), label="Flatten", layers_after=[]))
        self.refresh_document()
        self.toast("Flattened")

    def _popover(self, which: str) -> None:
        if self.document is None or self.document.empty:
            self.toast("Capture or open an image first")
            return
        pop = self._popovers.get(which)
        if pop is None:
            pop = {"resize": ResizePopover, "rotate": RotatePopover, "adjust": AdjustPopover}[which](self)
            anchor = self.tool_rail.button_for({"resize": "win.resize", "rotate": "win.rotate", "adjust": "win.adjust"}[which])
            pop.set_parent(anchor or self.stage)
            self._popovers[which] = pop
        pop.popup()

    def _copy(self) -> None:
        """Ctrl+C: the flattened image goes to the system clipboard (and the tray); a selected layer is remembered for Ctrl+V."""
        if self.document is None or self.document.empty:
            self.toast("Nothing to copy yet")
            return
        if self.editor.area is not None:                 # Ctrl+C with a marked area: just that region
            region = self.editor.area_surface()
            if region is None:
                self.toast("The marked area is empty")
                return
            ok = clipboard.copy_surface(region)
            if ok:
                self.clips.push(region, f"{self.document.name} · area")
            self._layer_clip = None
            self.toast(f"Copied the marked area ({region.get_width()}×{region.get_height()})" + ("" if ok else " · clipboard not available"))
            return
        layer = self.editor.selected_layer()
        everything = self.editor.all_selected
        flat = self.document.flatten()
        ok = clipboard.copy_surface(flat)
        if ok:
            self.clips.push(flat, self.document.name)
        self._layer_clip = layer.annotation.copy() if layer is not None else None   # after the clipboard "changed"
        n = len(self.document.layers)
        if everything:
            self.toast(f"Copied the flattened image with {n} layer{'s' if n != 1 else ''}" + ("" if ok else " · clipboard not available"))
        elif layer is not None:
            number = self.document.layers.index(layer) + 1
            self.toast(f"Copied layer {number} ({layer.badge.title()}) · Ctrl+V pastes a copy" + ("" if ok else " · clipboard not available"))
        elif ok:
            self.toast(f"Copied {self.document.name} to clipboard")
        else:
            self.toast("Clipboard not available", timeout=5)

    def _select_all(self) -> None:
        if self.editor.select_all():
            n = len(self.document.layers)
            self.toast(f"All {n} layer{'s' if n != 1 else ''} selected · Ctrl+C copies the flattened image · Delete removes them", timeout=3)
        elif self.document is not None and not self.document.empty:
            self.toast("No layers to select · Ctrl+C copies the image as it is", timeout=2)
        else:
            self.toast("Capture or open an image first", timeout=2)

    def _paste_clip(self, entry) -> None:
        """Paste a tray entry: as a layer on the current image, or as a new image on an empty stage."""
        if self.state.library:
            self.state.library = False
        self.paste_texture(entry.texture)

    def _discard(self) -> None:
        if self.document is None:
            return
        self.confirm_discard(lambda: (self.clear_document(), self.toast("Stage cleared")))

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
