import pathlib


def test_round_trip(tmp_path):
    from linscreencapture.model.settings import Settings
    s = Settings(root=str(tmp_path), window_width=1500, window_height=900, window_maximized=True,
                 left_collapsed=True, right_collapsed=False, screenshot_path="/tmp/shots")
    s.save()
    assert (tmp_path / "linscreencapture" / "settings.conf").is_file()
    t = Settings.load(root=str(tmp_path))
    assert (t.window_width, t.window_height, t.window_maximized) == (1500, 900, True)
    assert (t.left_collapsed, t.right_collapsed) == (True, False)
    assert t.screenshot_path == "/tmp/shots"


def test_defaults_when_missing(tmp_path):
    from linscreencapture.model.settings import Settings
    t = Settings.load(root=str(tmp_path))
    assert (t.window_width, t.window_height) == (1360, 840)
    assert t.left_collapsed and t.right_collapsed  # collapsed rails are the default


def test_legacy_screenshot_path_is_read(tmp_path):
    from linscreencapture.model.settings import Settings
    legacy = tmp_path / "linshot"
    legacy.mkdir()
    (legacy / "settings.conf").write_text("[Settings]\nscreenshot_path=/home/user/Shots\nfilename_format=1\n")
    t = Settings.load(root=str(tmp_path))
    assert t.screenshot_path == "/home/user/Shots" and t.numbering == "sequence" and t.prefix == "Screenshot_"


def test_the_default_save_folder_is_pictures_screenshots(tmp_path):
    import os
    from gi.repository import GLib
    from linscreencapture.model.settings import Settings, SCREENSHOTS_DIR
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Pictures")
    assert Settings(root=str(tmp_path)).screenshot_path == os.path.join(pictures, SCREENSHOTS_DIR) == os.path.join(pictures, "ScreenShots")


def test_the_old_pictures_default_moves_once_and_other_folders_stay(tmp_path):
    import os
    from gi.repository import GLib
    from linscreencapture.model.settings import Settings, config_dir
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Pictures")
    cfg = config_dir(str(tmp_path)); cfg.mkdir(parents=True)
    (cfg / "settings.conf").write_text(f"[Capture]\nscreenshot_path={pictures}/\n")      # an older file on the old default
    s = Settings.load(str(tmp_path))
    assert s.screenshot_path == os.path.join(pictures, "ScreenShots")
    s.screenshot_path = pictures; s.save()                                              # later chosen on purpose
    assert Settings.load(str(tmp_path)).screenshot_path == pictures
    (cfg / "settings.conf").write_text("[Capture]\nscreenshot_path=/srv/shots\n")
    assert Settings.load(str(tmp_path)).screenshot_path == "/srv/shots"
