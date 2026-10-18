"""Status icon for the background agent: ``python3 -m linscreencapture.tray``.

GTK 4 has no status-icon API and a process cannot load GTK 3 next to GTK 4, so the icon lives in this small GTK 3
helper. The agent (``app/application.py``) starts it and it talks back only over D-Bus: menu items activate the
agent's exported application actions (``hotkey-capture``, ``show-editor``, ``quit``) and the helper exits as soon as
the agent's bus name vanishes. XApp.StatusIcon is used on Cinnamon/MATE/Xfce; AyatanaAppIndicator3 elsewhere.

The icon is orange (``TRAY_COLOUR`` #ffa222, ``resources/icons/linscreencapture-tray.svg``, a full-colour SVG so the
panel does not recolour it). A **double-click** opens the editor; a right-click opens the menu. AppIndicator has no
click events, so there the menu's *Open editor* is the way in.
"""
from __future__ import annotations
import logging
import pathlib
import sys

from . import APP_ID
OBJECT_PATH = "/" + APP_ID.replace(".", "/")
ICONS = pathlib.Path(__file__).resolve().parent.parent / "resources" / "icons"
ICON_FILE = ICONS / "linscreencapture-tray.svg"
TRAY_COLOUR = "#ffa222"
PRGNAME = "linscreencapture-tray"   # unique: XApp derives the D-Bus name from it
FALLBACK_ICON = "linscreencapture3"
TOOLTIP = "LinScreenCapture · double-click to open the editor · PrintScreen captures a region"
# (label, application action) — None is a separator
MENU = (("Capture region to clipboard", "hotkey-capture"), ("Open editor", "show-editor"), None, ("Quit", "quit"))

LOG = logging.getLogger("linscreencapture.tray")


def icon_source() -> str:
    return str(ICON_FILE) if ICON_FILE.is_file() else FALLBACK_ICON


class DoubleClick:
    """Turns single ``activate`` events (button, X time in ms) into double-clicks."""

    def __init__(self, interval_ms: int = 400):
        self.interval = interval_ms
        self._last = None

    def click(self, button: int, time_ms: int) -> bool:
        if button != 1:
            self._last = None
            return False
        if self._last is not None and 0 <= time_ms - self._last <= self.interval:
            self._last = None
            return True
        self._last = time_ms
        return False


def build_menu(Gtk, activate) -> object:
    menu = Gtk.Menu()
    for entry in MENU:
        if entry is None:
            menu.append(Gtk.SeparatorMenuItem())
            continue
        label, action = entry
        item = Gtk.MenuItem(label=label)
        item.connect("activate", lambda _i, a=action: activate(a))
        menu.append(item)
    menu.show_all()
    return menu


def _xapp_icon(Gtk, menu, activate):
    import gi
    gi.require_version("XApp", "1.0")
    from gi.repository import XApp
    icon = XApp.StatusIcon()
    icon.set_name("linscreencapture")
    icon.set_icon_name(icon_source())
    icon.set_tooltip_text(TOOLTIP)
    icon.set_secondary_menu(menu)
    settings = Gtk.Settings.get_default()
    clicks = DoubleClick(settings.get_property("gtk-double-click-time") if settings else 400)

    def activated(_icon, button, time_ms):
        if clicks.click(button, time_ms):
            activate("show-editor")                  # double-click opens the editor
    icon.connect("activate", activated)
    icon.set_visible(True)
    return icon


def _ayatana_icon(Gtk, menu, activate):
    import gi
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AI
    src = icon_source()
    ind = AI.Indicator.new("linscreencapture", FALLBACK_ICON, AI.IndicatorCategory.APPLICATION_STATUS)
    if src.startswith("/"):
        ind.set_icon_theme_path(str(pathlib.Path(src).parent))
        ind.set_icon_full(pathlib.Path(src).stem, "LinScreenCapture")
    ind.set_title("LinScreenCapture")
    ind.set_menu(menu)
    ind.set_status(AI.IndicatorStatus.ACTIVE)
    return ind


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="tray: %(message)s")
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gio, GLib, Gtk
    # XApp names the icon's bus name after the program: as plain "tray.py" it collided with Linux Mint's own
    # tray.py helpers (mintreport), never acquired org.x.StatusIcon.tray_py and the icon stayed invisible.
    GLib.set_prgname(PRGNAME)
    if not Gtk.init_check()[0]:
        LOG.error("no display")
        return 1
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    actions = Gio.DBusActionGroup.get(bus, APP_ID, OBJECT_PATH)

    def activate(name: str) -> None:
        actions.activate_action(name, None)

    menu = build_menu(Gtk, activate)
    icon = None
    for make in (_xapp_icon, _ayatana_icon):
        try:
            icon = make(Gtk, menu, activate)
            LOG.info("status icon via %s", make.__name__.strip("_").replace("_icon", ""))
            break
        except (ValueError, ImportError) as exc:   # typelib missing
            LOG.info("%s unavailable: %s", make.__name__, exc)
    if icon is None:
        LOG.error("no status-icon library (install gir1.2-xapp-1.0 or gir1.2-ayatanaappindicator3-0.1)")
        return 1
    Gio.bus_watch_name_on_connection(bus, APP_ID, Gio.BusNameWatcherFlags.NONE, None,
                                     lambda *_: Gtk.main_quit())   # the agent is gone: so is the icon
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
