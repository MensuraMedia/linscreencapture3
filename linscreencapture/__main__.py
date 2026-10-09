"""Entry point: ``python -m linscreencapture`` or the ``linscreencapture`` script."""
from __future__ import annotations
import sys


def main(argv: list[str] | None = None) -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from .app.application import Application
    app = Application()
    return app.run(sys.argv if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
