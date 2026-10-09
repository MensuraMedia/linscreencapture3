#!/usr/bin/env bash
# Launch the development build of LinScreenCapture 2 from a menu entry.
# Rebuilds the GResource bundle when data/ or style.css changed, then runs the app.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RES="linscreencapture/linscreencapture.gresource"
if [ ! -f "$RES" ] || [ -n "$(find data linscreencapture/ui/style.css -newer "$RES" 2>/dev/null | head -1)" ]; then
  make resources >/dev/null
fi
exec python3 -m linscreencapture "$@"
