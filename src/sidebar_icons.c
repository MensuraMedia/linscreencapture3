#include "sidebar_icons.h"
#include <math.h>
#include <stddef.h>

// All coordinates are normalized to a 20x20 grid.
// If SIDEBAR_ICON_SIZE changes, icons scale proportionally.

static double S(double val) {
    return val * ((double)SIDEBAR_ICON_SIZE / 20.0);
}

// SET 1 design (Clean Minimal shapes) with SET 2 styling (bold strokes)
// Save icon uses SET 2 design (download arrow into tray)

static void draw_shot(cairo_t* cr, double x, double y) {
    // LinScreenCapture app icon: circle with inner dot
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);

    // Outer circle
    double cx = x + S(10);
    double cy = y + S(10);
    cairo_arc(cr, cx, cy, S(7), 0, 2 * 3.14159265);
    cairo_stroke(cr);

    // Inner dot
    cairo_arc(cr, cx, cy, S(2), 0, 2 * 3.14159265);
    cairo_fill(cr);
}

static void draw_arrow(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Shaft
    cairo_move_to(cr, x+S(4), y+S(16));
    cairo_line_to(cr, x+S(16), y+S(4));
    cairo_stroke(cr);

    // Arrowhead lines
    cairo_move_to(cr, x+S(16), y+S(4));
    cairo_line_to(cr, x+S(10), y+S(4));
    cairo_stroke(cr);
    cairo_move_to(cr, x+S(16), y+S(4));
    cairo_line_to(cr, x+S(16), y+S(10));
    cairo_stroke(cr);
}

static void draw_box(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    cairo_rectangle(cr, x+S(3), y+S(3), S(14), S(14));
    cairo_stroke(cr);
}

static void draw_circle(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);

    cairo_arc(cr, x+S(10), y+S(10), S(7), 0, 2*M_PI);
    cairo_stroke(cr);
}

static void draw_text(cairo_t* cr, double x, double y) {
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Top bar of T
    cairo_set_line_width(cr, SIDEBAR_ICON_STROKE);
    cairo_move_to(cr, x+S(4), y+S(4));
    cairo_line_to(cr, x+S(16), y+S(4));
    cairo_stroke(cr);

    // Vertical stroke (slightly heavier)
    cairo_set_line_width(cr, SIDEBAR_ICON_STROKE + 0.4);
    cairo_move_to(cr, x+S(10), y+S(4));
    cairo_line_to(cr, x+S(10), y+S(17));
    cairo_stroke(cr);

    // Bottom serif
    cairo_set_line_width(cr, SIDEBAR_ICON_STROKE);
    cairo_move_to(cr, x+S(7), y+S(17));
    cairo_line_to(cr, x+S(13), y+S(17));
    cairo_stroke(cr);
}

static void draw_copy(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Back rectangle
    cairo_rectangle(cr, x+S(2), y+S(2), S(11), S(13));
    cairo_stroke(cr);

    // Front rectangle (offset)
    cairo_rectangle(cr, x+S(7), y+S(5), S(11), S(13));
    cairo_stroke(cr);
}

static void draw_line(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);

    cairo_move_to(cr, x+S(4), y+S(16));
    cairo_line_to(cr, x+S(16), y+S(4));
    cairo_stroke(cr);
}

static void draw_select(cairo_t* cr, double x, double y) {
    // Dashed rectangle (marquee selection icon)
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    double dashes[] = {3.0, 2.0};
    cairo_set_dash(cr, dashes, 2, 0);
    cairo_rectangle(cr, x+S(3), y+S(3), S(14), S(14));
    cairo_stroke(cr);
    cairo_set_dash(cr, NULL, 0, 0);

    // Small crosshair cursor in lower-right corner
    cairo_set_line_width(cr, 1.2);
    cairo_move_to(cr, x+S(14), y+S(12));
    cairo_line_to(cr, x+S(14), y+S(18));
    cairo_stroke(cr);
    cairo_move_to(cr, x+S(11), y+S(15));
    cairo_line_to(cr, x+S(17), y+S(15));
    cairo_stroke(cr);
}

static void draw_flatten(cairo_t* cr, double x, double y) {
    // Two layers merging into one (flatten icon)
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Back layer
    cairo_rectangle(cr, x+S(2), y+S(2), S(10), S(8));
    cairo_stroke(cr);

    // Front layer
    cairo_rectangle(cr, x+S(8), y+S(8), S(10), S(8));
    cairo_stroke(cr);

    // Downward arrow between them
    cairo_set_line_width(cr, 1.5);
    cairo_move_to(cr, x+S(10), y+S(5));
    cairo_line_to(cr, x+S(10), y+S(13));
    cairo_stroke(cr);
    cairo_move_to(cr, x+S(7.5), y+S(11));
    cairo_line_to(cr, x+S(10), y+S(14));
    cairo_line_to(cr, x+S(12.5), y+S(11));
    cairo_stroke(cr);
}

static void draw_save(cairo_t* cr, double x, double y) {
    // SET 2 save icon: download arrow into tray
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Downward arrow shaft
    cairo_move_to(cr, x+S(10), y+S(3));
    cairo_line_to(cr, x+S(10), y+S(13));
    cairo_stroke(cr);

    // Arrow chevron
    cairo_move_to(cr, x+S(6), y+S(10));
    cairo_line_to(cr, x+S(10), y+S(14));
    cairo_line_to(cr, x+S(14), y+S(10));
    cairo_stroke(cr);

    // Tray
    cairo_move_to(cr, x+S(3), y+S(14));
    cairo_line_to(cr, x+S(3), y+S(18));
    cairo_line_to(cr, x+S(17), y+S(18));
    cairo_line_to(cr, x+S(17), y+S(14));
    cairo_stroke(cr);
}

