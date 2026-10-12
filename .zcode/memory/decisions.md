# Decisions

Record architectural decisions with rationale. Newest at the bottom.

Authoritative full list with rationale: HANDOFF.md §4 and docs/GUI_SPEC.md. Condensed index:

- 2026-10-08 Pure Python; a single C function via ctypes only after profiling shows a budget miss (spec §5).
- 2026-10-08 The 52 px header IS the title bar (client-side decoration); window buttons follow gtk-decoration-layout.
- 2026-10-08 Rails 220 px open / 56 px collapsed; auto-collapse below 1100 px unless toggled by hand; min window 960×600.
- 2026-10-08 Region uses the `selection` glyph, Crop keeps `crop` (only mockup deviation).
- 2026-10-08 Default file-name prefix `LinScreenCapture_` (was `LinShot_`).
- 2026-10-08 Old C sources stay as behavioural reference until Phase 5 parity, then are deleted.
- 2026-10-08 Placeholder actions toast "X arrives in Phase N" — every button wired from day one.
- 2026-10-08 Shell adjustments round 1: Capture top-left, no status chip, name-only title pre-capture, Settings bottom-right, round swatches, Library full-stage page (Ctrl+L).
- 2026-10-09 Tool placement round: Capture tops left rail; tool properties are a contextual header strip; zoom/fit and Copy/Flatten in right rail; no Props tab.
- 2026-10-09 Review round (post Phase 3): rails collapsed by default; Capture 30 px accent icon; stage paints capture pixel-exact; navigator live; right rail order Colour, View, Edit, Layers, navigator, Settings.
- 2026-10-09 Settings dialog (Capture page only until Phase 6); selection_style drives OverlaySession.simple.
