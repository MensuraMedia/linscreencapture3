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
