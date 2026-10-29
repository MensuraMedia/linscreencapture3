# Clipboard tray: the last four copies as a 2 × 2 grid (technical concept)

Status: **implemented** 2026-10-18 on `feat/clip-tray-4up` (drafted by the GLM worker, reviewed and completed by
Claude). Beyond the concept: the cells are `CellPicture`s that report no natural size; with plain `Gtk.Picture`s
four 192 × 108 thumbnails stretched the tray from 116 to 240 px (caught by the §5 test).
This is the roadmap item "clipboard tray with several slots" (HANDOFF §8, backlog), which the code already
parametrises (`ClipHistory.limit`, `clip_tray.SLOTS`).

## 1. What the user sees

The clipboard box in the left rail, above Library, keeps its size: 116 px high (`TRAY_HEIGHT`, the navigator's
height) across the open rail. It is cut into **quarters**: four thumbnails in a 2 × 2 grid, newest top-left, then
top-right, bottom-left, bottom-right.

```
┌─────────────┬─────────────┐
│  newest (1) │      2      │     each cell ≈ 96 × 54 px of picture
├─────────────┼─────────────┤     (rail 220 px − padding; 116 px tall box)
│      3      │   oldest(4) │
└─────────────┴─────────────┘
```

- A filled cell shows the copy scaled to fit (letterboxed, never stretched). Its tooltip reads
  "Copy · 1920×1080 · 14:05 · click for a larger preview".
- The cell whose image is on the system clipboard right now has the accent border (`.current`). After another
  application copies something, no cell is current.
- Empty cells are dashed placeholders. The first empty cell's tooltip reads "Copies you make appear here".
- A click opens the existing preview popover for that cell (`ClipPreview`): the larger sample, then Copy / Paste /
  Delete. Copy puts the image back on the clipboard and moves it to the newest cell.
- A fifth copy pushes the oldest out. The same pixels copied again move to the newest cell instead of being
  duplicated (`ClipHistory.push` already deduplicates by digest).
- Collapsed rail: the 30 px clipboard button's popover holds the same 2 × 2 tray, sized 200 × 116
  (`ClipTrayButton`). Its tooltip reads "Clipboard · the last 4 copies".

## 2. Current implementation

| Piece | File | Today |
| --- | --- | --- |
| History | `services/clip_history.py` | `LIMIT = 1`; entries newest first; each holds the full `surface`, a full-size `texture` and a ≤ 320×200 `preview` texture |
| Tray | `ui/clip_tray.py` | `SLOTS = 1`; `ClipTray` is a horizontal homogeneous `Gtk.Box` of `Gtk.MenuButton` slots, each owning a `ClipPreview` popover |
| Rail | `ui/panel_rail.py` | open width 220 px, collapsed 56 px |
| Style | `ui/style.css:184` | `button.clip-slot` dashed / `.filled` / `.current` |

Slots are `Gtk.MenuButton`s on purpose: a popover popped up by hand from a plain button's `clicked` handler was
closed again by the same button release on X11 (HANDOFF §6). Keep that.

## 3. Changes

1. **History size.** `clip_history.LIMIT = 4`. No other change in `ClipHistory`: `push`, `copy`, `remove` and
   `is_current` already handle several entries.
2. **Grid layout.** `ClipTray` becomes a `Gtk.Grid` with `row_homogeneous` and `column_homogeneous`, a 4 px
   row and column spacing, and `SLOTS = 4` cells at `(n % 2, n // 2)`. The box keeps `set_size_request(-1,
   TRAY_HEIGHT)` and `vexpand=False`. The cells' `Gtk.Picture`s keep `can_shrink=True` and
   `content_fit=CONTAIN`, so they cannot stretch the rail (HANDOFF §6, `hexpand` pitfall).
3. **Thumbnail texture.** Each cell is about 96 × 54 px, and the 320 × 200 `preview` texture scaled down by GTK at
   every frame is acceptable for four cells. For sharper results add a `thumb` texture (≤ 2 × cell size, 192 × 108)
   made in `push` with the same `preview_surface` helper. The popover keeps `preview`.
4. **Labels.** Tooltip strings as in §1. `ClipTrayButton` says "the last 4 copies". The module docstrings drop
   "one for now".
5. **CSS.** `button.clip-slot` keeps its rules. Add `padding: 1px` and `border-radius: 5px` for the smaller cells,
   and keep `.current` as the accent border, the only marker of the live clipboard entry.
6. **Keyboard / a11y.** Each cell gets an accessible label "Clipboard copy N of 4, W×H, HH:MM" (empty: "Empty
   clipboard slot N"). Tab order is reading order. Cells do not take focus on click, consistent with the rails.

## 4. Memory

Four entries hold up to four full surfaces plus textures. For 2560 × 1440 captures that is about 4 × 14.7 MB
(surface) + 4 × 14.7 MB (texture) ≈ 118 MB at worst. Acceptable on the target machines, and bounded by `LIMIT`.
If that is too much, drop the full-size `texture` and create it on demand in *Paste* (`clipboard.texture_from_surface`
is cheap compared with a paste). Measure before changing.

## 5. Tests (`tests/test_shell.py` / `tests/test_clip_tray.py`)

- Push five distinct surfaces: the tray shows the last four, newest at cell 0; the oldest is gone from history.
- Push a duplicate of entry 3: it moves to cell 0; history length stays 4.
- `remove` of the current entry clears the clipboard and leaves three filled cells, one dashed.
- The tray's allocated height stays `TRAY_HEIGHT` with four large (4000 × 3000) entries; the rail width stays
  `OPEN_WIDTH` (guards the stretching pitfall).
- Clicking cell 2 pops its popover with that entry (`ClipPreview.entry is history.entries[2]`).
- Collapsed rail: `ClipTrayButton.tray` has four cells.

## 6. Open questions

1. Order: newest top-left in reading order (recommended), or newest bottom-right?
2. Should copies made by other applications appear too? Today they are not tracked on purpose, because reading the
   clipboard on every change is intrusive (`clip_history.py` docstring). Recommended: keep it that way.
