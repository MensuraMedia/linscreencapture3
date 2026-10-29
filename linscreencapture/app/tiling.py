"""Tile several images on one page (Library → Combine). Pure geometry, no GTK.

The layout is a grid: every column is as wide as its widest image, every row as tall as its tallest, each image
sits centred in its cell at 1:1, and cells are ``gap`` px apart with a ``margin`` around the whole. Images fill the
grid in reading order. Two images always go side by side; for more, every column count is tried and the one with
the least empty page wins, nudged towards a screen-shaped (16:9) page so a long row or a tall column loses.
"""
from __future__ import annotations
import math

GAP = 10
MARGIN = 10
TARGET_ASPECT = 16 / 9


def _grid(sizes: list[tuple[int, int]], cols: int, gap: int, margin: int):
    rows = math.ceil(len(sizes) / cols)
    col_w = [0] * cols
    row_h = [0] * rows
    for n, (w, h) in enumerate(sizes):
        col_w[n % cols] = max(col_w[n % cols], w)
        row_h[n // cols] = max(row_h[n // cols], h)
    width = 2 * margin + sum(col_w) + gap * (cols - 1)
    height = 2 * margin + sum(row_h) + gap * (rows - 1)
    xs = [margin + sum(col_w[:c]) + gap * c for c in range(cols)]
    ys = [margin + sum(row_h[:r]) + gap * r for r in range(rows)]
    places = []
    for n, (w, h) in enumerate(sizes):
        c, r = n % cols, n // cols
        places.append((xs[c] + (col_w[c] - w) // 2, ys[r] + (row_h[r] - h) // 2))
    return width, height, places


def _score(width: int, height: int, sizes, aspect: float) -> float:
    used = sum(w * h for w, h in sizes) or 1
    waste = width * height / used                       # 1.0 = no empty page at all
    shape = abs(math.log((width / height) / aspect))    # 0 = exactly the target shape
    return waste + 0.35 * shape


def columns_for(sizes: list[tuple[int, int]], gap: int = GAP, margin: int = MARGIN,
                aspect: float = TARGET_ASPECT) -> int:
    """The column count ``tile`` uses for ``sizes``."""
    n = len(sizes)
    if n <= 2:
        return max(1, n)                                 # one image alone, two side by side
    best, best_cols = None, 1
    for cols in range(1, n + 1):
        if cols > 1 and math.ceil(n / cols) == math.ceil(n / (cols - 1)):
            continue                                     # same row count as fewer columns: a ragged last row only
        w, h, _ = _grid(sizes, cols, gap, margin)
        s = _score(w, h, sizes, aspect)
        if best is None or s < best - 1e-9:
            best, best_cols = s, cols
    return best_cols


def tile(sizes: list[tuple[int, int]], gap: int = GAP, margin: int = MARGIN,
         aspect: float = TARGET_ASPECT) -> tuple[int, int, list[tuple[int, int]]]:
    """Page size and each image's top-left for ``sizes`` (w, h) in order: ``(width, height, [(x, y), …])``."""
    if not sizes:
        return 2 * margin, 2 * margin, []
    return _grid(list(sizes), columns_for(sizes, gap, margin, aspect), gap, margin)
