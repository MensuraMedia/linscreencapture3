"""Page growth (docs/EDITOR-CANVAS-EXPANSION.md) and shadows on images, steps and callouts
(docs/EDITOR-SHADOWS-AND-PREVIEW.md). No GTK."""
import cairo

from linscreencapture.model import annotations as A
from linscreencapture.model.annotations import Annotation, Style
from linscreencapture.model.document import Document, expansion_for, expanded_base, EXPAND_PADDING, MAX_PAGE
from linscreencapture.model.undo import UndoStack, EditAnnotation, TransformBase


def _surface(w, h, rgba=(1, 1, 1, 1)):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgba(*rgba)
    cr.paint()
    s.flush()
    return s


def _px(surf, x, y):
    surf.flush()
    i = y * surf.get_stride() + x * 4
    b, g, r, a = surf.get_data()[i:i + 4]
    return r, g, b, a


def test_expansion_only_on_the_overflowing_sides_with_padding():
    assert expansion_for(100, 100, (10, 10, 50, 50)) == (0, 0, 0, 0)
    assert expansion_for(100, 100, (80, 10, 50, 50)) == (0, 0, 30 + EXPAND_PADDING, 0)
    assert expansion_for(100, 100, (-30, -5, 50, 50)) == (30 + EXPAND_PADDING, 5 + EXPAND_PADDING, 0, 0)
    assert expansion_for(100, 100, (-10, 90, 200, 20)) == (30, 0, 110, 30)   # right edge 190 + 20 - 100
    left, top, right, bottom = expansion_for(100, 100, (0, 0, 10 ** 6, 10))
    assert 100 + left + right == MAX_PAGE


def test_expanded_base_keeps_the_old_pixels_at_left_top():
    base = _surface(10, 10, (1, 0, 0, 1))
    out = expanded_base(base, 5, 3, 7, 0)
    assert (out.get_width(), out.get_height()) == (22, 13)
    assert _px(out, 5, 3) == (255, 0, 0, 255) and _px(out, 0, 0)[3] == 0 and _px(out, 21, 12)[3] == 0


def test_amend_folds_the_growth_into_the_edit_for_one_undo():
    doc = Document(_surface(100, 100))
    layer = doc.add_layer(Annotation("image", 10, 10, 60, 60, surface=_surface(50, 50, (0, 0, 1, 1))))
    stack = UndoStack(doc)
    stack.do(EditAnnotation(layer, {"x1": 80, "x2": 130}, label="Move"))
    stack.amend(TransformBase(expanded_base(doc.base, 0, 0, 50, 0), lambda x, y: (x, y)))
    assert stack.depth == 1 and stack.undo_label == "Move" and doc.width == 150
    stack.undo()
    assert doc.width == 100 and (layer.annotation.x1, layer.annotation.x2) == (10, 60)
    stack.redo()
    assert doc.width == 150 and layer.annotation.x1 == 80


def test_pasted_image_shadow_is_kept_through_flatten_and_save(tmp_path):
    doc = Document(_surface(300, 200))
    img = Annotation("image", 50, 50, 150, 100, style=Style(shadow=True, shadow_intensity=0.45), surface=_surface(100, 50, (0, 0.5, 0, 1)))
    doc.add_layer(img)
    flat = doc.flatten()
    shadowed, far = _px(flat, 152, 80), _px(flat, 250, 160)
    assert shadowed[0] < 230 and far == (255, 255, 255, 255)              # darker just right of the image edge
    assert A.shadow_extent(img.style, "image") == A.IMAGE_SHADOW_OFFSET + A.IMAGE_SHADOW_SIGMA * 3 + 1
    path = str(tmp_path / "out.png")
    doc.save(path)
    assert _px(Document.open(path).base, 152, 80) == shadowed             # the shadow is in the file
    doc.flatten_into_base()
    assert not doc.layers and _px(doc.base, 152, 80) == shadowed           # and in the flattened base


def test_image_shadow_follows_a_transparent_shape():
    disc = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
    cr = cairo.Context(disc)
    cr.arc(50, 50, 30, 0, 6.3)
    cr.set_source_rgb(0, 0, 1)
    cr.fill()
    disc.flush()
    doc = Document(_surface(200, 200))
    doc.add_layer(Annotation("image", 50, 50, 150, 150, style=Style(shadow=True, shadow_intensity=1.0), surface=disc))
    flat = doc.flatten()
    assert _px(flat, 58, 58) == (255, 255, 255, 255)        # the empty corner of the image rect casts no shadow
    assert _px(flat, 50 + 50 + 32, 100 + 4)[0] < 250         # just outside the disc, down-right: shadow


def test_step_and_callout_draw_a_shadow_when_switched_on():
    for kind, a in (("step", Annotation("step", 60, 60, number=1)),
                    ("callout", Annotation("callout", 40, 40, 120, 120, text="Hi"))):
        out = []
        for on in (False, True):
            doc = Document(_surface(200, 200))
            b = a.copy()
            b.style.shadow, b.style.shadow_intensity = on, 1.0
            doc.add_layer(b)
            out.append(bytes(doc.flatten().get_data()))
        assert out[0] != out[1], kind
        assert kind in A.SHADOW_KINDS


def test_moving_a_layer_reuses_its_blurred_shadow():
    A._SHADOW_CACHE.clear()
    a = Annotation("image", 10, 10, 210, 110, style=Style(shadow=True), surface=_surface(200, 100))
    first = A._shadow_surface(a)
    for dx in range(1, 30):                       # the drag preview is a fresh copy at a new place each time
        b = a.copy()
        b.move_by(dx, dx)
        surf, x0, y0 = A._shadow_surface(b)
        assert surf is first[0] and (x0, y0) == (first[1] + dx, first[2] + dx)
    assert len(A._SHADOW_CACHE) == 1
