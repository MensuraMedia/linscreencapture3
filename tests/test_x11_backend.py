import os
import pytest

from linscreencapture.backends.x11 import X11Backend

x11 = pytest.mark.skipif(os.environ.get("XDG_SESSION_TYPE", "x11") != "x11" or not os.environ.get("DISPLAY"),
                         reason="needs an X11 session")


@x11
def test_capture_screen_matches_root_geometry():
    b = X11Backend()
    assert b.available()
    s = b.capture_screen()
    from Xlib import display
    geo = display.Display().screen().root.get_geometry()
    assert (s.get_width(), s.get_height()) == (geo.width, geo.height)
    s.flush()
    assert s.get_data()[3] == 255  # alpha forced opaque


@x11
def test_list_windows_is_sane():
    wins = X11Backend().list_windows()
    assert isinstance(wins, list)
    for w in wins:
        assert w.width > 1 and w.height > 1
