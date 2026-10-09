#!/bin/bash
set -e

VERSION="1.0.0"
ARCH=$(dpkg --print-architecture)
PKG_NAME="linscreencapture_${VERSION}_${ARCH}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build"
PKG_DIR="$BUILD_DIR/$PKG_NAME"

echo "=== Building LinScreenCapture v${VERSION} .deb package ==="
echo "Architecture: $ARCH"
echo "Project dir:  $PROJECT_DIR"

# Build the binary
echo ""
echo "--- Compiling ---"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
cmake -DCMAKE_BUILD_TYPE=Release "$PROJECT_DIR"
make -j$(nproc)

# Create package directory structure
echo ""
echo "--- Creating package structure ---"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/doc/linscreencapture"

# Install binary
cp "$BUILD_DIR/linscreencapture" "$PKG_DIR/usr/bin/linscreencapture"
chmod 755 "$PKG_DIR/usr/bin/linscreencapture"

# Install .desktop file
cp "$PROJECT_DIR/packaging/linscreencapture.desktop" "$PKG_DIR/usr/share/applications/"

# Install icons at standard sizes
for size in 16 24 32 48 64 128 256; do
    icon_dir="$PKG_DIR/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$icon_dir"
    cp "$PROJECT_DIR/resources/icons/linscreencapture-${size}.png" "$icon_dir/linscreencapture.png"
done

# Install documentation
cp "$PROJECT_DIR/LICENSE" "$PKG_DIR/usr/share/doc/linscreencapture/"
cp "$PROJECT_DIR/README.md" "$PKG_DIR/usr/share/doc/linscreencapture/"

# Calculate installed size (in KB)
INSTALLED_SIZE=$(du -sk "$PKG_DIR" | cut -f1)

# Get dependencies from the compiled binary
DEPENDS=$(dpkg-shlibdeps -O "$PKG_DIR/usr/bin/linscreencapture" 2>/dev/null | sed 's/shlibs:Depends=//' || echo "libgtk-3-0, libx11-6, libcairo2")
if [ -z "$DEPENDS" ]; then
    DEPENDS="libgtk-3-0, libx11-6, libcairo2"
fi

# Create DEBIAN/control
cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: linscreencapture
Version: ${VERSION}
Section: graphics
Priority: optional
Architecture: ${ARCH}
Depends: ${DEPENDS}
Recommends: xdg-utils, xclip
Installed-Size: ${INSTALLED_SIZE}
Maintainer: MensuraMedia <mensuramedia@gmail.com>
Homepage: https://github.com/MensuraMedia/linscreencapture
Description: Modern screenshot tool for Linux with annotation support
 LinScreenCapture is a lightweight screenshot tool for Linux desktops that provides
 area capture with real-time visual feedback, annotation tools (arrows,
 rectangles, circles, text, freehand drawing), screenshot history,
 automatic clipboard copy, and system tray integration.
 .
 Features include configurable keyboard shortcuts, auto-save with
 customizable filename formats, and the ability to register as the
 default screenshot application.
EOF

# Create DEBIAN/postinst
cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/postinst"

# Create DEBIAN/postrm
cat > "$PKG_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database /usr/share/applications 2>/dev/null || true
    if [ "$1" = "purge" ]; then
        rm -f /tmp/linscreencapture.lock /tmp/linscreencapture.capture
    fi
fi
exit 0
EOF
chmod 755 "$PKG_DIR/DEBIAN/postrm"

# Build the .deb
echo ""
echo "--- Building .deb ---"
dpkg-deb --build --root-owner-group "$PKG_DIR"

# Move to project root
mv "$BUILD_DIR/${PKG_NAME}.deb" "$PROJECT_DIR/${PKG_NAME}.deb"

echo ""
echo "=== Package built successfully ==="
echo "Output: $PROJECT_DIR/${PKG_NAME}.deb"
echo ""
echo "Install with:   sudo dpkg -i ${PKG_NAME}.deb"
echo "Uninstall with: sudo apt remove linscreencapture"
echo ""

# Show package info
dpkg-deb --info "$PROJECT_DIR/${PKG_NAME}.deb"
