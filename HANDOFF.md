# HANDOFF — LinScreenCapture 3 (linscreencapture3)

Written 2026-10-08 after Phase 1, kept current through Phase 6 work of 2026-10-16. Read this first; it says where everything is, what was
decided, and what to do next. The spec (`docs/GUI_SPEC.md`) is authoritative for the GUI;
this file is authoritative for process and state.

## 0. Where things stand (2026-10-16)

Current: Phases 1–5 done; **Phase 6 in progress** on branch `feat/background-agent` (from `feat/phase5`), uncommitted
work on top of the pushed agent commits. Done in Phase 6 so far: background agent, tray helper, hotkey capture,
autostart, Settings **System** page, Cinnamon hotkey registrar (`services/hotkey_registrar.py`), the **Region Plus**
mode, and the clipboard fix (captures offered no image format on X11). Capture behaviour is specified in
`docs/CAPTURE.md`, which is authoritative. Tests: 117 pass; 2 cosmetic window-geometry failures under Xvfb
(`test_window_geometry`, `test_close_saves_settings`: 1350 vs 1360 px) predate the branch. Next: countdown chip, pin,
scrolling capture, registrar for other desktops, the rest of the System page and the Shortcuts page (§8), then the
operator's on-screen sign-off.

History (2026-10-09):

Phases 1–5 are done: shell, model + settings migration, capture (X11 verified live; portal and CLI backends
written), annotation tools with live layers and undo, image operations and file flows. The legacy C sources are
deleted. Work is on branch `feat/phase5` (push it, open the PR into `main` when the operator signs off). Next:
Phase 6, system integration (checklist in section 8). The operator reviews renders and asks for layout tweaks between
phases; expect that and keep `docs/FEATURES.md`, this file and `changelog.md` current with every change.

Update 2026-10-12: work continues on branch `feat/phase5` (cut from the docs/app-screenshots tip e9d017c; main itself
untouched). The repo is now bootstrapped with the universal standards: `AGENTS.md` at the root (stack + project rules),
`.zcode/memory/` seeds. Test state: 77 tests, 76 pass — the one failure is the uncommitted ShortcutRouter work
(`tests/test_shell.py:438`, Escape handling in `app/shortcuts.py`), which predates this branch and travels uncommitted.
Still unpushed/awaiting review: the three docs/app-screenshots commits and the s049 i18n doc on docs/i18n-strategy.

Update 2026-10-13 (evening): Phase 5 review round applied on `feat/phase5` — Gaussian annotation shadows and a
gradient stage shadow (the stacked-rectangle shadows banded), per-tool Opacity in the header strip, Delayed capture
as a toggle (it could not be turned off before), Ctrl+V of clipboard text as a text layer and Ctrl+C/Ctrl+V of a
selected layer, click on the empty stage drops the tool, numbered layers with tool-name labels, and the Ctrl+Z
regression (focus stuck in a header spin button) fixed by a capture-phase shortcut router. 94 tests pass.

Update 2026-10-13 (night): review round 2 on `feat/phase5` — the "3 s capture delay" was python-xlib parsing the
`GetImage` reply (3.5 s for 2560×1080); the X11 grab now goes through libX11 via ctypes (≈50 ms). Library has
group selection with Copy / Duplicate / Delete and double-click open; Ctrl+A selects all layers and Ctrl+C copies the
flattened result; a clipboard tray (last three copies, preview popover with Copy / Paste / Delete) sits above
Library in the left rail; transparent PNGs (checkerboard, alpha-preserving save) and an Eraser tool; tooltips show
the shortcut under the caption; Hand tool / Space / middle button pan the view; Space no longer activates a focused
rail button. Follow-up the same night: the tray is reduced to **one slot** (more slots = roadmap item in §8) and an
**Area tool** (Box area R, Round area O, Point chain J) marks a region for Ctrl+C / Enter (crop) / Delete (clear);
its vocabulary avoids other editors' terms. 105 tests pass. Per-feature layout/implementation notes: `docs/FEATURES.md` §16.

Update 2026-10-14: `docs/FEATURES.md` rewritten as the complete 16-section feature reference; the dashed frame around a
selected layer is off by default (handles only; corner ticks for handle-less layers; `Settings.selection_frame` and a
Settings → Window switch restore it). 106 tests. Awaiting the operator's on-screen sign-off and the PR into `main`.

## 0a. 2026-10-18 — branch `fix/tray-alttab-icons` (second machine)

