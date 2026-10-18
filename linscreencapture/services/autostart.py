"""Login autostart for the background agent: ``~/.config/autostart/com.mensuramedia.LinScreenCapture.desktop``.

The entry runs ``<launcher> --background``: the ``linscreencapture`` script when it is on PATH, otherwise this
checkout through ``python3 -m linscreencapture`` with ``Path=`` set to the checkout. No GTK here.
"""
from __future__ import annotations
import pathlib
import shlex
import shutil
import sys

from gi.repository import GLib

from .. import APP_ID

CHECKOUT = pathlib.Path(__file__).resolve().parent.parent.parent


def entry_path(root: str | None = None) -> pathlib.Path:
    return pathlib.Path(root or GLib.get_user_config_dir()) / "autostart" / f"{APP_ID}.desktop"


def launch_command(which=shutil.which) -> tuple[str, str | None]:
    """``(Exec line, Path or None)`` that starts the agent."""
    script = which("linscreencapture")
    if script:
        return f"{shlex.quote(script)} --background", None
    return f"{shlex.quote(sys.executable)} -m linscreencapture --background", str(CHECKOUT)


def desktop_entry(exec_line: str, path: str | None) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=LinScreenCapture agent",
        "Comment=Background agent: PrintScreen copies a region to the clipboard",
        f"Exec={exec_line}",
        f"Icon={APP_ID}",               # the application icon (install.sh, .deb, make launcher)
        "Terminal=false",
        "NoDisplay=true",
        "X-GNOME-Autostart-enabled=true",
        "X-GNOME-Autostart-Delay=3",
    ]
    if path:
        lines.append(f"Path={path}")
    return "\n".join(lines) + "\n"


def is_enabled(root: str | None = None) -> bool:
    """The entry exists and is not switched off (Cinnamon's Startup Applications writes
    ``X-GNOME-Autostart-enabled=false`` instead of deleting the file)."""
    p = entry_path(root)
    if not p.is_file():
        return False
    try:
        text = p.read_text().lower()
    except OSError:
        return False
    return "x-gnome-autostart-enabled=false" not in text and "hidden=true" not in text


def sync(want: bool, first_run: bool, root: str | None = None, which=shutil.which) -> bool:
    """Called at every start. On the first run the setting (default on) creates the entry; afterwards the entry on
    disk wins, so a choice made in the desktop's Startup Applications is respected. An enabled entry is rewritten
    when the launcher moved. Returns whether the agent runs at login."""
    if first_run:
        set_enabled(want, root, which)
        return want
    if not is_enabled(root):
        return False
    p = entry_path(root)
    fresh = desktop_entry(*launch_command(which))
    if p.read_text() != fresh:
        p.write_text(fresh)
    return True


def set_enabled(enabled: bool, root: str | None = None, which=shutil.which) -> pathlib.Path:
    """Write or remove the entry; returns its path."""
    p = entry_path(root)
    if enabled:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(desktop_entry(*launch_command(which)))
    elif p.exists():
        p.unlink()
    return p
