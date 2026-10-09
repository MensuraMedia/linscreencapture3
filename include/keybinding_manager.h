#ifndef KEYBINDING_MANAGER_H
#define KEYBINDING_MANAGER_H

#include <stdbool.h>

// Supported desktop environments
typedef enum {
    DE_CINNAMON,
    DE_GNOME,
    DE_XFCE,
    DE_MATE,
    DE_KDE,
    DE_UNKNOWN
} DesktopEnv;

// Shortcut key identifiers (matches main_window.c ShortcutKey enum values)
typedef enum {
    KB_NONE = 0,
    KB_PRINTSCREEN,
    KB_CTRL_PRINTSCREEN,
    KB_SHIFT_PRINTSCREEN,
    KB_CTRL_SHIFT_S,
    KB_CTRL_ALT_S
} KeyBinding;

// Detect the current desktop environment
DesktopEnv detect_desktop_environment(void);

// Get human-readable name for a desktop environment
const char* desktop_env_name(DesktopEnv de);

// Register a system-wide keybinding for LinScreenCapture capture
// exec_path: full path to the linscreencapture binary
// Returns true on success
bool keybinding_register(DesktopEnv de, KeyBinding key, const char* exec_path);

// Unregister any existing LinScreenCapture keybinding
bool keybinding_unregister(DesktopEnv de);

// Get the dconf/gsettings binding string for a key (e.g. "Print", "<Control>Print")
const char* keybinding_to_string(KeyBinding key);

#endif // KEYBINDING_MANAGER_H