Two machines work on this repository; pull before a session, push after it. Branch `fix/tray-alttab-icons` is cut
from `feat/phase5` at `01f5606` (the other machine's icon / installer / .deb work). It adds:

- `docs/ICONOGRAPHY.md`: the one application icon (master SVG + eight PNG renders, theme name `APP_ID`), its
  placement (menu, panel window list / Alt+Tab, tray, Startup Applications) with the recognition requirement for each,
  and rules. Linked from README and FEATURES.
- Fix: the autostart entry still wrote `Icon=linscreencapture3`, the retired theme name that `make launcher` now
  deletes, so Startup Applications showed a blank icon. It writes `Icon=<APP_ID>`; `test_agent` asserts it.
- Fix: **`make test` deleted the real `~/.config/autostart/<APP_ID>.desktop`**, so Run at startup silently went off
  on the development machine after every test run (and the app then honours the missing entry as "off").
  `install.sh --uninstall --destdir …` (run by `test_install_script_uninstalls`) removed `$HOME`'s autostart entry
  even when staging; it now skips `$HOME` under `--destdir`. Also `PreferencesDialog` defaulted `autostart_root` to
  the real config dir; it now defaults to `settings.root`. Guarded by
  `test_staged_uninstall_leaves_the_users_autostart_entry_alone` (fake `HOME`) and
  `test_preferences_autostart_switch_stays_in_the_settings_root`. Verified with a sentinel entry over the full suite.
- `tools/launch.sh` and `ui/style.css` header comments say LinScreenCapture 3; §8.0 points at the real tray icon file.

The same machine had found the tray (`tray.py` prgname) and `WM_CLASS` bugs independently; the other machine's
commits fixed both first, so that work was dropped in the rebase (kept locally as tag
`backup/fix-tray-alttab-icons-pre-rebase`). On this machine every earlier build (1.4 `linshot3`, LinScreenCapture2,
`gnome-screenshot`) was removed after a tar backup in `~/backups/`; `xvfb` is not installed here, so `make test`
uses the live display. The app on this machine is installed with `./install.sh` (`~/.local`); re-run it after a pull.

**Editor work, same day — branch `feat/editor-shadows-canvas`** (from `docs/editor-paste-shadow-concepts`, with
`fix/tray-alttab-icons` merged in). Full account: `docs/CHANGES-2026-10-18.md`.

- The arrow no longer fades while being drawn: the 60 % preview cap in `_draw_overlay` is gone; while drawing only
  the shadow waits for release (a shadow blur per motion measured 16–21 ms on large shapes).
- A Shadow switch on every marking tool: `SHADOW_KINDS` + `step`, `callout` (its switch was dead), `image`;
  new switches in the Step and Image strip sets.
- Pasted images cast a shadow of their own alpha (sigma 6 / offset 4), on by default (`[Tools] shadow_image`,
  `Settings.STYLED`, never universal), baked by flatten / save / copy. The blurred silhouette is cached module-wide by
  shape relative to the layer's origin, so moves reuse it.
- Page growth: an image layer pasted or moved past the page grows it to its painted extent + `EXPAND_PADDING` (20 px)
  in the same undo step (`EditorController._grow_page_for` from `_commit`, `UndoStack.amend` / `Compound`,
  `document.expansion_for` / `expanded_base`, `MAX_PAGE` 16384). Pastes are 1:1; Fit fits the image with its shadow.
- 144 tests. Design: `docs/EDITOR-SHADOWS-AND-PREVIEW.md`, `docs/EDITOR-CANVAS-EXPANSION.md` (differences from the
  design at the top of each). The 4-up clipboard tray (`docs/CLIPBOARD-TRAY-4UP.md`) is on `feat/clip-tray-4up`
  (rebased onto `feat/editor-shadows-canvas`; GLM draft, reviewed and completed; 150 tests).

**Branch `feat/stage-rotate-fill`** (stacked on `feat/clip-tray-4up`; PR #4, base `feat/clip-tray-4up`):
- Pasted images rotate: `Annotation.angle` (degrees clockwise about the rect centre; image layers only), drawn by
  `annotations._image_frame`, hit-tested on the turned picture, bounding box = turned extent; `TransformBase` now
  saves and restores `angle`; a page rotation turns image layers (`_image_transformed`) instead of stretching them.
  Canvas: a round rotate handle above the top edge (`tools.handles_for(a, zoom)`, `image_rotate`, Shift 15°);
  turned resize along the picture's own sides (`image_resize_turned`). Strip: a `↻ N°` popover button.
- Round selection handles (`HANDLE_PX` 9).
- Page size, fill and stage colour: the **Page dialog** (`ui/page_dialog.py`, from EDIT's `win.page-settings`;
  first built as an in-rail PAGE group, replaced at the operator's request): size with an anchor
  (`document.resized_page(…, anchor)`), fill (`Document.background`, `SetPageFill`, painted first by
  `Document.render`), stage colour (`Stage.set_stage_colour`, a display CSS provider); Apply = one undo step
  (`EditorController.apply_page`). Settings `[Stage] colour`, `page_fill`.
- Clipboard tray: double-click pastes (`ClipTray._pressed`, capture-phase `GestureClick`; single click pops the
  preview after the double-click time).
- Fixes found on the way: after Ctrl+Z / Ctrl+Y the header strip still showed the old values (`refresh_document`
  now calls `ToolProps.reload`); a selected image forced the window to 1450 px wide (the strip now scrolls in the
  header, title / subtitle ellipsize).
- 173 tests (`cde6405`). Then, at the operator's request, the **Layers list was removed**: the EDIT group has four
  arrange buttons (to front, forward, backward, to back; `win.layer-*`, Ctrl+(Shift+)Page Up / Down, enabled only
  when the selected layer can move that way), Ctrl+click picks the layer beneath the selected one, `LayerRow` and
  the layer thumbnails are deleted; 175 tests (`e816c44`). Then the Page group moved into the Page dialog and the
  arrange buttons got their own ARRANGE group with the app's own glyphs (`data/icons/custom/`, bundled by
  `tools/sync_icons.py`); 177 tests.
- Then: no stage shadow around the page (`Stage._draw_drop_shadow` deleted); Page button beside Fit in VIEW; the
  right rail's bottom is hairline + SETTINGS label + gear button, level with the left rail's ACTIONS line (a test
  checks open and collapsed); 179 tests.
- Library rework: toggle at the right rail's top right (`PanelRail.library_btn`), the rail's middle is a Stack
  (`editor` / `library`, sized by the visible page — a homogeneous stack let the hidden panel widen the rail) with
  `ui/library_panel.py`; Library page head = search (Gtk.FilterListModel + CustomFilter on name or tag), Open,
  Close; right-click PopoverMenu; tags `services/tags.py` (tags.json in the XDG data dir); Combine
  (`StudioWindow.combine`, `app/tiling.py`: grid, 10 px gap and margin, best column count by waste + 16:9 shape);
  Rename (F2, `rename_file`); Show in folder (`Gtk.FileLauncher`). Pitfall: on Library open the search field took
  focus and swallowed tool keys, Esc and F2 — the grid is focused instead. 193 tests.
- Change report: `docs/CHANGES-2026-10-18.md` §4.6–4.10.

**Merge order** (PRs opened 2026-10-18): #1 `fix/tray-alttab-icons` → `feat/phase5` first (without it `make test`
deletes the real autostart entry), then #2 `feat/editor-shadows-canvas` → `feat/phase5` (contains the docs branch),
then #3 `feat/clip-tray-4up` (based on `feat/editor-shadows-canvas`; retarget it to `feat/phase5` if #2's branch is
kept after merging). `gh` in this checkout resolves to the archived `MensuraMedia/linscreencapture`; pass
`-R MensuraMedia/linscreencapture3`. Installed on this machine from `feat/clip-tray-4up`. Open questions for the operator:
`docs/CHANGES-2026-10-18.md` §6.

