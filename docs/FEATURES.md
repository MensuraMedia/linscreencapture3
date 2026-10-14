# LinScreenCapture 3 — implemented features and functions

As of 2026-10-13 (Phases 1–5 plus two review rounds). Everything listed here exists in the code and is covered by
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
| CAPTURE | Region · Window · Full screen · Scrolling · Delayed · Pin | `win.capture-mode` (stateful: region, window, screen, scrolling); **Delayed is a toggle** (`win.capture-delayed`, boolean): on, the next captures in any mode wait `delay_seconds`; click the timer again to turn it off (a toast confirms each state); Pin = `app.pin` (Phase 6) |
| TOOLS | Select · Arrow · Line · Box · Circle · Text · Pen · Marker · **Eraser** · **Hand** | `win.tool::<name>` (stateful); every tool tooltip shows its shortcut letter under the caption |
| second row | **Box area · Round area · Point chain** · Blur · Pixelate · Fill · Step number · Callout · Crop · Resize · Rotate · Brightness · Move · Duplicate | tools via `win.tool`; the three Area tools mark a region (see §6a); Duplicate = Phase 7 placeholder |
| CLIPBOARD | a navigator-sized tray (116 px) with **one slot**: the last copy the app made (accent border while it is on the clipboard); hovering shows label · size · time, a click opens a preview popover (≤ 320×200 sample, caption, then Copy · Paste · Delete centred below). More slots are on the roadmap (HANDOFF §8) — `ClipHistory.limit` / `clip_tray.SLOTS` already parametrise it | `ui/clip_tray.py` + `services/clip_history.py`; Copy puts the sample back on the clipboard, Paste adds it as a layer (or a new image), Delete drops it from the tray and clears the clipboard if it held that copy |
| above the line | Library (toggle) | `win.library` |
| ACTIONS | Discard · Save | `win.discard` (clears the stage), `win.save` (Phase 5) |
| collapsed | caret, Capture, Region/Full screen/Delayed, seven tools (the active one always present), a clipboard button whose popover holds the same tray, Library, Discard, Save | same actions |

## 4. Header tool-properties strip (`ui/tool_props.py`)

Follows the active tool, and under Select/Move the **selected layer** (title reads `BOX · SELECTED`). Arrow/Line:
width, shadow, intensity, opacity. Box/Circle: + fill. Pen/Marker: width, shadow, opacity (marker paints at 4×
width; its opacity defaults to 0.40). Text/Callout: font, size, bold, italic, shadow, opacity. Step: badge size,
opacity. Fill: opacity. Blur/Pixelate: mode (switches the tool), block size. Crop, Select/Move without a
selection: hints. **Opacity** (0.05–1.00) applies to the whole annotation as one group, so a translucent filled
box shows no darker rim where stroke and fill overlap; it is per tool even when Universal is on.

Keyboard focus never stays in the strip: switches, toggles and scales do not take focus on click, a tool switch
hands focus back to the canvas, and Enter in a spin does the same (otherwise the spin's text field would swallow
Ctrl+Z and tool letters — see section 10).

Every control reads from and writes to `Settings` (`tools[<tool>].width/shadow/shadow_intensity/opacity/fill`,
`text_font_family/size/bold/italic`, `step_size`, `blur_block`; saved on change; the Universal switch in Settings
makes a change apply to every tool). With a layer selected the change is also applied to that annotation as an
undoable "Style" edit.

## 5. Right rail

