#include "../include/main_window.h"
#include <stdio.h>
#include <signal.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>

#define LOCK_FILE "/tmp/linscreencapture.lock"
#define SIGNAL_FILE "/tmp/linscreencapture.capture"

static MainWindow win = {0};
static volatile sig_atomic_t capture_requested = 0;

static void on_sigusr1(int sig) {
    (void)sig;
    capture_requested = 1;
}

// Periodically check if a capture was requested via signal
static gboolean check_capture_signal(gpointer data) {
    MainWindow* w = (MainWindow*)data;
    if (capture_requested) {
        capture_requested = 0;
        main_window_trigger_capture(w);
    }
    // Also check signal file (backup for when PID signaling fails)
    if (g_file_test(SIGNAL_FILE, G_FILE_TEST_EXISTS)) {
        unlink(SIGNAL_FILE);
        main_window_trigger_capture(w);
    }
    return G_SOURCE_CONTINUE;
}

static pid_t get_running_instance(void) {
    FILE* f = fopen(LOCK_FILE, "r");
    if (!f) return 0;

    pid_t pid = 0;
    if (fscanf(f, "%d", &pid) != 1) pid = 0;
    fclose(f);

    // Check if process is actually running
    if (pid > 0 && kill(pid, 0) == 0) {
        return pid;
    }
    return 0;
}

static void write_lock_file(void) {
    FILE* f = fopen(LOCK_FILE, "w");
    if (f) {
        fprintf(f, "%d\n", getpid());
        fclose(f);
    }
}

static void remove_lock_file(void) {
    unlink(LOCK_FILE);
}

static void signal_capture_to_instance(pid_t pid) {
    // Send SIGUSR1 to the running instance
    // (signal file backup removed — it caused double-capture)
    kill(pid, SIGUSR1);
}

int main(int argc, char* argv[]) {
    bool capture_mode = false;

    // Check for --capture flag
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--capture") == 0 || strcmp(argv[i], "-c") == 0) {
            capture_mode = true;
        }
    }

    // Check if another instance is already running
    pid_t existing = get_running_instance();
    if (existing > 0) {
        // Signal the running instance to capture
        signal_capture_to_instance(existing);
        return 0;
    }

    // We are the primary instance
    write_lock_file();
    atexit(remove_lock_file);

    // Set up signal handler for capture requests from other instances
    struct sigaction sa;
    sa.sa_handler = on_sigusr1;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    sigaction(SIGUSR1, &sa, NULL);

    if (!main_window_init(&win, argc, argv)) {
        fprintf(stderr, "Failed to initialize main window\n");
        return 1;
    }

    // If launched with --capture, schedule capture after the window is ready
    if (capture_mode) {
        // Hide window for background capture - will show after capture
        gtk_widget_hide(win.window);
        MainWindowData* data = (MainWindowData*)g_object_get_data(G_OBJECT(win.window), "window-data");
        if (data) data->capture_on_ready = true;
    }

    // Poll for capture signals from other instances every 200ms
    g_timeout_add(200, check_capture_signal, &win);

    gtk_main();

    main_window_cleanup(&win);
    return 0;
}
