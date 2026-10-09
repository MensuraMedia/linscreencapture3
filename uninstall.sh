#!/bin/bash
# LinScreenCapture Uninstaller
set -e

INSTALL_DIR="$HOME/.local/share/linscreencapture"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"

echo ""
echo "  Uninstalling LinScreenCapture..."
echo ""

rm -f "$BIN_DIR/linscreencapture"
rm -f "$APP_DIR/linscreencapture.desktop"
rm -rf "$INSTALL_DIR"
update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "  LinScreenCapture removed."
echo ""

read -rp "  Remove settings too? (~/.config/linscreencapture) [y/N] " answer
if [[ "${answer,,}" == "y" ]]; then
    rm -rf "$HOME/.config/linscreencapture"
    echo "  Settings removed."
fi

echo "  Done."
echo ""
