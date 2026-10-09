# LinScreenCapture 2 — implemented features and functions

As of 2026-10-09 (Phases 1–4 plus two review rounds). Everything listed here exists in the code and is covered by
`make test` (69 tests) or a render in `screenshots/dev/`. Planned work is in `HANDOFF.md` section 3.

## 1. Launching

| Function | How | Module |
| --- | --- | --- |
| Start the studio | `python3 -m linscreencapture`, the `linscreencapture` script, or the **LinScreenCapture3** menu entry (`make launcher`) | `__main__.py`, `tools/launch.sh` |
| Capture immediately | `linscreencapture --capture` (`-c`): a second instance forwards to the running one over D-Bus; at first start the window stays hidden until the capture is done | `app/application.py` |
| Diagnostics | `--debug` (`-d`) or `LSC_DEBUG=1`: timestamped log of versions (Python, PyGObject, GTK, libadwaita), session, resources and icon count, stylesheet, settings file and values, backend order, action counts, window build time, every capture step; GTK/GLib messages routed into the same stream under `toolkit` | `app/logging_setup.py` |
| Single instance | `Adw.Application` id `com.mensuramedia.LinScreenCapture`; a second launch raises the window | `app/application.py` |
| Window memory | size, maximised state and rail state are saved on close and restored | `model/settings.py`, `ui/studio_window.py` |

## 2. Window and chrome

| Function | Behaviour |
| --- | --- |
| Title bar | the 52 px Graphite header is the title bar (CSD): drag moves, double-click maximises, window buttons follow the system layout |
| Header contents | title block (document name + `Edit · W×H · FORMAT · n layers · saved/unsaved` once a document exists), the tool-properties strip in the centre, window controls |
| Rails | left 220 px open / 56 px collapsed, right the same; **collapsed by default**; carets are single chevrons pointing the way the rail moves |
| Auto-collapse | below 1100 px window width both rails collapse; when the window widens they return to the state they had before (manual toggles in the session win) |
| Minimum size | 960×600 |
| Toasts | bottom-centre messages for saves, copies, errors and placeholders ("… arrives in Phase N") |

## 3. Left rail

| Row | Controls | Actions |
| --- | --- | --- |
| Top | Capture (30 px accent icon) + collapse caret | `app.capture` (current mode) |
| CAPTURE | Region · Window · Full screen · Scrolling · Delayed · Pin | `win.capture-mode` (stateful: region, window, screen, scrolling, delayed); Pin = `app.pin` (Phase 6) |
| TOOLS | Select · Arrow · Line · Box · Circle · Text · Pen · Marker | `win.tool::<name>` (stateful) |
| second row | Blur · Pixelate · Fill · Step number · Callout · Crop · Resize · Rotate · Brightness · Move · Duplicate | tools via `win.tool`; Resize/Rotate/Brightness/Duplicate = Phase 5 placeholders |
| above the line | Library (toggle) | `win.library` |
| ACTIONS | Discard · Save | `win.discard` (clears the stage), `win.save` (Phase 5) |
| collapsed | caret, Capture, Region/Full screen/Delayed, seven tools (the active one always present), Library, Discard, Save | same actions |

## 4. Header tool-properties strip (`ui/tool_props.py`)

Follows the active tool, and under Select/Move the **selected layer** (title reads `BOX · SELECTED`). Arrow/Line:
width, shadow, intensity. Box/Circle: + fill. Pen/Marker: width, shadow (marker paints at 4× width, 40 %
opacity). Text/Callout: font, size, bold, italic, shadow. Step: badge size. Blur/Pixelate: mode (switches the
tool), block size. Fill, Crop, Select/Move without a selection: hints.

Every control reads from and writes to `Settings` (`tools[<tool>].width/shadow/shadow_intensity/fill`,
`text_font_family/size/bold/italic`, `step_size`, `blur_block`; saved on change; the Universal switch in Settings
makes a change apply to every tool). With a layer selected the change is also applied to that annotation as an
undoable "Style" edit.

## 5. Right rail

| Group | Controls | Actions |
| --- | --- | --- |
| COLOUR | 12 round swatches (accent ring = current), custom colour `+` (`Gtk.ColorDialog`), eyedropper | sets the colour for new annotations, recolours the selected layer, persists to settings; `win.eyedropper` arrives with Phase 5 |
| VIEW | zoom out · value · zoom in · fit | `win.zoom-out`, `win.zoom-in`, `win.zoom-fit` (fit never exceeds 1:1); `win.zoom-actual` = 1:1 |
| EDIT | Copy · Flatten | `win.copy` (composition to clipboard), `win.flatten` (Phase 5) |
| LAYERS | scrollable list: annotation layers top-first with a rendered 40×28 thumbnail, name, kind badge and eye; then `Base capture · IMG`; "No layers yet" when empty | row click selects the layer on the stage (and vice versa); eye = undoable show/hide |
| navigator (untitled) | thumbnail of the composite, dimmed outside the viewport, accent viewport rectangle that follows zoom and scroll; click or drag scrolls the stage | `ui/panel_rail.py::Navigator` |
| bottom-right | Settings | `app.preferences` |
| collapsed | caret, six colour dots, eyedropper, −, +, fit, Copy, Flatten, gear | same actions |

