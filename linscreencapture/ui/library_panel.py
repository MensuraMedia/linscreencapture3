"""The right rail while the Library is open: image controls, the selection's info and its tags.

Open page (220 px): IMAGE (Open, Combine, Copy, Duplicate, Rename, Show in folder, Delete), SELECTION (Select all,
Clear, Refresh), INFO (name, size, kind, file size, date; or a count and total size) and TAGS (the selection's tags
as removable chips and an "Add a tag" field that tags every selected image). Collapsed page: the same buttons in a
column. Buttons run ``win.library-*`` actions; sensitivity follows the selection.
"""
from __future__ import annotations
import datetime
import os

from gi.repository import GdkPixbuf, Gtk, Pango

from .widgets import rail_button, group_label, hairline, flow_group

IMAGE_ITEMS = (("arrow-square-out", "Open in the editor", "win.library-open", "Enter"),
               ("squares-four", "Combine: tile the selected images on one page", "win.library-combine", None),
               ("copy", "Copy the selected image(s) to the clipboard", "win.library-copy", "Ctrl+C"),
               ("files", "Duplicate the selected file(s) in the folder", "win.library-duplicate", "Ctrl+D"),
               ("cursor-text", "Rename the selected file", "win.library-rename", "F2"),
               ("folder-open", "Show in the file manager", "win.library-show", None),
               ("trash", "Move the selected file(s) to the trash", "win.library-delete", "Delete"))
SELECTION_ITEMS = (("selection-all", "Select all", "win.library-select-all", "Ctrl+A"),
                   ("selection-slash", "Clear the selection", "win.library-clear", None),
                   ("arrows-clockwise", "Refresh the folder", "win.library-refresh", None))
NEEDS = {"win.library-open": 1, "win.library-combine": 2, "win.library-copy": 1, "win.library-duplicate": 1,
         "win.library-rename": 1, "win.library-show": 1, "win.library-delete": 1, "win.library-clear": 1}
SINGLE = {"win.library-rename"}                                   # exactly one image


