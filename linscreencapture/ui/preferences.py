"""Settings dialog. Phase 3 ships the Capture page; System and Shortcuts pages arrive in Phase 6."""
from __future__ import annotations
import os

from gi.repository import Adw, Gio, Gtk, GLib

from ..model.settings import Settings, PREFIXES, NUMBERING, FORMATS, SELECTION_STYLES

LABELS = {
    "numbering": ("Sequence (LinScreenCapture_12)", "Timestamp (2026-10-09_21-14-05)"),
    "format": ("PNG", "JPEG", "WebP"),
    "selection_style": ("Free-form box with resize handles · adjust, then Enter", "Simple box · captures when you release"),
}


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings: Settings, on_change=None):
        super().__init__(title="Settings", search_enabled=False)
        self.settings = settings
        self.on_change = on_change
        self.add(self._capture_page())

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
        capture.add(self._combo("Selection box", LABELS["selection_style"], SELECTION_STYLES, "selection_style",
                                subtitle="How the region is chosen in the capture overlay"))
        capture.add(self._switch("Copy to clipboard", "Every capture is also copied, even if you never save", "copy_to_clipboard"))
        capture.add(self._spin("Delayed capture", "Seconds to wait for the Delayed mode", "delay_seconds", 0, 60))
        page.add(capture)

        window = Adw.PreferencesGroup(title="Window")
        window.add(self._switch("Start with the left rail collapsed", None, "left_collapsed"))
        window.add(self._switch("Start with the right rail collapsed", None, "right_collapsed"))
        page.add(window)
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