## 6. Stage

| State | Behaviour |
| --- | --- |
| Empty | camera glyph, "Press PrintScreen or click Capture", mode list, shortcut chips; HUD shows `—` |
| Document | the capture painted pixel-exact with square corners (shadow outside), centred, scrollable when larger than the viewport; HUD shows the zoom |
| Zoom | steps 25 · 50 · 75 · 100 · 150 · 200 · 300 · 400 · 800 · 1000 %; Ctrl+scroll; Ctrl+0 fit; Ctrl+1 1:1; a loaded document fits automatically |
| Library page | covers the stage: head (count · folder, Refresh, Delete, Open, close), grid of 180×120 thumbnails with name and date, empty state; double-click or Open loads the file into the editor; Delete = Phase 5 |

## 6a. Annotation editing (`app/editor_controller.py`, `app/tools.py`)

| Tool | Gesture | Result |
| --- | --- | --- |
| Arrow, Line | drag (Shift snaps to 45°) | filled arrow / round-capped line layer |
| Box, Circle | drag (Ctrl constrains to a square/circle); Fill switch in the strip | outlined or filled shape |
| Fill | drag | filled rectangle in the current colour |
| Pen, Marker | drag | stroke of the pointer path (sub-pixel jitter dropped); marker 4× width at 40 % |
| Text | click, type in the inline editor, Enter (Esc cancels) | text layer; double-click a text/callout layer under Select to edit it |
| Callout | drag from the bubble position to the target, type, Enter | bubble with tail |
| Step number | click | numbered badge; numbers renumber on delete/reorder |
| Blur, Pixelate | drag | redaction layer applied to the pixels beneath (dashed preview while dragging) |
| Crop | drag | preview only; applies in Phase 5 |
| Select / Move | click selects the topmost layer under the pointer; drag moves; handles resize (8 for shapes, 2 for arrows/lines/callouts; Ctrl keeps shapes square); Delete removes; Ctrl+D duplicates 12 px offset | undoable edits |

Live preview at 60 % opacity while drawing; a dashed accent outline and white handles mark the selection; the
cursor changes per handle. Every change is one `UndoStack` command: Ctrl+Z / Ctrl+Shift+Z (or Ctrl+Y) undo and
redo (20 deep) and the Undo toast names the step; the subtitle's layer count and `unsaved` follow.

## 7. Capture (`app/capture_controller.py`)

1. The studio hides; the compositor gets 300 ms (plus the delay for Delayed mode) to repaint.
2. The screen is frozen by the first working backend (`services/capture_service.py`): on X11 sessions x11 → portal
   → cli, on Wayland portal → x11 → cli, or the one chosen in Settings; each is tried once and the last error is
   reported in a toast.
3. Full screen: done. Region/Window: the overlay opens on every monitor (`ui/capture_overlay.py`).
4. The region is cropped, saved to the save folder as the next name, copied to the clipboard (if enabled), loaded
   into the editor, and announced in a toast.

| Backend | Mechanism | Window list |
| --- | --- | --- |
| `x11` | python-xlib root `GetImage`, one numpy copy BGRX → ARGB32 | `_NET_CLIENT_LIST_STACKING` + `_NET_FRAME_EXTENTS`, topmost first, docks/desktop skipped |
| `portal` | `org.freedesktop.portal.Screenshot` (async Response signal), temp file loaded and deleted | none (window mode falls back to region) |
| `cli` | `gnome-screenshot -f`, `grim`, `import -window root`, `spectacle -b -n -f -o` | none |

### Overlay

| Function | Keys / mouse |
| --- | --- |
| Select a region | drag; **Shift** constrains to a square; **Space** while dragging moves the box |
| Adjust (handles style) | 8 handles resize, drag inside moves, arrows nudge 1 px, Shift+arrows 10 px, Ctrl+A selects all |
| Confirm / cancel | **Enter** or double-click inside; **Esc** |
| Simple style (Settings → Selection box) | the capture happens on mouse release; no handles, no Enter |
| Window mode | hovering highlights the window under the pointer (title chip); click captures it with its frame |
| Mode bar | Region · Window · Full screen toggles at the top; key hints beside them |
| Readouts | size chip under the box (`W × H`), pointer position and colour under the pointer bottom-left |
| Multi-monitor | one overlay window per monitor; a selection cannot span monitors; HiDPI scale factors handled per monitor |

