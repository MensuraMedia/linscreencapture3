"""Paint bucket flood fill (headless)."""
import cairo

from linscreencapture.app import bucket
from linscreencapture.model.annotations import Annotation, Style, draw


def _page():
    """60 × 40: white, a black vertical wall at x = 30, a light-grey patch (250, 250, 250) at the top left."""
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 60, 40)
    cr = cairo.Context(s)
    cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(0, 0, 0); cr.rectangle(30, 0, 1, 40); cr.fill()
    cr.set_source_rgb(250 / 255, 250 / 255, 250 / 255); cr.rectangle(0, 0, 5, 5); cr.fill()
    s.flush()
    return s


def _px(s, x, y):
    s.flush()
    i = y * s.get_stride() + x * 4
    b, g, r, a = s.get_data()[i:i + 4]
    return r, g, b, a


def test_contiguous_fill_stops_at_the_wall_and_honours_tolerance():
    out, x0, y0 = bucket.fill(_page(), 10, 20, (1, 0, 0), tolerance=10)
    assert (x0, y0, out.get_width(), out.get_height()) == (0, 0, 30, 40)       # left of the wall only
    assert _px(out, 10, 20) == (255, 0, 0, 255) and _px(out, 2, 2) == (255, 0, 0, 255)   # grey within 10
    out, *_ = bucket.fill(_page(), 10, 20, (1, 0, 0), tolerance=0)
    assert _px(out, 2, 2)[3] == 0                                              # exact match only: the patch stays


def test_non_contiguous_fills_every_match_and_opacity_premultiplies():
    out, x0, _y0 = bucket.fill(_page(), 10, 20, (0, 0, 1), tolerance=0, contiguous=False, opacity=0.5)
    assert out.get_width() == 60 and x0 == 0                                   # both sides of the wall
    assert _px(out, 30, 10)[3] == 0                                            # the wall itself is not filled
    assert _px(out, 45, 10) == (0, 0, 128, 128)


def test_flood_follows_a_winding_corridor():
    import numpy as np
    m = np.zeros((7, 7), dtype=bool)
    m[1, 1:6] = True; m[1:6, 5] = True; m[5, 1:6] = True; m[3:6, 1] = True; m[3, 1:4] = True
    m[0, 0] = True                                                             # not connected
    f = bucket.flood(m, 1, 1)
    assert f.sum() == m.sum() - 1 and not f[0, 0]


def test_outside_the_page_does_nothing_and_a_bucket_layer_paints_its_pixels():
    assert bucket.fill(_page(), 99, 5, (1, 0, 0)) is None
    surf, x0, y0 = bucket.fill(_page(), 40, 20, (0, 1, 0))
    page = _page()
    a = Annotation("bucket", x0, y0, x0 + surf.get_width(), y0 + surf.get_height(), style=Style(), surface=surf)
    draw(a, cairo.Context(page), page)
    assert _px(page, 40, 20)[:3] == (0, 255, 0) and _px(page, 10, 20)[:3] == (255, 255, 255)
    assert a.bounding_box() == (31, 0, 29, 40) and a.copy().surface is surf
