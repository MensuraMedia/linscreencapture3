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
(`make unlauncher` removes it). `python3 -m linscreencapture --capture` starts a region capture straight away;
`--debug` prints start-up and capture diagnostics.

## Install as a package

```bash
python3 -m venv --system-site-packages .venv && . .venv/bin/activate
pip install -e .[dev]     # editable; `linscreencapture` is now on PATH
```

A `.deb` package and a system-wide `.desktop` entry arrive with the 3.0 release (Phase 7).

## PrintScreen hotkey

Binding PrintScreen to `linscreencapture --capture` from inside the app arrives in Phase 6. Until then bind it in
your desktop's keyboard settings (Cinnamon: Keyboard → Shortcuts → Custom; GNOME: Settings → Keyboard → Custom
Shortcuts) and disable the desktop's own screenshot binding on that key.

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
