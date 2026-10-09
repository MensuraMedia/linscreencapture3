"""Chooses a capture backend and runs it off the main loop; results come back on the main loop."""
from __future__ import annotations
import os
import threading
from typing import Callable

import cairo
from gi.repository import GLib

from ..backends.base import CaptureBackend, CaptureError, WindowInfo

Callback = Callable[[cairo.ImageSurface | None, Exception | None], None]


def session_type() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "x11" if os.environ.get("DISPLAY") else "unknown").lower()


def default_backends() -> list[CaptureBackend]:
    from ..backends.portal import PortalBackend
    from ..backends.x11 import X11Backend
    from ..backends.cli import CliBackend
    return [PortalBackend(), X11Backend(), CliBackend()]


class CaptureService:
    def __init__(self, preference: str = "auto", backends: list[CaptureBackend] | None = None,
                 use_thread: bool = True, session: str | None = None):
        self.preference = preference
        self.backends = backends if backends is not None else default_backends()
        self.use_thread = use_thread
        self.session = session or session_type()
        self.last_used: str | None = None

    # -- selection --------------------------------------------------------
    def order(self) -> list[CaptureBackend]:
        """Backends to try, in order, honouring the preference and the session type."""
        by_name = {b.name: b for b in self.backends}
        if self.preference in by_name:
            first = [by_name[self.preference]]
            rest = [b for b in self.backends if b.name != self.preference]
        else:
            pref = ["x11", "portal", "cli"] if self.session == "x11" else ["portal", "x11", "cli"]
            first, rest = [by_name[n] for n in pref if n in by_name], [b for b in self.backends if b.name not in pref]
        return [b for b in first + rest if b.available()]

    def list_windows(self) -> list[WindowInfo]:
        for b in self.order():
            try:
                wins = b.list_windows()
            except Exception:  # noqa: BLE001
                wins = []
            if wins:
                return wins
        return []

    # -- capture ----------------------------------------------------------
    def capture_screen(self, on_done: Callback) -> None:
        """Try backends in order; the first success wins; ``on_done`` runs on the main loop."""
        chain = self.order()
        if not chain:
            on_done(None, CaptureError("no capture backend is available on this session"))
            return
        self._try(chain, 0, on_done, None)

    def _try(self, chain: list[CaptureBackend], i: int, on_done: Callback, last_err: Exception | None) -> None:
        if i >= len(chain):
            on_done(None, last_err or CaptureError("capture failed"))
            return
        backend = chain[i]

        def finish(surface, err):
            if surface is not None:
                self.last_used = backend.name
                self._main(on_done, surface, None)
            else:
                self._main(self._try, chain, i + 1, on_done, err)

        if backend.is_async:
            backend.capture_screen_async(finish)
        elif self.use_thread:
            def work():
                try:
                    finish(backend.capture_screen(), None)
                except Exception as exc:  # noqa: BLE001
                    finish(None, exc)
            threading.Thread(target=work, daemon=True).start()
        else:
            try:
                finish(backend.capture_screen(), None)
            except Exception as exc:  # noqa: BLE001
                finish(None, exc)

    def _main(self, fn, *args) -> None:
        if self.use_thread:
            GLib.idle_add(lambda: (fn(*args), False)[1])
        else:
            fn(*args)
