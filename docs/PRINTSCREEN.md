# PrintScreen — user guide

How the capture hotkey works, from the key press to the paste. The technical reference, with the internals and the
history of every bug, is [CAPTURE.md](CAPTURE.md); this page is for using it, changing it and fixing it.

## In one paragraph

LinScreenCapture runs as a small background agent from the moment you log in. Press **PrintScreen**, anywhere —
over any application, on the desktop, or inside LinScreenCapture itself. The screen freezes; drag a box around what
you want. The moment you **release the mouse button** the capture is on the clipboard, as a lossless PNG at full
resolution, ready to paste into a chat, a document, a browser or a terminal. It is also saved to your screenshot
folder and loaded into the LinScreenCapture editor, without the editor popping up. Esc cancels and leaves nothing
behind.

## Taking a screenshot

| Step | What happens |
| --- | --- |
| Press **PrintScreen** | The screen freezes under a light veil with a crosshair, about 80 ms after the key. |
| Drag a box | A size chip shows the box's width × height. **Shift** keeps it square; **Space** (held) moves the box while you draw. |
| Release the mouse button | The capture happens immediately: clipboard first (about 20 ms), then the save folder, then the editor. |
| **Ctrl+A** instead of dragging | Captures the whole screen at once. |
| **Esc** | Cancels: nothing is copied, saved or loaded. |

Then paste anywhere with **Ctrl+V**.

**Need precision?** Use **Region Plus** instead (the capture mode bar at the top of the frozen screen, or the
Region Plus button in the editor's CAPTURE group): the box keeps eight resize handles and arrow-key nudging, and you
confirm with **Enter** or a double-click. PrintScreen itself always runs the fast Region capture.

## What you get

- **On the clipboard:** the exact pixels as PNG (lossless, the screen's own resolution, no scaling, no border), plus
  JPEG, BMP, TIFF and WebP conversions for applications that ask for those. The image is handed to the desktop's
  clipboard manager, so it can still be pasted after LinScreenCapture quits.
- **In the save folder:** a file named by Settings → Capture (prefix, sequence or timestamp, PNG/JPEG/WebP).
- **In the editor:** the capture is the current document and sits in the left rail's clipboard tray. The editor stays
  hidden unless it was already open (then it comes back holding the capture) or you switched on *The hotkey opens
  the editor*.

## The panel icon

While LinScreenCapture runs there is an **orange icon** (the application icon: an #ffa222 tile with a white selection frame and a pointer; the same icon shows in Alt+Tab and the menu) in the panel's
system tray.

- **Double-click** it to open the editor.
- **Right-click** it for the menu: *Capture region to clipboard*, *Open editor*, *Quit*.
- Hide it with Settings → System → *Panel icon*. The agent keeps running without it.

## Settings → System

| Setting | Default | What it does |
| --- | --- | --- |
| **Run at startup** | on | Starts the agent at login (without a window), so PrintScreen works straight away. Turning it off in Cinnamon's *Startup Applications* also counts. |
| Keep running in the background | on | Closing the editor only hides it. **Quit** (Ctrl+Q, or the panel icon's menu) ends the agent. |
| Panel icon | on | The orange icon described above. |
| The hotkey opens the editor | off | On: show the editor after every hotkey capture. |
| **Key** | PrintScreen | The capture hotkey: see below. |
| Register with the desktop | on | Writes the hotkey into Cinnamon's keyboard shortcuts and re-applies it every time the agent starts. |

## Choosing a different key

Settings → System → *Capture hotkey* → **Key**:

- **Presets:** PrintScreen, Ctrl+PrintScreen, Shift+PrintScreen, Ctrl+Shift+S, Ctrl+Alt+S, or Off.
- **Custom… / Record…:** a small window opens and takes the next key or combination you press.
  - PrintScreen, the function keys (F1–F12), Pause and similar keys work on their own.
  - Letters, digits and symbols need Ctrl, Alt, Shift or Super, so the hotkey never steals normal typing.
  - **Esc** cancels and keeps the old key; **Backspace** turns the hotkey off.
  - While the window is open the current hotkey is released, so you can record it again.

The new key works at once; there is no need to log out. LinScreenCapture also takes the key away from Cinnamon's
built-in screenshot tool, but it never changes a shortcut that belongs to another application. If the key is
already used by another application's custom shortcut, the agent's log says so; pick another key or change that
shortcut.

## When PrintScreen does nothing

Work through these in order:

1. **Is the agent running?** Look for the orange panel icon. If it is missing, start LinScreenCapture from the menu
   (or `linscreencapture --background`) and check that *Run at startup* is on.
2. **Is the key registered?** In Cinnamon's *Keyboard* settings → *Shortcuts* → *Custom Shortcuts* there should be an
   entry named **LinScreenCapture** with your key and the command `…/linscreencapture --capture`. If not, open
   Settings → System, switch *Register with the desktop* off and on again.
3. **Is another program grabbing the key?** An older LinShot (`linshot`) process, or another screenshot tool, can
   swallow PrintScreen. Quit it (`pgrep -af linshot`), or remove it from *Startup Applications*.
4. **Is Cinnamon running an old command?** `grep -i linscreencapture ~/.xsession-errors` shows what Cinnamon actually
   executes. Toggling *Register with the desktop* makes Cinnamon reload its shortcuts.
5. **Run the end-to-end probe:** `python3 tools/hotkey_probe.py --key Print` presses the key, drags a box and checks
   the clipboard (it moves the real mouse, so keep your hands off it). Exit status 0 means everything works.
6. Still stuck: start the agent with `linscreencapture --background --debug` and look for `capture requested` after
   the key press. [CAPTURE.md](CAPTURE.md) §4 has the detailed diagnosis.

## Limits

- Automatic key registration is implemented for **Cinnamon** (Linux Mint). On other desktops bind the command
  `linscreencapture --capture` to a key yourself in the desktop's keyboard settings ([INSTALL.md](../INSTALL.md)).
- On **Wayland** the screen is captured through the desktop portal, which may show its own permission dialog.
- Countdown, pin-to-screen and scrolling capture are still to come (Phase 6).
