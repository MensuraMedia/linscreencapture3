"""The document: a base image plus ordered annotation layers. No GTK."""
from __future__ import annotations
import itertools
import os
from dataclasses import dataclass, field

import cairo
from PIL import Image

from .annotations import Annotation, NAMES, BADGE, draw, renumber_steps

_ids = itertools.count(1)


@dataclass
class Layer:
    annotation: Annotation
    name: str = ""
    visible: bool = True
    id: int = field(default_factory=lambda: next(_ids))

    def __post_init__(self) -> None:
        if not self.name:
            self.name = NAMES[self.annotation.kind]

    @property
    def badge(self) -> str:
        return BADGE[self.annotation.kind]


# ---------------------------------------------------------------- image <-> cairo
def surface_from_pil(img: Image.Image) -> cairo.ImageSurface:
    img = img.convert("RGBA")
    w, h = img.size
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    # cairo wants premultiplied BGRA; Pillow's "BGRa" raw mode premultiplies for us
    data = img.tobytes("raw", "BGRa")
    stride = surf.get_stride()
    buf = surf.get_data()
    if stride == w * 4:
        buf[:] = data
    else:
        for row in range(h):
            buf[row * stride:row * stride + w * 4] = data[row * w * 4:(row + 1) * w * 4]
    surf.mark_dirty()
    return surf


def pil_from_surface(surf: cairo.ImageSurface) -> Image.Image:
    surf.flush()
    w, h, stride = surf.get_width(), surf.get_height(), surf.get_stride()
    data = bytes(surf.get_data())
    if stride != w * 4:
        data = b"".join(data[r * stride:r * stride + w * 4] for r in range(h))
    return Image.frombuffer("RGBA", (w, h), data, "raw", "BGRa", 0, 1).copy()


def load_image(path: str) -> cairo.ImageSurface:
    with Image.open(path) as img:
        img.load()
        return surface_from_pil(img)


def copy_surface(surf: cairo.ImageSurface) -> cairo.ImageSurface:
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, surf.get_width(), surf.get_height())
    cr = cairo.Context(out)
    cr.set_source_surface(surf, 0, 0)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.paint()
    out.flush()
    return out


# ---------------------------------------------------------------- document
class Document:
    """Base image + layers. Mutate through ``UndoStack`` commands from the controllers."""

    def __init__(self, base: cairo.ImageSurface | None = None, path: str | None = None):
        self.base = base
        self.path = path
        self.layers: list[Layer] = []
        self.dirty = False
        self.format = "PNG"

    # -- basics -----------------------------------------------------------
    @property
    def width(self) -> int:
        return self.base.get_width() if self.base else 0

    @property
    def height(self) -> int:
        return self.base.get_height() if self.base else 0

    @property
    def name(self) -> str:
        return os.path.basename(self.path) if self.path else "Untitled"

    @property
    def empty(self) -> bool:
        return self.base is None

    def summary(self) -> str:
        """The header subtitle: ``Edit · 1920×1080 · PNG · 2 layers · unsaved``."""
        if self.empty:
            return ""
        n = len(self.layers) + 1
        return f"Edit · {self.width}×{self.height} · {self.format} · {n} layer{'s' if n != 1 else ''} · {'unsaved' if self.dirty else 'saved'}"

    @classmethod
    def open(cls, path: str) -> "Document":
        doc = cls(load_image(path), path)
        doc.format = (os.path.splitext(path)[1][1:] or "png").upper().replace("JPG", "JPEG")
        return doc

    # -- layers (plain operations; undo wraps them) -----------------------
    def add_layer(self, annotation: Annotation, index: int | None = None) -> Layer:
        layer = Layer(annotation)
        if index is None:
            self.layers.append(layer)
        else:
            self.layers.insert(index, layer)
        if annotation.kind == "step":
            renumber_steps(l.annotation for l in self.layers)
        self.dirty = True
        return layer

    def remove_layer(self, layer: Layer) -> int:
        index = self.layers.index(layer)
        del self.layers[index]
        if layer.annotation.kind == "step":
            renumber_steps(l.annotation for l in self.layers)
        self.dirty = True
        return index

    def move_layer(self, layer: Layer, index: int) -> None:
        self.layers.remove(layer)
        self.layers.insert(max(0, min(index, len(self.layers))), layer)
        renumber_steps(l.annotation for l in self.layers)
        self.dirty = True

    def find_layer(self, layer_id: int) -> Layer | None:
        return next((l for l in self.layers if l.id == layer_id), None)

    # -- rendering ----------------------------------------------------------
    def render(self, cr: cairo.Context, target: cairo.ImageSurface | None, include_hidden: bool = False) -> None:
        """Paint base and layers onto ``cr`` (whose target image surface is ``target``)."""
        if self.base is not None:
            cr.save()
            cr.set_source_surface(self.base, 0, 0)
            cr.paint()
            cr.restore()
        for layer in self.layers:
            if layer.visible or include_hidden:
                draw(layer.annotation, cr, target)

    def flatten(self) -> cairo.ImageSurface:
        """A new surface with base and visible layers composited; the document is unchanged."""
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, self.width), max(1, self.height))
        self.render(cairo.Context(out), out)
        out.flush()
        return out

    def flatten_into_base(self) -> None:
        self.base = self.flatten()
        self.layers.clear()
        self.dirty = True

    def save(self, path: str | None = None, fmt: str | None = None, quality: int = 92) -> str:
        path = path or self.path
        if not path:
            raise ValueError("no path to save to")
        fmt = (fmt or os.path.splitext(path)[1][1:] or "png").upper().replace("JPG", "JPEG")
        img = pil_from_surface(self.flatten())
        if fmt == "JPEG":
            img = img.convert("RGB")
            img.save(path, "JPEG", quality=quality)
        elif fmt == "WEBP":
            img.save(path, "WEBP", quality=quality)
        else:
            img.save(path, "PNG")
        self.path, self.format, self.dirty = path, fmt, False
        return path
