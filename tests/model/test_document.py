import hashlib
import cairo
from PIL import Image

from linscreencapture.model.annotations import Annotation, Style
from linscreencapture.model.document import Document, surface_from_pil, pil_from_surface, load_image


def digest(surf: cairo.ImageSurface) -> str:
    surf.flush()
    return hashlib.sha256(bytes(surf.get_data())).hexdigest()


def gradient(w=64, h=48) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x * 4 % 256, y * 5 % 256, (x + y) % 256, 255)
    return img


def test_pil_cairo_round_trip_is_exact():
    img = gradient()
    back = pil_from_surface(surface_from_pil(img))
    assert back.tobytes() == img.tobytes()


def test_open_save_png_and_jpeg(tmp_path):
    src = tmp_path / "in.png"
    gradient().save(src)
    doc = Document.open(str(src))
    assert (doc.width, doc.height, doc.format, doc.name) == (64, 48, "PNG", "in.png")
    assert doc.summary() == "Edit · 64×48 · PNG · 1 layer · saved"
    doc.add_layer(Annotation("box", 5, 5, 30, 30, style=Style(colour="#00ff00", width=2)))
    assert doc.dirty and "2 layers · unsaved" in doc.summary()
    out = doc.save(str(tmp_path / "out.png"))
    assert not doc.dirty and doc.path == out
    reopened = load_image(out)
    assert digest(reopened) == digest(doc.flatten())
    jpg = doc.save(str(tmp_path / "out.jpg"))
    assert doc.format == "JPEG" and Image.open(jpg).size == (64, 48)


def test_flatten_skips_hidden_layers_and_leaves_layers_intact(tmp_path):
    base = surface_from_pil(gradient())
    doc = Document(base)
    plain = digest(doc.flatten())
    layer = doc.add_layer(Annotation("fill", 0, 0, 20, 20, style=Style(colour="#ffffff")))
    assert digest(doc.flatten()) != plain
    layer.visible = False
    assert digest(doc.flatten()) == plain
    assert len(doc.layers) == 1
    layer.visible = True
    doc.flatten_into_base()
    assert doc.layers == [] and digest(doc.base) != plain


def test_layer_order_and_step_numbers():
    doc = Document(surface_from_pil(gradient()))
    a = doc.add_layer(Annotation("step", 10, 10))
    b = doc.add_layer(Annotation("step", 20, 20))
    assert (a.annotation.number, b.annotation.number) == (1, 2)
    doc.move_layer(b, 0)
    assert (b.annotation.number, a.annotation.number) == (1, 2)
    assert doc.remove_layer(b) == 0 and a.annotation.number == 1
    assert a.badge == "STEP" and a.name == "Step"
