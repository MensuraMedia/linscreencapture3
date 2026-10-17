# Known issues — LinScreenCapture 3 (3.0.0.dev)

Status as of 2026-10-16, Phases 1–5 implemented, Phase 6 in progress on `feat/background-agent`. Capture, hotkey and
clipboard behaviour: `docs/CAPTURE.md` (its §11 lists the capture limits).

| Area | Issue | Status |
| --- | --- | --- |
| Hotkey | The registrar (Settings → System → *Register with the desktop*) supports Cinnamon only; on GNOME, Xfce, MATE and KDE bind `linscreencapture --capture` by hand (`INSTALL.md`) | Phase 6 |
| Clipboard | Fixed 2026-10-16: captures put on the clipboard offered no image format on X11, so pastes in other applications were empty. The clipboard now offers `image/png` plus a texture and hands the image to the clipboard manager | fixed |
| Wayland | The portal path is untested (no Wayland session on the development machine). Only the portal backend works; it cannot list windows, so Window mode falls back to Region; the portal may show a permission dialog on each capture depending on the desktop | by design of the portal |
| Multi-monitor | The capture overlay opens one window per monitor; a selection cannot span two monitors | open |
| HiDPI | Monitor scale factors are assumed to be integers | open |
| Scrolling capture, Pin to screen | Buttons present, not implemented | Phase 6 |
| Layers | Drag-to-reorder in the Layers list is not implemented (the undo command exists) | Phase 7 |
| Select all | Ctrl+A marks every layer for Copy and Delete; the selection cannot be moved or restyled as a group | open |
| Clipboard tray | One slot for now (several slots are on the roadmap, HANDOFF §8); only copies made by LinScreenCapture appear (editor Ctrl+C, captures, Library Copy); copies from other applications are not tracked | roadmap / by design |
| Area tool | A marked area can be copied, cropped to or cleared; it cannot yet be moved, inverted or feathered | roadmap |
| Eraser | Erases the composite (base and layers beneath); it cannot be restricted to one layer | by design |
| Text | Text and callouts render upright after Rotate (their anchor moves, the glyphs do not rotate) | open |
| Tests | Under Xvfb two window-geometry tests fail (`test_window_geometry`, `test_close_saves_settings`: 1350 vs 1360 px); cosmetic, predates the background-agent branch | open |
| Tests | `make test` uses `xvfb-run` when installed (it is on the development machine); without it, tests and `make snapshot` use the live display and briefly show windows | environment |
| Dialogs | Settings, Flatten and Delete prompts open as separate small windows (the studio uses a plain GTK window for its custom title bar) | by design |