static void draw_border(cairo_t* cr, double x, double y) {
    // Double rectangle (border/frame icon)
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Outer rectangle
    cairo_rectangle(cr, x+S(2), y+S(2), S(16), S(16));
    cairo_stroke(cr);

    // Inner rectangle (inset)
    cairo_rectangle(cr, x+S(5), y+S(5), S(10), S(10));
    cairo_stroke(cr);
}

static void draw_blur(cairo_t* cr, double x, double y) {
    // Pixelate/mosaic icon: small grid of squares
    double lw = 1.0;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    double cell = S(4.5);
    double ox = x + S(2);
    double oy = y + S(2);

    for (int r = 0; r < 4; r++) {
        for (int c = 0; c < 4; c++) {
            double shade = ((r + c) % 2 == 0) ? 0.8 : 0.4;
            cairo_set_source_rgba(cr, shade, shade, shade, 1.0);
            cairo_rectangle(cr, ox + c * cell, oy + r * cell, cell, cell);
            cairo_fill(cr);
        }
    }
}

static void draw_crop(cairo_t* cr, double x, double y) {
    // Crop icon: two overlapping L-shaped brackets
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Vertical line with horizontal top
    cairo_move_to(cr, x+S(6), y+S(2));
    cairo_line_to(cr, x+S(6), y+S(14));
    cairo_line_to(cr, x+S(18), y+S(14));
    cairo_stroke(cr);

    // Horizontal line with vertical bottom
    cairo_move_to(cr, x+S(2), y+S(6));
    cairo_line_to(cr, x+S(14), y+S(6));
    cairo_line_to(cr, x+S(14), y+S(18));
    cairo_stroke(cr);
}

static void draw_resize(cairo_t* cr, double x, double y) {
    // Resize icon: diagonal double-headed arrow with corner box
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Small rectangle (original)
    cairo_rectangle(cr, x+S(2), y+S(2), S(10), S(8));
    cairo_stroke(cr);

    // Diagonal arrow
    cairo_move_to(cr, x+S(10), y+S(10));
    cairo_line_to(cr, x+S(18), y+S(18));
    cairo_stroke(cr);

    // Arrowhead
    cairo_move_to(cr, x+S(14), y+S(18));
    cairo_line_to(cr, x+S(18), y+S(18));
    cairo_line_to(cr, x+S(18), y+S(14));
    cairo_stroke(cr);
}

static void draw_rotate(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    // Circular arrow (270 degree arc)
    cairo_arc(cr, x+S(10), y+S(10), S(7), -M_PI * 0.5, M_PI);
    cairo_stroke(cr);
    // Arrowhead
    cairo_move_to(cr, x+S(3), y+S(7));
    cairo_line_to(cr, x+S(3), y+S(12));
    cairo_line_to(cr, x+S(7), y+S(10));
    cairo_close_path(cr);
    cairo_fill(cr);
}

static void draw_brightness(cairo_t* cr, double x, double y) {
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    // Sun: circle with rays
    cairo_arc(cr, x+S(10), y+S(10), S(4), 0, 2*M_PI);
    cairo_stroke(cr);
    // 8 rays
    for (int i = 0; i < 8; i++) {
        double angle = i * M_PI / 4.0;
        double inner = S(6);
        double outer = S(9);
        cairo_move_to(cr, x+S(10) + cos(angle)*inner, y+S(10) + sin(angle)*inner);
        cairo_line_to(cr, x+S(10) + cos(angle)*outer, y+S(10) + sin(angle)*outer);
        cairo_stroke(cr);
    }
}

static void draw_duplicate(cairo_t* cr, double x, double y) {
    // Two overlapping pages with a small + sign
    double lw = SIDEBAR_ICON_STROKE;
    cairo_set_line_width(cr, lw);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(cr, CAIRO_LINE_JOIN_MITER);

    // Back page
    cairo_rectangle(cr, x+S(5), y+S(2), S(11), S(13));
    cairo_stroke(cr);

    // Front page (offset)
    cairo_rectangle(cr, x+S(2), y+S(5), S(11), S(13));
    cairo_stroke(cr);

    // Small + sign on front page
    cairo_set_line_width(cr, 1.5);
    cairo_move_to(cr, x+S(7.5), y+S(9));
    cairo_line_to(cr, x+S(7.5), y+S(15));
    cairo_stroke(cr);
    cairo_move_to(cr, x+S(4.5), y+S(12));
    cairo_line_to(cr, x+S(10.5), y+S(12));
    cairo_stroke(cr);
}

// Dispatch table
typedef void (*IconDrawFunc)(cairo_t*, double, double);

static const IconDrawFunc icon_funcs[ICON_COUNT] = {
    draw_shot,
    draw_line,
    draw_arrow,
    draw_box,
    draw_circle,
    draw_text,
    draw_select,
    draw_flatten,
    draw_copy,
    draw_border,
    draw_blur,
    draw_crop,
    draw_resize,
    draw_rotate,
    draw_brightness,
    draw_duplicate,
    draw_save
};

void sidebar_icon_draw(cairo_t* cr, SidebarIconType type, double x, double y) {
    if (type < 0 || type >= ICON_COUNT) return;

    // Save state so icon drawing doesn't affect caller
    cairo_save(cr);
    icon_funcs[type](cr, x, y);
    cairo_restore(cr);
}
