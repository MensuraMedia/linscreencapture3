"""Where captures land on disk."""
from __future__ import annotations
import os
import pathlib

import cairo

from ..model.document import Document
from ..model.settings import Settings


def save_capture(surface: cairo.ImageSurface, settings: Settings) -> Document:
    """Write ``surface`` to the configured folder with the next name and return its Document."""
    folder = pathlib.Path(os.path.expanduser(settings.screenshot_path))
    folder.mkdir(parents=True, exist_ok=True)
    name = settings.next_filename()
    doc = Document(surface)
    doc.save(str(folder / name), fmt=settings.format, quality=settings.jpeg_quality)
    return doc


def duplicate_path(path: str) -> str:
    """``shot.png`` -> ``shot copy.png``, then ``shot copy 2.png``… (the first name not on disk)."""
    p = pathlib.Path(path)
    stem, ext = p.stem, p.suffix
    candidate = p.with_name(f"{stem} copy{ext}")
    n = 2
    while candidate.exists():
        candidate = p.with_name(f"{stem} copy {n}{ext}")
        n += 1
    return str(candidate)


def duplicate_file(path: str) -> str:
    """Copy the file next to itself with a ``copy`` suffix and return the new path."""
    import shutil
    target = duplicate_path(path)
    shutil.copy2(path, target)
    return target
