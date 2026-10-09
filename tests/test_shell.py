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
            if b.get_action_name() == "app.capture" and b.get_width() > 30:
                assert b.get_height() == 30  # the full-width Capture button at the top of the left rail
            else:
                assert (b.get_width(), b.get_height()) in ((30, 30), (26, 26)), (b.get_tooltip_text(), b.get_width(), b.get_height())
        assert b.get_tooltip_text(), "button without tooltip"
        assert b.get_action_name() or isinstance(b, Gtk.ToggleButton), b.get_tooltip_text()
    img = next(w for w in _walk(btns[0]) if isinstance(w, Gtk.Image))
    assert img.get_pixel_size() == 18


def test_header_pieces(window):
    assert not hasattr(window.header, "chip") and not hasattr(window.header, "zoom") and not hasattr(window.header, "capture")
    assert not window.header.subtitle.get_visible() and window.header.title.get_label() == "LinScreenCapture"
    props = window.header.props
    assert props.get_mapped() and props.title.get_label() == "ARROW" and props.sets.get_visible_child_name() == "shape"
    window.state.tool = "text"
    pump(50)
    assert props.title.get_label() == "TEXT" and props.sets.get_visible_child_name() == "text"
    window.state.tool = "pixelate"
    pump(50)
    assert props.sets.get_visible_child_name() == "redact" and props.mode.get_first_child().get_active()
    window.state.tool = "arrow"


def test_capture_button_tops_the_left_rail(window):
    cap = window.tool_rail.capture
    assert cap.get_action_name() == "app.capture" and cap.get_width() > 120 and cap.get_height() == 30
    assert cap.get_parent().get_prev_sibling() is None  # first row of the open rail


def test_right_rail_holds_view_and_edit(window):
    pr = window.panel_rail
    assert pr.zoom.get_height() == 30 and pr.zoom.value.get_label() == "100%"
    window.activate_action("win.zoom-in", None)
    pump(50)
    assert pr.zoom.value.get_label() == "150%"
    window.activate_action("win.zoom-fit", None)
    assert [b.get_action_name() for b in pr.edit_buttons] == ["win.copy", "win.flatten"]
    left_actions = [b.get_tooltip_text() for b in _buttons(window.tool_rail.get_child_by_name("open")) if b.get_action_name() in ("win.copy", "win.flatten")]
    assert left_actions == []


def test_rail_carets_are_single_chevrons(window):
    icons = {b.lsc_icon for b in _buttons(window.tool_rail) + _buttons(window.panel_rail) if "rail" in (b.get_action_name() or "")}
    assert icons == {"caret-left", "caret-right"}
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


def test_colour_sync(window):
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



def test_document_shows_on_stage_and_in_layers(window, tmp_path):
    from PIL import Image
    from linscreencapture.model.document import Document
    Image.new("RGBA", (400, 300), (40, 120, 200, 255)).save(tmp_path / "cap.png")
    window.load_document(Document.open(str(tmp_path / "cap.png")))
    pump(150)
    assert window.stage.pages.get_visible_child_name() == "canvas"
    assert window.header.title.get_label() == "cap.png"
    assert window.header.subtitle.get_visible() and "400×300 · PNG · 1 layer · saved" in window.header.subtitle.get_label()
    rows = [r for r in _walk(window.panel_rail.layers) if isinstance(r, Gtk.ListBoxRow)]
    assert len(rows) == 1 and rows[0].name.get_label() == "Base capture"
    assert window.stage.hud.get_label().endswith("%")
    window.activate_action("win.zoom-fit", None)
    assert 0.1 <= window.state.zoom <= 1.0
    window.activate_action("win.discard", None)
    pump(50)
    assert window.stage.pages.get_visible_child_name() == "empty" and window.header.title.get_label() == "LinScreenCapture"
    assert window.panel_rail.layers_empty.get_visible()


def test_capture_actions_exist(app, window):
    for name in ("capture", "capture-region", "capture-window", "capture-screen", "capture-delayed"):
        assert app.lookup_action(name) is None  # the plain test app has no capture actions
    from linscreencapture.app.application import CAPTURE_ACTIONS, ACCELS
    assert set(CAPTURE_ACTIONS) == {"capture", "capture-region", "capture-window", "capture-screen", "capture-delayed"}
    assert ACCELS["app.capture"] == ["<Control>n"]
