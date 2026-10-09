"""Library: a full-stage page listing the capture folder so the user can pick an image to edit."""
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
        head.append(rail_button("arrows-clockwise", "Refresh", "win.library-refresh"))
        head.append(rail_button("trash", "Delete selected", "win.library-delete", classes=("danger",)))
        self.open_btn = Gtk.Button()
        ob = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ob.append(icon_loader.icon("folder-open", 18))
        ob.append(Gtk.Label(label="Open"))
        self.open_btn.set_child(ob)
        self.open_btn.add_css_class("primary-pill")
        self.open_btn.set_tooltip_text("Open the selected image in the editor")
        self.open_btn.set_action_name("win.library-open")
        self.open_btn.set_valign(Gtk.Align.CENTER)
        self.open_btn.set_margin_start(6)
        head.append(self.open_btn)
        close = rail_button("x", "Close library", "win.library")
        close.set_margin_start(6)
        head.append(close)
        self.append(head)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        self.selection = Gtk.SingleSelection(model=captures.store, autoselect=False)
        self.grid = Gtk.GridView(model=self.selection, factory=factory, min_columns=2, max_columns=12,
                                 single_click_activate=False, hexpand=True, vexpand=True)
        self.grid.add_css_class("library-grid")
        self.grid.set_accessible_role(Gtk.AccessibleRole.GRID)
        self.grid.connect("activate", lambda *_: self.activate_action("win.library-open", None))
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
        captures.connect("scanned", self._scanned)
        self._scanned(captures, captures.store.get_n_items())

    @property
    def selected(self) -> CaptureEntry | None:
        return self.selection.get_selected_item()

    def _scanned(self, index: CapturesIndex, n: int) -> None:
        folder = index.folder.replace(str(__import__("pathlib").Path.home()), "~")
        self.summary.set_label(f"{n} screenshot{'s' if n != 1 else ''} · {folder}")
        self.empty_label.set_label(f"No screenshots yet in {folder}")
        self.pages.set_visible_child_name("grid" if n else "empty")
        self.open_btn.set_sensitive(n > 0)

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
        cell.set_tooltip_text(e.path)