def _human(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _button(item) -> Gtk.Button:
    icon, label, action, key = item
    classes = ("danger",) if action == "win.library-delete" else ()
    return rail_button(icon, label, action, classes=classes, key=key)


class LibraryPanel(Gtk.Box):
    """The open rail's Library content (between the top row and the SETTINGS group)."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.library = None
        self.tags = None
        self.buttons: list[Gtk.Button] = []
        self.append(group_label("Image"))
        image = [_button(i) for i in IMAGE_ITEMS]
        grid = flow_group(image, per_line=5)
        grid.set_margin_top(4); grid.set_margin_bottom(10)
        self.append(grid)
        self.append(hairline())
        lbl = group_label("Selection"); lbl.set_margin_top(10)
        self.append(lbl)
        sel = [_button(i) for i in SELECTION_ITEMS]
        row = flow_group(sel, per_line=5)
        row.set_margin_top(4); row.set_margin_bottom(10)
        self.append(row)
        self.buttons = image + sel
        self.append(hairline())
        lbl = group_label("Info"); lbl.set_margin_top(10)
        self.append(lbl)
        self.info_name = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=20, margin_top=4)
        self.info_name.add_css_class("layer-name")
        self.info_detail = Gtk.Label(xalign=0.0, wrap=True, width_chars=20, max_width_chars=20, margin_bottom=10)
        self.info_detail.add_css_class("sublabel")
        self.append(self.info_name)
        self.append(self.info_detail)
        self.append(hairline())
        lbl = group_label("Tags"); lbl.set_margin_top(10)
        self.append(lbl)
        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4, row_spacing=4,
                                 max_children_per_line=6, margin_top=6, homogeneous=False)   # fills the width: a wrong
        # height-for-width (chips over the entry) came from a START-aligned flow box
        self.append(self.chips)
        self.tag_entry = Gtk.Entry(placeholder_text="Add a tag · Enter", margin_top=6)
        self.tag_entry.update_property([Gtk.AccessibleProperty.LABEL], ["Add a tag to the selected images"])
        self.tag_entry.connect("activate", lambda e: self.add_tag(e.get_text()))
        self.append(self.tag_entry)
        self.tags_hint = Gtk.Label(xalign=0.0, wrap=True, width_chars=20, max_width_chars=20, margin_top=4)
        self.tags_hint.add_css_class("sublabel")
        self.append(self.tags_hint)

    def bind(self, library, tags) -> None:
        self.library, self.tags = library, tags
        library.on_selection.append(self.refresh)
        self.refresh()

    # -- refresh ----------------------------------------------------------------
    def refresh(self) -> None:
        entries = self.library.selected_entries if self.library is not None else []
        n = len(entries)
        for b in self.buttons:
            need = NEEDS.get(b.get_action_name(), 0)
            b.set_sensitive(n >= need and (n == 1 if b.get_action_name() in SINGLE else True))
        self._info(entries)
        self._chips(entries)
        self.tag_entry.set_sensitive(n > 0)
        self.tags_hint.set_label("Select images to tag them" if n == 0 else
                                 "Tags go on every selected image · the Library's search finds them" if n > 1 else
                                 "The Library's search finds images by tag")

    def _info(self, entries) -> None:
        if not entries:
            self.info_name.set_label("Nothing selected")
            self.info_detail.set_label("Click an image · Ctrl+click or Shift+click for several · right-click for more")
            return
        sizes = [os.path.getsize(e.path) if os.path.exists(e.path) else 0 for e in entries]
        if len(entries) > 1:
            self.info_name.set_label(f"{len(entries)} images selected")
            self.info_detail.set_label(f"{_human(sum(sizes))} in all · Combine tiles them on one page")
            return
        e = entries[0]
        fmt, w, h = GdkPixbuf.Pixbuf.get_file_info(e.path)
        kind = fmt.get_name().upper() if fmt else os.path.splitext(e.path)[1][1:].upper()
        when = datetime.datetime.fromtimestamp(e.mtime).strftime("%b %-d, %Y · %H:%M")
        self.info_name.set_label(e.name)
        self.info_name.set_tooltip_text(e.path)
        self.info_detail.set_label(f"{w} × {h} px · {kind} · {_human(sizes[0])}\n{when}")

    def _chips(self, entries) -> None:
        while (c := self.chips.get_first_child()) is not None:
            self.chips.remove(c)
        if not entries or self.tags is None:
            return
        seen: dict[str, str] = {}
        for e in entries:                                  # the union over the selection, first spelling wins
            for t in self.tags.get(e.path):
                seen.setdefault(t.lower(), t)
        for t in sorted(seen.values(), key=str.lower):
            chip = Gtk.Button(label=f"{t}  ×", tooltip_text=f"Remove “{t}” from the selected image(s)")
            chip.add_css_class("tag-chip")
            chip.set_focus_on_click(False)
            chip.set_halign(Gtk.Align.START)
            chip.connect("clicked", lambda _b, tag=t: self.remove_tag(tag))
            self.chips.append(chip)
            chip.get_parent().set_halign(Gtk.Align.START)      # the FlowBoxChild must not stretch the pill

    # -- tag edits ----------------------------------------------------------------
    def add_tag(self, text: str) -> bool:
        entries = self.library.selected_entries if self.library is not None else []
        if not entries or self.tags is None:
            return False
        changed = self.tags.add([e.path for e in entries], text)
        self.tag_entry.set_text("")
        if changed:
            self.library.tags_changed()
        return changed

    def remove_tag(self, tag: str) -> bool:
        entries = self.library.selected_entries if self.library is not None else []
        changed = self.tags is not None and self.tags.remove([e.path for e in entries], tag)
        if changed:
            self.library.tags_changed()
        return bool(changed)


class LibraryColumn(Gtk.Box):
    """The collapsed rail's Library content: the same buttons in a column."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        self.buttons = []
        for n, item in enumerate(IMAGE_ITEMS + SELECTION_ITEMS):
            if n == len(IMAGE_ITEMS):
                self.append(hairline(30))
            b = _button(item)
            b.set_halign(Gtk.Align.CENTER)
            self.append(b)
            self.buttons.append(b)

    def bind(self, library) -> None:
        def sync():
            n = len(library.selected_entries)
            for b in self.buttons:
                need = NEEDS.get(b.get_action_name(), 0)
                b.set_sensitive(n >= need and (n == 1 if b.get_action_name() in SINGLE else True))
        library.on_selection.append(sync)
        sync()
