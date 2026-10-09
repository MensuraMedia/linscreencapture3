"""Last-resort backend: an external screenshot command writing a PNG we load."""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from typing import Callable

import cairo

from .base import WindowInfo, CaptureError

CANDIDATES = (
    ("gnome-screenshot", lambda p: ["gnome-screenshot", "-f", p]),
    ("grim", lambda p: ["grim", p]),
    ("import", lambda p: ["import", "-window", "root", p]),
    ("spectacle", lambda p: ["spectacle", "-b", "-n", "-f", "-o", p]),
)


class CliBackend:
    name = "cli"
    is_async = False

    def tool(self) -> tuple[str, Callable[[str], list[str]]] | None:
        for name, argv in CANDIDATES:
            if shutil.which(name):
                return name, argv
        return None

    def available(self) -> bool:
        return self.tool() is not None

    def capture_screen(self) -> cairo.ImageSurface:
        tool = self.tool()
        if tool is None:
            raise CaptureError("no screenshot command found (gnome-screenshot, grim, import, spectacle)")
        name, argv = tool
        fd, path = tempfile.mkstemp(prefix="lsc-", suffix=".png")
        os.close(fd)
        try:
            subprocess.run(argv(path), check=True, timeout=30, capture_output=True)
            from ..model.document import load_image
            return load_image(path)
        except subprocess.CalledProcessError as exc:
            raise CaptureError(f"{name} failed: {exc.stderr.decode(errors='replace').strip()}") from exc
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def capture_screen_async(self, on_done: Callable) -> None:  # pragma: no cover
        try:
            on_done(self.capture_screen(), None)
        except Exception as exc:  # noqa: BLE001
            on_done(None, exc)

    def list_windows(self) -> list[WindowInfo]:
        return []
