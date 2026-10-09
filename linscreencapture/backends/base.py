"""Capture backend protocol. Backends return cairo image surfaces in root (screen) coordinates."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Protocol

import cairo


@dataclass(frozen=True)
class WindowInfo:
    id: int
    title: str
    x: int
    y: int
    width: int
    height: int

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height


class CaptureError(RuntimeError):
    pass


class CaptureBackend(Protocol):
    name: str
    is_async: bool  # True: capture_screen_async must be used from the main loop (portal)

    def available(self) -> bool: ...
    def capture_screen(self) -> cairo.ImageSurface: ...                     # blocking; run in a thread
    def capture_screen_async(self, on_done: Callable[[cairo.ImageSurface | None, Exception | None], None]) -> None: ...
    def list_windows(self) -> list[WindowInfo]: ...                         # may be empty


def crop(surface: cairo.ImageSurface, x: int, y: int, w: int, h: int) -> cairo.ImageSurface:
    """A new surface holding the given region of ``surface`` (clamped to its bounds)."""
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(surface.get_width(), int(x + w)), min(surface.get_height(), int(y + h))
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.set_source_surface(surface, -x0, -y0)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.paint()
    out.flush()
    return out
