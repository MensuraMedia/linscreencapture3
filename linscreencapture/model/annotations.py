"""Annotation model and Cairo drawing, ported from the 1.4 ``editor_tools.c``.

Pure Python: cairo, Pango (via GI, no GTK), numpy and Pillow only, so it runs headless.

Kinds: arrow, line, box, circle, text, pen, marker, step, callout, fill, blur, pixelate.
Coordinates are document pixels. ``draw(annotation, cr, target)`` paints one annotation onto a
cairo context whose target image surface is ``target`` (needed by blur and pixelate, which sample
what is already painted beneath them, exactly as 1.4 did).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict, replace
from typing import Iterable

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

KINDS = ("arrow", "line", "box", "circle", "text", "pen", "marker", "step", "callout", "fill", "blur", "pixelate")
SHAPE_KINDS = ("arrow", "line", "box", "circle")          # share the "Shapes" settings
REDACT_KINDS = ("blur", "pixelate")
STROKE_KINDS = ("line", "pen", "marker")
BADGE = {"arrow": "ANNO", "line": "ANNO", "box": "ANNO", "circle": "ANNO", "text": "TEXT", "pen": "INK",
         "marker": "INK", "step": "STEP", "callout": "NOTE", "fill": "FILL", "blur": "REDACT", "pixelate": "REDACT"}
NAMES = {"arrow": "Arrow", "line": "Line", "box": "Box", "circle": "Circle", "text": "Text", "pen": "Pen",
         "marker": "Marker", "step": "Step", "callout": "Callout", "fill": "Fill", "blur": "Blur", "pixelate": "Pixelate"}


# ---------------------------------------------------------------- colours
def parse_hex(hx: str) -> tuple[float, float, float]:
    hx = hx.strip().lstrip("#")
    if len(hx) == 3:
        hx = "".join(c * 2 for c in hx)
    if len(hx) != 6:
        raise ValueError(f"not a hex colour: {hx!r}")
    return tuple(int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def to_hex(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in (r, g, b))


# ---------------------------------------------------------------- data
@dataclass
class Style:
    colour: str = "#e5484d"
    width: float = 4.0
    shadow: bool = False
    shadow_intensity: float = 0.4
    fill: bool = False
    blur_block: int = 10          # pixelate block size, 2..64
    blur_radius: float = 6.0      # soft blur radius in px
    font_family: str = "Ubuntu"
    font_size: float = 18.0       # points
    bold: bool = True
    italic: bool = False
    opacity: float = 1.0          # marker uses 0.4

    def copy(self) -> "Style":
        return replace(self)


@dataclass
class Annotation:
    kind: str
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    style: Style = field(default_factory=Style)
    text: str = ""
    points: list[tuple[float, float]] = field(default_factory=list)   # pen, marker
    number: int = 0                                                   # step

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown annotation kind {self.kind!r}")

    # -- geometry ---------------------------------------------------------
    @property
    def rect(self) -> tuple[float, float, float, float]:
        """Normalised (x, y, w, h)."""
        return normalised_rect(self.x1, self.y1, self.x2, self.y2)

    def move_by(self, dx: float, dy: float) -> None:
        self.x1 += dx; self.y1 += dy; self.x2 += dx; self.y2 += dy
        if self.points:
            self.points = [(x + dx, y + dy) for x, y in self.points]

    def bounding_box(self) -> tuple[float, float, float, float]:
        """(x, y, w, h) that fully contains the painted pixels, shadow included."""
        lw = self.style.width
        if self.kind in ("pen", "marker") and self.points:
            xs = [p[0] for p in self.points]; ys = [p[1] for p in self.points]
            x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            pad = (lw * 4 if self.kind == "marker" else lw) / 2 + 1
        elif self.kind == "arrow":
            x, y, w, h = self.rect
            pad = lw * 3.0 + 1
        elif self.kind == "step":
            r = step_radius(self.style)
            return self.x1 - r - 2, self.y1 - r - 2, 2 * r + 4, 2 * r + 4
        elif self.kind == "callout":
            x, y, w, h = callout_box(self)
            tx, ty = self.x2, self.y2
            x0, y0 = min(x, tx), min(y, ty)
            return x0 - 2, y0 - 2, max(x + w, tx) - x0 + 4, max(y + h, ty) - y0 + 4
        else:
            x, y, w, h = self.rect
            pad = lw / 2 + 1
        if self.style.shadow:
            pad += (1.0 + lw * 0.2) * 3 + 1.5
        return x - pad, y - pad, w + 2 * pad, h + 2 * pad

    def contains(self, px: float, py: float) -> bool:
        x, y, w, h = self.bounding_box()
        return x <= px <= x + w and y <= py <= y + h

    # -- (de)serialisation ------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["points"] = [list(p) for p in self.points]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        d = dict(d)
        style = Style(**d.pop("style", {}))
        d["points"] = [tuple(p) for p in d.get("points", [])]
        return cls(style=style, **d)


# ---------------------------------------------------------------- geometry helpers
def normalised_rect(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float, float, float]:
    return min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)


def snap45(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    """Snap the end point so the segment lies on a multiple of 45 degrees (Shift-drag)."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return x2, y2
    angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    return x1 + length * math.cos(angle), y1 + length * math.sin(angle)


