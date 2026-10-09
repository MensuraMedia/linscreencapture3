#include "../include/keybinding_manager.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <glib.h>

// ---------------------------------------------------------------------------
// Desktop environment detection
// ---------------------------------------------------------------------------

static bool check_env_contains(const char* env_var, const char* needle) {
    const char* val = g_getenv(env_var);
    if (!val) return false;
    // Case-insensitive search
    char* val_lower = g_ascii_strdown(val, -1);
    char* needle_lower = g_ascii_strdown(needle, -1);
    bool found = (strstr(val_lower, needle_lower) != NULL);
    g_free(val_lower);
    g_free(needle_lower);
    return found;
}

static bool process_running(const char* name) {
    char cmd[128];
    snprintf(cmd, sizeof(cmd), "pgrep -x %s > /dev/null 2>&1", name);
    return (system(cmd) == 0);
}

DesktopEnv detect_desktop_environment(void) {
    // Primary: XDG_CURRENT_DESKTOP (most reliable)
    if (check_env_contains("XDG_CURRENT_DESKTOP", "Cinnamon") ||
        check_env_contains("XDG_CURRENT_DESKTOP", "X-Cinnamon"))
        return DE_CINNAMON;

    if (check_env_contains("XDG_CURRENT_DESKTOP", "GNOME") ||
        check_env_contains("XDG_CURRENT_DESKTOP", "ubuntu:GNOME") ||
        check_env_contains("XDG_CURRENT_DESKTOP", "Budgie"))
        return DE_GNOME;

    if (check_env_contains("XDG_CURRENT_DESKTOP", "XFCE"))
        return DE_XFCE;

    if (check_env_contains("XDG_CURRENT_DESKTOP", "MATE"))
        return DE_MATE;

    if (check_env_contains("XDG_CURRENT_DESKTOP", "KDE"))
        return DE_KDE;

    // Secondary: DESKTOP_SESSION
    if (check_env_contains("DESKTOP_SESSION", "cinnamon"))
        return DE_CINNAMON;
    if (check_env_contains("DESKTOP_SESSION", "gnome") ||
        check_env_contains("DESKTOP_SESSION", "ubuntu"))
        return DE_GNOME;
    if (check_env_contains("DESKTOP_SESSION", "xfce"))
        return DE_XFCE;
    if (check_env_contains("DESKTOP_SESSION", "mate"))
        return DE_MATE;
    if (check_env_contains("DESKTOP_SESSION", "plasma") ||
        check_env_contains("DESKTOP_SESSION", "kde"))
        return DE_KDE;

    // Tertiary: running processes
    if (process_running("cinnamon")) return DE_CINNAMON;
    if (process_running("gnome-shell")) return DE_GNOME;
    if (process_running("xfce4-panel")) return DE_XFCE;
    if (process_running("mate-panel")) return DE_MATE;
    if (process_running("plasmashell")) return DE_KDE;

    return DE_UNKNOWN;
}

const char* desktop_env_name(DesktopEnv de) {
    switch (de) {
        case DE_CINNAMON: return "Cinnamon";
        case DE_GNOME:    return "GNOME";
        case DE_XFCE:     return "XFCE";
        case DE_MATE:     return "MATE";
        case DE_KDE:      return "KDE Plasma";
        case DE_UNKNOWN:  return "Unknown";
    }
    return "Unknown";
}

const char* keybinding_to_string(KeyBinding key) {
    switch (key) {
        case KB_PRINTSCREEN:       return "Print";
        case KB_CTRL_PRINTSCREEN:  return "<Control>Print";
        case KB_SHIFT_PRINTSCREEN: return "<Shift>Print";
        case KB_CTRL_SHIFT_S:      return "<Control><Shift>s";
        case KB_CTRL_ALT_S:        return "<Control><Alt>s";
        default:                   return "";
    }
}

// ---------------------------------------------------------------------------
// Helper: run a shell command, return success
// ---------------------------------------------------------------------------

static bool run_cmd(const char* cmd) {
    int ret = system(cmd);
    return (ret == 0);
}

// ---------------------------------------------------------------------------
// Cinnamon keybinding (dconf custom-keybindings)
// ---------------------------------------------------------------------------

