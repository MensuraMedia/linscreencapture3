"""Clipboard tray: a preview of the latest copy, above the Library button in the left rail.

Open rail: a 116 px box the size of the navigator holding ``SLOTS`` slots (one for now; more are on the
roadmap); hovering a slot shows its caption, a click opens a popover with a larger preview and Copy /
Paste / Delete buttons centred below it. Collapsed rail: one 30 px clipboard button whose popover holds
the same tray. Both read ``ClipHistory``.
"""
from __future__ import annotations
import datetime

from gi.repository import Gtk, Gdk, Gio

from .widgets import rail_button, group_label
from ..services import icon_loader
from ..services.clip_history import ClipHistory, ClipEntry

TRAY_HEIGHT = 116          # same as the navigator
SLOTS = 1          # grows with ClipHistory.LIMIT when the multi-copy tray lands
PREVIEW_W, PREVIEW_H = 320, 200


def _size_label(e: ClipEntry) -> str:
    when = datetime.datetime.fromtimestamp(e.when).strftime("%H:%M")
    return f"{e.width}×{e.height} · {when}"


class ClipPreview(Gtk.Popover):
    """Larger sample of one copy with Copy / Paste / Delete under it."""

    def __init__(self, history: ClipHistory, on_paste=None):
        super().__init__(autohide=True)
        self.add_css_class("clip-preview")
        self.history = history
        self.on_paste = on_paste
        self.entry: ClipEntry | None = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=False, halign=Gtk.Align.CENTER)
        self.picture.set_size_request(-1, 40)                 # the entry's preview texture is at most 320×200
        self.picture.add_css_class("clip-large")
        box.append(self.picture)
        self.caption = Gtk.Label(xalign=0.5)
        self.caption.add_css_class("sublabel")
        box.append(self.caption)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.CENTER)
        group = Gio.SimpleActionGroup()
        for name, fn in (("copy", self._copy), ("paste", self._paste), ("delete", self._delete)):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, f=fn: f())
            group.add_action(a)
        self.insert_action_group("clip", group)
        self.copy_btn = rail_button("copy", "Copy to the clipboard again", "clip.copy", classes=("small",), size=16)
        self.paste_btn = rail_button("clipboard-text", "Paste into the editor", "clip.paste", classes=("small",), size=16)
        self.delete_btn = rail_button("trash", "Remove from the tray (and clear the clipboard if it holds this copy)",
                                      "clip.delete", classes=("small", "danger"), size=16)
        for b in (self.copy_btn, self.paste_btn, self.delete_btn):
            row.append(b)
        box.append(row)
        self.set_child(box)

    def show_entry(self, entry: ClipEntry) -> None:
        """Fill the preview with ``entry`` (the owning MenuButton pops the popover up)."""
        self.entry = entry
        self.picture.set_paintable(entry.preview or entry.texture)
        self.caption.set_label(f"{entry.label} · {_size_label(entry)}" + (" · on the clipboard" if self.history.is_current(entry) else ""))

    def _toast(self, text: str) -> None:
        root = self.get_root()
        if root is not None and hasattr(root, "toast"):
            root.toast(text, timeout=2)

    def _copy(self) -> None:
        if self.entry is not None:
            ok = self.history.copy(self.entry)
            self._toast("Copied to the clipboard" if ok else "Clipboard not available")
            self.popdown()

    def _paste(self) -> None:
        if self.entry is not None and self.on_paste is not None:
            self.on_paste(self.entry)
            self.popdown()

    def _delete(self) -> None:
        if self.entry is not None:
            was_current = self.history.is_current(self.entry)
            self.history.remove(self.entry)
            self._toast("Removed from the tray · clipboard cleared" if was_current else "Removed from the tray")
            self.popdown()


class ClipTray(Gtk.Box):
    """``SLOTS`` slots, newest first; empty slots are dashed placeholders.

    Each slot is a ``Gtk.MenuButton`` owning its preview popover: a popover popped up by hand from a
    plain button's ``clicked`` handler was closed again at once by the same button release."""

    def __init__(self, history: ClipHistory, on_paste=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, homogeneous=True)
        self.add_css_class("clip-tray")
        self.set_size_request(-1, TRAY_HEIGHT)
        self.set_vexpand(False)                       # explicit: the pictures inside must not stretch the tray
        self.set_valign(Gtk.Align.END)
        self.history = history
        self.slots: list[Gtk.MenuButton] = []
        self.pictures: list[Gtk.Picture] = []
        self.previews: list[ClipPreview] = []
        for n in range(SLOTS):
            b = Gtk.MenuButton()
            b.add_css_class("clip-slot")
            b.set_always_show_arrow(False)
            b.set_focus_on_click(False)
            b.set_direction(Gtk.ArrowType.RIGHT)
            pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
            b.set_child(pic)
            pop = ClipPreview(history, on_paste)
            pop.connect("show", lambda p, n=n: self._showing(p, n))
            b.set_popover(pop)
            self.append(b)
            self.slots.append(b)
            self.pictures.append(pic)
            self.previews.append(pop)
        history.connect("changed", lambda *_: self.refresh())
        self.refresh()

    @property
    def preview(self) -> ClipPreview:
        """The preview that is open, else the first slot's (tests and tools)."""
        return next((p for p in self.previews if p.get_visible()), self.previews[0])

    def entry_at(self, n: int) -> ClipEntry | None:
        return self.history.entries[n] if n < len(self.history.entries) else None

    def refresh(self) -> None:
        for n, (slot, pic) in enumerate(zip(self.slots, self.pictures)):
            e = self.entry_at(n)
            pic.set_paintable((e.preview or e.texture) if e else None)
            slot.set_sensitive(e is not None)
            if e is None:
                slot.remove_css_class("filled")
                slot.set_tooltip_text("Copies you make appear here" if n == 0 else None)
                if self.previews[n].get_visible():
                    self.previews[n].popdown()
            else:
                slot.add_css_class("filled")
                slot.set_tooltip_text(f"{e.label} · {_size_label(e)} · click for a larger preview")
            if e is not None and self.history.is_current(e):
                slot.add_css_class("current")
            else:
                slot.remove_css_class("current")

    def _showing(self, pop: ClipPreview, n: int) -> None:
        e = self.entry_at(n)
        if e is not None:
            pop.show_entry(e)


class ClipTrayButton(Gtk.MenuButton):
    """Collapsed rail: a 30 px clipboard button whose popover holds the tray."""

    def __init__(self, history: ClipHistory, on_paste=None):
        super().__init__()
        self.add_css_class("rail-btn")
        self.set_child(icon_loader.icon("clipboard", 18))
        self.set_tooltip_text("Clipboard · the last copy")
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Clipboard tray"])
        self.set_focus_on_click(False)
        pop = Gtk.Popover()
        self.tray = ClipTray(history, on_paste)
        self.tray.set_size_request(200, TRAY_HEIGHT)
        self.tray.set_margin_top(6); self.tray.set_margin_bottom(6); self.tray.set_margin_start(6); self.tray.set_margin_end(6)
        pop.set_child(self.tray)
        self.set_popover(pop)
        history.connect("changed", lambda h: self.set_tooltip_text("Clipboard · the last copy · click to preview" if len(h) else "Clipboard · no copies yet"))