| Group | Controls | Actions |
| --- | --- | --- |
| COLOUR | 12 round swatches (accent ring = current), custom colour `+` (`Gtk.ColorDialog`), eyedropper | sets the colour for new annotations, recolours the selected layer, persists to settings; `win.eyedropper` arrives with Phase 5 |
| VIEW | zoom out · value · zoom in · fit | `win.zoom-out`, `win.zoom-in`, `win.zoom-fit` (fit never exceeds 1:1); `win.zoom-actual` = 1:1 |
| EDIT | Copy · Flatten | `win.copy` (flattened composition to the clipboard and the tray), `win.flatten` |
| LAYERS | scrollable list: annotation layers top-first with a rendered 40×28 thumbnail, a **number** (stack position, 1 = bottom), a label naming the **tool that made it** (`ARROW`, `BOX`, `BLUR`, `PIXELATE`, `TEXT`, `STEP`, `CALLOUT`, `IMAGE`…) and an eye; then `Base capture · IMG`; "No layers yet" when empty | row click selects the layer on the stage (and vice versa); eye = undoable show/hide |
| navigator (untitled) | thumbnail of the composite, dimmed outside the viewport, accent viewport rectangle that follows zoom and scroll; click or drag scrolls the stage | `ui/panel_rail.py::Navigator` |
| bottom-right | Settings | `app.preferences` |
| collapsed | caret, six colour dots, eyedropper, −, +, fit, Copy, Flatten, gear | same actions |

## 6. Stage

| State | Behaviour |
| --- | --- |
| Empty | camera glyph, "Press PrintScreen or click Capture", mode list, shortcut chips; HUD shows `—` |
| Document | the capture painted pixel-exact with square corners, centred, scrollable when larger than the viewport, over a muted 8 px checkerboard that shows through transparent pixels (clear PNGs, eraser strokes); a smooth gradient drop shadow (linear on the sides, radial on the corners, 18 px) sits outside the image; HUD shows the zoom |
| Panning | Hand tool (H) drag · Space held + drag · middle-button drag anywhere on the stage; the navigator still works | `Stage.scroll_by`, editor mode `pan` |
| Zoom | steps 25 · 50 · 75 · 100 · 150 · 200 · 300 · 400 · 800 · 1000 %; Ctrl+scroll; Ctrl+0 fit; Ctrl+1 1:1; a loaded document fits automatically |
| Library page | covers the stage: head (count · folder or "n of m selected", Refresh, Select all, Copy, Duplicate, Delete, Open, close), grid of 180×120 thumbnails with name and date, empty state; **group selection** (click, Ctrl+click, Shift+click, Ctrl+A); **double-click** (or Enter / Open) loads that file into the editor; Copy (Ctrl+C) puts one image + its file on the clipboard (several: the files, for a file manager); Duplicate (Ctrl+D) writes `name copy.png`, `name copy 2.png`…; Delete moves the selection to the trash after one confirmation; all three touch only the library, never the open document |

## 6a. Annotation editing (`app/editor_controller.py`, `app/tools.py`)

