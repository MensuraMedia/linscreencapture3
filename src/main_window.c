#include "../include/main_window.h"
#include "../include/screen_capture.h"
#include "../include/capture_overlay.h"
#include "../include/editor_tools.h"
#include "../include/sidebar_icons.h"
#include "../include/keybinding_manager.h"
#include "../include/utils.h"
#include <glib.h>
#include <stdlib.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>
#include <pwd.h>
#include <glib/gstdio.h>
#include <math.h>
#include <gdk/gdkx.h>
#include <X11/Xlib.h>
#include <X11/keysym.h>

// Wrapper to suppress warn_unused_result for system() calls
static inline void run_cmd(const char* cmd) {
    if (system(cmd) == -1) { /* intentionally ignored */ }
}

typedef enum {
    FILENAME_LINSCREENCAPTURE_NUMBER = 0,
    FILENAME_SCREENSHOT_NUMBER,
    FILENAME_LINSCREENCAPTURE_TIMESTAMP,
    FILENAME_SCREENSHOT_TIMESTAMP
} FilenameFormat;

typedef enum {
    SHORTCUT_NONE = 0,
    SHORTCUT_PRINTSCREEN,
    SHORTCUT_CTRL_PRINTSCREEN,
    SHORTCUT_SHIFT_PRINTSCREEN,
    SHORTCUT_CTRL_SHIFT_S,
    SHORTCUT_CTRL_ALT_S
} ShortcutKey;

typedef struct {
    char* screenshot_path;
    FilenameFormat filename_format;
    int auto_number;  // For auto-numbering format
    bool start_with_os;  // New: Start with OS option
    ShortcutKey shortcut_key;  // New: Shortcut key option
    bool default_screenshot_app;  // Register as default screenshot tool
    GdkRGBA tool_colors[6];      // Per-tool colors: [0]=arrow, [1]=box, [2]=circle, [3]=text, [4]=line, [5]=border
    double tool_widths[5];       // Per-tool line widths: [0]=arrow, [1]=box, [2]=circle, [3]=line, [4]=border
    char* text_font_family;      // Text tool font family
    double text_font_size;       // Text tool font size
    bool text_font_bold;         // Text tool bold
    bool text_font_italic;       // Text tool italic
    DesktopEnv detected_de;      // Detected desktop environment
    bool tool_shadow[6];         // Shadow enabled: [0]=arrow, [1]=box, [2]=circle, [3]=text, [4]=line, [5]=border
    double tool_shadow_intensity[6]; // Shadow intensity 0.0-1.0
    int blur_block_size;         // Pixelate block size (4-32)
} Settings;

// Forward declarations
static char* get_binary_path(void);
static void toggle_autostart(bool enable);
static void toggle_default_screenshot_app(bool enable);
static GtkWidget* create_history_item_widget(ScreenshotEntry* entry, MainWindow* win);
static void on_history_selection_changed(GtkFlowBox* flow_box, gpointer data);
static void on_history_child_activated(GtkFlowBox* flow_box, GtkFlowBoxChild* child, gpointer data);
static void on_browse_clicked(GtkWidget* widget, gpointer data);
static void create_settings_page(MainWindow* win, GtkWidget* notebook);
static void on_settings_changed(GtkWidget* widget, gpointer data);
static void register_shortcut_key(MainWindow* win, ShortcutKey key);
static GdkFilterReturn key_filter_func(GdkXEvent* xevent, GdkEvent* event, gpointer data);
static void save_image_with_annotations(MainWindow* win, cairo_surface_t* surface, GList* annotations, const char* filename);
static void on_capture_button_clicked(GtkWidget* widget, gpointer data);
static void on_flatten_button_clicked(GtkWidget* widget, gpointer data);
static void paste_overlay_free(PasteOverlay* overlay);
static void update_image_info(MainWindow* win, MainWindowData* win_data, const char* filepath);
static void on_delete_selected_clicked(GtkWidget* widget, gpointer data);
static void push_image_undo(MainWindowData* win_data);
static void undo_last_annotation(MainWindowData* win_data);
static void apply_crop(MainWindow* win, MainWindowData* win_data);
static void show_resize_dialog(MainWindow* win, MainWindowData* win_data);
static void show_rotate_dialog(MainWindow* win, MainWindowData* win_data);
static void show_brightness_dialog(MainWindow* win, MainWindowData* win_data);
static void duplicate_current_image(MainWindow* win, MainWindowData* win_data);
static gboolean on_scroll_event(GtkWidget* widget, GdkEventScroll* event, gpointer data);
static GdkFilterReturn key_filter_func_global(GdkXEvent* xevent, GdkEvent* event, gpointer data);
static void on_save_button_clicked(GtkWidget* widget, gpointer data);
static void on_copy_button_clicked(GtkWidget* widget, gpointer data);
static void grab_printscreen_key(MainWindow* win, ShortcutKey key);

// Preprocessing function to validate GTK objects
static gboolean validate_gtk_object(GtkWidget* widget, const char* context) {
    if (!widget) {
        g_warning("%s: Widget is NULL", context);
        return FALSE;
    }
    
    if (!GTK_IS_WIDGET(widget)) {
        g_warning("%s: Widget is not a valid GTK widget", context);
        return FALSE;
    }
    
    if (!G_IS_OBJECT(widget)) {
        g_warning("%s: Widget is not a valid GObject", context);
        return FALSE;
    }
    
    return TRUE;
}

// Safe wrapper for g_object_get_data
static gpointer safe_get_data(GtkWidget* widget, const char* key, const char* context) {
    if (!validate_gtk_object(widget, context)) {
        return NULL;
    }
    return g_object_get_data(G_OBJECT(widget), key);
}

// Safe wrapper for g_object_set_data
static void safe_set_data(GtkWidget* widget, const char* key, gpointer data, const char* context) {
    if (!validate_gtk_object(widget, context)) {
        return;
    }
    g_object_set_data(G_OBJECT(widget), key, data);
}

// Safe wrapper for g_object_set_data_full
static void safe_set_data_full(GtkWidget* widget, const char* key, gpointer data, GDestroyNotify destroy_func, const char* context) {
    if (!validate_gtk_object(widget, context)) {
        if (destroy_func && data) {
            destroy_func(data);
        }
        return;
    }
    g_object_set_data_full(G_OBJECT(widget), key, data, destroy_func);
}

static char* get_config_file_path(void) {
    const char* config_dir = g_get_user_config_dir();
    char* linscreencapture_dir = g_build_filename(config_dir, "linscreencapture", NULL);
    g_mkdir_with_parents(linscreencapture_dir, 0755);
    char* config_file = g_build_filename(linscreencapture_dir, "settings.conf", NULL);
    g_free(linscreencapture_dir);
    return config_file;
}

static void load_settings(Settings* settings) {
    // Set default values first
    settings->screenshot_path = g_strdup(g_get_user_special_dir(G_USER_DIRECTORY_PICTURES));
    settings->filename_format = FILENAME_LINSCREENCAPTURE_TIMESTAMP;
    settings->auto_number = 1;
    settings->start_with_os = false;
    settings->shortcut_key = SHORTCUT_PRINTSCREEN;
    settings->default_screenshot_app = false;

    // Default text font settings
    settings->text_font_family = g_strdup("Arial");
    settings->text_font_size = 15.0;
    settings->text_font_bold = true;
    settings->text_font_italic = false;

    // Default tool line widths
    settings->tool_widths[0] = 3.5;  // arrow
    settings->tool_widths[1] = 2.5;  // box
    settings->tool_widths[2] = 2.5;  // circle
    settings->tool_widths[3] = 3.0;  // line
    settings->tool_widths[4] = 2.5;  // border

    settings->blur_block_size = 10;

    // Default tool colors (all red)
    for (int i = 0; i < 6; i++) {
        settings->tool_colors[i].red = 1.0;
        settings->tool_colors[i].green = 0.0;
        settings->tool_colors[i].blue = 0.0;
        settings->tool_colors[i].alpha = 1.0;
        settings->tool_shadow[i] = false;
        settings->tool_shadow_intensity[i] = 0.4;
    }

    // Try to load from config file
    char* config_file = get_config_file_path();
    GKeyFile* key_file = g_key_file_new();

    if (g_key_file_load_from_file(key_file, config_file, G_KEY_FILE_NONE, NULL)) {
        // Load screenshot path
        char* path = g_key_file_get_string(key_file, "Settings", "screenshot_path", NULL);
        if (path) {
            g_free(settings->screenshot_path);
            settings->screenshot_path = path;
        }

        // Load filename format
        settings->filename_format = g_key_file_get_integer(key_file, "Settings", "filename_format", NULL);

        // Load auto number
        settings->auto_number = g_key_file_get_integer(key_file, "Settings", "auto_number", NULL);

        // Load start with OS
        settings->start_with_os = g_key_file_get_boolean(key_file, "Settings", "start_with_os", NULL);

        // Load shortcut key
        settings->shortcut_key = g_key_file_get_integer(key_file, "Settings", "shortcut_key", NULL);

        // Load default screenshot app
        GError* err = NULL;
        settings->default_screenshot_app = g_key_file_get_boolean(key_file, "Settings", "default_screenshot_app", &err);
        if (err) {
            settings->default_screenshot_app = false;
            g_error_free(err);
        }

        // Load per-tool colors
        const char* color_keys[] = {"color_arrow", "color_box", "color_circle", "color_text", "color_line", "color_border"};
        for (int i = 0; i < 6; i++) {
            char* color_str = g_key_file_get_string(key_file, "Settings", color_keys[i], NULL);
            if (color_str) {
                gdk_rgba_parse(&settings->tool_colors[i], color_str);
                g_free(color_str);
            }
        }

        // Load per-tool line widths
        const char* width_keys[] = {"width_arrow", "width_box", "width_circle", "width_line", "width_border"};
        for (int i = 0; i < 5; i++) {
            GError* werr = NULL;
            double w = g_key_file_get_double(key_file, "Settings", width_keys[i], &werr);
            if (!werr && w > 0) settings->tool_widths[i] = w;
            if (werr) g_error_free(werr);
        }

        // Load shadow settings
        const char* shadow_keys[] = {"shadow_arrow", "shadow_box", "shadow_circle", "shadow_text", "shadow_line", "shadow_border"};
        const char* shadow_int_keys[] = {"shadow_int_arrow", "shadow_int_box", "shadow_int_circle", "shadow_int_text", "shadow_int_line", "shadow_int_border"};
        for (int i = 0; i < 6; i++) {
            GError* sherr = NULL;
            settings->tool_shadow[i] = g_key_file_get_boolean(key_file, "Settings", shadow_keys[i], &sherr);
            if (sherr) { settings->tool_shadow[i] = false; g_error_free(sherr); }
            sherr = NULL;
            double si = g_key_file_get_double(key_file, "Settings", shadow_int_keys[i], &sherr);
            if (!sherr && si >= 0) settings->tool_shadow_intensity[i] = si; else if (sherr) g_error_free(sherr);
        }

        // Load blur settings
        GError* berr = NULL;
        int bsize = g_key_file_get_integer(key_file, "Settings", "blur_block_size", &berr);
        if (!berr && bsize >= 4) settings->blur_block_size = bsize; else if (berr) g_error_free(berr);

        // Load text font settings
        char* font = g_key_file_get_string(key_file, "Settings", "text_font_family", NULL);
        if (font) { g_free(settings->text_font_family); settings->text_font_family = font; }
        GError* serr = NULL;
        double fsize = g_key_file_get_double(key_file, "Settings", "text_font_size", &serr);
        if (!serr && fsize > 0) settings->text_font_size = fsize; else if (serr) g_error_free(serr);
        serr = NULL;
        settings->text_font_bold = g_key_file_get_boolean(key_file, "Settings", "text_font_bold", &serr);
        if (serr) { settings->text_font_bold = false; g_error_free(serr); }
        serr = NULL;
        settings->text_font_italic = g_key_file_get_boolean(key_file, "Settings", "text_font_italic", &serr);
        if (serr) { settings->text_font_italic = false; g_error_free(serr); }
    }
    
    g_key_file_free(key_file);
    g_free(config_file);
}

static void save_settings(Settings* settings) {
    char* config_file = get_config_file_path();
    GKeyFile* key_file = g_key_file_new();
    
    // Save all settings
    g_key_file_set_string(key_file, "Settings", "screenshot_path", settings->screenshot_path);
    g_key_file_set_integer(key_file, "Settings", "filename_format", settings->filename_format);
    g_key_file_set_integer(key_file, "Settings", "auto_number", settings->auto_number);
    g_key_file_set_boolean(key_file, "Settings", "start_with_os", settings->start_with_os);
    g_key_file_set_integer(key_file, "Settings", "shortcut_key", settings->shortcut_key);
    g_key_file_set_boolean(key_file, "Settings", "default_screenshot_app", settings->default_screenshot_app);

    // Save per-tool colors
    const char* color_keys[] = {"color_arrow", "color_box", "color_circle", "color_text", "color_line", "color_border"};
    for (int i = 0; i < 6; i++) {
        char* color_str = gdk_rgba_to_string(&settings->tool_colors[i]);
        g_key_file_set_string(key_file, "Settings", color_keys[i], color_str);
        g_free(color_str);
    }

    // Save per-tool line widths
    const char* width_keys[] = {"width_arrow", "width_box", "width_circle", "width_line", "width_border"};
    for (int i = 0; i < 5; i++) {
        g_key_file_set_double(key_file, "Settings", width_keys[i], settings->tool_widths[i]);
    }

    // Save text font settings
    g_key_file_set_string(key_file, "Settings", "text_font_family", settings->text_font_family);
    g_key_file_set_double(key_file, "Settings", "text_font_size", settings->text_font_size);
    g_key_file_set_boolean(key_file, "Settings", "text_font_bold", settings->text_font_bold);
    g_key_file_set_boolean(key_file, "Settings", "text_font_italic", settings->text_font_italic);

    // Save blur settings
    g_key_file_set_integer(key_file, "Settings", "blur_block_size", settings->blur_block_size);

    // Save shadow settings
    const char* shadow_keys[] = {"shadow_arrow", "shadow_box", "shadow_circle", "shadow_text", "shadow_line", "shadow_border"};
    const char* shadow_int_keys[] = {"shadow_int_arrow", "shadow_int_box", "shadow_int_circle", "shadow_int_text", "shadow_int_line", "shadow_int_border"};
    for (int i = 0; i < 6; i++) {
        g_key_file_set_boolean(key_file, "Settings", shadow_keys[i], settings->tool_shadow[i]);
        g_key_file_set_double(key_file, "Settings", shadow_int_keys[i], settings->tool_shadow_intensity[i]);
    }

    // Save to file
    GError* error = NULL;
    if (!g_key_file_save_to_file(key_file, config_file, &error)) {
        g_warning("Failed to save settings: %s", error->message);
        g_error_free(error);
    }
    
    g_key_file_free(key_file);
    g_free(config_file);
}

static void on_browse_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    GtkWidget* entry = GTK_WIDGET(data);
    
    GtkWidget* dialog = gtk_file_chooser_dialog_new(
        "Select Screenshot Directory",
        NULL,
        GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER,
        "_Cancel", GTK_RESPONSE_CANCEL,
        "_Select", GTK_RESPONSE_ACCEPT,
        NULL
    );
    
    // Set current folder if entry has a path
    const char* current_path = gtk_entry_get_text(GTK_ENTRY(entry));
    if (current_path && *current_path) {
        gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(dialog), current_path);
    }
    
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_ACCEPT) {
        char* folder = gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(dialog));
        gtk_entry_set_text(GTK_ENTRY(entry), folder);
        g_free(folder);
    }
    
    gtk_widget_destroy(dialog);
}

static char* generate_screenshot_filename(MainWindow* win) {
    Settings* settings = safe_get_data(win->window, "settings", "generate_screenshot_filename");
    
    char* filename = NULL;
    char timestamp[20];
    static int number = 1;  // Static counter for auto-numbering
    
    switch (settings->filename_format) {
        case FILENAME_LINSCREENCAPTURE_NUMBER:
            filename = g_strdup_printf("%s/LinScreenCapture_%04d.png", settings->screenshot_path, number++);
            break;
        case FILENAME_SCREENSHOT_NUMBER:
            filename = g_strdup_printf("%s/Screenshot_%04d.png", settings->screenshot_path, number++);
            break;
        case FILENAME_LINSCREENCAPTURE_TIMESTAMP: {
            time_t now = time(NULL);
            struct tm* tm_info = localtime(&now);
            strftime(timestamp, sizeof(timestamp), "%Y%m%d_%H%M%S", tm_info);
            filename = g_strdup_printf("%s/LinScreenCapture_%s.png", settings->screenshot_path, timestamp);
            break;
        }
        case FILENAME_SCREENSHOT_TIMESTAMP: {
            time_t now = time(NULL);
            struct tm* tm_info = localtime(&now);
            strftime(timestamp, sizeof(timestamp), "%Y%m%d_%H%M%S", tm_info);
            filename = g_strdup_printf("%s/Screenshot_%s.png", settings->screenshot_path, timestamp);
            break;
        }
    }
    
    return filename;
}

static void rgb_data_destroy(guchar* pixels, gpointer data) {
    (void)data;  // Unused parameter
    g_free(pixels);
}

static void copy_to_clipboard(MainWindow* win, cairo_surface_t* surface, GList* annotations) {
    if (!surface) return;
    
    // Create a new surface to hold both the image and annotations
    int width = cairo_image_surface_get_width(surface);
    int height = cairo_image_surface_get_height(surface);
    cairo_surface_t* combined_surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
    
    // Create Cairo context for the new surface
    cairo_t* cr = cairo_create(combined_surface);
    
    // Draw the original image
    cairo_set_source_surface(cr, surface, 0, 0);
    cairo_paint(cr);
    
    // Draw all annotations
    GList* iter;
    for (iter = annotations; iter != NULL; iter = iter->next) {
        Annotation* annotation = (Annotation*)iter->data;
        annotation_draw(annotation, cr);
    }
    
    // Ensure all drawing operations are complete
    cairo_surface_flush(combined_surface);
    
    // Get surface data and stride
    unsigned char* surface_data = cairo_image_surface_get_data(combined_surface);
    int stride = cairo_image_surface_get_stride(combined_surface);
    
    // Create a new buffer for RGB data conversion
    guchar* rgb_data = g_malloc(width * height * 4);
    if (!rgb_data) {
        cairo_destroy(cr);
        cairo_surface_destroy(combined_surface);
        return;
    }
    
    // Convert ARGB to RGBA (Cairo uses ARGB32, GdkPixbuf uses RGBA)
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int src_idx = y * stride + x * 4;
            int dst_idx = (y * width + x) * 4;
            
            // Cairo (ARGB) -> GdkPixbuf (RGBA)
            guchar alpha = surface_data[src_idx + 3];
            guchar red = surface_data[src_idx + 2];
            guchar green = surface_data[src_idx + 1];
            guchar blue = surface_data[src_idx + 0];
            
            rgb_data[dst_idx + 0] = red;
            rgb_data[dst_idx + 1] = green;
            rgb_data[dst_idx + 2] = blue;
            rgb_data[dst_idx + 3] = alpha;
        }
    }
    
    // Create pixbuf from converted data
    GdkPixbuf* pixbuf = gdk_pixbuf_new_from_data(
        rgb_data,
        GDK_COLORSPACE_RGB,
        TRUE,  // has alpha
        8,     // bits per sample
        width,
        height,
        width * 4,  // rowstride for packed RGB data
        rgb_data_destroy,  // Use our type-safe destroy function
        NULL
    );
    
    // Get the clipboard and set the image
    GtkClipboard* clipboard = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
    
    // Create a copy of the pixbuf that will persist after we free our local resources
    GdkPixbuf* clipboard_pixbuf = gdk_pixbuf_copy(pixbuf);
    gtk_clipboard_set_image(clipboard, clipboard_pixbuf);
    gtk_clipboard_store(clipboard);
    g_object_unref(clipboard_pixbuf);
    
    // Clean up
    g_object_unref(pixbuf);
    cairo_destroy(cr);
    cairo_surface_destroy(combined_surface);
    
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Image with annotations copied to clipboard");
}

static cairo_surface_t* add_border_to_surface(cairo_surface_t* surface, double border_width, double r, double g, double b) {
    if (!surface) return NULL;
    
    int width = cairo_image_surface_get_width(surface);
    int height = cairo_image_surface_get_height(surface);
    
    // Create a new surface with space for the border
    cairo_surface_t* bordered_surface = cairo_image_surface_create(
        CAIRO_FORMAT_ARGB32,
        width + 2 * border_width,
        height + 2 * border_width
    );
    
    cairo_t* cr = cairo_create(bordered_surface);
    
    // Clear the surface
    cairo_set_operator(cr, CAIRO_OPERATOR_CLEAR);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
    
    // Draw the original image in the center
    cairo_set_source_surface(cr, surface, border_width, border_width);
    cairo_paint(cr);
    
    // Draw the border
    cairo_set_source_rgb(cr, r, g, b);
    cairo_set_line_width(cr, border_width);
    cairo_rectangle(cr, 
                   border_width/2, border_width/2, 
                   width + border_width, height + border_width);
    cairo_stroke(cr);
    
    cairo_destroy(cr);
    return bordered_surface;
}

// Public entry point for triggering capture from outside (e.g. signal, tray, --capture)
void main_window_trigger_capture(MainWindow* win) {
    on_capture_button_clicked(NULL, win);
}

