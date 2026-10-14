"""Whole-image operations (pure): crop, scale, rotate, flip, brightness/contrast/grayscale/invert.

Each returns a new base surface plus a function that maps annotation coordinates from the old
image to the new one, so layers follow the pixels. Used by ``undo.TransformBase``.
"""
from __future__ import annotations
import math
from typing import Callable

import cairo
from PIL import Image, ImageEnhance, ImageOps

from ..model.document import pil_from_surface, surface_from_pil

Point = tuple[float, float]
Mapper = Callable[[float, float], Point]


def crop(base: cairo.ImageSurface, x: int, y: int, w: int, h: int) -> tuple[cairo.ImageSurface, Mapper]:
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(base.get_width(), int(x + w)), min(base.get_height(), int(y + h))
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, x1 - x0), max(1, y1 - y0))
    cr = cairo.Context(out)
    cr.set_source_surface(base, -x0, -y0)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.paint()
    out.flush()
    return out, lambda px, py: (px - x0, py - y0)


def scale(base: cairo.ImageSurface, new_w: int, new_h: int) -> tuple[cairo.ImageSurface, Mapper]:
    new_w, new_h = max(1, int(new_w)), max(1, int(new_h))
    img = pil_from_surface(base).resize((new_w, new_h), Image.LANCZOS)
    sx, sy = new_w / base.get_width(), new_h / base.get_height()
    return surface_from_pil(img), lambda px, py: (px * sx, py * sy)


def rotate(base: cairo.ImageSurface, degrees: int) -> tuple[cairo.ImageSurface, Mapper]:
    """Rotate clockwise by 90, 180 or 270 degrees."""
    degrees %= 360
    w, h = base.get_width(), base.get_height()
    img = pil_from_surface(base)
    if degrees == 90:
        return surface_from_pil(img.transpose(Image.ROTATE_270)), lambda px, py: (h - py, px)
    if degrees == 180:
        return surface_from_pil(img.transpose(Image.ROTATE_180)), lambda px, py: (w - px, h - py)
    if degrees == 270:
        return surface_from_pil(img.transpose(Image.ROTATE_90)), lambda px, py: (py, w - px)
    return base, lambda px, py: (px, py)


def flip(base: cairo.ImageSurface, horizontal: bool) -> tuple[cairo.ImageSurface, Mapper]:
    w, h = base.get_width(), base.get_height()
    img = pil_from_surface(base)
    if horizontal:
        return surface_from_pil(img.transpose(Image.FLIP_LEFT_RIGHT)), lambda px, py: (w - px, py)
    return surface_from_pil(img.transpose(Image.FLIP_TOP_BOTTOM)), lambda px, py: (px, h - py)


def adjust(base: cairo.ImageSurface, brightness: float = 0.0, contrast: float = 0.0,
           grayscale: bool = False, invert: bool = False) -> cairo.ImageSurface:
    """brightness/contrast in -100..100 (0 = unchanged)."""
    img = pil_from_surface(base)
    rgb, alpha = img.convert("RGB"), img.getchannel("A")
    if brightness:
        rgb = ImageEnhance.Brightness(rgb).enhance(1.0 + brightness / 100.0)
    if contrast:
        rgb = ImageEnhance.Contrast(rgb).enhance(1.0 + contrast / 100.0)
    if grayscale:
        rgb = ImageOps.grayscale(rgb).convert("RGB")
    if invert:
        rgb = ImageOps.invert(rgb)
    rgb.putalpha(alpha)
    return surface_from_pil(rgb)


def identity(px: float, py: float) -> Point:
    return px, py


def crop_masked(base: cairo.ImageSurface, area) -> tuple[cairo.ImageSurface, Mapper]:
    """Crop to the area's bounding box and clear everything outside the area (round / point chain)."""
    from ..model.annotations import area_path
    if area.shape == "points" and area.points:
        xs = [p[0] for p in area.points]; ys = [p[1] for p in area.points]
        x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    else:
        x, y, w, h = area.rect
    x0, y0 = max(0, int(math.floor(x))), max(0, int(math.floor(y)))
    x1, y1 = min(base.get_width(), int(math.ceil(x + w))), min(base.get_height(), int(math.ceil(y + h)))
    out, mapper = crop(base, x0, y0, max(1, x1 - x0), max(1, y1 - y0))
    if area.shape != "box":
        cr = cairo.Context(out)
        cr.translate(-x0, -y0)
        cr.set_operator(cairo.OPERATOR_DEST_IN)      # keep only what lies inside the area
        cr.set_source_rgba(0, 0, 0, 1)
        if area_path(cr, area):
            cr.fill()
        out.flush()
    return out, mapper
