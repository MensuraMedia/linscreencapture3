"""Background agent and capture flow: settings, autostart, clipboard, hotkey capture, Region/Region Plus, registrar."""
import types

import cairo
import pytest


# -- settings ---------------------------------------------------------------
def test_agent_settings_defaults_and_round_trip(tmp_path):
    from linscreencapture.model.settings import Settings
    s = Settings.load(root=str(tmp_path))
    assert (s.keep_running, s.tray_icon, s.hotkey_opens_editor) == (True, True, False)
    s.keep_running, s.tray_icon, s.hotkey_opens_editor = False, False, True
    s.save()
    t = Settings.load(root=str(tmp_path))
    assert (t.keep_running, t.tray_icon, t.hotkey_opens_editor) == (False, False, True)
    assert "[System]" in s.path.read_text() and "hotkey_opens_editor=true" in s.path.read_text()


# -- autostart --------------------------------------------------------------
def test_autostart_entry_uses_the_script_on_path(tmp_path):
    from linscreencapture.services import autostart
    p = autostart.set_enabled(True, str(tmp_path), which=lambda _n: "/home/u/.local/bin/linscreencapture")
    text = p.read_text()
    assert p == tmp_path / "autostart" / "com.mensuramedia.LinScreenCapture.desktop"
    assert "Exec=/home/u/.local/bin/linscreencapture --background" in text and "Path=" not in text
    assert "Icon=com.mensuramedia.LinScreenCapture\n" in text     # the installed app icon (docs/ICONOGRAPHY.md)
    assert autostart.is_enabled(str(tmp_path))
    autostart.set_enabled(False, str(tmp_path))
    assert not p.exists() and not autostart.is_enabled(str(tmp_path))


def test_autostart_falls_back_to_the_checkout(tmp_path):
    from linscreencapture.services import autostart
    text = autostart.set_enabled(True, str(tmp_path), which=lambda _n: None).read_text()
    assert "-m linscreencapture --background" in text and f"Path={autostart.CHECKOUT}" in text


# -- capture flow (docs/CAPTURE.md) ------------------------------------------
class _Win:
    def __init__(self, visible):
        self.visible, self.presented, self.loaded, self.toasts, self.clips = visible, 0, [], [], None

    def get_visible(self):
        return self.visible

    def set_visible(self, v):
        self.visible = v

    def present(self):
        self.presented += 1
        self.visible = True

    def load_document(self, doc):
        self.loaded.append(doc)

    def toast(self, text, timeout=3):
        self.toasts.append(text)

    def lookup_action(self, _name):
        return None


def _controller(tmp_path, win, built=None, opens_editor=False):
    from linscreencapture.app.capture_controller import CaptureController
    from linscreencapture.model.settings import Settings
    settings = Settings(root=str(tmp_path), screenshot_path=str(tmp_path / "shots"), hotkey_opens_editor=opens_editor)
    notes = []
    app = types.SimpleNamespace(settings=settings, props=types.SimpleNamespace(active_window=win),
                                send_notification=lambda i, n: notes.append(n), ensure_window=lambda: built)
    c = CaptureController(app)
    c.notes = notes
    return c


def _start(c, hotkey, visible):
    c._hotkey, c._was_visible, c._mode, c._t0, c.busy = hotkey, visible, "region", 0.0, True


def _surface():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 80, 60)
    cr = cairo.Context(s)
    cr.set_source_rgb(0.2, 0.6, 0.9)
    cr.paint()
    return s


def _clipboard_has_png():
    from gi.repository import Gdk
    clip = Gdk.Display.get_default().get_clipboard()
    return clip.is_local() and clip.get_formats().contain_mime_type("image/png")


def test_clipboard_offers_lossless_png_to_other_applications(gtk):
    from linscreencapture.services import clipboard
    from gi.repository import Gdk
    assert clipboard.copy_surface(_surface())
    formats = Gdk.Display.get_default().get_clipboard().get_formats()
    assert formats.contain_mime_type("image/png") and formats.contain_gtype(Gdk.Texture)
    png = clipboard.image_providers(_surface())[0]
    assert png.ref_formats().contain_mime_type("image/png")


