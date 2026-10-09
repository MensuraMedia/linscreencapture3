"""Orchestrates a capture: hide the studio, freeze the screen, pick a region, save, copy, show."""
from __future__ import annotations
import logging
import os
import time
from typing import Callable

import cairo
from gi.repository import GLib

from ..backends.base import crop
from ..services.capture_service import CaptureService
from ..services import clipboard
from ..services.file_store import save_capture
from ..model.document import Document

HIDE_SETTLE_MS = 300  # time for the compositor to repaint without the studio window
LOG = logging.getLogger("linscreencapture.capture")


class CaptureController:
    def __init__(self, app, service: CaptureService | None = None):
        self.app = app
        self.service = service
        self.busy = False

    # -- entry points -----------------------------------------------------
    def capture(self, mode: str | None = None) -> None:
        win = self.app.props.active_window
        if self.busy:
            return
        settings = self.app.settings
        if self.service is None:
            self.service = CaptureService(settings.backend)
        self.service.preference = settings.backend
        if mode is None and win is not None:
            action = win.lookup_action("capture-mode")
            mode = action.get_state().get_string() if action else "region"
        mode = mode or "region"
        if mode in ("scrolling", "pin"):
            if win:
                win.toast(f"{mode.capitalize()} capture arrives in Phase 6")
            return
        delay = settings.delay_seconds if mode == "delayed" else 0
        self._mode = "region" if mode == "delayed" else mode
        self.busy = True
        self._t0 = time.monotonic()
        LOG.debug("capture requested: mode %s, delay %d s, backend preference %s", mode, delay, settings.backend)
        self._was_visible = bool(win and win.get_visible())
        if win is not None:
            if delay:
                win.toast(f"Capturing in {delay} s")
            win.set_visible(False)
        GLib.timeout_add(HIDE_SETTLE_MS + delay * 1000, self._grab)

    # -- steps -------------------------------------------------------------
    def _grab(self) -> bool:
        LOG.debug("freezing the screen (%.0f ms after request)", (time.monotonic() - self._t0) * 1000)
        self.service.capture_screen(self._got_screen)
        return False

    def _got_screen(self, surface: cairo.ImageSurface | None, err: Exception | None) -> None:
        if surface is None:
            LOG.error("capture failed: %s", err)
            self._fail(f"Capture failed: {err}")
            return
        LOG.debug("screen frozen: %dx%d via %s backend (%.0f ms)", surface.get_width(), surface.get_height(),
                  self.service.last_used, (time.monotonic() - self._t0) * 1000)
        if self._mode == "screen":
            self._finish(surface, None)
            return
        from ..ui.capture_overlay import OverlaySession
        windows = self.service.list_windows() if self._mode == "window" else []
        if self._mode == "window" and not windows:
            LOG.info("no window list from the backend; falling back to region mode")
            self._mode = "region"
        LOG.debug("overlay: mode %s, %d windows listed", self._mode, len(windows))
        session = OverlaySession(surface, self._mode, windows, lambda rect: self._finish(surface, rect),
                                 simple=(self.app.settings.selection_style == "simple"))
        session.show()

    def _finish(self, surface: cairo.ImageSurface, rect: tuple[int, int, int, int] | None) -> None:
        win = self.app.props.active_window
        if rect is None and self._mode != "screen":
            LOG.debug("capture cancelled by the user")
            self._done(win, None)
            return
        if rect is not None:
            surface = crop(surface, *rect)
            LOG.debug("cropped to %s", rect)
        settings = self.app.settings
        try:
            doc = save_capture(surface, settings)
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Could not save: {exc}")
            return
        copied = clipboard.copy_surface(surface) if settings.copy_to_clipboard else False
        LOG.info("saved %s (%dx%d)%s in %.0f ms", doc.path, doc.width, doc.height,
                 ", copied to clipboard" if copied else "", (time.monotonic() - self._t0) * 1000)
        self._done(win, doc, copied)

    def _done(self, win, doc: Document | None, copied: bool = False) -> None:
        self.busy = False
        if win is None:
            return
        if doc is not None:
            win.load_document(doc)
        win.present()
        if doc is not None:
            win.toast(f"Saved {doc.name}" + (" · copied to clipboard" if copied else ""))

    def _fail(self, message: str) -> None:
        self.busy = False
        win = self.app.props.active_window
        if win is not None:
            win.present()
            win.toast(message, timeout=5)
