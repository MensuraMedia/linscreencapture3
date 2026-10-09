# HANDOFF — LinScreenCapture 2 (linscreencapture3)

Written 2026-10-08 after Phase 1. Read this first; it says where everything is, what was
decided, and what to do next. The spec (`docs/GUI_SPEC.md`) is authoritative for the GUI;
this file is authoritative for process and state.

## 1. Mission

Rebuild the 1.4 C/GTK3 screenshot tool as **LinScreenCapture 2: Python 3 + GTK 4 + libadwaita**,
reproducing the Studio Editor design (header, two mirrored rails, stage, right-rail panels) in
the Graphite Night look. Pure Python, no C extension (decided 2026-10-08; rationale and the
performance budget are in the spec, section 5). Local-only tool; no cloud, no telemetry.

## 2. Ground truth

| Fact | Value |
| --- | --- |
| Repo | `/home/user/projects/linscreencapture3`, remote `origin` = `github.com/MensuraMedia/linscreencapture3` (branch `main`); `upstream` = the 1.4 repo `MensuraMedia/linscreencapture` |
| Last pushed commit | see `git log --oneline -1`; everything is committed and pushed at the time of writing |
| Run | `make resources && python3 -m linscreencapture` (or the menu entry **LinScreenCapture3**, installed by `make launcher`) |
| Test | `make test` → 16 tests (`tests/`). No Xvfb on this machine: tests and `make snapshot` run on the live display and flash a window |
| Renders | `make snapshot` → `screenshots/dev/shell_*.png` (open, collapsed, library, props) for comparison with `screenshots/01_*.png` and `02_*.png` |
| Design canvas | https://claude.ai/artifact/NTRyK2yrrpnhbW6sUmnBoA (9 artboards; sources in `docs/mockups/`, generator `docs/mockups/gen_mockups.py`) |
| Spec | `docs/GUI_SPEC.md` (repo copy) and the living doc https://claude.ai/code/artifact/5e6387bf-76b0-45f6-9874-a6ba13f90732 |
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
| 2 | Model and settings | `Document`, `Annotation` dataclasses + Cairo draw (port `src/editor_tools.c`), `UndoStack` (20), full `Settings` schema + 1.x migration | next |
| 3 | Capture | backends (portal, X11 bulk copy, CLI), `CaptureService`, overlay window, `FileStore`, clipboard, `--capture` activation, live status chip | |
| 4 | Annotation tools and layers | stage draws the document; all tools; handles; Layers panel live; colour and props wired | |
| 5 | Image operations and files | crop/resize/rotate/brightness, blur/pixelate layers, flatten, save/copy/discard/paste, captures actions; **then remove `src/`, `include/`, `CMakeLists.txt`, `debian/`, `install.sh`, `uninstall.sh`, `packaging/build-deb.sh`** | |
| 6 | System integration | hotkey registrar (GNOME append fix), autostart, delayed, pin, scrolling capture, preferences dialog | |
| 7 | Polish and release | navigator live, shortcuts window, about, toasts, golden-image tests, packaging, tag 2.0.0 | |

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
6. Old C sources stay as the behavioural reference until Phase 5 parity.
7. Placeholder actions toast "X arrives in Phase N" so every button is wired from day one.
8. Shell adjustments (2026-10-08, `docs/SHELL-ADJUSTMENTS-2026-10-08.md`): Capture top-left, no status
   chip, name-only title until a capture exists, `Settings` bottom-right of the right rail, round colour
   swatches with no card/well/hex entry, and **Library** (full-stage page, Ctrl+L) instead of a Captures panel.

## 5. Code map (Phase 1)

```
linscreencapture/
  __main__.py            entry; Application().run()
  app/application.py     Adw.Application, app id com.mensuramedia.LinScreenCapture, accels, --capture
  app/view_state.py      GObject: zoom, left/right_collapsed (+ *_manual), panel, tool, colour, status, title
  model/settings.py      GLib.KeyFile persistence, Phase-1 subset, legacy read
  model/captures_index.py threaded thumbnail scan → Gio.ListStore (newest first)
  services/icon_loader.py GResource register, IconTheme resource path, icon(name, size)
  ui/style.css           Graphite Night tokens + every widget rule
  ui/widgets/            rail_button, group_label, hairline, flow_group (Gtk.Grid), rail_page, pin_width,
                         StatusChip, ZoomPill, SwatchGrid, LayerRow, colour_class()
  ui/header_bar.py       Gtk.HeaderBar subclass (title block, chip, zoom pill, Capture, window controls)
  ui/tool_rail.py        Item descriptors (icon, label, action, target, collapsed) → open/collapsed pages
  ui/panel_rail.py       Layers / Props pages, ColourPalette, Navigator, Settings button, collapsed page
  ui/library_page.py     Library page (grid of the save folder) shown in the stage stack
  ui/stage.py            empty-state placeholder + HUD; DrawingArea reserved for Phase 4
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
- `Gtk.Widget.activate_action` needs the prefixed name (`win.tool`), and tests must pump a real
  main loop (`GLib.MainLoop` + timeout) before reading allocations.
- `pkill -f "python3 -m linscreencapture"` from an agent shell kills the agent's own shell
  (pattern matches its command line). Use `pgrep -a -x python3 | grep …` or let `timeout` end it.
- `.gitignore` used to list `linshot` and `Makefile` as build artefacts; after the rename they hid
  the Python package. Removed; keep it that way.

## 7. What to verify on screen before Phase 2

- Header drag, double-click maximise, and the three window buttons under Cinnamon.
- Resize below 1100 px → both rails collapse; above → reopen; a manual caret click sticks.
- Typing a letter in the hex entry: if it switches tools, scope the single-letter accelerators to the
  stage in Phase 4 (listed in `app/application.py`, `ACCELS`).

## 8. Phase 2 start checklist

1. Port `src/editor_tools.c` → `model/annotations.py` (dataclasses + Cairo draw functions; keep the
   shadow and blur-block semantics), add `model/document.py` and `model/undo.py`.
2. Extend `model/settings.py` to the full schema table in spec §2 and migrate the legacy file on
   first run (copy, do not move).
3. `pytest tests/model` must run without a display; add property tests for undo.
4. Update `changelog.md`, this file (status table), README roadmap; backup; commit; push.
