# Studio shell adjustments — 2026-10-08

Living copy: https://claude.ai/code/artifact/cbe0b9ea-f751-41eb-9c3d-6861d47ad98e

Six operator-requested adjustments to the Phase 1 shell. All in the `ui/` layer plus one new
stateful action; the model and the capture plan are untouched.

| # | Change | Before | After | Where |
| --- | --- | --- | --- | --- |
| 1 | Capture button | far right of the header | first element of the header (top-left) | `ui/header_bar.py` |
| 2 | Status chip | `● Ready` beside the title | removed; status via toasts and (from Phase 3) the subtitle | `ui/header_bar.py` |
| 3 | Header text | `No capture` / `Press PrintScreen or click Capture · Pictures` | `LinScreenCapture`, no subtitle until a document exists | `app/view_state.py` |
| 4 | Settings | `Preferences…` at the bottom of the Props page | `Settings` text button bottom-right of the right rail on every page; gear at the bottom of the collapsed rail | `ui/panel_rail.py` |
| 5 | Colour | card with 54×34 foreground well, hex label, square 6×2 swatches, hex entry | no card: `COLOUR` label row with custom-colour (`+`) and eyedropper buttons, 18 px round swatches 6 per row, accent ring on the current one; collapsed rail shows six dots | `ui/panel_rail.py`, `ui/widgets`, `ui/style.css` |
| 6 | Captures panel | third right-rail tab | **Library**: a full-stage page (180×120 thumbnails, name, date; Open / Delete / Refresh / Close); left-rail `Library` toggle, Ctrl+L; right rail keeps Layers and Props | `ui/library_page.py` (new), `ui/stage.py`, `ui/tool_rail.py`, `ui/studio_window.py` |

Naming: **Library** over Screenshots — the window is the Studio and a studio keeps a library;
"Screenshots" would repeat the app's own name and exclude images opened from elsewhere.

## Actions

| Action | Kind | Change |
| --- | --- | --- |
| `win.panel` | stateful string | values `layers`, `props` |
| `win.library` | stateful boolean (new) | toggles the Library page; left-rail toggle, Ctrl+L, the page's `×` |
| `win.library-open`, `win.library-delete` | new | toast "arrives in Phase 5"; Open also on double-click |
| `win.library-refresh` | new | rescans the save folder (also runs when the page opens) |
| `win.custom-colour` | new | placeholder for `Gtk.ColorDialog`, Phase 4 |
| `app.preferences` | unchanged id | label and toast read `Settings` |

## Colour palette spec

18 px circles in a `Gtk.Grid`, 6 per row, 8 px gaps; `Gtk.ToggleButton`s in one group; rest = the colour
with a 1 px inset highlight at 12 % white; hover = 2 px ring at 35 % text colour; current = 2 px accent ring,
2 px offset. Collapsed rail: the first six colours in one column, 10 px apart. The current hex is shown in the
custom-colour button's tooltip; it is no longer typed by hand.

## Library page spec

Head: 52 px surface bar, `Library` (14/500) over `N screenshots · ~/Pictures`, spacer, Refresh and Delete
(30 px icon buttons), `Open` (accent primary), `×`. Grid: `Gtk.GridView`, 14 px padding, 2–12 columns;
cell = 180×120 cover-fit thumbnail (6 px radius), file name (12 px, middle-ellipsised), date
`Oct 8, 2026 · 21:14` (11 px muted); hover surface 60 %, selected accent-soft. Empty state: `images` glyph +
`No screenshots yet in ~/Pictures`, Open insensitive. Model: the existing `CapturesIndex` store. The header title
reads `Library` while the page is open; the zoom HUD hides.

Phase 5 will make Open load the file as a document (prompting for unsaved changes) and Delete move to the
trash after confirmation.

## Verification

`make test` → 16 pass (header order, no chip, palette ring sync, Library toggle and title, Settings last and
right-aligned). `make snapshot` → `screenshots/dev/shell_open.png`, `shell_collapsed.png`, `shell_library.png`,
`shell_props.png`. Check by hand: grid reflow while resizing; Ctrl+L while a spin button has focus.
