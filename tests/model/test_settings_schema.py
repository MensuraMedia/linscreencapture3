import pathlib

from linscreencapture.model.settings import Settings, parse_colour, TOOLS, HOTKEYS

LEGACY = """[Settings]
screenshot_path=/home/user/Shots
filename_format=1
auto_number=1
start_with_os=true
shortcut_key=4
default_screenshot_app=true
color_arrow=rgb(0,255,0)
color_box=#0091ff
color_circle=rgba(255,178,36,1)
color_text=rgb(230,72,77)
color_line=#fff
color_border=rgb(1,2,3)
width_arrow=5.5
width_box=2
width_circle=3
width_line=1.5
width_border=2.5
shadow_arrow=true
shadow_int_arrow=0.75
shadow_text=true
blur_block_size=16
text_font_family=DejaVu Sans
text_font_size=22
text_font_bold=false
text_font_italic=true
"""


def test_legacy_file_migrates_every_field(tmp_path):
    (tmp_path / "linshot").mkdir()
    (tmp_path / "linshot" / "settings.conf").write_text(LEGACY)
    s = Settings.load(root=str(tmp_path))
    assert s.migrated_from and s.screenshot_path == "/home/user/Shots"
    assert (s.prefix, s.numbering) == ("Screenshot_", "sequence")
    assert s.autostart and s.register_hotkey and s.hotkey == HOTKEYS[4] == "<Control><Shift>s"
    assert s.tools["arrow"].colour == "#00ff00" and s.tools["arrow"].width == 5.5
    assert s.tools["arrow"].shadow and s.tools["arrow"].shadow_intensity == 0.75
    assert s.tools["box"].colour == "#0091ff" and s.tools["circle"].colour == "#ffb224"
    assert s.tools["text"].colour == "#e6484d" and s.tools["text"].shadow
    assert s.tools["line"].colour == "#ffffff" and s.tools["line"].width == 1.5
    assert s.tools["pen"].colour == "#e5484d"  # tools 1.4 did not have keep the 2.0 default
    assert (s.blur_block, s.text_font_family, s.text_font_size, s.text_bold, s.text_italic) == (16, "DejaVu Sans", 22.0, False, True)
    # the legacy file is untouched and the new one does not exist until save()
    assert (tmp_path / "linshot" / "settings.conf").read_text() == LEGACY
    assert not s.path.exists()
    s.save()
    t = Settings.load(root=str(tmp_path))
    assert t.as_dict() == {**s.as_dict()}
    assert "migrated_from" in s.path.read_text()


def test_legacy_prefix_timestamp_mapping(tmp_path):
    for fmt, prefix, numbering in ((0, "LinScreenCapture_", "sequence"), (2, "LinScreenCapture_", "timestamp"), (3, "Screenshot_", "timestamp")):
        root = tmp_path / str(fmt)
        (root / "linshot").mkdir(parents=True)
        (root / "linshot" / "settings.conf").write_text(f"[Settings]\nfilename_format={fmt}\n")
        s = Settings.load(root=str(root))
        assert (s.prefix, s.numbering) == (prefix, numbering)


def test_full_round_trip_and_validation(tmp_path):
    s = Settings(root=str(tmp_path))
    s.format = "jpeg"; s.jpeg_quality = 80; s.backend = "x11"; s.delay_seconds = 5
    s.tools["pen"].colour = "#6e56cf"; s.tools["pen"].width = 7
    s.universal = True; s.blur_radius = 12.5
    s.save()
    text = s.path.read_text()
    assert "[Tools]" in text and "colour_pen=#6e56cf" in text
    t = Settings.load(root=str(tmp_path))
    assert t.as_dict() == s.as_dict()
    # invalid choices fall back to defaults
    s.path.write_text(text.replace("backend=x11", "backend=magic").replace("format=jpeg", "format=bmp"))
    u = Settings.load(root=str(tmp_path))
    assert (u.backend, u.format) == ("auto", "png")


def test_tool_style_and_universal():
    s = Settings(root="/nonexistent")
    s.tools["box"].colour = "#46a758"; s.tools["box"].width = 9
    st = s.tool_style("box")
    assert (st.colour, st.width, st.fill, st.font_family) == ("#46a758", 9, False, "Ubuntu")
    assert s.tool_style("fill").fill is True
    s.universal = True
    assert s.tool_style("box").colour == s.tools["arrow"].colour
    s.set_colour_for("box", "#000000")
    assert all(s.tools[t].colour == "#000000" for t in TOOLS)


def test_next_filename():
    s = Settings(root="/nonexistent")
    assert s.next_filename(existing=set()) == "LinScreenCapture_1.png"
    assert s.next_filename(existing={"LinScreenCapture_1.png", "LinScreenCapture_2.png"}) == "LinScreenCapture_3.png"
    s.format = "jpeg"; s.prefix = "Screenshot_"
    assert s.next_filename(existing=set()) == "Screenshot_1.jpg"
    s.numbering = "timestamp"
    import datetime
    assert s.next_filename(when=datetime.datetime(2026, 10, 9, 21, 14, 5)) == "Screenshot_2026-10-09_21-14-05.jpg"


def test_parse_colour():
    assert parse_colour("rgb(255, 0, 128)") == "#ff0080"
    assert parse_colour("#ABC") == "#aabbcc"
    assert parse_colour("rgba(0,0,0,0.5)") == "#000000"
    assert parse_colour("blue") is None