## 1. Mission

Rebuild the 1.4 C/GTK3 screenshot tool as **LinScreenCapture 3: Python 3 + GTK 4 + libadwaita**,
reproducing the Studio Editor design (header, two mirrored rails, stage, right-rail panels) in
the Graphite Night look. Pure Python, no C extension (decided 2026-10-08; rationale and the
performance budget are in the spec, section 5). Local-only tool; no cloud, no telemetry.

## 2. Ground truth

| Fact | Value |
| --- | --- |
| Repo | `/home/user/projects/linscreencapture3`, remote `origin` = `github.com/MensuraMedia/linscreencapture3` (branch `main`); `upstream` = the 1.4 repo `MensuraMedia/linscreencapture` |
| Last pushed commit | see `git log --oneline -1`; everything is committed and pushed at the time of writing |
| Run | `make resources && python3 -m linscreencapture` (add `--debug` or `LSC_DEBUG=1` for timestamped start-up, toolkit and capture logging via `app/logging_setup.py`) (or the menu entry **LinScreenCapture3**, installed by `make launcher`) |
| Test | `make test` → 119 tests on 2026-10-16 (117 pass; §0), headless model tests in `tests/model`, shell and agent tests in `tests/`. `make test` runs under `xvfb-run` (installed); without it, tests and `make snapshot` run on the live display and flash a window |
| Renders | `make snapshot` → `screenshots/dev/shell_*.png` (default, open, collapsed, library, text tool, document, document zoomed, settings); `tools/snapshot_overlay.py` renders the live capture overlay to `screenshots/dev/overlay.png` (git-ignored: it contains the real screen) for comparison with `screenshots/01_*.png` and `02_*.png` |
| Design canvas | https://claude.ai/artifact/NTRyK2yrrpnhbW6sUmnBoA (9 artboards; sources in `docs/mockups/`, generator `docs/mockups/gen_mockups.py`) |
| Spec | `docs/GUI_SPEC.md` (repo copy) and the living doc https://claude.ai/code/artifact/5e6387bf-76b0-45f6-9874-a6ba13f90732 |
| Feature reference | `docs/FEATURES.md` — every implemented function, action, key, setting and module (update it with each phase) |
| Change notes | `docs/SHELL-ADJUSTMENTS-2026-10-08.md`, `docs/TOOL-PLACEMENT.md` (operator review rounds) |
| Local changelog | `changelog.md` (git-ignored by the family convention; keep it updated every session) |
| Backups | `~/backups/linscreencapture3/<YYYYMMDD-HHMMSS>_linscreencapture3.tar.gz` + `backup-log.md`, via `bash ~/projects/Zai-ZCode/s009_backup_project.sh /home/user/projects/linscreencapture3 -m "..."` after every completed phase |
| Icons | Phosphor regular, 51 glyphs committed under `data/icons/scalable/actions/lsc-*-symbolic.svg`; re-sync with `make icons` from `~/projects/assets/icons/regular` |
| Settings | `~/.config/linscreencapture/settings.conf` (Phase 1 keys: window size/maximised, rail collapsed flags, save folder); legacy 1.x file `~/.config/linshot/settings.conf` read for the save folder until the Phase 2 migration |
| Dev machine | Linux Mint Cinnamon on X11, GTK 4.14.5, libadwaita 1.5, Python 3.12, PyGObject 3.48, pycairo, Pillow 10.2, numpy, python-xlib, xdg-desktop-portal 1.20 |

