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


def test_capture_button_tops_the_left_rail_as_an_icon(window):
    cap = window.tool_rail.capture
    assert cap.get_action_name() == "app.capture" and (cap.get_width(), cap.get_height()) == (30, 30)
    assert "primary" in cap.get_css_classes()
    assert cap.get_parent().get_prev_sibling() is None  # first row of the open rail


def test_defaults_are_collapsed_and_breakpoint_restores_them(tmp_path, app):
    from linscreencapture.model.settings import Settings
    from linscreencapture.ui.studio_window import StudioWindow
    s = Settings(root=str(tmp_path), screenshot_path=str(tmp_path / "pics"))
    assert s.left_collapsed and s.right_collapsed
    app.register(None)
    win = StudioWindow(app, s)
    assert win.state.left_collapsed and win.state.right_collapsed
    win._bp_apply(); win._bp_unapply()
    assert win.state.left_collapsed and win.state.right_collapsed   # restored, not forced open
    win.state.left_collapsed = False
    win._bp_apply(); assert win.state.left_collapsed
    win._bp_unapply(); assert not win.state.left_collapsed and win.state.right_collapsed
    win.destroy()


def test_library_is_always_visible_above_the_actions_line(window):
    for page in ("open", "collapsed"):
        btns = _buttons(window.tool_rail.get_child_by_name(page))
        lib = [b for b in btns if b.get_action_name() == "win.library"]
        assert len(lib) == 1, page
        assert isinstance(lib[0].get_next_sibling(), Gtk.Separator), page   # the hairline right below it


def test_layers_sit_above_the_navigator_and_navigator_tracks_the_view(window, tmp_path):
    from PIL import Image
    from linscreencapture.model.document import Document
    pr = window.panel_rail
    page = pr.get_child_by_name("open").get_child().get_child()  # scrolled window -> viewport -> box
    kids = []
    c = page.get_first_child()
    while c is not None:
        kids.append(c); c = c.get_next_sibling()
    assert kids.index(pr.layers.get_parent().get_parent().get_parent()) < kids.index(pr.navigator)
    assert all(not (isinstance(k, Gtk.Label) and k.get_label() == "NAVIGATOR") for k in kids)
    Image.new("RGBA", (2000, 1200), (90, 60, 30, 255)).save(tmp_path / "big.png")
    window.load_document(Document.open(str(tmp_path / "big.png")))
    pump(200)
    full = pr.navigator.visible_image_rect()
    assert full is not None and full[2] == 2000 and full[3] == 1200       # fit: everything visible
    window.state.zoom = 2.0
    pump(200)
    part = pr.navigator.visible_image_rect()
    assert part[2] < 2000 and part[3] < 1200                                 # zoomed: a sub-rectangle
    pr.navigator._go(pr.navigator.get_width() * 0.9, pr.navigator.get_height() * 0.9)
    pump(100)
    moved = pr.navigator.visible_image_rect()
    assert moved[0] > part[0] and moved[1] > part[1]                         # dragging scrolled the stage


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
    # no accelerator may be a bare letter or an editing chord: those are routed in the bubble phase
    for accels in ACCELS.values():
        for a in accels:
            assert "<Control>" in a or "<Shift>" in a, a
            assert a not in ("<Control>c", "<Control>v", "<Control>z", "<Control>d", "<Control>y"), a



def test_simple_selection_captures_on_release(gtk):
    import cairo
    from linscreencapture.ui.capture_overlay import OverlaySession
    from linscreencapture.services.selection import Selection
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200)
    done = []
    s = OverlaySession(surf, "region", [], done.append, simple=True)
    ow = type("OW", (), {})()  # a stand-in for the window: only _drag_end's inputs are needed
    s.selection = Selection(10, 10, 110, 60)
    from linscreencapture.ui.capture_overlay import OverlayWindow
    OverlayWindow._drag_end(type("W", (), {"session": s, "_drag_mode": "new"})())
    assert done == [(10, 10, 100, 50)]
    s2 = OverlaySession(surf, "region", [], done.append, simple=False)
    s2.selection = Selection(10, 10, 110, 60)
    OverlayWindow._drag_end(type("W", (), {"session": s2, "_drag_mode": "new"})())
    assert len(done) == 1  # handles mode waits for Enter