def constrain_square(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    """Constrain the end point so the box is a square / the ellipse a circle (Ctrl-drag)."""
    side = max(abs(x2 - x1), abs(y2 - y1))
    return x1 + math.copysign(side, x2 - x1 or 1), y1 + math.copysign(side, y2 - y1 or 1)


def step_radius(style: Style) -> float:
    return max(10.0, style.font_size * 0.75)


def callout_box(a: Annotation) -> tuple[float, float, float, float]:
    """The bubble rectangle of a callout: anchored at (x1, y1); text decides its size."""
    w, h = measure_text(a.text or " ", a.style)
    pad = 8.0
    return a.x1, a.y1, w + 2 * pad, h + 2 * pad


# ---------------------------------------------------------------- text
def _font(style: Style) -> Pango.FontDescription:
    desc = Pango.FontDescription()
    desc.set_family(style.font_family or "Sans")
    desc.set_size(int(style.font_size * Pango.SCALE))
    desc.set_weight(Pango.Weight.BOLD if style.bold else Pango.Weight.NORMAL)
    desc.set_style(Pango.Style.ITALIC if style.italic else Pango.Style.NORMAL)
    return desc


def _layout(cr: cairo.Context, text: str, style: Style) -> Pango.Layout:
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(_font(style))
    layout.set_text(text, -1)
    return layout


_measure_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)


def measure_text(text: str, style: Style) -> tuple[float, float]:
    """Logical (width, height) in px of ``text`` in ``style``'s font."""
    cr = cairo.Context(_measure_surface)
    layout = _layout(cr, text, style)
    _ink, logical = layout.get_extents()
    return logical.width / Pango.SCALE, logical.height / Pango.SCALE


# ---------------------------------------------------------------- drawing
def draw(a: Annotation, cr: cairo.Context, target: cairo.ImageSurface | None = None) -> None:
    """Paint ``a`` on ``cr``. ``target`` is the image surface beneath (for blur/pixelate)."""
    if a.kind in REDACT_KINDS:
        if target is not None:
            _draw_redaction(a, cr, target)
        return
    _draw_shadow(a, cr)
    r, g, b = parse_hex(a.style.colour)
    cr.save()
    cr.set_source_rgba(r, g, b, a.style.opacity)
    cr.set_line_width(a.style.width)
    _PAINTERS[a.kind](a, cr)
    cr.restore()


def _arrow_path(a: Annotation, cr: cairo.Context, extra: float = 0.0) -> bool:
    dx, dy = a.x2 - a.x1, a.y2 - a.y1
    length = math.hypot(dx, dy)
    if length < 2.0:
        return False
    angle = math.atan2(dy, dx)
    lw = a.style.width
    shaft_half = lw * 0.5 + extra * 0.5
    head_length, head_half = lw * 5.0, lw * 3.0
    if head_length > length * 0.6:
        head_length = length * 0.6
        head_half = head_length * 0.6
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    tip_x, tip_y = a.x2, a.y2
    neck_x, neck_y = tip_x - head_length * cos_a, tip_y - head_length * sin_a
    tail_x, tail_y = a.x1, a.y1
    sx, sy = sin_a * shaft_half, cos_a * shaft_half
    hx, hy = sin_a * head_half, cos_a * head_half
    cr.move_to(neck_x - sx, neck_y + sy)
    cr.line_to(tail_x - sx, tail_y + sy)
    cr.arc(tail_x, tail_y, shaft_half, angle + math.pi / 2, angle - math.pi / 2)
    cr.line_to(neck_x + sx, neck_y - sy)
    cr.line_to(neck_x + hx, neck_y - hy)
    cr.line_to(tip_x, tip_y)
    cr.line_to(neck_x - hx, neck_y + hy)
    cr.close_path()
    return True