## 3. Phase plan and status

Each phase is gated on the operator's sign-off of the previous one.

| # | Phase | Scope | Status |
| --- | --- | --- | --- |
| 1 | Layout shell | window, CSD header, rails open/collapsed, auto-collapse, stage placeholder, static panels, icon pipeline, CSS, tests | **done** (commit "Phase 1: Studio layout shell") — awaiting on-screen sign-off |
| 2 | Model and settings | `Document`, `Annotation` dataclasses + Cairo draw (port `src/editor_tools.c`), `UndoStack` (20), full `Settings` schema + 1.x migration | **done** (commit "Phase 2: model and settings") — awaiting sign-off |
| 3 | Capture | backends (portal, X11 bulk copy, CLI), `CaptureService`, overlay window, `FileStore`, clipboard, `--capture` activation, live subtitle | **done** (commit "Phase 3: capture") — awaiting sign-off |
| 4 | Annotation tools and layers | stage draws the document; all tools; handles; Layers panel live; colour and props wired | **done** (commit "Phase 4: annotation tools") — awaiting sign-off |
| 5 | Image operations and files | crop/resize/rotate/brightness, flatten, save/save-as/paste, unsaved prompts, Library delete, eyedropper; legacy C sources removed | **done** (commit "Phase 5") — awaiting sign-off |
| 6 | System integration | hotkey registrar (GNOME append fix), autostart, delayed countdown chip, pin to screen, scrolling capture, Settings System + Shortcuts pages | **in progress** on `feat/background-agent`: agent, tray, hotkey capture, autostart, System page (partial), Cinnamon registrar, Region Plus, clipboard fix done; countdown, pin, scrolling, other-desktop registrar, Shortcuts page to do |
| 7 | Polish and release | navigator live, shortcuts window, about, toasts, golden-image tests, packaging, tag 3.0.0 | |

The full phase table with gate criteria is in `docs/GUI_SPEC.md` section 10 and the README roadmap.

## 4. Decisions in force

1. Pure Python; a single C function via ctypes only after profiling shows a budget miss (spec §5).
2. The 52 px header **is** the title bar (client-side decoration). Window buttons follow
   `gtk-decoration-layout` minus the icon/menu tokens; GTK hides them under server-side decoration.
3. Rails: 220 px open / 56 px collapsed; auto-collapse below 1100 px (`Adw.Breakpoint`) unless the
   user toggled by hand this session; minimum window 960×600; state persisted.
4. One deviation from the mockup: Region uses the `selection` glyph, Crop keeps `crop`.
5. Default file-name prefix is `LinScreenCapture_` (was `LinShot_`). The only remaining
   `linshot` strings are the labelled legacy config path.
6. The 1.4 C sources were removed in Phase 5 (they remain in the original repository).
7. Placeholder actions toast "X arrives in Phase N" so every button is wired from day one.
8. Shell adjustments (2026-10-08, `docs/SHELL-ADJUSTMENTS-2026-10-08.md`): Capture top-left, no status
   chip, name-only title until a capture exists, `Settings` bottom-right of the right rail, round colour
   swatches with no card/well/hex entry, and **Library** (full-stage page, Ctrl+L) instead of a Captures panel.
9. Tool placement (2026-10-09, `docs/TOOL-PLACEMENT.md`): Capture tops the left rail; tool properties are a
   contextual header strip (`ui/tool_props.py`); zoom/fit and Copy/Flatten live in the right rail; no Props tab;
   single-chevron carets.
10. Review round 2026-10-09 (after Phase 3): both rails **collapsed by default** (auto-collapse restores the prior
    state when the window widens again); Capture is a 30 px accent icon in both rail states, never full width;
    the stage paints the capture pixel-exact with square corners (shadow outside only); the navigator is live
    (thumbnail + viewport rectangle, click/drag scrolls) and has no title; Library sits just above the Actions
    hairline in both rail states; right rail order is Colour, View, Edit, Layers, navigator, Settings.
11. Settings dialog (`ui/preferences.py`): **Capture** page (save folder, prefix, numbering, format, delay, window
    switches) and **System** page (Background agent: keep running, tray, start at login, PrintScreen opens the
    editor; Capture hotkey: key preset, register with the desktop). Retired 2026-10-16: `copy_to_clipboard` (every
    capture is copied) and `selection_style` (replaced by the Region and Region Plus modes; `OverlaySession.simple`
    now follows the mode).
12. Shortcut routing (2026-10-13): tool letters and editing chords are routed in the bubble phase by
    `app/shortcuts.py`; accelerators are global chords only. Product name is **LinScreenCapture 3**, version 3.0.0.dev1.

