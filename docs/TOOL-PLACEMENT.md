# Studio tool placement — 2026-10-09

Living copy: https://claude.ai/code/artifact/88f20a07-5c23-4967-b974-cbbbf1c4a867

Each zone has one job: the **left rail starts things** (capture, pick a tool), the **header tunes the tool in
hand**, the **right rail manages the result** (layers, colour, view, output).

| Control | Was | Now | Does |
| --- | --- | --- | --- |
| Capture | header, top-left | top of the left rail, full-width accent button (icon when collapsed) | `app.capture-region` in the selected mode |
| Tool properties | right rail, Props tab | header centre strip, follows the active tool | width, shadow, intensity, fill, font, size, bold, italic, blur mode/block, hints |
| Zoom −/value/+/Fit | header right | right rail, `VIEW` | `win.zoom-out/in/fit`; the stage HUD mirrors the value |
| Copy, Flatten | left rail Actions | right rail, `EDIT` | `win.copy`, `win.flatten` |
| Discard, Library, Save | left rail Actions | unchanged | clear, Library page, save |
| Layers | right rail tab | right rail, first group (no tabs) | list with thumbnails, badges, visibility |
| Colour, Navigator, Settings | right rail | unchanged | swatches; overview; Settings |
| Rail carets | double chevrons | single `caret-left` / `caret-right` | point the way the rail will move |

## Left rail

Top row: **Capture** + collapse caret `<`. `CAPTURE`: Region, Window, Full screen, Scrolling, Delayed, Pin
(one mode active). `TOOLS`: Select, Arrow, Line, Box, Circle, Text, Pen, Marker; then Blur, Pixelate, Fill,
Step, Callout, Crop, Resize, Rotate, Brightness, Move, Duplicate. `ACTIONS`: Discard, Library, Save. Collapsed:
caret `>`, Capture icon, three modes, seven tools (active always present), Discard, Save.

## Header tool-properties strip (`ui/tool_props.py`)

| Tool | Title | Controls |
| --- | --- | --- |
| Arrow, Line | ARROW / LINE | Width 1–20, Shadow, Intensity 0–1 |
| Box, Circle | BOX / CIRCLE | Width, Shadow, Intensity, Fill |
| Pen, Marker | PEN / MARKER | Width, Shadow; hint "Marker paints at 4× width, 40 % opacity" |
| Text, Callout | TEXT / CALLOUT | Font, Size 6–96, B, I, Shadow |
| Step number | STEP NUMBER | Badge size; hint |
| Fill | FILL | hint |
| Blur, Pixelate | BLUR / PIXELATE | Mode (Pixelate│Blur, preselected), Block 2–32 |
| Crop | CROP | hint "Drag to crop · Enter applies · Esc cancels" |
| Select, Move | SELECT / MOVE | hint "Click to select · drag to move · Delete removes · Ctrl+D duplicates" |

Controls are 28–30 px tall so the header stays 52 px. Colour stays in the right rail because every tool shares
it. Phase 4 binds each control to `Settings.tools[tool]` / text / blur settings; the Universal switch moves to
Settings.

## Right rail

`LAYERS` list → hairline → `COLOUR` (12 round swatches, custom, eyedropper) → hairline → `VIEW` (zoom pill: −,
value, +, Fit) → `EDIT` (Copy, Flatten) → spacer → `NAVIGATOR` → `Settings` bottom-right. Collapsed: caret `<`,
six colour dots, eyedropper, −, +, Fit, Copy, Flatten, spacer, gear.

## Carets

`caret-left` / `caret-right` (Phosphor regular) replace the double chevrons. Open rails show the caret that
collapses them (left rail `<`, right rail `>`); collapsed rails show the caret that expands them (`>` / `<`).

## Verification

`make test` → 50 pass (header strip switches with the tool, Capture first in the left rail, zoom and Copy/Flatten
in the right rail and absent from the left, only single-chevron carets). `make snapshot` → `shell_open.png`,
`shell_collapsed.png`, `shell_library.png`, `shell_text_tool.png`.