static void on_capture_button_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_capture_button_clicked");
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Capturing screen...");
    
    // Show capture overlay
    CaptureOverlay overlay = {0};
    if (!capture_overlay_init(&overlay)) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to initialize capture overlay");
        return;
    }
    
    // Run the overlay until user makes a selection
    gtk_main();
    
    // Get the selected area
    CaptureArea area = capture_overlay_get_selection(&overlay);
    capture_overlay_cleanup(&overlay);
    
    if (area.width == 0 || area.height == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Capture cancelled");
        return;
    }
    
    // Initialize screen capture
    if (!capture_init()) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to initialize screen capture");
        return;
    }
    
    // Capture selected area
    cairo_surface_t* surface = capture_screen(CAPTURE_AREA, &area);
    if (!surface) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to capture screen");
        capture_cleanup();
        return;
    }
    
    // Clean up screen capture
    capture_cleanup();
    
    // Add border to the captured image
    cairo_surface_t* bordered_surface = add_border_to_surface(surface, 3.0, 0.0, 0.0, 0.0);
    cairo_surface_destroy(surface);  // Free the original surface
    
    if (!bordered_surface) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to add border to image");
        return;
    }
    
    // Generate filename and save immediately
    char* filename = generate_screenshot_filename(win);
    
    // Save the raw screenshot without annotations
    cairo_status_t status = cairo_surface_write_to_png(bordered_surface, filename);
    if (status != CAIRO_STATUS_SUCCESS) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to save screenshot");
        g_free(filename);
        cairo_surface_destroy(bordered_surface);
        return;
    }
    
    // Add to history
    screenshot_history_add(&win->screenshot_history, filename);
    
    // Update history view
    GList* entries = screenshot_history_get_sorted(&win->screenshot_history);
    
    // Clear existing history items
    GList* children = gtk_container_get_children(GTK_CONTAINER(win->history_flow_box));
    for (GList* iter = children; iter != NULL; iter = iter->next) {
        gtk_widget_destroy(GTK_WIDGET(iter->data));
    }
    g_list_free(children);
    
    // Add updated history items
    for (GList* iter = entries; iter != NULL; iter = iter->next) {
        ScreenshotEntry* entry = (ScreenshotEntry*)iter->data;
        GtkWidget* item_widget = create_history_item_widget(entry, win);
        gtk_flow_box_insert(GTK_FLOW_BOX(win->history_flow_box), item_widget, -1);
    }
    gtk_widget_show_all(win->history_flow_box);

    // Update image count label
    GtkWidget* count_lbl = safe_get_data(win->window, "history-count-label", "refresh_history");
    if (count_lbl && GTK_IS_LABEL(count_lbl)) {
        int cnt = g_list_length(entries);
        char cnt_msg[32];
        snprintf(cnt_msg, sizeof(cnt_msg), "%d image%s", cnt, cnt != 1 ? "s" : "");
        gtk_label_set_text(GTK_LABEL(count_lbl), cnt_msg);
    }

    // Update window data
    if (win_data->current_image) {
        cairo_surface_destroy(win_data->current_image);
    }
    win_data->current_image = bordered_surface;
    
    // Clear existing annotations
    g_list_free_full(win_data->annotations, (GDestroyNotify)annotation_free);
    win_data->annotations = NULL;

    // Track original filename for save sequencing
    g_free(win_data->current_filename);
    win_data->current_filename = g_strdup(filename);
    win_data->save_sequence = 1;

    // Copy to clipboard
    copy_to_clipboard(win, bordered_surface, NULL);

    // Switch to Screenshot tab so user sees the latest capture
    GtkWidget* notebook = gtk_widget_get_ancestor(win->canvas, GTK_TYPE_NOTEBOOK);
    if (notebook) {
        gtk_notebook_set_current_page(GTK_NOTEBOOK(notebook), 0);
    }

    // Redraw canvas
    gtk_widget_queue_draw(win->canvas);

    update_image_info(win, win_data, filename);
    g_free(filename);
}

static void copy_marquee_region(MainWindow* win, MainWindowData* win_data) {
    int x = win_data->marquee_bounds.x1;
    int y = win_data->marquee_bounds.y1;
    int w = win_data->marquee_bounds.x2 - x;
    int h = win_data->marquee_bounds.y2 - y;
    int img_w = cairo_image_surface_get_width(win_data->current_image);
    int img_h = cairo_image_surface_get_height(win_data->current_image);

    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x + w > img_w) w = img_w - x;
    if (y + h > img_h) h = img_h - y;
    if (w < 1 || h < 1) return;

    cairo_surface_t* region = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_t* rcr = cairo_create(region);

    cairo_set_source_surface(rcr, win_data->current_image, -x, -y);
    cairo_paint(rcr);

    for (GList* iter = win_data->annotations; iter; iter = iter->next) {
        cairo_save(rcr);
        cairo_translate(rcr, -x, -y);
        annotation_draw((Annotation*)iter->data, rcr);
        cairo_restore(rcr);
    }

    cairo_surface_flush(region);

    GdkPixbuf* pb = gdk_pixbuf_get_from_surface(region, 0, 0, w, h);
    if (pb) {
        GtkClipboard* clipboard = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
        gtk_clipboard_set_image(clipboard, pb);
        gtk_clipboard_store(clipboard);
        g_object_unref(pb);
    }

    cairo_destroy(rcr);
    cairo_surface_destroy(region);

    char msg[80];
    snprintf(msg, sizeof(msg), "Selection %dx%d copied to clipboard", w, h);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
}

static void on_copy_button_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_copy_button_clicked");

    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image to copy");
        return;
    }

    // If marquee selection is active, copy only the selected region
    if (win_data->has_marquee) {
        copy_marquee_region(win, win_data);
    } else {
        copy_to_clipboard(win, win_data->current_image, win_data->annotations);
    }
}

static void on_tool_button_clicked(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    if (!win || !win->window) {
        return;
    }
    
    // Remove active class from all buttons
    GtkWidget* buttons_container = gtk_widget_get_parent(widget);
    if (!buttons_container) {
        return;
    }
    
    GList* children = gtk_container_get_children(GTK_CONTAINER(buttons_container));
    for (GList* iter = children; iter != NULL; iter = iter->next) {
        GtkWidget* button = GTK_WIDGET(iter->data);
        GtkStyleContext* context = gtk_widget_get_style_context(button);
        gtk_style_context_remove_class(context, "active");
    }
    g_list_free(children);
    
    // Add active class to clicked button
    GtkStyleContext* context = gtk_widget_get_style_context(widget);
    gtk_style_context_add_class(context, "active");
    
    int tool_id = GPOINTER_TO_INT(safe_get_data(widget, "tool-id", "on_tool_button_clicked"));
    
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_tool_button_clicked");
    Settings* settings = safe_get_data(win->window, "settings", "on_tool_button_clicked");
    if (win_data) {
        win_data->current_tool.type = tool_id;

        // Apply saved color and width for drawing tools
        if (settings) {
            int color_map = -1;
            int width_map = -1;
            if (tool_id == TOOL_ARROW)     { color_map = 0; width_map = 0; }
            else if (tool_id == TOOL_RECTANGLE) { color_map = 1; width_map = 1; }
            else if (tool_id == TOOL_ELLIPSE)   { color_map = 2; width_map = 2; }
            else if (tool_id == TOOL_TEXT)       { color_map = 3; }
            else if (tool_id == TOOL_LINE)       { color_map = 4; width_map = 3; }
            else if (tool_id == TOOL_BORDER)     { color_map = 5; width_map = 4; }
            else if (tool_id == TOOL_BLUR) {
                win_data->current_tool.blur_block_size = settings->blur_block_size;
            }
            if (color_map >= 0) {
                win_data->current_tool.color = settings->tool_colors[color_map];
                // Apply shadow settings (shadow indices match color indices for 0-4)
                int shadow_map = color_map;
                win_data->current_tool.shadow = settings->tool_shadow[shadow_map];
                win_data->current_tool.shadow_intensity = settings->tool_shadow_intensity[shadow_map];
            }
            if (width_map >= 0) {
                win_data->current_tool.line_width = settings->tool_widths[width_map];
            }
            if (tool_id == TOOL_TEXT) {
                g_free(win_data->current_tool.font.family);
                win_data->current_tool.font.family = g_strdup(settings->text_font_family);
                win_data->current_tool.font.size = settings->text_font_size;
                win_data->current_tool.font.is_bold = settings->text_font_bold;
                win_data->current_tool.font.is_italic = settings->text_font_italic;
            }
        }

        const char* tool_names[] = {
            "None", "Arrow", "Rectangle", "Ellipse", "Text", "Freehand", "Select", "Line", "Border", "Blur", "Crop", "Resize", "Rotate", "Brightness", "Duplicate"
        };
        char status[50];
        snprintf(status, sizeof(status), "Selected tool: %s", tool_names[tool_id]);
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, status);
    }
}

static gboolean on_sidebar_icon_draw(GtkWidget* widget, cairo_t* cr, gpointer data) {
    (void)data;
    int icon_type = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "icon-type"));
    cairo_set_source_rgb(cr, 0.9, 0.9, 0.9);
    sidebar_icon_draw(cr, (SidebarIconType)icon_type, 0, 0);
    return FALSE;
}

static gboolean on_draw(GtkWidget* widget, cairo_t* cr, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_draw");
    
    if (!win_data) {
        return FALSE;
    }
    
    // Get widget allocation
    GtkAllocation allocation;
    gtk_widget_get_allocation(widget, &allocation);
    
    // Set up Cairo context
    cairo_save(cr);
    
    // Clear the background with theme color
    cairo_set_source_rgb(cr, 0.176, 0.176, 0.176);  // #2d2d2d
    cairo_rectangle(cr, 0, 0, allocation.width, allocation.height);
    cairo_fill(cr);
    
    if (win_data->current_image) {
        // Get image dimensions
        int width = cairo_image_surface_get_width(win_data->current_image);
        int height = cairo_image_surface_get_height(win_data->current_image);
        
        // Apply zoom to canvas size
        double zoom = win_data->zoom_level;
        int zoomed_w = (int)(width * zoom);
        int zoomed_h = (int)(height * zoom);

        // Set canvas size to match zoomed image size if needed
        if (gtk_widget_get_allocated_width(win->canvas) != zoomed_w ||
            gtk_widget_get_allocated_height(win->canvas) != zoomed_h) {
            gtk_widget_set_size_request(win->canvas, zoomed_w, zoomed_h);
        }

        // Create a new surface for the image (at original resolution)
        cairo_surface_t* image_surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
        cairo_t* image_cr = cairo_create(image_surface);

        // Draw the image
        cairo_set_source_surface(image_cr, win_data->current_image, 0, 0);
        cairo_paint(image_cr);
        
        // Draw annotations on the image surface
        GList* iter;
        for (iter = win_data->annotations; iter != NULL; iter = iter->next) {
            Annotation* annotation = (Annotation*)iter->data;
            annotation_draw(annotation, image_cr);
        }
        
        // Draw current annotation if drawing
        if (win_data->drawing) {
            if (win_data->current_tool.type == TOOL_CROP) {
                // Crop preview: dashed box with dimensions, dimmed outside area
                int cx = MIN(win_data->start_point.x1, win_data->start_point.x2);
                int cy = MIN(win_data->start_point.y1, win_data->start_point.y2);
                int cw = abs(win_data->start_point.x2 - win_data->start_point.x1);
                int ch = abs(win_data->start_point.y2 - win_data->start_point.y1);

                if (cw > 0 && ch > 0) {
                    // Dim area outside crop
                    cairo_set_source_rgba(image_cr, 0, 0, 0, 0.4);
                    cairo_rectangle(image_cr, 0, 0, width, cy);
                    cairo_fill(image_cr);
                    cairo_rectangle(image_cr, 0, cy + ch, width, height - cy - ch);
                    cairo_fill(image_cr);
                    cairo_rectangle(image_cr, 0, cy, cx, ch);
                    cairo_fill(image_cr);
                    cairo_rectangle(image_cr, cx + cw, cy, width - cx - cw, ch);
                    cairo_fill(image_cr);

                    // Dashed border
                    double dashes[] = {4.0, 3.0};
                    cairo_set_dash(image_cr, dashes, 2, 0);
                    cairo_set_line_width(image_cr, 1.5);
                    cairo_set_source_rgba(image_cr, 1, 1, 1, 0.9);
                    cairo_rectangle(image_cr, cx + 0.5, cy + 0.5, cw, ch);
                    cairo_stroke(image_cr);
                    cairo_set_dash(image_cr, NULL, 0, 0);

                    // Dimension label
                    char dim_str[32];
                    snprintf(dim_str, sizeof(dim_str), "%dx%d", cw, ch);
                    cairo_set_source_rgba(image_cr, 1, 1, 1, 0.8);
                    cairo_set_font_size(image_cr, 12);
                    cairo_move_to(image_cr, cx + 4, cy > 16 ? cy - 4 : cy + ch + 14);
                    cairo_show_text(image_cr, dim_str);
                }
            } else {
                Annotation* current = annotation_create(win_data->current_tool.type, &win_data->current_tool);
                if (current) {
                    current->bounds = win_data->start_point;
                    annotation_draw(current, image_cr);
                    annotation_free(current);
                }
            }
        }

        // Draw all paste overlays
        for (GList* piter = win_data->paste_overlays; piter; piter = piter->next) {
            PasteOverlay* overlay = (PasteOverlay*)piter->data;
            cairo_set_source_surface(image_cr, overlay->surface, overlay->x, overlay->y);
            cairo_paint(image_cr);

            // Draw dashed border around each overlay
            int pw = cairo_image_surface_get_width(overlay->surface);
            int ph = cairo_image_surface_get_height(overlay->surface);
            cairo_save(image_cr);
            cairo_set_line_join(image_cr, CAIRO_LINE_JOIN_MITER);
            cairo_set_line_cap(image_cr, CAIRO_LINE_CAP_BUTT);
            double dashes[] = {4.0, 3.0};
            cairo_set_dash(image_cr, dashes, 2, 0);
            cairo_set_line_width(image_cr, 1.5);
            // Highlight the actively dragged overlay in a different color
            if (overlay == win_data->dragging_overlay) {
                cairo_set_source_rgba(image_cr, 1.0, 0.6, 0.2, 0.9);
            } else {
                cairo_set_source_rgba(image_cr, 0.2, 0.6, 1.0, 0.9);
            }
            cairo_rectangle(image_cr, overlay->x + 0.5, overlay->y + 0.5, pw, ph);
            cairo_stroke(image_cr);
            cairo_restore(image_cr);
        }

        // Draw persistent marquee selection
        if (win_data->has_marquee) {
            Annotation marq = {0};
            marq.type = TOOL_MARQUEE;
            marq.bounds = win_data->marquee_bounds;
            annotation_draw(&marq, image_cr);
        }

        // Draw the combined image and annotations to the widget with zoom
        cairo_scale(cr, zoom, zoom);
        cairo_set_source_surface(cr, image_surface, 0, 0);
        cairo_paint(cr);
        
        // Clean up
        cairo_destroy(image_cr);
        cairo_surface_destroy(image_surface);
    }
    
    cairo_restore(cr);
    return TRUE;
}

static void show_text_dialog(MainWindow* win, MainWindowData* win_data, double x, double y) {
    GtkWidget* dialog = gtk_dialog_new_with_buttons(
        "Enter Text",
        GTK_WINDOW(win->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "_Cancel",
        GTK_RESPONSE_CANCEL,
        "_OK",
        GTK_RESPONSE_ACCEPT,
        NULL
    );
    
    // Create text entry
    GtkWidget* content_area = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget* entry = gtk_entry_new();
    gtk_entry_set_activates_default(GTK_ENTRY(entry), TRUE);
    gtk_container_add(GTK_CONTAINER(content_area), entry);
    
    // Set dialog properties
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_ACCEPT);
    gtk_window_set_position(GTK_WINDOW(dialog), GTK_WIN_POS_MOUSE);
    gtk_widget_show_all(dialog);
    
    // Run dialog
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));
    if (response == GTK_RESPONSE_ACCEPT) {
        const char* text = gtk_entry_get_text(GTK_ENTRY(entry));
        if (text && *text) {  // If text is not empty
            // Create text annotation
            Annotation* annotation = annotation_create(TOOL_TEXT, &win_data->current_tool);
            if (annotation) {
                annotation->text = g_strdup(text);
                annotation->bounds.x1 = x;
                annotation->bounds.y1 = y;
                win_data->annotations = g_list_append(win_data->annotations, annotation);
                gtk_widget_queue_draw(win->canvas);
            }
        }
    }
    
    gtk_widget_destroy(dialog);
}

// Helper function to find text annotation at coordinates
static Annotation* find_text_at_coords(MainWindowData* win_data, double x, double y) {
    GList* iter;
    for (iter = win_data->annotations; iter != NULL; iter = iter->next) {
        Annotation* annotation = (Annotation*)iter->data;
        if (annotation->type == TOOL_TEXT) {
            // Check if coordinates are within text bounds
            if (x >= annotation->bounds.x1 && x <= annotation->bounds.x2 &&
                y >= annotation->bounds.y1 && y <= annotation->bounds.y2) {
                return annotation;
            }
        }
    }
    return NULL;
}

static gboolean on_button_press(GtkWidget* widget, GdkEventButton* event, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_button_press");

    // Transform coordinates for zoom
    double zoom = win_data->zoom_level;
    event->x /= zoom;
    event->y /= zoom;

    if (event->button == 1) {  // Left mouse button
        // Check if clicking on any paste overlay (check topmost/last first)
        for (GList* piter = g_list_last(win_data->paste_overlays); piter; piter = piter->prev) {
            PasteOverlay* overlay = (PasteOverlay*)piter->data;
            int pw = cairo_image_surface_get_width(overlay->surface);
            int ph = cairo_image_surface_get_height(overlay->surface);
            if (event->x >= overlay->x && event->x <= overlay->x + pw &&
                event->y >= overlay->y && event->y <= overlay->y + ph) {
                win_data->dragging_paste = true;
                win_data->dragging_overlay = overlay;
                win_data->paste_drag_ox = event->x - overlay->x;
                win_data->paste_drag_oy = event->y - overlay->y;
                gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Dragging pasted image - click Flatten when positioned");
                return TRUE;
            }
        }

        // Clear marquee when starting a new drawing action
        if (win_data->current_tool.type != TOOL_NONE) {
            win_data->has_marquee = false;
        }

        // Check if clicking on an existing text annotation
        Annotation* text_annotation = find_text_at_coords(win_data, event->x, event->y);
        if (text_annotation) {
            win_data->selected_text = text_annotation;
            win_data->drag_start_x = event->x - text_annotation->bounds.x1;
            win_data->drag_start_y = event->y - text_annotation->bounds.y1;
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Text selected - drag to move");
            return TRUE;
        }

        // If not clicking text, handle normal tool operations
        if (win_data->current_tool.type == TOOL_TEXT) {
            // Deselect any selected text when creating new text
            win_data->selected_text = NULL;
            show_text_dialog(win, win_data, event->x, event->y);
        } else if (win_data->current_tool.type == TOOL_RESIZE) {
            show_resize_dialog(win, win_data);
        } else if (win_data->current_tool.type == TOOL_ROTATE) {
            show_rotate_dialog(win, win_data);
        } else if (win_data->current_tool.type == TOOL_BRIGHTNESS) {
            show_brightness_dialog(win, win_data);
        } else if (win_data->current_tool.type == TOOL_DUPLICATE) {
            duplicate_current_image(win, win_data);
        } else if (win_data->current_tool.type != TOOL_NONE) {
            win_data->selected_text = NULL;  // Deselect text when using other tools
            win_data->drawing = true;
            win_data->start_point.x1 = event->x;
            win_data->start_point.y1 = event->y;
            win_data->start_point.x2 = event->x;
            win_data->start_point.y2 = event->y;
        }
    }
    
    return TRUE;
}

static gboolean on_motion_notify(GtkWidget* widget, GdkEventMotion* event, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_motion_notify");

    // Transform coordinates for zoom
    double zoom = win_data->zoom_level;
    event->x /= zoom;
    event->y /= zoom;

    if (win_data->dragging_paste && win_data->dragging_overlay) {
        win_data->dragging_overlay->x = event->x - win_data->paste_drag_ox;
        win_data->dragging_overlay->y = event->y - win_data->paste_drag_oy;
        gtk_widget_queue_draw(win->canvas);
    } else if (win_data->selected_text) {
        // Update text position while dragging
        double new_x = event->x - win_data->drag_start_x;
        double new_y = event->y - win_data->drag_start_y;
        
        // Update text bounds
        double width = win_data->selected_text->bounds.x2 - win_data->selected_text->bounds.x1;
        double height = win_data->selected_text->bounds.y2 - win_data->selected_text->bounds.y1;
        win_data->selected_text->bounds.x1 = new_x;
        win_data->selected_text->bounds.y1 = new_y;
        win_data->selected_text->bounds.x2 = new_x + width;
        win_data->selected_text->bounds.y2 = new_y + height;
        
        gtk_widget_queue_draw(win->canvas);
    } else if (win_data->drawing) {
        win_data->start_point.x2 = event->x;
        win_data->start_point.y2 = event->y;

        // Shift held: snap Line/Arrow to 0/45/90/135/180/225/270/315 degrees
        if ((event->state & GDK_SHIFT_MASK) &&
            (win_data->current_tool.type == TOOL_LINE ||
             win_data->current_tool.type == TOOL_ARROW)) {
            double dx = event->x - win_data->start_point.x1;
            double dy = event->y - win_data->start_point.y1;
            double dist = sqrt(dx * dx + dy * dy);
            if (dist > 1.0) {
                double angle = atan2(dy, dx);
                // Snap to nearest 45-degree increment
                double snapped = round(angle / (G_PI / 4.0)) * (G_PI / 4.0);
                win_data->start_point.x2 = win_data->start_point.x1 + (int)(dist * cos(snapped));
                win_data->start_point.y2 = win_data->start_point.y1 + (int)(dist * sin(snapped));
            }
        }

        // Ctrl held: constrain to equal ratio (square/circle)
        if ((event->state & GDK_CONTROL_MASK) &&
            (win_data->current_tool.type == TOOL_RECTANGLE ||
             win_data->current_tool.type == TOOL_ELLIPSE ||
             win_data->current_tool.type == TOOL_MARQUEE)) {
            int dx = win_data->start_point.x2 - win_data->start_point.x1;
            int dy = win_data->start_point.y2 - win_data->start_point.y1;
            int size = abs(dx) > abs(dy) ? abs(dx) : abs(dy);
            win_data->start_point.x2 = win_data->start_point.x1 + (dx >= 0 ? size : -size);
            win_data->start_point.y2 = win_data->start_point.y1 + (dy >= 0 ? size : -size);
        }

        gtk_widget_queue_draw(win->canvas);
    }
    
    return TRUE;
}

static gboolean on_scroll_event(GtkWidget* widget, GdkEventScroll* event, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_scroll_event");
    if (!win_data || !win_data->current_image) return FALSE;

    // Only zoom with Ctrl held
    if (!(event->state & GDK_CONTROL_MASK)) return FALSE;

    double old_zoom = win_data->zoom_level;

    if (event->direction == GDK_SCROLL_UP) {
        win_data->zoom_level *= 1.15;
    } else if (event->direction == GDK_SCROLL_DOWN) {
        win_data->zoom_level /= 1.15;
    } else if (event->direction == GDK_SCROLL_SMOOTH) {
        // Smooth scrolling (trackpad)
        if (event->delta_y < 0) {
            win_data->zoom_level *= 1.08;
        } else if (event->delta_y > 0) {
            win_data->zoom_level /= 1.08;
        }
    }

    // Clamp zoom range
    if (win_data->zoom_level < 0.1) win_data->zoom_level = 0.1;
    if (win_data->zoom_level > 10.0) win_data->zoom_level = 10.0;

    if (win_data->zoom_level != old_zoom) {
        // Resize canvas to match zoomed image dimensions
        int img_w = cairo_image_surface_get_width(win_data->current_image);
        int img_h = cairo_image_surface_get_height(win_data->current_image);
        gtk_widget_set_size_request(win->canvas,
            (int)(img_w * win_data->zoom_level),
            (int)(img_h * win_data->zoom_level));
        gtk_widget_queue_draw(win->canvas);

        char msg[64];
        snprintf(msg, sizeof(msg), "Zoom: %d%%", (int)(win_data->zoom_level * 100));
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
    }

    return TRUE;
}

