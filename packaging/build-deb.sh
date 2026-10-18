#!/usr/bin/env bash
# Build the LinScreenCapture .deb (Debian, Ubuntu, Linux Mint):
#
#   packaging/build-deb.sh            → packaging/linscreencapture_<version>_all.deb
#   sudo apt install ./packaging/linscreencapture_<version>_all.deb
#
# The package is laid out by ./install.sh --prefix /usr --destdir <stage>, so the .deb and the script install the
# same files. Needs dpkg-deb, glib-compile-resources and the app's own runtime packages (to compile the resources).
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$SRC/packaging}"
APP_ID="com.mensuramedia.LinScreenCapture"

PYVER="$(sed -n 's/^version = "\(.*\)"/\1/p' "$SRC/pyproject.toml")"
VERSION="$(echo "$PYVER" | sed -E 's/\.?(dev|a|b|rc)([0-9]*)$/~\1\2/')"   # 3.0.0.dev1 → 3.0.0~dev1
PKG="linscreencapture_${VERSION}_all"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOTFS="$STAGE/$PKG"

"$SRC/install.sh" --prefix /usr --destdir "$ROOTFS" --no-start --force >/dev/null
find "$ROOTFS" -name '__pycache__' -prune -exec rm -rf {} +

mkdir -p "$ROOTFS/usr/share/doc/linscreencapture" "$ROOTFS/DEBIAN"
for f in README.md INSTALL.md docs/PRINTSCREEN.md docs/CAPTURE.md; do
  install -m 0644 "$SRC/$f" "$ROOTFS/usr/share/doc/linscreencapture/"
done
cat > "$ROOTFS/usr/share/doc/linscreencapture/copyright" <<COPY
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: LinScreenCapture
Source: https://github.com/MensuraMedia/linscreencapture3

Files: *
Copyright: MensuraMedia
License: CC-BY-NC-4.0
 See LICENSE.md in the source repository.

Files: data/icons/scalable/actions/*
Copyright: Phosphor Icons
License: MIT
COPY

SIZE="$(du -sk "$ROOTFS/usr" | cut -f1)"
cat > "$ROOTFS/DEBIAN/control" <<CTRL
Package: linscreencapture
Version: $VERSION
Section: graphics
Priority: optional
Architecture: all
Maintainer: MensuraMedia <noreply@github.com>
Installed-Size: $SIZE
Depends: python3 (>= 3.11), python3-gi (>= 3.46), python3-gi-cairo, python3-cairo, python3-pil, python3-numpy,
 gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1 (>= 1.4), gir1.2-pango-1.0
Recommends: python3-xlib, gir1.2-gtk-3.0, gir1.2-xapp-1.0 | gir1.2-ayatanaappindicator3-0.1, xclip | wl-clipboard,
 xdg-desktop-portal
Suggests: fonts-ubuntu
Homepage: https://github.com/MensuraMedia/linscreencapture3
Description: screenshot studio: PrintScreen copies a region to the clipboard
 LinScreenCapture runs as a small background agent. PrintScreen freezes the
 screen; drag a box and the capture is on the clipboard (lossless PNG) the
 moment the mouse is released, saved to the screenshot folder and loaded into
 the editor. The editor annotates (arrows, boxes, text, steps, blur, ...),
 crops, resizes and pastes images as resizable layers. An orange panel icon
 opens the editor on a double-click. Hotkey registration is automatic on
 Cinnamon (Linux Mint); any key can be chosen in Settings.
CTRL

cat > "$ROOTFS/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
  update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
POST
cat > "$ROOTFS/DEBIAN/postrm" <<'POST'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
  update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
POST
chmod 0755 "$ROOTFS/DEBIAN/postinst" "$ROOTFS/DEBIAN/postrm"

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$ROOTFS" "$OUT/$PKG.deb" >/dev/null
echo "$OUT/$PKG.deb"