static bool cinnamon_unregister(void) {
    // Remove in-memory keybindings from Cinnamon's keybinding manager
    run_cmd("dbus-send --session --dest=org.Cinnamon --type=method_call "
            "/org/Cinnamon org.Cinnamon.Eval "
            "string:'Main.keybindingManager.remove_custom_keybindings();"
            " Main.keybindingManager.removeHotKey(\"linscreencapture\");"
            " Main.keybindingManager.removeHotKey(\"custom0\"); \"ok\";' "
            "2>/dev/null");
    // Remove dconf entries
    run_cmd("dconf reset -f /org/cinnamon/desktop/keybindings/custom-keybindings/custom0/");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings custom-list '[]'");
    // Also purge any stale GNOME-path entries (csd-media-keys reads both schemas)
    run_cmd("dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/ 2>/dev/null");
    run_cmd("gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"[]\" 2>/dev/null");
    // Restore Cinnamon's built-in screenshot keys
    run_cmd("gsettings reset org.cinnamon.desktop.keybindings.media-keys screenshot");
    run_cmd("gsettings reset org.cinnamon.desktop.keybindings.media-keys area-screenshot");
    run_cmd("gsettings reset org.cinnamon.desktop.keybindings.media-keys screenshot-clip 2>/dev/null");
    run_cmd("gsettings reset org.cinnamon.desktop.keybindings.media-keys window-screenshot 2>/dev/null");
    return true;
}

static bool cinnamon_register(KeyBinding key, const char* exec_path) {
    char cmd[512];

    // Purge any stale GNOME-path entries first (csd-media-keys reads both schemas)
    run_cmd("dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/ 2>/dev/null");
    run_cmd("gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"[]\" 2>/dev/null");

    // Cinnamon expects custom-list entries as 'customN' (not arbitrary names)
    run_cmd("gsettings set org.cinnamon.desktop.keybindings custom-list \"['custom0']\"");

    // Set the binding
    const char* binding = keybinding_to_string(key);
    snprintf(cmd, sizeof(cmd),
        "dconf write /org/cinnamon/desktop/keybindings/custom-keybindings/custom0/binding \"['%s']\"",
        binding);
    run_cmd(cmd);

    // Set the command
    snprintf(cmd, sizeof(cmd),
        "dconf write /org/cinnamon/desktop/keybindings/custom-keybindings/custom0/command \"'%s --capture'\"",
        exec_path);
    run_cmd(cmd);

    // Set the name
    run_cmd("dconf write /org/cinnamon/desktop/keybindings/custom-keybindings/custom0/name \"'LinScreenCapture Screenshot'\"");

    // Disable ALL Cinnamon built-in screenshot handlers to avoid conflict
    // Must use gsettings (not dconf write) — Cinnamon reads from gsettings
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys screenshot '[]'");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys area-screenshot '[]'");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys screenshot-clip '[]' 2>/dev/null");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys window-screenshot '[]' 2>/dev/null");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys window-screenshot-clip '[]' 2>/dev/null");
    run_cmd("gsettings set org.cinnamon.desktop.keybindings.media-keys area-screenshot-clip '[]' 2>/dev/null");

    // Force Cinnamon to reload custom keybindings via D-Bus
    // First remove all existing custom keybindings (purges stale in-memory entries),
    // then re-setup from dconf. This mirrors what Cinnamon's keyboard GUI does.
    run_cmd("dbus-send --session --dest=org.Cinnamon --type=method_call "
            "/org/Cinnamon org.Cinnamon.Eval "
            "string:'Main.keybindingManager.remove_custom_keybindings();"
            " Main.keybindingManager.removeHotKey(\"linscreencapture\");"
            " Main.keybindingManager.setup_custom_keybindings(); \"ok\";' "
            "2>/dev/null");

    return true;
}

// ---------------------------------------------------------------------------
// GNOME keybinding (gsettings custom-keybindings)
// ---------------------------------------------------------------------------

static bool gnome_unregister(void) {
    // Clear the custom keybinding list and wipe the entire linscreencapture subtree
    run_cmd("gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"[]\" 2>/dev/null");
    run_cmd("dconf reset -f /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/ 2>/dev/null");
    return true;
}

