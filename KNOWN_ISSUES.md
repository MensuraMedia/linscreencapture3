# Known Issues — LinScreenCapture 1.4.0 Beta

> LinScreenCapture is beta software. The keybinding system works reliably on **Linux Mint (Cinnamon)** but has known limitations on other desktop environments. This document tracks those issues and their severity.

---

## Keybinding Registration — Cross-DE Reliability

**Filed:** 2026-03-29
**Severity:** High
**Affects:** GNOME, XFCE, MATE, KDE — all Debian-based distros running these DEs
**Component:** `src/keybinding_manager.c`, `src/main_window.c`

### Summary

LinScreenCapture's "Set as default screenshot app" feature registers a system-wide keybinding (default: PrintScreen) to launch `linscreencapture --capture`. This registration uses DE-specific APIs (gsettings, dconf, xfconf-query, XGrabKey). While the Cinnamon path has been hardened through multiple bug fixes, the other DE paths have unresolved issues that may cause silent failures, data loss, or conflicts.

### Per-DE Status

| Desktop Environment | Distros | Status | Key Issues |
|---|---|---|---|
| **Cinnamon** | Linux Mint | **Working** | Fully hardened — stale binding purge, D-Bus reload, cross-schema cleanup |
| **GNOME** | Ubuntu, Pop!_OS, Debian | **Bugs** | Overwrites user's custom keybindings; missing GNOME 42+ support |
| **XFCE** | Xubuntu, MX Linux | **Partial** | Does not disable xfce4-screenshooter; may not override default bindings |
| **MATE** | Ubuntu MATE | **Partial** | Does not work with Compiz; doesn't disable mate-screenshot |
| **KDE Plasma** | Kubuntu, KDE Neon | **Limited** | X11-only fallback; no kglobalaccel integration; fails on Wayland |
| **Other/Unknown** | i3, Openbox, Sway, etc. | **Fragile** | Raw XGrabKey; fails if compositor grabs key first; no Wayland |

---

### Issue 1: GNOME — Custom Keybindings List Overwrite (Critical)

**Severity:** Critical — data loss
**Affects:** Ubuntu 20.04+, Pop!_OS, Debian GNOME

When LinScreenCapture registers its keybinding on GNOME, it **replaces the entire `custom-keybindings` list** with only its own entry. Any custom keyboard shortcuts the user previously configured in GNOME Settings are silently removed from the active list.

**Root cause:** `gnome_register()` sets:
```
org.gnome.settings-daemon.plugins.media-keys custom-keybindings = ['/…/linscreencapture/']
```
instead of appending to the existing list.

**Workaround:** Do not enable "Set as default screenshot app" on GNOME if you have custom keyboard shortcuts. Instead, manually add the keybinding in GNOME Settings → Keyboard → Custom Shortcuts.

---

### Issue 2: GNOME 42+ — Incomplete Screenshot Disabling

**Severity:** Medium
**Affects:** Ubuntu 22.04+, Fedora 36+, Debian 12+

GNOME 42 replaced `gnome-screenshot` with a built-in screenshot UI (`org.gnome.shell.keybindings show-screenshot-ui`). LinScreenCapture disables the old `screenshot` key but not `show-screenshot-ui`, so GNOME's built-in tool may still intercept PrintScreen.

**Workaround:** Manually disable GNOME's screenshot UI:
```bash
gsettings set org.gnome.shell.keybindings show-screenshot-ui '[]'
```

---

### Issue 3: XFCE — Default Binding Not Overridden

**Severity:** Medium
**Affects:** Xubuntu, MX Linux, Linux Lite

LinScreenCapture adds a custom XFCE shortcut but does not remove `xfce4-screenshooter`'s default PrintScreen binding. Both may fire simultaneously, or XFCE's default may take precedence.

**Workaround:** Manually remove the default in XFCE Settings → Keyboard → Application Shortcuts.

---

### Issue 4: MATE — Compiz Incompatibility

**Severity:** Medium
**Affects:** Ubuntu MATE with Compiz window manager