static gboolean on_button_release(GtkWidget* widget, GdkEventButton* event, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_button_release");

    // Transform coordinates for zoom
    double zoom = win_data->zoom_level;
    event->x /= zoom;
    event->y /= zoom;

    if (event->button == 1) {
        if (win_data->dragging_paste) {
            win_data->dragging_paste = false;
            win_data->dragging_overlay = NULL;
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Paste positioned - click Flatten to commit");
        } else if (win_data->selected_text) {
            // Finish moving text
            win_data->selected_text = NULL;
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Text moved");
        } else if (win_data->drawing) {
            win_data->drawing = false;

            if (win_data->current_tool.type == TOOL_MARQUEE) {
                // Marquee tool: store selection and copy region to clipboard
                if (win_data->current_image) {
                    int x = MIN(win_data->start_point.x1, win_data->start_point.x2);
                    int y = MIN(win_data->start_point.y1, win_data->start_point.y2);
                    int w = abs(win_data->start_point.x2 - win_data->start_point.x1);
                    int h = abs(win_data->start_point.y2 - win_data->start_point.y1);

                    if (w > 1 && h > 1) {
                        int img_w = cairo_image_surface_get_width(win_data->current_image);
                        int img_h = cairo_image_surface_get_height(win_data->current_image);

                        // Clamp to image bounds
                        if (x < 0) x = 0;
                        if (y < 0) y = 0;
                        if (x + w > img_w) w = img_w - x;
                        if (y + h > img_h) h = img_h - y;

                        // Store marquee selection persistently
                        win_data->has_marquee = true;
                        win_data->marquee_bounds.x1 = x;
                        win_data->marquee_bounds.y1 = y;
                        win_data->marquee_bounds.x2 = x + w;
                        win_data->marquee_bounds.y2 = y + h;

                        // Create surface with selected region + annotations
                        cairo_surface_t* region = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
                        cairo_t* rcr = cairo_create(region);

                        cairo_set_source_surface(rcr, win_data->current_image, -x, -y);
                        cairo_paint(rcr);

                        for (GList* iter = win_data->annotations; iter; iter = iter->next) {
                            cairo_save(rcr);
                            cairo_translate(rcr, -x, -y);
                            annotation_draw((Annotation*)iter->data, rcr);
                            cairo_restore(rcr);
                        }

                        cairo_surface_flush(region);

                        // Copy to clipboard
                        GdkPixbuf* pb = gdk_pixbuf_get_from_surface(region, 0, 0, w, h);
                        if (pb) {
                            GtkClipboard* clipboard = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
                            gtk_clipboard_set_image(clipboard, pb);
                            gtk_clipboard_store(clipboard);
                            g_object_unref(pb);
                        }

                        cairo_destroy(rcr);
                        cairo_surface_destroy(region);

                        char msg[80];
                        snprintf(msg, sizeof(msg), "Selected %dx%d - copied to clipboard (Ctrl+V to paste)", w, h);
                        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
                    }
                }
                gtk_widget_queue_draw(win->canvas);
            } else if (win_data->current_tool.type == TOOL_CROP) {
                // Crop tool: crop image to drawn rectangle
                apply_crop(win, win_data);
            } else if (win_data->current_tool.type == TOOL_RESIZE) {
                // Resize tool: show resize dialog on click release
                win_data->drawing = false;
                show_resize_dialog(win, win_data);
            } else {
                // Normal tool: create and add new annotation
                Annotation* annotation = annotation_create(win_data->current_tool.type, &win_data->current_tool);
                if (annotation) {
                    annotation->bounds = win_data->start_point;
                    win_data->annotations = g_list_append(win_data->annotations, annotation);
                }
                gtk_widget_queue_draw(win->canvas);
            }
        }
    }
    
    return TRUE;
}

static void apply_crop(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->current_image) return;
    push_image_undo(win_data);

    int x = MIN(win_data->start_point.x1, win_data->start_point.x2);
    int y = MIN(win_data->start_point.y1, win_data->start_point.y2);
    int w = abs(win_data->start_point.x2 - win_data->start_point.x1);
    int h = abs(win_data->start_point.y2 - win_data->start_point.y1);

    if (w < 2 || h < 2) return;

    int img_w = cairo_image_surface_get_width(win_data->current_image);
    int img_h = cairo_image_surface_get_height(win_data->current_image);
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x + w > img_w) w = img_w - x;
    if (y + h > img_h) h = img_h - y;

    // Create cropped surface
    cairo_surface_t* cropped = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_t* cr = cairo_create(cropped);
    cairo_set_source_surface(cr, win_data->current_image, -x, -y);
    cairo_paint(cr);
    cairo_destroy(cr);

    // Replace current image
    cairo_surface_destroy(win_data->current_image);
    win_data->current_image = cropped;
    win_data->zoom_level = 1.0;

    // Clear annotations (they're relative to old image coordinates)
    g_list_free_full(win_data->annotations, (GDestroyNotify)annotation_free);
    win_data->annotations = NULL;

    gtk_widget_queue_draw(win->canvas);

    char msg[64];
    snprintf(msg, sizeof(msg), "Cropped to %dx%d", w, h);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
    update_image_info(win, win_data, NULL);
}

// Push current image state onto undo stack (for image-level operations)
static void push_image_undo(MainWindowData* win_data) {
    if (!win_data->current_image) return;
    int w = cairo_image_surface_get_width(win_data->current_image);
    int h = cairo_image_surface_get_height(win_data->current_image);
    cairo_surface_t* copy = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_t* cr = cairo_create(copy);
    cairo_set_source_surface(cr, win_data->current_image, 0, 0);
    cairo_paint(cr);
    cairo_destroy(cr);
    win_data->image_undo_stack = g_list_prepend(win_data->image_undo_stack, copy);
    // Limit stack to 20 entries
    while (g_list_length(win_data->image_undo_stack) > 20) {
        GList* last = g_list_last(win_data->image_undo_stack);
        cairo_surface_destroy((cairo_surface_t*)last->data);
        win_data->image_undo_stack = g_list_delete_link(win_data->image_undo_stack, last);
    }
}

// Helper: replace current image with a new pixbuf
static void replace_image_from_pixbuf(MainWindow* win, MainWindowData* win_data, GdkPixbuf* pb, const char* status_msg) {
    push_image_undo(win_data);
    int new_w = gdk_pixbuf_get_width(pb);
    int new_h = gdk_pixbuf_get_height(pb);
    cairo_surface_destroy(win_data->current_image);
    win_data->current_image = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, new_w, new_h);
    cairo_t* cr = cairo_create(win_data->current_image);
    gdk_cairo_set_source_pixbuf(cr, pb, 0, 0);
    cairo_paint(cr);
    cairo_destroy(cr);
    win_data->zoom_level = 1.0;
    g_list_free_full(win_data->annotations, (GDestroyNotify)annotation_free);
    win_data->annotations = NULL;
    gtk_widget_queue_draw(win->canvas);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, status_msg);
    update_image_info(win, win_data, NULL);
}

static void show_resize_dialog(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image to resize");
        return;
    }

    int cur_w = cairo_image_surface_get_width(win_data->current_image);
    int cur_h = cairo_image_surface_get_height(win_data->current_image);

    GtkWidget* dialog = gtk_dialog_new_with_buttons("Resize Image",
        GTK_WINDOW(win->window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Cancel", GTK_RESPONSE_CANCEL, "Resize", GTK_RESPONSE_ACCEPT, NULL);
    gtk_window_set_default_size(GTK_WINDOW(dialog), 380, -1);
    GtkWidget* content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(content), 24);
    gtk_box_set_spacing(GTK_BOX(content), 10);

    // Current size
    char cur_size[64];
    snprintf(cur_size, sizeof(cur_size), "Current size:  %d x %d pixels", cur_w, cur_h);
    GtkWidget* cur_label = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(cur_label), cur_size);
    gtk_widget_set_halign(cur_label, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(content), cur_label, FALSE, FALSE, 4);

    // --- Scale by percentage ---
    GtkWidget* pct_title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(pct_title), "<b>Scale by Percentage</b>");
    gtk_widget_set_halign(pct_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(content), pct_title, FALSE, FALSE, 2);

    GtkWidget* prow = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_box_pack_start(GTK_BOX(prow), gtk_label_new("Scale:"), FALSE, FALSE, 0);
    GtkWidget* pct_spin = gtk_spin_button_new_with_range(1, 500, 5);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(pct_spin), 100);
    gtk_box_pack_start(GTK_BOX(prow), pct_spin, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(prow), gtk_label_new("%"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(content), prow, FALSE, FALSE, 4);

    // Separator
    gtk_box_pack_start(GTK_BOX(content), gtk_separator_new(GTK_ORIENTATION_HORIZONTAL), FALSE, FALSE, 6);

    // --- Exact dimensions ---
    GtkWidget* dim_title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(dim_title), "<b>Exact Dimensions</b>");
    gtk_widget_set_halign(dim_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(content), dim_title, FALSE, FALSE, 2);

    GtkWidget* w_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_box_pack_start(GTK_BOX(w_row), gtk_label_new("Width:"), FALSE, FALSE, 0);
    GtkWidget* w_spin = gtk_spin_button_new_with_range(1, 10000, 1);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(w_spin), cur_w);
    gtk_box_pack_start(GTK_BOX(w_row), w_spin, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(w_row), gtk_label_new("px"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(content), w_row, FALSE, FALSE, 4);

    GtkWidget* h_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_box_pack_start(GTK_BOX(h_row), gtk_label_new("Height:"), FALSE, FALSE, 0);
    GtkWidget* h_spin = gtk_spin_button_new_with_range(1, 10000, 1);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(h_spin), cur_h);
    gtk_box_pack_start(GTK_BOX(h_row), h_spin, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(h_row), gtk_label_new("px"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(content), h_row, FALSE, FALSE, 4);

    gtk_widget_show_all(dialog);

    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_ACCEPT) {
        int pct = (int)gtk_spin_button_get_value(GTK_SPIN_BUTTON(pct_spin));
        int new_w, new_h;
        if (pct != 100) {
            new_w = cur_w * pct / 100;
            new_h = cur_h * pct / 100;
        } else {
            new_w = (int)gtk_spin_button_get_value(GTK_SPIN_BUTTON(w_spin));
            new_h = (int)gtk_spin_button_get_value(GTK_SPIN_BUTTON(h_spin));
        }
        if (new_w > 0 && new_h > 0 && (new_w != cur_w || new_h != cur_h)) {
            GdkPixbuf* pb = gdk_pixbuf_get_from_surface(win_data->current_image, 0, 0, cur_w, cur_h);
            if (pb) {
                GdkPixbuf* resized = gdk_pixbuf_scale_simple(pb, new_w, new_h, GDK_INTERP_BILINEAR);
                g_object_unref(pb);
                if (resized) {
                    char msg[64];
                    snprintf(msg, sizeof(msg), "Resized to %dx%d", new_w, new_h);
                    replace_image_from_pixbuf(win, win_data, resized, msg);
                    g_object_unref(resized);
                }
            }
        }
    }
    gtk_widget_destroy(dialog);
}

// Helper callback: button in rotate dialog emits response
static void rotate_btn_clicked(GtkWidget* btn, gpointer dialog) {
    int resp = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(btn), "resp-id"));
    gtk_dialog_response(GTK_DIALOG(dialog), resp);
}

static void show_rotate_dialog(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image");
        return;
    }

    int cur_w = cairo_image_surface_get_width(win_data->current_image);
    int cur_h = cairo_image_surface_get_height(win_data->current_image);

    GtkWidget* dialog = gtk_dialog_new_with_buttons("Rotate / Flip",
        GTK_WINDOW(win->window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Cancel", GTK_RESPONSE_CANCEL, NULL);
    gtk_window_set_resizable(GTK_WINDOW(dialog), FALSE);
    GtkWidget* content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(content), 16);
    gtk_box_set_spacing(GTK_BOX(content), 6);

    // Stacked buttons — narrow vertical layout
    const char* labels[] = {
        "Rotate 90\xC2\xB0 Right",
        "Rotate 90\xC2\xB0 Left",
        "Rotate 180\xC2\xB0",
        "Flip Horizontal",
        "Flip Vertical"
    };
    const int resp_ids[] = {10, 11, 12, 13, 14};

    for (int i = 0; i < 5; i++) {
        GtkWidget* btn = gtk_button_new_with_label(labels[i]);
        g_object_set_data(G_OBJECT(btn), "resp-id", GINT_TO_POINTER(resp_ids[i]));
        g_signal_connect(btn, "clicked", G_CALLBACK(rotate_btn_clicked), dialog);
        gtk_box_pack_start(GTK_BOX(content), btn, FALSE, FALSE, 0);
    }

    gtk_widget_show_all(dialog);
    int response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);

    GdkPixbuf* pb = gdk_pixbuf_get_from_surface(win_data->current_image, 0, 0, cur_w, cur_h);
    if (!pb) return;

    GdkPixbuf* result = NULL;
    const char* msg = "";
    switch (response) {
        case 10: result = gdk_pixbuf_rotate_simple(pb, GDK_PIXBUF_ROTATE_CLOCKWISE); msg = "Rotated 90 right"; break;
        case 11: result = gdk_pixbuf_rotate_simple(pb, GDK_PIXBUF_ROTATE_COUNTERCLOCKWISE); msg = "Rotated 90 left"; break;
        case 12: result = gdk_pixbuf_rotate_simple(pb, GDK_PIXBUF_ROTATE_UPSIDEDOWN); msg = "Rotated 180"; break;
        case 13: result = gdk_pixbuf_flip(pb, TRUE); msg = "Flipped horizontal"; break;
        case 14: result = gdk_pixbuf_flip(pb, FALSE); msg = "Flipped vertical"; break;
        default: break;
    }

    g_object_unref(pb);
    if (result) {
        replace_image_from_pixbuf(win, win_data, result, msg);
        g_object_unref(result);
    }
}

// Brightness dialog state for real-time preview
typedef struct {
    MainWindow* win;
    MainWindowData* win_data;
    cairo_surface_t* original;  // Copy of image before adjustments
    GtkWidget* br_scale;
    GtkWidget* ct_scale;
    GtkWidget* bw_check;
    GtkWidget* inv_check;
    int width, height;
} BrightnessState;

static void apply_brightness_preview(BrightnessState* state) {
    double brightness = gtk_range_get_value(GTK_RANGE(state->br_scale)) / 100.0;
    double contrast = gtk_range_get_value(GTK_RANGE(state->ct_scale)) / 100.0;
    gboolean grayscale = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(state->bw_check));
    gboolean invert = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(state->inv_check));

    // Restore from original first
    cairo_surface_flush(state->original);
    unsigned char* src = cairo_image_surface_get_data(state->original);
    int src_stride = cairo_image_surface_get_stride(state->original);

    cairo_surface_flush(state->win_data->current_image);
    unsigned char* dst = cairo_image_surface_get_data(state->win_data->current_image);
    int dst_stride = cairo_image_surface_get_stride(state->win_data->current_image);

    double cf = 1.0 + contrast;
    for (int y = 0; y < state->height; y++) {
        for (int x = 0; x < state->width; x++) {
            int si = y * src_stride + x * 4;
            int di = y * dst_stride + x * 4;
            double b = src[si + 0] / 255.0;
            double g = src[si + 1] / 255.0;
            double r = src[si + 2] / 255.0;
            double a = src[si + 3];

            r += brightness; g += brightness; b += brightness;
            r = (r - 0.5) * cf + 0.5;
            g = (g - 0.5) * cf + 0.5;
            b = (b - 0.5) * cf + 0.5;
            if (grayscale) { double l = r*0.299 + g*0.587 + b*0.114; r=g=b=l; }
            if (invert) { r=1-r; g=1-g; b=1-b; }
            r = r < 0 ? 0 : (r > 1 ? 1 : r);
            g = g < 0 ? 0 : (g > 1 ? 1 : g);
            b = b < 0 ? 0 : (b > 1 ? 1 : b);

            dst[di + 0] = (unsigned char)(b * 255);
            dst[di + 1] = (unsigned char)(g * 255);
            dst[di + 2] = (unsigned char)(r * 255);
            dst[di + 3] = (unsigned char)(a);
        }
    }
    cairo_surface_mark_dirty(state->win_data->current_image);
    gtk_widget_queue_draw(state->win->canvas);
}

static void on_brightness_changed(GtkWidget* widget, gpointer data) {
    (void)widget;
    apply_brightness_preview((BrightnessState*)data);
}

static void show_brightness_dialog(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image");
        return;
    }

    // Save original for undo and real-time preview
    push_image_undo(win_data);

    int cur_w = cairo_image_surface_get_width(win_data->current_image);
    int cur_h = cairo_image_surface_get_height(win_data->current_image);

    // Make a working copy of the original for preview restoration
    cairo_surface_t* original = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, cur_w, cur_h);
    cairo_t* copy_cr = cairo_create(original);
    cairo_set_source_surface(copy_cr, win_data->current_image, 0, 0);
    cairo_paint(copy_cr);
    cairo_destroy(copy_cr);

    GtkWidget* dialog = gtk_dialog_new_with_buttons("Brightness / Color",
        GTK_WINDOW(win->window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Cancel", GTK_RESPONSE_CANCEL, "Apply", GTK_RESPONSE_ACCEPT, NULL);
    gtk_window_set_default_size(GTK_WINDOW(dialog), 400, -1);
    GtkWidget* content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(content), 20);
    gtk_box_set_spacing(GTK_BOX(content), 8);

    // State for callbacks
    BrightnessState state = {win, win_data, original, NULL, NULL, NULL, NULL, cur_w, cur_h};

    // Brightness
    GtkWidget* br_title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(br_title), "<b>Brightness</b>");
    gtk_widget_set_halign(br_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(content), br_title, FALSE, FALSE, 0);
    state.br_scale = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, -100, 100, 1);
    gtk_range_set_value(GTK_RANGE(state.br_scale), 0);
    gtk_scale_set_value_pos(GTK_SCALE(state.br_scale), GTK_POS_RIGHT);
    gtk_widget_set_size_request(state.br_scale, 300, -1);
    g_signal_connect(state.br_scale, "value-changed", G_CALLBACK(on_brightness_changed), &state);
    gtk_box_pack_start(GTK_BOX(content), state.br_scale, FALSE, FALSE, 4);

    // Contrast
    GtkWidget* ct_title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(ct_title), "<b>Contrast</b>");
    gtk_widget_set_halign(ct_title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(content), ct_title, FALSE, FALSE, 0);
    state.ct_scale = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, -100, 100, 1);
    gtk_range_set_value(GTK_RANGE(state.ct_scale), 0);
    gtk_scale_set_value_pos(GTK_SCALE(state.ct_scale), GTK_POS_RIGHT);
    gtk_widget_set_size_request(state.ct_scale, 300, -1);
    g_signal_connect(state.ct_scale, "value-changed", G_CALLBACK(on_brightness_changed), &state);
    gtk_box_pack_start(GTK_BOX(content), state.ct_scale, FALSE, FALSE, 4);

    gtk_box_pack_start(GTK_BOX(content), gtk_separator_new(GTK_ORIENTATION_HORIZONTAL), FALSE, FALSE, 6);

    // Grayscale + Invert
    state.bw_check = gtk_check_button_new_with_label("Grayscale (Black & White)");
    g_signal_connect(state.bw_check, "toggled", G_CALLBACK(on_brightness_changed), &state);
    gtk_box_pack_start(GTK_BOX(content), state.bw_check, FALSE, FALSE, 4);

    state.inv_check = gtk_check_button_new_with_label("Invert Colors");
    g_signal_connect(state.inv_check, "toggled", G_CALLBACK(on_brightness_changed), &state);
    gtk_box_pack_start(GTK_BOX(content), state.inv_check, FALSE, FALSE, 4);

    gtk_widget_show_all(dialog);

    int response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);

    if (response != GTK_RESPONSE_ACCEPT) {
        // Cancel — restore original from undo stack
        undo_last_annotation(win_data);
    } else {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Brightness/color adjusted");
    }

    cairo_surface_destroy(original);
}

static void duplicate_current_image(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image to duplicate");
        return;
    }

    Settings* settings = safe_get_data(win->window, "settings", "duplicate_current_image");
    const char* save_dir = (settings && settings->screenshot_path) ?
                           settings->screenshot_path :
                           g_get_user_special_dir(G_USER_DIRECTORY_PICTURES);

    // Determine base name from current filename or generate one
    const char* base_name = win_data->current_filename;
    char* generated = NULL;
    if (!base_name) {
        generated = generate_screenshot_filename(win);
        base_name = generated;
    }

    // Get just the filename without directory
    char* basename_only = g_path_get_basename(base_name);

    // Split at last '.' to insert _N before extension
    char* dot = strrchr(basename_only, '.');
    char* name_prefix;
    const char* ext;
    if (dot) {
        name_prefix = g_strndup(basename_only, (gsize)(dot - basename_only));
        ext = dot;  // includes the dot
    } else {
        name_prefix = g_strdup(basename_only);
        ext = ".png";
    }

    // Find next available number
    int n = 1;
    char* dest_path = NULL;
    while (1) {
        g_free(dest_path);
        dest_path = g_strdup_printf("%s/%s_%d%s", save_dir, name_prefix, n, ext);
        if (!g_file_test(dest_path, G_FILE_TEST_EXISTS)) break;
        n++;
        if (n > 9999) break;  // Safety limit
    }

    // Save the current image (with annotations baked in) as the duplicate
    int w = cairo_image_surface_get_width(win_data->current_image);
    int h = cairo_image_surface_get_height(win_data->current_image);
    cairo_surface_t* combined = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_t* cr = cairo_create(combined);
    cairo_set_source_surface(cr, win_data->current_image, 0, 0);
    cairo_paint(cr);
    for (GList* iter = win_data->annotations; iter; iter = iter->next) {
        annotation_draw((Annotation*)iter->data, cr);
    }
    cairo_destroy(cr);

    // Save using GdkPixbuf
    GdkPixbuf* pb = gdk_pixbuf_get_from_surface(combined, 0, 0, w, h);
    cairo_surface_destroy(combined);
    if (pb) {
        const char* save_ext = ext + 1;  // skip the dot
        const char* format = "png";
        if (g_ascii_strcasecmp(save_ext, "jpg") == 0 || g_ascii_strcasecmp(save_ext, "jpeg") == 0)
            format = "jpeg";
        else if (g_ascii_strcasecmp(save_ext, "bmp") == 0)
            format = "bmp";
        else if (g_ascii_strcasecmp(save_ext, "tiff") == 0 || g_ascii_strcasecmp(save_ext, "tif") == 0)
            format = "tiff";

        GError* error = NULL;
        if (gdk_pixbuf_save(pb, dest_path, format, &error, NULL)) {
            char msg[256];
            char* dest_base = g_path_get_basename(dest_path);
            snprintf(msg, sizeof(msg), "Duplicated: %s", dest_base);
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
            g_free(dest_base);
        } else {
            char msg[256];
            snprintf(msg, sizeof(msg), "Failed to duplicate: %s", error ? error->message : "unknown error");
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
            if (error) g_error_free(error);
        }
        g_object_unref(pb);
    }

    g_free(dest_path);
    g_free(name_prefix);
    g_free(basename_only);
    g_free(generated);
}

static void undo_last_annotation(MainWindowData* win_data) {
    // First try undoing annotations
    if (win_data->annotations) {
        GList* last = g_list_last(win_data->annotations);
        Annotation* annotation = last->data;
        win_data->annotations = g_list_delete_link(win_data->annotations, last);
        win_data->undo_stack = g_list_append(win_data->undo_stack, annotation);
        gtk_widget_queue_draw(win_data->win.canvas);
        return;
    }

    // No annotations — try undoing image-level operations (crop, resize, rotate, brightness)
    if (win_data->image_undo_stack) {
        GList* top = win_data->image_undo_stack;
        cairo_surface_t* prev = (cairo_surface_t*)top->data;
        win_data->image_undo_stack = g_list_delete_link(win_data->image_undo_stack, top);

        if (win_data->current_image) {
            cairo_surface_destroy(win_data->current_image);
        }
        win_data->current_image = prev;
        win_data->zoom_level = 1.0;
        gtk_widget_queue_draw(win_data->win.canvas);

        MainWindow* mwin = &win_data->win;
        update_image_info(mwin, win_data, NULL);
        gtk_statusbar_push(GTK_STATUSBAR(mwin->statusbar), 0, "Undo: image restored");
    }
}

