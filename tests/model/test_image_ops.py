import cairo
from PIL import Image

from linscreencapture.app import image_ops
from linscreencapture.model.annotations import Annotation
from linscreencapture.model.document import Document, surface_from_pil, pil_from_surface
from linscreencapture.model.undo import UndoStack, TransformBase, AddLayer
from tests.model.test_document import gradient, digest


def test_crop_scale_rotate_flip_map_coordinates():
    base = surface_from_pil(gradient(64, 48))
    out, m = image_ops.crop(base, 10, 8, 20, 16)
    assert (out.get_width(), out.get_height()) == (20, 16) and m(10, 8) == (0, 0)
    out, m = image_ops.scale(base, 128, 96)
    assert (out.get_width(), out.get_height()) == (128, 96) and m(32, 24) == (64, 48)
    out, m = image_ops.rotate(base, 90)
    assert (out.get_width(), out.get_height()) == (48, 64) and m(0, 0) == (48, 0) and m(64, 48) == (0, 64)
    out, m = image_ops.rotate(base, 270)
    assert (out.get_width(), out.get_height()) == (48, 64) and m(0, 0) == (0, 64)
    out, m = image_ops.rotate(base, 180)
    assert m(0, 0) == (64, 48)
    out, m = image_ops.flip(base, True)
    assert m(10, 5) == (54, 5)
    out, m = image_ops.flip(base, False)
    assert m(10, 5) == (10, 43)
    # rotating four times gives the original pixels back
    s = base
    for _ in range(4):
        s, _m = image_ops.rotate(s, 90)
    assert digest(s) == digest(base)


def test_adjust_changes_pixels_and_keeps_alpha():
    base = surface_from_pil(gradient(16, 16))
    out = image_ops.adjust(base, brightness=50, contrast=10, grayscale=True, invert=True)
    assert digest(out) != digest(base)
    px = pil_from_surface(out).getpixel((3, 3))
    assert px[3] == 255 and px[0] == px[1] == px[2]        # grayscale, opaque
    assert digest(image_ops.adjust(base)) == digest(base)  # no-op leaves pixels alone


def test_transform_base_moves_layers_and_undoes():
    doc = Document(surface_from_pil(gradient(64, 48)))
    stack = UndoStack(doc)
    stack.do(AddLayer(Annotation("box", 10, 10, 30, 20)))
    stack.do(AddLayer(Annotation("pen", points=[(5, 5), (15, 15)])))
    before = digest(doc.flatten())
    new, m = image_ops.crop(doc.base, 8, 8, 40, 30)
    stack.do(TransformBase(new, m, label="Crop"))
    assert doc.width == 40 and doc.layers[0].annotation.rect == (2, 2, 20, 10)
    assert doc.layers[1].annotation.points == [(-3, -3), (7, 7)]
    stack.undo()
    assert doc.width == 64 and doc.layers[0].annotation.rect == (10, 10, 20, 10) and digest(doc.flatten()) == before
    stack.redo()
    assert doc.width == 40


def test_image_annotation_draws_and_serialises():
    doc = Document(surface_from_pil(gradient(64, 48)))
    tile = surface_from_pil(Image.new("RGBA", (8, 8), (255, 255, 255, 255)))
    a = Annotation("image", 10, 10, 26, 26, surface=tile)
    doc.add_layer(a)
    out = doc.flatten()
    assert pil_from_surface(out).getpixel((18, 18))[:3] == (255, 255, 255)
    d = a.to_dict()
    assert "surface" not in d and Annotation.from_dict(d).kind == "image"
