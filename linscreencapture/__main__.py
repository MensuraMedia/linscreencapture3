"""Entry point: ``python -m linscreencapture`` or the ``linscreencapture`` script."""
from __future__ import annotations
import sys


def main(argv: list[str] | None = None) -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib
    from . import APP_ID
    # Before GTK starts: X11 takes WM_CLASS from the program name. Under ``python3 -m`` it was "__main__.py", so
    # Alt+Tab, the panel and "not responding" dialogs could not match the window to its .desktop entry and icon.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("LinScreenCapture")
    from .app.application import Application
    app = Application()
    return app.run(sys.argv if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