static void flatten_paste_overlay(MainWindow* win, MainWindowData* win_data) {
    if (!win_data->paste_overlays && !win_data->paste_overlay) {
        // Nothing to flatten — just bake annotations if any
        if (!win_data->annotations && !win_data->current_image) return;
    }
    if (!win_data->current_image) return;

    int img_w = cairo_image_surface_get_width(win_data->current_image);
    int img_h = cairo_image_surface_get_height(win_data->current_image);

    cairo_surface_t* combined = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, img_w, img_h);
    cairo_t* cr = cairo_create(combined);

    // Draw existing image
    cairo_set_source_surface(cr, win_data->current_image, 0, 0);
    cairo_paint(cr);

    // Draw existing annotations
    for (GList* iter = win_data->annotations; iter; iter = iter->next) {
        annotation_draw((Annotation*)iter->data, cr);
    }

    // Draw all paste overlays at their positions
    for (GList* iter = win_data->paste_overlays; iter; iter = iter->next) {
        PasteOverlay* overlay = (PasteOverlay*)iter->data;
        cairo_set_source_surface(cr, overlay->surface, overlay->x, overlay->y);
        cairo_paint(cr);
    }

    cairo_destroy(cr);

    // Replace current image
    cairo_surface_destroy(win_data->current_image);
    win_data->current_image = combined;

    // Clear annotations (baked in)
    g_list_free_full(win_data->annotations, (GDestroyNotify)annotation_free);
    win_data->annotations = NULL;
    g_list_free_full(win_data->undo_stack, (GDestroyNotify)annotation_free);
    win_data->undo_stack = NULL;

    // Clear all paste overlays
    g_list_free_full(win_data->paste_overlays, (GDestroyNotify)paste_overlay_free);
    win_data->paste_overlays = NULL;
    win_data->paste_overlay = NULL;
    win_data->dragging_overlay = NULL;
    win_data->has_marquee = false;

    int count = 0;
    char msg[128];
    snprintf(msg, sizeof(msg), "All overlays and annotations flattened into image");
    gtk_widget_queue_draw(win->canvas);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
    (void)count;
}

static void on_flatten_button_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_flatten_button_clicked");
    if (win_data) {
        flatten_paste_overlay(win, win_data);
    }
}

static void update_image_info(MainWindow* win, MainWindowData* win_data, const char* filepath) {
    GtkWidget* info_label = safe_get_data(win->window, "image-info-label", "update_image_info");
    if (!info_label || !GTK_IS_LABEL(info_label)) return;

    if (!win_data->current_image) {
        gtk_label_set_text(GTK_LABEL(info_label), "");
        return;
    }

    int w = cairo_image_surface_get_width(win_data->current_image);
    int h = cairo_image_surface_get_height(win_data->current_image);

    char size_str[32] = "";
    if (filepath) {
        struct stat st;
        if (stat(filepath, &st) == 0) {
            if (st.st_size >= 1048576) {
                snprintf(size_str, sizeof(size_str), "  %.1fMB", (double)st.st_size / 1048576.0);
            } else if (st.st_size >= 1024) {
                snprintf(size_str, sizeof(size_str), "  %.0fKB", (double)st.st_size / 1024.0);
            } else {
                snprintf(size_str, sizeof(size_str), "  %ldB", (long)st.st_size);
            }
        }
    }

    char msg[128];
    snprintf(msg, sizeof(msg), "%dx%d%s", w, h, size_str);
    gtk_label_set_text(GTK_LABEL(info_label), msg);
}

static void paste_overlay_free(PasteOverlay* overlay) {
    if (!overlay) return;
    if (overlay->surface) cairo_surface_destroy(overlay->surface);
    free(overlay);
}

static void paste_from_clipboard(MainWindow* win, MainWindowData* win_data) {
    GtkClipboard* clipboard = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
    GdkPixbuf* pb = gtk_clipboard_wait_for_image(clipboard);
    if (!pb) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image in clipboard to paste");
        return;
    }

    int paste_w = gdk_pixbuf_get_width(pb);
    int paste_h = gdk_pixbuf_get_height(pb);

    // Create a new paste overlay
    PasteOverlay* overlay = (PasteOverlay*)malloc(sizeof(PasteOverlay));
    overlay->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, paste_w, paste_h);
    cairo_t* cr = cairo_create(overlay->surface);
    gdk_cairo_set_source_pixbuf(cr, pb, 0, 0);
    cairo_paint(cr);
    cairo_destroy(cr);

    // Position: offset each successive paste so they don't stack exactly
    int count = g_list_length(win_data->paste_overlays);
    double offset = count * 20.0;

    if (win_data->current_image) {
        int img_w = cairo_image_surface_get_width(win_data->current_image);
        int img_h = cairo_image_surface_get_height(win_data->current_image);
        overlay->x = (img_w - paste_w) / 2.0 + offset;
        overlay->y = (img_h - paste_h) / 2.0 + offset;
        if (overlay->x < 0) overlay->x = 0;
        if (overlay->y < 0) overlay->y = 0;
    } else {
        // No image — create a canvas from the paste
        win_data->current_image = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, paste_w, paste_h);
        cairo_t* bgcr = cairo_create(win_data->current_image);
        cairo_set_source_rgb(bgcr, 1.0, 1.0, 1.0);
        cairo_paint(bgcr);
        cairo_destroy(bgcr);
        overlay->x = 0;
        overlay->y = 0;
    }

    // Add to multi-paste list
    win_data->paste_overlays = g_list_append(win_data->paste_overlays, overlay);

    // Also set legacy single pointer to the newest overlay for backward compat
    win_data->paste_overlay = overlay->surface;
    win_data->paste_x = overlay->x;
    win_data->paste_y = overlay->y;

    win_data->dragging_paste = false;
    win_data->dragging_overlay = NULL;
    win_data->has_marquee = false;

    g_object_unref(pb);

    // Switch to Screenshot tab
    GtkWidget* notebook = gtk_widget_get_ancestor(win->canvas, GTK_TYPE_NOTEBOOK);
    if (notebook) {
        gtk_notebook_set_current_page(GTK_NOTEBOOK(notebook), 0);
    }

    char msg[128];
    snprintf(msg, sizeof(msg), "Pasted (%d overlay%s) - drag to position, Flatten to commit",
             count + 1, count > 0 ? "s" : "");
    gtk_widget_queue_draw(win->canvas);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
}

// GDK event filter — intercepts key events BEFORE any GTK widget sees them
static GdkFilterReturn key_filter_func_global(GdkXEvent* xevent, GdkEvent* event, gpointer data) {
    (void)xevent;
    if (!event || event->type != GDK_KEY_PRESS) return GDK_FILTER_CONTINUE;

    GdkEventKey* key = (GdkEventKey*)event;
    MainWindow* win = (MainWindow*)data;

    if (!(key->state & GDK_CONTROL_MASK)) return GDK_FILTER_CONTINUE;

    MainWindowData* win_data = safe_get_data(win->window, "window-data", "key_filter_func_global");
    if (!win_data) return GDK_FILTER_CONTINUE;

    switch (key->keyval) {
        case GDK_KEY_s:
            on_save_button_clicked(NULL, win);
            return GDK_FILTER_REMOVE;
        case GDK_KEY_c:
            on_copy_button_clicked(NULL, win);
            return GDK_FILTER_REMOVE;
        case GDK_KEY_v:
            paste_from_clipboard(win, win_data);
            gtk_widget_grab_focus(win->canvas);
            return GDK_FILTER_REMOVE;
        case GDK_KEY_z:
            undo_last_annotation(win_data);
            gtk_widget_grab_focus(win->canvas);
            return GDK_FILTER_REMOVE;
        case GDK_KEY_n:
            on_capture_button_clicked(NULL, win);
            return GDK_FILTER_REMOVE;
        default:
            break;
    }
    return GDK_FILTER_CONTINUE;
}

static gboolean on_key_press(GtkWidget* widget, GdkEventKey* event, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_key_press");

    if (event->state & GDK_CONTROL_MASK) {
        // Always handle app shortcuts, even when focus is on a spinbutton/entry/combo.
        // We intercept before GTK's built-in text editing handlers.
        switch (event->keyval) {
            case GDK_KEY_z:  // Ctrl+Z: Undo
                undo_last_annotation(win_data);
                gtk_widget_grab_focus(win->canvas);
                return TRUE;

            case GDK_KEY_v:  // Ctrl+V: Paste
                paste_from_clipboard(win, win_data);
                gtk_widget_grab_focus(win->canvas);
                return TRUE;

            case GDK_KEY_c:  // Ctrl+C: Copy to clipboard
                on_copy_button_clicked(NULL, win);
                return TRUE;

            case GDK_KEY_s:  // Ctrl+S: Save
                on_save_button_clicked(NULL, win);
                return TRUE;

            case GDK_KEY_n:  // Ctrl+N: New capture
                on_capture_button_clicked(NULL, win);
                return TRUE;

            case GDK_KEY_a:  // Ctrl+A: Select all (marquee entire image)
                if (win_data->current_image) {
                    int w = cairo_image_surface_get_width(win_data->current_image);
                    int h = cairo_image_surface_get_height(win_data->current_image);
                    win_data->has_marquee = true;
                    win_data->marquee_bounds.x1 = 0;
                    win_data->marquee_bounds.y1 = 0;
                    win_data->marquee_bounds.x2 = w;
                    win_data->marquee_bounds.y2 = h;
                    // Copy entire image to clipboard
                    copy_to_clipboard(win, win_data->current_image, win_data->annotations);
                    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "All selected - copied to clipboard");
                    gtk_widget_queue_draw(win->canvas);
                }
                return TRUE;

            default:
                break;
        }
    }

    // Escape: clear paste overlays or marquee selection
    if (event->keyval == GDK_KEY_Escape) {
        if (win_data->paste_overlays) {
            g_list_free_full(win_data->paste_overlays, (GDestroyNotify)paste_overlay_free);
            win_data->paste_overlays = NULL;
            win_data->paste_overlay = NULL;
            win_data->dragging_overlay = NULL;
            gtk_widget_queue_draw(win->canvas);
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "All pastes discarded");
            return TRUE;
        }
        if (win_data->has_marquee) {
            win_data->has_marquee = false;
            gtk_widget_queue_draw(win->canvas);
            gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Selection cleared");
            return TRUE;
        }
    }

    // Delete key: delete selected history images
    if (event->keyval == GDK_KEY_Delete && win->history_flow_box) {
        GList* selected = gtk_flow_box_get_selected_children(GTK_FLOW_BOX(win->history_flow_box));
        if (selected) {
            on_delete_selected_clicked(NULL, win);
            g_list_free(selected);
            return TRUE;
        }
    }

    // Delete: remove selected region content
    if (event->keyval == GDK_KEY_Delete && win_data->has_marquee && win_data->current_image) {
        cairo_t* cr = cairo_create(win_data->current_image);
        int x = win_data->marquee_bounds.x1;
        int y = win_data->marquee_bounds.y1;
        int w = win_data->marquee_bounds.x2 - x;
        int h = win_data->marquee_bounds.y2 - y;
        cairo_set_source_rgb(cr, 1.0, 1.0, 1.0);
        cairo_rectangle(cr, x, y, w, h);
        cairo_fill(cr);
        cairo_destroy(cr);
        win_data->has_marquee = false;
        gtk_widget_queue_draw(win->canvas);
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Selection deleted");
        return TRUE;
    }

    return FALSE;
}

// Generate a sequenced save filename from the original capture filename
// e.g. /path/LinScreenCapture_20260328_120000.png -> /path/LinScreenCapture_20260328_120000_1.png
static char* generate_save_filename(MainWindowData* win_data, MainWindow* win) {
    Settings* settings = safe_get_data(win->window, "settings", "generate_save_filename");
    char* base = win_data->current_filename;
    if (!base) {
        // Fallback if no original filename tracked
        return generate_screenshot_filename(win);
    }

    // Use just the basename from the original file, combined with Settings path
    char* basename = g_path_get_basename(base);
    char* save_dir = (settings && settings->screenshot_path) ?
                     settings->screenshot_path :
                     (char*)g_get_user_special_dir(G_USER_DIRECTORY_PICTURES);

    // Split basename at last '.' to insert _N before extension
    char* dot = strrchr(basename, '.');
    if (!dot) {
        char* result = g_strdup_printf("%s/%s_%d", save_dir, basename, win_data->save_sequence);
        g_free(basename);
        return result;
    }

    // Build: save_dir/name_N.ext
    size_t prefix_len = (size_t)(dot - basename);
    char* name_prefix = g_strndup(basename, prefix_len);
    char* result = g_strdup_printf("%s/%s_%d%s", save_dir, name_prefix, win_data->save_sequence, dot);
    g_free(name_prefix);
    g_free(basename);
    return result;
}

static void on_save_button_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_save_button_clicked");

    if (!win_data->current_image) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No image to save");
        return;
    }

    // Generate sequenced filename based on original capture name
    char* default_filename = generate_save_filename(win_data, win);

    GtkWidget* dialog = gtk_file_chooser_dialog_new(
        "Save Screenshot",
        GTK_WINDOW(win->window),
        GTK_FILE_CHOOSER_ACTION_SAVE,
        "Cancel", GTK_RESPONSE_CANCEL,
        "Save", GTK_RESPONSE_ACCEPT,
        NULL
    );

    // Split into folder and basename for the save dialog
    char* dir = g_path_get_dirname(default_filename);
    char* base = g_path_get_basename(default_filename);
    gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(dialog), dir);
    gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(dialog), base);
    g_free(dir);
    g_free(base);
    g_free(default_filename);
    
    // Add file filters
    GtkFileFilter* filter_all = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_all, "All Supported Formats");
    gtk_file_filter_add_pattern(filter_all, "*.*");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_all);
    
    GtkFileFilter* filter_jpg = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_jpg, "JPEG Images (*.jpg, *.jpeg)");
    gtk_file_filter_add_pattern(filter_jpg, "*.jpg");
    gtk_file_filter_add_pattern(filter_jpg, "*.jpeg");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_jpg);
    
    GtkFileFilter* filter_png = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_png, "PNG Images (*.png)");
    gtk_file_filter_add_pattern(filter_png, "*.png");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_png);
    
    GtkFileFilter* filter_gif = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_gif, "GIF Images (*.gif)");
    gtk_file_filter_add_pattern(filter_gif, "*.gif");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_gif);
    
    GtkFileFilter* filter_svg = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_svg, "SVG Images (*.svg)");
    gtk_file_filter_add_pattern(filter_svg, "*.svg");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_svg);
    
    GtkFileFilter* filter_tiff = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_tiff, "TIFF Images (*.tif, *.tiff)");
    gtk_file_filter_add_pattern(filter_tiff, "*.tif");
    gtk_file_filter_add_pattern(filter_tiff, "*.tiff");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_tiff);
    
    GtkFileFilter* filter_webp = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_webp, "WebP Images (*.webp)");
    gtk_file_filter_add_pattern(filter_webp, "*.webp");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_webp);
    
    GtkFileFilter* filter_bmp = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_bmp, "BMP Images (*.bmp)");
    gtk_file_filter_add_pattern(filter_bmp, "*.bmp");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_bmp);
    
    GtkFileFilter* filter_heic = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_heic, "HEIC/HEIF Images (*.heic, *.heif)");
    gtk_file_filter_add_pattern(filter_heic, "*.heic");
    gtk_file_filter_add_pattern(filter_heic, "*.heif");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_heic);
    
    GtkFileFilter* filter_raw = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_raw, "RAW Images (*.raw)");
    gtk_file_filter_add_pattern(filter_raw, "*.raw");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_raw);
    
    GtkFileFilter* filter_ico = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_ico, "ICO Images (*.ico)");
    gtk_file_filter_add_pattern(filter_ico, "*.ico");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_ico);
    
    GtkFileFilter* filter_psd = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_psd, "PSD Images (*.psd)");
    gtk_file_filter_add_pattern(filter_psd, "*.psd");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_psd);
    
    GtkFileFilter* filter_eps = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_eps, "EPS Images (*.eps)");
    gtk_file_filter_add_pattern(filter_eps, "*.eps");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_eps);
    
    GtkFileFilter* filter_ai = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_ai, "AI Images (*.ai)");
    gtk_file_filter_add_pattern(filter_ai, "*.ai");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_ai);
    
    GtkFileFilter* filter_avif = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_avif, "AVIF Images (*.avif)");
    gtk_file_filter_add_pattern(filter_avif, "*.avif");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_avif);
    
    GtkFileFilter* filter_cr2 = gtk_file_filter_new();
    gtk_file_filter_set_name(filter_cr2, "CR2/CR3 Images (*.cr2, *.cr3)");
    gtk_file_filter_add_pattern(filter_cr2, "*.cr2");
    gtk_file_filter_add_pattern(filter_cr2, "*.cr3");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter_cr2);
    
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_ACCEPT) {
        char* filename = gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(dialog));
        save_image_with_annotations(win, win_data->current_image, win_data->annotations, filename);

        // Increment sequence for next save
        win_data->save_sequence++;

        g_free(filename);
    }

    gtk_widget_destroy(dialog);
}

static void save_image_with_annotations(MainWindow* win, cairo_surface_t* surface, GList* annotations, const char* filename) {
    if (!surface || !filename) return;
    
    // Create a new surface with annotations
    int width = cairo_image_surface_get_width(surface);
    int height = cairo_image_surface_get_height(surface);
    cairo_surface_t* combined_surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
    
    // Create Cairo context for the new surface
    cairo_t* cr = cairo_create(combined_surface);
    
    // Draw the original image
    cairo_set_source_surface(cr, surface, 0, 0);
    cairo_paint(cr);
    
    // Draw all annotations
    GList* iter;
    for (iter = annotations; iter != NULL; iter = iter->next) {
        Annotation* annotation = (Annotation*)iter->data;
        annotation_draw(annotation, cr);
    }

    // Draw all paste overlays (if any are still floating)
    MainWindowData* save_win_data = safe_get_data(win->window, "window-data", "save_image_with_annotations");
    if (save_win_data) {
        for (GList* piter = save_win_data->paste_overlays; piter; piter = piter->next) {
            PasteOverlay* overlay = (PasteOverlay*)piter->data;
            cairo_set_source_surface(cr, overlay->surface, overlay->x, overlay->y);
            cairo_paint(cr);
        }
    }

    // Ensure all drawing operations are complete
    cairo_surface_flush(combined_surface);

    // Get the file extension
    const char* ext = strrchr(filename, '.');
    if (!ext) {
        cairo_destroy(cr);
        cairo_surface_destroy(combined_surface);
        return;
    }
    ext++; // Skip the dot
    
    // Create a pixbuf from the surface
    GdkPixbuf* pixbuf = gdk_pixbuf_get_from_surface(combined_surface, 0, 0, width, height);
    if (!pixbuf) {
        cairo_destroy(cr);
        cairo_surface_destroy(combined_surface);
        return;
    }
    
    // Save based on file extension
    GError* error = NULL;
    if (g_ascii_strcasecmp(ext, "jpg") == 0 || g_ascii_strcasecmp(ext, "jpeg") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "jpeg", &error, "quality", "100", NULL);
    } else if (g_ascii_strcasecmp(ext, "png") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "png", &error, "compression", "9", NULL);
    } else if (g_ascii_strcasecmp(ext, "gif") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "gif", &error, NULL);
    } else if (g_ascii_strcasecmp(ext, "svg") == 0) {
        // Note: SVG requires special handling as it's a vector format
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "SVG format not supported for screenshots");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "SVG format not supported for screenshots");
    } else if (g_ascii_strcasecmp(ext, "tiff") == 0 || g_ascii_strcasecmp(ext, "tif") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "tiff", &error, NULL);
    } else if (g_ascii_strcasecmp(ext, "webp") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "webp", &error, "quality", "100", NULL);
    } else if (g_ascii_strcasecmp(ext, "bmp") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "bmp", &error, NULL);
    } else if (g_ascii_strcasecmp(ext, "heic") == 0 || g_ascii_strcasecmp(ext, "heif") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "HEIC/HEIF format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "HEIC/HEIF format not supported");
    } else if (g_ascii_strcasecmp(ext, "raw") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "RAW format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "RAW format not supported");
    } else if (g_ascii_strcasecmp(ext, "ico") == 0) {
        gdk_pixbuf_save(pixbuf, filename, "ico", &error, NULL);
    } else if (g_ascii_strcasecmp(ext, "psd") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "PSD format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "PSD format not supported");
    } else if (g_ascii_strcasecmp(ext, "eps") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "EPS format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "EPS format not supported");
    } else if (g_ascii_strcasecmp(ext, "ai") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "AI format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "AI format not supported");
    } else if (g_ascii_strcasecmp(ext, "avif") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "AVIF format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "AVIF format not supported");
    } else if (g_ascii_strcasecmp(ext, "cr2") == 0 || g_ascii_strcasecmp(ext, "cr3") == 0) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "CR2/CR3 format not supported");
        error = g_error_new(G_FILE_ERROR, G_FILE_ERROR_FAILED, "CR2/CR3 format not supported");
    }
    
    if (error) {
        char error_msg[256];
        snprintf(error_msg, sizeof(error_msg), "Failed to save image: %s", error->message);
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, error_msg);
        g_error_free(error);
    } else {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Image saved successfully");
        
        // Add to history
        screenshot_history_add(&win->screenshot_history, filename);
        
        // Clear existing history items
        GList* children = gtk_container_get_children(GTK_CONTAINER(win->history_flow_box));
        for (GList* iter = children; iter != NULL; iter = iter->next) {
            gtk_widget_destroy(GTK_WIDGET(iter->data));
        }
        g_list_free(children);
        
        // Add updated history items
        GList* entries = screenshot_history_get_sorted(&win->screenshot_history);
        for (GList* iter = entries; iter != NULL; iter = iter->next) {
            ScreenshotEntry* entry = (ScreenshotEntry*)iter->data;
            GtkWidget* item_widget = create_history_item_widget(entry, win);
            gtk_flow_box_insert(GTK_FLOW_BOX(win->history_flow_box), item_widget, -1);
        }
        
        gtk_widget_show_all(win->history_flow_box);

        // Update image count
        GtkWidget* cnt_lbl = safe_get_data(win->window, "history-count-label", "settings_refresh_history");
        if (cnt_lbl && GTK_IS_LABEL(cnt_lbl)) {
            int cnt = g_list_length(entries);
            char cnt_msg[32];
            snprintf(cnt_msg, sizeof(cnt_msg), "%d image%s", cnt, cnt != 1 ? "s" : "");
            gtk_label_set_text(GTK_LABEL(cnt_lbl), cnt_msg);
        }
    }

    // Clean up
    g_object_unref(pixbuf);
    cairo_destroy(cr);
    cairo_surface_destroy(combined_surface);
}

