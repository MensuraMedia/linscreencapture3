from gi.repository import Gtk, GLib

from tests.conftest import pump


def _walk(widget):
    yield widget
    c = widget.get_first_child()
    while c is not None:
        yield from _walk(c)
        c = c.get_next_sibling()


def _buttons(widget):
    return [w for w in _walk(widget) if isinstance(w, Gtk.Button) and "rail-btn" in w.get_css_classes()]


def test_window_geometry(window):
    assert window.get_width() == 1360 and window.get_height() == 840
    assert window.header.get_height() in (52, 53)  # 52 px + 1 px bottom border
    assert window.tool_rail.get_width() == 220
    assert window.panel_rail.get_width() == 220


def test_rail_buttons_are_30px_with_tooltip_and_action(window):
    btns = _buttons(window.tool_rail) + _buttons(window.panel_rail) + _buttons(window.header)
    assert len(btns) > 40
    for b in btns:
        if b.get_mapped():
            if b.get_action_name() == "win.panel" and isinstance(b, Gtk.ToggleButton):
                assert b.get_height() == 30  # the three-way panel switch stretches across the rail by design
            else:
                assert (b.get_width(), b.get_height()) in ((30, 30), (26, 26)), (b.get_tooltip_text(), b.get_width(), b.get_height())
        assert b.get_tooltip_text(), "button without tooltip"
        assert b.get_action_name() or isinstance(b, Gtk.ToggleButton), b.get_tooltip_text()
    img = next(w for w in _walk(btns[0]) if isinstance(w, Gtk.Image))
    assert img.get_pixel_size() == 18


def test_header_pieces(window):
    assert not hasattr(window.header, "chip")  # status chip removed
    assert window.header.zoom.get_height() == 30
    assert window.header.capture.get_height() == 30
    prev = window.header.capture.get_prev_sibling()  # first widget in the start box (an empty WindowControls may precede it)
    assert prev is None or isinstance(prev, Gtk.WindowControls)
    assert not window.header.subtitle.get_visible() and window.header.title.get_label() == "LinScreenCapture"
    assert window.header.get_decoration_layout().endswith("close")
    assert "icon" not in window.header.get_decoration_layout()


def test_tool_action_checks_exactly_one_toggle(window):
    window.activate_action("win.tool", GLib.Variant("s", "box"))
    pump(50)
    assert window.state.tool == "box"
    checked = [b for b in _buttons(window.tool_rail.get_child_by_name("open"))
               if isinstance(b, Gtk.ToggleButton) and b.get_action_name() == "win.tool" and b.get_active()]
    assert len(checked) == 1 and checked[0].get_tooltip_text() == "Box"


def test_rails_collapse_and_expand(window):
    window.activate_action("win.toggle-left-rail", None)
    pump(50)
    assert window.state.left_collapsed and window.state.left_manual
    assert window.tool_rail.get_visible_child_name() == "collapsed"
    pump(400)  # crossfade + size interpolation
    assert window.tool_rail.get_width() == 56
    window.activate_action("win.toggle-right-rail", None)
    pump(50)
    assert window.panel_rail.get_visible_child_name() == "collapsed"


def test_collapsed_rail_always_shows_active_tool(window):
    window.state.tool = "marker"  # not in the collapsed subset
    pump(50)
    items = window.tool_rail.collapsed_tool_items()
    assert any(i.target == "marker" for i in items) and len(items) == 7


def test_breakpoint_respects_manual_choice(window):
    window.state.right_manual = True
    window.state.right_collapsed = False
    window._bp_apply()
    assert window.state.left_collapsed and not window.state.right_collapsed
    window._bp_unapply()
    assert not window.state.left_collapsed and not window.state.right_collapsed


def test_panel_switch_and_colour_sync(window):
    window.activate_action("win.panel", GLib.Variant("s", "props"))
    pump(50)
    assert window.panel_rail.panels.get_visible_child_name() == "props"
    window.state.colour = "#0091ff"
    pump(50)
    pal = window.panel_rail.palette
    checked = [hx for hx, b in pal.swatches._buttons.items() if b.get_active()]
    assert checked == ["#0091ff"] and pal.current == "#0091ff"
    pal.swatches._buttons["#46a758"].set_active(True)
    assert window.state.colour == "#46a758"


def test_library_page_toggles(window):
    window.activate_action("win.library", None)
    pump(100)
    assert window.state.library and window.stage.pages.get_visible_child_name() == "library"
    assert window.header.title.get_label() == "Library"
    lib_btn = next(b for b in _buttons(window.tool_rail) if b.get_tooltip_text() == "Library")
    assert isinstance(lib_btn, Gtk.ToggleButton) and lib_btn.get_active()
    window.activate_action("win.library", None)
    pump(100)
    assert not window.state.library and window.stage.pages.get_visible_child_name() == "empty"
    assert window.header.title.get_label() == "LinScreenCapture"


def test_settings_button_is_last_in_right_rail(window):
    btn = window.panel_rail.settings_btn
    assert btn.get_action_name() == "app.preferences" and btn.get_tooltip_text() == "Settings"
    assert btn.get_next_sibling() is None and btn.get_halign() == Gtk.Align.END


def test_close_saves_settings(window):
    window.state.left_collapsed = True
    window._on_close()
    from linscreencapture.model.settings import Settings
    s = Settings.load(root=window.settings.root)
    assert s.left_collapsed is True and s.window_width == 1360
