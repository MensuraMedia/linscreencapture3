"""Settings dialog: the Capture page and the System page (run at startup, background agent, capture hotkey).

The capture hotkey is a preset (PrintScreen by default) or any shortcut the user records (``ShortcutRecorder``).
The in-app Shortcuts page arrives with the rest of Phase 6."""
from __future__ import annotations
import os

from gi.repository import Adw, Gdk, Gio, Gtk, GLib

from ..model.settings import Settings, PREFIXES, NUMBERING, FORMATS, HOTKEYS

LABELS = {
    "numbering": ("Sequence (LinScreenCapture_12)", "Timestamp (2026-10-09_21-14-05)"),
    "format": ("PNG", "JPEG", "WebP"),
    "hotkey": ("Off", "PrintScreen", "Ctrl+PrintScreen", "Shift+PrintScreen", "Ctrl+Shift+S", "Ctrl+Alt+S"),
}


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings: Settings, on_change=None, autostart_root: str | None = None, suspend_hotkey=None):
        super().__init__(title="Settings", search_enabled=False)
        self.settings = settings
        self.on_change = on_change
        # default to the settings' own root: a dialog built on test settings must never touch ~/.config/autostart
        self.autostart_root = autostart_root if autostart_root is not None else settings.root
        self.suspend_hotkey = suspend_hotkey or (lambda _on: None)
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
        startup = Adw.PreferencesGroup(title="Startup")
        self.autostart_row = self._switch("Run at startup",
                                          "Starts the background agent without a window when you log in, so the "
                                          "capture hotkey works straight away", "autostart")
        startup.add(self.autostart_row)
        page.add(startup)

        agent = Adw.PreferencesGroup(title="Background agent",
                                     description="The hotkey runs a region capture that is saved and copied to the clipboard")
        agent.add(self._switch("Keep running in the background",
                               "Closing the window hides it; Quit (Ctrl+Q or the tray menu) ends the agent", "keep_running"))
        agent.add(self._switch("Panel icon", "The orange icon in the panel while the app runs · double-click opens "
                               "the editor · right-click: Capture, Open editor, Quit", "tray_icon"))
        agent.add(self._switch("The hotkey opens the editor",
                               "Off: the capture goes to the clipboard, the save folder and the studio without popping it up",
                               "hotkey_opens_editor"))
        page.add(agent)

        hotkey = Adw.PreferencesGroup(title="Capture hotkey",
                                      description="Runs the fast Region capture from anywhere, including inside this window")
        hotkey.add(self._hotkey_row())
        hotkey.add(self._switch("Register with the desktop",
                                "Cinnamon: written as a custom shortcut and re-applied at every start", "register_hotkey"))
        page.add(hotkey)
        return page

    # -- capture hotkey ----------------------------------------------------
    def _hotkey_row(self) -> Adw.ComboRow:
        """Presets plus a last "Custom" entry; the Record button (or choosing Custom) records any key combination."""
        self.hotkey_row = row = Adw.ComboRow(title="Key")
        record = Gtk.Button(label="Record…", valign=Gtk.Align.CENTER)
        record.set_tooltip_text("Press any key or key combination to use as the capture hotkey")
        record.connect("clicked", lambda *_: self.record_hotkey())
        row.add_suffix(record)
        self._hotkey_sync = False
        self._fill_hotkey_row()
        row.connect("notify::selected", self._hotkey_selected)
        return row

    def _fill_hotkey_row(self) -> None:
        """Show the current hotkey. The model is never replaced (doing that from the combo's own selection handler
        froze the dialog); only the last item's label is swapped, and never while the popover is choosing."""
        current = self.settings.hotkey
        custom = current not in HOTKEYS
        label = f"Custom · {hotkey_label(current)}" if custom else "Custom…"
        self._hotkey_sync = True
        model = self.hotkey_row.get_model()
        if model is None:
            self.hotkey_row.set_model(Gtk.StringList.new(list(LABELS["hotkey"]) + [label]))
        elif model.get_string(len(HOTKEYS)) != label:
            model.splice(len(HOTKEYS), 1, [label])
        self.hotkey_row.set_selected(len(HOTKEYS) if custom else HOTKEYS.index(current))
        self._hotkey_sync = False

    def _hotkey_selected(self, row, _p) -> None:
        if self._hotkey_sync:
            return
        i = row.get_selected()
        if i < len(HOTKEYS):
            self._set("hotkey", HOTKEYS[i])
        else:                                 # open the recorder once the combo's popover has closed
            GLib.idle_add(lambda: (self.record_hotkey(), False)[1])

    def record_hotkey(self) -> "ShortcutRecorder":
        self.suspend_hotkey(True)
        rec = ShortcutRecorder(self.get_root(), self._recorded)
        rec.present()
        return rec

    def _recorded(self, accel: str | None) -> None:
        """``accel`` is an accelerator name, ``none`` (turned off) or None (cancelled)."""
        if accel is not None and accel != self.settings.hotkey:
            self._set("hotkey", accel)        # on_change re-registers it with the desktop
        else:
            self.suspend_hotkey(False)
        GLib.idle_add(lambda: (self._fill_hotkey_row(), False)[1])

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