| Tool | Gesture | Result |
| --- | --- | --- |
| Arrow, Line | drag (Shift snaps to 45°) | filled arrow / round-capped line layer |
| Box, Circle | drag (Ctrl constrains to a square/circle); Fill switch in the strip | outlined or filled shape |
| Fill | drag | filled rectangle in the current colour |
| Pen, Marker | drag | stroke of the pointer path (sub-pixel jitter dropped); marker 4× width at 40 % |
| Eraser (E) | drag | a stroke that clears what lies beneath to transparent (`OPERATOR_DEST_OUT`; the Opacity slider sets the erase strength); default width 24 px; shown as a translucent band while dragging and in thumbnails; PNG keeps the transparency, JPEG lands it on white |
| Hand (H) | drag | pans the view (no layer); Space held does the same with any tool, as does a middle-button drag |
| **Area** — Box area (R), Round area (O) | drag (Shift keeps it square / round) | marks a region: dashed accent outline with a faint fill. While an area is marked: **Ctrl+C** copies just that region (outside the shape transparent; also in the tray), **Enter** crops to it (`image_ops.crop_masked`: bounding box, pixels outside a round/chain area cleared), **Delete** clears it to transparent (a `CUTOUT` layer, undoable), **Esc** / a tool switch drops it |
| **Area** — Point chain (J) | click points; each click joins a line from the previous point; click the first point (within 9 px) or double-click to close; Backspace removes the last point; Esc cancels | the enclosed polygon becomes the marked area (same Ctrl+C / Enter / Delete as above) |
| Text | click, type in the inline editor, Enter (Esc cancels) | text layer; double-click a text/callout layer under Select to edit it |
| Callout | drag from the bubble position to the target, type, Enter | bubble with tail |
| Step number | click | numbered badge; numbers renumber on delete/reorder |
| Blur, Pixelate | drag | redaction layer applied to the pixels beneath (dashed preview while dragging) |
| Crop | drag, then Enter / Apply crop (Esc or Cancel abandons) | the base is cropped and every layer moves with it; a veil shows the pending crop |
| Select / Move | click selects the topmost layer under the pointer; drag moves; handles resize (8 for shapes and pasted images, 2 for arrows/lines/callouts; Ctrl keeps shapes square); Delete removes; Ctrl+D duplicates 12 px offset | undoable edits |
| Select all (Ctrl+A) | — | marks every layer (dashed outline around the image and each layer, Select tool active); Ctrl+C then copies the flattened image with every edit; Delete removes all layers as one undo step; Escape, a plain selection or a click on the empty stage ends it |
| Eyedropper (right rail) | click the image | the composite pixel under the pointer becomes the current colour |
| Copy (Ctrl+C) | — | the flattened composition goes to the system clipboard and to the left rail's clipboard tray; if a layer is selected it is also remembered for Ctrl+V (until the clipboard changes elsewhere) |
| Paste (Ctrl+V) | a layer copied in the app · an image on the clipboard · text on the clipboard | layer: a copy 12 px offset (repeated pastes cascade) · image: with a document open an `image` layer centred and selected (scaled down to fit), with none a new Untitled document · text (from a document, a web page…): a `text` layer in the Text tool's style centred on the image, Select tool active; clipboard images are detected by GType (local `Gdk.Texture` subclasses) or `image/*` MIME types |
| Click on the empty stage | a click (not a drag) outside the image, in the canvas margin or beyond it | drops the active tool back to Select, clears the selection and any pending text entry; the zoom pill overlay is not "empty stage" |

