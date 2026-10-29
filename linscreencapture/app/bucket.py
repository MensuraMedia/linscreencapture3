"""Bucket fill (the paint-bucket tool): flood the pixels that match the clicked one. Pure numpy, no GTK.

Pixels match when every channel of their premultiplied BGRA value is within ``tolerance`` (0–255) of the seed's.
Contiguous fills grow from the seed through matching pixels (4-connected, a scanline fill: whole runs per row, so it
stays fast on full-screen captures); otherwise every matching pixel on the page is filled. The result is a surface
cropped to the filled area, in the fill colour at ``opacity``, and its top-left on the page: the editor adds it as a
``bucket`` layer, so a fill is undoable and never touches the pixels beneath it.
"""
from __future__ import annotations

import cairo
import numpy as np

TOLERANCE = 32


def _pixels(surface: cairo.ImageSurface) -> np.ndarray:
    surface.flush()
    h, stride = surface.get_height(), surface.get_stride()
    return np.ndarray((h, stride // 4, 4), dtype=np.uint8, buffer=surface.get_data())[:, :surface.get_width(), :]


def matching(surface: cairo.ImageSurface, x: int, y: int, tolerance: int = TOLERANCE) -> np.ndarray:
    """Boolean mask of the pixels within ``tolerance`` of pixel (x, y)."""
    px = _pixels(surface).astype(np.int16)
    seed = px[y, x]
    return (np.abs(px - seed) <= tolerance).all(axis=2)


def _runs(row: np.ndarray) -> np.ndarray:
    """Start indices of the True runs in a boolean row."""
    edges = np.flatnonzero(row[1:] & ~row[:-1]) + 1
    return np.concatenate(([0], edges)) if row.size and row[0] else edges


def flood(mask: np.ndarray, x: int, y: int) -> np.ndarray:
    """The 4-connected region of ``mask`` that contains (x, y) (a scanline flood fill)."""
    h, w = mask.shape
    filled = np.zeros_like(mask)
    if not mask[y, x]:
        return filled
    stack = [(x, y)]
    while stack:
        sx, sy = stack.pop()
        if filled[sy, sx] or not mask[sy, sx]:
            continue
        row = mask[sy]
        gaps = np.flatnonzero(~row)
        left = gaps[gaps < sx]
        right = gaps[gaps > sx]
        l = int(left[-1]) + 1 if left.size else 0
        r = int(right[0]) if right.size else w
        filled[sy, l:r] = True
        for ny in (sy - 1, sy + 1):
            if 0 <= ny < h:
                seg = mask[ny, l:r] & ~filled[ny, l:r]
                for start in _runs(seg):
                    stack.append((l + int(start), ny))
    return filled


def fill(surface: cairo.ImageSurface, x: int, y: int, rgb: tuple[float, float, float], tolerance: int = TOLERANCE,
         contiguous: bool = True, opacity: float = 1.0):
    """``(painted surface, left, top)`` for a fill at (x, y) of ``surface``; None outside it or when nothing matches."""
    w, h = surface.get_width(), surface.get_height()
    if not (0 <= x < w and 0 <= y < h):
        return None
    mask = matching(surface, x, y, int(tolerance))
    if contiguous:
        mask = flood(mask, x, y)
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0)
    buf = _pixels(out)
    a = max(0.0, min(1.0, opacity))
    bgra = np.array([round(rgb[2] * a * 255), round(rgb[1] * a * 255), round(rgb[0] * a * 255), round(a * 255)],
                    dtype=np.uint8)                         # premultiplied
    buf[mask[y0:y1, x0:x1]] = bgra
    out.mark_dirty()
    return out, x0, y0
