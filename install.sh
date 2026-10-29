#!/usr/bin/env bash
# LinScreenCapture installer.
#
#   ./install.sh                 install for this user into ~/.local (no root needed)
#   ./install.sh --system        install for all users into /usr/local (uses sudo)
#   ./install.sh --deps          also install the required system packages with apt (uses sudo)
#   ./install.sh --uninstall     remove an installation (add --system for the system-wide one)
#   ./install.sh --no-start      do not start the background agent after installing
#   ./install.sh --force         replace a `linscreencapture` launcher that this script did not write
#   ./install.sh --prefix DIR --destdir DIR   staging for packagers (used by packaging/build-deb.sh)
#
# Layout under PREFIX:
#   lib/linscreencapture/linscreencapture/         the Python package (with the compiled .gresource)
#   lib/linscreencapture/data/icons/hicolor/...    the application icon (the panel icon reads it)
#   bin/linscreencapture                            launcher: python3 -P -m linscreencapture
#   share/applications/com.mensuramedia.LinScreenCapture.desktop
#   share/icons/hicolor/<size>/apps/com.mensuramedia.LinScreenCapture.{png,svg}
#
# On first start the app turns on Run at startup and registers PrintScreen with Cinnamon (docs/PRINTSCREEN.md).
set -euo pipefail

APP_ID="com.mensuramedia.LinScreenCapture"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPS=(python3 python3-gi python3-gi-cairo python3-cairo python3-pil python3-numpy python3-xlib
      gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtk-3.0 gir1.2-xapp-1.0 libglib2.0-bin libgdk-pixbuf2.0-bin xclip)
BUILD_DEPS=(libglib2.0-dev-bin)

MODE=user PREFIX="" DESTDIR="" WANT_DEPS=0 UNINSTALL=0 START=1 FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --user) MODE=user ;;
    --system) MODE=system ;;
    --prefix) PREFIX="$2"; shift ;;
    --destdir) DESTDIR="$2"; shift ;;
    --deps) WANT_DEPS=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --no-start) START=0 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done
if [ -z "$PREFIX" ]; then
  if [ "$MODE" = system ]; then PREFIX=/usr/local; else PREFIX="$HOME/.local"; fi
fi
[ -n "$DESTDIR" ] && START=0

SUDO=""
if [ -z "$DESTDIR" ] && [ "$MODE" = system ] && [ "$(id -u)" -ne 0 ]; then SUDO=sudo; fi
run() { $SUDO "$@"; }

ROOT="$DESTDIR$PREFIX"
LIB="$ROOT/lib/linscreencapture"
BIN="$ROOT/bin/linscreencapture"
APPS="$ROOT/share/applications"
ICONS="$ROOT/share/icons/hicolor"
SIZES=(16 24 32 48 64 128 256 512)

refresh_caches() {
  [ -n "$DESTDIR" ] && return 0
  run gtk-update-icon-cache -q -t -f "$ICONS" 2>/dev/null || true
  run update-desktop-database -q "$APPS" 2>/dev/null || true
}

if [ "$UNINSTALL" = 1 ]; then
  echo "Removing LinScreenCapture from $PREFIX"
  if [ -z "$DESTDIR" ] && command -v gdbus >/dev/null 2>&1; then   # ask a running agent to quit
    gdbus call --session --dest "$APP_ID" --object-path /com/mensuramedia/LinScreenCapture \
      --method org.gtk.Actions.Activate quit [] {} >/dev/null 2>&1 || true
  fi
  run rm -rf "$LIB"
  run rm -f "$BIN" "$APPS/$APP_ID.desktop" "$ICONS/scalable/apps/$APP_ID.svg"
  for s in "${SIZES[@]}"; do run rm -f "$ICONS/${s}x${s}/apps/$APP_ID.png"; done
  if [ "$MODE" = user ] && [ -z "$DESTDIR" ]; then   # a staged (--destdir) uninstall never touches $HOME
    rm -f "$HOME/.config/autostart/$APP_ID.desktop"
    echo "Your settings stay in ~/.config/linscreencapture; delete that folder to remove them too."
    echo "The PrintScreen shortcut stays in Cinnamon's Custom Shortcuts until you remove it there."
  fi
  refresh_caches
  echo "Done."
  exit 0
