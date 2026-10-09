import cairo
from PIL import Image

from linscreencapture.model.settings import Settings
from linscreencapture.services.file_store import save_capture


def test_save_capture_names_sequentially(tmp_path):
    s = Settings(root=str(tmp_path), screenshot_path=str(tmp_path / "shots"))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 12, 8)
    d1 = save_capture(surf, s)
    d2 = save_capture(surf, s)
    assert d1.name == "LinScreenCapture_1.png" and d2.name == "LinScreenCapture_2.png"
    assert not d1.dirty and Image.open(d1.path).size == (12, 8)
    s.format = "jpeg"
    assert save_capture(surf, s).name == "LinScreenCapture_1.jpg"