def _ellipse_path(a: Annotation, cr: cairo.Context) -> bool:
    x, y, w, h = a.rect
    if w <= 0 or h <= 0:
        return False
    cr.save()
    cr.translate(x + w / 2, y + h / 2)
    cr.scale(w / 2, h / 2)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()
    return True


def _stroke_points(a: Annotation, cr: cairo.Context) -> None:
    if len(a.points) == 1:
        x, y = a.points[0]
        cr.arc(x, y, cr.get_line_width() / 2, 0, 2 * math.pi)
        cr.fill()
        return
    cr.move_to(*a.points[0])
    for p in a.points[1:]:
        cr.line_to(*p)
    cr.stroke()


def _draw_shadow(a: Annotation, cr: cairo.Context) -> None:
    """Three offset passes with decreasing opacity, as in 1.4."""
    if not a.style.shadow or a.style.shadow_intensity <= 0 or a.kind in ("step", "callout", "fill"):
        return
    lw = a.style.width
    for p in (3, 2, 1):
        cr.save()
        off = (1.0 + lw * 0.2) * p
        cr.translate(off, off)
        cr.set_source_rgba(0, 0, 0, a.style.shadow_intensity * 0.25 / p)
        extra = 0.5 * p
        cr.set_line_width(lw + extra)
        k = a.kind
        if k == "arrow":
            if _arrow_path(a, cr, extra):
                cr.fill()
        elif k == "line":
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(a.x1, a.y1); cr.line_to(a.x2, a.y2); cr.stroke()
        elif k == "box":
            cr.rectangle(*a.rect); cr.stroke()
        elif k == "circle":
            if _ellipse_path(a, cr):
                cr.stroke()
        elif k == "text" and a.text:
            cr.move_to(a.x1, a.y1)
            PangoCairo.show_layout(cr, _layout(cr, a.text, a.style))
        elif k in ("pen", "marker") and a.points:
            cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
            if k == "marker":
                cr.set_line_width(lw * 4 + extra)
            _stroke_points(a, cr)
        cr.restore()


def _paint_arrow(a: Annotation, cr: cairo.Context) -> None:
    if _arrow_path(a, cr):
        cr.fill()


def _paint_line(a: Annotation, cr: cairo.Context) -> None:
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(a.x1, a.y1); cr.line_to(a.x2, a.y2); cr.stroke()


def _paint_box(a: Annotation, cr: cairo.Context) -> None:
    cr.rectangle(*a.rect)
    if a.style.fill:
        cr.fill_preserve()
    cr.stroke()


def _paint_circle(a: Annotation, cr: cairo.Context) -> None:
    if _ellipse_path(a, cr):
        if a.style.fill:
            cr.fill_preserve()
        cr.stroke()


def _paint_text(a: Annotation, cr: cairo.Context) -> None:
    if not a.text:
        return
    layout = _layout(cr, a.text, a.style)
    _ink, logical = layout.get_extents()
    a.x2 = a.x1 + logical.width / Pango.SCALE     # keep bounds in step with the glyphs, as 1.4 did
    a.y2 = a.y1 + logical.height / Pango.SCALE
    cr.move_to(a.x1, a.y1)
    PangoCairo.show_layout(cr, layout)


def _paint_pen(a: Annotation, cr: cairo.Context) -> None:
    if not a.points:
        return
    cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
    _stroke_points(a, cr)


def _paint_marker(a: Annotation, cr: cairo.Context) -> None:
    if not a.points:
        return
    r, g, b = parse_hex(a.style.colour)
    cr.set_source_rgba(r, g, b, 0.4 if a.style.opacity >= 1.0 else a.style.opacity)
    cr.set_line_width(a.style.width * 4)
    cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
    _stroke_points(a, cr)


