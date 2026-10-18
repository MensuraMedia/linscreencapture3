# Iconography — the application icon

LinScreenCapture 3 has **one application icon**: an orange `#ffa222` rounded tile (gradient `#ffb84d` → `#ff8f14`)
with a white region-selection frame, a dashed marquee inside it, and a pointer at the bottom-right corner. Use this
icon, and only this icon, wherever the desktop shows the application, so users recognise it in the menu, the panel,
the tray and Alt+Tab alike. Full colour on purpose: the panel does not recolour it, and the orange reads on dark and
light panels.

## The files

Icon-theme name: **`com.mensuramedia.LinScreenCapture`** (the application id, `APP_ID`).

| File (tracked in git) | Type | Role |
| --- | --- | --- |
| `data/icons/hicolor/scalable/apps/com.mensuramedia.LinScreenCapture.svg` | SVG, 256 × 256 viewBox | the master; also bundled in the GResource as `icons/scalable/apps/<APP_ID>.svg` |
| `resources/icons/linscreencapture-{16,24,32,48,64,128,256,512}.png` | PNG, 8-bit RGBA, transparent | renders of the master for each hicolor size |

`install.sh`, the `.deb` (`packaging/build-deb.sh` runs `install.sh --prefix /usr`) and `make launcher` install them as
`share/icons/hicolor/scalable/apps/<APP_ID>.svg` and `share/icons/hicolor/<N>x<N>/apps/<APP_ID>.png`.
Edit the SVG first and regenerate the PNGs from it; the two must never show different marks.

Not the application icon: `resources/icons/shutter.png` (a black aperture glyph, unused), the old grey ring
(replaced 2026-10-17; the theme name `linscreencapture3` is retired and `make launcher` deletes it) and the Phosphor
glyphs in `data/icons/` (symbolic icons for in-app controls, recoloured by CSS).

## Placement

| Where | How the icon gets there | Recognition requirement |
| --- | --- | --- |
| Program menu (Cinnamon menu, app grid, search) | `.desktop` `Icon=<APP_ID>`: `data/com.mensuramedia.LinScreenCapture.desktop` (install.sh, .deb) or `data/linscreencapture3-dev.desktop.in` (`make launcher`) | the icon installed in the hicolor theme |
| Panel window list, Alt+Tab, "not responding" dialogs | the window's `_NET_WM_ICON`, from `Gtk.Window.set_default_icon_name(APP_ID)` (`icon_loader.install_app_icon`); resolves from the bundled SVG even when nothing is installed | `WM_CLASS` = `com.mensuramedia.LinScreenCapture` (prgname set in `__main__.py` before GTK starts) equal to the launcher's `StartupWMClass` |
| System tray / panel status icon (XApp; Ayatana AppIndicator elsewhere) | `tray.py` loads the SVG by absolute path (`ICON_FILE`), theme name `APP_ID` as fallback | the helper's prgname `linscreencapture-tray`, so its bus name is `org.x.StatusIcon.linscreencapture_tray` and not Mint's `tray_py` |
| Startup Applications | autostart entry `Icon=<APP_ID>` (`services/autostart.py`) | same theme name |

The Alt+Tab icon appears only while a studio window exists; the background agent has no window, so it shows in the
panel's tray area only. Check a running build with `xprop WM_CLASS _NET_WM_ICON` (click the window) and
`gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListNames | grep StatusIcon`.

## Action glyphs

Buttons use Phosphor (regular weight) through the resource bundle (`lsc-<name>-symbolic`, `data/icons/icons.txt`).
Where Phosphor has no clear glyph the app draws its own in the same style — 256 grid, 16 px weight,
`fill="currentColor"` so GTK recolours it — in `data/icons/custom/`, bundled by `tools/sync_icons.py`. Today: the
four arrange glyphs `layer-back`, `layer-backward`, `layer-forward`, `layer-front` (the filled square is the
selected layer). These are action glyphs, never a substitute for the application icon.

## Rules

- Use this icon for every place the desktop represents the application. Do not substitute a Phosphor glyph,
  `shutter.png`, a stock icon or a separate "tray" variant.
- Refer to it by the theme name `APP_ID` everywhere (both `.desktop` files, the autostart entry, the window default,
  the tray fallback). A new place that shows the application uses the same name; add it to the table above.
- Set the prgname in every process that shows UI. Unset, it is `__main__.py` or `tray.py`: Alt+Tab cannot match the
  window, and the tray icon collides with Mint's `mintreport-tray` on the XApp bus name and never appears.
- Keep the master SVG and the PNG renders in step, at all eight sizes, and keep the transparent margin; the hicolor
  sizes are what the menu (24–48 px), the panel (16–24 px) and Alt+Tab (48–128 px) pick from.
