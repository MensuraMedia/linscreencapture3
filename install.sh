#!/bin/bash
# LinScreenCapture Quick Installer
# Usage: curl -sL <raw-url> | bash  OR  bash install.sh
set -e

echo ""
echo "  LinScreenCapture — Screenshot & Annotation Tool for Linux"
echo "  ================================================="
echo ""

# Check we're on a Debian-based system
if ! command -v apt &>/dev/null; then
    echo "ERROR: This installer requires a Debian-based system (apt package manager)."
    exit 1
fi

# Check for X11
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo "WARNING: LinScreenCapture is optimized for X11. Wayland support is limited."
    echo "         Continuing anyway..."
    echo ""
fi

REPO_URL="https://github.com/MensuraMedia/linscreencapture.git"
INSTALL_DIR="$HOME/.local/share/linscreencapture"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"

echo "[1/5] Installing build dependencies..."
sudo apt update -qq
sudo apt install -y -qq cmake build-essential libgtk-3-dev libx11-dev libcairo2-dev git xclip >/dev/null 2>&1
echo "      Done."

echo "[2/5] Downloading LinScreenCapture..."
rm -rf "$INSTALL_DIR"
git clone --depth 1 -q "$REPO_URL" "$INSTALL_DIR"
echo "      Done."

echo "[3/5] Building..."
mkdir -p "$INSTALL_DIR/build"
cd "$INSTALL_DIR/build"
cmake -DCMAKE_BUILD_TYPE=Release .. -Wno-dev >/dev/null 2>&1
make -j"$(nproc)" >/dev/null 2>&1
echo "      Done."

echo "[4/5] Installing..."
mkdir -p "$BIN_DIR" "$APP_DIR"

# Symlink binary
ln -sf "$INSTALL_DIR/build/linscreencapture" "$BIN_DIR/linscreencapture"

# Desktop entry
cat > "$APP_DIR/linscreencapture.desktop" << EOF
[Desktop Entry]
Version=1.4
Type=Application
Name=LinScreenCapture
GenericName=Screenshot Tool
Comment=Capture, annotate, and share screenshots
Exec=$BIN_DIR/linscreencapture
Icon=$INSTALL_DIR/resources/icons/linscreencapture-128.png
Terminal=false
Categories=Utility;Graphics;GTK;
Keywords=screenshot;capture;screen;annotation;
StartupNotify=true

[Desktop Action capture]
Name=Capture Screenshot
Exec=$BIN_DIR/linscreencapture --capture
EOF

update-desktop-database "$APP_DIR" 2>/dev/null || true
echo "      Done."

# Ensure ~/.local/bin is on PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC=""
    if [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
    fi
    if [ -n "$SHELL_RC" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    fi
    export PATH="$BIN_DIR:$PATH"
fi

echo "[5/5] Detecting desktop environment..."
DE="${XDG_CURRENT_DESKTOP:-unknown}"
echo "      Detected: $DE"
echo ""

echo "  ================================================="
echo "  LinScreenCapture installed successfully!"
echo "  ================================================="
echo ""
echo "  Launch:           linscreencapture"
echo "  Capture shortcut: linscreencapture --capture"
echo "  Uninstall:        bash $INSTALL_DIR/uninstall.sh"
echo ""

case "${DE,,}" in
    *cinnamon*)
        echo "  Keybinding (Cinnamon):"
        echo "    Open LinScreenCapture → Settings → check 'Set as default screenshot app'"
        echo "    PrintScreen will work immediately."
        ;;
    *gnome*|*ubuntu*)
        echo "  Keybinding (GNOME):"
        echo "    Settings → Keyboard → Custom Shortcuts → Add:"
        echo "      Name: LinScreenCapture"
        echo "      Command: $BIN_DIR/linscreencapture --capture"
        echo "      Key: PrintScreen"
        ;;
    *xfce*)
        echo "  Keybinding (XFCE):"
        echo "    Settings → Keyboard → Application Shortcuts"
        echo "    Remove xfce4-screenshooter from PrintScreen, then add:"
        echo "      $BIN_DIR/linscreencapture --capture"
        ;;
    *mate*)
        echo "  Keybinding (MATE):"
        echo "    Control Center → Keyboard Shortcuts"
        echo "    Add custom: $BIN_DIR/linscreencapture --capture → PrintScreen"
        ;;
    *kde*|*plasma*)
        echo "  Keybinding (KDE):"
        echo "    System Settings → Shortcuts → Custom Shortcuts → Add:"
        echo "      Command: $BIN_DIR/linscreencapture --capture"
        echo "      Key: PrintScreen (disable Spectacle first)"
        ;;
    *)
        echo "  Keybinding:"
        echo "    Add a keyboard shortcut in your DE settings for:"
        echo "      $BIN_DIR/linscreencapture --capture"
        ;;
esac

echo ""
