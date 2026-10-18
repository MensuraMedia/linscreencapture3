"""Installer script, package layout, app identity (WM_CLASS / icon) and zoom steps."""
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ID = "com.mensuramedia.LinScreenCapture"


def _install(tmp_path, *extra):
    env = dict(os.environ, DISPLAY="", WAYLAND_DISPLAY="")
    return subprocess.run([str(ROOT / "install.sh"), "--prefix", "/opt/lsc", "--destdir", str(tmp_path), "--no-start", *extra],
                          capture_output=True, text=True, env=env, timeout=120)


def test_install_script_lays_out_the_package(tmp_path):
    r = _install(tmp_path)
    assert r.returncode == 0, r.stderr
    root = tmp_path / "opt/lsc"
    launcher = (root / "bin/linscreencapture").read_text()
    assert "installed by install.sh" in launcher and "/opt/lsc/lib/linscreencapture" in launcher
    assert os.access(root / "bin/linscreencapture", os.X_OK)
    lib = root / "lib/linscreencapture"
    assert (lib / "linscreencapture/__main__.py").is_file() and (lib / "linscreencapture/linscreencapture.gresource").is_file()
    assert (lib / f"data/icons/hicolor/scalable/apps/{APP_ID}.svg").is_file()   # the panel icon reads it
    assert not list(lib.rglob("__pycache__"))
    desktop = (root / f"share/applications/{APP_ID}.desktop").read_text()
    assert "Exec=/opt/lsc/bin/linscreencapture\n" in desktop and f"StartupWMClass={APP_ID}" in desktop
    assert f"Icon={APP_ID}" in desktop and "@BIN@" not in desktop and "DBusActivatable" not in desktop
    for s in (16, 48, 256, 512):
        assert (root / f"share/icons/hicolor/{s}x{s}/apps/{APP_ID}.png").is_file()
    assert (root / f"share/icons/hicolor/scalable/apps/{APP_ID}.svg").is_file()


def test_install_script_never_replaces_a_foreign_launcher(tmp_path):
    (tmp_path / "opt/lsc/bin").mkdir(parents=True)
    (tmp_path / "opt/lsc/bin/linscreencapture").write_text("#!/bin/sh\nexec dev-wrapper\n")
    r = _install(tmp_path)
    assert r.returncode == 1 and "--force" in r.stderr
    assert _install(tmp_path, "--force").returncode == 0


def test_install_script_uninstalls(tmp_path):
    assert _install(tmp_path).returncode == 0
    r = _install(tmp_path, "--uninstall")
    assert r.returncode == 0, r.stderr
    root = tmp_path / "opt/lsc"
    assert not (root / "bin/linscreencapture").exists() and not (root / "lib/linscreencapture").exists()
    assert not (root / f"share/applications/{APP_ID}.desktop").exists()


def test_staged_uninstall_leaves_the_users_autostart_entry_alone(tmp_path):
    """--destdir is staging: an uninstall there must not delete $HOME/.config/autostart (it wiped the real one)."""
    home = tmp_path / "home"
    entry = home / f".config/autostart/{APP_ID}.desktop"
    entry.parent.mkdir(parents=True)
    entry.write_text("[Desktop Entry]\nName=keep me\n")
    env = dict(os.environ, DISPLAY="", WAYLAND_DISPLAY="", HOME=str(home))
    for extra in ((), ("--uninstall",)):
        r = subprocess.run([str(ROOT / "install.sh"), "--prefix", "/opt/lsc", "--destdir", str(tmp_path / "stage"),
                            "--no-start", *extra], capture_output=True, text=True, env=env, timeout=120)
        assert r.returncode == 0, r.stderr
    assert entry.read_text() == "[Desktop Entry]\nName=keep me\n"


def test_app_icon_is_bundled_and_named_after_the_app_id():
    xml = (ROOT / "data/linscreencapture.gresource.xml").read_text()
    assert f'alias="icons/scalable/apps/{APP_ID}.svg"' in xml
    svg = (ROOT / f"data/icons/hicolor/scalable/apps/{APP_ID}.svg").read_text()
    assert "#ffa222" in svg
    assert "set_prgname(APP_ID)" in (ROOT / "linscreencapture/__main__.py").read_text()   # WM_CLASS for Alt+Tab


def test_zoom_steps_by_four_percent_and_stops_at_100():
    from linscreencapture.app.view_state import next_zoom
    z, seen = 1.0, []
    for _ in range(5):
        z = next_zoom(z, +1); seen.append(round(z * 100))
    assert seen == [104, 108, 112, 116, 121]
    z, seen = 1.0, []
    for _ in range(4):
        z = next_zoom(z, -1); seen.append(round(z * 100))
    assert seen == [96, 92, 88, 85]
    assert next_zoom(0.98, +1) == 1.0 and next_zoom(1.02, -1) == 1.0     # crossing 100 % stops there
    assert next_zoom(0.12, +1) == 0.13 and next_zoom(0.1, -1) == 0.1 and next_zoom(10.0, +1) == 10.0
    for pct in range(11, 1000, 7):                                         # every step is 1–5 %
        up = next_zoom(pct / 100, +1) * 100
        down = next_zoom(pct / 100, -1) * 100
        assert up - pct >= 1 and pct - down >= 1                           # always moves
        assert (up - pct) / pct <= 0.05 + 1e-9 or up - pct == 1            # at most 5 % (or the 1 % minimum)
        assert (pct - down) / pct <= 0.05 + 1e-9 or pct - down == 1
