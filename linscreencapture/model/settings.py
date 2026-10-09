"""Persisted settings: the full 2.0 schema, migrated from the 1.4 key file on first run.

Stored as a GLib key file at ``~/.config/linscreencapture/settings.conf`` in four groups:
``[Window]`` geometry and rail state, ``[Capture]`` saving and capture options, ``[System]``
hotkey and autostart, ``[Tools]`` per-tool colour, width and shadow plus text and blur options.

The legacy 1.x file ``~/.config/linshot/settings.conf`` (single ``[Settings]`` group) is read once
when the new file does not exist; it is copied, never moved or modified. No GTK here.
"""
from __future__ import annotations
import os
import pathlib
import re
from dataclasses import dataclass, field, asdict

from gi.repository import GLib

from .annotations import Style

NEW_DIR = "linscreencapture"
LEGACY_DIR = "linshot"
FILE = "settings.conf"

TOOLS = ("arrow", "line", "box", "circle", "text", "pen", "marker", "step", "callout", "fill")
PREFIXES = ("LinScreenCapture_", "Screenshot_")
NUMBERING = ("sequence", "timestamp")
FORMATS = ("png", "jpeg", "webp")
BACKENDS = ("auto", "portal", "x11", "cli")
SELECTION_STYLES = ("handles", "simple")   # handles: adjust then Enter · simple: captures on release
HOTKEYS = ("none", "Print", "<Control>Print", "<Shift>Print", "<Control><Shift>s", "<Control><Alt>s")

# 1.4 defaults (main_window.c) so a migrated profile looks exactly as it did
_LEGACY_WIDTHS = {"arrow": 3.5, "box": 2.5, "circle": 2.5, "line": 3.0}
_LEGACY_TOOLS = ("arrow", "box", "circle", "text", "line")   # "border" is dropped in 2.0


def config_dir(root: str | None = None) -> pathlib.Path:
    return pathlib.Path(root or GLib.get_user_config_dir()) / NEW_DIR


def legacy_file(root: str | None = None) -> pathlib.Path:
    return pathlib.Path(root or GLib.get_user_config_dir()) / LEGACY_DIR / FILE


def _default_pictures() -> str:
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Pictures")


def parse_colour(text: str) -> str | None:
    """``#rrggbb``, ``#rgb``, ``rgb(r,g,b)`` or ``rgba(r,g,b,a)`` (GdkRGBA strings) -> ``#rrggbb``."""
    t = text.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{6})", t)
    if m:
        return "#" + m.group(1)
    m = re.fullmatch(r"#([0-9a-f]{3})", t)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1))
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*[\d.]+\s*)?\)", t)
    if m:
        return "#%02x%02x%02x" % tuple(max(0, min(255, round(float(v)))) for v in m.groups())
    return None


@dataclass
class ToolStyle:
    colour: str = "#e5484d"
    width: float = 4.0
    shadow: bool = False
    shadow_intensity: float = 0.4


def _default_tools() -> dict[str, ToolStyle]:
    return {t: ToolStyle() for t in TOOLS}