static void update_delete_btn_sensitivity(MainWindow* win) {
    GtkWidget* delete_btn = safe_get_data(win->window, "delete-btn", "update_delete_btn_sensitivity");
    if (!delete_btn || !win->history_flow_box) return;
    GList* selected = gtk_flow_box_get_selected_children(GTK_FLOW_BOX(win->history_flow_box));
    gtk_widget_set_sensitive(delete_btn, selected != NULL);
    if (selected) {
        int count = g_list_length(selected);
        char msg[64];
        snprintf(msg, sizeof(msg), "%d image%s selected", count, count > 1 ? "s" : "");
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
    }
    g_list_free(selected);
}

// Called when flow box selection changes (Ctrl+Click, Shift+Click handled natively by GTK)
static void on_history_selection_changed(GtkFlowBox* flow_box, gpointer data) {
    (void)flow_box;
    MainWindow* win = (MainWindow*)data;
    update_delete_btn_sensitivity(win);
}

// Refresh history when the History tab is selected (picks up new files)
static void on_notebook_switch_page(GtkNotebook* notebook, GtkWidget* page,
                                     guint page_num, gpointer data) {
    (void)notebook; (void)page;
    if (page_num != 1) return;  // Only refresh on History tab (index 1)

    MainWindow* win = (MainWindow*)data;
    if (!win->history_flow_box) return;

    // Reload from disk
    screenshot_history_load(&win->screenshot_history);

    // Rebuild flow box
    GList* children = gtk_container_get_children(GTK_CONTAINER(win->history_flow_box));
    for (GList* iter = children; iter; iter = iter->next) {
        gtk_widget_destroy(GTK_WIDGET(iter->data));
    }
    g_list_free(children);

    GList* entries = screenshot_history_get_sorted(&win->screenshot_history);
    for (GList* iter = entries; iter; iter = iter->next) {
        ScreenshotEntry* entry = (ScreenshotEntry*)iter->data;
        GtkWidget* item_widget = create_history_item_widget(entry, win);
        gtk_flow_box_insert(GTK_FLOW_BOX(win->history_flow_box), item_widget, -1);
    }
    gtk_widget_show_all(win->history_flow_box);

    // Update count
    GtkWidget* cnt_lbl = safe_get_data(win->window, "history-count-label", "on_notebook_switch_page");
    if (cnt_lbl && GTK_IS_LABEL(cnt_lbl)) {
        int cnt = g_list_length(entries);
        char cnt_msg[32];
        snprintf(cnt_msg, sizeof(cnt_msg), "%d image%s", cnt, cnt != 1 ? "s" : "");
        gtk_label_set_text(GTK_LABEL(cnt_lbl), cnt_msg);
    }

    update_delete_btn_sensitivity(win);
}

// Double-click (child-activated) opens image in editor
static void on_history_child_activated(GtkFlowBox* flow_box, GtkFlowBoxChild* child, gpointer data) {
    (void)flow_box;
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_history_child_activated");

    // Get filepath from the child's image widget
    GtkWidget* inner = gtk_bin_get_child(GTK_BIN(child));
    if (!inner) return;
    const char* filepath = safe_get_data(inner, "filepath", "on_history_child_activated");
    if (!filepath) return;

    // Load the image using GdkPixbuf (supports PNG, JPG, BMP, GIF, TIFF, WebP, etc.)
    GdkPixbuf* pixbuf = gdk_pixbuf_new_from_file(filepath, NULL);
    if (!pixbuf) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Failed to load image");
        return;
    }

    int img_w = gdk_pixbuf_get_width(pixbuf);
    int img_h = gdk_pixbuf_get_height(pixbuf);
    cairo_surface_t* surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, img_w, img_h);
    cairo_t* load_cr = cairo_create(surface);
    gdk_cairo_set_source_pixbuf(load_cr, pixbuf, 0, 0);
    cairo_paint(load_cr);
    cairo_destroy(load_cr);
    g_object_unref(pixbuf);

    // Clean up existing image and annotations
    if (win_data->current_image) {
        cairo_surface_destroy(win_data->current_image);
    }
    g_list_free_full(win_data->annotations, (GDestroyNotify)annotation_free);

    // Set the new image
    win_data->current_image = surface;
    win_data->annotations = NULL;
    win_data->zoom_level = 1.0;

    // Clear any selections
    gtk_flow_box_unselect_all(GTK_FLOW_BOX(win->history_flow_box));
    update_delete_btn_sensitivity(win);

    // Switch to screenshot tab
    GtkWidget* notebook = gtk_widget_get_ancestor(win->canvas, GTK_TYPE_NOTEBOOK);
    if (notebook) {
        gtk_notebook_set_current_page(GTK_NOTEBOOK(notebook), 0);
    }

    gtk_widget_queue_draw(win->canvas);
    update_image_info(win, win_data, filepath);
}

static GtkWidget* create_history_item_widget(ScreenshotEntry* entry, MainWindow* win) {
    (void)win;
    // Create thumbnail — no event_box so flow box receives clicks directly
    GtkWidget* image = gtk_image_new_from_pixbuf(entry->thumbnail);
    gtk_widget_set_halign(image, GTK_ALIGN_CENTER);
    gtk_widget_set_valign(image, GTK_ALIGN_CENTER);

    // Store filepath directly on the image widget
    safe_set_data_full(image, "filepath", g_strdup(entry->filepath), g_free, "create_history_item_widget");

    return image;
}

// --- History deletion support ---
// No checkbox needed — Ctrl+Click to select/deselect, Delete button removes selected.

static void on_delete_selected_clicked(GtkWidget* widget, gpointer data) {
    (void)widget;
    MainWindow* win = (MainWindow*)data;
    if (!win->history_flow_box) return;

    GList* selected = gtk_flow_box_get_selected_children(GTK_FLOW_BOX(win->history_flow_box));
    if (!selected) {
        gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "No images selected — Ctrl+Click to select");
        return;
    }

    // Confirm deletion
    int count = g_list_length(selected);
    char msg[128];
    snprintf(msg, sizeof(msg), "Delete %d screenshot%s from disk?", count, count > 1 ? "s" : "");

    GtkWidget* dialog = gtk_message_dialog_new(GTK_WINDOW(win->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        GTK_MESSAGE_WARNING, GTK_BUTTONS_YES_NO, "%s", msg);
    gtk_window_set_title(GTK_WINDOW(dialog), "Confirm Deletion");
    int response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);

    if (response != GTK_RESPONSE_YES) {
        g_list_free(selected);
        return;
    }

    // Delete files and remove from flow box
    int deleted = 0;
    for (GList* iter = selected; iter; iter = iter->next) {
        GtkFlowBoxChild* child = GTK_FLOW_BOX_CHILD(iter->data);
        GtkWidget* inner = gtk_bin_get_child(GTK_BIN(child));
        if (!inner) continue;

        const char* filepath = safe_get_data(inner, "filepath", "on_delete_selected_clicked");
        if (filepath && g_file_test(filepath, G_FILE_TEST_EXISTS)) {
            if (g_unlink(filepath) == 0) {
                deleted++;
            }
        }
        gtk_widget_destroy(GTK_WIDGET(child));
    }
    g_list_free(selected);

    // Reload history from disk so deleted files are removed from the data structure
    screenshot_history_load(&win->screenshot_history);

    // Rebuild the flow box from the reloaded history
    GList* children = gtk_container_get_children(GTK_CONTAINER(win->history_flow_box));
    for (GList* iter = children; iter; iter = iter->next) {
        gtk_widget_destroy(GTK_WIDGET(iter->data));
    }
    g_list_free(children);

    GList* entries = screenshot_history_get_sorted(&win->screenshot_history);
    for (GList* iter = entries; iter; iter = iter->next) {
        ScreenshotEntry* entry = (ScreenshotEntry*)iter->data;
        GtkWidget* item_widget = create_history_item_widget(entry, win);
        gtk_flow_box_insert(GTK_FLOW_BOX(win->history_flow_box), item_widget, -1);
    }
    gtk_widget_show_all(win->history_flow_box);

    // Update count label
    GtkWidget* cnt_lbl = safe_get_data(win->window, "history-count-label", "on_delete_selected_clicked");
    if (cnt_lbl && GTK_IS_LABEL(cnt_lbl)) {
        int remaining = g_list_length(entries);
        char cnt_msg[32];
        snprintf(cnt_msg, sizeof(cnt_msg), "%d image%s", remaining, remaining != 1 ? "s" : "");
        gtk_label_set_text(GTK_LABEL(cnt_lbl), cnt_msg);
    }

    // Disable delete button
    update_delete_btn_sensitivity(win);

    snprintf(msg, sizeof(msg), "%d screenshot%s deleted", deleted, deleted > 1 ? "s" : "");
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, msg);
}

static void create_settings_page(MainWindow* win, GtkWidget* notebook) {
    Settings* settings = safe_get_data(win->window, "settings", "create_settings_page");
    
    GtkWidget* vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_widget_set_margin_start(vbox, 10);
    gtk_widget_set_margin_end(vbox, 10);
    gtk_widget_set_margin_top(vbox, 10);
    gtk_widget_set_margin_bottom(vbox, 10);

    // Screenshot Path Frame
    GtkWidget* path_frame = gtk_frame_new("Screenshot Path");
    GtkWidget* path_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 5);
    gtk_container_set_border_width(GTK_CONTAINER(path_box), 10);
    
    GtkWidget* path_entry = gtk_entry_new();
    gtk_widget_set_can_focus(path_entry, TRUE);
    gtk_widget_set_can_default(path_entry, FALSE);
    gtk_entry_set_text(GTK_ENTRY(path_entry), settings->screenshot_path);
    safe_set_data(path_entry, "settings", settings, "create_settings_page");
    safe_set_data(path_entry, "window", win, "create_settings_page");
    g_signal_connect(path_entry, "changed", G_CALLBACK(on_settings_changed), NULL);
    
    GtkWidget* browse_button = gtk_button_new_with_label("Browse");
    g_signal_connect(browse_button, "clicked", G_CALLBACK(on_browse_clicked), path_entry);
    
    gtk_box_pack_start(GTK_BOX(path_box), path_entry, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(path_box), browse_button, FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(path_frame), path_box);
    gtk_box_pack_start(GTK_BOX(vbox), path_frame, FALSE, FALSE, 0);

    // Filename Format Frame
    GtkWidget* format_frame = gtk_frame_new("Filename Format");
    GtkWidget* format_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_container_set_border_width(GTK_CONTAINER(format_box), 10);
    
    const char* format_labels[] = {
        "Screenshot_%Y%m%d_%H%M%S",
        "LinScreenCapture_%Y%m%d_%H%M%S",
        "Screenshot_%d_%H%M",
        "LinScreenCapture_%d_%H%M"
    };
    
    GtkWidget* format_radio = NULL;
    for (int i = 0; i < 4; i++) {
        GtkWidget* radio = gtk_radio_button_new_with_label_from_widget(
            GTK_RADIO_BUTTON(format_radio), format_labels[i]);
        format_radio = radio;
        
        safe_set_data(radio, "settings", settings, "create_settings_page");
        safe_set_data(radio, "window", win, "create_settings_page");
        safe_set_data(radio, "format", GINT_TO_POINTER(i), "create_settings_page");
        
        if (settings->filename_format == (FilenameFormat)i) {
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(radio), TRUE);
        }
        
        g_signal_connect(radio, "toggled", G_CALLBACK(on_settings_changed), NULL);
        gtk_box_pack_start(GTK_BOX(format_box), radio, FALSE, FALSE, 0);
    }
    
    gtk_container_add(GTK_CONTAINER(format_frame), format_box);
    gtk_box_pack_start(GTK_BOX(vbox), format_frame, FALSE, FALSE, 0);

    // Startup Options Frame
    GtkWidget* startup_frame = gtk_frame_new("Startup Options");
    GtkWidget* startup_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_container_set_border_width(GTK_CONTAINER(startup_box), 10);

    GtkWidget* autostart_check = gtk_check_button_new_with_label("Start with OS");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(autostart_check), settings->start_with_os);
    safe_set_data(autostart_check, "settings", settings, "create_settings_page");
    safe_set_data(autostart_check, "window", win, "create_settings_page");
    g_signal_connect(autostart_check, "toggled", G_CALLBACK(on_settings_changed), NULL);
    gtk_box_pack_start(GTK_BOX(startup_box), autostart_check, FALSE, FALSE, 0);

    GtkWidget* default_app_check = gtk_check_button_new_with_label(
        "Set as default screenshot app (remaps PrintScreen key)");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(default_app_check), settings->default_screenshot_app);
    safe_set_data(default_app_check, "settings", settings, "create_settings_page");
    safe_set_data(default_app_check, "window", win, "create_settings_page");
    safe_set_data(default_app_check, "default-app", GINT_TO_POINTER(1), "create_settings_page");
    g_signal_connect(default_app_check, "toggled", G_CALLBACK(on_settings_changed), NULL);
    gtk_box_pack_start(GTK_BOX(startup_box), default_app_check, FALSE, FALSE, 0);

    gtk_container_add(GTK_CONTAINER(startup_frame), startup_box);
    gtk_box_pack_start(GTK_BOX(vbox), startup_frame, FALSE, FALSE, 0);

    // Desktop environment detection label
    char de_info[128];
    snprintf(de_info, sizeof(de_info), "Desktop: %s", desktop_env_name(settings->detected_de));
    GtkWidget* de_label = gtk_label_new(de_info);
    gtk_widget_set_halign(de_label, GTK_ALIGN_START);
    gtk_widget_set_opacity(de_label, 0.6);
    gtk_box_pack_start(GTK_BOX(vbox), de_label, FALSE, FALSE, 2);

    // Shortcut Key Frame
    GtkWidget* shortcut_frame = gtk_frame_new("Shortcut Key");
    GtkWidget* shortcut_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_container_set_border_width(GTK_CONTAINER(shortcut_box), 10);
    
    // Labels and enum values must match 1:1
    const char* shortcut_labels[] = {
        "Print Screen",
        "Ctrl + Print Screen",
        "Shift + Print Screen",
        "Ctrl + Shift + S",
        "Ctrl + Alt + S"
    };
    // Map radio index -> ShortcutKey enum value (skip SHORTCUT_NONE=0)
    const ShortcutKey shortcut_values[] = {
        SHORTCUT_PRINTSCREEN,       // 1
        SHORTCUT_CTRL_PRINTSCREEN,  // 2
        SHORTCUT_SHIFT_PRINTSCREEN, // 3
        SHORTCUT_CTRL_SHIFT_S,      // 4
        SHORTCUT_CTRL_ALT_S         // 5
    };

    GtkWidget* shortcut_radio = NULL;
    for (int i = 0; i < 5; i++) {
        GtkWidget* radio = gtk_radio_button_new_with_label_from_widget(
            GTK_RADIO_BUTTON(shortcut_radio), shortcut_labels[i]);
        shortcut_radio = radio;

        safe_set_data(radio, "settings", settings, "create_settings_page");
        safe_set_data(radio, "window", win, "create_settings_page");
        // Store enum value (1-5), never 0, so GINT_TO_POINTER is always non-NULL
        safe_set_data(radio, "shortcut", GINT_TO_POINTER(shortcut_values[i]), "create_settings_page");

        if (settings->shortcut_key == shortcut_values[i]) {
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(radio), TRUE);
        }

        g_signal_connect(radio, "toggled", G_CALLBACK(on_settings_changed), NULL);
        gtk_box_pack_start(GTK_BOX(shortcut_box), radio, FALSE, FALSE, 0);
    }
    
    gtk_container_add(GTK_CONTAINER(shortcut_frame), shortcut_box);
    gtk_box_pack_start(GTK_BOX(vbox), shortcut_frame, FALSE, FALSE, 0);

    // Add the vbox to the notebook
    GtkWidget* settings_tab_label = gtk_label_new("Settings");
    gtk_widget_set_halign(settings_tab_label, GTK_ALIGN_CENTER);
    gtk_notebook_append_page(GTK_NOTEBOOK(notebook), vbox, settings_tab_label);
}

static void create_about_page(GtkWidget* notebook, GtkCssProvider* css_provider) {
    GtkWidget* vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 15);
    gtk_widget_set_margin_start(vbox, 30);
    gtk_widget_set_margin_end(vbox, 30);
    gtk_widget_set_margin_top(vbox, 30);
    gtk_widget_set_margin_bottom(vbox, 30);
    gtk_widget_set_valign(vbox, GTK_ALIGN_START);

    // Apply dark background
    GtkStyleContext* vbox_ctx = gtk_widget_get_style_context(vbox);
    gtk_style_context_add_provider(vbox_ctx,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(vbox_ctx, "content-area");

    // App name
    GtkWidget* title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(title),
        "<span size='xx-large' weight='bold' foreground='#e0e0e0'>LinScreenCapture</span>");
    gtk_widget_set_halign(title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(vbox), title, FALSE, FALSE, 0);

    // Version
    GtkWidget* version = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(version),
        "<span size='large' foreground='#aaaaaa'>Version 1.4.0 Beta</span>");
    gtk_widget_set_halign(version, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(vbox), version, FALSE, FALSE, 0);

    // Separator
    GtkWidget* sep = gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_box_pack_start(GTK_BOX(vbox), sep, FALSE, FALSE, 5);

    // Description
    GtkWidget* desc = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(desc),
        "<span foreground='#cccccc'>"
        "LinScreenCapture is a modern, open-source screenshot tool built for Linux Debian-based systems.\n\n"
        "Capture screenshots with real-time area selection, annotate with lines, arrows,\n"
        "rectangles, circles, text, borders, and freehand drawing. Blur regions to redact\n"
        "sensitive content. Use the marquee tool to select and copy regions, paste multiple\n"
        "images with drag-to-position, and flatten all changes into the image.\n\n"
        "Per-tool color, width, and shadow settings with universal apply option.\n"
        "Configurable keyboard shortcuts, system tray, and persistent settings."
        "</span>");
    gtk_label_set_line_wrap(GTK_LABEL(desc), TRUE);
    gtk_widget_set_halign(desc, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(vbox), desc, FALSE, FALSE, 0);

    // Details
    GtkWidget* details = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(details),
        "<span foreground='#999999'>"
        "<b>Created:</b>  January 2025\n"
        "<b>Status:</b>    Beta - undergoing continual updates and improvements\n"
        "<b>License:</b>   Open Source (CC BY-NC 4.0)\n"
        "<b>Platform:</b>  Linux (Debian, Ubuntu, Mint, and derivatives)\n"
        "<b>Toolkit:</b>    GTK 3 + Cairo + X11\n"
        "<b>Source:</b>    github.com/MensuraMedia/linscreencapture"
        "</span>");
    gtk_label_set_line_wrap(GTK_LABEL(details), TRUE);
    gtk_widget_set_halign(details, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(vbox), details, FALSE, FALSE, 10);

    // Footer
    GtkWidget* footer = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(footer),
        "<span foreground='#666666' size='small'>"
        "LinScreenCapture is currently in Beta and is undergoing continual updates.\n"
        "Free for education, research, and personal projects.\n"
        "Commercial use requires explicit permission."
        "</span>");
    gtk_widget_set_halign(footer, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(vbox), footer, FALSE, FALSE, 0);

    // Add to notebook
    GtkWidget* about_tab_label = gtk_label_new("About");
    gtk_widget_set_halign(about_tab_label, GTK_ALIGN_CENTER);
    gtk_notebook_append_page(GTK_NOTEBOOK(notebook), vbox, about_tab_label);
}

// --- Colors tab ---

static const GdkRGBA palette_colors[12] = {
    {1.0, 0.0, 0.0, 1.0},    {1.0, 0.5, 0.0, 1.0},    {1.0, 1.0, 0.0, 1.0},
    {0.0, 0.8, 0.0, 1.0},    {0.0, 0.5, 1.0, 1.0},    {0.6, 0.0, 1.0, 1.0},
    {1.0, 1.0, 1.0, 1.0},    {0.75, 0.75, 0.75, 1.0},  {0.5, 0.5, 0.5, 1.0},
    {0.0, 0.0, 0.0, 1.0},    {0.6, 0.2, 0.0, 1.0},    {1.0, 0.4, 0.7, 1.0},
};

static gboolean on_palette_draw(GtkWidget* widget, cairo_t* cr, gpointer data) {
    (void)data;
    int ci = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "palette-idx"));
    const GdkRGBA* c = &palette_colors[ci];

    double cx = 9.0, cy = 9.0, radius = 7.5;

    // Filled circle
    cairo_arc(cr, cx, cy, radius, 0, 2 * M_PI);
    cairo_set_source_rgba(cr, c->red, c->green, c->blue, c->alpha);
    cairo_fill(cr);

    // Selection indicator: soft glow instead of hard outline
    gboolean selected = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "is-selected"));
    if (selected) {
        // Multi-layer glow rings (outer to inner, fading)
        for (int g = 4; g >= 1; g--) {
            cairo_arc(cr, cx, cy, radius + g * 1.2, 0, 2 * M_PI);
            cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.15 / g);
            cairo_set_line_width(cr, 1.5);
            cairo_stroke(cr);
        }
        // Inner bright ring
        cairo_arc(cr, cx, cy, radius + 0.5, 0, 2 * M_PI);
        cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.7);
        cairo_set_line_width(cr, 1.5);
        cairo_stroke(cr);
    } else {
        // Subtle border
        cairo_arc(cr, cx, cy, radius, 0, 2 * M_PI);
        cairo_set_source_rgba(cr, 0.35, 0.35, 0.35, 0.5);
        cairo_set_line_width(cr, 0.8);
        cairo_stroke(cr);
    }
    return FALSE;
}

typedef struct {
    MainWindow* win;
    int tool_color_idx;  // 0=arrow,1=box,2=circle,3=text
    int palette_idx;     // index into palette_colors
    GtkWidget* grid;     // the grid to refresh check marks
} PaletteClickData;

static void update_palette_checks(GtkWidget* grid, int tool_color_idx, MainWindow* win) {
    Settings* settings = safe_get_data(win->window, "settings", "update_palette_checks");
    if (!settings) return;
    GdkRGBA* cur = &settings->tool_colors[tool_color_idx];
    GList* children = gtk_container_get_children(GTK_CONTAINER(grid));
    for (GList* l = children; l; l = l->next) {
        GtkWidget* child = GTK_WIDGET(l->data);
        int ci = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(child), "palette-idx"));
        const GdkRGBA* pc = &palette_colors[ci];
        gboolean match = (fabs(pc->red - cur->red) < 0.01 &&
                          fabs(pc->green - cur->green) < 0.01 &&
                          fabs(pc->blue - cur->blue) < 0.01);
        g_object_set_data(G_OBJECT(child), "is-selected", GINT_TO_POINTER(match));
        gtk_widget_queue_draw(child);
    }
    g_list_free(children);
}

