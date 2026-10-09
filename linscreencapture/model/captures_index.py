"""Thumbnails of the capture folder, newest first, for the Captures panel."""
from __future__ import annotations
import os
import threading
import pathlib

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject

EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
THUMB_W, THUMB_H = 188, 128  # 2x of the 94x64 cell


class CaptureEntry(GObject.Object):
    __gtype_name__ = "LscCaptureEntry"
    path = GObject.Property(type=str, default="")
    name = GObject.Property(type=str, default="")
    mtime = GObject.Property(type=float, default=0.0)
    texture = GObject.Property(type=Gdk.Texture, default=None)

    def __init__(self, path: str, mtime: float, texture=None):
        super().__init__()
        self.path = path
        self.name = os.path.basename(path)
        self.mtime = mtime
        self.texture = texture


class CapturesIndex(GObject.Object):
    """``store`` is a Gio.ListStore of CaptureEntry sorted newest first."""
    __gsignals__ = {"scanned": (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self, folder: str):
        super().__init__()
        self.folder = folder
        self.store = Gio.ListStore.new(CaptureEntry)
        self._gen = 0

    def scan(self) -> None:
        """Rescan in a worker thread; the store is replaced on the main loop."""
        self._gen += 1
        gen = self._gen
        folder = self.folder
        threading.Thread(target=self._worker, args=(folder, gen), daemon=True).start()

    def _worker(self, folder: str, gen: int) -> None:
        entries: list[CaptureEntry] = []
        p = pathlib.Path(folder).expanduser()
        if p.is_dir():
            files = [f for f in p.iterdir() if f.suffix.lower() in EXTS and f.is_file()]
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files[:200]:
                tex = None
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(f), THUMB_W, THUMB_H, True)
                    tex = Gdk.Texture.new_for_pixbuf(pb)
                except GLib.Error:
                    pass
                entries.append(CaptureEntry(str(f), f.stat().st_mtime, tex))
        GLib.idle_add(self._apply, entries, gen)

    def _apply(self, entries, gen: int) -> bool:
        if gen != self._gen:
            return False
        self.store.remove_all()
        for e in entries:
            self.store.append(e)
        self.emit("scanned", len(entries))
        return False