## 8. Settings (`model/settings.py`, dialog `ui/preferences.py`)

File `~/.config/linscreencapture/settings.conf`, groups `[Window] [Capture] [System] [Tools]`; a 1.4 file at
`~/.config/linshot/settings.conf` is migrated once on first run (every key, `rgb()` colours, prefix/numbering
derived from `filename_format`) and left untouched; `[Meta] migrated_from` records it.

| Dialog row (Capture page) | Key | Values |
| --- | --- | --- |
| Save folder (picker) | `screenshot_path` | any folder |
| File name prefix | `prefix` | `LinScreenCapture_`, `Screenshot_` |
| Numbering | `numbering` | `sequence` (`_1`, `_2`, …, first free number) · `timestamp` (`_2026-10-09_21-14-05`) |
| Format | `format` (+ `jpeg_quality`) | png · jpeg · webp |
| Selection box | `selection_style` | `handles` · `simple` |
| Copy to clipboard | `copy_to_clipboard` | bool |
| Delayed capture | `delay_seconds` | 0–60 |
| Start with the left/right rail collapsed | `left_collapsed`, `right_collapsed` | bool (apply live) |

Not yet in the dialog (keys exist): `backend`, `include_pointer`, `pin_opacity`, `reopen_last`, `[System]`
autostart/hotkey/register_hotkey, `[Tools]` per-tool colour/width/shadow/intensity, universal, blur block/radius,
text font/size/bold/italic. `Settings.tool_style(tool)` builds a drawing `Style`; `next_filename()` applies the
naming rules.

## 9. Model (`model/`, pure Python, headless-tested)

| Module | Provides |
| --- | --- |
| `annotations.py` | `Style`, `Annotation` (kinds arrow, line, box, circle, text, pen, marker, step, callout, fill, blur, pixelate), Cairo painters ported from 1.4, three-pass shadows, pixelate (numpy) and blur (Pillow) on the composite, `snap45`, `constrain_square`, bounding boxes, hit test, dict round-trip, `renumber_steps` |
| `document.py` | `Document` (base surface, `Layer` list with ids/badges/visibility, dirty flag, `summary()`), `open()`/`save()` PNG/JPEG/WebP, `flatten()`, `flatten_into_base()`, exact PIL↔cairo conversion |
| `undo.py` | `UndoStack` (20 deep, redo, labels, on_change) with `AddLayer`, `RemoveLayer`, `MoveLayer`, `EditAnnotation`, `SetVisible`, `ReplaceBase` |
| `captures_index.py` | threaded thumbnail scan of the save folder → `Gio.ListStore`, newest first |
| `settings.py` | schema, validation, migration, naming |

## 10. Keyboard shortcuts

| Keys | Action |
| --- | --- |
| PrintScreen (system binding, Phase 6) · Ctrl+N | capture in the current mode |
| Ctrl+Shift+N | full-screen capture |
| V A L B C T P M · U X N K | tools (Select, Arrow, Line, Box, Circle, Text, Pen, Marker · Blur, Pixelate, Step, Crop) |
| Ctrl+C | copy the composition |
| Ctrl+Z · Ctrl+Shift+Z / Ctrl+Y · Delete · Ctrl+D | undo · redo · delete layer · duplicate layer |
| Ctrl+S | save (Phase 5) |
| Ctrl+scroll · Ctrl+0 · Ctrl+1 | zoom · fit · 1:1 |
| Ctrl+[ · Ctrl+] | collapse/expand left · right rail |
| Ctrl+L | Library page |
| Ctrl+, | Settings |
| Ctrl+Q | quit |

## 11. Developer tools

| Command | Purpose |
| --- | --- |
| `make resources` | compile `data/` + `style.css` into the GResource bundle |
| `make icons` | re-sync the 53 Phosphor glyphs from `ICON_SRC` and regenerate the manifest |
| `make test` | pytest (Xvfb if installed, else the live display) |
| `make snapshot` | render default, open, collapsed, library, text-tool, document, zoomed and settings views to `screenshots/dev/` |
| `make snapshot` also writes | `shell_annotated.png`: seven annotation kinds, a selected box with handles |
| `tools/snapshot_overlay.py` | render the live capture overlay (output git-ignored: it contains the real screen) |
| `make launcher` / `make unlauncher` | install/remove the **LinScreenCapture3** menu entry |
| `bash ~/projects/Zai-ZCode/s009_backup_project.sh …` | family backup into `~/backups/linscreencapture3/` |
