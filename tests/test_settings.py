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
    assert not t.left_collapsed and not t.right_collapsed


def test_legacy_screenshot_path_is_read(tmp_path):
    from linscreencapture.model.settings import Settings
    legacy = tmp_path / "linshot"
    legacy.mkdir()
    (legacy / "settings.conf").write_text("[Settings]\nscreenshot_path=/home/user/Shots\nfilename_format=1\n")
    t = Settings.load(root=str(tmp_path))
    assert t.screenshot_path == "/home/user/Shots" and t.numbering == "sequence" and t.prefix == "Screenshot_"