Live preview at 60 % opacity (or the tool's own opacity if lower) while drawing; a dashed accent outline and white handles mark the selection; the
cursor changes per handle. Every change is one `UndoStack` command: Ctrl+Z / Ctrl+Shift+Z (or Ctrl+Y) undo and
redo (20 deep) and the Undo toast names the step; the subtitle's layer count and `unsaved` follow.

## 6b. Image operations and file flows (`app/image_ops.py`, `ui/popovers.py`, `ui/studio_window.py`)

| Function | Where | Behaviour |
| --- | --- | --- |
| Resize | Resize button → popover | width, height, percent, keep-ratio; Apply scales the base (Lanczos) and every layer's coordinates |
| Rotate / Flip | Rotate button → popover | 90° CW, 90° CCW, 180°, flip H, flip V; layers follow |
| Brightness | Brightness button → popover | brightness and contrast −100…100, grayscale, invert, **live preview** on the stage; Apply commits, Cancel or closing restores |
| Flatten | right rail `EDIT` | confirmation, then all layers merge into the base (one undo step) |
| Save / Save As | Ctrl+S / Ctrl+Shift+S | in place when the document has a file; otherwise a file dialog seeded with the save folder and the next name; format by extension (PNG, JPEG with the configured quality, WebP) |
| Unsaved changes | Discard, Library Open | a Save / Discard / Cancel prompt when the document is dirty |
| Library Delete | Library page | moves the file to the trash after confirmation, then rescans |
| Undo | all of the above | crop, resize, rotate, flip and adjust are `TransformBase` commands that also restore layer positions |

## 7. Capture (`app/capture_controller.py`)

1. The studio hides; the compositor gets 300 ms (plus `delay_seconds` while the Delayed toggle is on — it starts off on every launch, the mode starts as Region) to repaint.
2. The screen is frozen by the first working backend (`services/capture_service.py`): on X11 sessions x11 → portal
   → cli, on Wayland portal → x11 → cli, or the one chosen in Settings; each is tried once and the last error is
   reported in a toast.
3. Full screen: done. Region/Window: the overlay opens on every monitor (`ui/capture_overlay.py`).
4. The region is cropped, saved to the save folder as the next name, copied to the clipboard (if enabled), loaded
   into the editor, and announced in a toast.

| Backend | Mechanism | Window list |
| --- | --- | --- |
| `x11` | libX11 `XGetImage` through ctypes (≈50 ms for 2560×1080; python-xlib's pure-Python reply parsing took ≈3.5 s and read as a "capture delay"), one numpy copy BGRX → ARGB32; python-xlib only as a fallback | `_NET_CLIENT_LIST_STACKING` + `_NET_FRAME_EXTENTS` via python-xlib, topmost first, docks/desktop skipped |
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
| `annotations.py` | `Style` (incl. `opacity`), `Annotation` (kinds arrow, line, box, circle, text, pen, marker, step, callout, fill, blur, pixelate, image), Cairo painters ported from 1.4, **Gaussian shadows** (a black silhouette blurred with Pillow, cached per annotation, offset and sigma grow with the line width; replaces the 1.4 three-pass shadow that banded), whole-annotation opacity via a cairo group, pixelate (numpy) and blur (Pillow) on the composite, `snap45`, `constrain_square`, bounding boxes, hit test, dict round-trip, `renumber_steps`; `BADGE[kind]` is the tool name in capitals |
| `document.py` | `Document` (base surface, `Layer` list with ids/badges/visibility, dirty flag, `summary()`), `open()`/`save()` PNG/JPEG/WebP, `flatten()`, `flatten_into_base()`, exact PIL↔cairo conversion |
| `undo.py` | `UndoStack` (20 deep, redo, labels, on_change) with `AddLayer`, `RemoveLayer`, `MoveLayer`, `EditAnnotation`, `SetVisible`, `ReplaceBase`, `TransformBase` |
| `app/image_ops.py` | pure crop, scale, rotate, flip, adjust returning the new base and a coordinate mapper |
| `captures_index.py` | threaded thumbnail scan of the save folder → `Gio.ListStore`, newest first |
| `settings.py` | schema, validation, migration, naming |

## 10. Keyboard shortcuts

Two tiers, so a shortcut can never steal a keystroke from a text field. **Global chords** are GTK application
accelerators (which GTK dispatches in the capture phase, before the focused widget). **Editing and tool keys**
go through `app/shortcuts.py`, a capture-phase router on the window that yields whenever the inline text editor,
a text entry or anything inside a popover has focus, swallows tool letters during a drag, and retargets Delete
and Escape to the Library page while it is open. With focus in a header **spin button** (after adjusting Width,
say) the editing chords, tool letters and Escape still work and move the focus back to the canvas; digits, Enter,
Delete and arrows keep editing the number. So Ctrl+Z works whatever tool is active and wherever the last click went.


| Keys | Action |
| --- | --- |
| PrintScreen (system binding, Phase 6) · Ctrl+N | capture in the current mode |
| Ctrl+Shift+N | full-screen capture |
| V A L B C T P M E H · R O J · U X N K | tools (Select, Arrow, Line, Box, Circle, Text, Pen, Marker, Eraser, Hand · Box area, Round area, Point chain · Blur, Pixelate, Step, Crop) — routed, never while typing or dragging; each tool button's tooltip shows its letter |
| Area marked: Ctrl+C · Enter · Delete · Esc · Backspace | copy the region · crop to it · clear it · drop it · (chain in progress) remove the last point |
| Space (held) · middle button | pan the view with a drag (Space is always swallowed, so it never activates a focused rail button) |
| Ctrl+A | editor: select all layers · Library: select all files |
| Ctrl+C | copy the composition to the clipboard (and remember the selected layer for Ctrl+V) |
| Ctrl+V | paste: a copied layer, a clipboard image (image layer / new document) or clipboard text (text layer) |
| Ctrl+Z · Ctrl+Shift+Z / Ctrl+Y · Delete · Ctrl+D · Esc | undo · redo · delete layer(s) (Library: trash the selection) · duplicate layer (Library: duplicate files) · clear selection / close Library — routed, so inside a text field they edit the text |
| Library: Ctrl+C · Ctrl+D · Delete · Enter · Esc | copy the selection · duplicate · trash · open · close |
| Ctrl+S · Ctrl+Shift+S | save · save as |
| Enter (Crop tool) | apply the pending crop |
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
| `make snapshot` also writes | `shell_annotated.png` (seven kinds, a selected box), `shell_crop.png` (pending crop), `shell_adjust.png` (Brightness popover with live preview), `shell_select_all_tray.png` (Ctrl+A outline, three copies in the tray), `shell_eraser.png` (checkerboard through an eraser stroke), `shell_library_multiselect.png` (8 of 8 selected), `shell_area_chain.png` (a closed point chain) |
| `tools/snapshot_overlay.py` | render the live capture overlay (output git-ignored: it contains the real screen) |
| `make launcher` / `make unlauncher` | install/remove the **LinScreenCapture3** menu entry |
| `bash ~/projects/Zai-ZCode/s009_backup_project.sh …` | family backup into `~/backups/linscreencapture3/` |

## 12. Review round 2 (2026-10-13) — layout and implementation notes for agents

One entry per feature of the round: where it lives, how it is wired, what to keep in mind.

| Feature | Layout | Implementation |
| --- | --- | --- |
| Capture delay | Delayed is the timer toggle in the CAPTURE group; it is off at every launch and the mode is Region (`win.capture-delayed` boolean, `win.capture-mode` "region"). | `capture_controller.capture()` reads the toggle; the real "3 s delay" users saw was python-xlib parsing the `GetImage` reply. `backends/x11.py::grab_root_libx11` now calls libX11 `XGetImage` through ctypes (≈50 ms); python-xlib remains for the window list and as a fallback. A toast warns when the toggle is on with `delay_seconds` = 0. |
| Library controls | Head row, right-aligned: Refresh · Select all · Copy · Duplicate · Delete · Open · Close. Summary line reads "n of m selected" with a group selection. | `ui/library_page.py` uses `Gtk.MultiSelection`; `selected_entries` reads the bitset. Window actions `library-select-all/copy/duplicate/delete/open`; the router maps Ctrl+A/C/D, Delete, Enter, Esc to them while `state.library` is true. `services/file_store.duplicate_file` names copies. Copy of one file = texture + `Gdk.FileList` + `text/uri-list` union; several = files only. `CapturesIndex._apply` keeps the store when the folder is unchanged so a rescan never wipes the selection. Double-click = GridView `activate(position)` → `activated_entry` → open. |
| Ctrl+A / Ctrl+C in the editor | Dashed accent outline around the image and each visible layer; header strip shows the Select hint. | `EditorController.select_all()` sets `all_selected` (cleared by `select()`, `_commit()`, tool change); `_copy()` copies `document.flatten()` and toasts the layer count; `delete_selected()` commits `undo.RemoveLayers` (one step). Moving all layers together is not implemented. |
| Clipboard tray | Left rail, CLIPBOARD group between the tool grid and Library; 116 px like the navigator; **one slot** for now (accent border = currently on the clipboard; hover = caption tooltip); collapsed rail: a `clipboard` MenuButton with the tray in a popover. Slot click → popover: ≤ 320×200 sample, caption, Copy · Paste · Delete centred. Roadmap: several slots (`SLOTS`, `ClipHistory.limit`). | `services/clip_history.py::ClipHistory` (signal `changed`, limit 1 — the class supports any limit, blake2b digest dedupe, `preview` texture ≤ 320×200, `remove()` clears the system clipboard when the entry owns it, external clipboard changes drop the "current" mark). `ui/clip_tray.py`: `ClipTray` (slots are `Gtk.MenuButton`s — a popover popped up from a plain button's `clicked` handler was closed by the same release), `ClipPreview` (actions `clip.copy/paste/delete` in a local `Gio.SimpleActionGroup`), `ClipTrayButton`. Pushed from `StudioWindow._copy`, `_library_copy` and `CaptureController._finish` (when copy-to-clipboard is on). Copies made by other apps are not tracked. |
| Transparent PNGs | Checkerboard under the image on the stage; PNG save keeps alpha; JPEG composites on white. | `Stage._checkerboard()` (16 px repeat pattern, two greys near the stage colour) painted inside the image clip before the composite; `Document.save` pastes RGBA onto white for JPEG; open/paste already preserved alpha (`surface_from_pil`). |
| Eraser tool | TOOLS row 2 after Marker (icon `eraser`, key E); strip set "eraser": Width (2–80, default 24) · Opacity · hint. Layer badge `ERASER`. | Annotation kind `eraser` (stroke kind; `draw()` → `_erase`: `OPERATOR_DEST_OUT` with the tool opacity as strength); previews and thumbnails use `_paint_eraser_ghost` (a translucent white band) because clearing the overlay would also clear the checkerboard. `settings.TOOLS` includes `eraser` (`width_eraser`, `opacity_eraser`). |
| Shortcut captions | Every rail/pill/head button tooltip is two lines: caption, then the key in small muted type. | `widgets.tooltip_with_key()` + `rail_button(key=…)`; `tool_rail.Item.key` (tools take theirs from `shortcuts.KEY_FOR_TOOL`); `get_tooltip_text()` returns `"Caption\nKey"`. |
| Panning with the mouse | Hand tool (icon `hand`, key H, strip hint); Space held with any tool; middle-button drag anywhere on the stage. Cursors `grab` / `grabbing`. | Editor mode `pan`: deltas measured in stage-scroller coordinates (`_to_scroller`) so scrolling the canvas does not feed back into the drag; `Stage.scroll_by(dx, dy, origin)` clamps adjustments; middle button is a `Gtk.GestureDrag(button=2)` on the scroller. Space: `ShortcutRouter` sets `editor.set_space_pan(True/False)` on press/release (and on window deactivate). |
| Area tool (Box area · Round area · Point chain) | TOOLS row 2, first three buttons (icons `bounding-box`, `circle-dashed`, `polygon`; Blur moved to `drop-half`); keys R · O · J; strip set "area" shows a per-mode hint. Marked area = dashed accent outline + 12 % fill; chain in progress = accent lines, rubber band to the pointer, white dot on the first point. The vocabulary is deliberately its own (area, point chain, mark) — no marquee / lasso / select / path / pen terms. | `EditorController.area` is an `Annotation("cutout", shape=box\|round\|points)`; drag modes `area`; clicks → `_chain_click` (closes within `CHAIN_CLOSE_PX` of the first point or on double-click); `area_path()` in `model/annotations.py` traces the region for drawing, `_cutout` (DEST_OUT fill, the Delete layer), `area_surface()` (Ctrl+C: DEST_IN copy) and `image_ops.crop_masked` (Enter: crop to the bbox + DEST_IN). Router: Esc → `cancel_area`, Backspace → `chain_pop`, Enter → `apply_crop` (area first), Delete → `delete_selected` (area first). Tool switch cancels. Style/colour irrelevant; `settings.TOOLS` unchanged. |
| Space toggling the right rail | Not intended. A rail button held keyboard focus (initial focus landed on the first focusable widget) and Space activated it. | The window focuses the canvas on map; the router swallows Space (editor and Library) so a focused button never sees it. Guarded by `test_hand_space_and_middle_button_pan_the_view`. |
