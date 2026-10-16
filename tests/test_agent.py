"""Background agent: settings, autostart entry, quiet hotkey capture, tray/application action contract."""
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


# -- quiet capture ----------------------------------------------------------
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


def _controller(tmp_path, win):
    from linscreencapture.app.capture_controller import CaptureController
    from linscreencapture.model.settings import Settings
    settings = Settings(root=str(tmp_path), screenshot_path=str(tmp_path / "shots"), copy_to_clipboard=False)
    notes = []
    app = types.SimpleNamespace(settings=settings, props=types.SimpleNamespace(active_window=win),
                                send_notification=lambda i, n: notes.append(n))
    c = CaptureController(app)
    c.notes = notes
    return c


def _surface():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 80, 60)
    cr = cairo.Context(s)
    cr.set_source_rgb(0.2, 0.6, 0.9)
    cr.paint()
    return s


def test_quiet_capture_without_a_window_saves_and_copies(gtk, tmp_path):
    c = _controller(tmp_path, None)
    c._quiet, c._was_visible, c._mode, c._t0, c.busy = True, False, "region", 0.0, True
    c._finish(_surface(), (10, 10, 40, 30))
    files = list((tmp_path / "shots").iterdir())
    assert len(files) == 1 and not c.busy and c.notes == []
    from gi.repository import Gdk
    clip = Gdk.Display.get_default().get_clipboard()
    assert clip.is_local() and clip.get_formats().contain_gtype(Gdk.MemoryTexture)


def test_quiet_capture_leaves_a_hidden_studio_hidden(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win)
    c._quiet, c._was_visible, c._mode, c._t0, c.busy = True, False, "region", 0.0, True
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 0 and win.loaded == [] and not win.visible


def test_quiet_capture_restores_a_visible_studio_without_replacing_its_document(gtk, tmp_path):
    win = _Win(visible=True)
    c = _controller(tmp_path, win)
    c._quiet, c._was_visible, c._mode, c._t0, c.busy = True, True, "region", 0.0, True
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 1 and win.loaded == [] and "copied to clipboard" in win.toasts[-1]


def test_quiet_cancel_and_failure(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win)
    c._quiet, c._was_visible, c._mode, c._t0, c.busy = True, False, "region", 0.0, True
    c._finish(_surface(), None)                   # Esc in the overlay
    assert win.presented == 0 and not (tmp_path / "shots").exists()
    c.busy = True
    c._fail("Capture failed: boom")               # no studio on screen: a desktop notification instead
    assert len(c.notes) == 1 and win.presented == 0 and not c.busy


def test_editor_capture_still_opens_the_editor(gtk, tmp_path):
    win = _Win(visible=False)
    c = _controller(tmp_path, win)
    c._quiet, c._was_visible, c._mode, c._t0, c.busy = False, False, "region", 0.0, True
    c._finish(_surface(), (0, 0, 20, 20))
    assert win.presented == 1 and len(win.loaded) == 1


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