@dataclass
class Settings:
    # [Window]
    window_width: int = 1360
    window_height: int = 840
    window_maximized: bool = False
    left_collapsed: bool = True   # the collapsed rails are the default on first run
    right_collapsed: bool = True
    # [Capture]
    screenshot_path: str = field(default_factory=_default_pictures)
    prefix: str = "LinScreenCapture_"
    numbering: str = "sequence"
    format: str = "png"
    jpeg_quality: int = 92
    copy_to_clipboard: bool = True
    delay_seconds: int = 3
    include_pointer: bool = False
    pin_opacity: int = 90
    backend: str = "auto"
    reopen_last: bool = True
    selection_style: str = "handles"
    # [System]
    autostart: bool = False
    hotkey: str = "Print"
    register_hotkey: bool = False
    # [Tools]
    tools: dict[str, ToolStyle] = field(default_factory=_default_tools)
    universal: bool = False
    blur_block: int = 10
    blur_radius: float = 6.0
    text_font_family: str = "Ubuntu"
    text_font_size: float = 18.0
    text_bold: bool = True
    text_italic: bool = False
    # bookkeeping
    root: str | None = None          # config root override (tests)
    migrated_from: str | None = None  # set when this instance came from the 1.x file

    # -- derived ----------------------------------------------------------
    @property
    def path(self) -> pathlib.Path:
        return config_dir(self.root) / FILE

    def tool_style(self, tool: str) -> Style:
        """A drawing ``Style`` for ``tool`` honouring the universal switch and text/blur options."""
        src = self.tools["arrow"] if self.universal else self.tools.get(tool, ToolStyle())
        return Style(colour=src.colour, width=src.width, shadow=src.shadow, shadow_intensity=src.shadow_intensity,
                     fill=(tool == "fill"), blur_block=self.blur_block, blur_radius=self.blur_radius,
                     font_family=self.text_font_family, font_size=self.text_font_size,
                     bold=self.text_bold, italic=self.text_italic)

    def set_colour_for(self, tool: str, colour: str) -> None:
        targets = TOOLS if self.universal else (tool,)
        for t in targets:
            self.tools[t].colour = colour

    def next_filename(self, existing: set[str] | None = None, when=None) -> str:
        """``LinScreenCapture_12.png`` or ``Screenshot_2026-10-09_21-14-05.png`` (not yet on disk)."""
        import datetime
        ext = "jpg" if self.format == "jpeg" else self.format
        if self.numbering == "timestamp":
            stamp = (when or datetime.datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
            return f"{self.prefix}{stamp}.{ext}"
        names = existing if existing is not None else (
            set(os.listdir(self.screenshot_path)) if os.path.isdir(self.screenshot_path) else set())
        n = 1
        while f"{self.prefix}{n}.{ext}" in names:
            n += 1
        return f"{self.prefix}{n}.{ext}"

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, root: str | None = None) -> "Settings":
        s = cls(root=root)
        if s.path.is_file():
            kf = GLib.KeyFile()
            try:
                kf.load_from_file(str(s.path), GLib.KeyFileFlags.NONE)
            except GLib.Error:
                return s
            s._read(kf)
            return s
        legacy = legacy_file(root)
        if legacy.is_file():
            kf = GLib.KeyFile()
            try:
                kf.load_from_file(str(legacy), GLib.KeyFileFlags.NONE)
                s._read_legacy(kf)
                s.migrated_from = str(legacy)
            except GLib.Error:
                pass
        return s

    def _read(self, kf: GLib.KeyFile) -> None:
        g = _Getter(kf)
        self.window_width = g.int("Window", "width", self.window_width)
        self.window_height = g.int("Window", "height", self.window_height)
        self.window_maximized = g.bool("Window", "maximized", self.window_maximized)
        self.left_collapsed = g.bool("Window", "left_collapsed", self.left_collapsed)
        self.right_collapsed = g.bool("Window", "right_collapsed", self.right_collapsed)
        self.screenshot_path = g.str("Capture", "screenshot_path", self.screenshot_path)
        self.prefix = g.str("Capture", "prefix", self.prefix)
        self.numbering = g.choice("Capture", "numbering", NUMBERING, self.numbering)
        self.format = g.choice("Capture", "format", FORMATS, self.format)
        self.jpeg_quality = max(1, min(100, g.int("Capture", "jpeg_quality", self.jpeg_quality)))
        self.copy_to_clipboard = g.bool("Capture", "copy_to_clipboard", self.copy_to_clipboard)
        self.delay_seconds = max(0, min(60, g.int("Capture", "delay_seconds", self.delay_seconds)))
        self.include_pointer = g.bool("Capture", "include_pointer", self.include_pointer)
        self.pin_opacity = max(10, min(100, g.int("Capture", "pin_opacity", self.pin_opacity)))
        self.backend = g.choice("Capture", "backend", BACKENDS, self.backend)
        self.reopen_last = g.bool("Capture", "reopen_last", self.reopen_last)
        self.selection_style = g.choice("Capture", "selection_style", SELECTION_STYLES, self.selection_style)
        self.autostart = g.bool("System", "autostart", self.autostart)
        self.hotkey = g.choice("System", "hotkey", HOTKEYS, self.hotkey)
        self.register_hotkey = g.bool("System", "register_hotkey", self.register_hotkey)
        for t in TOOLS:
            ts = self.tools[t]
            ts.colour = parse_colour(g.str("Tools", f"colour_{t}", ts.colour)) or ts.colour
            ts.width = max(0.5, min(40.0, g.float("Tools", f"width_{t}", ts.width)))
            ts.shadow = g.bool("Tools", f"shadow_{t}", ts.shadow)
            ts.shadow_intensity = max(0.0, min(1.0, g.float("Tools", f"shadow_intensity_{t}", ts.shadow_intensity)))
        self.universal = g.bool("Tools", "universal", self.universal)
        self.blur_block = max(2, min(64, g.int("Tools", "blur_block", self.blur_block)))
        self.blur_radius = max(0.5, min(40.0, g.float("Tools", "blur_radius", self.blur_radius)))
        self.text_font_family = g.str("Tools", "text_font_family", self.text_font_family)
        self.text_font_size = max(4.0, min(200.0, g.float("Tools", "text_font_size", self.text_font_size)))
        self.text_bold = g.bool("Tools", "text_bold", self.text_bold)
        self.text_italic = g.bool("Tools", "text_italic", self.text_italic)
        self.migrated_from = g.str("Meta", "migrated_from", None) or None

    def _read_legacy(self, kf: GLib.KeyFile) -> None:
        """Map the 1.4 ``[Settings]`` group onto the 2.0 fields."""
        g = _Getter(kf)
        S = "Settings"
        self.screenshot_path = g.str(S, "screenshot_path", self.screenshot_path)
        fmt = g.int(S, "filename_format", 2)      # 1.4 default: LinShot prefix + timestamp
        self.prefix = PREFIXES[fmt % 2]            # 0,2 -> LinScreenCapture_ (was LinShot_); 1,3 -> Screenshot_
        self.numbering = "timestamp" if fmt >= 2 else "sequence"
        self.autostart = g.bool(S, "start_with_os", self.autostart)
        self.hotkey = HOTKEYS[max(0, min(len(HOTKEYS) - 1, g.int(S, "shortcut_key", 1)))]
        self.register_hotkey = g.bool(S, "default_screenshot_app", self.register_hotkey)
        for t in _LEGACY_TOOLS:
            ts = self.tools[t]
            c = parse_colour(g.str(S, f"color_{t}", ""))
            ts.colour = c or "#ff0000"             # 1.4 default colour was pure red
            if t != "text":
                ts.width = g.float(S, f"width_{t}", _LEGACY_WIDTHS.get(t, ts.width))
            ts.shadow = g.bool(S, f"shadow_{t}", False)
            ts.shadow_intensity = max(0.0, min(1.0, g.float(S, f"shadow_int_{t}", 0.4)))
        self.blur_block = max(2, min(64, g.int(S, "blur_block_size", self.blur_block)))
        self.text_font_family = g.str(S, "text_font_family", "Arial")
        self.text_font_size = g.float(S, "text_font_size", 14.0)
        self.text_bold = g.bool(S, "text_font_bold", True)
        self.text_italic = g.bool(S, "text_font_italic", False)

    def save(self) -> None:
        kf = GLib.KeyFile()
        if self.path.is_file():
            try:
                kf.load_from_file(str(self.path), GLib.KeyFileFlags.KEEP_COMMENTS)
            except GLib.Error:
                kf = GLib.KeyFile()
        kf.set_integer("Window", "width", int(self.window_width))
        kf.set_integer("Window", "height", int(self.window_height))
        kf.set_boolean("Window", "maximized", bool(self.window_maximized))
        kf.set_boolean("Window", "left_collapsed", bool(self.left_collapsed))
        kf.set_boolean("Window", "right_collapsed", bool(self.right_collapsed))
        kf.set_string("Capture", "screenshot_path", self.screenshot_path)
        kf.set_string("Capture", "prefix", self.prefix)
        kf.set_string("Capture", "numbering", self.numbering)
        kf.set_string("Capture", "format", self.format)
        kf.set_integer("Capture", "jpeg_quality", int(self.jpeg_quality))
        kf.set_boolean("Capture", "copy_to_clipboard", bool(self.copy_to_clipboard))
        kf.set_integer("Capture", "delay_seconds", int(self.delay_seconds))
        kf.set_boolean("Capture", "include_pointer", bool(self.include_pointer))
        kf.set_integer("Capture", "pin_opacity", int(self.pin_opacity))
        kf.set_string("Capture", "backend", self.backend)
        kf.set_boolean("Capture", "reopen_last", bool(self.reopen_last))
        kf.set_string("Capture", "selection_style", self.selection_style)
        kf.set_boolean("System", "autostart", bool(self.autostart))
        kf.set_string("System", "hotkey", self.hotkey)
        kf.set_boolean("System", "register_hotkey", bool(self.register_hotkey))
        for t in TOOLS:
            ts = self.tools[t]
            kf.set_string("Tools", f"colour_{t}", ts.colour)
            kf.set_double("Tools", f"width_{t}", float(ts.width))
            kf.set_boolean("Tools", f"shadow_{t}", bool(ts.shadow))
            kf.set_double("Tools", f"shadow_intensity_{t}", float(ts.shadow_intensity))
        kf.set_boolean("Tools", "universal", bool(self.universal))
        kf.set_integer("Tools", "blur_block", int(self.blur_block))
        kf.set_double("Tools", "blur_radius", float(self.blur_radius))
        kf.set_string("Tools", "text_font_family", self.text_font_family)
        kf.set_double("Tools", "text_font_size", float(self.text_font_size))
        kf.set_boolean("Tools", "text_bold", bool(self.text_bold))
        kf.set_boolean("Tools", "text_italic", bool(self.text_italic))
        if self.migrated_from:
            kf.set_string("Meta", "migrated_from", self.migrated_from)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        kf.save_to_file(str(self.path))

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("root", None)
        return d


class _Getter:
    def __init__(self, kf: GLib.KeyFile):
        self.kf = kf

    def _try(self, fn, group, key, default):
        try:
            return fn(group, key)
        except GLib.Error:
            return default

    def int(self, g, k, d):
        return self._try(self.kf.get_integer, g, k, d)

    def float(self, g, k, d):
        return self._try(self.kf.get_double, g, k, d)

    def bool(self, g, k, d):
        return self._try(self.kf.get_boolean, g, k, d)

    def str(self, g, k, d):
        v = self._try(self.kf.get_string, g, k, None)
        return d if v is None else v

    def choice(self, g, k, allowed, d):
        v = self.str(g, k, d)
        return v if v in allowed else d
