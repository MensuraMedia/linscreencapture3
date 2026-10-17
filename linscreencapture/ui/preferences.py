"""Settings dialog: the Capture page and the System page (background agent, PrintScreen, autostart).

The hotkey preset, its registration and the Shortcuts page arrive with the rest of Phase 6."""
from __future__ import annotations
import os

from gi.repository import Adw, Gio, Gtk, GLib

from ..model.settings import Settings, PREFIXES, NUMBERING, FORMATS, HOTKEYS

LABELS = {
    "numbering": ("Sequence (LinScreenCapture_12)", "Timestamp (2026-10-09_21-14-05)"),
    "format": ("PNG", "JPEG", "WebP"),
    "hotkey": ("Off", "PrintScreen", "Ctrl+PrintScreen", "Shift+PrintScreen", "Ctrl+Shift+S", "Ctrl+Alt+S"),
}


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings: Settings, on_change=None, autostart_root: str | None = None):
        super().__init__(title="Settings", search_enabled=False)
        self.settings = settings
        self.on_change = on_change
        self.autostart_root = autostart_root
        self.add(self._capture_page())
        self.add(self._system_page())

    # -- pages ------------------------------------------------------------
    def _capture_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Capture", icon_name="lsc-camera-symbolic")
        s = self.settings

        saving = Adw.PreferencesGroup(title="Saving")
        self.folder_row = Adw.ActionRow(title="Save folder", subtitle=self._pretty(s.screenshot_path),
                                        activatable=True)
        pick = Gtk.Button(icon_name="lsc-folder-open-symbolic", valign=Gtk.Align.CENTER)
        pick.add_css_class("flat")
        pick.set_tooltip_text("Choose folder")
        pick.connect("clicked", self._choose_folder)
        self.folder_row.add_suffix(pick)
        self.folder_row.connect("activated", self._choose_folder)
        saving.add(self.folder_row)
        saving.add(self._combo("File name prefix", PREFIXES, PREFIXES, "prefix"))
        saving.add(self._combo("Numbering", LABELS["numbering"], NUMBERING, "numbering"))
        saving.add(self._combo("Format", LABELS["format"], FORMATS, "format"))
        page.add(saving)

        capture = Adw.PreferencesGroup(title="Capture")
        capture.add(self._spin("Delayed capture", "Seconds to wait for the Delayed mode", "delay_seconds", 0, 60))
        page.add(capture)

        window = Adw.PreferencesGroup(title="Window")
        window.add(self._switch("Start with the left rail collapsed", None, "left_collapsed"))
        window.add(self._switch("Start with the right rail collapsed", None, "right_collapsed"))
        window.add(self._switch("Dashed frame around the selected layer", "Off: only the resize handles mark the selection", "selection_frame"))
        page.add(window)
        return page

    def _system_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="System", icon_name="lsc-gear-symbolic")
        from ..services import autostart
        self.settings.autostart = autostart.is_enabled(self.autostart_root)   # the entry on disk is the truth
        agent = Adw.PreferencesGroup(title="Background agent",
                                     description="PrintScreen runs a region capture that is saved and copied to the clipboard")
        agent.add(self._switch("Keep running in the background",
                               "Closing the window hides it; Quit (Ctrl+Q or the tray menu) ends the agent", "keep_running"))
        agent.add(self._switch("Tray icon", "Capture · Open editor · Quit", "tray_icon"))
        self.autostart_row = self._switch("Start at login", "Starts the agent without a window", "autostart")
        agent.add(self.autostart_row)
        agent.add(self._switch("PrintScreen opens the editor",
                               "Off: the capture goes to the clipboard, the save folder and the studio without popping it up",
                               "hotkey_opens_editor"))
        page.add(agent)

        hotkey = Adw.PreferencesGroup(title="Capture hotkey",
                                      description="Runs the fast Region capture from anywhere, including inside this window")
        hotkey.add(self._combo("Key", LABELS["hotkey"], HOTKEYS, "hotkey"))
        hotkey.add(self._switch("Register with the desktop",
                                "Cinnamon: written as a custom shortcut and re-applied at every start", "register_hotkey"))
        page.add(hotkey)
        return page

    # -- row builders -----------------------------------------------------
    def _combo(self, title: str, labels, values, field: str, subtitle: str | None = None) -> Adw.ComboRow:
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new(list(labels)))
        if subtitle:
            row.set_subtitle(subtitle)
        current = getattr(self.settings, field)
        row.set_selected(list(values).index(current) if current in values else 0)
        row.connect("notify::selected", lambda r, _p: self._set(field, list(values)[r.get_selected()]))
        return row

    def _switch(self, title: str, subtitle: str | None, field: str) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, active=bool(getattr(self.settings, field)))
        if subtitle:
            row.set_subtitle(subtitle)
        row.connect("notify::active", lambda r, _p: self._set(field, r.get_active()))
        return row

    def _spin(self, title: str, subtitle: str, field: str, lo: int, hi: int) -> Adw.SpinRow:
        row = Adw.SpinRow.new_with_range(lo, hi, 1)
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.set_value(getattr(self.settings, field))
        row.connect("notify::value", lambda r, _p: self._set(field, int(r.get_value())))
        return row

    # -- behaviour ---------------------------------------------------------
    def _set(self, field: str, value) -> None:
        if getattr(self.settings, field) == value:
            return
        setattr(self.settings, field, value)
        if field == "autostart":
            from ..services import autostart
            try:
                autostart.set_enabled(bool(value), self.autostart_root)
            except OSError as exc:
                print(f"autostart not changed: {exc}")
        try:
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            print(f"settings not saved: {exc}")
        if self.on_change:
            self.on_change(field, value)

    def _choose_folder(self, *_a) -> None:
        dialog = Gtk.FileDialog(title="Save captures in…", modal=True)
        try:
            dialog.set_initial_folder(Gio.File.new_for_path(os.path.expanduser(self.settings.screenshot_path)))
        except Exception:  # noqa: BLE001
            pass
        dialog.select_folder(self.get_root(), None, self._folder_chosen)

    def _folder_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder is not None:
            path = folder.get_path()
            self._set("screenshot_path", path)
            self.folder_row.set_subtitle(self._pretty(path))

    @staticmethod
    def _pretty(path: str) -> str:
        home = os.path.expanduser("~")
        return path.replace(home, "~") if path.startswith(home) else path