def test_preferences_dialog_builds_and_saves(window):
    from linscreencapture.ui.preferences import PreferencesDialog
    changes = []
    dlg = PreferencesDialog(window.settings, on_change=lambda f, v: changes.append((f, v)))
    dlg.present(window)
    pump(200)
    dlg._set("selection_style", "simple")
    assert changes == [("selection_style", "simple")] and window.settings.path.is_file()
    assert "selection_style=simple" in window.settings.path.read_text()
    dlg.close()
    pump(50)



class _Gesture:
    """Stand-in for a Gtk gesture: only the modifier state is read."""
    def __init__(self, shift=False, ctrl=False):
        from gi.repository import Gdk
        self.state = (Gdk.ModifierType.SHIFT_MASK if shift else 0) | (Gdk.ModifierType.CONTROL_MASK if ctrl else 0)

    def get_current_event_state(self):
        return self.state


def _drag(window, tool, x1, y1, x2, y2, shift=False, ctrl=False):
    """Drag in image pixels: the stage is at zoom 1 with the image origin known."""
    window.state.tool = tool
    ed = window.editor
    ox, oy = window.stage.image_origin()
    g = _Gesture(shift, ctrl)
    ed._drag_begin(g, ox + x1, oy + y1)
    ed._drag_update(g, x2 - x1, y2 - y1)
    ed._drag_end(g, x2 - x1, y2 - y1)


def _load_blank(window, tmp_path, size=(500, 400)):
    from PIL import Image
    from linscreencapture.model.document import Document
    Image.new("RGBA", size, (30, 40, 50, 255)).save(tmp_path / "blank.png")
    window.load_document(Document.open(str(tmp_path / "blank.png")))
    window.state.zoom = 1.0
    pump(200)


def test_drawing_tools_create_layers_with_undo(window, tmp_path):
    _load_blank(window, tmp_path)
    doc = window.document
    _drag(window, "arrow", 20, 20, 200, 120)
    _drag(window, "box", 40, 40, 140, 100, ctrl=True)
    _drag(window, "pixelate", 60, 60, 160, 160)
    pump(50)
    assert [l.annotation.kind for l in doc.layers] == ["arrow", "box", "pixelate"]
    assert doc.layers[1].annotation.rect == (40, 40, 100, 100)          # Ctrl made it square
    assert doc.layers[0].annotation.style.colour == window.state.colour
    assert window.editor.selected_id == doc.layers[-1].id                 # the new layer is selected
    rows = [r for r in _walk(window.panel_rail.layers) if isinstance(r, Gtk.ListBoxRow)]
    assert [r.name.get_label() for r in rows] == ["3", "2", "1", "Base capture"]           # numbered by stack position
    assert [r.kind.get_label() for r in rows] == ["PIXELATE", "BOX", "ARROW", "IMG"]       # the label names the tool
    assert "4 layers · unsaved" in window.header.subtitle.get_label()
    assert window.lookup_action("undo").get_enabled()
    window.activate_action("win.undo", None); pump(30)
    window.activate_action("win.undo", None); pump(30)
    assert [l.annotation.kind for l in doc.layers] == ["arrow"]
    window.activate_action("win.redo", None); pump(30)
    assert [l.annotation.kind for l in doc.layers] == ["arrow", "box"]


def test_strokes_steps_text_and_callout(window, tmp_path):
    _load_blank(window, tmp_path)
    doc = window.document
    ed = window.editor
    window.state.tool = "pen"
    ox, oy = window.stage.image_origin()
    g = _Gesture()
    ed._drag_begin(g, ox + 10, oy + 10)
    for d in (5, 10, 20, 30):
        ed._drag_update(g, d, d)
    ed._drag_end(g, 30, 30)
    assert doc.layers[-1].annotation.kind == "pen" and len(doc.layers[-1].annotation.points) == 5
    window.state.tool = "step"
    ed._click(g, 1, ox + 50, oy + 50); ed._click(g, 1, ox + 90, oy + 50)
    assert [l.annotation.number for l in doc.layers if l.annotation.kind == "step"] == [1, 2]
    window.state.tool = "text"
    ed._click(g, 1, ox + 100, oy + 100)
    pump(50)
    assert window.stage.text_entry.get_visible()
    window.stage.text_entry.set_text("Login form")
    window.stage.commit_text_entry()
    assert doc.layers[-1].annotation.kind == "text" and doc.layers[-1].annotation.text == "Login form"
    _drag(window, "callout", 120, 120, 200, 200)
    assert window.stage.text_entry.get_visible()
    window.stage.text_entry.set_text("Click here")
    window.stage.commit_text_entry()
    a = doc.layers[-1].annotation
    assert a.kind == "callout" and a.text == "Click here" and (a.x2, a.y2) == (200, 200)
    window.state.tool = "text"
    ed._click(g, 1, ox + 10, oy + 10)
    window.stage.cancel_text_entry()
    assert doc.layers[-1].annotation.kind == "callout"      # cancelled entry adds nothing


