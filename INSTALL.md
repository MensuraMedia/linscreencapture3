# LinScreenCapture Installation Guide

> Complete guide for installing LinScreenCapture on Debian-based Linux systems.
> Covers Linux Mint, Ubuntu, Pop!_OS, Debian, Xubuntu, MX Linux, and derivatives.

**Version:** 1.4.0 Beta
**Platform:** Linux (Debian-based, X11)
**License:** CC BY-NC 4.0

---

## Quick Start

Choose the method that fits your needs:

| Method | Best For | Difficulty | Time |
|---|---|---|---|
| [.deb Package](#option-1-deb-package-recommended) | Most users | Easy | 2 min |
| [Build from Source](#option-2-build-from-source) | Developers, customization | Moderate | 5 min |
| [CMake Install](#option-3-cmake-system-install) | System-wide install from source | Moderate | 5 min |
| [Portable Build](#option-4-portable-build-no-install) | Testing, no root needed | Easy | 3 min |

---

## System Requirements

### Minimum
- Debian-based Linux distribution (Debian 11+, Ubuntu 20.04+, Linux Mint 20+)
- X11 display server (Wayland has limited support — see [Known Issues](KNOWN_ISSUES.md))
- GTK 3.20 or later
- 50 MB disk space

### Supported Desktop Environments
- **Linux Mint Cinnamon** — full support including automatic PrintScreen keybinding
- **GNOME** — supported with manual keybinding setup recommended (see [Keybinding Setup](#keybinding-setup))
- **XFCE** — supported with manual keybinding setup recommended
- **MATE** — supported (Marco window manager required for automatic keybinding)
- **KDE Plasma** — basic support, manual keybinding required
- **Other X11 DEs** — should work; keybinding requires manual configuration

---

## Option 1: .deb Package (Recommended)

The simplest way to install LinScreenCapture. Handles dependencies, icons, desktop integration, and menu entries automatically.

### Step 1: Install build dependencies

```bash
sudo apt update
sudo apt install cmake build-essential libgtk-3-dev libx11-dev libcairo2-dev dpkg-dev
```

### Step 2: Download and build the package

```bash
git clone https://github.com/MensuraMedia/linscreencapture.git
cd linscreencapture
bash packaging/build-deb.sh
```

### Step 3: Install

```bash
sudo dpkg -i linscreencapture_1.0.0_amd64.deb
```

If there are missing dependencies:
```bash
sudo apt --fix-broken install
```

### Step 4: Launch

LinScreenCapture appears in your application menu under **Graphics** or **Utilities**. You can also run:
```bash
linscreencapture
```

### Uninstall

```bash
sudo apt remove linscreencapture
```

To also remove configuration files:
```bash
sudo apt purge linscreencapture
rm -rf ~/.config/linscreencapture
```

---

## Option 2: Build from Source

For developers or users who want to customize before building.

### Step 1: Install dependencies

**Debian / Ubuntu / Linux Mint:**
```bash
sudo apt update
sudo apt install cmake build-essential libgtk-3-dev libx11-dev libcairo2-dev xclip
```

**Verify dependencies are installed:**
```bash
pkg-config --modversion gtk+-3.0   # Should show 3.x.x
pkg-config --modversion x11        # Should show 1.x.x
pkg-config --modversion cairo      # Should show 1.x.x
```

### Step 2: Clone and build

```bash
git clone https://github.com/MensuraMedia/linscreencapture.git
cd linscreencapture
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
```

### Step 3: Run

```bash
./linscreencapture
```

The binary is self-contained — it only needs the `resources/` folder in the same directory for icons.

### Build Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `gtk+-3.0 not found` | GTK3 dev headers missing | `sudo apt install libgtk-3-dev` |
| `x11 not found` | X11 dev headers missing | `sudo apt install libx11-dev` |
| `cairo not found` | Cairo dev headers missing | `sudo apt install libcairo2-dev` |
| `cmake: command not found` | CMake not installed | `sudo apt install cmake` |
| `cc: command not found` | No C compiler | `sudo apt install build-essential` |
| Warnings treated as errors | Expected — strict mode | All warnings must be fixed before merge |

### Runtime Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Screenshot pastes into GIMP/Firefox but not into a terminal, CLI tool, or Electron app | `xclip` missing — non-GTK apps read the X11 clipboard through it | `sudo apt install xclip` |

`xclip` is the bridge non-GTK programs use to read `image/png` off the X11 clipboard. LinScreenCapture
publishes the image correctly without it, but those consumers cannot see it. See
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the full write-up.

---

## Option 3: CMake System Install

Installs LinScreenCapture system-wide to `/usr/local/` with proper icon and desktop file integration.

### Steps 1-2: Same as Build from Source above

### Step 3: Install system-wide

```bash
cd build
sudo make install
```

This installs:
- Binary to `/usr/local/bin/linscreencapture`
- Desktop file to `/usr/local/share/applications/linscreencapture.desktop`
- Icons to `/usr/local/share/icons/hicolor/` (16px through 256px)

### Step 4: Update system caches

```bash
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor
sudo update-desktop-database /usr/share/applications
```

### Uninstall

From the build directory:
```bash
sudo make uninstall     # If supported
```

Or manually:
```bash
sudo rm /usr/local/bin/linscreencapture
sudo rm /usr/local/share/applications/linscreencapture.desktop
sudo rm /usr/local/share/icons/hicolor/*/apps/linscreencapture.png
rm -rf ~/.config/linscreencapture
```

---

## Option 4: Portable Build (No Install)

Run LinScreenCapture directly from the source tree without installing anything system-wide. No root access needed.

```bash
# Install dependencies (one-time, requires sudo)
sudo apt install cmake build-essential libgtk-3-dev libx11-dev libcairo2-dev xclip

# Clone and build
git clone https://github.com/MensuraMedia/linscreencapture.git
cd linscreencapture
mkdir -p build && cd build
cmake .. && make -j$(nproc)

# Run directly
./linscreencapture
```

The build directory contains everything needed:
```
build/
  linscreencapture          # The binary
  resources/       # Icons and assets (copied automatically)
```

You can move the `build/` folder anywhere. To create a desktop shortcut manually, see [Manual Desktop Integration](#manual-desktop-integration) below.

---

## Post-Install Setup

### Keybinding Setup

LinScreenCapture can register a system-wide keybinding (default: PrintScreen) to capture screenshots instantly.

#### Linux Mint (Cinnamon) — Automatic

1. Open LinScreenCapture → **Settings** tab
2. Check **"Set as default screenshot app"**
3. Select your preferred shortcut key
4. PrintScreen is immediately active — no restart needed

#### Ubuntu / GNOME — Manual Recommended

Automatic registration has a known issue on GNOME (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)). Configure manually instead:

1. Open **Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts**
2. Click **+** to add a new shortcut
3. Set:
   - **Name:** LinScreenCapture
   - **Command:** `linscreencapture --capture` (or full path: `/usr/local/bin/linscreencapture --capture`)
   - **Shortcut:** Press PrintScreen (or your preferred key)
4. If PrintScreen is already bound, first disable it:
   ```bash
   # GNOME 41 and earlier
   gsettings set org.gnome.settings-daemon.plugins.media-keys screenshot '[]'

   # GNOME 42+ (Ubuntu 22.04+)
   gsettings set org.gnome.shell.keybindings show-screenshot-ui '[]'
   ```

#### Xubuntu / XFCE — Manual Recommended

1. Open **Settings → Keyboard → Application Shortcuts**
2. Find and remove the existing PrintScreen entry (usually `xfce4-screenshooter`)
3. Click **Add**, enter `linscreencapture --capture`, then press PrintScreen when prompted

#### Ubuntu MATE — Manual Recommended

1. Open **Control Center → Keyboard Shortcuts**
2. Find **Take a screenshot** and disable or change it
3. Add a custom shortcut:
   - **Command:** `linscreencapture --capture`
   - **Key:** PrintScreen

#### KDE Plasma — Manual Required

1. Open **System Settings → Shortcuts → Spectacle**
2. Disable PrintScreen bindings for Spectacle
3. Go to **Custom Shortcuts → Edit → New → Global Shortcut → Command/URL**
4. Set the command to `linscreencapture --capture` and bind to PrintScreen

> **Note:** LinScreenCapture requires X11. On KDE Wayland sessions, the keybinding may work but screen capture functionality is limited.

### Auto-Start at Login (Optional)

To launch LinScreenCapture automatically when you log in:

```bash
mkdir -p ~/.config/autostart
cp /usr/share/applications/linscreencapture.desktop ~/.config/autostart/
```

Or if running from source:
```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/linscreencapture.desktop << EOF
[Desktop Entry]
Type=Application
Name=LinScreenCapture
Exec=/path/to/your/linscreencapture
Hidden=false
X-GNOME-Autostart-enabled=true
EOF
```

### Manual Desktop Integration

If you used the portable build and want a menu entry:

```bash
# Create desktop file
cat > ~/.local/share/applications/linscreencapture.desktop << EOF
[Desktop Entry]
Version=1.4
Type=Application
Name=LinScreenCapture
GenericName=Screenshot Tool
Comment=Capture, annotate, and share screenshots
Exec=/full/path/to/linscreencapture
Icon=/full/path/to/linscreencapture/resources/icons/linscreencapture-128.png
Terminal=false
Categories=Utility;Graphics;GTK;
Keywords=screenshot;capture;screen;annotation;
StartupNotify=true

[Desktop Action capture]
Name=Capture Screenshot
Exec=/full/path/to/linscreencapture --capture
EOF

# Update desktop database
update-desktop-database ~/.local/share/applications/
```

Replace `/full/path/to/` with the actual path to your LinScreenCapture binary and source directory.

---

## Command-Line Usage

```
linscreencapture                 Launch the LinScreenCapture GUI
linscreencapture --capture       Capture a screenshot immediately (area selection)
linscreencapture -c              Short form of --capture
```

When LinScreenCapture is already running, `linscreencapture --capture` signals the existing instance to start a capture instead of launching a second window.

---

## Configuration

LinScreenCapture stores settings in:
```
~/.config/linscreencapture/settings.conf
```

Settings include:
- Screenshot save path
- Filename format and prefix
- Per-tool colors, widths, and shadow options
- Text font, size, bold, italic
- Selected shortcut key
- Default screenshot app toggle

All settings are configurable through the **Settings** and **Tools** tabs in the GUI. Manual editing of the config file is not required.

To reset all settings to defaults:
```bash
rm ~/.config/linscreencapture/settings.conf
```

---

## Verifying Your Installation

After installation, verify everything is working:

```bash
# Check the binary runs
linscreencapture --help 2>&1 || linscreencapture &

# Check desktop integration (should show linscreencapture.desktop)
ls ~/.local/share/applications/linscreencapture.desktop 2>/dev/null || \
ls /usr/share/applications/linscreencapture.desktop 2>/dev/null || \
ls /usr/local/share/applications/linscreencapture.desktop 2>/dev/null

# Check your desktop environment (helps with keybinding setup)
echo $XDG_CURRENT_DESKTOP

# Test capture mode
linscreencapture --capture
```

---

## Updating

### From .deb package
```bash
cd linscreencapture
git pull
bash packaging/build-deb.sh
sudo dpkg -i linscreencapture_1.0.0_amd64.deb
```

### From source build
```bash
cd linscreencapture
git pull
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
```

---

## Getting Help

- **Known issues:** [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
- **Bug reports:** [github.com/MensuraMedia/linscreencapture/issues](https://github.com/MensuraMedia/linscreencapture/issues)
- **Source code:** [github.com/MensuraMedia/linscreencapture](https://github.com/MensuraMedia/linscreencapture)
