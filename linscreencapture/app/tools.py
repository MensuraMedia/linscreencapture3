"""Pure tool geometry: drag → annotation, handles for the selected annotation, handle drags → edits."""
from __future__ import annotations
import math
from dataclasses import replace

from ..model.annotations import Annotation, Style, snap45, constrain_square, callout_box, step_radius

DRAG_TOOLS = ("arrow", "line", "box", "circle", "fill", "blur", "pixelate", "callout", "crop")
STROKE_TOOLS = ("pen", "marker")
CLICK_TOOLS = ("text", "step")
MIN_DRAG = 3.0


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
def handles_for(a: Annotation) -> dict[str, tuple[float, float]]:
    """Named handle positions (image px) for the selected annotation."""
    k = a.kind
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


def handle_at(a: Annotation, px: float, py: float, tolerance: float) -> str | None:
    for name, (hx, hy) in handles_for(a).items():
        if abs(px - hx) <= tolerance and abs(py - hy) <= tolerance:
            return name
    return None


def handle_changes(a: Annotation, handle: str, px: float, py: float, ctrl: bool = False) -> dict:
    """Field changes that move ``handle`` of ``a`` to (px, py)."""
    k = a.kind
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
    x, y, w, h = a.bounding_box()
    return x, y, w, h


def duplicate(a: Annotation, offset: float = 12.0) -> Annotation:
    b = Annotation.from_dict(a.to_dict())
    b.move_by(offset, offset)
    return b
