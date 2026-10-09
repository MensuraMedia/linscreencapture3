"""Persisted settings (Phase 1 subset): window geometry, rail state, save folder.

Stored as a GLib key file at ``~/.config/linscreencapture/settings.conf``.
The legacy 1.x file ``~/.config/linshot/settings.conf`` is read for the save
folder when the new file does not exist yet; the full schema migration lands in
Phase 2.
"""
from __future__ import annotations
import os
import pathlib
from dataclasses import dataclass, field

from gi.repository import GLib

NEW_DIR = "linscreencapture"
LEGACY_DIR = "linshot"
FILE = "settings.conf"


def config_dir(root: str | None = None) -> pathlib.Path:
    return pathlib.Path(root or GLib.get_user_config_dir()) / NEW_DIR


def _default_pictures() -> str:
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~/Pictures")


@dataclass
class Settings:
    window_width: int = 1360
    window_height: int = 840
    window_maximized: bool = False
    left_collapsed: bool = False
    right_collapsed: bool = False
    screenshot_path: str = field(default_factory=_default_pictures)
    root: str | None = None  # config root override (tests)

    # -- persistence -------------------------------------------------------
    @property
    def path(self) -> pathlib.Path:
        return config_dir(self.root) / FILE

    @classmethod
    def load(cls, root: str | None = None) -> "Settings":
        s = cls(root=root)
        kf = GLib.KeyFile()
        if s.path.is_file():
            try:
                kf.load_from_file(str(s.path), GLib.KeyFileFlags.NONE)
            except GLib.Error:
                return s
            s.window_width = _get(kf, "Window", "width", s.window_width, int)
            s.window_height = _get(kf, "Window", "height", s.window_height, int)
            s.window_maximized = _get(kf, "Window", "maximized", s.window_maximized, bool)
            s.left_collapsed = _get(kf, "Window", "left_collapsed", s.left_collapsed, bool)
            s.right_collapsed = _get(kf, "Window", "right_collapsed", s.right_collapsed, bool)
            s.screenshot_path = _get(kf, "Settings", "screenshot_path", s.screenshot_path, str)
        else:
            legacy = pathlib.Path(root or GLib.get_user_config_dir()) / LEGACY_DIR / FILE
            if legacy.is_file():
                lk = GLib.KeyFile()
                try:
                    lk.load_from_file(str(legacy), GLib.KeyFileFlags.NONE)
                    s.screenshot_path = _get(lk, "Settings", "screenshot_path", s.screenshot_path, str)
                except GLib.Error:
                    pass
        return s

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
        kf.set_string("Settings", "screenshot_path", self.screenshot_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        kf.save_to_file(str(self.path))


def _get(kf: GLib.KeyFile, group: str, key: str, default, kind):
    try:
        if kind is int:
            return kf.get_integer(group, key)
        if kind is bool:
            return kf.get_boolean(group, key)
        return kf.get_string(group, key)
    except GLib.Error:
        return default