static void on_palette_color_clicked(GtkWidget* widget, GdkEventButton* event, gpointer data) {
    (void)widget; (void)event;
    PaletteClickData* pcd = (PaletteClickData*)data;
    Settings* settings = safe_get_data(pcd->win->window, "settings", "on_palette_color_clicked");
    if (!settings) return;
    settings->tool_colors[pcd->tool_color_idx] = palette_colors[pcd->palette_idx];
    save_settings(settings);

    // Update active tool color if matching
    MainWindowData* win_data = safe_get_data(pcd->win->window, "window-data", "on_palette_color_clicked");
    if (win_data) {
        ToolType types[] = {TOOL_ARROW, TOOL_RECTANGLE, TOOL_ELLIPSE, TOOL_TEXT};
        if (win_data->current_tool.type == types[pcd->tool_color_idx]) {
            win_data->current_tool.color = palette_colors[pcd->palette_idx];
        }
    }

    update_palette_checks(pcd->grid, pcd->tool_color_idx, pcd->win);
}

static GtkWidget* create_tool_color_section(const char* tool_name, int tool_color_idx,
                                             MainWindow* win, GList** alloc_list) {
    GtkWidget* frame = gtk_frame_new(tool_name);
    GtkWidget* grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(grid), 3);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 3);
    gtk_container_set_border_width(GTK_CONTAINER(grid), 8);
    gtk_container_add(GTK_CONTAINER(frame), grid);

    for (int i = 0; i < 12; i++) {
        GtkWidget* swatch = gtk_drawing_area_new();
        gtk_widget_set_size_request(swatch, 18, 18);
        gtk_widget_add_events(swatch, GDK_BUTTON_PRESS_MASK);
        g_object_set_data(G_OBJECT(swatch), "palette-idx", GINT_TO_POINTER(i));
        g_object_set_data(G_OBJECT(swatch), "is-selected", GINT_TO_POINTER(0));
        g_signal_connect(swatch, "draw", G_CALLBACK(on_palette_draw), NULL);

        PaletteClickData* pcd = g_new0(PaletteClickData, 1);
        pcd->win = win;
        pcd->tool_color_idx = tool_color_idx;
        pcd->palette_idx = i;
        pcd->grid = grid;
        *alloc_list = g_list_append(*alloc_list, pcd);

        g_signal_connect(swatch, "button-press-event", G_CALLBACK(on_palette_color_clicked), pcd);
        gtk_grid_attach(GTK_GRID(grid), swatch, i % 6, i / 6, 1, 1);
    }

    // Set initial check marks
    update_palette_checks(grid, tool_color_idx, win);

    // Store grid reference on the window so universal callback can refresh it
    char grid_key[32];
    snprintf(grid_key, sizeof(grid_key), "palette-grid-%d", tool_color_idx);
    safe_set_data(win->window, grid_key, grid, "create_tool_color_section");

    return frame;
}

static void on_shadow_toggled(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_shadow_toggled");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_shadow_toggled");
    if (!settings) return;
    int idx = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "shadow-idx"));
    settings->tool_shadow[idx] = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
    save_settings(settings);
    if (win_data) {
        ToolType types[] = {TOOL_ARROW, TOOL_RECTANGLE, TOOL_ELLIPSE, TOOL_TEXT, TOOL_LINE, TOOL_BORDER};
        if (win_data->current_tool.type == types[idx]) {
            win_data->current_tool.shadow = settings->tool_shadow[idx];
        }
    }
}

static void on_shadow_intensity_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_shadow_intensity_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_shadow_intensity_changed");
    if (!settings) return;
    int idx = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "shadow-idx"));
    settings->tool_shadow_intensity[idx] = gtk_range_get_value(GTK_RANGE(widget));
    save_settings(settings);
    if (win_data) {
        ToolType types[] = {TOOL_ARROW, TOOL_RECTANGLE, TOOL_ELLIPSE, TOOL_TEXT, TOOL_LINE, TOOL_BORDER};
        if (win_data->current_tool.type == types[idx]) {
            win_data->current_tool.shadow_intensity = settings->tool_shadow_intensity[idx];
        }
    }
}

static void on_universal_check_toggled(GtkWidget* widget, gpointer data) {
    (void)data;
    GtkWidget* controls = g_object_get_data(G_OBJECT(widget), "uni-controls");
    if (controls) {
        gtk_widget_set_sensitive(controls,
            gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget)));
    }
}

static void on_blur_size_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_blur_size_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_blur_size_changed");
    if (!settings) return;
    settings->blur_block_size = (int)gtk_range_get_value(GTK_RANGE(widget));
    save_settings(settings);
    if (win_data && win_data->current_tool.type == TOOL_BLUR) {
        win_data->current_tool.blur_block_size = settings->blur_block_size;
    }
}

static void on_tool_width_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_tool_width_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_tool_width_changed");
    if (!settings) return;

    int width_idx = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(widget), "width-idx"));
    double val = gtk_spin_button_get_value(GTK_SPIN_BUTTON(widget));
    settings->tool_widths[width_idx] = val;
    save_settings(settings);

    // Update active tool if matching
    if (win_data) {
        ToolType types[] = {TOOL_ARROW, TOOL_RECTANGLE, TOOL_ELLIPSE, TOOL_LINE};
        if (win_data->current_tool.type == types[width_idx]) {
            win_data->current_tool.line_width = val;
        }
    }
}

static void on_text_font_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_text_font_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_text_font_changed");
    if (!settings) return;

    const char* key = g_object_get_data(G_OBJECT(widget), "font-key");
    if (!key) return;

    if (g_strcmp0(key, "family") == 0) {
        g_free(settings->text_font_family);
        char* active = gtk_combo_box_text_get_active_text(GTK_COMBO_BOX_TEXT(widget));
        settings->text_font_family = active ? active : g_strdup("Arial");
        if (win_data) {
            g_free(win_data->current_tool.font.family);
            win_data->current_tool.font.family = g_strdup(settings->text_font_family);
        }
    } else if (g_strcmp0(key, "size") == 0) {
        settings->text_font_size = gtk_spin_button_get_value(GTK_SPIN_BUTTON(widget));
        if (win_data) win_data->current_tool.font.size = settings->text_font_size;
    } else if (g_strcmp0(key, "bold") == 0) {
        settings->text_font_bold = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
        if (win_data) win_data->current_tool.font.is_bold = settings->text_font_bold;
    } else if (g_strcmp0(key, "italic") == 0) {
        settings->text_font_italic = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
        if (win_data) win_data->current_tool.font.is_italic = settings->text_font_italic;
    }

    save_settings(settings);

    // Update sample text label if it exists
    GtkWidget* sample = safe_get_data(win->window, "sample-text-label", "on_text_font_changed");
    if (sample && GTK_IS_LABEL(sample)) {
        const char* fam = settings->text_font_family ? settings->text_font_family : "Arial";
        int sz = (int)settings->text_font_size;
        if (sz > 18) sz = 18;
        const char* weight = settings->text_font_bold ? "bold" : "normal";
        const char* style = settings->text_font_italic ? "italic" : "normal";
        // Show shadow as a subtle background color on the text
        const char* fg = settings->tool_shadow[3] ? "#bbbbbb" : "#cccccc";
        const char* bg_attr = settings->tool_shadow[3] ? " background='#1a1a1a'" : "";
        char markup[512];
        snprintf(markup, sizeof(markup),
            "<span font_family='%s' font_size='%dpt' font_weight='%s' font_style='%s' foreground='%s'%s>"
            "Sample Text\n0123456789</span>", fam, sz, weight, style, fg, bg_attr);
        gtk_label_set_markup(GTK_LABEL(sample), markup);
    }
}

// Helper: create a bold label
static GtkWidget* create_bold_label(const char* text) {
    GtkWidget* label = gtk_label_new(NULL);
    char* markup = g_markup_printf_escaped("<b>%s</b>", text);
    gtk_label_set_markup(GTK_LABEL(label), markup);
    g_free(markup);
    gtk_widget_set_halign(label, GTK_ALIGN_START);
    return label;
}

// Refresh all stored tool palette grids after universal color change
static void refresh_all_tool_palettes(MainWindow* win) {
    // tool_color indices: 0=arrow, 1=box, 2=circle, 3=text, 4=line, 5=border
    const char* grid_keys[] = {
        "palette-grid-0", "palette-grid-1", "palette-grid-2",
        "palette-grid-3", "palette-grid-4", "palette-grid-5"
    };
    for (int i = 0; i < 6; i++) {
        GtkWidget* grid = safe_get_data(win->window, grid_keys[i], "refresh_all_tool_palettes");
        if (grid && GTK_IS_WIDGET(grid)) {
            update_palette_checks(grid, i, win);
        }
    }
}

// Refresh all individual tool section widgets from current Settings
static void refresh_all_tool_widgets(MainWindow* win) {
    Settings* settings = safe_get_data(win->window, "settings", "refresh_all_tool_widgets");
    if (!settings) return;

    // Refresh width spinbuttons (indices 0-4: arrow, box, circle, line, border)
    for (int i = 0; i < 5; i++) {
        char wkey[32];
        snprintf(wkey, sizeof(wkey), "tool-width-spin-%d", i);
        GtkWidget* spin = safe_get_data(win->window, wkey, "refresh_all_tool_widgets");
        if (spin && GTK_IS_SPIN_BUTTON(spin)) {
            g_signal_handlers_block_by_func(spin, G_CALLBACK(on_tool_width_changed), win);
            gtk_spin_button_set_value(GTK_SPIN_BUTTON(spin), settings->tool_widths[i]);
            g_signal_handlers_unblock_by_func(spin, G_CALLBACK(on_tool_width_changed), win);
        }
    }

    // Refresh shadow checkboxes (indices 0-5: arrow, box, circle, text, line, border)
    for (int i = 0; i < 6; i++) {
        char skey[32];
        snprintf(skey, sizeof(skey), "tool-shadow-check-%d", i);
        GtkWidget* check = safe_get_data(win->window, skey, "refresh_all_tool_widgets");
        if (check && GTK_IS_TOGGLE_BUTTON(check)) {
            g_signal_handlers_block_by_func(check, G_CALLBACK(on_shadow_toggled), win);
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(check), settings->tool_shadow[i]);
            g_signal_handlers_unblock_by_func(check, G_CALLBACK(on_shadow_toggled), win);
        }

        // Refresh shadow intensity scales
        char ikey[32];
        snprintf(ikey, sizeof(ikey), "tool-shadow-scale-%d", i);
        GtkWidget* scale = safe_get_data(win->window, ikey, "refresh_all_tool_widgets");
        if (scale && GTK_IS_RANGE(scale)) {
            g_signal_handlers_block_by_func(scale, G_CALLBACK(on_shadow_intensity_changed), win);
            gtk_range_set_value(GTK_RANGE(scale), settings->tool_shadow_intensity[i]);
            g_signal_handlers_unblock_by_func(scale, G_CALLBACK(on_shadow_intensity_changed), win);
        }
    }

    // Refresh all color palette grids
    refresh_all_tool_palettes(win);
}

// Callback: Universal Settings apply to all tools
static void on_universal_color_clicked(GtkWidget* widget, GdkEventButton* event, gpointer data) {
    (void)widget; (void)event;
    PaletteClickData* pcd = (PaletteClickData*)data;
    Settings* settings = safe_get_data(pcd->win->window, "settings", "on_universal_color_clicked");
    if (!settings) return;
    // Apply to all 6 tool colors
    for (int i = 0; i < 6; i++) {
        settings->tool_colors[i] = palette_colors[pcd->palette_idx];
    }
    save_settings(settings);
    MainWindowData* win_data = safe_get_data(pcd->win->window, "window-data", "on_universal_color_clicked");
    if (win_data) {
        win_data->current_tool.color = palette_colors[pcd->palette_idx];
    }
    // Refresh the universal palette check marks (use index 0 for matching since all are the same now)
    update_palette_checks(pcd->grid, 0, pcd->win);
    // Refresh ALL individual tool widgets (colors, widths, shadows)
    refresh_all_tool_widgets(pcd->win);
}

static void on_universal_width_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_universal_width_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_universal_width_changed");
    if (!settings) return;
    double val = gtk_spin_button_get_value(GTK_SPIN_BUTTON(widget));
    for (int i = 0; i < 5; i++) settings->tool_widths[i] = val;
    save_settings(settings);
    if (win_data) win_data->current_tool.line_width = val;
    refresh_all_tool_widgets(win);
}

static void on_universal_shadow_toggled(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_universal_shadow_toggled");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_universal_shadow_toggled");
    if (!settings) return;
    gboolean active = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
    for (int i = 0; i < 6; i++) settings->tool_shadow[i] = active;
    save_settings(settings);
    if (win_data) win_data->current_tool.shadow = active;
    refresh_all_tool_widgets(win);
}

static void on_universal_shadow_intensity_changed(GtkWidget* widget, gpointer data) {
    MainWindow* win = (MainWindow*)data;
    Settings* settings = safe_get_data(win->window, "settings", "on_universal_shadow_intensity_changed");
    MainWindowData* win_data = safe_get_data(win->window, "window-data", "on_universal_shadow_intensity_changed");
    if (!settings) return;
    double val = gtk_range_get_value(GTK_RANGE(widget));
    for (int i = 0; i < 6; i++) settings->tool_shadow_intensity[i] = val;
    save_settings(settings);
    if (win_data) win_data->current_tool.shadow_intensity = val;
    refresh_all_tool_widgets(win);
}

// Helper: create a tool section (color circles + width + shadow) in compact form
static GtkWidget* create_tool_section(const char* name, int color_idx, int width_idx,
                                       int shadow_idx, MainWindow* win, GList** alloc_list) {
    Settings* settings = safe_get_data(win->window, "settings", "create_tool_section");

    GtkWidget* section = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
    gtk_widget_set_margin_bottom(section, 14);

    // Bold title
    gtk_box_pack_start(GTK_BOX(section), create_bold_label(name), FALSE, FALSE, 2);

    // Color circles row
    GtkWidget* color_section = create_tool_color_section(NULL, color_idx, win, alloc_list);
    GtkWidget* inner = gtk_bin_get_child(GTK_BIN(color_section));
    g_object_ref(inner);
    gtk_container_remove(GTK_CONTAINER(color_section), inner);
    gtk_box_pack_start(GTK_BOX(section), inner, FALSE, FALSE, 0);
    g_object_unref(inner);
    gtk_widget_destroy(color_section);

    // Width + Shadow + Intensity all on one row
    if (width_idx >= 0) {
        GtkWidget* opts_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);

        // Width
        GtkWidget* wlabel = gtk_label_new("Width:");
        GtkWidget* wspin = gtk_spin_button_new_with_range(1, 10, 0.5);
        gtk_spin_button_set_value(GTK_SPIN_BUTTON(wspin), settings ? settings->tool_widths[width_idx] : 2.0);
        g_object_set_data(G_OBJECT(wspin), "width-idx", GINT_TO_POINTER(width_idx));
        g_signal_connect(wspin, "value-changed", G_CALLBACK(on_tool_width_changed), win);
        gtk_box_pack_start(GTK_BOX(opts_row), wlabel, FALSE, FALSE, 0);
        gtk_box_pack_start(GTK_BOX(opts_row), wspin, FALSE, FALSE, 0);

        // Store widget reference for universal refresh
        char wkey[32];
        snprintf(wkey, sizeof(wkey), "tool-width-spin-%d", width_idx);
        safe_set_data(win->window, wkey, wspin, "create_tool_section");

        // Shadow toggle + intensity slider on same row
        GtkWidget* shadow_check = gtk_check_button_new_with_label("Shadow");
        gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(shadow_check),
                                     settings ? settings->tool_shadow[shadow_idx] : false);
        g_object_set_data(G_OBJECT(shadow_check), "shadow-idx", GINT_TO_POINTER(shadow_idx));
        g_signal_connect(shadow_check, "toggled", G_CALLBACK(on_shadow_toggled), win);
        gtk_box_pack_start(GTK_BOX(opts_row), shadow_check, FALSE, FALSE, 4);

        // Store shadow check reference
        char skey[32];
        snprintf(skey, sizeof(skey), "tool-shadow-check-%d", shadow_idx);
        safe_set_data(win->window, skey, shadow_check, "create_tool_section");

        GtkWidget* int_scale = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, 0.1, 1.0, 0.1);
        gtk_scale_set_draw_value(GTK_SCALE(int_scale), FALSE);
        gtk_widget_set_size_request(int_scale, 70, -1);
        gtk_range_set_value(GTK_RANGE(int_scale),
                            settings ? settings->tool_shadow_intensity[shadow_idx] : 0.4);
        g_object_set_data(G_OBJECT(int_scale), "shadow-idx", GINT_TO_POINTER(shadow_idx));
        g_signal_connect(int_scale, "value-changed", G_CALLBACK(on_shadow_intensity_changed), win);

        // Store shadow scale reference
        char ikey[32];
        snprintf(ikey, sizeof(ikey), "tool-shadow-scale-%d", shadow_idx);
        safe_set_data(win->window, ikey, int_scale, "create_tool_section");
        gtk_box_pack_start(GTK_BOX(opts_row), int_scale, TRUE, TRUE, 0);

        gtk_box_pack_start(GTK_BOX(section), opts_row, FALSE, FALSE, 0);
    }

    return section;
}

