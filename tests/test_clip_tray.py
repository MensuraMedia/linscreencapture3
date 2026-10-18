"""The 2 × 2 clipboard tray: the checks from docs/CLIPBOARD-TRAY-4UP.md §5."""
import cairo
import pytest

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

# the session ``gtk`` fixture skips only when init_check() fails; on some setups it succeeds without
# opening a display and the suite then errors inside icon_loader. Detect that here and skip the module.
if not Gtk.init_check() or Gdk.Display.get_default() is None:
    pytest.skip("no X display (run under xvfb-run)", allow_module_level=True)

from conftest import pump  # noqa: E402
from linscreencapture.services.clip_history import LIMIT  # noqa: E402
from linscreencapture.ui.clip_tray import SLOTS, TRAY_HEIGHT  # noqa: E402
from linscreencapture.ui.tool_rail import OPEN_WIDTH  # noqa: E402


def _surface(w: int, h: int, shade: int) -> cairo.ImageSurface:
    """A solid surface; ``shade`` varies so consecutive copies stay distinct."""
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(shade / 255, 0, 0)
    cr.paint()
    return s


def _fill(window, count: int = 4) -> None:
    for n in range(count):
        window.clips.push(_surface(40, 30, (n + 1) * 40), f"copy {n + 1}")
    pump(50)


def test_five_copies_keep_the_last_four(window):
    h, tray = window.clips, window.tool_rail.tray
    oldest = h.push(_surface(40, 30, 10), "first")
    for n in range(2, 6):
        h.push(_surface(40, 30, n * 40), f"copy {n}")
    pump(50)
    assert len(h) == 4 and oldest not in h.entries              # the fifth copy pushed the first out
    assert tray.entry_at(0) is h.entries[0] and h.entries[0].label == "copy 5"
    assert tray.slots[0].get_tooltip_text().startswith("copy 5 · 40×30 · ")
    assert tray.pictures[0].get_paintable() is h.entries[0].thumb   # cells show the small texture
    assert all(s.get_sensitive() and "filled" in s.get_css_classes() for s in tray.slots)
    assert [tray.query_child(s)[:2] for s in tray.slots] == [(0, 0), (1, 0), (0, 1), (1, 1)]  # reading order


def test_a_repeat_copy_moves_to_the_newest_cell(window):
    h, tray = window.clips, window.tool_rail.tray
    _fill(window)
    third = h.entries[2]
    h.push(third.surface, "again"); pump(50)                    # the same pixels as entry 3
    assert len(h) == 4                                          # no duplicate was added
    assert tray.entry_at(0) is third and third.label == "again"
    assert tray.pictures[0].get_paintable() is third.thumb


def test_removing_the_current_copy_clears_the_clipboard(window):
    h, tray = window.clips, window.tool_rail.tray
    _fill(window)
    cur = h.entries[0]
    assert h.is_current(cur)
    h.remove(cur); pump(50)
    assert h._current is None and not h.is_current(h.entries[0])
    assert Gdk.Display.get_default().get_clipboard().get_content() is None
    assert [s.get_sensitive() for s in tray.slots] == [True, True, True, False]
    assert "filled" in tray.slots[2].get_css_classes() and "filled" not in tray.slots[3].get_css_classes()
    assert tray.slots[3].get_tooltip_text() == "Copies you make appear here"   # the first empty cell


def test_four_large_copies_neither_stretch_the_tray_nor_the_rail(window):
    for n in range(4):
        window.clips.push(_surface(4000, 3000, (n + 1) * 60), f"big {n + 1}")
    pump(300)
    tray = window.tool_rail.tray
    assert tray.get_height() == TRAY_HEIGHT
    assert window.tool_rail.get_width() == OPEN_WIDTH
    assert all(p.get_paintable() is not None for p in tray.pictures)
    sizes = [(p.get_width(), p.get_height()) for p in tray.pictures]  # each quarter really shows its thumbnail
    assert all(w >= 60 and h >= 30 for w, h in sizes) and len(set(sizes)) == 1, sizes
    for e in window.clips.entries:                              # the cells' texture is a thumb, never the full size
        assert e.thumb.get_width() <= 192 and e.thumb.get_height() <= 108


def test_clicking_cell_2_opens_that_entrys_preview(window):
    h, tray = window.clips, window.tool_rail.tray
    _fill(window)
    tray.slots[2].popup(); pump(150)                            # a MenuButton's programmatic click
    assert tray.previews[2].get_visible() and tray.preview is tray.previews[2]
    assert tray.preview.entry is h.entries[2]
    assert tray.preview.picture.get_paintable() is h.entries[2].preview     # the popover keeps the larger sample


def test_collapsed_rail_button_holds_four_cells(window):
    tray = window.tool_rail.tray_button.tray
    assert len(tray.slots) == SLOTS == LIMIT == 4
    assert tray.get_size_request() == (200, TRAY_HEIGHT)
