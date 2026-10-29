# Screen capture — technical reference

User guide: [PRINTSCREEN.md](PRINTSCREEN.md).

This is the authoritative description of how LinScreenCapture 3 takes screenshots: the hotkey, the background agent,
the capture modes, the overlay, the clipboard and the save path. Other documents summarise it and point here:
`README.md`, `docs/FEATURES.md` §1, §11 and §12, `HANDOFF.md`, `INSTALL.md`, `KNOWN_ISSUES.md`. When the code and this
file disagree, fix one of them in the same change.

Status: 2026-10-16, branch `feat/background-agent` (built on `feat/phase5`). It was verified on Linux Mint 22.3
Cinnamon (X11, 2560×1080) by driving the real hotkey and mouse through XTest.

---

## 1. Intended behaviour

1. **The hotkey works everywhere.** The capture hotkey (PrintScreen by default, or any key combination the user
   records in Settings) starts a capture wherever the user is, including inside the LinScreenCapture window.
   The agent runs at startup (on by default), so the hotkey works from login onwards.
2. **Region is fast and immediate.** The screen freezes and you draw a box. The capture happens **the moment the
   mouse button is released**. There are no handles and no confirmation step.
3. **Region Plus is the precise variant.** The box keeps eight resize handles, arrow-key nudging and Space-move.
   **Enter** or a **double-click** confirms.
