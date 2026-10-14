"""The last few images this app put on the clipboard, for the left rail's clipboard tray.

Every copy the app makes (Ctrl+C in the editor, a capture copied on save, Copy in the Library) is
pushed here; the tray shows the newest one (``LIMIT``; more slots are on the roadmap). An entry can be copied back to the clipboard or removed;
removing the entry that currently owns the clipboard clears the clipboard too. Copies made by other
applications are not tracked (reading the clipboard on every change would be intrusive).
"""
from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field

import cairo
from gi.repository import Gdk, GLib, GObject

from . import clipboard

LIMIT = 1          # one copy for now; the tray grows to several slots later (roadmap: HANDOFF §8)
PREVIEW_W, PREVIEW_H = 320, 200     # the tray's larger sample; the slots show the same texture smaller


@dataclass
class ClipEntry:
    surface: cairo.ImageSurface
    label: str
    when: float = field(default_factory=time.time)
    digest: str = ""
    texture: object = None          # full-size Gdk.Texture (pasting)
    preview: object = None          # ≤ 320×200 Gdk.Texture (tray slots and the preview popover)

    @property
    def width(self) -> int:
        return self.surface.get_width()

    @property
    def height(self) -> int:
        return self.surface.get_height()


def preview_surface(surface: cairo.ImageSurface, max_w: int = PREVIEW_W, max_h: int = PREVIEW_H) -> cairo.ImageSurface:
    """``surface`` scaled to fit max_w × max_h (never enlarged)."""
    w, h = surface.get_width(), surface.get_height()
    scale = min(1.0, max_w / max(1, w), max_h / max(1, h))
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, tw, th)
    cr = cairo.Context(out)
    cr.scale(tw / w, th / h)
    cr.set_source_surface(surface, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    out.flush()
    return out


def _digest(surface: cairo.ImageSurface) -> str:
    surface.flush()
    h = hashlib.blake2b(digest_size=12)
    h.update(f"{surface.get_width()}x{surface.get_height()}".encode())
    h.update(bytes(surface.get_data()))
    return h.hexdigest()


class ClipHistory(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, limit: int = LIMIT, watch_clipboard: bool = True):
        super().__init__()
        self.limit = limit
        self.entries: list[ClipEntry] = []       # newest first
        self._current: ClipEntry | None = None   # the entry that owns the system clipboard right now
        if watch_clipboard:
            display = Gdk.Display.get_default()
            if display is not None:
                display.get_clipboard().connect("changed", self._clipboard_changed)

    # -- recording ------------------------------------------------------------
    def push(self, surface: cairo.ImageSurface, label: str = "Copy") -> ClipEntry:
        """Record ``surface`` as the newest copy (the same pixels twice in a row are not repeated)."""
        digest = _digest(surface)
        for e in self.entries:
            if e.digest == digest:
                self.entries.remove(e)
                e.when = time.time()
                e.label = label
                self.entries.insert(0, e)
                self._current = e
                self.emit("changed")
                return e
        entry = ClipEntry(surface, label, digest=digest, texture=clipboard.texture_from_surface(surface),
                          preview=clipboard.texture_from_surface(preview_surface(surface)))
        self.entries.insert(0, entry)
        del self.entries[self.limit:]
        self._current = entry
        self.emit("changed")
        return entry

    def copy(self, entry: ClipEntry) -> bool:
        """Put ``entry`` back on the system clipboard and make it the newest."""
        ok = clipboard.copy_surface(entry.surface)
        if entry in self.entries:
            self.entries.remove(entry)
        self.entries.insert(0, entry)
        entry.when = time.time()
        self._current = entry
        self.emit("changed")
        return ok

    def remove(self, entry: ClipEntry) -> None:
        """Forget ``entry``; if it owns the clipboard, the clipboard is cleared as well."""
        if entry in self.entries:
            self.entries.remove(entry)
        if entry is self._current:
            self._current = None
            display = Gdk.Display.get_default()
            if display is not None:
                display.get_clipboard().set_content(None)
        self.emit("changed")

    def is_current(self, entry: ClipEntry) -> bool:
        return entry is self._current

    def _clipboard_changed(self, clip: Gdk.Clipboard) -> None:
        if not clip.is_local():                   # another application took the clipboard
            self._current = None
            self.emit("changed")

    def __len__(self) -> int:
        return len(self.entries)