## 5. Code map (Phase 1)

```
linscreencapture/
  __main__.py            entry; Application().run()
  app/application.py     Adw.Application, app id com.mensuramedia.LinScreenCapture, accels, --capture
  app/view_state.py      GObject: zoom, left/right_collapsed (+ *_manual), panel, tool, colour, status, title
  model/settings.py      full schema ([Window] [Capture] [System] [Tools]), 1.x migration, tool_style(), next_filename()
  model/annotations.py   Annotation + Style dataclasses, Cairo painters for 12 kinds, pixelate/blur pixel ops, geometry helpers
  model/document.py      Document (base surface + Layer list), flatten/save/open, PIL<->cairo conversion
  model/undo.py          UndoStack (20) + commands: AddLayer, RemoveLayer, MoveLayer, EditAnnotation, SetVisible, ReplaceBase
  model/captures_index.py threaded thumbnail scan → Gio.ListStore (newest first; the store is kept when the folder is unchanged)
  services/clip_history.py ClipHistory: the last three copies the app made (digest dedupe, preview textures, clipboard ownership)
  ui/clip_tray.py        ClipTray (three MenuButton slots), ClipPreview popover (clip.* actions), ClipTrayButton for the collapsed rail
  services/icon_loader.py GResource register, IconTheme resource path, icon(name, size)
  ui/style.css           Graphite Night tokens + every widget rule
  ui/widgets/            rail_button, group_label, hairline, flow_group (Gtk.Grid), rail_page, pin_width,
                         StatusChip, ZoomPill, SwatchGrid, LayerRow, colour_class()
  ui/header_bar.py       Gtk.HeaderBar subclass (title block, ToolProps strip as title widget, window controls)
  ui/tool_props.py       per-tool control sets in a Gtk.Stack keyed by tool group; follows ViewState.tool
  ui/tool_rail.py        Item descriptors (icon, label, action, target, collapsed) → open/collapsed pages
  ui/panel_rail.py       Layers, ColourPalette, VIEW (ZoomPill), EDIT (Copy, Flatten), Navigator, Settings; collapsed page
  ui/library_page.py     Library page (grid of the save folder, Gtk.MultiSelection, Select all/Copy/Duplicate/Delete/Open head) in the stage stack
  app/image_ops.py       pure crop / scale / rotate / flip / adjust with coordinate mappers
  ui/popovers.py         Resize, Rotate and Brightness popovers
  ui/stage.py            empty state, Library page, document canvas (flatten cache, zoom, rounded + shadow), Ctrl+scroll zoom, fit_zoom()
  ui/capture_overlay.py  OverlaySession (shared state, physical root px) + OverlayWindow per monitor: veil, handles, crosshair, chips, mode bar, keys
  app/capture_controller.py hide studio → settle → backend → overlay or screen → crop → clipboard → save → ensure_window + load_document (docs/CAPTURE.md §5)
  backends/              base (protocol, crop), x11 (libX11 XGetImage via ctypes; python-xlib for the window list), portal (D-Bus Screenshot), cli
  services/capture_service.py backend order by session/preference, one fall-through per backend, thread → main loop
  services/selection.py  pure selection geometry (handles, hit, resize, move, clamp, square)
  services/file_store.py save_capture(), duplicate_file(); services/clipboard.py copy_surface(): union of image/png bytes + GdkTexture value, then store_async
  services/hotkey_registrar.py Cinnamon custom keybinding for Settings.hotkey (register / unregister / reload_cinnamon)
  app/shortcuts.py       capture-phase ShortcutRouter: tool letters (incl. E eraser, H hand), Ctrl chords, Ctrl+A, Space pan, Library routing
  ui/studio_window.py    composes everything; win.* actions; breakpoint; close saves settings
tools/sync_icons.py, tools/snapshot_shell.py, tools/launch.sh
tests/ conftest (live-display fixtures), test_icons, test_settings, test_shell
data/ icons, gresource.xml, .desktop files
```

## 6. Pitfalls learned (do not rediscover)

- A child with `hexpand=True` (entry, scale, stretched button) makes its **rail** expand. Rails set
  `hexpand=False` explicitly and each page is wrapped by `pin_width()` (a scrolled window with an
  EXTERNAL horizontal policy reports no natural width).
- `Gtk.FlowBox` reports all children on one line as its natural width; the rails use `Gtk.Grid`.
- Never name a CSS class `toggle`: GTK adds that class to every `Gtk.ToggleButton`.
- `Gdk.Clipboard.set_texture` is not in PyGObject; use `clipboard.set(texture)` (Phase 3).
- GTK runs **application accelerators in the capture phase**, before the focused widget: a bare-letter accel
  fires while the user types. Keys that compete with typing live in `app/shortcuts.py`; only
  global chords go through `set_accels_for_action`. `tests/test_shell.py::test_shortcuts_never_interfere_with_typing`
  guards this.