4. **Every capture goes to the clipboard first**, as lossless PNG at the native resolution, then to the save folder,
   then into the studio (the editor document and the left rail's clipboard tray). This holds for every route: the
   hotkey, the tray, the Capture button, Ctrl+N and Ctrl+Shift+N. There is no setting that turns the clipboard off.
5. **The application is a small background agent.** It runs at login with no window. A hotkey capture never pops
   the studio up: a hidden studio receives the capture unseen, and a studio that was on screen is shown again
   holding the capture. Settings → System → *PrintScreen opens the editor* presents the studio after every hotkey
   capture.
6. **Esc cancels** at any point. A cancelled capture writes nothing: no file, no clipboard change, no document.

## 2. Components

| Piece | File | Role |
| --- | --- | --- |
| Agent | `app/application.py` | primary `Adw.Application` (`com.mensuramedia.LinScreenCapture`); `hold()` while `keep_running`; actions `app.hotkey-capture`, `app.show-editor`, `app.capture*`, `app.quit`; options `--capture` and `--background`; `ensure_window()` builds the studio hidden |
| Capture controller | `app/capture_controller.py` | the flow in §5; decides whether the studio is presented (`presents`) |
| Backends | `backends/x11.py`, `backends/portal.py`, `backends/cli.py`, `services/capture_service.py` | freeze the whole screen into a cairo surface (§6) |
| Overlay | `ui/capture_overlay.py` | one fullscreen `OverlayWindow` per monitor sharing an `OverlaySession`; Region / Region Plus / Window; the mode bar can also switch to Full screen |
| Clipboard | `services/clipboard.py` | lossless multi-format clipboard plus hand-off to the clipboard manager (§7) |
| Save | `services/file_store.py` | `save_capture()`: the next name in the save folder (`Settings.next_filename()`) |
| Hotkey registrar | `services/hotkey_registrar.py` | writes the Cinnamon custom keybinding and makes Cinnamon reload it (§4) |
| Autostart | `services/autostart.py` | `~/.config/autostart/com.mensuramedia.LinScreenCapture.desktop` → `linscreencapture --background` |
| Tray | `tray.py` | a GTK 3 status-icon helper process, shown whenever the app runs: an orange #ffa222 icon (the application icon `data/icons/hicolor/scalable/apps/com.mensuramedia.LinScreenCapture.svg`); double-click → *Open editor*; menu *Capture region to clipboard*, *Open editor*, *Quit* |

## 3. Triggers

| Trigger | Path | Mode | Studio afterwards |
| --- | --- | --- | --- |
| Capture hotkey (desktop keybinding) | `linscreencapture --capture` → D-Bus → `app.hotkey-capture` | Region, no delay | unchanged: hidden stays hidden, a visible studio is shown with the capture |
| Tray → *Capture region to clipboard* | `app.hotkey-capture` over D-Bus | Region, no delay | as above |
| `.desktop` action *Capture a region* | `linscreencapture --capture` | Region | as above |
| Capture button, **Ctrl+N** | `app.capture` | the rail's current mode, plus the Delayed toggle | presented with the capture |
| **Ctrl+Shift+N** | `app.capture-screen` | Full screen | presented |
| `app.capture-region`, `-region-plus`, `-window`, `-screen`, `-delayed` | explicit actions | as named | presented |

`--capture` started when no agent is running makes that process the agent (no window up front) and then runs the
hotkey capture. A second `--capture` only forwards the action and exits. The 1.4 build used SIGUSR1 plus a 200 ms
poll; v3 uses GApplication's D-Bus activation, so it has no poll latency.

## 4. The hotkey on Cinnamon

The desktop owns the key; the application never grabs it itself. The 1.4 build tried an XGrabKey alongside the
desktop binding and got double captures.

**Registration** (`hotkey_registrar.register(Settings.hotkey)`). It runs at every agent start while
`Settings.register_hotkey` is on, and again whenever the key or the switch changes on the System page:

1. Find our entry in `org.cinnamon.desktop.keybindings custom-list`: the first `customN` whose `command` contains
   `linscreencapture` or `linshot`. Reuse it. Further entries of ours (stale builds) are reset and dropped from the
   list. An entry that belongs to another application is **never** overwritten. If none of the entries is ours, the
   first free `customN` is taken.
2. Write the relocatable schema `org.cinnamon.desktop.keybindings.custom-keybinding` at
   `/org/cinnamon/desktop/keybindings/custom-keybindings/customN/`:
   - `binding = ['<Primary>Print']`: a **list**. `<Control>` is written as `<Primary>`, as Cinnamon's own settings do.
   - `command = '/home/user/.local/bin/linscreencapture --capture'`: the absolute path of `linscreencapture` on
     `PATH`. Without it on `PATH`, the command is `env PYTHONPATH=<checkout> python3 -m linscreencapture --capture`.
   - `name = 'LinScreenCapture'`.
3. Remove the same accelerator from Cinnamon's six built-in screenshot keys in
   `org.cinnamon.desktop.keybindings.media-keys`: `screenshot`, `area-screenshot`, `window-screenshot`, and the three
   `*-clip` variants. Set the remainder with a real `[]`; 1.4 learned that writing `''` is ignored.
4. **Make Cinnamon reload.** Cinnamon caches its custom bindings, so a dconf write alone changes nothing on screen.
   The registrar calls `org.Cinnamon.Eval` with
   `Main.keybindingManager.remove_custom_keybindings(); Main.keybindingManager.setup_custom_keybindings();`.
   If that call is unavailable, it falls back to writing `custom-list` to `[]` and back, because a changed value
   triggers the same reload.

**Choosing the hotkey** (Settings → System → *Capture hotkey* → *Key*): the presets (`Settings.HOTKEYS`: Off,
`Print`, `<Control>Print`, `<Shift>Print`, `<Control><Shift>s`, `<Control><Alt>s`), or **Custom…** / **Record…**,
which opens a small recorder window and takes the next key press:

- PrintScreen, the function keys, Pause and similar keys work on their own; a letter, digit or symbol needs Ctrl,
  Alt, Shift or Super (a bare letter would stop typing everywhere). Alt+PrintScreen (Sys_Req on X11) is stored as
  `<Alt>Print`. Esc cancels; Backspace turns the hotkey off.
- While the recorder is open, the agent removes its own desktop binding so the current key reaches the recorder
  (`Application.suspend_hotkey`); it is re-registered when the recorder closes, with the new key or the old one.
- Any GTK accelerator name is accepted in the settings file (`settings.valid_hotkey`); an unreadable value falls back
  to `Print`.
- A key already bound to another application's custom shortcut is logged as a conflict but not taken from it.

**Diagnosing a dead hotkey.** Work through these in order:
1. Does the agent log (`--debug`) show `capture requested`? If it does, the key works and the problem is further on.
2. Look in `~/.xsession-errors` for `Execution of '…' failed`. That means Cinnamon is running a stale command, so
   reload it as in step 4 above.
3. List Cinnamon's live bindings for the key:
   ```
   gdbus call --session --dest org.Cinnamon --object-path /org/Cinnamon --method org.Cinnamon.Eval \
     'let o=[];Main.keybindingManager.bindings.forEach((v,k)=>{let s=JSON.stringify(v.bindings||"");if(/Print/.test(s))o.push(k+" "+v.name+" "+s)});o.join(" | ")'
   ```
4. Look for another process holding the key with XGrabKey, such as a leftover 1.4 `linshot --capture`. On
   2026-10-16 exactly this swallowed PrintScreen until the process was ended.
5. Check that the GNOME path `org.gnome.settings-daemon.plugins.media-keys custom-keybindings` holds no stale entry.
   `csd-media-keys` reads it too.

**Other desktops.** The registrar supports Cinnamon only. On GNOME, Xfce, MATE and KDE, bind
`linscreencapture --capture` by hand; `INSTALL.md` has the steps. On GNOME also clear
`org.gnome.shell.keybindings show-screenshot-ui`.

## 5. The capture flow (`CaptureController`)

1. `capture(mode, hotkey)`. A hotkey forces `region` with no delay. Otherwise the mode comes from the rail
   (`win.capture-mode`) and the Delayed toggle adds `Settings.delay_seconds`. `scrolling` and `pin` show
   "arrives in Phase 6".
2. Hide the studio if it is visible, then wait **300 ms** (`HIDE_SETTLE_MS`) for the compositor to repaint without
   it. When nothing of ours is on screen the wait is **0 ms**.
3. Freeze the screen with the first working backend (§6). The whole virtual screen is frozen, in physical pixels.
4. `screen` finishes at once. `region`, `region-plus` and `window` open the overlay on every monitor (§8).
   `window` falls back to `region` when the backend cannot list windows.
5. On confirm: crop the frozen surface to the rectangle. The pixels are exactly the frozen screen; nothing is
   re-grabbed and nothing is scaled.
6. **Clipboard first:** `clipboard.copy_surface(cropped)` (§7).
7. Save: `save_capture()` writes the next file name in the save folder in the configured format.
8. The studio: `ensure_window()` builds it hidden if there is none. Then `load_document(doc)` runs and the capture is
   pushed onto the clipboard tray.
9. Present the studio only if `presents` is true: the capture was not a hotkey capture, the studio was visible
   before, or *PrintScreen opens the editor* is on. In that case a toast reports `Saved <name> · copied to clipboard`.
10. On failure: show a toast if the studio is going to be on screen, otherwise a desktop notification
    (`Application.send_notification`). If saving fails after the copy, the message adds "the image is on the
    clipboard".

**Measured on the reference machine:** the overlay is up 75–80 ms after the key; the clipboard is set within
20 ms of mouse release; save and load add about 80 ms; the clipboard manager has the image after about 40 ms more.

## 6. Freezing the screen (backends)

| Backend | When | How |
| --- | --- | --- |
| `x11` | first on X11 sessions | libX11 `XGetImage` of the root window through ctypes. A 2560×1080 grab takes about 50 ms. python-xlib's `get_image` took about 3.5 s and was the "capture delay" of 2026-10-13. One numpy copy converts BGRX to cairo ARGB32 |
| `portal` | first on Wayland | `org.freedesktop.portal.Screenshot`; the temporary file is loaded and deleted |
| `cli` | last resort | `gnome-screenshot -f`, `grim`, `import -window root`, `spectacle -b -n -f -o` |

`Settings.backend` (auto · portal · x11 · cli) moves a backend to the front. Each backend is tried once and the last
error is reported.

## 7. Clipboard: lossless and readable by every paste target

`services/clipboard.py`. The clipboard is given a **union** of two providers for the same pixels:

1. `image/png` bytes, from `Gdk.Texture.save_to_png_bytes()`. This is lossless, at the capture's native resolution,
   8-bit RGBA, and is what other applications request.
2. A `GdkTexture` value, typed as the base class, for pastes inside the application with no PNG round trip. Because
   it is typed as `GdkTexture`, GDK also offers its own conversions (`image/bmp`, `image/jpeg`, `image/tiff`,
   `image/webp`, icon formats).

After `set_content`, **`Gdk.Clipboard.store_async()`** hands the data to the desktop's clipboard manager
(`csd-clipboard` on Cinnamon). The image then survives even if the agent exits. This is the GTK 4 equivalent of the
1.4 fix `gtk_clipboard_store()` (commit `8814ee5` of the original repository).

**Bug fixed on 2026-10-16.** Before this date the clipboard was set with
`ContentProvider.new_for_value(memory_texture)` alone. That advertises only the GType `GdkMemoryTexture`, for which
GDK has no serializer. On X11 the clipboard therefore offered only `TARGETS`, `TIMESTAMP` and `SAVE_TARGETS`, and
every paste in another application came up empty, while the app reported "copied to clipboard". Regression tests:
`tests/test_agent.py::test_clipboard_offers_lossless_png_to_other_applications` and the capture-flow tests.

**Quality guarantees.**
- No scaling: the crop is taken from physical root pixels.
- No colour conversion beyond B8G8R8A8-premultiplied to PNG. Screen pixels are opaque, so un-premultiplying is exact.
- No border is added. 1.4 baked a 3 px black border into every capture; v3 does not.
- Verified on 2026-10-16: the PNG pulled by `xclip -selection clipboard -t image/png -o` is pixel-identical to the
  saved file.

**Terminals and CLIs.** These read the clipboard with `xclip -selection clipboard -t image/png -o` on X11, or
`wl-paste --type image/png` on Wayland. Install `xclip` or `wl-clipboard` through apt; do not use a `~/.local/bin`
shim, which can shadow the real binary.

Other copy paths (editor **Ctrl+C**, Library Copy, the tray slot's Copy) use the same service.
`image_providers(surface)` can be combined with other providers; Library Copy adds a file list and
`text/uri-list`, for example.

## 8. The overlay

The overlay shows one fullscreen window per monitor. Coordinates are physical root pixels of the frozen surface,
which makes it correct on multi-monitor and HiDPI setups. The veil is 45 % black outside the selection. A crosshair
and a size chip follow the pointer. The mode bar at the top holds only the Region · Region Plus · Window · Full screen
icons (tooltips name them). There is no hint text anywhere on the overlay: the top key hints were removed on
2026-10-17 and the bottom-right "Release to capture" chip on 2026-10-18, both at the operator's request.

| | Region | Region Plus |
| --- | --- | --- |
| Draw | drag a box (Shift = square, Space held = move the box while drawing) | same |
| Finish | **mouse release captures** | **Enter**, or a **double-click** inside the box |
| Adjust | none | 8 handles; arrows nudge 1 px, Shift+arrows 10 px; drag inside to move |
| Rail item | `selection` icon, `win.capture-mode::region` | `bounding-box` icon, `win.capture-mode::region-plus` |

Common keys: **Esc** cancels and a click without a drag clears the box. **Ctrl+A** captures the whole screen at once
in Region and selects it (for adjusting, then Enter) in Region Plus. Enter and a double-click inside the box also
confirm in Region, for a box drawn with Space-move, but release normally gets there first.
Window mode: hovering highlights a window and a click captures it. Switching modes in the mode bar takes effect at
once; the hints follow the mode (`OverlayWindow.refresh_hints`).

The 1.4 overlay covered the primary monitor only and re-grabbed the screen after hiding itself, which risked
capturing the veil. v3 crops the frozen image instead.

## 9. Settings

| Key | Default | Effect |
| --- | --- | --- |
| `[System] hotkey` | `Print` | a preset or any recorded accelerator (§4) |
| `[System] register_hotkey` | on | when on, the agent writes the desktop binding at every start. Switching it off, or choosing the Off preset, removes our binding (`hotkey_registrar.unregister`) |
| `[System] keep_running` | on | the agent holds itself alive; closing the studio hides it |
| `[System] tray_icon` | on | the status-icon helper |
| `[System] autostart` | on | *Run at startup*: the login entry (`--background`). The first run creates it; afterwards the entry on disk is the truth (a switch-off in Cinnamon's Startup Applications, `X-GNOME-Autostart-enabled=false`, counts as off), and an enabled entry is rewritten when the launcher path changes (`autostart.sync`) |
| `[System] hotkey_opens_editor` | off | present the studio after every hotkey capture |
| `[Capture] delay_seconds` | 3 | used by the Delayed toggle (in-app captures only) |
| `[Capture] backend` | auto | backend order (§6) |
| `[Capture] screenshot_path`, `prefix`, `numbering`, `format`, `jpeg_quality` | | the save path (default `~/Pictures/ScreenShots`) and naming |

Retired on 2026-10-16: `[Capture] copy_to_clipboard` (every capture is copied now) and `[Capture] selection_style`
(replaced by the Region and Region Plus modes). Both are removed from the file at the next save.

## 10. Verifying

- `make test`: `tests/test_agent.py` covers the clipboard formats, the hotkey and in-app flows, Region and Region
  Plus, the registrar (with fake GSettings), autostart and the settings.
- Live, on X11: `python3 tools/hotkey_probe.py --key Control_L+Print` presses the hotkey through XTest, drags a
  box (moving the real pointer), then checks `xclip -selection clipboard -t TARGETS -o` (it must list `image/png`)
  and the size of the PNG it reads back. Exit status 0 means a PNG of the dragged size is on the clipboard.
- Agent log: `linscreencapture --background --debug` prints `capture requested`, `screen frozen`, `cropped`,
  `clipboard set`, `saved` and `clipboard handed to the clipboard manager`, with times.

## 11. Known limits

- The registrar covers Cinnamon only; other desktops need a manual binding.
- The Wayland portal path is untested. On Wayland the overlay depends on the compositor allowing fullscreen windows
  on every output.
- Scrolling capture, Pin and the delay countdown chip are not built yet (Phase 6).
- Turning *Keep running* off takes effect at the next start.