static bool gnome_register(KeyBinding key, const char* exec_path) {
    char cmd[512];

    // Add linscreencapture to custom keybindings list
    run_cmd("gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "
            "\"['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/']\" 2>/dev/null");

    // Set binding
    const char* binding = keybinding_to_string(key);
    snprintf(cmd, sizeof(cmd),
        "dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/binding \"'%s'\"",
        binding);
    run_cmd(cmd);

    // Set command
    snprintf(cmd, sizeof(cmd),
        "dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/command \"'%s --capture'\"",
        exec_path);
    run_cmd(cmd);

    // Set name
    run_cmd("dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linscreencapture/name \"'LinScreenCapture Screenshot'\"");

    // Disable GNOME's built-in screenshot for the key
    if (key == KB_PRINTSCREEN) {
        run_cmd("gsettings set org.gnome.settings-daemon.plugins.media-keys screenshot \"''\" 2>/dev/null");
        run_cmd("gsettings set org.gnome.shell.keybindings screenshot \"@as []\" 2>/dev/null");
    }

    return true;
}

// ---------------------------------------------------------------------------
// XFCE keybinding (xfconf-query)
// ---------------------------------------------------------------------------

static bool xfce_unregister(void) {
    // Remove LinScreenCapture command from XFCE shortcuts
    run_cmd("xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/Print' -r 2>/dev/null");
    run_cmd("xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/<Control>Print' -r 2>/dev/null");
    run_cmd("xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/<Shift>Print' -r 2>/dev/null");
    run_cmd("xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/<Control><Shift>s' -r 2>/dev/null");
    run_cmd("xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/<Control><Alt>s' -r 2>/dev/null");
    return true;
}

static bool xfce_register(KeyBinding key, const char* exec_path) {
    char cmd[512];
    const char* binding = keybinding_to_string(key);

    // First remove any existing binding for this key
    snprintf(cmd, sizeof(cmd),
        "xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/%s' -r 2>/dev/null",
        binding);
    run_cmd(cmd);

    // Set new binding
    snprintf(cmd, sizeof(cmd),
        "xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/%s' -n -t string -s '%s --capture'",
        binding, exec_path);
    return run_cmd(cmd);
}

// ---------------------------------------------------------------------------
// MATE keybinding (gsettings)
// ---------------------------------------------------------------------------

static bool mate_unregister(void) {
    run_cmd("gsettings set org.mate.Marco.global-keybindings run-command-screenshot '' 2>/dev/null");
    return true;
}

static bool mate_register(KeyBinding key, const char* exec_path) {
    char cmd[512];
    const char* binding = keybinding_to_string(key);

    // Set the screenshot command
    snprintf(cmd, sizeof(cmd),
        "gsettings set org.mate.Marco.global-keybindings run-command-screenshot '%s' 2>/dev/null",
        binding);
    run_cmd(cmd);

    // Set the command to execute
    snprintf(cmd, sizeof(cmd),
        "gsettings set org.mate.Marco.keybinding-commands command-screenshot '%s --capture' 2>/dev/null",
        exec_path);
    return run_cmd(cmd);
}

// ---------------------------------------------------------------------------
// X11 fallback (XGrabKey — works on any X11 DE but may conflict)
// ---------------------------------------------------------------------------

static bool x11_register(KeyBinding key, const char* exec_path) {
    (void)exec_path;
    (void)key;
    // X11 grab is handled directly in main_window.c via the existing
    // XGrabKey mechanism. This fallback just returns true to indicate
    // the caller should use the X11 path.
    return true;
}

static bool x11_unregister(void) {
    return true;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

bool keybinding_register(DesktopEnv de, KeyBinding key, const char* exec_path) {
    if (key == KB_NONE) return false;
    if (!exec_path || !exec_path[0]) return false;

    switch (de) {
        case DE_CINNAMON: return cinnamon_register(key, exec_path);
        case DE_GNOME:    return gnome_register(key, exec_path);
        case DE_XFCE:     return xfce_register(key, exec_path);
        case DE_MATE:     return mate_register(key, exec_path);
        case DE_KDE:      return x11_register(key, exec_path);  // KDE: fallback for now
        case DE_UNKNOWN:  return x11_register(key, exec_path);
    }
    return false;
}

bool keybinding_unregister(DesktopEnv de) {
    switch (de) {
        case DE_CINNAMON: return cinnamon_unregister();
        case DE_GNOME:    return gnome_unregister();
        case DE_XFCE:     return xfce_unregister();
        case DE_MATE:     return mate_unregister();
        case DE_KDE:      return x11_unregister();
        case DE_UNKNOWN:  return x11_unregister();
    }
    return false;
}