- A **spin button keeps keyboard focus** after a click on its text or its +/- buttons, and its `Gtk.Text` binds
  Ctrl+Z itself, so a bubble-phase router never saw Ctrl+Z or tool letters once the user had touched the header's
  Width spin ("Ctrl+Z does not work while a tool is active"). The router therefore runs in the CAPTURE phase,
  yields only to real text fields and popovers, and hands focus back to the canvas; the strip's other controls have
  `focus_on_click=False`. Guarded by `test_undo_works_with_focus_in_a_header_spin`.
- `Gdk.ContentFormats.contain_gtype(Gdk.Texture)` is **false for a local copy**: the clipboard offers the concrete
  subclass (`GdkMemoryTexture`). Walk `get_gtypes()` with `GType.is_a` (see `StudioWindow._holds_image`).
- `ContentProvider.new_for_value(memory_texture)` alone offers only the GType `GdkMemoryTexture`, which GDK cannot
  serialize: on X11 other applications saw no image target and pasted nothing, while the app toasted "copied"
  (fixed 2026-10-16). Offer `image/png` bytes explicitly, type the texture value as `GdkTexture`, and call
  `store_async` (`services/clipboard.py`). Check with `xclip -selection clipboard -t TARGETS -o`.
- Cinnamon caches custom keybindings: a dconf write changes nothing until `org.Cinnamon.Eval` reruns
  `setup_custom_keybindings` (`hotkey_registrar.reload_cinnamon`). A leftover 1.4 `linshot --capture` holding an
  XGrabKey swallowed PrintScreen on 2026-10-16; `docs/CAPTURE.md` §4 has the diagnosis steps.
- Stacked offset copies as a shadow (1.4 style, three passes) show as hard bands on dark captures. Annotation
  shadows are a Pillow-blurred silhouette cached on the annotation; the stage shadow is four linear and four radial
  gradients.
- `make snapshot` (and any probe) must construct `Application(non_unique=True)`: with the default flags a running
  LinScreenCapture instance is *activated* instead and the tool exits silently with stale renders on disk.
- `Gtk.Widget.activate_action` needs the prefixed name (`win.tool`), and tests must pump a real
  main loop (`GLib.MainLoop` + timeout) before reading allocations.
- `pkill -f "python3 -m linscreencapture"` from an agent shell kills the agent's own shell
  (pattern matches its command line). Use `pgrep -a -x python3 | grep …` or let `timeout` end it.
- `.gitignore` used to list `linshot` and `Makefile` as build artefacts; after the rename they hid
  the Python package. Removed; keep it that way.
- **python-xlib `get_image` is slow**: its pure-Python reply parsing takes ~3.5 s for a 2560×1080 root window
  (17 s under load) — users read it as a capture delay that no toggle could switch off. The X11 backend grabs through
  libX11 `XGetImage` with ctypes (~50 ms; the `XImage` struct must declare `data` as `c_void_p` and be freed through
  its `destroy_image` function pointer). Guarded by `test_x11_grab_is_fast_and_delay_defaults_off`.
- `pkill -f <pattern>` also kills the agent shell whenever the pattern appears in that shell's own command line
  (happened again with `pkill -f delay_probe.py`). Kill by PID: `for p in $(pgrep -x python3 -a | grep … | awk …)`.
- Monkeypatching `GLib.timeout_add` in a probe patches the module the probe itself uses (same object); a probe that
  "hangs" after such a patch is waiting on its own fake timer.
- A popover `popup()` called from a plain button's `clicked` handler is closed again by the same button release on
  X11; use a `Gtk.MenuButton` with `set_popover` (the clipboard tray slots) — it pops on press and survives.
- `Gtk.WidgetPaintable` of the window does not include popovers (own surfaces), and a popover child on this display
  yields no render node; `tools/snapshot_shell.py::render_widget` skips such widgets instead of failing the chain.
- A `Gio.ListStore.remove_all()` + re-append on every Library open wiped the GridView selection; `CapturesIndex._apply`
  compares (path, mtime) and leaves an unchanged store alone.
- A `Gtk.Picture` with `can_shrink=True` still reports the texture's natural size, so a popover around it grew to the
  full capture; the tray keeps a pre-scaled ≤ 320×200 `preview` texture per entry instead.
- A grid of `Gtk.Picture`s with `can_shrink=True` still asks for the textures' natural size: four 192 × 108 tray
  thumbnails stretched the 116 px clipboard tray to 240 px. `clip_tray.CellPicture` overrides `do_measure` to ask
  for nothing; the homogeneous grid sizes the cells.
