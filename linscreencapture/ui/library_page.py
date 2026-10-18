"""Library: a full-stage page listing the capture folder so the user can pick images to edit or manage.

Several images can be selected (click, Ctrl+click, Shift+click, Ctrl+A). The image controls (Open, Combine, Copy,
Duplicate, Rename, Show in folder, Delete), the selection's info and its tags live in the right rail's Library panel
(``ui/library_panel.py``) and in a right-click menu on the grid; they only touch the library (files on disk, tags and
the clipboard), except Open and Combine, which load the editor. The search field filters by file name or tag. A
double-click (or Enter / Open) opens that image in the editor.
"""
from __future__ import annotations
import datetime

from gi.repository import Gdk, Gio, Graphene, Gtk, Pango

from .widgets import rail_button
from ..services import icon_loader
from ..model.captures_index import CapturesIndex, CaptureEntry

CELL_W, CELL_H = 180, 120
# the right-click menu: (label, action) sections
MENU = ((("Open in the editor", "win.library-open"), ("Combine on one page", "win.library-combine")),
        (("Copy", "win.library-copy"), ("Duplicate", "win.library-duplicate"), ("Rename…", "win.library-rename"),
         ("Add a tag…", "win.library-tag"), ("Show in folder", "win.library-show")),
        (("Move to trash", "win.library-delete"),))


