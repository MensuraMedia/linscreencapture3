# Known issues — LinScreenCapture 3 (3.0.0.dev)

Status as of 2026-10-13, Phases 1–5 implemented. The 1.4 keybinding issues documented here before are moot:
the C hotkey registrar no longer exists; its Python port (with the GNOME append fix) is Phase 6 work.

| Area | Issue | Status |
| --- | --- | --- |
| Hotkey | PrintScreen is not registered by the app yet; bind it in the desktop's keyboard settings to `linscreencapture --capture` | Phase 6 |
| Wayland | Only the portal backend works; it cannot list windows, so Window mode falls back to Region; the portal may show a permission dialog on each capture depending on the desktop | by design of the portal |
| Multi-monitor | The capture overlay opens one window per monitor; a selection cannot span two monitors | open |
| HiDPI | Monitor scale factors are assumed to be integers | open |
| Scrolling capture, Pin to screen | Buttons present, not implemented | Phase 6 |
| Layers | Drag-to-reorder in the Layers list is not implemented (the undo command exists) | Phase 7 |
| Select all | Ctrl+A marks every layer for Copy and Delete; the selection cannot be moved or restyled as a group | open |
| Clipboard tray | One slot for now (several slots are on the roadmap, HANDOFF §8); only copies made by LinScreenCapture appear (editor Ctrl+C, captures, Library Copy); copies from other applications are not tracked | roadmap / by design |
| Area tool | A marked area can be copied, cropped to or cleared; it cannot yet be moved, inverted or feathered | roadmap |
| Eraser | Erases the composite (base and layers beneath); it cannot be restricted to one layer | by design |
| Text | Text and callouts render upright after Rotate (their anchor moves, the glyphs do not rotate) | open |
| Tests | No Xvfb on the development machine: `make test` and `make snapshot` use the live display and briefly show windows | environment |
| Dialogs | Settings, Flatten and Delete prompts open as separate small windows (the studio uses a plain GTK window for its custom title bar) | by design |
