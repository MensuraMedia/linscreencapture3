"""Turned image layers, the page size and the page fill (headless)."""
import math

import cairo
import pytest

from linscreencapture.app import image_ops, tools
from linscreencapture.model.annotations import Annotation, draw, image_corners, normalise_angle
from linscreencapture.model.document import Document, resized_page
from linscreencapture.model.undo import SetPageFill, TransformBase, UndoStack


def _surface(w, h, rgba=(0, 0.6, 0, 1)):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgba(*rgba)
    cr.paint()
    s.flush()
    return s


def _image(x=100, y=50, w=80, h=40, angle=0.0):
    return Annotation("image", x, y, x + w, y + h, surface=_surface(w, h), angle=angle)


def _pixel(surf, x, y):
    surf.flush()
    i = y * surf.get_stride() + x * 4
    b, g, r, a = surf.get_data()[i:i + 4]
    return r, g, b, a


def test_normalise_angle():
    assert normalise_angle(190) == -170 and normalise_angle(-180) == 180 and normalise_angle(360) == 0
    assert normalise_angle(45.004) == 45.0


def test_a_quarter_turn_swaps_the_bounding_box_and_keeps_the_centre():
    a = _image(angle=90)
    x, y, w, h = a.bounding_box()
    assert (round(w, 6), round(h, 6)) == (40, 80)
    assert (round(x + w / 2, 6), round(y + h / 2, 6)) == (140, 70)


def test_hit_testing_follows_the_turned_picture():
    a = _image(0, 0, 200, 20, angle=45)            # a thin diagonal bar about (100, 10)
    assert a.contains(100, 10) and a.contains(130, 40)
    assert not a.contains(5, 0)                    # inside the upright box, outside the turned bar


def test_a_turned_image_paints_turned():
    page = _surface(300, 300, (1, 1, 1, 1))
    a = _image(110, 140, 80, 20, angle=90)         # upright frame about (150, 150): now 20 wide, 80 tall
    cr = cairo.Context(page)
    draw(a, cr, page)
    assert _pixel(page, 150, 115)[:3] == (0, 153, 0)   # 35 px above the centre: inside after the turn
    assert _pixel(page, 120, 150)[:3] == (255, 255, 255)  # 30 px left: was inside before the turn


def test_the_angle_survives_copy_and_dict_round_trip():
    a = _image(angle=30)
    assert a.copy().angle == 30 and Annotation.from_dict(a.to_dict(), surface=a.surface).angle == 30


def test_rotating_the_page_turns_an_image_layer_instead_of_stretching_it():
    doc = Document(_surface(400, 200))
    layer = doc.add_layer(_image(100, 50, 80, 40))
    undo = UndoStack(doc)
    new, mapper = image_ops.rotate(doc.base, 90)
    undo.do(TransformBase(new, mapper))
    a = layer.annotation
    assert a.angle == 90
    assert (round(a.rect[2], 6), round(a.rect[3], 6)) == (80, 40)        # its own size is unchanged
    cx, cy = a.rect[0] + a.rect[2] / 2, a.rect[1] + a.rect[3] / 2
    assert (round(cx, 6), round(cy, 6)) == (200 - 70, 140)               # the centre followed the pixels
    undo.undo()
    assert a.angle == 0 and a.rect == (100, 50, 80, 40)


def test_flipping_the_page_still_mirrors_corners():
    doc = Document(_surface(400, 200))
    layer = doc.add_layer(_image(100, 50, 80, 40))
    new, mapper = image_ops.flip(doc.base, True)
    TransformBase(new, mapper).apply(doc)
    assert layer.annotation.rect == (220, 50, 80, 40) and layer.annotation.angle == 0


# ---------------------------------------------------------------- handles
def test_image_handles_include_a_rotate_handle_above_the_top_edge():
    a = _image(100, 50, 80, 40)
    h = tools.handles_for(a, zoom=2.0)
    assert h["rotate"] == (140, 50 - tools.ROTATE_REACH_PX / 2)
    assert tools.handle_at(a, 140, 37, 3, zoom=2.0) == "rotate"


def test_the_rotate_handle_sets_the_angle_and_shift_snaps():
    a = _image(100, 50, 80, 40)                     # centre (140, 70)
    assert tools.handle_changes(a, "rotate", 200, 70) == {"angle": 90}
    assert tools.handle_changes(a, "rotate", 140, 130) == {"angle": 180}
    free = tools.handle_changes(a, "rotate", 200, 40)["angle"]
    assert 60 < free < 65
    assert tools.handle_changes(a, "rotate", 200, 40, shift=True) == {"angle": 60}


def test_resizing_a_turned_image_keeps_the_opposite_corner_on_the_page():
    a = _image(100, 50, 80, 40, angle=30)
    nw_before = image_corners(a)[0]
    se = tools.handles_for(a)["se"]
    ch = tools.handle_changes(a, "se", se[0] + 20, se[1] + 20, shift=True)   # free stretch
    b = a.copy()
    for k, v in ch.items():
        setattr(b, k, v)
    assert all(math.isclose(p, q, abs_tol=1e-6) for p, q in zip(image_corners(b)[0], nw_before))
    assert b.rect[2] > 80 and b.angle == 30


def test_the_selection_rect_of_a_turned_image_is_its_turned_extent():
    a = _image(100, 50, 80, 40, angle=90)
    x, y, w, h = tools.selection_rect(a)
    assert (round(w, 6), round(h, 6)) == (40, 80)


# ---------------------------------------------------------------- page size and fill
def test_resized_page_grows_and_shrinks_about_the_centre():
    base = _surface(100, 60)
    out, dx, dy = resized_page(base, 140, 80)
    assert (out.get_width(), out.get_height(), dx, dy) == (140, 80, 20, 10)
    assert _pixel(out, 5, 5)[3] == 0 and _pixel(out, 70, 40)[3] == 255
    out, dx, dy = resized_page(base, 50, 60)
    assert (out.get_width(), dx, dy) == (50, -25, 0)


def test_page_fill_paints_behind_transparent_parts_and_is_undoable():
    doc = Document(_surface(40, 30, (0, 0, 0, 0)))
    undo = UndoStack(doc)
    assert _pixel(doc.flatten(), 5, 5)[3] == 0
    undo.do(SetPageFill("#ff8000"))
    assert _pixel(doc.flatten(), 5, 5) == (255, 128, 0, 255)
    undo.undo()
    assert doc.background is None and _pixel(doc.flatten(), 5, 5)[3] == 0


def test_page_fill_survives_flatten_into_base(tmp_path):
    doc = Document(_surface(40, 30, (0, 0, 0, 0)))
    doc.background = "#0000ff"
    doc.flatten_into_base()
    assert _pixel(doc.base, 1, 1) == (0, 0, 255, 255)
    from PIL import Image
    doc.save(str(tmp_path / "f.png"))
    assert Image.open(tmp_path / "f.png").getpixel((1, 1)) == (0, 0, 255, 255)


@pytest.mark.parametrize("w,h", [(0, 10), (99999, 10)])
def test_resized_page_is_clamped(w, h):
    out, _dx, _dy = resized_page(_surface(10, 10), w, h)
    assert 1 <= out.get_width() <= 16384
