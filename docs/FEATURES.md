# LinScreenCapture 3 — feature reference

Complete description of everything the application does as of 2026-10-16 (Phases 1–5 of 7, two review
rounds and the Phase 6 work so far on `feat/background-agent`). Every item below exists in the code on branch
`feat/background-agent` and is covered by `make test` (119 tests: 117 pass, 2 cosmetic window-geometry failures under
Xvfb) or a render in `screenshots/dev/`. Planned work (Phase 6: countdown, pin, scrolling capture, registrar for other
desktops; Phase 7: polish and release) and the backlog are in `HANDOFF.md` §3 and §8; known limits in
`KNOWN_ISSUES.md`; the GUI specification in `docs/GUI_SPEC.md`. Capture, hotkey and clipboard behaviour is specified
in `docs/CAPTURE.md` (authoritative); §1, §11 and §12 here summarise it.

Conventions: `win.*` are window actions, `app.*` application actions (`ui/studio_window.py`,
`app/application.py`); a key in **bold** is a shortcut; "strip" is the tool-properties strip in the header.

Contents: 1 Launching · 2 Window and chrome · 3 Left rail · 4 Header strip · 5 Right rail · 6 Stage ·
7 Annotation tools · 8 Selection, clipboard and the Area tool · 9 Image operations and files · 10 Library ·
11 Capture · 12 Settings · 13 Model and services · 14 Keyboard and mouse reference · 15 Developer tools ·
16 Layout and implementation notes for agents

---

## 1. Launching

| Function | How | Module |
| --- | --- | --- |
| Start the studio | `python3 -m linscreencapture`, the `linscreencapture` console script, or the **LinScreenCapture3** menu entry installed by `make launcher` (runs `tools/launch.sh` from the checkout) | `__main__.py`, `tools/launch.sh`, `data/linscreencapture3-dev.desktop.in` |
| Capture immediately | `linscreencapture --capture` (`-c`), the PrintScreen binding: a second instance forwards `app.hotkey-capture` to the running agent over D-Bus; started cold, the process becomes the agent with no window. Always the fast Region capture, from anywhere including the studio: clipboard first, then the save folder, then the studio, which is not popped up (hidden stays hidden, visible is shown again with the capture; §11). With *PrintScreen opens the editor* on, the studio is presented every time. The `.desktop` file exposes it as the "Capture a region" action | `app/application.py` |
| Background agent | the primary instance `hold()`s itself while `keep_running` is on: closing the studio hides it (`hide_on_close`, document kept), Quit (**Ctrl+Q**, tray) ends the process. `--background` (`-b`) starts the agent with no window; a second `--background` exits quietly | `app/application.py` |
| Tray icon | `python3 -m linscreencapture.tray`: a separate GTK 3 process (GTK 4 has no status icon and cannot share a process with GTK 3), started and stopped by the agent, exits when the agent's bus name vanishes. XApp.StatusIcon first, AyatanaAppIndicator3 as the fallback. Shown whenever the application runs (agent or not). The icon is orange #ffa222 (the application icon `data/icons/hicolor/scalable/apps/com.mensuramedia.LinScreenCapture.svg`, full colour so the panel does not recolour it). Menu (right-click): *Capture region to clipboard* (`app.hotkey-capture`), *Open editor* (`app.show-editor`), *Quit* (`app.quit`); **double-click** = Open editor (`tray.DoubleClick` pairs XApp `activate` events within the GTK double-click time; AppIndicator has no click events, so there only the menu). The helper sets its program name to `linscreencapture-tray`: XApp derives the D-Bus name from it, and the default `tray.py` collided with Linux Mint's own tray helpers, leaving the icon invisible. `LSC_NO_TRAY=1` disables it | `tray.py` |
| Hotkey registration | Settings → System → *Capture hotkey*: a preset or any recorded key combination (*Record…*, `ShortcutRecorder`), and *Register with the desktop* (default on). On Cinnamon the agent writes our `customN` custom keybinding (`<Primary>Print` style, a list), never overwrites another application's slot, frees the key from the six built-in screenshot bindings and reloads Cinnamon through `org.Cinnamon.Eval`; re-applied at every agent start while the switch is on. Other desktops: bind `linscreencapture --capture` by hand (`docs/CAPTURE.md` §4) | `services/hotkey_registrar.py` |
| Autostart | `~/.config/autostart/com.mensuramedia.LinScreenCapture.desktop` running `<linscreencapture on PATH> --background` (else `python3 -m linscreencapture --background` with `Path=` the checkout); created on the first run (on by default) and written or removed by Settings → System → *Run at startup*; afterwards the file on disk is the truth (`autostart.sync`) | `services/autostart.py` |
| Installation | `install.sh` (user `~/.local` by default, `--system` → `/usr/local` with sudo, `--deps` apt-installs the packages, `--uninstall`, `--force` to replace a foreign launcher, `--prefix`/`--destdir` for packagers) and the Debian package `packaging/linscreencapture_<version>_all.deb`, built by `packaging/build-deb.sh` (`make deb`) from `install.sh --prefix /usr`. Layout: `lib/linscreencapture/` (package + `.gresource` + app icon SVG), `bin/linscreencapture` launcher, `share/applications/com.mensuramedia.LinScreenCapture.desktop`, `share/icons/hicolor/{16…512,scalable}/apps/` | `install.sh`, `packaging/` |
| App identity | `__main__` sets the program name to the app id before GTK starts, so the window's `WM_CLASS` is `com.mensuramedia.LinScreenCapture` (it was `__main__.py`, which left Alt+Tab with a generic icon and named the "not responding" dialog `__main__.py`); every window carries the app icon (`Gtk.Window.set_default_icon_name`, the SVG is bundled in the `.gresource` as `scalable/apps/<id>.svg`); the menu entries are named after the id with `StartupWMClass`. The icon (`data/icons/hicolor/scalable/apps/com.mensuramedia.LinScreenCapture.svg`, PNGs in `resources/icons/`) is an orange #ffa222 tile with a white selection frame, a dashed marquee and a pointer; the panel icon and the autostart entry use the same artwork and theme name; placement and rules: `docs/ICONOGRAPHY.md` | `__main__.py`, `services/icon_loader.py`, `services/autostart.py` |
| Single instance | `Adw.Application`, id `com.mensuramedia.LinScreenCapture`; a second launch raises the window. Tools and probes build `Application(non_unique=True)` so they never activate a running copy | `app/application.py` |
| Diagnostics | `--debug` (`-d`) or `LSC_DEBUG=1`: timestamped log of versions (Python, PyGObject, GTK, libadwaita), session type, resource and icon count, stylesheet, settings file and values, backend order, action counts, window build time and every capture step; GTK/GLib messages go to the same stream under `toolkit` | `app/logging_setup.py` |
| Window memory | size, maximised state and the collapsed state of both rails are saved on close and restored on the next start | `model/settings.py`, `StudioWindow._on_close` |
| First keyboard focus | the stage canvas, never a rail button (so Space and Enter cannot activate one by accident) | `StudioWindow` (`map` handler) |

