import math
import cairo
import pytest

from linscreencapture.model.annotations import (Annotation, Style, KINDS, draw, snap45, constrain_square,
                                                measure_text, renumber_steps, parse_hex, to_hex)


def surface(w=200, h=160):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(0.3, 0.6, 0.9)
    cr.paint()
    return s


def painted_bbox(before: cairo.ImageSurface, after: cairo.ImageSurface):
    """Bounding box of pixels that differ between two same-size surfaces."""
    before.flush(); after.flush()
    w, h, st = before.get_width(), before.get_height(), before.get_stride()
    a, b = bytes(before.get_data()), bytes(after.get_data())
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            i = y * st + x * 4
            if a[i:i + 4] != b[i:i + 4]:
                xs.append(x); ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def sample(kind: str) -> Annotation:
    st = Style(colour="#e5484d", width=4, shadow=(kind in ("arrow", "box")), shadow_intensity=0.6)
    if kind in ("pen", "marker"):
        return Annotation(kind, style=st, points=[(30, 40), (60, 70), (90, 50), (120, 90)])
    if kind == "text":
        return Annotation(kind, 30, 30, style=st, text="Login form")
    if kind == "step":
        return Annotation(kind, 80, 80, style=st, number=3)
    if kind == "callout":
        return Annotation(kind, 30, 30, 150, 120, style=st, text="Click here")
    return Annotation(kind, 30, 40, 150, 120, style=st)


@pytest.mark.parametrize("kind", [k for k in KINDS if k not in ("blur", "pixelate")])  # redaction covered below
def test_every_kind_draws_inside_its_bounding_box(kind):
    base = surface()
    s = surface()
    a = sample(kind)
    draw(a, cairo.Context(s), s)
    box = painted_bbox(base, s)
    assert box is not None, f"{kind} painted nothing"
    bx, by, bw, bh = a.bounding_box()
    px, py, pw, ph = box
    assert bx - 1 <= px and by - 1 <= py, (kind, box, a.bounding_box())
    assert px + pw <= bx + bw + 1 and py + ph <= by + bh + 1, (kind, box, a.bounding_box())


def test_text_bounds_follow_the_glyphs():
    a = sample("text")
    s = surface()
    draw(a, cairo.Context(s), s)
    w, h = measure_text(a.text, a.style)
    assert math.isclose(a.x2 - a.x1, w, abs_tol=0.01) and math.isclose(a.y2 - a.y1, h, abs_tol=0.01)
    assert w > 40 and h > 10


def test_pixelate_changes_only_its_region():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
    cr = cairo.Context(s)
    for y in range(100):  # a gradient so blocks average to something different
        cr.set_source_rgb(y / 100, 0.2, 1 - y / 100)
        cr.rectangle(0, y, 100, 1); cr.fill()
    before = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
    c2 = cairo.Context(before); c2.set_source_surface(s, 0, 0); c2.paint()
    a = Annotation("pixelate", 20, 20, 60, 60, style=Style(blur_block=8))
    draw(a, cairo.Context(s), s)
    box = painted_bbox(before, s)
    assert box == (20, 20, 40, 40)
    a2 = Annotation("blur", 10, 10, 50, 50, style=Style(blur_radius=4))
    draw(a2, cairo.Context(s), s)
    assert painted_bbox(before, s)[:2] == (10, 10)


def test_marker_is_translucent_and_wide():
    s = surface()
    a = sample("marker")
    draw(a, cairo.Context(s), s)
    s.flush()
    x, y = 60, 70
    i = y * s.get_stride() + x * 4
    b, g, r, al = s.get_data()[i:i + 4]
    assert al == 255 and 120 < r < 220, (r, g, b)  # blended red over blue, not solid


def test_shadow_grows_the_bounding_box():
    a = Annotation("box", 10, 10, 50, 50, style=Style(width=2, shadow=False))
    b = Annotation("box", 10, 10, 50, 50, style=Style(width=2, shadow=True))
    assert b.bounding_box()[2] > a.bounding_box()[2]


def test_geometry_helpers():
    assert snap45(0, 0, 10, 1) == pytest.approx((math.hypot(10, 1), 0))
    x, y = snap45(0, 0, 10, 9)
    assert math.isclose(x, y, abs_tol=1e-9)
    assert constrain_square(0, 0, 10, 30) == (30, 30)  # the dominant axis wins
    assert constrain_square(0, 0, -10, 4) == (-10, 10)


def test_steps_renumber_in_order():
    items = [Annotation("step", number=9), Annotation("box"), Annotation("step", number=9)]
    renumber_steps(items)
    assert [a.number for a in items if a.kind == "step"] == [1, 2]


def test_move_and_hit():
    a = sample("pen")
    a.move_by(5, -5)
    assert a.points[0] == (35, 35)
    assert a.contains(60, 60) and not a.contains(5, 5)


def test_round_trip_dict_and_colours():
    a = sample("callout")
    b = Annotation.from_dict(a.to_dict())
    assert b == a
    assert parse_hex("#4c9dff") == pytest.approx((0x4c / 255, 0x9d / 255, 1.0))
    assert to_hex(*parse_hex("#4c9dff")) == "#4c9dff"
    with pytest.raises(ValueError):
        Annotation("nope")