LinScreenCapture writes keybindings to `org.mate.Marco.global-keybindings`, but users running Compiz (selectable via MATE Tweak) use a different keybinding system. The registration succeeds silently but has no effect.

Additionally, `mate-screenshot`'s own binding is not disabled, so it may intercept the key.

**Workaround:** Use Marco (not Compiz) as your window manager, or bind manually via CompizConfig Settings Manager.

---

### Issue 5: KDE Plasma — No Native Integration

**Severity:** High
**Affects:** Kubuntu, KDE Neon, any Plasma desktop

LinScreenCapture falls back to raw X11 `XGrabKey` on KDE, which:
- Cannot override Spectacle's PrintScreen binding (owned by `kglobalaccel5` at the compositor level)
- Does not work at all on Wayland sessions (KDE defaults to Wayland on many distros)
- Provides no error feedback if the grab fails

**Workaround:** Manually unbind PrintScreen from Spectacle in KDE System Settings → Shortcuts → Spectacle, then add a custom shortcut for `linscreencapture --capture`.

---

### Issue 6: No Error Reporting

**Severity:** Medium
**Affects:** All DEs

All `gsettings`, `dconf`, and `xfconf-query` commands run via `system()` with errors redirected to `/dev/null`. If registration fails (missing tools, permission denied, schema not found), the user receives no feedback — the checkbox appears to work but the keybinding is not active.

---

### Issue 7: Cinnamon — custom0 Collision

**Severity:** Low
**Affects:** Linux Mint (Cinnamon)

LinScreenCapture always uses the `custom0` slot for its keybinding. If the user already has a custom keybinding named `custom0` configured in Cinnamon's Keyboard Settings, LinScreenCapture will overwrite it.

**Workaround:** If you have existing custom keybindings, rename them to avoid the `custom0` slot before enabling LinScreenCapture's keybinding.

---

### Issue 8: Wayland — No Support

**Severity:** Medium (increasing over time)
**Affects:** All DEs on Wayland sessions

LinScreenCapture's keybinding system is entirely X11-based. The XGrabKey fallback and GDK event filter do nothing on Wayland. DE-native registration (gsettings/dconf) still works for Cinnamon/GNOME/XFCE/MATE to launch the command, but LinScreenCapture's own X11 screen capture will need porting to the XDG Desktop Portal screenshot API for Wayland.

Linux Mint currently defaults to X11 but is actively developing Wayland support for Cinnamon. Ubuntu has defaulted to Wayland since 21.04.

---

## Recommendations for Users

1. **Linux Mint (Cinnamon):** Use "Set as default screenshot app" — it works reliably
2. **All other DEs:** Configure the keybinding manually through your DE's keyboard settings, pointing to `linscreencapture --capture`
3. **KDE/Wayland users:** Manual configuration is required; the automatic setup will not work
4. **GNOME users:** Do NOT use the automatic setup if you have existing custom keyboard shortcuts — it will erase them

## For Developers

These issues are tracked for resolution in future releases. The Cinnamon path (`cinnamon_register`/`cinnamon_unregister`) serves as the reference implementation for how each DE path should work:
- Clear stale entries before registering
- Disable the DE's built-in screenshot handler
- Force the DE to reload (not just write to dconf)
- Clean up fully on unregister (restore defaults)
- Report errors to the user

---

## Clipboard — Screenshot Won't Paste Into a Terminal / CLI Consumer (e.g. Claude Code)

**Filed:** 2026-08-24
**Status:** Resolved (packaging fix — no application code change)
**Severity:** High — a core feature appears broken
**Affects:** Any Debian/Ubuntu/Mint install that does not already have `xclip`
**Component:** `install.sh`, `debian/control`, `packaging/build-deb.sh`

### Symptom

After a capture, LinScreenCapture reports "Image with annotations copied to clipboard" and pasting into
another GTK application (GIMP, Firefox) works. But pasting into a terminal-based or non-GTK
consumer — a CLI agent, an Electron app, a terminal emulator's image paste — yields nothing. The
clipboard looks like it was only partially populated.