def _paint_step(a: Annotation, cr: cairo.Context) -> None:
    rad = step_radius(a.style)
    cr.save()
    cr.translate(1.5, 1.5); cr.set_source_rgba(0, 0, 0, 0.35)
    cr.arc(a.x1, a.y1, rad, 0, 2 * math.pi); cr.fill()
    cr.restore()
    cr.arc(a.x1, a.y1, rad, 0, 2 * math.pi); cr.fill()
    st = replace(a.style, bold=True, font_size=max(9.0, rad * 0.95))
    layout = _layout(cr, str(a.number or 1), st)
    _ink, logical = layout.get_extents()
    w, h = logical.width / Pango.SCALE, logical.height / Pango.SCALE
    cr.set_source_rgb(1, 1, 1)
    cr.move_to(a.x1 - w / 2, a.y1 - h / 2)
    PangoCairo.show_layout(cr, layout)


def _rounded_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _paint_callout(a: Annotation, cr: cairo.Context) -> None:
    x, y, w, h = callout_box(a)
    tx, ty = a.x2, a.y2                       # the tail points at the target
    cr.save()
    cr.translate(1.5, 2.0); cr.set_source_rgba(0, 0, 0, 0.3)
    _rounded_rect(cr, x, y, w, h, 6); cr.fill()
    cr.restore()
    # tail: a triangle from the nearest bubble edge to the target point
    cx, cy = x + w / 2, y + h / 2
    base = 10.0
    if abs(tx - cx) > abs(ty - cy):
        ex = x + w if tx > cx else x
        cr.move_to(ex, max(y + 4, min(y + h - 4, ty - base))); cr.line_to(tx, ty)
        cr.line_to(ex, max(y + 4, min(y + h - 4, ty + base)))
    else:
        ey = y + h if ty > cy else y
        cr.move_to(max(x + 4, min(x + w - 4, tx - base)), ey); cr.line_to(tx, ty)
        cr.line_to(max(x + 4, min(x + w - 4, tx + base)), ey)
    cr.close_path(); cr.fill()
    _rounded_rect(cr, x, y, w, h, 6); cr.fill()
    cr.set_source_rgb(1, 1, 1)
    cr.move_to(x + 8, y + 8)
    PangoCairo.show_layout(cr, _layout(cr, a.text or " ", a.style))


def _paint_fill(a: Annotation, cr: cairo.Context) -> None:
    cr.rectangle(*a.rect); cr.fill()


_PAINTERS = {"arrow": _paint_arrow, "line": _paint_line, "box": _paint_box, "circle": _paint_circle,
             "text": _paint_text, "pen": _paint_pen, "marker": _paint_marker, "step": _paint_step,
             "callout": _paint_callout, "fill": _paint_fill}


# ---------------------------------------------------------------- redaction (pixel ops on the target)
def _clamped_region(a: Annotation, target: cairo.ImageSurface) -> tuple[int, int, int, int] | None:
    x, y, w, h = a.rect
    bx, by = max(0, int(x)), max(0, int(y))
    bw, bh = min(int(w), target.get_width() - bx), min(int(h), target.get_height() - by)
    if bw < 2 or bh < 2:
        return None
    return bx, by, bw, bh


def _draw_redaction(a: Annotation, cr: cairo.Context, target: cairo.ImageSurface) -> None:
    import numpy as np
    region = _clamped_region(a, target)
    if region is None:
        return
    bx, by, bw, bh = region
    target.flush()
    stride = target.get_stride()
    buf = np.ndarray((target.get_height(), stride // 4, 4), dtype=np.uint8, buffer=target.get_data())
    sub = buf[by:by + bh, bx:bx + bw, :]
    if a.kind == "pixelate":
        block = max(2, int(a.style.blur_block))
        for row in range(0, bh, block):
            for col in range(0, bw, block):
                cell = sub[row:row + block, col:col + block, :]
                cell[:, :, :3] = cell[:, :, :3].reshape(-1, 3).mean(axis=0).astype(np.uint8)
    else:
        from PIL import Image, ImageFilter
        img = Image.frombuffer("RGBA", (bw, bh), sub.tobytes(), "raw", "BGRa", 0, 1)
        img = img.filter(ImageFilter.GaussianBlur(max(0.5, a.style.blur_radius)))
        out = np.frombuffer(img.convert("RGBA").tobytes(), dtype=np.uint8).reshape(bh, bw, 4)
        sub[:, :, 0] = out[:, :, 2]; sub[:, :, 1] = out[:, :, 1]; sub[:, :, 2] = out[:, :, 0]
    target.mark_dirty_rectangle(bx, by, bw, bh)


def renumber_steps(annotations: Iterable[Annotation]) -> None:
    n = 1
    for a in annotations:
        if a.kind == "step":
            a.number = n
            n += 1
