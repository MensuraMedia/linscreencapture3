"""Orchestrates a capture: hide the studio, freeze the screen, pick a region, copy, save, load.

The authoritative description is ``docs/CAPTURE.md``. In short:

* Modes: ``region`` (draw a box; the capture happens on mouse release, no handles), ``region-plus`` (the box keeps
  eight handles, arrow nudging and Space-move; Enter or a double-click confirms), ``window``, ``screen``.
* Every capture, wherever it was started, is copied to the clipboard first (lossless PNG), then saved to the save
  folder, then loaded into the studio and pushed to its clipboard tray.
* A *hotkey* capture (PrintScreen, ``app.hotkey-capture``, the tray) is always ``region`` with no delay, and does not
  pop the studio up: a hidden studio receives the capture in the background, and a visible one is shown again with
  it. ``Settings.hotkey_opens_editor`` presents the studio every time. With no studio on screen, failures become a
  desktop notification.
"""
from __future__ import annotations
import logging
import time

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
        self._hotkey = False
        self._was_visible = False

    # -- entry points -----------------------------------------------------
    def capture(self, mode: str | None = None, hotkey: bool = False) -> None:
        win = self.app.props.active_window
        if self.busy:
            return
        self._hotkey = hotkey
        settings = self.app.settings
        if self.service is None:
            self.service = CaptureService(settings.backend)
        self.service.preference = settings.backend
        delayed = mode == "delayed"                 # app.capture-delayed: the current mode, delayed
        if delayed:
            mode = None
        if hotkey:
            mode, delayed = "region", False         # PrintScreen is always the fast region capture
        elif win is not None:
            toggle = win.lookup_action("capture-delayed")   # the rail's Delayed toggle (off again on click)
            delayed = delayed or bool(toggle and toggle.get_state().get_boolean())
            if mode is None:
                action = win.lookup_action("capture-mode")
                mode = action.get_state().get_string() if action else "region"
        mode = mode or "region"
        if mode in ("scrolling", "pin"):
            if win:
                win.toast(f"{mode.capitalize()} capture arrives in Phase 6")
            return
        delay = settings.delay_seconds if delayed else 0
        self._mode = mode
        self.busy = True
        self._t0 = time.monotonic()
        LOG.debug("capture requested: mode %s, delay %d s, hotkey %s", mode, delay, hotkey)
        self._was_visible = bool(win and win.get_visible())
        if win is not None:
            if delay:
                win.toast(f"Capturing in {delay} s")
            win.set_visible(False)
        settle = HIDE_SETTLE_MS if self._was_visible else 0    # nothing on screen to repaint away
        GLib.timeout_add(settle + delay * 1000, self._grab)

    @property
    def presents(self) -> bool:
        """Whether this capture ends with the studio on screen."""
        return (not self._hotkey) or self._was_visible or bool(self.app.settings.hotkey_opens_editor)

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
        session = OverlaySession(surface, self._mode, windows, lambda rect: self._finish(surface, rect))
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
        copied = clipboard.copy_surface(surface)        # first: the clipboard is what the user is waiting for
        LOG.debug("clipboard %s (%.0f ms)", "set" if copied else "NOT available", (time.monotonic() - self._t0) * 1000)
        try:
            doc = save_capture(surface, self.app.settings)
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Could not save: {exc}" + (" · the image is on the clipboard" if copied else ""))
            return
        if win is None:
            ensure = getattr(self.app, "ensure_window", None)
            win = ensure() if ensure else None          # the studio receives every capture, even unseen
        if win is not None:
            win.load_document(doc)
            if copied and getattr(win, "clips", None) is not None:
                win.clips.push(surface, doc.name)       # the left rail's clipboard tray
        LOG.info("saved %s (%dx%d)%s in %.0f ms", doc.path, doc.width, doc.height,
                 ", copied to clipboard" if copied else "", (time.monotonic() - self._t0) * 1000)
        self._done(win, doc, copied)

    def _done(self, win, doc: Document | None, copied: bool = False) -> None:
        self.busy = False
        if win is None or not self.presents:
            return
        win.present()
        if doc is not None:
            win.toast(f"Saved {doc.name}" + (" · copied to clipboard" if copied else ""))

    def _fail(self, message: str) -> None:
        self.busy = False
        win = self.app.props.active_window
        if win is None or not self.presents:
            from gi.repository import Gio
            note = Gio.Notification.new("LinScreenCapture")
            note.set_body(message)
            self.app.send_notification("capture-failed", note)
            return
        win.present()
        win.toast(message, timeout=5)
