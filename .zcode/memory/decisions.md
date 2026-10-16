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
- 2026-10-13 Review round (post Phase 5): shadows are Gaussian (annotations: blurred silhouette; stage: gradients) — stacked-copy shadows banded; Opacity is a per-tool strip control (never universal; marker 0.4); Delayed is a toggle on the capture modes, not a mode; layers are numbered and labelled by tool name; the ShortcutRouter runs in the CAPTURE phase so Ctrl+Z/tool letters survive focus in a header spin button; a click on the empty stage returns to Select; Ctrl+V pastes text as a text layer and a copied layer as a duplicate.
- 2026-10-13 Review round 2: X11 grab via libX11 ctypes (python-xlib get_image = the 3 s "delay"); Library is multi-select with Copy/Duplicate/Delete that touch files only; Ctrl+A = all layers, Ctrl+C = flattened image; a clipboard tray (last 3 app copies, MenuButton slots + preview popover) lives above Library in the left rail; eraser = DEST_OUT stroke kind, stage shows a checkerboard; tooltips carry the shortcut; pan = Hand tool / Space / middle button; Space is always swallowed by the router. Same night: tray = one slot (multi-slot on the roadmap); Area tool (Box area / Round area / Point chain, keys R O J) marks a region for Ctrl+C / Enter crop / Delete clear — its vocabulary deliberately avoids marquee/lasso/select/path/pen.
- 2026-10-16 Background agent: the primary instance is the agent (hold() while keep_running; closing the studio hides it). PrintScreen = app.hotkey-capture = a quiet region capture to the clipboard + save folder that never loads the editor and leaves the studio as it was; the editor flow is opt-in (hotkey_opens_editor). The tray icon is a separate GTK 3 process (tray.py) because GTK 4 has no status-icon API and GTK 3/4 cannot share a process; it talks to the agent only over D-Bus actions and exits when the bus name vanishes. The GTK clipboard is owned by the agent process, so the agent must stay resident for pastes to work.