## 2. Window and chrome

| Function | Behaviour |
| --- | --- |
| Theme | "Graphite Night": one dark palette (`ui/style.css`), Ubuntu / Cantarell fonts, 30 px controls, 18 px glyphs, 6 px radii; the dark scheme is forced (`Adw.ColorScheme.FORCE_DARK`) |
| Title bar | the 52 px header is the window's title bar (client-side decoration): drag moves, double-click maximises; the system window buttons follow `gtk-decoration-layout` (icon/menu tokens dropped) |
| Header contents | left: the title block — the document name, and once a document exists the subtitle `Edit · W×H · FORMAT · n layers · saved/unsaved`; centre: the tool-properties strip (§4); right: window controls |
| Rails | left and right rails are 220 px open and 56 px collapsed; **collapsed by default** on first run (Settings → Window changes that); carets are single chevrons pointing the way the rail moves; **Ctrl+[** / **Ctrl+]** toggle them |
| Auto-collapse | below 1100 px window width both rails collapse; when the window widens they return to the state they had before; a caret clicked by hand wins for the rest of the session |
| Minimum size | 960×600; default 1360×840 |
| Toasts | bottom-centre messages for saves, copies, captures, hints and errors; placeholders say "… arrives in Phase N" |
| Dialogs | Settings, Flatten, Delete and unsaved-changes prompts are libadwaita dialogs (they open as small separate windows because the studio uses a plain GTK window for its custom title bar) |
| Icons | 64 Phosphor "regular" glyphs compiled into the GResource as `lsc-<name>-symbolic`, recoloured by CSS |

## 3. Left rail (`ui/tool_rail.py`)

Every button has a two-line tooltip: the caption, then its shortcut in small muted type.