### Producer vs. consumer (why "non-GTK" is about the *other* app)

A clipboard paste has two parties, and "non-GTK" refers to the **consumer**, not this app:

- **Producer** = LinScreenCapture (GTK). It owns the selection and advertises `image/png`.
- **Consumer** = whatever you paste *into*. A GTK/GDK consumer (GIMP, Firefox) reads the
  selection in-process, so it works. A non-GTK consumer (a terminal CLI like Claude Code) has
  no GDK loop and shells out to `xclip`/`wl-paste` — so it fails when that helper is absent.

LinScreenCapture being GTK is exactly *why* paste works into GIMP but not the terminal; the
producer's toolkit does not help the consumer.

### Root cause

**Not a defect in `copy_to_clipboard()`.** LinScreenCapture publishes the image correctly:

- `gtk_clipboard_set_image()` takes ownership of the X11 `CLIPBOARD` selection.
- `gtk_clipboard_store()` hands the payload to the session clipboard manager (`csd-clipboard` on
  Cinnamon), so the image survives LinScreenCapture exiting.
- GTK advertises the full image target set: `image/png`, `image/bmp`, `image/jpeg`, `image/tiff`,
  `image/webp`, alongside `TARGETS` / `SAVE_TARGETS` / `MULTIPLE` / `TIMESTAMP`.

The gap is on the **reading** side. GTK applications retrieve the selection through GDK directly.
Non-GTK consumers almost universally shell out to `xclip` (X11) or `wl-paste` (Wayland) to pull
`image/png` off the clipboard. Neither ships in a default Debian/Ubuntu/Mint desktop install, and
LinScreenCapture did not declare either — so on a clean system those consumers had no way to read the
selection, and failed silently.

### Verification

Measured on Linux Mint (Cinnamon, X11) against a live capture:

| Check | Result |
|---|---|
| Targets advertised after capture | `image/png`, `image/bmp`, `image/jpeg`, `image/tiff`, `image/webp` |
| `xclip -selection clipboard -t image/png -o` | valid PNG, 606x306, RGBA |
| Saved file `LinScreenCapture_20260824_155332.png` | 606x306, RGB |
| Pixel diff, clipboard vs saved file | **0 mismatches across all 185,436 pixels** |
| Image survives LinScreenCapture exiting | yes — clipboard manager retains it |

The clipboard payload is pixel-for-pixel the same screenshot that was written to disk.

### Fix

Declare the clipboard bridge so it is present on every install:

- `install.sh` — added `xclip` to the `apt install` line
- `debian/control` — `Recommends: xdg-utils, xclip`
- `packaging/build-deb.sh` — same `Recommends` in the generated control file

### Fix for an existing install

```bash
sudo apt install xclip
```

No rebuild needed — this is a runtime dependency, not a code change. Take a new screenshot and the
paste will work.

### Why it kept recurring, and the fix that holds (2026-09-30 correction)

This resurfaced, and a closer look corrected two earlier assumptions:

- **Earlier claim (wrong):** "Cinnamon has no persistent clipboard manager, so the app must stay
  running until you paste." **Correction:** `csd-clipboard` *is* running and *does* persist the
  image — including the `image/png` target — after LinScreenCapture exits. Verified end-to-end:
  a GTK producer set + stored an image, exited, and `xclip -selection clipboard -t image/png -o`
  still returned a valid PNG. So the app does **not** need to stay open.

- **Why prior "fixes" didn't hold:** evidence on this machine showed `xclip` had **never** been
  apt-installed (no entry in apt/dpkg logs back to 2025), yet apt packages clearly persist here
  (an unrelated package installed days earlier was still present). So the thing that "worked
  before" was a *transient* `xclip` reachable from `$HOME` (most likely a `~/.local/bin/xclip`
  shim) that got removed or overwritten between sessions — not a package. A non-executable shim
  left in `~/.local/bin` is worse than nothing: that dir precedes `/usr/bin` on `PATH`
  (`.profile`/`.bashrc`), so it *shadows* a real `xclip`.

