#include "../include/utils.h"
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
#include <pwd.h>

#define HISTORY_DIR "LinScreenCapture"

char* get_history_dir(void) {
    const char* home = getenv("HOME");
    if (!home) {
        struct passwd* pw = getpwuid(getuid());
        home = pw->pw_dir;
    }
    
    char* history_dir = g_build_filename(home, "Downloads", HISTORY_DIR, NULL);
    
    // Create directory if it doesn't exist
    struct stat st = {0};
    if (stat(history_dir, &st) == -1) {
        mkdir(history_dir, 0700);
    }
    
    return history_dir;
} 