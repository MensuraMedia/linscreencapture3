# Installing LinScreenCapture 3

LinScreenCapture 3 is a Python 3 + GTK 4 application. There is nothing to compile: install the system
libraries, clone, build the resource bundle, run.

## Requirements

| Component | Minimum | Debian / Ubuntu / Mint package |
| --- | --- | --- |
| Python | 3.11 | `python3` |
| GTK | 4.10 | `gir1.2-gtk-4.0` |
| libadwaita | 1.4 | `gir1.2-adw-1` |
| PyGObject, PyCairo | 3.46 / 1.25 | `python3-gi python3-gi-cairo python3-cairo` |
| Pillow, NumPy | 10 / 1.26 | `python3-pil python3-numpy` |
| python-xlib (X11 capture) | 0.33 | `python3-xlib` |
| XDG portal (Wayland capture) | 1.14 | `xdg-desktop-portal xdg-desktop-portal-gtk` (or `-gnome`, `-kde`, `-xapp`) |
| Resource compiler | | `libglib2.0-dev-bin` |
| Clipboard helper for terminals (optional) | | `xclip` (X11) or `wl-clipboard` (Wayland) |
| Fonts (optional) | | `fonts-ubuntu` |

```bash
sudo apt install python3 python3-gi python3-gi-cairo python3-cairo python3-pil python3-numpy python3-xlib \
                 gir1.2-gtk-4.0 gir1.2-adw-1 xdg-desktop-portal xdg-desktop-portal-gtk libglib2.0-dev-bin fonts-ubuntu
```

## Run from a checkout

```bash
git clone https://github.com/MensuraMedia/linscreencapture3.git
cd linscreencapture3
make resources            # compiles data/ and the stylesheet into linscreencapture/linscreencapture.gresource
python3 -m linscreencapture
```

`make launcher` installs a **LinScreenCapture3** entry in your application menu that runs this checkout
(`~/.local/share/applications/com.mensuramedia.LinScreenCapture.desktop`, with the icon; `make unlauncher` removes it). `python3 -m linscreencapture --capture` runs the hotkey capture (`app.hotkey-capture`):
the fast Region capture, copied to the clipboard, saved and loaded into the studio without popping it up; with no
agent running, that process becomes the agent. `--background` starts the agent with no window; `--debug` prints
start-up and capture diagnostics. Capture behaviour in full: [docs/CAPTURE.md](docs/CAPTURE.md).

## Install

Three ways, all installing the same files (the `.deb` is built from `install.sh`):

### 1. The Debian package (Linux Mint, Ubuntu, Debian)

```bash
sudo apt install ./packaging/linscreencapture_3.0.0~dev1_all.deb
```

`apt` pulls in the dependencies. The package installs `/usr/bin/linscreencapture`, the menu entry
`com.mensuramedia.LinScreenCapture.desktop`, the icon in every hicolor size and the documentation in
`/usr/share/doc/linscreencapture/`. Remove it with `sudo apt remove linscreencapture`. Rebuild it from a checkout
with `make deb` (or `packaging/build-deb.sh`); the version comes from `pyproject.toml` (`3.0.0.dev1` → `3.0.0~dev1`).

### 2. The installer script

```bash
./install.sh --deps          # for this user, into ~/.local; --deps installs the system packages with apt first
./install.sh --system        # for all users, into /usr/local (sudo)
./install.sh --uninstall     # remove it again (add --system for the system-wide copy)
```

| Option | Effect |
| --- | --- |
| `--user` (default) | install into `~/.local`: no root needed |
| `--system` | install into `/usr/local` with `sudo` |
| `--deps` | `apt-get install` the runtime and build packages first |
| `--no-start` | do not start the background agent afterwards (it starts by default) |
| `--force` | replace a `linscreencapture` launcher the script did not write (a development wrapper) |
| `--prefix DIR`, `--destdir DIR` | packaging: install under `DESTDIR/PREFIX` (the `.deb` uses `--prefix /usr`) |
| `--uninstall` | remove the files; the user mode also removes the login autostart entry |

Layout under the prefix: `lib/linscreencapture/` (the Python package with its compiled `.gresource`, and the
application icon the panel icon reads), `bin/linscreencapture` (a launcher running `python3 -m linscreencapture`),
`share/applications/com.mensuramedia.LinScreenCapture.desktop` and `share/icons/hicolor/*/apps/`.

### 3. Run from the checkout (development)

See *Run from a checkout* above; `make launcher` adds the menu entry.

### After installing

The first start turns on *Run at startup* and registers **PrintScreen** with Cinnamon, so from then on PrintScreen
captures a region to the clipboard and the orange panel icon is there (double-click opens the editor). How to use
it, change the key or fix a dead key: [docs/PRINTSCREEN.md](docs/PRINTSCREEN.md).

The menu entry is named after the application id and carries `StartupWMClass=com.mensuramedia.LinScreenCapture`,
the window's `WM_CLASS` (the app sets its program name to the id before GTK starts), so Alt+Tab, the window list
and the panel show the application icon.

## Capture hotkey

**Cinnamon:** works out of the box: the default hotkey is PrintScreen and *Register with the desktop* is on. To change
it, open Settings → System → *Capture hotkey* and pick a preset (Off, PrintScreen, Ctrl+PrintScreen,
Shift+PrintScreen, Ctrl+Shift+S, Ctrl+Alt+S) or press **Record…** and press any key combination. *Run at startup*
(Settings → System → Startup, on by default) starts the agent at login. The agent writes a Cinnamon
custom shortcut running `linscreencapture --capture`, removes the key from Cinnamon's built-in screenshot bindings,
makes Cinnamon reload, and re-applies the binding at every start. The command is the absolute path of
`linscreencapture` on `PATH`, or `python3 -m linscreencapture --capture` with `PYTHONPATH` set to the checkout.
Shortcuts that belong to other applications are never overwritten.

**Other desktops** (GNOME, Xfce, MATE, KDE): bind `linscreencapture --capture` by hand in the desktop's keyboard
settings (GNOME: Settings → Keyboard → Custom Shortcuts) and remove the desktop's own screenshot binding from that
key; on GNOME also clear `org.gnome.shell.keybindings show-screenshot-ui`.

A hotkey that does nothing: see [docs/CAPTURE.md](docs/CAPTURE.md) §4.

## Upgrading from LinScreenCapture 1.x

Nothing to do: on first start the 1.x settings file `~/.config/linshot/settings.conf` is read once and copied to
`~/.config/linscreencapture/settings.conf` (colours, widths, shadows, save folder, naming). The old file is left
untouched. The 1.x binary and its CMake build are gone from this repository; the 1.4 sources remain in the
[original repository](https://github.com/MensuraMedia/linscreencapture).

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `FileNotFoundError: … linscreencapture.gresource missing` | resources not compiled | `make resources` |
| `Namespace Adw not available` | libadwaita bindings missing | `sudo apt install gir1.2-adw-1` |
| Capture fails with "no capture backend" | no X11 display and no portal | install `xdg-desktop-portal` + a backend for your desktop |
| Window mode falls back to region | the backend has no window list (Wayland, portal) | use Region, or run on X11 |
| Pasting into a terminal app gives nothing | terminal apps shell out to a clipboard helper | `sudo apt install xclip` (X11) or `wl-clipboard` |