def test_select_move_resize_delete_duplicate(window, tmp_path):
    _load_blank(window, tmp_path)
    doc, ed = window.document, window.editor
    _drag(window, "box", 100, 100, 200, 160)
    box = doc.layers[0]
    ed.select(None)
    _drag(window, "select", 150, 130, 170, 150)                   # click inside → select, drag → move
    assert ed.selected_id == box.id and box.annotation.rect == (120, 120, 100, 60)
    _drag(window, "select", 220, 180, 260, 220)                   # the se handle → resize
    assert box.annotation.rect == (120, 120, 140, 100)
    assert window.undo.undo_label == "Resize"
    window.activate_action("win.duplicate-layer", None); pump(30)
    assert len(doc.layers) == 2 and doc.layers[1].annotation.rect == (132, 132, 140, 100)
    window.activate_action("win.delete-layer", None); pump(30)
    assert len(doc.layers) == 1 and ed.selected_id is None
    window.state.colour = "#46a758"
    ed.select(box.id)
    window.state.colour = "#ffb224"
    assert box.annotation.style.colour == "#ffb224"               # palette recolours the selection


def test_strip_writes_settings_and_selected_layer(window, tmp_path):
    _load_blank(window, tmp_path)
    doc, ed, s = window.document, window.editor, window.settings
    window.state.tool = "arrow"
    pump(30)
    props = window.header.props
    props.width_spin.set_value(9)
    props.shadow.set_active(True)
    assert s.tools["arrow"].width == 9 and s.tools["arrow"].shadow is True
    assert "width_arrow=9" in s.path.read_text()
    _drag(window, "arrow", 10, 10, 100, 100)
    a = doc.layers[0].annotation
    assert a.style.width == 9 and a.style.shadow
    window.state.tool = "select"
    ed.select(doc.layers[0].id)
    window.state.tool = "arrow"   # strip shows arrow settings; selection cleared by tool change
    assert ed.selected_id is None
    window.state.tool = "select"; ed.select(doc.layers[0].id)
    props.width_spin.set_value(2)
    assert s.tools["arrow"].width == 2 and a.style.width == 2
    window.state.tool = "pixelate"
    pump(30)
    assert props.mode.get_first_child().get_active()
    props.mode.get_last_child().set_active(True)
    assert window.state.tool == "blur"



def test_shortcuts_never_interfere_with_typing(window, tmp_path):
    from gi.repository import Gdk
    from linscreencapture.app.shortcuts import TOOL_KEYS
    _load_blank(window, tmp_path)
    r, ed = window.shortcuts, window.editor
    window.state.tool = "text"
    ed._click(_Gesture(), 1, *[c + 50 for c in window.stage.image_origin()])
    pump(50)
    assert window.stage.text_entry.get_visible() and window.get_focus() is not None
    for key in TOOL_KEYS:                                   # typing a, b, c … must not switch tools
        assert r.handle(key, 0) is False
    assert r.handle(Gdk.KEY_Delete, 0) is False and r.handle(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK) is False
    assert window.state.tool == "text"
    window.stage.cancel_text_entry()
    window.stage.canvas.grab_focus()
    pump(30)
    assert r.handle(Gdk.KEY_a, 0) is True and window.state.tool == "arrow"
    assert r.handle(Gdk.KEY_A, Gdk.ModifierType.SHIFT_MASK) is False   # Shift+letter is not a tool key
    # a focused spin button in the header strip keeps digits and Enter, but tool letters and
    # editing chords still work and hand the focus back to the canvas
    spin = window.header.props.width_spin
    spin.grab_focus()
    pump(30)
    assert r.handle(Gdk.KEY_5, 0) is False and r.handle(Gdk.KEY_Return, 0) is False
    assert r.handle(Gdk.KEY_b, 0) is True and window.state.tool == "box"
    pump(30)
    assert window.get_focus() is window.stage.canvas
    spin.grab_focus(); pump(30)
    assert r.handle(Gdk.KEY_Escape, 0) is True and window.get_focus() is window.stage.canvas
    window.state.tool = "arrow"
    window.stage.canvas.grab_focus(); pump(30)
    # editing chords route to window actions only when nothing editable has focus
    _drag(window, "box", 10, 10, 80, 60)
    assert len(window.document.layers) == 1 and ed.selected_id is not None
    assert r.handle(Gdk.KEY_d, Gdk.ModifierType.CONTROL_MASK) is True
    pump(30); assert len(window.document.layers) == 2
    assert r.handle(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK) is True
    pump(30); assert len(window.document.layers) == 1
    assert r.handle(Gdk.KEY_Z, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK) is True
    pump(30); assert len(window.document.layers) == 2
    ed.select(window.document.layers[0].id)
    assert r.handle(Gdk.KEY_Escape, 0) is True and ed.selected_id is None   # Escape clears the selection
    assert r.handle(Gdk.KEY_Escape, 0) is False                            # nothing selected: not consumed
    ed.select(window.document.layers[0].id)
    assert r.handle(Gdk.KEY_Delete, 0) is True
    pump(30); assert len(window.document.layers) == 1
    # mid-drag, tool letters are swallowed rather than switching tools
    ed._mode = "draw"
    assert r.handle(Gdk.KEY_l, 0) is True and window.state.tool == "box"
    ed._mode = None
    # with the Library open, Delete targets the library and Escape closes it
    window.activate_action("win.library", None); pump(50)
    assert r.handle(Gdk.KEY_a, 0) is True and window.state.tool == "box"
    assert r.handle(Gdk.KEY_Escape, 0) is True
    pump(50); assert not window.state.library