**The durable fix is the package**, because apt state persists in this environment:

```bash
sudo apt install xclip        # survives across sessions, like any apt package
```

Do not rely on a `~/.local/bin/xclip` shim as the fix. It is only durable if it is executable and
not shadowing a real binary, and an automated agent cannot safely make it executable (installing an
auto-invoked executable onto `PATH` is treated as an unauthorized-persistence action and is blocked).

### Wayland note

The equivalent bridge on Wayland is `wl-clipboard` (`wl-paste`). LinScreenCapture's capture path is X11-only
today (see Issue 8 above), so this only becomes relevant once Wayland capture lands.

---

## Clipboard — Deferred Code Issues (Open)

Found while diagnosing the `xclip` issue above. None of these caused that bug, and none are
fixed yet — they are recorded here for a later pass. All line numbers are against `src/main_window.c`
as of v1.4.0.

### Issue A: Copy omits floating paste overlays

**Severity:** Medium — Copy silently produces a different image than the canvas shows
**Location:** `copy_to_clipboard()`, ~line 387

`copy_to_clipboard()` composites the base image and `annotations`, but never walks
`win_data->paste_overlays`. Both of the other render paths do:

| Path | Draws overlays? |
|---|---|
| Canvas draw, ~line 882 | yes |
| `save_image_with_annotations()`, ~line 2267 | yes |
| `copy_to_clipboard()` | **no** |

So after one or more `Ctrl+V` pastes, Copy/`Ctrl+C` yields the flat image while Save writes the
composited one. Flatten first as a workaround.

**Attempted fix, not landed.** Compositing `paste_overlays` into the combined surface — mirroring
the save path exactly — compiles clean under `-Werror`, but did not change the clipboard output in
testing: with two overlays visibly rendered on the canvas (confirmed by their dashed borders), the
copied image was still pixel-identical to the flat base image. Why the block does not take effect
is unresolved and needs a debugger pass, not more guessing. Note that the first paste lands at
offset (0,0) with identical content, so any test must use a second offset paste or a different
source image to be meaningful.

### Issue B: Hand-rolled ARGB→RGBA conversion

**Severity:** Low — latent, not currently reachable
**Location:** `copy_to_clipboard()`, ~lines 424-441

The manual pixel loop converting Cairo ARGB32 to `GdkPixbuf` RGBA:

- assumes little-endian byte order (`b,g,r,a` in memory); wrong on big-endian
- never un-premultiplies alpha, which Cairo stores premultiplied and `GdkPixbuf` expects straight

Neither bites today because every capture is fully opaque — measured `min alpha = 255` across a
live capture, and drawing annotations with `CAIRO_OPERATOR_OVER` onto an opaque base keeps it
opaque. It becomes a real defect the moment any partially transparent base image reaches this path.

`gdk_pixbuf_get_from_surface()` handles both correctly and is already used by the marquee copy path
(~line 668) and the save path (~line 2287). Replacing the loop with it verified pixel-identical on
a live capture round-trip (0 mismatches across 168,734 px), so this part is low-risk.

### Issue C: Redundant full-image pixbuf copy

**Severity:** Low — memory only
**Location:** `copy_to_clipboard()`, ~line 460

```c
GdkPixbuf* clipboard_pixbuf = gdk_pixbuf_copy(pixbuf);
gtk_clipboard_set_image(clipboard, clipboard_pixbuf);
```

`gtk_clipboard_set_image()` takes its own reference, so the extra `gdk_pixbuf_copy()` is unnecessary
and roughly doubles peak memory during a copy — about 10 MB extra for a 2565x1046 full-screen
capture. Passing `pixbuf` directly and unreffing it after is sufficient.

### Also noted

`gtk_clipboard_store()` runs on every copy. It is correct and wanted — it is what makes the image
survive LinScreenCapture exiting — but it forces the clipboard manager to snapshot the image synchronously in
every advertised format, so it is worth profiling on large captures if the UI ever feels like it
stalls after a capture.
