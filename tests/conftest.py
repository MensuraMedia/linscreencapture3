import os, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402


def pump(ms: int = 150) -> None:
    """Run the default main loop for ``ms`` milliseconds so layout and frame clocks advance."""
    loop = GLib.MainLoop()
    GLib.timeout_add(ms, loop.quit)
    loop.run()


@pytest.fixture(scope="session")
def gtk():
    if not Gtk.init_check():
        pytest.skip("no display (run under xvfb-run)")
    from linscreencapture.services import icon_loader
    icon_loader.install()
    icon_loader.install_css()
    Adw.init()
    return Gtk


@pytest.fixture(scope="session")
def app(gtk):
    return Gtk.Application(application_id="com.mensuramedia.LinScreenCapture.Tests")


@pytest.fixture
def settings(tmp_path):
    from linscreencapture.model.settings import Settings
    return Settings(root=str(tmp_path), screenshot_path=str(tmp_path / "pics"))


@pytest.fixture
def window(app, settings):
    from linscreencapture.ui.studio_window import StudioWindow
    app.register(None)
    win = StudioWindow(app, settings)
    win.set_default_size(1360, 840)
    win.present()
    pump(400)
    yield win
    win.destroy()
    pump(50)