def test_crop_flatten_save_and_image_ops(window, tmp_path):
    _load_blank(window, tmp_path, (300, 200))
    doc, ed = window.document, window.editor
    _drag(window, "box", 50, 50, 150, 120)
    _drag(window, "crop", 40, 40, 200, 160)
    assert ed.crop_rect == (40, 40, 160, 120)
    window.activate_action("win.crop-apply", None); pump(100)
    assert (doc.width, doc.height) == (160, 120) and doc.layers[0].annotation.rect == (10, 10, 100, 70)
    assert ed.crop_rect is None and window.undo.undo_label == "Crop"
    window.image_op("rotate", 90); pump(50)
    assert (doc.width, doc.height) == (120, 160)
    window.image_op("scale", 60, 80); pump(50)
    assert (doc.width, doc.height) == (60, 80)
    window.image_op("adjust", {"brightness": 40, "contrast": 0, "grayscale": True, "invert": False}); pump(50)
    assert window.undo.depth == 5 and doc.dirty
    window.flatten_now(); pump(50)
    assert doc.layers == [] and window.undo.undo_label == "Flatten"
    window.activate_action("win.undo", None); pump(50)
    assert len(doc.layers) == 1
    # save in place, then the subtitle reads saved
    window.activate_action("win.save", None); pump(100)
    assert not doc.dirty and "saved" in window.header.subtitle.get_label()
    from PIL import Image
    assert Image.open(doc.path).size == (60, 80)


def test_paste_and_eyedropper(window, tmp_path):
    from gi.repository import Gdk, GLib
    import cairo
    _load_blank(window, tmp_path, (200, 150))
    doc, ed = window.document, window.editor
    # a red 20x20 texture pasted as an image layer, centred and selected
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)
    cr = cairo.Context(s); cr.set_source_rgb(1, 0, 0); cr.paint(); s.flush()
    tex = Gdk.MemoryTexture.new(20, 20, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, GLib.Bytes.new(bytes(s.get_data())), s.get_stride())
    window.paste_texture(tex); pump(50)
    a = doc.layers[-1].annotation
    assert a.kind == "image" and a.rect == (90, 65, 20, 20) and ed.selected_id == doc.layers[-1].id
    assert window.state.tool == "select"
    # eyedropper samples the composite under the click
    window.activate_action("win.eyedropper", None)
    assert ed.eyedropper
    ox, oy = window.stage.image_origin()
    ed._click(_Gesture(), 1, ox + 100, oy + 75)
    assert window.state.colour == "#ff0000" and not ed.eyedropper
    ed._click(_Gesture(), 1, ox + 5, oy + 5)   # a plain click now, no sampling
    assert window.state.colour == "#ff0000"
    # pasting with no document makes a new one
    window.clear_document(); pump(30)
    window.paste_texture(tex); pump(50)
    assert window.document is not None and window.document.width == 20 and window.document.path is None