static void create_colors_page(MainWindow* win, GtkWidget* notebook) {
    GtkWidget* scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),
                                   GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);

    GtkWidget* page_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_margin_start(page_box, 12);
    gtk_widget_set_margin_end(page_box, 12);
    gtk_widget_set_margin_top(page_box, 8);
    gtk_widget_set_margin_bottom(page_box, 8);
    gtk_container_add(GTK_CONTAINER(scroll), page_box);

    GList* alloc_list = NULL;
    Settings* settings = safe_get_data(win->window, "settings", "create_colors_page");

    // === Universal Setting (top, full width) ===
    GtkWidget* uni_sec = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3);
    gtk_widget_set_margin_bottom(uni_sec, 4);

    // Universal checkbox with bold label — enables/disables the universal controls
    GtkWidget* uni_header = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* uni_check = gtk_check_button_new();
    GtkWidget* uni_title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(uni_title), "<b>Universal Setting</b>");
    gtk_box_pack_start(GTK_BOX(uni_header), uni_check, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(uni_header), uni_title, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(uni_sec), uni_header, FALSE, FALSE, 0);

    GtkWidget* uni_desc = gtk_label_new("Enable to apply settings to all tools at once");
    gtk_widget_set_halign(uni_desc, GTK_ALIGN_START);
    gtk_widget_set_opacity(uni_desc, 0.5);
    gtk_widget_set_margin_start(uni_desc, 24);
    gtk_box_pack_start(GTK_BOX(uni_sec), uni_desc, FALSE, FALSE, 0);

    // Wrap universal controls in a container toggled by checkbox
    GtkWidget* uni_controls = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3);
    gtk_widget_set_sensitive(uni_controls, FALSE);
    g_object_set_data(G_OBJECT(uni_check), "uni-controls", uni_controls);
    g_signal_connect(uni_check, "toggled", G_CALLBACK(on_universal_check_toggled), NULL);

    // Use index 99 so it doesn't overwrite any real tool grid (0-5)
    GtkWidget* uni_color = create_tool_color_section(NULL, 99, win, &alloc_list);
    GtkWidget* uni_inner = gtk_bin_get_child(GTK_BIN(uni_color));
    g_object_ref(uni_inner);
    gtk_container_remove(GTK_CONTAINER(uni_color), uni_inner);
    GList* uni_children = gtk_container_get_children(GTK_CONTAINER(uni_inner));
    for (GList* l = uni_children; l; l = l->next) {
        GtkWidget* child = GTK_WIDGET(l->data);
        int ci = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(child), "palette-idx"));
        PaletteClickData* upcd = g_new0(PaletteClickData, 1);
        upcd->win = win; upcd->tool_color_idx = 99; upcd->palette_idx = ci; upcd->grid = uni_inner;
        alloc_list = g_list_append(alloc_list, upcd);
        // Disconnect ALL handlers for on_palette_color_clicked regardless of data
        guint n = g_signal_handlers_disconnect_matched(child,
            G_SIGNAL_MATCH_FUNC, 0, 0, NULL, G_CALLBACK(on_palette_color_clicked), NULL);
        (void)n;
        g_signal_connect(child, "button-press-event", G_CALLBACK(on_universal_color_clicked), upcd);
    }
    g_list_free(uni_children);
    gtk_box_pack_start(GTK_BOX(uni_controls), uni_inner, FALSE, FALSE, 0);
    g_object_unref(uni_inner);
    gtk_widget_destroy(uni_color);

    GtkWidget* uni_opts = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* uwl = gtk_label_new("Width:");
    GtkWidget* uws = gtk_spin_button_new_with_range(1, 10, 0.5);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(uws), settings ? settings->tool_widths[0] : 2.0);
    g_signal_connect(uws, "value-changed", G_CALLBACK(on_universal_width_changed), win);
    GtkWidget* usc = gtk_check_button_new_with_label("Shadow");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(usc), settings ? settings->tool_shadow[0] : false);
    g_signal_connect(usc, "toggled", G_CALLBACK(on_universal_shadow_toggled), win);
    GtkWidget* usl = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, 0.1, 1.0, 0.1);
    gtk_scale_set_draw_value(GTK_SCALE(usl), FALSE);
    gtk_widget_set_size_request(usl, 60, -1);
    gtk_range_set_value(GTK_RANGE(usl), settings ? settings->tool_shadow_intensity[0] : 0.4);
    g_signal_connect(usl, "value-changed", G_CALLBACK(on_universal_shadow_intensity_changed), win);
    gtk_box_pack_start(GTK_BOX(uni_opts), uwl, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(uni_opts), uws, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(uni_opts), usc, FALSE, FALSE, 4);
    gtk_box_pack_start(GTK_BOX(uni_opts), usl, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(uni_controls), uni_opts, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(uni_sec), uni_controls, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(page_box), uni_sec, FALSE, FALSE, 0);

    // Separator
    GtkWidget* sep = gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_widget_set_margin_top(sep, 4);
    gtk_widget_set_margin_bottom(sep, 8);
    gtk_box_pack_start(GTK_BOX(page_box), sep, FALSE, FALSE, 0);

    // === 3x3 tool settings grid ===
    GtkWidget* tools_grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(tools_grid), 10);
    gtk_grid_set_column_spacing(GTK_GRID(tools_grid), 16);
    gtk_grid_set_column_homogeneous(GTK_GRID(tools_grid), TRUE);

    // Row 0: Line, Arrow, Box
    gtk_grid_attach(GTK_GRID(tools_grid), create_tool_section("Line",   4, 3, 4, win, &alloc_list), 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(tools_grid), create_tool_section("Arrow",  0, 0, 0, win, &alloc_list), 1, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(tools_grid), create_tool_section("Box",    1, 1, 1, win, &alloc_list), 2, 0, 1, 1);

    // Row 1: Circle, Border, Blur
    gtk_grid_attach(GTK_GRID(tools_grid), create_tool_section("Circle", 2, 2, 2, win, &alloc_list), 0, 1, 1, 1);
    gtk_grid_attach(GTK_GRID(tools_grid), create_tool_section("Border", 5, 4, 5, win, &alloc_list), 1, 1, 1, 1);

    // Blur section (special — has block size instead of width)
    GtkWidget* blur_sec = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3);
    gtk_widget_set_margin_bottom(blur_sec, 14);
    gtk_box_pack_start(GTK_BOX(blur_sec), create_bold_label("Blur"), FALSE, FALSE, 0);
    GtkWidget* blur_desc = gtk_label_new("Pixelate region");
    gtk_widget_set_halign(blur_desc, GTK_ALIGN_START);
    gtk_widget_set_opacity(blur_desc, 0.5);
    gtk_box_pack_start(GTK_BOX(blur_sec), blur_desc, FALSE, FALSE, 0);
    GtkWidget* blur_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* blur_label = gtk_label_new("Intensity:");
    GtkWidget* blur_scale = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, 4, 32, 2);
    gtk_scale_set_draw_value(GTK_SCALE(blur_scale), TRUE);
    gtk_widget_set_size_request(blur_scale, 80, -1);
    gtk_range_set_value(GTK_RANGE(blur_scale), settings ? settings->blur_block_size : 10);
    g_signal_connect(blur_scale, "value-changed", G_CALLBACK(on_blur_size_changed), win);
    gtk_box_pack_start(GTK_BOX(blur_row), blur_label, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(blur_row), blur_scale, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(blur_sec), blur_row, FALSE, FALSE, 0);
    gtk_grid_attach(GTK_GRID(tools_grid), blur_sec, 2, 1, 1, 1);

    gtk_box_pack_start(GTK_BOX(page_box), tools_grid, FALSE, FALSE, 0);

    // === Text section (full width, below grid) ===
    GtkWidget* sep2 = gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_widget_set_margin_top(sep2, 6);
    gtk_widget_set_margin_bottom(sep2, 10);
    gtk_box_pack_start(GTK_BOX(page_box), sep2, FALSE, FALSE, 0);

    GtkWidget* text_sec = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_box_pack_start(GTK_BOX(text_sec), create_bold_label("Text"), FALSE, FALSE, 2);

    // Row 1: Color circles
    GtkWidget* tc = create_tool_color_section(NULL, 3, win, &alloc_list);
    GtkWidget* tci = gtk_bin_get_child(GTK_BIN(tc));
    g_object_ref(tci); gtk_container_remove(GTK_CONTAINER(tc), tci);
    gtk_box_pack_start(GTK_BOX(text_sec), tci, FALSE, FALSE, 2);
    g_object_unref(tci); gtk_widget_destroy(tc);

    // Row 2: Font family
    GtkWidget* fr = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* fl = gtk_label_new("Font:");
    GtkWidget* fc = gtk_combo_box_text_new();
    const char* font_list[] = {
        "Arial", "Helvetica", "Sans", "Verdana", "Tahoma",
        "Times New Roman", "Serif", "Georgia",
        "Courier New", "Monospace", "Consolas",
        "Impact", "Comic Sans MS", "Trebuchet MS",
        "Ubuntu", "Noto Sans", "DejaVu Sans", "Liberation Sans"
    };
    int ai = 0;
    const char* cf = settings ? settings->text_font_family : "Arial";
    for (int fi = 0; fi < 18; fi++) {
        gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(fc), font_list[fi]);
        if (g_ascii_strcasecmp(font_list[fi], cf) == 0) ai = fi;
    }
    gtk_combo_box_set_active(GTK_COMBO_BOX(fc), ai);
    g_object_set_data(G_OBJECT(fc), "font-key", (gpointer)"family");
    g_signal_connect(fc, "changed", G_CALLBACK(on_text_font_changed), win);
    gtk_widget_set_size_request(fc, 160, -1);
    gtk_box_pack_start(GTK_BOX(fr), fl, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(fr), fc, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(text_sec), fr, FALSE, FALSE, 2);

    // Row 3: Size + B + I
    GtkWidget* sr = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* sll = gtk_label_new("Size:");
    GtkWidget* ss = gtk_spin_button_new_with_range(6, 72, 1);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(ss), settings ? settings->text_font_size : 15.0);
    g_object_set_data(G_OBJECT(ss), "font-key", (gpointer)"size");
    g_signal_connect(ss, "value-changed", G_CALLBACK(on_text_font_changed), win);
    GtkWidget* bcc = gtk_check_button_new_with_label("B");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(bcc), settings ? settings->text_font_bold : true);
    g_object_set_data(G_OBJECT(bcc), "font-key", (gpointer)"bold");
    g_signal_connect(bcc, "toggled", G_CALLBACK(on_text_font_changed), win);
    GtkWidget* icc = gtk_check_button_new_with_label("I");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(icc), settings ? settings->text_font_italic : false);
    g_object_set_data(G_OBJECT(icc), "font-key", (gpointer)"italic");
    g_signal_connect(icc, "toggled", G_CALLBACK(on_text_font_changed), win);
    gtk_box_pack_start(GTK_BOX(sr), sll, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(sr), ss, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(sr), bcc, FALSE, FALSE, 4);
    gtk_box_pack_start(GTK_BOX(sr), icc, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(text_sec), sr, FALSE, FALSE, 2);

    // Row 4: Shadow + intensity slider
    GtkWidget* tsr = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkWidget* tsc2 = gtk_check_button_new_with_label("Shadow");
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(tsc2), settings ? settings->tool_shadow[3] : false);
    g_object_set_data(G_OBJECT(tsc2), "shadow-idx", GINT_TO_POINTER(3));
    g_signal_connect(tsc2, "toggled", G_CALLBACK(on_shadow_toggled), win);
    g_signal_connect(tsc2, "toggled", G_CALLBACK(on_text_font_changed), win);
    g_object_set_data(G_OBJECT(tsc2), "font-key", (gpointer)"shadow-refresh");
    safe_set_data(win->window, "tool-shadow-check-3", tsc2, "create_colors_page");
    GtkWidget* tss = gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL, 0.1, 1.0, 0.1);
    gtk_scale_set_draw_value(GTK_SCALE(tss), FALSE);
    gtk_widget_set_size_request(tss, 80, -1);
    gtk_range_set_value(GTK_RANGE(tss), settings ? settings->tool_shadow_intensity[3] : 0.4);
    g_object_set_data(G_OBJECT(tss), "shadow-idx", GINT_TO_POINTER(3));
    g_signal_connect(tss, "value-changed", G_CALLBACK(on_shadow_intensity_changed), win);
    safe_set_data(win->window, "tool-shadow-scale-3", tss, "create_colors_page");
    gtk_box_pack_start(GTK_BOX(tsr), tsc2, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(tsr), tss, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(text_sec), tsr, FALSE, FALSE, 2);

    // Row 5: Sample text preview (reflects font, size, bold, italic, shadow)
    GtkWidget* sample_label = gtk_label_new(NULL);
    {
        const char* sfam = settings ? settings->text_font_family : "Arial";
        int ssz = settings ? (int)settings->text_font_size : 15;
        const char* swt = (settings && settings->text_font_bold) ? "bold" : "normal";
        const char* sst = (settings && settings->text_font_italic) ? "italic" : "normal";
        char smarkup[512];
        snprintf(smarkup, sizeof(smarkup),
            "<span font_family='%s' font_size='%dpt' font_weight='%s' font_style='%s' foreground='#cccccc'>"
            "Sample Text\n0123456789</span>", sfam, ssz > 18 ? 18 : ssz, swt, sst);
        gtk_label_set_markup(GTK_LABEL(sample_label), smarkup);
    }
    gtk_widget_set_halign(sample_label, GTK_ALIGN_START);
    gtk_widget_set_margin_top(sample_label, 6);
    safe_set_data(win->window, "sample-text-label", sample_label, "create_colors_page");
    gtk_box_pack_start(GTK_BOX(text_sec), sample_label, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(page_box), text_sec, FALSE, FALSE, 0);

    GtkWidget* tools_tab_label = gtk_label_new("Tools");
    gtk_widget_set_halign(tools_tab_label, GTK_ALIGN_CENTER);
    gtk_notebook_append_page(GTK_NOTEBOOK(notebook), scroll, tools_tab_label);
}

static void register_shortcut_key(MainWindow* win, ShortcutKey key) {
    Settings* settings = safe_get_data(win->window, "settings", "register_shortcut_key");
    if (!settings) return;

    // Get the binary path
    char* binary_path = get_binary_path();

    // Unregister old, register new via DE-native method
    keybinding_unregister(settings->detected_de);
    keybinding_register(settings->detected_de, (KeyBinding)key, binary_path);

    // Only install X11 event filter for DEs that use XGrabKey fallback
    if (settings->detected_de == DE_UNKNOWN || settings->detected_de == DE_KDE) {
        GdkDisplay* display = gdk_display_get_default();
        GdkScreen* screen = gdk_display_get_default_screen(display);
        GdkWindow* root = gdk_screen_get_root_window(screen);
        gdk_window_add_filter(root, (GdkFilterFunc)key_filter_func, win);
    }

    g_free(binary_path);
}

static void destroy_widget(gpointer data, gpointer user_data) {
    (void)user_data;
    if (GTK_IS_WIDGET(data)) {
        gtk_widget_destroy(GTK_WIDGET(data));
    }
}

static void on_settings_changed(GtkWidget* widget, gpointer data) {
    (void)data;  // Mark unused parameter as used
    Settings* settings = safe_get_data(widget, "settings", "on_settings_changed");
    MainWindow* win = safe_get_data(widget, "window", "on_settings_changed");
    
    if (!settings || !win) {
        g_warning("Settings or window pointer not found in widget data");
        return;
    }

    // Handle path entry changes
    if (GTK_IS_ENTRY(widget)) {
        const char* new_path = gtk_entry_get_text(GTK_ENTRY(widget));
        if (g_strcmp0(settings->screenshot_path, new_path) != 0) {
            g_free(settings->screenshot_path);
            settings->screenshot_path = g_strdup(new_path);
            
            // Update screenshot history path and reload
            screenshot_history_set_path(&win->screenshot_history, new_path);
            screenshot_history_load(&win->screenshot_history);
            
            // Clear and update history items in the view
            GtkFlowBox* history_box = GTK_FLOW_BOX(win->history_flow_box);
            GList* children = gtk_container_get_children(GTK_CONTAINER(history_box));
            g_list_foreach(children, destroy_widget, NULL);
            g_list_free(children);
            
            GList* entries = screenshot_history_get_sorted(&win->screenshot_history);
            for (GList* l = entries; l != NULL; l = l->next) {
                ScreenshotEntry* entry = l->data;
                GtkWidget* item_widget = create_history_item_widget(entry, win);
                gtk_flow_box_insert(GTK_FLOW_BOX(history_box), item_widget, -1);
            }
        }
    }
    // Handle checkbox changes
    else if (GTK_IS_CHECK_BUTTON(widget)) {
        gpointer default_app_data = safe_get_data(widget, "default-app", "on_settings_changed");
        if (default_app_data) {
            settings->default_screenshot_app = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
            toggle_default_screenshot_app(settings->default_screenshot_app);
        } else {
            settings->start_with_os = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget));
            toggle_autostart(settings->start_with_os);
        }
    }
    // Handle radio button changes (filename format and shortcut keys)
    else if (GTK_IS_RADIO_BUTTON(widget) && gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget))) {
        gpointer format_data = safe_get_data(widget, "format", "on_settings_changed");
        gpointer shortcut_data = safe_get_data(widget, "shortcut", "on_settings_changed");
        
        if (format_data) {
            settings->filename_format = (FilenameFormat)GPOINTER_TO_INT(format_data);
        }
        else if (shortcut_data) {
            int new_shortcut = GPOINTER_TO_INT(shortcut_data);
            if (settings->shortcut_key != (ShortcutKey)new_shortcut) {
                settings->shortcut_key = (ShortcutKey)new_shortcut;
                // Apply immediately via DE-native keybinding manager
                register_shortcut_key(win, settings->shortcut_key);
                grab_printscreen_key(win, settings->shortcut_key);
            }
        }
    }
    
    save_settings(settings);
}

static void toggle_autostart(bool enable) {
    char* autostart_dir = g_build_filename(g_get_user_config_dir(), "autostart", NULL);
    char* desktop_file = g_build_filename(autostart_dir, "linscreencapture.desktop", NULL);
    
    if (enable) {
        // Create autostart directory if it doesn't exist
        g_mkdir_with_parents(autostart_dir, 0755);
        
        // Create desktop entry file
        FILE* file = fopen(desktop_file, "w");
        if (file) {
            fprintf(file, "[Desktop Entry]\n");
            fprintf(file, "Type=Application\n");
            fprintf(file, "Name=LinScreenCapture\n");
            char* bin_path = get_binary_path();
            fprintf(file, "Exec=%s\n", bin_path);
            g_free(bin_path);
            fprintf(file, "Hidden=false\n");
            fprintf(file, "NoDisplay=false\n");
            fprintf(file, "X-GNOME-Autostart-enabled=true\n");
            fclose(file);
        }
    } else {
        // Remove desktop entry file
        g_unlink(desktop_file);
    }
    
    g_free(desktop_file);
    g_free(autostart_dir);
}

static char* get_binary_path(void) {
    char buf[1024];
    ssize_t len = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (len > 0) {
        buf[len] = '\0';
        return g_strdup(buf);
    }
    return g_strdup("linscreencapture");
}

static void toggle_default_screenshot_app(bool enable) {
    char* apps_dir = g_build_filename(g_get_user_data_dir(), "applications", NULL);
    char* desktop_file = g_build_filename(apps_dir, "linscreencapture.desktop", NULL);
    char* binary_path = get_binary_path();

    if (enable) {
        g_mkdir_with_parents(apps_dir, 0755);

        // Create .desktop file for LinScreenCapture
        FILE* file = fopen(desktop_file, "w");
        if (file) {
            fprintf(file, "[Desktop Entry]\n");
            fprintf(file, "Version=1.4\n");
            fprintf(file, "Type=Application\n");
            fprintf(file, "Name=LinScreenCapture\n");
            fprintf(file, "GenericName=Screenshot Tool\n");
            fprintf(file, "Comment=Capture, annotate, and share screenshots\n");
            fprintf(file, "Exec=%s\n", binary_path);
            fprintf(file, "Icon=%s/resources/icons/linscreencapture-128.png\n", g_path_get_dirname(binary_path));
            fprintf(file, "Terminal=false\n");
            fprintf(file, "Categories=Utility;Graphics;GTK;\n");
            fprintf(file, "Keywords=screenshot;capture;screen;snip;annotation;\n");
            fprintf(file, "MimeType=image/png;image/jpeg;\n");
            fprintf(file, "StartupNotify=true\n");
            fclose(file);
        }

        char* update_cmd = g_strdup_printf("update-desktop-database %s 2>/dev/null", apps_dir);
        if (system(update_cmd) == -1) { /* ignored */ }
        g_free(update_cmd);

    } else {
        // Remove desktop file and unregister keybinding
        g_unlink(desktop_file);
        char* update_cmd = g_strdup_printf("update-desktop-database %s 2>/dev/null", apps_dir);
        if (system(update_cmd) == -1) { /* ignored */ }
        g_free(update_cmd);

        // Unregister via the DE-native method
        DesktopEnv de = detect_desktop_environment();
        keybinding_unregister(de);
    }

    g_free(binary_path);
    g_free(desktop_file);
    g_free(apps_dir);
}

static GdkFilterReturn key_filter_func(GdkXEvent* xevent, GdkEvent* event, gpointer data) {
    (void)event;
    MainWindow* win = (MainWindow*)data;
    XEvent* xe = (XEvent*)xevent;

    if (xe->type == KeyPress) {
        XKeyEvent* key_event = (XKeyEvent*)xe;
        KeySym key_sym = XLookupKeysym(key_event, 0);
        // Strip lock keys (NumLock=Mod2, CapsLock=Lock, ScrollLock=Mod5)
        unsigned int mods = key_event->state & ~(Mod2Mask | LockMask | Mod5Mask);
        Settings* settings = safe_get_data(win->window, "settings", "key_filter_func");
        if (!settings) return GDK_FILTER_CONTINUE;

        bool matched = false;
        switch (settings->shortcut_key) {
            case SHORTCUT_PRINTSCREEN:
                matched = (key_sym == XK_Print && mods == 0);
                break;
            case SHORTCUT_CTRL_PRINTSCREEN:
                matched = (key_sym == XK_Print && mods == ControlMask);
                break;
            case SHORTCUT_SHIFT_PRINTSCREEN:
                matched = (key_sym == XK_Print && mods == ShiftMask);
                break;
            case SHORTCUT_CTRL_SHIFT_S:
                matched = (key_sym == XK_s && mods == (ControlMask | ShiftMask));
                break;
            case SHORTCUT_CTRL_ALT_S:
                matched = (key_sym == XK_s && mods == (ControlMask | Mod1Mask));
                break;
            default:
                break;
        }

        if (matched) {
            on_capture_button_clicked(NULL, win);
            return GDK_FILTER_REMOVE;
        }
    }

    return GDK_FILTER_CONTINUE;
}

// --- System tray icon ---

static void on_tray_activate(GtkStatusIcon* icon, gpointer data) {
    (void)icon;
    MainWindow* win = (MainWindow*)data;
    if (gtk_widget_get_visible(win->window)) {
        gtk_widget_hide(win->window);
    } else {
        gtk_widget_show(win->window);
        gtk_window_present(GTK_WINDOW(win->window));
    }
}

static void on_tray_capture(GtkMenuItem* item, gpointer data) {
    (void)item;
    MainWindow* win = (MainWindow*)data;
    main_window_trigger_capture(win);
}

static void on_tray_show(GtkMenuItem* item, gpointer data) {
    (void)item;
    MainWindow* win = (MainWindow*)data;
    gtk_widget_show(win->window);
    gtk_window_present(GTK_WINDOW(win->window));
}

static void on_tray_quit(GtkMenuItem* item, gpointer data) {
    (void)item;
    (void)data;
    gtk_main_quit();
}

// GtkStatusIcon is deprecated in GTK3 but is the only portable tray API available
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"

static void on_tray_popup(GtkStatusIcon* icon, guint button, guint activate_time, gpointer data) {
    (void)icon;
    MainWindow* win = (MainWindow*)data;
    GtkWidget* menu = gtk_menu_new();

    GtkWidget* capture_item = gtk_menu_item_new_with_label("Capture Screenshot");
    g_signal_connect(capture_item, "activate", G_CALLBACK(on_tray_capture), win);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), capture_item);

    GtkWidget* show_item = gtk_menu_item_new_with_label("Show LinScreenCapture");
    g_signal_connect(show_item, "activate", G_CALLBACK(on_tray_show), win);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), show_item);

    GtkWidget* sep = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), sep);

    GtkWidget* quit_item = gtk_menu_item_new_with_label("Quit");
    g_signal_connect(quit_item, "activate", G_CALLBACK(on_tray_quit), win);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), quit_item);

    gtk_widget_show_all(menu);

    // Anchor the menu to the status icon under the pointer. Passing the real
    // button/activate_time plus gtk_status_icon_position_menu positions the menu
    // at the icon the user right-clicked; popup_at_pointer(NULL) discarded the
    // trigger event and fell back to a wrong location away from the cursor.
    gtk_menu_popup(GTK_MENU(menu), NULL, NULL,
                   gtk_status_icon_position_menu, icon,
                   button, activate_time);
}

// Create the app icon (circle with dot) as a pixbuf at given size via Cairo
static GdkPixbuf* create_app_icon_pixbuf(int size, bool for_tray) {
    cairo_surface_t* surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
    cairo_t* cr = cairo_create(surface);

    double cx = size / 2.0;
    double cy = size / 2.0;
    double outer_r = size * 0.35;
    double inner_r = size * 0.10;
    double lw = size * 0.10;

    if (for_tray) {
        // Tray icon: dark circle background for visibility
        cairo_set_source_rgb(cr, 0.18, 0.18, 0.18);
        cairo_arc(cr, cx, cy, size * 0.46, 0, 2 * G_PI);
        cairo_fill(cr);
    }

    // Outer circle
    cairo_set_line_width(cr, lw);
    cairo_set_source_rgb(cr, 0.9, 0.9, 0.9);
    cairo_arc(cr, cx, cy, outer_r, 0, 2 * G_PI);
    cairo_stroke(cr);

    // Inner dot
    cairo_arc(cr, cx, cy, inner_r, 0, 2 * G_PI);
    cairo_fill(cr);

    cairo_destroy(cr);
    cairo_surface_flush(surface);

    GdkPixbuf* pb = gdk_pixbuf_get_from_surface(surface, 0, 0, size, size);
    cairo_surface_destroy(surface);
    return pb;
}

static void setup_tray_icon(MainWindow* win) {
    GdkPixbuf* tray_pb = create_app_icon_pixbuf(24, true);
    if (tray_pb) {
        win->tray_icon = gtk_status_icon_new_from_pixbuf(tray_pb);
        g_object_unref(tray_pb);
    } else {
        win->tray_icon = gtk_status_icon_new_from_icon_name("camera-photo");
    }
    gtk_status_icon_set_tooltip_text(win->tray_icon, "LinScreenCapture Screenshot Tool");
    gtk_status_icon_set_visible(win->tray_icon, TRUE);

    g_signal_connect(win->tray_icon, "activate", G_CALLBACK(on_tray_activate), win);
    g_signal_connect(win->tray_icon, "popup-menu", G_CALLBACK(on_tray_popup), win);
}

#pragma GCC diagnostic pop

// Intercept window close to minimize to tray instead of quitting
static gboolean on_delete_event(GtkWidget* widget, GdkEvent* event, gpointer data) {
    (void)event;
    MainWindow* win = (MainWindow*)data;
    if (win->minimize_to_tray) {
        gtk_widget_hide(widget);
        return TRUE;  // Prevent destruction
    }
    return FALSE;  // Allow normal destroy
}

// Auto-capture after window is ready
static gboolean on_capture_on_ready(gpointer data) {
    MainWindow* win = (MainWindow*)data;
    MainWindowData* win_data = (MainWindowData*)g_object_get_data(G_OBJECT(win->window), "window-data");
    if (win_data && win_data->capture_on_ready) {
        win_data->capture_on_ready = false;
        main_window_trigger_capture(win);
        gtk_widget_show(win->window);
        gtk_window_present(GTK_WINDOW(win->window));
    }
    return G_SOURCE_REMOVE;
}

// --- X11 key grab for PrintScreen interception ---

static void grab_printscreen_key(MainWindow* win, ShortcutKey key) {
    Settings* settings = safe_get_data(win->window, "settings", "grab_printscreen_key");

    Display* dpy = GDK_DISPLAY_XDISPLAY(gdk_display_get_default());
    Window root = DefaultRootWindow(dpy);

    // Always ungrab any previous grabs by LinScreenCapture
    XUngrabKey(dpy, XKeysymToKeycode(dpy, XK_Print), AnyModifier, root);
    XUngrabKey(dpy, XKeysymToKeycode(dpy, XK_s), AnyModifier, root);
    XFlush(dpy);

    // For DEs with native keybinding support (Cinnamon, GNOME, XFCE, MATE),
    // the DE handles the key via its own daemon + our wrapper/binding.
    // XGrabKey would cause double-capture, so skip it.
    if (settings && settings->detected_de != DE_UNKNOWN && settings->detected_de != DE_KDE) {
        return;
    }

    // X11 fallback: grab the key directly (for unknown DEs and KDE)
    KeyCode kc;
    unsigned int mod = 0;

    switch (key) {
        case SHORTCUT_PRINTSCREEN:
            kc = XKeysymToKeycode(dpy, XK_Print);
            mod = 0;
            break;
        case SHORTCUT_CTRL_PRINTSCREEN:
            kc = XKeysymToKeycode(dpy, XK_Print);
            mod = ControlMask;
            break;
        case SHORTCUT_SHIFT_PRINTSCREEN:
            kc = XKeysymToKeycode(dpy, XK_Print);
            mod = ShiftMask;
            break;
        case SHORTCUT_CTRL_SHIFT_S:
            kc = XKeysymToKeycode(dpy, XK_s);
            mod = ControlMask | ShiftMask;
            break;
        case SHORTCUT_CTRL_ALT_S:
            kc = XKeysymToKeycode(dpy, XK_s);
            mod = ControlMask | Mod1Mask;
            break;
        default:
            return;
    }

    unsigned int lock_masks[] = {0, Mod2Mask, LockMask, Mod5Mask,
                                  Mod2Mask | LockMask, Mod2Mask | Mod5Mask,
                                  LockMask | Mod5Mask, Mod2Mask | LockMask | Mod5Mask};
    for (int i = 0; i < 8; i++) {
        XGrabKey(dpy, kc, mod | lock_masks[i], root, True, GrabModeAsync, GrabModeAsync);
    }

    XFlush(dpy);
}

