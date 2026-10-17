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