class LibraryPage(Gtk.Box):
    def __init__(self, captures: CapturesIndex, tags=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.add_css_class("library")
        self.captures = captures
        self.tags = tags

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.add_css_class("library-head")
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        t = Gtk.Label(label="Library", xalign=0.0)
        t.add_css_class("title")
        # ellipsized: a long folder path must never widen the page (it pushed the right rail off the window)
        self.summary = Gtk.Label(label="", xalign=0.0, ellipsize=Pango.EllipsizeMode.MIDDLE, width_chars=12)
        self.summary.add_css_class("subtitle")
        block.append(t)
        block.append(self.summary)
        head.append(block)
        self.search = Gtk.SearchEntry(placeholder_text="Filter by name or tag", valign=Gtk.Align.CENTER, width_chars=22)
        self.search.update_property([Gtk.AccessibleProperty.LABEL], ["Filter the library by file name or tag"])
        self.search.connect("search-changed", lambda *_: self._refilter())
        head.append(self.search)
        self.open_btn = Gtk.Button()
        ob = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ob.append(icon_loader.icon("arrow-square-out", 18))
        ob.append(Gtk.Label(label="Open"))
        self.open_btn.set_child(ob)
        self.open_btn.add_css_class("primary-pill")
        self.open_btn.set_tooltip_markup("Open the selected image in the editor\n<span size='small' alpha='65%'>Double-click · Enter</span>")
        self.open_btn.set_action_name("win.library-open")
        self.open_btn.set_valign(Gtk.Align.CENTER)
        self.open_btn.set_margin_start(6)
        head.append(self.open_btn)
        close = rail_button("x", "Close library", "win.library", key="Esc")
        close.set_margin_start(6)
        head.append(close)
        self.append(head)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        factory.connect("unbind", self._unbind)
        self.filter = Gtk.CustomFilter.new(self._keep)
        self.filtered = Gtk.FilterListModel(model=captures.store, filter=self.filter)
        self.selection = Gtk.MultiSelection(model=self.filtered)
        self.selection.connect("selection-changed", lambda *_: self._selection_changed())
        self.on_selection: list = []                      # the right rail's Library panel listens here
        self.grid = Gtk.GridView(model=self.selection, factory=factory, min_columns=2, max_columns=12,
                                 single_click_activate=False, hexpand=True, vexpand=True)
        self.grid.add_css_class("library-grid")
        self.grid.set_accessible_role(Gtk.AccessibleRole.GRID)
        self.grid.connect("activate", self._activated)          # double-click or Enter on a cell
        scroller = Gtk.ScrolledWindow(child=self.grid, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, hexpand=True, vexpand=True)
        self.empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        g = icon_loader.icon("images", 48)
        g.add_css_class("empty-glyph")
        self.empty.append(g)
        self.empty_label = Gtk.Label(label="No screenshots yet")
        self.empty_label.add_css_class("empty-title")
        self.empty.append(self.empty_label)
        self.pages = Gtk.Stack(hexpand=True, vexpand=True)
        self.pages.add_named(self.empty, "empty")
        self.pages.add_named(scroller, "grid")
        self.append(self.pages)
        self.menu = self._build_menu()
        self.activated_entry: CaptureEntry | None = None
        self._cells: set = set()                                # bound cells, so tag edits relabel them in place
        captures.connect("scanned", self._scanned)
        self._scanned(captures, captures.store.get_n_items())

    # -- selection ------------------------------------------------------------
    @property
    def selected_entries(self) -> list[CaptureEntry]:
        """The selection in grid order."""
        bits = self.selection.get_selection()
        return [self.selection.get_item(bits.get_nth(i)) for i in range(bits.get_size())]

    @property
    def selected(self) -> CaptureEntry | None:
        """The first selected entry (what Open uses)."""
        entries = self.selected_entries
        return entries[0] if entries else None

    def select_all(self) -> int:
        self.selection.select_all()
        return len(self.selected_entries)

    def clear_selection(self) -> None:
        self.selection.unselect_all()

    def _selection_changed(self) -> None:
        n = len(self.selected_entries)
        self.open_btn.set_sensitive(n > 0)
        self._summary(self.captures.store.get_n_items(), n)
        for cb in list(self.on_selection):
            cb()

    def _summary(self, total: int, selected: int = 0) -> None:
        folder = self.captures.folder.replace(str(__import__("pathlib").Path.home()), "~")
        shown = self.filtered.get_n_items()
        text = f"{total} screenshot{'s' if total != 1 else ''} · {folder}"
        if shown != total:
            text = f"{shown} of {total} shown · {folder}"
        if selected > 1:
            text = f"{selected} of {shown} selected · {folder}"
        self.summary.set_label(text)

    def _activated(self, _grid, position: int) -> None:
        self.activated_entry = self.selection.get_item(position)
        self.activate_action("win.library-open", None)

    def _scanned(self, index: CapturesIndex, n: int) -> None:
        folder = index.folder.replace(str(__import__("pathlib").Path.home()), "~")
        self.empty_label.set_label(f"No screenshots yet in {folder}")
        self.pages.set_visible_child_name("grid" if n else "empty")
        self._selection_changed()

    # -- filter and tags ----------------------------------------------------------
    def _keep(self, entry: CaptureEntry) -> bool:
        text = self.search.get_text().strip().lower() if hasattr(self, "search") else ""
        if not text:
            return True
        return text.lstrip("#") in entry.name.lower() or (self.tags is not None and self.tags.matches(entry.path, text))

    def _refilter(self) -> None:
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._summary(self.captures.store.get_n_items(), len(self.selected_entries))

    def tags_changed(self) -> None:
        """After a tag edit: relabel the visible cells and re-run the filter."""
        for cell in list(self._cells):
            self._show_tags(cell)
        if self.search.get_text().strip():
            self._refilter()
        for cb in list(self.on_selection):
            cb()

    def _show_tags(self, cell) -> None:
        tags = self.tags.get(cell.entry.path) if (self.tags is not None and cell.entry is not None) else []
        cell.tag_label.set_label("  ".join(f"#{t}" for t in tags))
        cell.tag_label.set_visible(bool(tags))

    # -- right-click menu ------------------------------------------------------------
    def _build_menu(self) -> Gtk.PopoverMenu:
        model = Gio.Menu()
        for section in MENU:
            sec = Gio.Menu()
            for label, action in section:
                sec.append(label, action)
            model.append_section(None, sec)
        pop = Gtk.PopoverMenu.new_from_model(model)
        pop.set_parent(self)
        pop.set_has_arrow(False)
        pop.set_halign(Gtk.Align.START)
        return pop

    def context_menu(self, position: int, x: float, y: float) -> None:
        """Right-click on cell ``position`` at page point (x, y): a cell outside the selection becomes the selection."""
        if not self.selection.is_selected(position):
            self.selection.select_item(position, True)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self.menu.set_pointing_to(rect)
        self.menu.popup()

    def _right_click(self, gesture: Gtk.GestureClick, _n: int, x: float, y: float) -> None:
        cell = gesture.get_widget()
        if cell.position is None:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        ok, pt = cell.compute_point(self, Graphene.Point().init(x, y))
        self.context_menu(cell.position, pt.x if ok else x, pt.y if ok else y)

    # -- cells ----------------------------------------------------------------
    def _setup(self, _f, item: Gtk.ListItem) -> None:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cell.add_css_class("library-cell")
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        pic.set_size_request(CELL_W, CELL_H)
        pic.add_css_class("cap-thumb")
        pic.set_overflow(Gtk.Overflow.HIDDEN)
        name = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=22)
        name.add_css_class("layer-name")
        date = Gtk.Label(xalign=0.0)
        date.add_css_class("cap-name")
        tag_label = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=24, visible=False)
        tag_label.add_css_class("cap-tags")
        for w in (pic, name, date, tag_label):
            cell.append(w)
        cell.entry, cell.position, cell.tag_label = None, None, tag_label
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._right_click)
        cell.add_controller(click)
        item.set_child(cell)

    def _bind(self, _f, item: Gtk.ListItem) -> None:
        e: CaptureEntry = item.get_item()
        cell = item.get_child()
        pic = cell.get_first_child()
        name = pic.get_next_sibling()
        date = name.get_next_sibling()
        pic.set_paintable(e.texture)
        name.set_label(e.name)
        date.set_label(datetime.datetime.fromtimestamp(e.mtime).strftime("%b %-d, %Y · %H:%M"))
        cell.set_tooltip_text(f"{e.path}\nDouble-click opens · Ctrl+click adds to the selection · right-click for more")
        cell.entry, cell.position = e, item.get_position()
        self._show_tags(cell)
        self._cells.add(cell)

    def _unbind(self, _f, item: Gtk.ListItem) -> None:
        cell = item.get_child()
        cell.entry, cell.position = None, None
        self._cells.discard(cell)