def test_hotkey_capture_with_no_window_copies_saves_and_loads_unseen(gtk, tmp_path):
    hidden = _Win(visible=False)
    c = _controller(tmp_path, None, built=hidden)
    _start(c, hotkey=True, visible=False)
    c._finish(_surface(), (10, 10, 40, 30))
    assert len(list((tmp_path / "shots").iterdir())) == 1 and not c.busy and c.notes == []
    assert _clipboard_has_png()
    assert len(hidden.loaded) == 1 and hidden.presented == 0 and not hidden.visible


def test_hotkey_capture_over_a_visible_studio_loads_and_shows_it(gtk, tmp_path):
    win = _Win(visible=True)
    c = _controller(tmp_path, win)
    _start(c, hotkey=True, visible=True)
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 1 and len(win.loaded) == 1 and "copied to clipboard" in win.toasts[-1]


def test_hotkey_opens_editor_setting_presents_the_studio(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win, opens_editor=True)
    _start(c, hotkey=True, visible=False)
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 1 and len(win.loaded) == 1


def test_in_app_capture_copies_to_the_clipboard_and_opens_the_editor(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win)
    _start(c, hotkey=False, visible=True)
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 1 and len(win.loaded) == 1 and _clipboard_has_png()


def test_hotkey_cancel_and_failure(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win)
    _start(c, hotkey=True, visible=False)
    c._finish(_surface(), None)                   # Esc in the overlay
    assert win.presented == 0 and not (tmp_path / "shots").exists()
    c.busy = True
    c._fail("Capture failed: boom")               # no studio on screen: a desktop notification instead
    assert len(c.notes) == 1 and win.presented == 0 and not c.busy


# -- Region and Region Plus ---------------------------------------------------
def test_region_captures_on_release_and_region_plus_waits(gtk):
    from linscreencapture.ui.capture_overlay import OverlaySession, OverlayWindow
    from linscreencapture.services.selection import Selection
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200)
    done = []
    region = OverlaySession(surf, "region", [], done.append)
    assert region.simple and region.mode_name == "region"
    region.selection = Selection(10, 10, 110, 60)
    OverlayWindow._drag_end(type("W", (), {"session": region, "_drag_mode": "new"})())
    assert done == [(10, 10, 100, 50)]
    plus = OverlaySession(surf, "region-plus", [], done.append)
    assert not plus.simple and plus.mode == "region" and plus.mode_name == "region-plus"
    plus.selection = Selection(10, 10, 110, 60)
    OverlayWindow._drag_end(type("W", (), {"session": plus, "_drag_mode": "new"})())
    assert len(done) == 1                          # handles stay up until Enter
    plus.confirm()
    assert done[-1] == (10, 10, 100, 50)
    plus2 = OverlaySession(surf, "region", [], done.append)
    plus2.set_mode("region-plus")
    assert not plus2.simple and plus2.mode_name == "region-plus"


# -- hotkey registrar ---------------------------------------------------------
class _FakeSettings:
    store = {}

    def __init__(self, schema, path=""):
        self.key = (schema, path)
        self.store.setdefault(self.key, {})

    def get_strv(self, k):
        return list(self.store[self.key].get(k, []))

    def set_strv(self, k, v):
        self.store[self.key][k] = list(v)

    def get_string(self, k):
        return self.store[self.key].get(k, "")

    def set_string(self, k, v):
        self.store[self.key][k] = v

    def reset(self, k):
        self.store[self.key].pop(k, None)


