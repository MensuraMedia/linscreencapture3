"""Pure tool geometry: drag → annotation, handles for the selected annotation, handle drags → edits."""
from __future__ import annotations
import math
from dataclasses import replace

from ..model.annotations import (Annotation, Style, snap45, constrain_square, callout_box, step_radius,
                                 image_corners, image_centre, to_local, to_page, normalise_angle)

DRAG_TOOLS = ("arrow", "line", "box", "circle", "blur", "pixelate", "callout", "crop")   # ("fill" retired 2026-10-18)
STROKE_TOOLS = ("pen", "marker", "eraser")
AREA_TOOLS = {"area_box": "box", "area_round": "round", "area_points": "points"}   # tool -> Annotation.shape
CLICK_TOOLS = ("text", "step", "bucket")
MIN_DRAG = 3.0
ROTATE_REACH_PX = 26      # on-screen distance of an image layer's rotate handle above its top edge
ROTATE_SNAP = 15.0        # Shift while rotating: whole multiples of this many degrees


def annotation_from_drag(tool: str, x1: float, y1: float, x2: float, y2: float, style: Style,
                         shift: bool = False, ctrl: bool = False) -> Annotation | None:
    """Build the annotation a drag from (x1, y1) to (x2, y2) produces, or None if too small."""
    if tool not in DRAG_TOOLS or tool == "crop":
        return None
    if tool in ("arrow", "line") and shift:
        x2, y2 = snap45(x1, y1, x2, y2)
    if tool in ("box", "circle", "fill", "blur", "pixelate") and ctrl:
        x2, y2 = constrain_square(x1, y1, x2, y2)
    if tool in ("arrow", "line"):
        if math.hypot(x2 - x1, y2 - y1) < MIN_DRAG:
            return None
    elif tool != "callout" and (abs(x2 - x1) < MIN_DRAG or abs(y2 - y1) < MIN_DRAG):
        return None
    return Annotation(tool, x1, y1, x2, y2, style=style.copy())


def annotation_from_points(tool: str, points: list[tuple[float, float]], style: Style) -> Annotation | None:
    if tool not in STROKE_TOOLS or not points:
        return None
    pts = [points[0]]
    for p in points[1:]:
        if math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) >= 1.0:   # drop sub-pixel jitter
            pts.append(p)
    return Annotation(tool, pts[0][0], pts[0][1], pts[-1][0], pts[-1][1], style=style.copy(), points=pts)


def annotation_from_click(tool: str, x: float, y: float, style: Style, text: str = "", number: int = 1) -> Annotation | None:
    if tool == "text":
        return Annotation("text", x, y, x, y, style=style.copy(), text=text)
    if tool == "step":
        return Annotation("step", x, y, x, y, style=style.copy(), number=number)
    return None


# ---------------------------------------------------------------- handles
def handles_for(a: Annotation, zoom: float = 1.0) -> dict[str, tuple[float, float]]:
    """Named handle positions (image px) for the selected annotation.

    An image layer has eight resize handles on its turned frame plus ``rotate``, ``ROTATE_REACH_PX`` screen px
    above its top edge (``zoom`` converts that to image px)."""
    k = a.kind
    if k == "image":
        x, y, w, h = a.rect
        local = {"nw": (x, y), "n": (x + w / 2, y), "ne": (x + w, y), "e": (x + w, y + h / 2),
                 "se": (x + w, y + h), "s": (x + w / 2, y + h), "sw": (x, y + h), "w": (x, y + h / 2),
                 "rotate": (x + w / 2, y - ROTATE_REACH_PX / max(zoom, 1e-6))}
        return {n: to_page(a, *p) for n, p in local.items()}
    if k in ("arrow", "line"):
        return {"start": (a.x1, a.y1), "end": (a.x2, a.y2)}
    if k == "callout":
        x, y, w, h = callout_box(a)
        return {"anchor": (x, y), "target": (a.x2, a.y2)}
    if k in ("box", "circle", "fill", "blur", "pixelate"):
        x, y, w, h = a.rect
        return {"nw": (x, y), "n": (x + w / 2, y), "ne": (x + w, y), "e": (x + w, y + h / 2),
                "se": (x + w, y + h), "s": (x + w / 2, y + h), "sw": (x, y + h), "w": (x, y + h / 2)}
    return {}   # text, pen, marker, step: move only


def handle_at(a: Annotation, px: float, py: float, tolerance: float, zoom: float = 1.0) -> str | None:
    for name, (hx, hy) in handles_for(a, zoom).items():
        if abs(px - hx) <= tolerance and abs(py - hy) <= tolerance:
            return name
    return None


MIN_IMAGE_PX = 4.0


