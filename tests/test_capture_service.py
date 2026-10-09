import cairo
import pytest

from linscreencapture.backends.base import CaptureError, WindowInfo, crop
from linscreencapture.services.capture_service import CaptureService


class Fake:
    is_async = False

    def __init__(self, name, ok=True, avail=True, windows=()):
        self.name, self.ok, self.avail, self.windows, self.calls = name, ok, avail, list(windows), 0

    def available(self):
        return self.avail

    def capture_screen(self):
        self.calls += 1
        if not self.ok:
            raise CaptureError(f"{self.name} broke")
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 30)
        return s

    def capture_screen_async(self, cb):
        try:
            cb(self.capture_screen(), None)
        except Exception as exc:  # noqa: BLE001
            cb(None, exc)

    def list_windows(self):
        return self.windows


def run(service):
    out = {}
    service.capture_screen(lambda s, e: out.update(s=s, e=e))
    return out


def test_order_prefers_session_then_preference():
    x, p, c = Fake("x11"), Fake("portal"), Fake("cli")
    assert [b.name for b in CaptureService("auto", [p, x, c], False, "x11").order()] == ["x11", "portal", "cli"]
    assert [b.name for b in CaptureService("auto", [p, x, c], False, "wayland").order()] == ["portal", "x11", "cli"]
    assert [b.name for b in CaptureService("cli", [p, x, c], False, "x11").order()] == ["cli", "portal", "x11"]
    x.avail = False
    assert [b.name for b in CaptureService("auto", [p, x, c], False, "x11").order()] == ["portal", "cli"]


def test_falls_through_once_per_backend_and_reports_last_error():
    x, p, c = Fake("x11", ok=False), Fake("portal", ok=False), Fake("cli")
    svc = CaptureService("auto", [p, x, c], use_thread=False, session="x11")
    out = run(svc)
    assert out["e"] is None and out["s"].get_width() == 40 and svc.last_used == "cli"
    assert (x.calls, p.calls, c.calls) == (1, 1, 1)
    c.ok = False
    out = run(svc)
    assert out["s"] is None and "cli broke" in str(out["e"])


def test_no_backend_available():
    svc = CaptureService("auto", [Fake("x11", avail=False)], use_thread=False, session="x11")
    out = run(svc)
    assert out["s"] is None and isinstance(out["e"], CaptureError)


def test_list_windows_and_crop():
    w = WindowInfo(1, "Term", 10, 20, 100, 50)
    svc = CaptureService("auto", [Fake("x11", windows=[w])], use_thread=False, session="x11")
    assert svc.list_windows() == [w] and w.rect == (10, 20, 100, 50)
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 30)
    assert (crop(s, 10, 10, 100, 100).get_width(), crop(s, 10, 10, 100, 100).get_height()) == (30, 20)
    assert crop(s, -5, -5, 10, 10).get_width() == 5