def test_registrar_reuses_our_slot_folds_stale_ones_and_frees_builtin_keys():
    from linscreencapture.services import hotkey_registrar as reg
    _FakeSettings.store = {}
    root = _FakeSettings(reg.ROOT_SCHEMA)
    root.set_strv("custom-list", ["custom0", "custom1", "custom2"])
    other = _FakeSettings(reg.CUSTOM_SCHEMA, reg.CUSTOM_PATH.format("custom0"))
    other.set_string("command", "firefox"); other.set_strv("binding", ["<Super>f"])
    old = _FakeSettings(reg.CUSTOM_SCHEMA, reg.CUSTOM_PATH.format("custom1"))
    old.set_string("command", "/home/u/projects/linshot/build/linshot --capture"); old.set_strv("binding", ["Print"])
    dup = _FakeSettings(reg.CUSTOM_SCHEMA, reg.CUSTOM_PATH.format("custom2"))
    dup.set_string("command", "linscreencapture --capture")
    media = _FakeSettings(reg.MEDIA_SCHEMA)
    media.set_strv("area-screenshot-clip", ["<Primary>Print"])
    reloads = []
    slot = reg.register("<Control>Print", "/x/linscreencapture --capture", settings_new=_FakeSettings,
                        custom_new=_FakeSettings, reload=lambda r, c: reloads.append(c))
    assert slot == "custom1"
    assert old.get_strv("binding") == ["<Primary>Print"] and old.get_string("command") == "/x/linscreencapture --capture"
    assert root.get_strv("custom-list") == ["custom0", "custom1"] and dup.get_string("command") == ""
    assert other.get_string("command") == "firefox"            # never touch another application's slot
    assert media.get_strv("area-screenshot-clip") == [] and reloads == [["custom0", "custom1"]]
    reg.unregister(settings_new=_FakeSettings, custom_new=_FakeSettings, reload=lambda r, c: None)
    assert root.get_strv("custom-list") == ["custom0"] and old.get_string("command") == ""


def test_registrar_takes_a_free_slot_when_none_is_ours():
    from linscreencapture.services import hotkey_registrar as reg
    _FakeSettings.store = {}
    _FakeSettings(reg.ROOT_SCHEMA).set_strv("custom-list", ["custom0"])
    _FakeSettings(reg.CUSTOM_SCHEMA, reg.CUSTOM_PATH.format("custom0")).set_string("command", "xterm")
    slot = reg.register("Print", "lsc --capture", settings_new=_FakeSettings, custom_new=_FakeSettings, reload=lambda r, c: None)
    assert slot == "custom1" and _FakeSettings(reg.ROOT_SCHEMA).get_strv("custom-list") == ["custom0", "custom1"]


# -- tray / application contract ---------------------------------------------
def test_tray_menu_actions_exist_on_the_agent(gtk, tmp_path, monkeypatch):
    monkeypatch.setenv("LSC_NO_TRAY", "1")
    from linscreencapture import APP_ID, tray
    from linscreencapture.app.application import Application
    from linscreencapture.model.settings import Settings
    assert tray.APP_ID == APP_ID
    app = Application(non_unique=True)
    app.settings = Settings(root=str(tmp_path))
    assert app.register(None)
    try:
        for entry in tray.MENU:
            if entry is not None:
                assert app.has_action(entry[1]), entry
        assert app._agent and app._tray is None      # keep_running holds the app; LSC_NO_TRAY skips the icon
    finally:
        app.release()


# -- any hotkey, run at startup ------------------------------------------------
def test_defaults_are_printscreen_registered_and_run_at_startup(tmp_path):
    from linscreencapture.model.settings import Settings
    s = Settings(root=str(tmp_path))
    assert (s.hotkey, s.register_hotkey, s.autostart) == ("Print", True, True)


def test_any_recorded_hotkey_round_trips_and_garbage_is_ignored(tmp_path):
    from linscreencapture.model.settings import Settings, valid_hotkey
    assert valid_hotkey("Print") and valid_hotkey("<Super><Shift>F12") and valid_hotkey("none")
    assert not valid_hotkey("") and not valid_hotkey("Ctrl+S") and not valid_hotkey("<Control>")
    s = Settings(root=str(tmp_path)); s.hotkey = "<Alt><Super>F9"; s.save()
    assert Settings.load(root=str(tmp_path)).hotkey == "<Alt><Super>F9"
    s.path.write_text(s.path.read_text().replace("hotkey=<Alt><Super>F9", "hotkey=Ctrl+S"))
    assert Settings.load(root=str(tmp_path)).hotkey == "Print"