bool main_window_init(MainWindow* win, int argc, char* argv[]) {
    gtk_init(&argc, &argv);
    
    // Initialize screenshot history
    screenshot_history_init(&win->screenshot_history);
    screenshot_history_load(&win->screenshot_history);
    
    // Create main window
    win->window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    if (!validate_gtk_object(win->window, "main_window_init")) {
        return false;
    }
    
    // Initialize other MainWindow fields
    win->toolbar = NULL;
    win->canvas = NULL;
    win->statusbar = NULL;
    win->history_flow_box = NULL;
    
    win->tray_icon = NULL;
    win->minimize_to_tray = false;

    gtk_window_set_title(GTK_WINDOW(win->window), "LinScreenCapture");
    gtk_window_set_default_size(GTK_WINDOW(win->window), 800, 600);

    // Set application icon (generated via Cairo, no file dependency)
    GList* icon_list = NULL;
    int icon_sizes[] = {16, 24, 32, 48, 64, 128};
    for (int i = 0; i < 6; i++) {
        GdkPixbuf* pb = create_app_icon_pixbuf(icon_sizes[i], false);
        if (pb) icon_list = g_list_append(icon_list, pb);
    }
    if (icon_list) {
        gtk_window_set_icon_list(GTK_WINDOW(win->window), icon_list);
        g_list_free_full(icon_list, g_object_unref);
    }

    // Connect destroy signal (only fires if delete-event allows it)
    g_signal_connect(win->window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    // Intercept close to minimize to tray
    g_signal_connect(win->window, "delete-event", G_CALLBACK(on_delete_event), win);
    
    // Initialize window data
    MainWindowData* data = g_new0(MainWindowData, 1);
    if (!data) {
        gtk_widget_destroy(win->window);
        return false;
    }
    
    // Initialize the window data structure
    data->win = *win;  // Now safe to copy since win is fully initialized
    data->current_image = NULL;
    tool_settings_init(&data->current_tool);
    data->annotations = NULL;
    data->undo_stack = NULL;
    data->drawing = false;
    data->selected_text = NULL;
    data->drag_start_x = 0;
    data->drag_start_y = 0;
    data->current_filename = NULL;
    data->save_sequence = 1;
    data->has_marquee = false;
    data->paste_overlay = NULL;
    data->paste_x = 0;
    data->paste_y = 0;
    data->dragging_paste = false;
    data->paste_drag_ox = 0;
    data->paste_drag_oy = 0;
    data->paste_overlays = NULL;
    data->dragging_overlay = NULL;
    data->zoom_level = 1.0;
    data->image_undo_stack = NULL;

    // Set window data using safe wrapper
    safe_set_data_full(win->window, "window-data", data, g_free, "main_window_init");
    
    // Add key press event handling — connect to window AND install a GDK event
    // filter so shortcuts work even when spinbuttons/combos have focus
    gtk_widget_add_events(win->window, GDK_KEY_PRESS_MASK);
    g_signal_connect(win->window, "key-press-event", G_CALLBACK(on_key_press), win);
    // Install GDK event filter for reliable Ctrl+key interception
    gdk_window_add_filter(NULL, key_filter_func_global, win);
    
    // Initialize settings
    Settings* settings = g_new0(Settings, 1);
    load_settings(settings);
    safe_set_data_full(win->window, "settings", settings, g_free, "main_window_init");

    // Detect desktop environment
    settings->detected_de = detect_desktop_environment();

    // Reload history with the configured screenshot path
    if (settings->screenshot_path) {
        screenshot_history_set_path(&win->screenshot_history, settings->screenshot_path);
        screenshot_history_load(&win->screenshot_history);
    }

    // Create main horizontal box
    GtkWidget* main_hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_container_add(GTK_CONTAINER(win->window), main_hbox);
    
    // Create sidebar container
    GtkWidget* sidebar_container = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_size_request(sidebar_container, 110, -1);
    gtk_widget_set_hexpand(sidebar_container, FALSE);
    gtk_widget_set_vexpand(sidebar_container, TRUE);
    
    // Style the sidebar container
    GtkCssProvider* css_provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css_provider,
        "box.sidebar { background-color: #2d2d2d; }"
        "button.sidebar-button { "
        "   background: none; "
        "   color: #ffffff; "
        "   border: none; "
        "   border-radius: 0; "
        "   padding: 10px 8px 10px 15px; "
        "   margin: 0; "
        "   font-size: 13px; "
        "   min-width: 110px; "
        "   min-height: 0; "
        "   outline: none; "
        "   box-shadow: none; "
        "}"
        "button.sidebar-button:focus { outline: none; box-shadow: none; }"
        "button.sidebar-button:hover { background-color: #3d3d3d; }"
        "button.sidebar-button:active, button.sidebar-button.active { background-color: #4d4d4d; }"
        "label.footer { color: #888888; font-size: 13px; padding: 10px 8px 10px 15px; }"
        "box.content-area { background-color: #2d2d2d; }"
        "drawing-area { background-color: #2d2d2d; }"
        "notebook { background-color: #2d2d2d; }"
        "notebook header { background-color: #252525; padding: 0; }"
        "notebook tab {"
        "   padding: 10px 20px;"
        "   min-height: 20px;"
        "   background-color: #252525;"
        "   border: none;"
        "   border-radius: 0;"
        "   outline: none;"
        "   box-shadow: none;"
        "   border-right: 1px solid #3a3a3a;"
        "}"
        "notebook tab:checked {"
        "   background-color: #2d2d2d;"
        "   border: none;"
        "   border-bottom: 2px solid #e0e0e0;"
        "   border-right: 1px solid #3a3a3a;"
        "}"
        "notebook tab:hover:not(:checked) {"
        "   background-color: #333333;"
        "}"
        "notebook tab label {"
        "   color: #ffffff;"
        "   font-size: 13px;"
        "}"
        "notebook > stack { background-color: #2d2d2d; }"
        "frame { color: #cccccc; }"
        "frame > border { border-color: #555555; }"
        "frame > label { color: #cccccc; }"
        "radiobutton label, checkbutton label { color: #cccccc; font-size: 13px; }"
        "entry { background-color: #3d3d3d; color: #e0e0e0; border-color: #555555; }"
        "spinbutton { font-size: 11px; min-height: 18px; padding: 0 2px; }"
        "spinbutton button { min-height: 8px; min-width: 8px; padding: 0; margin: 0; font-size: 7px; color: #cccccc; }"
        "spinbutton button:hover { color: #ffffff; }"
        "scale { min-height: 12px; }"
        "scale slider { min-height: 10px; min-width: 10px; background-color: #888888; border-radius: 5px; }"
        "scale trough { background-color: #444444; min-height: 4px; border-radius: 2px; }"
        "scale highlight { background-color: #e0e0e0; min-height: 4px; border-radius: 2px; }"
        "combobox { font-size: 12px; }"
        "flowboxchild { border: 2px solid transparent; border-radius: 4px; padding: 2px; }"
        "flowboxchild:selected { border: 2px solid #5599ff; background-color: rgba(85,153,255,0.2); }"
        "flowboxchild:selected image { opacity: 0.75; }"
        "separator { background-color: #555555; }",
        -1, NULL);
    
    // Apply CSS globally so it covers all tabs and widgets
    GdkScreen* screen = gdk_screen_get_default();
    gtk_style_context_add_provider_for_screen(screen,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);

    GtkStyleContext* sidebar_context = gtk_widget_get_style_context(sidebar_container);
    gtk_style_context_add_class(sidebar_context, "sidebar");
    
    // Create buttons container
    GtkWidget* buttons_container = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_box_pack_start(GTK_BOX(sidebar_container), buttons_container, TRUE, TRUE, 0);

    // Create buttons with icons and labels
    // Icon indices match SidebarIconType enum
    const char* button_labels[] = {
        "Capture", "Line", "Arrow", "Box", "Circle", "Text", "Select", "Flatten", "Copy",
        "Border", "Blur", "Crop", "Resize", "Rotate", "Bright", "Dupe", "Save"
    };
    typedef struct { char type; int id; } BtnDef;
    BtnDef button_defs[] = {
        {'a', 0},               // 0: LinScreenCapture (capture)
        {'t', TOOL_LINE},       // 1: Line
        {'t', TOOL_ARROW},      // 2: Arrow
        {'t', TOOL_RECTANGLE},  // 3: Box
        {'t', TOOL_ELLIPSE},    // 4: Circle
        {'t', TOOL_TEXT},       // 5: Text
        {'t', TOOL_MARQUEE},    // 6: Select
        {'a', 1},               // 7: Flatten
        {'a', 2},               // 8: Copy
        {'t', TOOL_BORDER},     // 9: Border
        {'t', TOOL_BLUR},       // 10: Blur
        {'t', TOOL_CROP},       // 11: Crop
        {'t', TOOL_RESIZE},     // 12: Resize
        {'t', TOOL_ROTATE},     // 13: Rotate
        {'t', TOOL_BRIGHTNESS}, // 14: Brightness
        {'t', TOOL_DUPLICATE},  // 15: Duplicate
        {'a', 3}                // 16: Save
    };

    for (int i = 0; i < 17; i++) {
        GtkWidget* button = gtk_button_new();
        gtk_widget_set_hexpand(button, TRUE);

        // Create hbox to hold icon + label
        GtkWidget* hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
        gtk_container_add(GTK_CONTAINER(button), hbox);

        // Create drawing area for icon
        GtkWidget* icon_area = gtk_drawing_area_new();
        gtk_widget_set_size_request(icon_area, SIDEBAR_ICON_SIZE, SIDEBAR_ICON_SIZE);
        safe_set_data(icon_area, "icon-type", GINT_TO_POINTER(i), "main_window_init");
        g_signal_connect(icon_area, "draw", G_CALLBACK(on_sidebar_icon_draw), NULL);
        gtk_box_pack_start(GTK_BOX(hbox), icon_area, FALSE, FALSE, 0);

        // Create label
        GtkWidget* label = gtk_label_new(button_labels[i]);
        gtk_widget_set_halign(label, GTK_ALIGN_START);
        gtk_box_pack_start(GTK_BOX(hbox), label, FALSE, FALSE, 0);

        // Style the button
        GtkStyleContext* button_context = gtk_widget_get_style_context(button);
        gtk_style_context_add_provider(button_context,
            GTK_STYLE_PROVIDER(css_provider),
            GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
        gtk_style_context_add_class(button_context, "sidebar-button");

        // Connect signals
        if (button_defs[i].type == 't') {
            safe_set_data(button, "tool-id", GINT_TO_POINTER(button_defs[i].id), "main_window_init");
            g_signal_connect(button, "clicked", G_CALLBACK(on_tool_button_clicked), win);
        } else if (i == 0) {
            g_signal_connect(button, "clicked", G_CALLBACK(on_capture_button_clicked), win);
        } else if (i == 7) { // Flatten
            g_signal_connect(button, "clicked", G_CALLBACK(on_flatten_button_clicked), win);
        } else if (i == 8) { // Copy
            g_signal_connect(button, "clicked", G_CALLBACK(on_copy_button_clicked), win);
        } else if (i == 16) { // Save
            g_signal_connect(button, "clicked", G_CALLBACK(on_save_button_clicked), win);
        }

        gtk_box_pack_start(GTK_BOX(buttons_container), button, FALSE, FALSE, 0);
    }
    
    // Add footer label
    GtkWidget* footer_label = gtk_label_new("Mensura Media");
    gtk_widget_set_halign(footer_label, GTK_ALIGN_CENTER);
    gtk_widget_set_hexpand(footer_label, TRUE);
    GtkStyleContext* footer_context = gtk_widget_get_style_context(footer_label);
    gtk_style_context_add_provider(footer_context,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(footer_context, "footer");
    gtk_box_pack_end(GTK_BOX(sidebar_container), footer_label, FALSE, FALSE, 0);
    
    // Add sidebar to main container
    gtk_box_pack_start(GTK_BOX(main_hbox), sidebar_container, FALSE, FALSE, 0);
    
    // Create content area
    GtkWidget* content_area = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_box_pack_start(GTK_BOX(main_hbox), content_area, TRUE, TRUE, 0);
    
    // Apply content area style
    GtkStyleContext* content_context = gtk_widget_get_style_context(content_area);
    gtk_style_context_add_provider(content_context,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(content_context, "content-area");
    
    // Create notebook for tabs
    GtkWidget* notebook = gtk_notebook_new();
    gtk_box_pack_start(GTK_BOX(content_area), notebook, TRUE, TRUE, 0);

    // Apply tab styling
    GtkStyleContext* nb_context = gtk_widget_get_style_context(notebook);
    gtk_style_context_add_provider(nb_context,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);

    // Create current screenshot page
    GtkWidget* screenshot_page = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    GtkWidget* screenshot_label = gtk_label_new("Image");
    gtk_widget_set_halign(screenshot_label, GTK_ALIGN_CENTER);
    gtk_notebook_append_page(GTK_NOTEBOOK(notebook), screenshot_page, screenshot_label);

    // Create scrolled window for the canvas
    GtkWidget* canvas_scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(canvas_scroll),
                                 GTK_POLICY_AUTOMATIC,
                                 GTK_POLICY_AUTOMATIC);
    gtk_widget_set_hexpand(canvas_scroll, TRUE);
    gtk_widget_set_vexpand(canvas_scroll, TRUE);
    gtk_box_pack_start(GTK_BOX(screenshot_page), canvas_scroll, TRUE, TRUE, 0);
    
    // Create canvas for displaying captures
    win->canvas = gtk_drawing_area_new();
    gtk_widget_set_size_request(win->canvas, 400, 300);  // Set initial size
    gtk_widget_add_events(win->canvas,
                         GDK_BUTTON_PRESS_MASK |
                         GDK_BUTTON_RELEASE_MASK |
                         GDK_POINTER_MOTION_MASK |
                         GDK_SCROLL_MASK |
                         GDK_SMOOTH_SCROLL_MASK);
    
    // Apply drawing area style
    GtkStyleContext* canvas_context = gtk_widget_get_style_context(win->canvas);
    gtk_style_context_add_provider(canvas_context,
        GTK_STYLE_PROVIDER(css_provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(canvas_context, "drawing-area");
    
    // Connect canvas signals
    g_signal_connect(win->canvas, "draw", G_CALLBACK(on_draw), win);
    g_signal_connect(win->canvas, "button-press-event", G_CALLBACK(on_button_press), win);
    g_signal_connect(win->canvas, "button-release-event", G_CALLBACK(on_button_release), win);
    g_signal_connect(win->canvas, "motion-notify-event", G_CALLBACK(on_motion_notify), win);
    g_signal_connect(win->canvas, "scroll-event", G_CALLBACK(on_scroll_event), win);

    // Add canvas to scrolled window
    gtk_container_add(GTK_CONTAINER(canvas_scroll), win->canvas);
    
    // Create history page
    GtkWidget* history_page = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    GtkWidget* history_label = gtk_label_new("Files");
    gtk_widget_set_halign(history_label, GTK_ALIGN_CENTER);
    gtk_notebook_append_page(GTK_NOTEBOOK(notebook), history_page, history_label);

    // History toolbar: image count + hint + delete button
    GtkWidget* history_toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_widget_set_margin_start(history_toolbar, 8);
    gtk_widget_set_margin_end(history_toolbar, 8);
    gtk_widget_set_margin_top(history_toolbar, 6);
    gtk_widget_set_margin_bottom(history_toolbar, 4);

    // Image count label (updated when history loads) — left aligned
    GtkWidget* count_label = gtk_label_new("0 images");
    gtk_widget_set_halign(count_label, GTK_ALIGN_START);
    safe_set_data(win->window, "history-count-label", count_label, "main_window_init");
    gtk_box_pack_start(GTK_BOX(history_toolbar), count_label, FALSE, FALSE, 0);

    GtkWidget* hint_label = gtk_label_new("Ctrl+Click select  |  Shift+Click range  |  Delete key");
    gtk_widget_set_opacity(hint_label, 0.4);
    gtk_box_pack_start(GTK_BOX(history_toolbar), hint_label, FALSE, FALSE, 0);

    GtkWidget* delete_btn = gtk_button_new_with_label("Delete");
    gtk_widget_set_sensitive(delete_btn, FALSE);
    safe_set_data(win->window, "delete-btn", delete_btn, "main_window_init");
    g_signal_connect(delete_btn, "clicked", G_CALLBACK(on_delete_selected_clicked), win);
    gtk_box_pack_start(GTK_BOX(history_toolbar), delete_btn, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(history_page), history_toolbar, FALSE, FALSE, 0);

    // Create scrolled window for history
    GtkWidget* history_scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(history_scroll),
                                 GTK_POLICY_AUTOMATIC,
                                 GTK_POLICY_AUTOMATIC);
    gtk_widget_set_vexpand(history_scroll, TRUE);
    gtk_widget_set_hexpand(history_scroll, TRUE);
    gtk_container_add(GTK_CONTAINER(history_page), history_scroll);
    
    // Create flow box for history thumbnails
    GtkWidget* flow_box = gtk_flow_box_new();
    gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(flow_box), GTK_SELECTION_MULTIPLE);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(flow_box), FALSE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(flow_box), 2);
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(flow_box), 5);
    gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(flow_box), 5);
    gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(flow_box), 5);
    gtk_widget_set_margin_start(flow_box, 5);
    gtk_widget_set_margin_end(flow_box, 5);
    gtk_widget_set_margin_top(flow_box, 5);
    gtk_widget_set_margin_bottom(flow_box, 5);
    gtk_container_add(GTK_CONTAINER(history_scroll), flow_box);

    // Double-click to open, single-click to select
    gtk_flow_box_set_activate_on_single_click(GTK_FLOW_BOX(flow_box), FALSE);

    // Refresh history when tab is selected (picks up new files added externally)
    g_signal_connect(notebook, "switch-page", G_CALLBACK(on_notebook_switch_page), win);

    // Connect flow box signals — GTK handles Ctrl+Click and Shift+Click natively
    g_signal_connect(flow_box, "selected-children-changed", G_CALLBACK(on_history_selection_changed), win);
    g_signal_connect(flow_box, "child-activated", G_CALLBACK(on_history_child_activated), win);
    
    // Create bottom bar: image info (left) + statusbar (right)
    GtkWidget* bottom_bar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_box_pack_start(GTK_BOX(content_area), bottom_bar, FALSE, FALSE, 0);

    // Image info label — persistent, no border
    GtkWidget* image_info_label = gtk_label_new("");
    gtk_widget_set_margin_start(image_info_label, 8);
    gtk_widget_set_margin_end(image_info_label, 4);
    gtk_widget_set_margin_top(image_info_label, 2);
    gtk_widget_set_margin_bottom(image_info_label, 2);
    gtk_label_set_xalign(GTK_LABEL(image_info_label), 0.0);
    gtk_box_pack_start(GTK_BOX(bottom_bar), image_info_label, FALSE, FALSE, 0);
    safe_set_data(win->window, "image-info-label", image_info_label, "main_window_init");

    // Vertical separator pipe
    GtkWidget* info_sep = gtk_label_new("|");
    gtk_widget_set_opacity(info_sep, 0.3);
    gtk_widget_set_margin_start(info_sep, 4);
    gtk_widget_set_margin_end(info_sep, 4);
    gtk_box_pack_start(GTK_BOX(bottom_bar), info_sep, FALSE, FALSE, 0);

    // Statusbar — for transient messages (zoom, copy, save, etc.)
    win->statusbar = gtk_statusbar_new();
    gtk_box_pack_start(GTK_BOX(bottom_bar), win->statusbar, TRUE, TRUE, 0);
    gtk_statusbar_push(GTK_STATUSBAR(win->statusbar), 0, "Ready");
    
    // Update window data with canvas and statusbar
    data->win.canvas = win->canvas;
    data->win.statusbar = win->statusbar;
    
    // Store flow box in window data for history updates
    win->history_flow_box = flow_box;
    
    // Create colors tab (before Settings)
    create_colors_page(win, notebook);

    // Create settings tab
    create_settings_page(win, notebook);

    // Create about tab
    create_about_page(notebook, css_provider);

    // Set up system tray icon and enable minimize-to-tray
    setup_tray_icon(win);
    win->minimize_to_tray = true;

    // Register keyboard shortcut - use X11 grab for reliable interception
    register_shortcut_key(win, settings->shortcut_key);
    grab_printscreen_key(win, settings->shortcut_key);

    // Store window pointer globally for accel callbacks
    safe_set_data(win->window, "main-win-ptr", win, "main_window_init");

    // Show all widgets
    gtk_widget_show_all(win->window);

    // Set focus to the canvas so the path entry doesn't auto-focus
    gtk_widget_grab_focus(win->canvas);

    // Schedule auto-capture if --capture flag was set
    g_idle_add(on_capture_on_ready, win);

    return true;
}

void main_window_cleanup(MainWindow* win) {
    if (!win) {
        return;
    }
    
    // Clean up window data first
    if (win->window && GTK_IS_WIDGET(win->window)) {
        MainWindowData* data = safe_get_data(win->window, "window-data", "main_window_cleanup");
        if (data) {
            if (data->current_image) {
                cairo_surface_destroy(data->current_image);
                data->current_image = NULL;
            }
            
            // Free filename tracking
            g_free(data->current_filename);
            data->current_filename = NULL;

            // Free all paste overlays
            if (data->paste_overlays) {
                g_list_free_full(data->paste_overlays, (GDestroyNotify)paste_overlay_free);
                data->paste_overlays = NULL;
            }
            data->paste_overlay = NULL;
            data->dragging_overlay = NULL;

            // Free both annotations list and undo stack
            g_list_free_full(data->annotations, (GDestroyNotify)annotation_free);
            g_list_free_full(data->undo_stack, (GDestroyNotify)annotation_free);
            data->annotations = NULL;
            data->undo_stack = NULL;
            
            // Remove the data from the window before freeing
            safe_set_data(win->window, "window-data", NULL, "main_window_cleanup");
        }
    }
    
    // Clean up history
    screenshot_history_cleanup(&win->screenshot_history);
    
    // Clean up widgets
    if (win->window && GTK_IS_WIDGET(win->window)) {
        gtk_widget_destroy(win->window);
        win->window = NULL;
    }
} 