| Row | Controls | Actions |
| --- | --- | --- |
| Top | Capture (30 px accent icon, **Ctrl+N**) · collapse caret (**Ctrl+[**) | `app.capture` captures in the current mode |
| CAPTURE | Region · Region Plus · Window · Full screen (**Ctrl+Shift+N**) · Scrolling · Delayed · Pin | `win.capture-mode` is a stateful choice (region, region-plus, window, screen, scrolling); Region (`selection` icon) captures on mouse release, Region Plus (`bounding-box` icon) keeps handles until Enter or a double-click; **Region is the mode at every launch**. **Delayed is a toggle** (`win.capture-delayed`, boolean, **off at every launch**): while on, captures in any mode wait `delay_seconds` first; clicking the timer again turns it off; a toast confirms each state and warns when the configured delay is 0 s. Scrolling and Pin are Phase 6 placeholders (toast) |
| TOOLS row 1 | Select **V** · Arrow **A** · Line **L** · Box **B** · Circle **C** · Text **T** · Pen **P** · Marker **M** · Eraser **E** · Hand **H** | `win.tool::<name>` (stateful; exactly one toggle checked) |
| TOOLS row 2 | Box area **R** · Round area **O** · Point chain **J** · Blur **U** · Pixelate **X** · Fill · Step number **N** · Callout · Crop **K** · Resize · Rotate · Brightness · Move · Duplicate | tools via `win.tool`; Resize / Rotate / Brightness open popovers (`win.resize`, `win.rotate`, `win.adjust`); Duplicate (file) is a Phase 7 placeholder |
| CLIPBOARD | a navigator-sized tray (116 px) with **one slot** holding the last copy the application made (accent border while that copy is still on the clipboard); hover shows `label · W×H · time`; a click opens a preview popover (sample ≤ 320×200, caption, then **Copy · Paste · Delete** centred below). Copy puts the sample back on the clipboard; Paste adds it to the open image as a layer (or opens it as a new image on an empty stage); Delete drops it from the tray and clears the system clipboard if it held that copy. Several slots are a roadmap item (HANDOFF §8); `ClipHistory.limit` and `clip_tray.SLOTS` already parametrise it | `ui/clip_tray.py`, `services/clip_history.py` |
| above the line | Library (**Ctrl+L**, toggle) | `win.library` |
| ACTIONS | Discard · Save (**Ctrl+S**) | `win.discard` clears the stage (asks when unsaved); `win.save` |
| Collapsed page | caret, Capture, Region / Full screen / Delayed, seven tools (Arrow, Box, Text, Pen, Blur, Step, Crop — the active tool always takes the last slot if it is not among them), a clipboard button whose popover holds the same tray, Library, Discard, Save | same actions |

## 4. Header tool-properties strip (`ui/tool_props.py`)

The strip follows the active tool, and under Select / Move the **selected layer** (title reads for example
`BOX · SELECTED`). Each control reads from and writes to `Settings` the moment it changes; with a layer
selected the change is also applied to that annotation as an undoable "Style" edit.

| Tool(s) | Controls |
| --- | --- |
| Arrow, Line | Width (1–20) · Shadow · Intensity (0–1) · Opacity |
| Box, Circle | the same plus Fill |
| Pen, Marker | Width · Shadow · Opacity (the marker paints at 4× width; its opacity defaults to 0.40) |
| Eraser | Width (2–80, default 24) · Opacity (= erase strength) · hint |
| Text, Callout | Font (Ubuntu, Cantarell, DejaVu Sans, Liberation Sans, Noto Sans) · Size (6–96) · Bold · Italic · Shadow · Opacity |
| Step number | Badge size (8–48) · Opacity |
| Fill | Opacity |
| Blur, Pixelate | Mode (Pixelate / Blur — switches the tool) · Block size (2–32) |
| Crop | hint · Apply crop · Cancel |
| Box area, Round area, Point chain | a hint for the mode (drag / click points, then Ctrl+C · Enter · Delete · Esc) |
| Hand | hint (also Space, middle button) |
| Select, Move (no selection) | hint (click, drag, Delete, Ctrl+D, Ctrl+A) |

Opacity (0.05–1.00) applies to the whole annotation as one cairo group, so a translucent filled box shows no
darker rim where stroke and fill overlap; it is stored per tool and stays per tool even when the Universal
switch makes width/shadow/fill shared.

Keyboard focus never stays in the strip: switches, toggles, scales and buttons do not take focus on click, a
tool switch and the font dropdown hand focus back to the canvas, Enter in a spin does the same, and the shortcut
router (§14) handles editing chords and tool letters even while a spin button holds focus.

## 5. Right rail (`ui/panel_rail.py`)

| Group | Controls | Behaviour |
| --- | --- | --- |
| COLOUR | 12 round 18 px swatches (accent ring on the current one), custom colour `+` (`Gtk.ColorDialog`), eyedropper | sets the colour for new annotations, recolours the selected layer (undoable), persists to every tool's settings; the eyedropper makes the next click on the image pick that composite pixel (toast shows the hex) |
| VIEW | zoom out · value · zoom in · fit | `win.zoom-out` / `win.zoom-in` (**Ctrl+−** / **Ctrl++**) zoom by **4 %** of the current zoom per step, on whole percents (100 → 104 → 108 → 112 …; 100 → 96 → 92 → 88 …), at least 1 % per step, always stopping at 100 % when crossing it, within 10–1000 % (`view_state.next_zoom`); `win.zoom-fit` (**Ctrl+0**, never above 1:1); `win.zoom-actual` (**Ctrl+1**) |
| EDIT | Copy (**Ctrl+C**) · Flatten | `win.copy` (§8), `win.flatten` (§9) |
| LAYERS | scrollable list, annotation layers top-first: a rendered 40×28 thumbnail of that layer alone, its **number** (stack position, 1 = bottom), a label naming the **tool that made it** (`ARROW`, `BOX`, `BLUR`, `PIXELATE`, `TEXT`, `STEP`, `CALLOUT`, `ERASER`, `CUTOUT`, `IMAGE`…) and an eye; the last row is `Base capture · IMG`; "No layers yet" when empty | a row click selects the layer on the stage and vice versa; the eye hides/shows the layer (undoable). Drag-to-reorder is not implemented (`MoveLayer` exists) |
| Navigator (untitled) | 116 px thumbnail of the composite, dimmed outside the viewport, accent rectangle for the visible part | follows zoom and scroll; click or drag scrolls the stage to that point |
| bottom-right | Settings (**Ctrl+,**) | `app.preferences` |
| Collapsed page | caret, six colour dots, eyedropper, −, +, fit, Copy, Flatten, gear | same actions |

## 6. Stage (`ui/stage.py`)

| State | Behaviour |
| --- | --- |
| Empty | camera glyph, "Press PrintScreen or click Capture", mode list, shortcut chips (Ctrl+N region · Ctrl+Shift+N full screen · Ctrl+V paste); HUD shows `—` |
| Document | the image painted pixel-exact with square corners, centred, scrollable when larger than the viewport, over a muted 8 px **checkerboard** that shows through transparent pixels (clear PNGs, eraser strokes, cleared areas); a smooth drop shadow (linear gradients on the sides, radial on the corners, 18 px reach) outside the image; the HUD bottom-left shows the zoom |
| Zoom | the 4 % steps above, also per **Ctrl+scroll** notch; a loaded or cropped document fits automatically; nearest-neighbour filtering from 400 % up |
| Panning | Hand tool (**H**) drag · **Space** held + drag with any tool · **middle-button** drag anywhere on the stage; cursors `grab` / `grabbing`; the navigator also scrolls |
| Inline text entry | Text and Callout type into an entry positioned over the image (Enter commits, Esc cancels); keyboard shortcuts yield to it |
| Click on the empty stage | a click (not a drag) outside the image — in the canvas margin or beyond — drops the active tool back to Select, clears the selection, any marked area and any pending text; the zoom HUD is not "empty stage" |
| Library page | covers the stage while the Library is open (§10) |

## 7. Annotation tools (`app/editor_controller.py`, `app/tools.py`, `model/annotations.py`)

Every drawing produces one layer and one undo step; the new layer is selected. A live preview shows while
dragging (at 60 % opacity, or the tool's own opacity if lower); the strip's width, shadow, opacity, fill and
font settings apply at creation.

| Tool | Gesture | Result |
| --- | --- | --- |
| Arrow **A**, Line **L** | drag; **Shift** snaps to 45° | filled arrow with a head that scales with the width / round-capped line |
| Box **B**, Circle **C** | drag; **Ctrl** constrains to a square / circle; Fill switch | outlined or filled rectangle / ellipse |
| Fill | drag | rectangle filled with the current colour |
| Pen **P** | drag | free stroke of the pointer path (sub-pixel jitter dropped), round caps and joins |
| Marker **M** | drag | the same at 4× width and 40 % opacity (per-tool opacity) |
| Eraser **E** | drag | a stroke that clears what lies beneath to transparent (`OPERATOR_DEST_OUT`; the Opacity slider is the strength); shown as a translucent band while dragging and in thumbnails; PNG keeps the transparency, JPEG lands it on white |
| Text **T** | click, type, **Enter** (**Esc** cancels) | text layer in the strip's font; double-click a text or callout layer under Select to edit its text |
| Callout | drag from the bubble position to the target, type, Enter | rounded bubble with a tail pointing at the target; white text |
| Step number **N** | click | numbered badge (size from the strip); numbers follow stack order and renumber on delete and reorder |
| Blur **U**, Pixelate **X** | drag (dashed preview) | redaction applied to the pixels beneath at render time (Gaussian blur radius / block average), so layers under it are redacted too |
| Crop **K** | drag, then **Enter** or Apply crop (**Esc** / Cancel abandons) | the base is cropped and every layer moves with it; a dark veil shows the pending crop |
| Hand **H** | drag | pans the view (no layer) |
| Box area **R**, Round area **O**, Point chain **J** | see §8 | mark a region for copy, crop or clear |
| Select **V** / Move | click selects the topmost layer under the pointer; drag moves it; handles resize (8 for boxes, circles, fills, redactions and pasted images; 2 for arrows, lines and callouts; **Ctrl** keeps shapes square). **Pasted images** resize like in an image editor (`tools.image_resize`): corner handles keep the proportions, **Shift** stretches freely, **Ctrl** resizes about the centre, edge handles stretch one side, never below 4 px; a solid frame marks the selected image and a `W × H px · N %` readout follows the drag; the header strip shows **W**, a proportions lock, **H**, **Scale %** (of the pasted image's own size), **100 %** and **Fit** (fit inside the image, centred). **Arrow keys** nudge the selected layer 1 px (Shift: 10 px); **Delete** removes; **Ctrl+D** duplicates 12 px offset | undoable edits; cursor changes per handle. The selection shows **handles only** (text, pen, marker and step layers, which have no handles, get four small corner ticks); Settings → Window → "Dashed frame around the selected layer" restores a dashed frame |

Shadows (Arrow, Line, Box, Circle, Text, Pen, Marker) are a Gaussian-blurred black silhouette of the shape,
cached per annotation, whose offset and blur grow with the line width (the 1.4 three-pass shadow banded).

Undo: **Ctrl+Z**, redo **Ctrl+Shift+Z** or **Ctrl+Y**, 20 steps deep; the Undo toast names the step; the
subtitle's layer count and `unsaved` follow every change.

## 8. Selection, clipboard and the Area tool

### Selecting layers

| Action | Keys | Behaviour |
| --- | --- | --- |
| Select one | click (Select / Move) or a Layers row | white handles with an accent border (corner ticks for layers without handles; the dashed frame is optional); the strip shows its properties |
| Select all | **Ctrl+A** | every layer is marked: dashed outline around the image and each layer, Select tool active. Ctrl+C then copies the flattened image, Delete removes all layers in one undo step; a plain selection, Esc, a tool switch or a click on the empty stage ends it. Moving all layers together is not implemented |
| Clear selection | **Esc** | |

### Clipboard

| Action | Keys | Behaviour |
| --- | --- | --- |
| Copy | **Ctrl+C**, EDIT → Copy | with an **area marked**: just that region (outside the shape transparent); otherwise the **flattened image** with every layer. A selected layer is also remembered so Ctrl+V pastes a copy of it (until the clipboard changes elsewhere). Every copy also lands in the clipboard tray (§3) |
| Paste | **Ctrl+V** | in order: a layer copied in the app → a copy 12 px offset (repeated pastes cascade); an image on the clipboard → with a document open an `image` layer centred and selected (scaled down to fit), with none a new Untitled document; text on the clipboard (from a document, a web page…) → a `text` layer in the Text tool's style centred on the image, Select tool active (CRLF normalised, 2000 characters max). Clipboard images are recognised by GType (local `Gdk.Texture` subclasses) or `image/*` MIME types |
| Tray | left rail | the last copy with preview, Copy, Paste, Delete (§3) |

### The Area tool

Three modes mark a region of the image. The vocabulary (area, point chain, mark) is deliberately distinct from
other image editors' selection terms.

| Mode | Key | Gesture |
| --- | --- | --- |
| Box area | **R** | drag; **Shift** keeps it square |
| Round area | **O** | drag; **Shift** keeps it round |
| Point chain | **J** | each click joins a line from the previous point; a rubber band follows the pointer; click the first point (within 9 px) or **double-click** to close; **Backspace** removes the last point; **Esc** cancels the chain |

A marked area shows as a dashed accent outline with a faint fill. While it is marked:

| Key | Effect |
| --- | --- |
| **Ctrl+C** | copies the region (bounding box; outside a round or chained shape transparent) to the clipboard and the tray |
| **Enter** | crops the document to the area (`image_ops.crop_masked`: bounding box, pixels outside the shape cleared); layers move with the crop; one undo step |
| **Delete** | clears the area to transparent as a `CUTOUT` layer (undoable; it clears whatever is beneath it in the stack) |
| **Esc**, a tool switch, a click on the empty stage | drops the area |

## 9. Image operations and files (`app/image_ops.py`, `ui/popovers.py`, `ui/studio_window.py`)

| Function | Where | Behaviour |
| --- | --- | --- |
| Crop | Crop tool, Area tool | see §7 and §8 |
| Resize | Resize button → popover | width, height, percent, keep-ratio; Apply scales the base (Lanczos) and every layer's coordinates |
| Rotate / Flip | Rotate button → popover | 90° clockwise, 90° counter-clockwise, 180°, flip horizontal, flip vertical; layers follow (text stays upright: KNOWN_ISSUES) |
| Brightness | Brightness button → popover | brightness and contrast −100…100, grayscale, invert, **live preview** on the stage; Apply commits, Cancel or closing restores |
| Flatten | EDIT → Flatten | confirmation, then all layers merge into the base (one undo step) |
| Save / Save As | **Ctrl+S** / **Ctrl+Shift+S** | in place when the document has a file; otherwise a file dialog seeded with the save folder and the next free name; format by extension — PNG (keeps transparency), JPEG (configured quality, transparent pixels on white), WebP; the Library rescans |
| Discard | ACTIONS → Discard | clears the stage; with unsaved changes a Save / Discard / Cancel prompt first |
| Unsaved changes | Discard, Library Open | the same prompt |
| Undo | all of the above | crop, resize, rotate, flip, adjust are `TransformBase` commands that also restore layer positions; flatten is a `ReplaceBase` |

## 10. Library (`ui/library_page.py`, `model/captures_index.py`)

A full-stage page of the save folder, newest first, toggled by the Library button or **Ctrl+L** (Esc closes).

| Function | Behaviour |
| --- | --- |
| Head | title, `n screenshots · ~/folder` (or `k of n selected`), then Refresh · Select all · Copy · Duplicate · Delete · **Open** · Close |
| Grid | 180×120 thumbnails with file name and date (`Oct 9, 2026 · 14:17`); up to 200 newest PNG/JPEG/BMP/GIF/WebP/TIFF files; thumbnails are loaded in a worker thread; an empty folder shows a placeholder |
| Selection | click, **Ctrl+click**, **Shift+click**, **Ctrl+A** (`Gtk.MultiSelection`); a rescan (Refresh, Open, save) keeps the selection when the folder has not changed |
| Open | **double-click**, **Enter** or the Open button loads the file into the editor (prompting first if the current document is unsaved) |
| Copy (**Ctrl+C**) | one file: its pixels, the file and a `text/uri-list` go on the clipboard (and into the tray); several files: the files only, for pasting into a file manager |
| Duplicate (**Ctrl+D**) | copies each selected file next to itself as `name copy.png`, `name copy 2.png`… and rescans |
| Delete (**Delete**) | moves the selection to the trash after one confirmation, then rescans |
| Scope | Copy, Duplicate and Delete touch only the library (files on disk and the clipboard), never the document on the stage |

## 11. Capture (`app/capture_controller.py`, `services/capture_service.py`, `backends/`, `ui/capture_overlay.py`)

Summary of `docs/CAPTURE.md` §5 (authoritative).

1. The mode: a hotkey capture (`app.hotkey-capture`) is always Region with no delay; otherwise the rail's mode, plus
   `delay_seconds` while the Delayed toggle is on (a toast announces it). Scrolling and Pin toast "arrives in Phase 6".
   A visible studio hides and the compositor gets 300 ms to repaint without it; with nothing on screen the wait is 0 ms.
2. The screen is frozen by the first working backend: on X11 sessions x11 → portal → cli, on Wayland portal → x11
   → cli, or the backend chosen in Settings first; each is tried once and the last error is shown in a toast.
3. Full screen: done. Region / Region Plus / Window: the overlay opens on every monitor.
4. The frozen screen is cropped (no re-grab, no scaling) and copied to the clipboard **first**, on every route:
   `image/png` plus a `GdkTexture` value, then `store_async` to the clipboard manager (`services/clipboard.py`).
5. It is saved to the save folder under the next name (§12).
6. `ensure_window()` builds the studio hidden if there is none; the capture is loaded as the document and pushed onto
   the clipboard tray.
7. The studio is presented with a toast (`Saved … · copied to clipboard`) only when `presents`: the capture was not a
   hotkey capture, the studio was visible before, or *PrintScreen opens the editor* is on. Errors with no studio on
   screen become a desktop notification. Cancelling the overlay (Esc) writes nothing.

| Backend | Mechanism | Window list |
| --- | --- | --- |
| `x11` | libX11 `XGetImage` through ctypes (≈50 ms for 2560×1080; python-xlib's pure-Python reply parsing took ≈3.5 s and was perceived as a "capture delay"), one numpy copy BGRX → ARGB32; python-xlib only as a fallback | `_NET_CLIENT_LIST_STACKING` + `_NET_FRAME_EXTENTS` via python-xlib: topmost first, docks and desktop skipped |
| `portal` | `org.freedesktop.portal.Screenshot` (async Response signal), temporary file loaded and deleted | none (Window mode falls back to Region) |
| `cli` | `gnome-screenshot -f`, `grim`, `import -window root`, `spectacle -b -n -f -o` | none |

### Overlay

| Function | Keys / mouse |
| --- | --- |
| Select a region | drag; **Shift** constrains to a square; **Space** while dragging moves the box instead of resizing; 45 % veil outside the box |
| Region | the capture happens on mouse release: no handles |
| Region Plus | 8 handles resize, drag inside moves, **arrows** nudge 1 px, **Shift+arrows** 10 px; **Enter** or a double-click inside the box captures |
| Both modes | **Esc** cancels; **Ctrl+A** selects the whole screen (then **Enter** captures); **Enter** and a double-click inside the box also confirm in Region; a click without a drag clears the box |
| Window mode | hovering highlights the window under the pointer with its title; a click captures it including its frame |
| Mode bar | Region · Region Plus · Window · Full screen icon toggles at the top, nothing else (tooltips name them); switching takes effect at once. No hint text anywhere on the overlay |
| Readouts | size chip under the box (`W × H`); pointer position and the colour under it bottom-left |
| Multi-monitor | one overlay window per monitor sharing one session; a selection cannot span monitors; integer HiDPI scale factors per monitor |

**Hotkey capture** (`capture("region", hotkey=True)`, from `app.hotkey-capture`: the desktop hotkey via
`--capture`, the tray, the `.desktop` action): always Region, ignoring the rail's mode and the Delayed toggle. The
capture goes to the clipboard, the save folder and the studio like any other; the studio is not popped up — a hidden
studio holds the capture unseen, a visible one is shown again with it. *PrintScreen opens the editor* presents it
every time. Details: `docs/CAPTURE.md` §1–§5.

## 12. Settings (`model/settings.py`, dialog `ui/preferences.py`)

File `~/.config/linscreencapture/settings.conf` (GLib key file), groups `[Window] [Capture] [System] [Tools]`.
A 1.4 file at `~/.config/linshot/settings.conf` is migrated once on first run (colours in `rgb()` form, prefix
and numbering derived from `filename_format`, tool widths and shadows, blur block, text font) and left untouched;
`[Meta] migrated_from` records it. Every setting is written the moment it changes; window geometry on close.

| Dialog row (Capture page) | Key | Values |
| --- | --- | --- |
| Save folder (picker) | `screenshot_path` | any folder (default: the Pictures directory) |
| File name prefix | `prefix` | `LinScreenCapture_` · `Screenshot_` |
| Numbering | `numbering` | `sequence` (`_1`, `_2`, … first free number) · `timestamp` (`_2026-10-09_21-14-05`) |
| Format | `format` (+ `jpeg_quality`, default 92) | png · jpeg · webp |
| Delayed capture | `delay_seconds` | 0–60 (used while the Delayed toggle is on) |
| Start with the left / right rail collapsed | `left_collapsed`, `right_collapsed` | bool (applied live) |
| Dashed frame around the selected layer | `selection_frame` | bool, default off (handles only) |

| Dialog row (System page) | Key | Values |
| --- | --- | --- |
| Keep running in the background | `[System] keep_running` | bool, default on; applies from the next window (turning it off takes effect at the next start) |
| Panel icon | `[System] tray_icon` | bool, default on; starts or stops the helper live |
| Run at startup | `[System] autostart` | bool, default on; writes or removes the autostart entry (§1), and the switch reads the file |
| PrintScreen opens the editor | `[System] hotkey_opens_editor` | bool, default off (studio not popped up, §11) |
| Key (Capture hotkey group) | `[System] hotkey` | Off (`none`) · `Print` (default) · `<Control>Print` · `<Shift>Print` · `<Control><Shift>s` · `<Control><Alt>s` · Custom (any recorded accelerator; *Record…*) |
| Register with the desktop | `[System] register_hotkey` | bool, default on; on Cinnamon writes the binding now and at every agent start; off removes it (§1) |

Retired on 2026-10-16 and removed from the file at the next save: `[Capture] copy_to_clipboard` (every capture is
copied) and `[Capture] selection_style` (replaced by the Region and Region Plus modes).

Keys without a dialog row yet (Phase 6 pages): `backend` (auto · portal · x11 · cli), `include_pointer`,
`pin_opacity`, `reopen_last`. `[Tools]` keys are written by
the header strip and the palette: per tool `colour_*`, `width_*`, `shadow_*`, `shadow_intensity_*`, `fill_*`,
`opacity_*` for arrow, line, box, circle, text, pen, marker, eraser, step, callout, fill; shared `universal`,
`blur_block`, `blur_radius`, `text_font_family`, `text_font_size`, `text_bold`, `text_italic`, `step_size`.
`Settings.tool_style(tool)` builds a drawing `Style`; `next_filename()` applies the naming rules.

## 13. Model and services (pure Python where noted; headless tests in `tests/model/`)

| Module | Provides |
| --- | --- |
| `model/annotations.py` (no GTK) | `Style`, `Annotation` (kinds arrow, line, box, circle, text, pen, marker, eraser, step, callout, fill, blur, pixelate, image, cutout; `shape` for cutouts), Cairo painters, Gaussian shadows, whole-annotation opacity, eraser and cutout clearing (`DEST_OUT`), `area_path()`, pixelate (numpy) and blur (Pillow) on the composite, `snap45`, `constrain_square`, bounding boxes, hit tests, dict round-trip, `renumber_steps`; `NAMES` / `BADGE` |
| `model/document.py` | `Document` (base surface, ordered `Layer`s with ids and badges, dirty flag, `summary()`), `open()` / `save()` (PNG, JPEG on white, WebP), `flatten()`, exact PIL ↔ cairo conversion with alpha |
| `model/undo.py` | `UndoStack` (20 deep, redo, labels, change callback) with `AddLayer`, `RemoveLayer`, `RemoveLayers`, `MoveLayer`, `EditAnnotation`, `SetVisible`, `ReplaceBase`, `TransformBase` |
| `model/settings.py` | schema, migration, `tool_style()`, `next_filename()` |
| `model/captures_index.py` | threaded thumbnail scan of the save folder → `Gio.ListStore` newest first; unchanged folders keep the store |
| `app/image_ops.py` | crop, `crop_masked`, scale, rotate, flip, adjust — each returns the new base and a coordinate mapper |
| `app/tools.py` | drag / stroke / click / area tool tables, handles and handle drags, selection rectangles, duplicate |
| `app/shortcuts.py` | the capture-phase `ShortcutRouter` (§14) |
| `app/view_state.py` | observable zoom, rail state, tool, colour, title, library flag |
| `services/capture_service.py` | backend order by session and preference, one fall-through per backend, worker thread → main loop |
| `services/selection.py` | overlay selection geometry (handles, hit, resize, move, clamp, square) |
| `services/file_store.py` | `save_capture()`, `duplicate_file()` |
| `services/clipboard.py` | `texture_from_surface()`, `image_providers()` (`image/png` bytes + a value typed `GdkTexture`), `set_providers()` (union, then `store_async` to the clipboard manager), `copy_surface()` |
| `services/hotkey_registrar.py` | `supported()`, `register(hotkey)`, `unregister()`, `reload_cinnamon()`: the Cinnamon custom keybinding (`docs/CAPTURE.md` §4) |
| `services/clip_history.py` | `ClipHistory`: the last copies (limit 1 today), digest dedupe, ≤ 320×200 preview textures, clipboard ownership tracking |
| `services/icon_loader.py` | GResource registration, icon theme path, `icon(name, size)` |

## 14. Keyboard and mouse reference

Two tiers, so a shortcut can never steal a keystroke from a text field. **Global chords** are GTK application
accelerators. **Editing and tool keys** go through `app/shortcuts.py`, a capture-phase router on the window
that yields whenever the inline text editor, a text entry or anything inside a popover has focus, swallows tool
letters during a drag, handles chords and tool letters even with focus in a header spin button (then returns
focus to the canvas; digits, Enter, Delete and arrows still edit the number), and retargets keys to the Library
while it is open.

| Keys | Action |
| --- | --- |
| **Ctrl+N** · **Ctrl+Shift+N** | capture in the current mode · full-screen capture |
| capture hotkey (desktop; PrintScreen by default) | the fast Region capture from anywhere (`app.hotkey-capture`); registered on Cinnamon by Settings → System, bound by hand elsewhere |
| **V A L B C T P M E H** | Select, Arrow, Line, Box, Circle, Text, Pen, Marker, Eraser, Hand |
| **R O J** | Box area, Round area, Point chain |
| **U X N K** | Blur, Pixelate, Step number, Crop |
| **Ctrl+Z** · **Ctrl+Shift+Z** / **Ctrl+Y** | undo · redo |
| **Ctrl+A** | select all layers (Library: select all files) |
| **Ctrl+C** | copy the marked area, else the flattened image (Library: copy the selected files) |
| **Ctrl+V** | paste a copied layer, a clipboard image or clipboard text |
| **Ctrl+D** | duplicate the selected layer (Library: duplicate the selected files) |
| **Delete** | clear the marked area · delete all selected layers · delete the selected layer (Library: trash the selection) |
| **Enter** | crop to the marked area · apply the pending crop (Library: open) |
| **Esc** | drop the area or chain · cancel the crop · stop the eyedropper · clear the selection (Library: close) |
| **Backspace** | remove the last point of a chain in progress |
| **Space** (held) | pan with a drag; always swallowed, so it never activates a focused button |
| **Shift** / **Ctrl** while dragging | 45° snap for arrows and lines · square / round shapes and areas (Shift) · square shapes and handle drags (Ctrl) |
| **Ctrl+S** · **Ctrl+Shift+S** | save · save as |
| **Ctrl+scroll** · **Ctrl+0** · **Ctrl+1** · **Ctrl++** · **Ctrl+−** | zoom · fit · 1:1 · in · out |
| **Ctrl+[** · **Ctrl+]** | collapse / expand the left · right rail |
| **Ctrl+L** · **Ctrl+,** · **Ctrl+Q** | Library · Settings · quit |
| Mouse | left: draw / select / mark; middle drag: pan; Ctrl+scroll: zoom; double-click: edit text, close a chain, open a Library file; click on the empty stage: back to Select |

Overlay keys are listed in §11.

## 15. Developer tools

| Command | Purpose |
| --- | --- |
| `make resources` | compile `data/` and `style.css` into the GResource bundle (`linscreencapture/linscreencapture.gresource`) |
| `make icons` | re-sync the 64 Phosphor glyphs listed in `data/icons/icons.txt` from `ICON_SRC` and regenerate the manifest |
| `make run` | resources + `python3 -m linscreencapture` |
| `make test` | pytest, 105 tests (Xvfb if installed, else the live display: a window flashes) |
| `make snapshot` | render to `screenshots/dev/`: `shell_default`, `shell_open`, `shell_collapsed`, `shell_library`, `shell_text_tool`, `shell_document`, `shell_annotated`, `shell_crop`, `shell_adjust`, `shell_document_zoomed`, `shell_select_all_tray`, `shell_eraser`, `shell_area_chain`, `shell_library_multiselect`, `shell_settings` (popover contents cannot be rendered and are skipped) |
| `tools/snapshot_overlay.py` | render the live capture overlay (output git-ignored: it contains the real screen) |
| `make launcher` / `make unlauncher` | install / remove the **LinScreenCapture3** menu entry pointing at this checkout |
| `bash ~/projects/Zai-ZCode/s009_backup_project.sh …` | family backup into `~/backups/linscreencapture3/` |

Process rules (AGENTS.md): feature work on `feat/…` and `docs/…` branches; never commit real screen captures;
keep this file, `HANDOFF.md` and `changelog.md` current; never `pkill -f` a pattern that appears in the agent's
own shell.

## 16. Layout and implementation notes for agents

One entry per feature of the two review rounds after Phase 5: where it lives, how it is wired, what to keep in mind.

| Feature | Layout | Implementation |
| --- | --- | --- |
| Soft shadows | annotation shadows and the stage drop shadow | `_shadow_surface()` in `model/annotations.py`: a black silhouette blurred with Pillow, cached on the annotation by geometry and style, offset and sigma from the width; `Stage._draw_drop_shadow`: four linear + four radial gradients (stacked rectangles banded on dark captures) |
| Per-tool opacity | Opacity slider in every drawing tool's strip set | `ToolStyle.opacity` (`opacity_<tool>`), `ToolProps._opacity()` one scale per set kept in step by `_load`; `draw()` composites shadow + shape in a cairo group and `paint_with_alpha` |
| Capture delay | Delayed is the timer toggle in CAPTURE; off at every launch, mode Region | `capture_controller.capture()` reads `win.capture-delayed`; the perceived delay was python-xlib's `GetImage` parsing — `backends/x11.py::grab_root_libx11` calls libX11 through ctypes (declare `XImage.data` as `c_void_p`, free via the struct's `destroy_image`) |
| Copy / paste | Ctrl+C / Ctrl+V | `StudioWindow._copy` (area → region, select-all → flattened, layer remembered in `_layer_clip` until the clipboard "changed" from elsewhere), `_paste` → `paste_layer` / `paste_texture` / `paste_text`; `_holds_image` walks `get_gtypes()` with `GType.is_a` because `contain_gtype(Gdk.Texture)` is false for local `GdkMemoryTexture` |
| Click on the empty stage | canvas margin or scroller background | `Stage._stage_click` + `EditorController.clicked_outside`; a drag's release is ignored through `_suppress_click`, cleared on idle |
| Ctrl+Z with a tool active | — | focus stuck in a header spin's `Gtk.Text`, which binds Ctrl+Z; `ShortcutRouter` runs in the CAPTURE phase, `focus_kind()` returns text / spin / other; strip controls `focus_on_click=False`, `release_focus()` on tool switch and Enter |
| Layer rows | numbered, tool-name badge | `PanelRail.set_document` numbers by stack position; `BADGE = NAMES upper` |
| Library controls | head row Refresh · Select all · Copy · Duplicate · Delete · Open · Close; summary `k of n selected` | `Gtk.MultiSelection`, `selected_entries` from the bitset; window actions `library-select-all/copy/duplicate/delete/open`; router maps Ctrl+A/C/D, Delete, Enter, Esc while `state.library`; `file_store.duplicate_file`; Copy of one file = texture + `Gdk.FileList` + `text/uri-list` union, several = files only; `CapturesIndex._apply` keeps the store when (path, mtime) are unchanged; double-click = GridView `activate(position)` → `activated_entry` |
| Select all | dashed outline around the image and each layer | `EditorController.select_all()` / `all_selected` (cleared by `select()`, `_commit()`, tool change); `delete_selected()` commits `undo.RemoveLayers` |
| Clipboard tray | CLIPBOARD group above Library; one 116 px slot; collapsed rail: a clipboard MenuButton with the tray in a popover | `ClipHistory` (signal `changed`, `limit`, blake2b dedupe, `preview` texture ≤ 320×200, `remove()` clears the clipboard when the entry owns it); `ClipTray` slots are `Gtk.MenuButton`s (a popover popped up from a plain button's `clicked` handler was closed by the same release); `ClipPreview` actions `clip.copy/paste/delete`; pushed from `_copy`, `_library_copy`, `CaptureController._finish` |
| Transparent PNGs | checkerboard under the image | `Stage._checkerboard()` painted inside the image clip; `Document.save` pastes RGBA onto white for JPEG |
| Eraser | TOOLS row 1 after Marker, key E, own strip set | kind `eraser` (stroke): `_erase` = `OPERATOR_DEST_OUT` with the opacity as strength; `_paint_eraser_ghost` for previews and thumbnails; `settings.TOOLS` has `eraser` (default width 24) |
| Area tool | TOOLS row 2 first three buttons (`bounding-box`, `circle-dashed`, `polygon`; Blur moved to `drop-half`); keys R O J; strip hint per mode | `EditorController.area` is an `Annotation("cutout", shape=box\|round\|points)`; drag mode `area`; `_chain_click` closes within `CHAIN_CLOSE_PX` of the first point or on double-click; `area_path()` traces the region for drawing, `_cutout` (Delete layer), `area_surface()` (Ctrl+C, `DEST_IN`) and `image_ops.crop_masked` (Enter); router: Esc → `cancel_area`, Backspace → `chain_pop`, Enter → `apply_crop` (area first), Delete → `delete_selected` (area first); a tool switch cancels |
| Shortcut captions | two-line tooltips everywhere | `widgets.tooltip_with_key()`, `rail_button(key=…)`, `tool_rail.Item.key` from `shortcuts.KEY_FOR_TOOL`; `get_tooltip_text()` returns `"Caption\nKey"` |
| Panning | Hand tool, Space, middle button; cursors grab / grabbing | editor mode `pan` with deltas in stage-scroller coordinates (`_to_scroller`) so scrolling never feeds back into the drag; `Stage.scroll_by(dx, dy, origin)`; middle button = `Gtk.GestureDrag(button=2)` on the scroller; Space = `set_space_pan()` from the router's press / release and on window deactivate |
| Space toggled the right rail | not intended | initial focus sat on a rail button; the window focuses the canvas on map and the router swallows Space everywhere |
| Snapshot tool | `make snapshot` | `Application(non_unique=True)`; `render_widget()` skips widgets without a render node (popovers) |