fi

if [ "$WANT_DEPS" = 1 ]; then
  echo "Installing system packages: ${DEPS[*]} ${BUILD_DEPS[*]}"
  sudo apt-get update -q
  sudo apt-get install -y "${DEPS[@]}" "${BUILD_DEPS[@]}"
fi

# -- checks ---------------------------------------------------------------------------------------------
missing=()
python3 - <<'EOF' || missing+=(python-modules)
import sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: F401
import cairo, PIL, numpy  # noqa: F401
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is needed")
EOF
command -v glib-compile-resources >/dev/null 2>&1 || missing+=(glib-compile-resources)
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing: ${missing[*]}. Run ./install.sh --deps, or: sudo apt install ${DEPS[*]} ${BUILD_DEPS[*]}" >&2
  exit 1
fi

if [ -e "$BIN" ] && ! grep -q "installed by install.sh" "$BIN" 2>/dev/null && [ "$FORCE" != 1 ]; then
  echo "$BIN exists and was not written by this installer (a development wrapper?)." >&2
  echo "Re-run with --force to replace it, or use --prefix to install elsewhere." >&2
  exit 1
fi

# -- build ----------------------------------------------------------------------------------------------
echo "Building the resource bundle"
glib-compile-resources --target "$SRC/linscreencapture/linscreencapture.gresource" \
  --sourcedir "$SRC/data" --sourcedir "$SRC/linscreencapture/ui" "$SRC/data/linscreencapture.gresource.xml"

# -- install --------------------------------------------------------------------------------------------
echo "Installing into $ROOT"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/lib/data/icons/hicolor/scalable/apps"
(cd "$SRC" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - linscreencapture) | tar -xf - -C "$STAGE/lib"
cp "$SRC/data/icons/hicolor/scalable/apps/$APP_ID.svg" "$STAGE/lib/data/icons/hicolor/scalable/apps/"
cat > "$STAGE/launcher" <<EOF
#!/bin/sh
# LinScreenCapture launcher (installed by install.sh)
PYTHONPATH="$PREFIX/lib/linscreencapture\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHONPATH
exec python3 -P -m linscreencapture "\$@"
# -P: never import from the current directory, so starting it inside a checkout still runs the installed copy
EOF
sed -e "s|@BIN@|$PREFIX/bin/linscreencapture|g" "$SRC/data/$APP_ID.desktop" > "$STAGE/$APP_ID.desktop"

run rm -rf "$LIB"
run mkdir -p "$LIB" "$ROOT/bin" "$APPS" "$ICONS/scalable/apps"
run cp -r "$STAGE/lib/." "$LIB/"
run install -m 0755 "$STAGE/launcher" "$BIN"
run install -m 0644 "$STAGE/$APP_ID.desktop" "$APPS/$APP_ID.desktop"
run install -m 0644 "$SRC/data/icons/hicolor/scalable/apps/$APP_ID.svg" "$ICONS/scalable/apps/$APP_ID.svg"
for s in "${SIZES[@]}"; do
  run mkdir -p "$ICONS/${s}x${s}/apps"
  run install -m 0644 "$SRC/resources/icons/linscreencapture-$s.png" "$ICONS/${s}x${s}/apps/$APP_ID.png"
done
refresh_caches

echo "Installed: $PREFIX/bin/linscreencapture"
if [ -z "$DESTDIR" ] && [ "$MODE" = user ] && ! echo ":$PATH:" | grep -q ":$PREFIX/bin:"; then
  echo "Note: $PREFIX/bin is not on your PATH; the menu entry and PrintScreen use the full path and work anyway."
fi

if [ "$START" = 1 ] && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  echo "Starting the background agent (PrintScreen captures a region to the clipboard)"
  (setsid "$PREFIX/bin/linscreencapture" --background >/dev/null 2>&1 < /dev/null &) || true
fi
echo "Done. Open LinScreenCapture from the menu, or press PrintScreen. Guide: docs/PRINTSCREEN.md"