def image_resize(a: Annotation, handle: str, px: float, py: float, keep: bool = True, centre: bool = False) -> dict:
    """Resize an image layer the way image editors do.

    Corner handles keep the layer's proportions (``keep``; Shift turns it off for a free stretch); edge handles
    stretch one side. ``centre`` (Ctrl) resizes about the centre. The box never flips inside out: it stops at
    ``MIN_IMAGE_PX``."""
    x, y, w, h = a.rect
    l, t, r, b = x, y, x + w, y + h
    cx, cy = x + w / 2, y + h / 2
    horiz = "w" in handle or "e" in handle
    vert = "n" in handle or "s" in handle
    if centre:
        nw = 2 * abs(px - cx) if horiz else w
        nh = 2 * abs(py - cy) if vert else h
    else:
        nw = ((px - l) if "e" in handle else (r - px)) if horiz else w
        nh = ((py - t) if "s" in handle else (b - py)) if vert else h
    nw, nh = max(MIN_IMAGE_PX, nw), max(MIN_IMAGE_PX, nh)
    if keep and horiz and vert and w > 0 and h > 0:
        s = max(nw / w, nh / h)                       # follow the pointer along the axis that moved more
        nw, nh = max(MIN_IMAGE_PX, w * s), max(MIN_IMAGE_PX, h * s)
    if centre:
        l, t = cx - nw / 2, cy - nh / 2
    else:
        if horiz:
            l = r - nw if "w" in handle else l
        if vert:
            t = b - nh if "n" in handle else t
    return {"x1": l, "y1": t, "x2": l + nw, "y2": t + nh}


def image_rotate(a: Annotation, px: float, py: float, snap: bool = False) -> dict:
    """The angle that points the rotate handle (above the top edge) at (px, py); ``snap`` (Shift): 15° steps."""
    cx, cy = image_centre(a)
    deg = math.degrees(math.atan2(py - cy, px - cx)) + 90.0
    if snap:
        deg = round(deg / ROTATE_SNAP) * ROTATE_SNAP
    return {"angle": normalise_angle(deg)}


def image_resize_turned(a: Annotation, handle: str, px: float, py: float, keep: bool = True, centre: bool = False) -> dict:
    """``image_resize`` in the layer's own upright frame, so a turned picture resizes along its own sides and the
    opposite corner stays put on the page."""
    if not a.angle:
        return image_resize(a, handle, px, py, keep, centre)
    lx, ly = to_local(a, px, py)
    ch = image_resize(a, handle, lx, ly, keep, centre)
    ocx, ocy = image_centre(a)
    ncx, ncy = (ch["x1"] + ch["x2"]) / 2, (ch["y1"] + ch["y2"]) / 2
    wcx, wcy = to_page(a, ncx, ncy)                     # the new centre, turned about the old one
    dx, dy = wcx - ncx, wcy - ncy
    return {"x1": ch["x1"] + dx, "y1": ch["y1"] + dy, "x2": ch["x2"] + dx, "y2": ch["y2"] + dy}


def handle_changes(a: Annotation, handle: str, px: float, py: float, ctrl: bool = False, shift: bool = False) -> dict:
    """Field changes that move ``handle`` of ``a`` to (px, py). Image layers: see ``image_resize``/``image_rotate``."""
    k = a.kind
    if k == "image":
        if handle == "rotate":
            return image_rotate(a, px, py, snap=shift)
        return image_resize_turned(a, handle, px, py, keep=not shift, centre=ctrl)
    if k in ("arrow", "line"):
        return {"x1": px, "y1": py} if handle == "start" else {"x2": px, "y2": py}
    if k == "callout":
        if handle == "target":
            return {"x2": px, "y2": py}
        return {"x1": px, "y1": py}
    x, y, w, h = a.rect
    l, t, r, b = x, y, x + w, y + h
    if "w" in handle:
        l = px
    if "e" in handle:
        r = px
    if "n" in handle:
        t = py
    if "s" in handle:
        b = py
    if ctrl and handle in ("nw", "ne", "sw", "se"):
        side = max(abs(r - l), abs(b - t))
        l, r = (r - side, r) if "w" in handle else (l, l + side)
        t, b = (b - side, b) if "n" in handle else (t, t + side)
    return {"x1": l, "y1": t, "x2": r, "y2": b}


def move_changes(a: Annotation, dx: float, dy: float) -> dict:
    ch = {"x1": a.x1 + dx, "y1": a.y1 + dy, "x2": a.x2 + dx, "y2": a.y2 + dy}
    if a.points:
        ch["points"] = [(x + dx, y + dy) for x, y in a.points]
    return ch


def selection_rect(a: Annotation) -> tuple[float, float, float, float]:
    """Dashed outline for the selection (image px)."""
    if a.kind == "step":
        r = step_radius(a.style)
        return a.x1 - r, a.y1 - r, 2 * r, 2 * r
    if a.kind == "callout":
        return callout_box(a)
    if a.kind == "image":
        xs = [p[0] for p in image_corners(a)]; ys = [p[1] for p in image_corners(a)]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    x, y, w, h = a.bounding_box()
    return x, y, w, h


def duplicate(a: Annotation, offset: float = 12.0) -> Annotation:
    b = a.copy()
    b.move_by(offset, offset)
    return b
