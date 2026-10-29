"""Clipboard tray: the last four copies, above the Library button in the left rail.

Open rail: a 116 px box the size of the navigator cut into ``SLOTS`` quarters in a 2 × 2 grid, newest
top-left; hovering a cell shows its caption, a click opens a popover with a larger preview and Copy /
Paste / Delete buttons centred below it, and a double-click pastes the copy into the stage at once. Collapsed rail: one 30 px clipboard button whose popover holds
the same tray. Both read ``ClipHistory``.
"""
from __future__ import annotations
import datetime

from gi.repository import Gtk, Gdk, Gio, GLib

from .widgets import rail_button, group_label
from ..services import icon_loader
from ..services.clip_history import ClipHistory, ClipEntry

TRAY_HEIGHT = 116          # same as the navigator
SLOTS = 4                  # the 2 × 2 grid; matches ClipHistory.LIMIT
PREVIEW_W, PREVIEW_H = 320, 200


def _clock(e: ClipEntry) -> str:
    return datetime.datetime.fromtimestamp(e.when).strftime("%H:%M")


def _size_label(e: ClipEntry) -> str:
    return f"{e.width}×{e.height} · {_clock(e)}"


class CellPicture(Gtk.Picture):
    """A picture that asks for no size of its own: a ``Gtk.Picture`` reports its texture's natural size even with
    ``can_shrink``, so four 192 × 108 thumbnails grew the 116 px tray to 240 px. The grid sizes the cells instead."""

    def do_measure(self, orientation, for_size):
        return 0, 0, -1, -1


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


class ClipTray(Gtk.Grid):
    """``SLOTS`` cells in a 2 × 2 grid, newest top-left; empty cells are dashed placeholders.

    Each cell is a ``Gtk.MenuButton`` owning its preview popover: a popover popped up by hand from a
    plain button's ``clicked`` handler was closed again at once by the same button release.

    Pointer clicks are claimed by a capture-phase gesture so a double-click can paste: the first click waits
    for the double-click time, then pops the preview up (after the release, so it stays open); a second click
    within that time pastes instead. The keyboard (Enter / Space) still opens the preview directly."""

    def __init__(self, history: ClipHistory, on_paste=None):
        super().__init__(row_homogeneous=True, column_homogeneous=True, row_spacing=4, column_spacing=4)
        self.add_css_class("clip-tray")
        self.set_size_request(-1, TRAY_HEIGHT)
        self.set_vexpand(False)                       # explicit: the pictures inside must not stretch the tray
        self.set_valign(Gtk.Align.END)
        self.history = history
        self.on_paste = on_paste
        self._pending: dict[int, int] = {}            # slot -> GLib source of a single click waiting to pop up
        self.slots: list[Gtk.MenuButton] = []
        self.pictures: list[Gtk.Picture] = []
        self.previews: list[ClipPreview] = []
        for n in range(SLOTS):
            b = Gtk.MenuButton()
            b.add_css_class("clip-slot")
            b.set_always_show_arrow(False)
            b.set_focus_on_click(False)
            b.set_direction(Gtk.ArrowType.RIGHT)
            pic = CellPicture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
            b.set_child(pic)
            pop = ClipPreview(history, on_paste)
            pop.connect("show", lambda p, n=n: self._showing(p, n))
            b.set_popover(pop)
            click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            click.connect("pressed", lambda g, n_press, _x, _y, n=n: self._pressed(g, n, n_press))
            b.add_controller(click)
            self.attach(b, n % 2, n // 2, 1, 1)       # cells in reading order; tab order follows
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
            pic.set_paintable((e.thumb or e.preview or e.texture) if e else None)
            slot.set_sensitive(e is not None)
            if e is None:
                slot.remove_css_class("filled")
                slot.set_tooltip_text("Copies you make appear here" if n == len(self.history.entries) else None)
                slot.update_property([Gtk.AccessibleProperty.LABEL], [f"Empty clipboard slot {n + 1}"])
                if self.previews[n].get_visible():
                    self.previews[n].popdown()
            else:
                slot.add_css_class("filled")
                slot.set_tooltip_text(f"{e.label} · {_size_label(e)} · click for a larger preview · double-click pastes")
                slot.update_property([Gtk.AccessibleProperty.LABEL],
                                     [f"Clipboard copy {n + 1} of {SLOTS}, {e.width}×{e.height}, {_clock(e)}"])
            if e is not None and self.history.is_current(e):
                slot.add_css_class("current")
            else:
                slot.remove_css_class("current")

    def _pressed(self, gesture: Gtk.GestureClick, n: int, n_press: int) -> None:
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)        # the MenuButton must not toggle on its own
        if self.entry_at(n) is None:
            return
        self._cancel_pending(n)
        if n_press >= 2:
            self.paste(n)
            return
        wait = Gtk.Settings.get_default().get_property("gtk-double-click-time") if Gtk.Settings.get_default() else 400
        self._pending[n] = GLib.timeout_add(wait, self._single_click, n)

    def _cancel_pending(self, n: int) -> None:
        src = self._pending.pop(n, None)
        if src is not None:
            GLib.source_remove(src)

    def _single_click(self, n: int) -> bool:
        self._pending.pop(n, None)
        if self.entry_at(n) is not None:
            self.slots[n].popup()
        return False

    def paste(self, n: int) -> bool:
        """Double-click: paste copy ``n`` into the stage (a layer on the open image, or a new image)."""
        e = self.entry_at(n)
        if e is None or self.on_paste is None:
            return False
        self._cancel_pending(n)
        if self.previews[n].get_visible():
            self.previews[n].popdown()
        holder = self.get_ancestor(Gtk.Popover)
        if holder is not None:
            holder.popdown()                                    # the collapsed rail's tray popover closes too
        self.on_paste(e)
        return True

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
        self.set_tooltip_text("Clipboard · the last 4 copies")
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Clipboard tray"])
        self.set_focus_on_click(False)
        pop = Gtk.Popover()
        self.tray = ClipTray(history, on_paste)
        self.tray.set_size_request(200, TRAY_HEIGHT)
        self.tray.set_margin_top(6); self.tray.set_margin_bottom(6); self.tray.set_margin_start(6); self.tray.set_margin_end(6)
        pop.set_child(self.tray)
        self.set_popover(pop)
        history.connect("changed", lambda h: self.set_tooltip_text(
            "Clipboard · the last 4 copies · click to preview" if len(h) else "Clipboard · no copies yet"))