def test_key_presses_become_accelerators(gtk):
    from gi.repository import Gdk
    from linscreencapture.ui.preferences import accel_for_key, hotkey_label
    C, S, A = Gdk.ModifierType.CONTROL_MASK, Gdk.ModifierType.SHIFT_MASK, Gdk.ModifierType.ALT_MASK
    assert accel_for_key(Gdk.KEY_Print, 0)[0] == "Print"
    assert accel_for_key(Gdk.KEY_Sys_Req, A)[0] == "<Alt>Print"
    assert accel_for_key(Gdk.KEY_S, C | S)[0] == "<Shift><Control>s"
    assert accel_for_key(Gdk.KEY_F12, 0)[0] == "F12"
    assert accel_for_key(Gdk.KEY_s, 0)[0] is None              # a bare letter would stop typing everywhere
    assert accel_for_key(Gdk.KEY_Control_L, C) == (None, "")   # modifiers alone wait for the real key
    assert hotkey_label("<Control>Print") == "Ctrl+Print" and hotkey_label("none") == "Off"


def test_preferences_record_a_custom_hotkey_and_turn_it_off(window):
    from conftest import pump
    from linscreencapture.ui.preferences import PreferencesDialog
    changes, suspended = [], []
    dlg = PreferencesDialog(window.settings, on_change=lambda f, v: changes.append((f, v)), suspend_hotkey=suspended.append)
    dlg.present(window)
    pump(100)
    rec = dlg.record_hotkey()
    assert suspended == [True]
    rec.finish("<Super>F9")
    pump(50)
    assert window.settings.hotkey == "<Super>F9" and ("hotkey", "<Super>F9") in changes
    assert "hotkey=<Super>F9" in window.settings.path.read_text()
    assert dlg.hotkey_row.get_selected() == 6 and "Super" in dlg.hotkey_row.get_model().get_string(6)
    dlg.record_hotkey().close()                                # cancelled: the old binding comes back
    pump(50)
    assert suspended[-1] is False and window.settings.hotkey == "<Super>F9"
    dlg.hotkey_row.set_selected(1)                             # back to the PrintScreen preset
    pump(50)
    assert window.settings.hotkey == "Print" and dlg.hotkey_row.get_selected() == 1
    dlg.record_hotkey().finish("none")
    pump(50)
    assert window.settings.hotkey == "none" and dlg.hotkey_row.get_selected() == 0
    dlg.close()
    pump(50)


def test_autostart_sync_first_run_then_follows_the_entry(tmp_path):
    from linscreencapture.services import autostart
    root, which = str(tmp_path), (lambda _n: "/u/.local/bin/linscreencapture")
    assert autostart.sync(True, True, root, which) and autostart.is_enabled(root)
    p = autostart.entry_path(root)
    p.write_text(p.read_text().replace("--background", "--old"))
    assert autostart.sync(True, False, root, which) and "--background" in p.read_text()   # launcher refreshed
    p.write_text(p.read_text().replace("X-GNOME-Autostart-enabled=true", "X-GNOME-Autostart-enabled=false"))
    assert not autostart.is_enabled(root) and not autostart.sync(True, False, root, which)  # desktop's choice wins
    assert not autostart.sync(False, True, str(tmp_path / "b"), which)


def test_tray_icon_is_orange_and_double_click_opens_the_editor():
    from linscreencapture import tray
    assert tray.ICON_FILE.name == f"{tray.APP_ID}.svg" and tray.TRAY_COLOUR in tray.ICON_FILE.read_text()
    assert tray.TRAY_COLOUR == "#ffa222" and tray.icon_source() == str(tray.ICON_FILE)
    assert tray.PRGNAME == "linscreencapture-tray"              # not "tray.py": Mint's helpers own that bus name
    dc = tray.DoubleClick(400)
    assert not dc.click(1, 1000) and dc.click(1, 1300)          # two left clicks within the interval
    assert not dc.click(1, 2000) and not dc.click(1, 2600)      # too slow: two single clicks
    assert not dc.click(3, 2700) and not dc.click(1, 2800)      # another button resets the pair
