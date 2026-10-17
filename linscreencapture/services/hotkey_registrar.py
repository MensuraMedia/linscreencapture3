"""Registers the capture hotkey (``Settings.hotkey``) with the desktop. Cinnamon for now; see docs/CAPTURE.md §4.

Lessons carried over from 1.4 (``keybinding_manager.c``, commits 88493c8 … ccd3425 of the original repository):

* Cinnamon only honours custom entries named ``customN`` that are listed in ``custom-list``; ``binding`` is a list.
* The built-in screenshot keys must be emptied with a real ``[]`` value, and all six of them must be checked.
* Cinnamon caches its bindings: a ``dconf`` write is not picked up until the custom list is rebuilt. This module asks
  Cinnamon to rebuild it (``org.Cinnamon.Eval`` → ``remove_custom_keybindings(); setup_custom_keybindings()``) and
  falls back to re-writing ``custom-list`` (a changed value triggers the same reload).
* Stale entries from earlier builds (commands containing ``linshot`` or ``linscreencapture``) are folded into one slot.
* Only one mechanism owns the key: no XGrabKey on desktops that have a keybinding API (double captures otherwise).

Unlike 1.4, an existing ``customN`` that belongs to another application is never overwritten. No GTK here.
"""
from __future__ import annotations
import logging
import shlex
import shutil
import sys

from gi.repository import Gio, GLib

LOG = logging.getLogger("linscreencapture.hotkey")

ROOT_SCHEMA = "org.cinnamon.desktop.keybindings"
CUSTOM_SCHEMA = "org.cinnamon.desktop.keybindings.custom-keybinding"
CUSTOM_PATH = "/org/cinnamon/desktop/keybindings/custom-keybindings/{}/"
MEDIA_SCHEMA = "org.cinnamon.desktop.keybindings.media-keys"
BUILTIN_SCREENSHOT_KEYS = ("screenshot", "area-screenshot", "window-screenshot",
                           "screenshot-clip", "area-screenshot-clip", "window-screenshot-clip")
NAME = "LinScreenCapture"
OURS = ("linscreencapture", "linshot")       # commands that belong to this application, any version
RELOAD_JS = 'Main.keybindingManager.remove_custom_keybindings(); Main.keybindingManager.setup_custom_keybindings(); "ok";'


def supported() -> bool:
    src = Gio.SettingsSchemaSource.get_default()
    return src is not None and src.lookup(CUSTOM_SCHEMA, True) is not None and src.lookup(ROOT_SCHEMA, True) is not None


def cinnamon_accel(hotkey: str) -> str:
    """``<Control>Print`` → ``<Primary>Print`` (how Cinnamon's own keyboard settings write it)."""
    return hotkey.replace("<Control>", "<Primary>")


def capture_command(which=shutil.which) -> str:
    script = which("linscreencapture")
    if script:
        return f"{shlex.quote(script)} --capture"
    from .autostart import CHECKOUT
    return f"env PYTHONPATH={shlex.quote(str(CHECKOUT))} {shlex.quote(sys.executable)} -m linscreencapture --capture"


def _custom(slot: str, new=Gio.Settings.new_with_path) -> Gio.Settings:
    return new(CUSTOM_SCHEMA, CUSTOM_PATH.format(slot))


def _is_ours(command: str) -> bool:
    return any(tag in command for tag in OURS)


def _free_slot(used: set[str]) -> str:
    n = 0
    while f"custom{n}" in used:
        n += 1
    return f"custom{n}"


def register(hotkey: str, command: str | None = None, *, settings_new=Gio.Settings.new,
             custom_new=Gio.Settings.new_with_path, reload=None) -> str | None:
    """Bind ``hotkey`` to ``command``; returns the custom slot used, or None when the hotkey is ``none``."""
    if hotkey in ("", "none"):
        unregister(settings_new=settings_new, custom_new=custom_new, reload=reload)
        return None
    accel = cinnamon_accel(hotkey)
    command = command or capture_command()
    root = settings_new(ROOT_SCHEMA)
    customs = list(root.get_strv("custom-list"))
    slot = None
    for name in list(customs):
        cs = custom_new(CUSTOM_SCHEMA, CUSTOM_PATH.format(name))
        if not _is_ours(cs.get_string("command")):
            if accel in cs.get_strv("binding"):
                LOG.warning("%s (%s) is also bound to %s", name, cs.get_string("name"), accel)
            continue
        if slot is None:
            slot = name                              # reuse our first slot
        else:                                        # fold duplicates from earlier builds into it
            cs.reset("binding"); cs.reset("command"); cs.reset("name")
            customs.remove(name)
    if slot is None:
        slot = _free_slot(set(customs))
        customs.append(slot)
    cs = custom_new(CUSTOM_SCHEMA, CUSTOM_PATH.format(slot))
    cs.set_strv("binding", [accel])
    cs.set_string("command", command)
    cs.set_string("name", NAME)
    media = settings_new(MEDIA_SCHEMA)
    for key in BUILTIN_SCREENSHOT_KEYS:              # free the key from Cinnamon's own screenshot actions
        current = list(media.get_strv(key))
        kept = [a for a in current if cinnamon_accel(a) != accel]
        if kept != current:
            media.set_strv(key, kept)
            LOG.info("removed %s from the built-in %s binding", accel, key)
    root.set_strv("custom-list", customs)
    Gio.Settings.sync()
    (reload or reload_cinnamon)(root, customs)
    LOG.info("hotkey %s → %s (%s)", accel, command, slot)
    return slot


def unregister(*, settings_new=Gio.Settings.new, custom_new=Gio.Settings.new_with_path, reload=None) -> None:
    root = settings_new(ROOT_SCHEMA)
    customs = list(root.get_strv("custom-list"))
    for name in list(customs):
        cs = custom_new(CUSTOM_SCHEMA, CUSTOM_PATH.format(name))
        if _is_ours(cs.get_string("command")):
            cs.reset("binding"); cs.reset("command"); cs.reset("name")
            customs.remove(name)
    root.set_strv("custom-list", customs)
    Gio.Settings.sync()
    (reload or reload_cinnamon)(root, customs)


def reload_cinnamon(root: Gio.Settings, customs: list[str]) -> None:
    """Make the running Cinnamon re-read its custom keybindings."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync("org.Cinnamon", "/org/Cinnamon", "org.Cinnamon", "Eval", GLib.Variant("(s)", (RELOAD_JS,)),
                            GLib.VariantType("(bs)"), Gio.DBusCallFlags.NONE, 2000, None)
        ok, _out = res.unpack()
        if ok:
            LOG.debug("Cinnamon reloaded its custom keybindings")
            return
    except GLib.Error as exc:
        LOG.debug("org.Cinnamon.Eval unavailable: %s", exc.message)
    root.set_strv("custom-list", [])                 # fallback: a changed value makes Cinnamon reload
    Gio.Settings.sync()
    root.set_strv("custom-list", customs)
    Gio.Settings.sync()