- Initial keyboard focus lands on the first focusable widget (a rail button), so Space/Enter activated it ("Space
  toggles the right pane"). The window focuses the canvas on map and the router swallows Space.

## 7. What to verify on screen before Phase 2

- Header drag, double-click maximise, and the three window buttons under Cinnamon.
- Resize below 1100 px → both rails collapse; above → reopen; a manual caret click sticks.
- Typing a letter in the hex entry: if it switches tools, scope the single-letter accelerators to the
  stage in Phase 4 (listed in `app/application.py`, `ACCELS`).

## 8. Phase 6 start checklist (system integration)

Backlog carried from the Phase 5 review rounds (schedule with Phase 6/7, operator's call):

- **Design docs 2026-10-18 (shadows, preview and page growth implemented on `feat/editor-shadows-canvas`; see §0a):**
  `docs/EDITOR-CANVAS-EXPANSION.md` (the page grows to fit a pasted or moved image, 20 px padding, one undo step),
  `docs/CLIPBOARD-TRAY-4UP.md` (the tray as a 2 × 2 grid of the last four copies; supersedes the item below),
  `docs/EDITOR-SHADOWS-AND-PREVIEW.md` (pasted-image shadow kept through flatten; a Shadow switch on every
  marking tool, fixing the dead Callout switch; the drawing preview at full colour: the 60 % cap in
  `EditorController._draw_overlay` is the fading arrow). Suggested order: preview fix, shadow switches,
  image shadow, canvas expansion, 4-up tray.
- Clipboard tray with several slots (three or more, newest first). `ClipHistory.limit` and `clip_tray.SLOTS` already
  parametrise it; the tray was reduced to one slot on 2026-10-13 to keep the rail quiet.
- Area tool follow-ups: move / restyle the marked region as a group, feather the edge, invert the area, Ctrl+X cut.
- Select all (Ctrl+A) follow-ups: move or restyle all layers together.

0. **Done 2026-10-16 on `feat/background-agent`** (branched from `feat/phase5`) — background agent: `--background`,
   `hold()` while `keep_running`, `hide_on_close`, `app.hotkey-capture` (fast Region → clipboard first, then file,
   then the studio without popping it up) and `app.show-editor`, the GTK 3 tray helper `linscreencapture/tray.py` (XApp / Ayatana, own process,
   exits with the agent's bus name), `services/autostart.py`, the Settings **System** page (keep running, tray,
   start at login, PrintScreen opens the editor), `tests/test_agent.py`. Later the same day: the **Region Plus** mode
   (handles, arrows, Enter/double-click; Region now captures on release), every capture copied to the clipboard
   first (PNG + texture union, `store_async` to the clipboard manager; the old texture-only provider gave other
   applications nothing to paste on X11), `[Capture] copy_to_clipboard` and `selection_style` retired, and the
   Cinnamon hotkey registrar (item 1). On the dev machine the hotkey is Ctrl+PrintScreen, bound through the
   registrar to `~/.local/bin/linscreencapture --capture` (a wrapper around `tools/launch.sh`); autostart is enabled.
   Full description: `docs/CAPTURE.md`. **2026-10-17** (merged into `feat/phase5`): any hotkey can be recorded
   (Settings → System → *Capture hotkey* → *Record…* / *Custom…*, `ShortcutRecorder`; the desktop binding is
   released while recording), *Run at startup* is its own group and on by default (`autostart.sync`: first run
   creates the entry, later the file wins), `register_hotkey` defaults on. The dev machine is back on plain
   PrintScreen. Tests run with `GSETTINGS_BACKEND=memory`, `LSC_NO_HOTKEY=1` and `LSC_NO_TRAY=1` (conftest), so they
   never touch the real desktop. Gotcha: never `set_model` on an `Adw.ComboRow` from its own `notify::selected`
   handler; it froze the dialog.
   Same day, later: the panel icon is orange #ffa222 (now the app icon itself, `data/icons/hicolor/scalable/apps/com.mensuramedia.LinScreenCapture.svg`; see `docs/ICONOGRAPHY.md`), shown whenever
   the app runs, double-click opens the editor (`tray.DoubleClick`); pasted images resize like in an image editor
   (`tools.image_resize`: corners keep proportions, Shift free, Ctrl about the centre; header W / lock / H / Scale %
   / 100 % / Fit; arrow keys nudge); user guide `docs/PRINTSCREEN.md`. Gotcha: XApp derives the icon's bus name from
   the program name, and `tray.py` collided with Mint's own `tray.py` (mintreport), so the icon never showed. The
   helper now calls `GLib.set_prgname("linscreencapture-tray")`.
   Later still: a new app icon (orange tile, selection frame, pointer) used for the window, Alt+Tab, the menu and the
   panel; the window's WM_CLASS is now the app id (was `__main__.py`); `install.sh` and the `.deb`
   (`packaging/build-deb.sh`, `make deb`; the built package is tracked in `packaging/`); zoom steps 4 % per notch,
   at most 5 %, stopping at 100 % (`view_state.next_zoom`). The dev menu entry is now
   `~/.local/share/applications/com.mensuramedia.LinScreenCapture.desktop` (`make launcher`).
1. `services/hotkey_registrar.py`: **done for Cinnamon** (2026-10-16; reuses our `customN`, never overwrites another
   application's slot, frees the six built-in screenshot keys, reloads through `org.Cinnamon.Eval`; re-applied at
   every agent start while `register_hotkey` is on; `docs/CAPTURE.md` §4). Still to port from `keybinding_manager.c`:
   GNOME **append to** `custom-keybindings` and clear `show-screenshot-ui`, XFCE xfconf, MATE marco; KDE/other:
   the manual path (documented in `INSTALL.md`).
2. Settings dialog **System** page: **partly done** — hotkey preset (`Settings.hotkey`), register switch
   (`register_hotkey`), keep running, tray, autostart and *PrintScreen opens the editor* rows exist. Still to add:
   backend choice, include pointer, pin opacity, reopen last; and the **Shortcuts** page listing both shortcut tiers.
3. Delayed capture: countdown chip in the header (the `StatusChip` widget is ready) instead of a toast. The
   rail's Delayed button is already a boolean toggle (`win.capture-delayed`) that applies to any mode.
4. Pin to screen (`app.pin`): borderless always-on-top window at `pin_opacity`, Esc/double-click closes.
5. Scrolling capture (`app.capture-scrolling`): repeated region captures stitched by overlap matching (NumPy).
6. Include pointer: draw the cursor from `Gdk` into the frozen screen when `include_pointer`.
7. Tests for the registrar (gsettings calls mocked), the countdown and the stitcher; FEATURES/HANDOFF/changelog.

## 8b. Image-operation notes (Phase 5)

- `app/image_ops.py` is pure: each op returns `(new_base, mapper)`; `undo.TransformBase` swaps the base and runs
  every annotation through the mapper (and restores both on undo). Adjust has no mapper.
- Crop: the Crop tool stores `editor.crop_rect` after the drag; Enter / `win.crop-apply` applies, Esc /
  `win.crop-cancel` abandons; the overlay draws a veil around the pending rectangle.
- Brightness popover previews by temporarily swapping `doc.base` (`window.preview_base`), restored on close.
- Paste: `Gdk.Texture.download` cannot fill a Python buffer (PyGObject copies it), so textures are decoded via
  `save_to_png_bytes`. Pasted images are `image` annotations carrying a cairo surface (`Annotation.copy()` keeps
  it; `to_dict()` omits it).
- Popovers anchor to the rail buttons found with `ToolRail.button_for(action)`.

## 8a. Editor notes (Phase 4)

- `app/tools.py` is pure (drag → annotation, handles, handle/move changes, duplicate); `app/editor_controller.py`
  owns gestures on `Stage.canvas`, the live preview and selection overlay (`Stage.extra_draw`), the inline text
  entry (`Stage.show_text_entry`) and all undoable commands via `window.undo`.
- During a move/resize the original layer is hidden and a preview copy is drawn; the edit is one `EditAnnotation`.
- The header strip (`ui/tool_props.py`) follows `ViewState.tool` or, under Select/Move, the selected layer; it
  writes `Settings` and applies "Style" edits to the selection. The palette recolours the selection too and
  persists the colour to every tool entry.
- (2026-10-18) The layer list is gone; `PanelRail.set_document` is now a no-op kept for callers. Restacking:
  `EditorController.arrange_selected` (`MoveLayer`), actions `win.layer-front/forward/backward/back`.

## 9. Capture notes (Phase 3)

- Flow (`CaptureController`, revised 2026-10-16; authoritative: `docs/CAPTURE.md` §5): hide the studio → 300 ms settle
  (0 ms when nothing is on screen; + delay seconds for Delayed, in-app only) → `CaptureService.capture_screen` (thread)
  → mode `screen`: finish; `region`/`region-plus`/`window`: `OverlaySession.show()` one window per monitor → `crop` →
  **clipboard first** (always) → `save_capture` → `ensure_window()` + `load_document` + clipboard tray → present + toast
  only when `presents` (not a hotkey capture, or the studio was visible, or `hotkey_opens_editor`).
- Backend order: preference from Settings, else X11 → portal → CLI on X11 sessions and portal → X11 → CLI on Wayland;
  each is tried once; the last error is reported. X11 copies the root `GetImage` bytes in one numpy copy (BGRX → ARGB32).
- Overlay coordinates are physical root pixels; each monitor window converts with its origin and scale factor.
  Window mode uses `_NET_CLIENT_LIST_STACKING` (+ `_NET_FRAME_EXTENTS`) on X11; without a window list it falls back
  to region. Region captures on mouse release; Region Plus adds handles and arrows (±1/±10) and confirms with Enter or
  a double-click. Both: Esc, Space (move while dragging), Shift (square), Ctrl+A.
- Known limits: a selection cannot span monitors; HiDPI assumes integer scale factors; the portal path is untested here
  (no Wayland session on the dev machine).

## 9. Model notes (Phase 2)

- `Annotation.kind` ∈ arrow, line, box, circle, text, pen, marker, step, callout, fill, blur, pixelate. Blur and
  pixelate modify the pixels of the target surface beneath them (as 1.4 did), so they must be drawn in layer order
  onto the composite; `Document.render(cr, target)` passes the surface for that reason.
- Shadows: three offset passes, intensity×0.25/pass, as in `editor_tools.c`. Marker = pen at 4× width, 40 % alpha.
  Step = filled circle, radius max(10, font×0.75), white number; steps renumber on add/remove/move.
- `Settings.tool_style(tool)` builds the drawing `Style`; `universal=True` makes every tool read the arrow entry.
- 1.4 → 2.0 key mapping is in `Settings._read_legacy`; `filename_format` 0/2 → `LinScreenCapture_`, 1/3 →
  `Screenshot_`; ≥2 → timestamp. `border` tool is dropped. Colours accept `rgb()`/`rgba()`/hex.