def test_discard_prompts_only_when_dirty(window, tmp_path):
    _load_blank(window, tmp_path)
    window.activate_action("win.discard", None); pump(100)
    assert window.document is None                  # saved document: cleared without a prompt
    _load_blank(window, tmp_path)
    _drag(window, "box", 10, 10, 60, 60)
    assert window.document.dirty
    window.activate_action("win.discard", None); pump(150)
    assert window.document is not None              # dirty: the prompt is up, nothing cleared yet
    for w in list(window.get_application().get_windows()) + [window]:
        pass
    # close any open Adw dialog by answering it through the API
    from gi.repository import Adw
    dlg = Adw.Dialog.get_visible_dialogs if hasattr(Adw.Dialog, "get_visible_dialogs") else None
    window.clear_document()


def test_undo_works_with_focus_in_a_header_spin(window, tmp_path):
    """Regression: after adjusting Width, Ctrl+Z used to be swallowed by the spin's text field."""
    from gi.repository import Gdk
    from linscreencapture.app.shortcuts import ShortcutRouter
    _load_blank(window, tmp_path)
    _drag(window, "box", 10, 10, 80, 60)
    assert len(window.document.layers) == 1
    window.header.props.width_spin.grab_focus(); pump(30)
    r = ShortcutRouter(window)
    assert r.handle(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK) is True
    pump(30)
    assert len(window.document.layers) == 0 and window.get_focus() is window.stage.canvas


def test_click_on_empty_stage_drops_the_tool(window, tmp_path):
    _load_blank(window, tmp_path)
    _drag(window, "box", 10, 10, 80, 60)
    window.state.tool = "arrow"
    window.editor.select(window.document.layers[0].id)
    pump(30)                                     # lets the post-drag click suppression lapse
    window.editor.clicked_outside()
    assert window.state.tool == "select" and window.editor.selected_id is None
    assert not window.stage.point_in_image(-5, -5)


def test_paste_text_becomes_a_text_layer(window, tmp_path):
    _load_blank(window, tmp_path)
    window.paste_text("Pasted from a web page\r\nsecond line")
    pump(30)
    layer = window.document.layers[-1]
    assert layer.annotation.kind == "text" and layer.annotation.text == "Pasted from a web page\nsecond line"
    assert window.state.tool == "select" and window.editor.selected_id == layer.id
    x, y, w, h = layer.annotation.rect
    assert 0 <= x < window.document.width and 0 <= y < window.document.height


def test_copy_then_paste_duplicates_a_layer(window, tmp_path):
    _load_blank(window, tmp_path)
    _drag(window, "box", 10, 10, 80, 60)
    window.editor.select(window.document.layers[0].id)
    window.activate_action("win.copy", None); pump(50)
    assert window._layer_clip is not None
    window.activate_action("win.paste", None); pump(50)
    assert [l.annotation.kind for l in window.document.layers] == ["box", "box"]
    assert window.document.layers[1].annotation.x1 == window.document.layers[0].annotation.x1 + 12


def test_delayed_capture_is_a_toggle(window):
    act = window.lookup_action("capture-delayed")
    assert act is not None and act.get_state().get_boolean() is False
    window.activate_action("win.capture-delayed", None)
    assert act.get_state().get_boolean() is True
    window.activate_action("win.capture-delayed", None)
    assert act.get_state().get_boolean() is False
    modes = window.lookup_action("capture-mode")
    assert modes.get_state().get_string() == "region"        # the mode is untouched by the delay toggle


def test_opacity_control_writes_per_tool_setting(window, settings):
    props = window.header.props
    window.state.tool = "box"; pump(30)
    props.opacity_scales[0].set_value(0.5)
    assert settings.tools["box"].opacity == 0.5 and settings.tools["arrow"].opacity == 1.0
    assert settings.tool_style("box").opacity == 0.5 and settings.tool_style("marker").opacity == 0.4
    window.state.tool = "marker"; pump(30)
    assert all(abs(sc.get_value() - 0.4) < 1e-6 for sc in props.opacity_scales)


def test_clipboard_image_detection_accepts_texture_subclasses(window, tmp_path):
    """Local copies are offered as GdkMemoryTexture (a subclass), other apps as image/* MIME types."""
    from gi.repository import Gdk
    from linscreencapture.services.clipboard import texture_from_surface
    import cairo
    local = Gdk.ContentProvider.new_for_value(texture_from_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)))
    assert window._holds_image(local.ref_formats()) is True
    assert window._holds_image(Gdk.ContentFormats.new(["image/png"])) is True
    assert window._holds_image(Gdk.ContentFormats.new(["text/plain"])) is False