def hotkey_label(accel: str) -> str:
    """``<Control>Print`` → ``Ctrl+Print`` (as the desktop shows it); ``none`` → ``Off``."""
    if accel in ("", "none"):
        return "Off"
    ok, key, mods = Gtk.accelerator_parse(accel)
    return Gtk.accelerator_get_label(key, mods) if ok and key else accel


MODIFIER_KEYS = {Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Alt_L,
                 Gdk.KEY_Alt_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Hyper_L,
                 Gdk.KEY_Hyper_R, Gdk.KEY_ISO_Level3_Shift, Gdk.KEY_Caps_Lock, Gdk.KEY_Num_Lock}


def accel_for_key(keyval: int, state: Gdk.ModifierType) -> tuple[str | None, str]:
    """The accelerator a key press stands for, or ``(None, reason)`` when it cannot be a global hotkey.

    Plain letters, digits and symbols need a modifier (they would stop typing everywhere); PrintScreen, the function
    keys, Pause and the like work alone. Alt+PrintScreen arrives as Sys_Req on X11 and is mapped back to Print."""
    mods = state & Gtk.accelerator_get_default_mod_mask()
    if keyval in MODIFIER_KEYS:
        return None, ""
    if keyval == Gdk.KEY_Sys_Req:
        keyval = Gdk.KEY_Print
    keyval = Gdk.keyval_to_lower(keyval)
    if not mods and Gdk.keyval_to_unicode(keyval) > 0x20:
        return None, "Add Ctrl, Alt, Shift or Super to a letter, digit or symbol"
    name = Gtk.accelerator_name(keyval, mods)
    return (name, "") if name else (None, "That key cannot be used")


class ShortcutRecorder(Adw.Window):
    """A small modal window that records the next key combination. It is a window of its own (not part of the
    application) so the studio's accelerators never see the keys; the desktop binding is released while it is open."""

    def __init__(self, parent, done):
        super().__init__(title="Capture hotkey", modal=True, default_width=420, default_height=260, resizable=False)
        if isinstance(parent, Gtk.Window):
            self.set_transient_for(parent)
        self._done = done
        self._result = None
        self.status = Adw.StatusPage(icon_name="lsc-camera-symbolic", title="Press the new hotkey",
                                     description="PrintScreen, a function key or a combination such as "
                                                 "Ctrl+Shift+S\nEsc cancels · Backspace turns the hotkey off")
        view = Adw.ToolbarView(content=self.status)
        view.add_top_bar(Adw.HeaderBar())
        self.set_content(view)
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        self.connect("close-request", self._closing)

    def _key(self, _ctl, keyval, _code, state) -> bool:
        mods = state & Gtk.accelerator_get_default_mod_mask()
        if not mods and keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if not mods and keyval == Gdk.KEY_BackSpace:
            return self.finish("none")
        accel, reason = accel_for_key(keyval, state)
        if accel is None:
            if reason:
                self.status.set_description(reason)
            return True
        return self.finish(accel)

    def finish(self, accel: str) -> bool:
        self._result = accel
        self.close()
        return True

    def _closing(self, *_a) -> bool:
        done, self._done = self._done, None
        if done:
            done(self._result)
        return False
