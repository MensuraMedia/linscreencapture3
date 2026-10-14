"""Library: a full-stage page listing the capture folder so the user can pick images to edit or manage.

Several images can be selected (click, Ctrl+click, Shift+click, Ctrl+A); Copy, Duplicate and Delete act on
the selection and only touch the library (files on disk and the clipboard), never the document on the
stage. A double-click (or Enter / Open) opens that image in the editor.
"""
from __future__ import annotations
import datetime

from gi.repository import Gtk, Pango

from .widgets import rail_button
from ..services import icon_loader
from ..model.captures_index import CapturesIndex, CaptureEntry

CELL_W, CELL_H = 180, 120


class LibraryPage(Gtk.Box):
    def __init__(self, captures: CapturesIndex):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.add_css_class("library")
        self.captures = captures

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.add_css_class("library-head")
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        t = Gtk.Label(label="Library", xalign=0.0)
        t.add_css_class("title")
        self.summary = Gtk.Label(label="", xalign=0.0)
        self.summary.add_css_class("subtitle")
        block.append(t)
        block.append(self.summary)
        head.append(block)
        head.append(Gtk.Box(hexpand=True))
        self.select_all_btn = rail_button("selection-all", "Select all", "win.library-select-all", key="Ctrl+A")
        self.copy_btn = rail_button("copy", "Copy the selected image(s) to the clipboard", "win.library-copy", key="Ctrl+C")
        self.duplicate_btn = rail_button("files", "Duplicate the selected file(s) in the folder", "win.library-duplicate", key="Ctrl+D")
        self.delete_btn = rail_button("trash", "Move the selected file(s) to the trash", "win.library-delete", classes=("danger",), key="Delete")
        head.append(rail_button("arrows-clockwise", "Refresh", "win.library-refresh"))
        for b in (self.select_all_btn, self.copy_btn, self.duplicate_btn, self.delete_btn):
            head.append(b)
        self.open_btn = Gtk.Button()
        ob = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ob.append(icon_loader.icon("folder-open", 18))
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
        self.selection = Gtk.MultiSelection(model=captures.store)
        self.selection.connect("selection-changed", lambda *_: self._selection_changed())
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
        self.activated_entry: CaptureEntry | None = None
        captures.connect("scanned", self._scanned)
        self._scanned(captures, captures.store.get_n_items())

    # -- selection ------------------------------------------------------------
    @property
    def selected_entries(self) -> list[CaptureEntry]:
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

    def _selection_changed(self) -> None:
        n = len(self.selected_entries)
        for b in (self.copy_btn, self.duplicate_btn, self.delete_btn):
            b.set_sensitive(n > 0)
        self.open_btn.set_sensitive(n > 0)
        total = self.captures.store.get_n_items()
        self._summary(total, n)

    def _summary(self, total: int, selected: int = 0) -> None:
        folder = self.captures.folder.replace(str(__import__("pathlib").Path.home()), "~")
        text = f"{total} screenshot{'s' if total != 1 else ''} · {folder}"
        if selected > 1:
            text = f"{selected} of {total} selected · {folder}"
        self.summary.set_label(text)

    def _activated(self, _grid, position: int) -> None:
        self.activated_entry = self.selection.get_item(position)
        self.activate_action("win.library-open", None)

    def _scanned(self, index: CapturesIndex, n: int) -> None:
        folder = index.folder.replace(str(__import__("pathlib").Path.home()), "~")
        self._summary(n, len(self.selected_entries))
        self.empty_label.set_label(f"No screenshots yet in {folder}")
        self.pages.set_visible_child_name("grid" if n else "empty")
        self._selection_changed()

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
        cell.append(pic)
        cell.append(name)
        cell.append(date)
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
        cell.set_tooltip_text(f"{e.path}\nDouble-click opens · Ctrl+click adds to the selection")
