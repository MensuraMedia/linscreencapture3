"""Capture overlay: the frozen screen, a veil, a selection with handles, crosshair and chips.

One ``OverlayWindow`` per monitor shares an ``OverlaySession``; coordinates in the session are
physical root pixels (the frozen surface's pixels).
"""
from __future__ import annotations
import math
from typing import Callable

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from .widgets import rail_button
from ..services.selection import Selection, square_end, HANDLE
from ..backends.base import WindowInfo

ACCENT = (0x4c / 255, 0x9d / 255, 1.0)
MODES = (("selection", "Region", "region"), ("app-window", "Window", "window"), ("monitor", "Full screen", "screen"))


class OverlaySession:
    def __init__(self, surface: cairo.ImageSurface, mode: str, windows: list[WindowInfo],
                 on_done: Callable[[tuple[int, int, int, int] | None], None]):
        self.surface = surface
        self.mode = mode if mode in ("region", "window") else "region"
        self.windows = windows
        self.on_done = on_done
        self.selection: Selection | None = None
        self.hover_window: WindowInfo | None = None
        self.pointer: tuple[float, float] | None = None
        self.overlays: list[OverlayWindow] = []
        self.finished = False

    # -- lifecycle ----------------------------------------------------------
    def show(self, display: Gdk.Display | None = None) -> None:
        display = display or Gdk.Display.get_default()
        monitors = display.get_monitors()
        for i in range(monitors.get_n_items()):
            ow = OverlayWindow(self, monitors.get_item(i))
            self.overlays.append(ow)
        for ow in self.overlays:
            ow.present()
        if self.overlays:
            self.overlays[0].grab_focus()

    def redraw(self) -> None:
        for ow in self.overlays:
            ow.area.queue_draw()

    def finish(self, rect: tuple[int, int, int, int] | None) -> None:
        if self.finished:
            return
        self.finished = True
        for ow in self.overlays:
            ow.close()
        self.overlays.clear()
        self.on_done(rect)

    def confirm(self) -> None:
        if self.selection is None or self.selection.is_empty:
            return
        x, y, w, h = self.selection.normalised().rect
        self.finish((x, y, w, h))

    def cancel(self) -> None:
        self.finish(None)

    def whole_screen(self) -> None:
        self.finish((0, 0, self.surface.get_width(), self.surface.get_height()))

    def set_mode(self, mode: str) -> None:
        if mode == "screen":
            self.whole_screen()
            return
        self.mode = mode
        self.selection = None
        self.redraw()

    def window_at(self, x: float, y: float) -> WindowInfo | None:
        for w in self.windows:  # topmost first
            if w.x <= x <= w.x + w.width and w.y <= y <= w.y + w.height:
                return w
        return None

    def nudge(self, dx: int, dy: int) -> None:
        if self.selection:
            self.selection = self.selection.moved(dx, dy).clamped(0, 0, self.surface.get_width(), self.surface.get_height())
            self.redraw()


class OverlayWindow(Gtk.Window):
    def __init__(self, session: OverlaySession, monitor: Gdk.Monitor):
        super().__init__(decorated=False, resizable=False, title="LinScreenCapture capture")
        self.session = session
        self.monitor = monitor
        geo = monitor.get_geometry()
        self.scale = monitor.get_scale_factor() or 1
        self.ox, self.oy = geo.x * self.scale, geo.y * self.scale   # physical origin of this monitor
        self.add_css_class("capture-overlay")
        self.set_default_size(geo.width, geo.height)
        self.fullscreen_on_monitor(monitor)
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair"))

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True, can_focus=True, focusable=True)
        self.area.set_draw_func(self._draw)
        overlay = Gtk.Overlay(child=self.area)
        overlay.add_overlay(self._mode_bar())
        overlay.add_overlay(self._hint_bar())
        self.set_child(overlay)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        motion.connect("leave", lambda *_: self._set_pointer(None))
        self.area.add_controller(motion)
        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.area.add_controller(drag)
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", self._click)
        self.area.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        keys.connect("key-released", self._key_up)
        self.add_controller(keys)
        self._drag_mode: str | None = None     # new | move | handle name
        self._drag_start: Selection | None = None
        self._anchor = (0.0, 0.0)
        self._space = False
        self._last = (0.0, 0.0)

    # -- coordinate helpers ------------------------------------------------
    def to_root(self, lx: float, ly: float) -> tuple[float, float]:
        return self.ox + lx * self.scale, self.oy + ly * self.scale

    def to_local(self, rx: float, ry: float) -> tuple[float, float]:
        return (rx - self.ox) / self.scale, (ry - self.oy) / self.scale

    # -- chrome -------------------------------------------------------------
    def _mode_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.START,
                      margin_top=16)
        bar.add_css_class("chip")
        bar.add_css_class("overlay-bar")
        first = None
        for icon, label, mode in MODES:
            b = rail_button(icon, label, toggle=True)
            b.set_active(mode == self.session.mode)
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.connect("toggled", lambda btn, m=mode: btn.get_active() and self.session.set_mode(m))
            bar.append(b)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class("hairline")
        sep.set_margin_start(6); sep.set_margin_end(6)
        bar.append(sep)
        for key, what in (("Enter", "capture"), ("Esc", "cancel"), ("Space", "move"), ("Shift", "square")):
            k = Gtk.Label(label=key); k.add_css_class("kind"); bar.append(k)
            w = Gtk.Label(label=what); w.add_css_class("sublabel"); w.set_margin_end(6); bar.append(w)
        return bar

    def _hint_bar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END, valign=Gtk.Align.END,
                      margin_end=16, margin_bottom=16)
        bar.add_css_class("chip")
        lbl = Gtk.Label(label="Arrows nudge 1 px · Shift+Arrows 10 px · double-click captures")
        lbl.add_css_class("sublabel")
        bar.append(lbl)
        return bar

    # -- drawing ------------------------------------------------------------
    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        s = self.session
        cr.save()
        cr.scale(1 / self.scale, 1 / self.scale)
        cr.set_source_surface(s.surface, -self.ox, -self.oy)
        cr.paint()
        cr.restore()
        # veil with a hole
        hole = None
        if s.mode == "window" and s.hover_window and (s.selection is None):
            hole = s.hover_window.rect
        elif s.selection and not s.selection.is_empty:
            hole = s.selection.normalised().rect
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.rectangle(0, 0, w, h)
        if hole:
            lx, ly = self.to_local(hole[0], hole[1])
            cr.rectangle(lx, ly, hole[2] / self.scale, hole[3] / self.scale)
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.fill()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)
        # crosshair
        if s.pointer and self._drag_mode is None and s.mode == "region":
            px, py = self.to_local(*s.pointer)
            cr.set_source_rgba(*ACCENT, 0.55)
            cr.set_line_width(1)
            cr.move_to(0, int(py) + 0.5); cr.line_to(w, int(py) + 0.5)
            cr.move_to(int(px) + 0.5, 0); cr.line_to(int(px) + 0.5, h)
            cr.stroke()
        if hole:
            lx, ly = self.to_local(hole[0], hole[1])
            lw, lh = hole[2] / self.scale, hole[3] / self.scale
            cr.set_source_rgb(*ACCENT)
            cr.set_line_width(1)
            cr.rectangle(int(lx) + 0.5, int(ly) + 0.5, lw, lh)
            cr.stroke()
            if s.selection and s.mode == "region":
                for hx, hy in s.selection.normalised().handle_positions().values():
                    cx, cy = self.to_local(hx, hy)
                    cr.rectangle(cx - HANDLE / 2, cy - HANDLE / 2, HANDLE, HANDLE)
                    cr.set_source_rgb(1, 1, 1); cr.fill_preserve()
                    cr.set_source_rgb(*ACCENT); cr.set_line_width(1.5); cr.stroke()
            self._chip(cr, f"{hole[2]} × {hole[3]}", lx + lw - 8, ly + lh + 10, anchor_right=True,
                       flip_up=(ly + lh + 40 > h))
            if s.mode == "window" and s.hover_window and s.hover_window.title:
                self._chip(cr, s.hover_window.title[:60], lx + 8, ly + 10)
        if s.pointer:
            rx, ry = s.pointer
            colour = self._sample(int(rx), int(ry))
            self._chip(cr, f"x {int(rx)}   y {int(ry)}   {colour}", 16, h - 42)

    def _sample(self, x: int, y: int) -> str:
        s = self.session.surface
        if not (0 <= x < s.get_width() and 0 <= y < s.get_height()):
            return ""
        i = y * s.get_stride() + x * 4
        b, g, r = s.get_data()[i:i + 3]
        return f"#{r:02X}{g:02X}{b:02X}"

    def _chip(self, cr: cairo.Context, text: str, x: float, y: float, anchor_right: bool = False, flip_up: bool = False) -> None:
        layout = PangoCairo.create_layout(cr)
        desc = Pango.FontDescription("Ubuntu Mono 10")
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        _ink, log = layout.get_extents()
        tw, th = log.width / Pango.SCALE, log.height / Pango.SCALE
        cw, ch = tw + 20, max(26, th + 10)
        if anchor_right:
            x -= cw
        if flip_up:
            y -= ch + 20
        r = 6
        cr.new_sub_path()
        cr.arc(x + cw - r, y + r, r, -math.pi / 2, 0); cr.arc(x + cw - r, y + ch - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + ch - r, r, math.pi / 2, math.pi); cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgba(38 / 255, 42 / 255, 48 / 255, 0.94); cr.fill_preserve()
        cr.set_source_rgb(0x3a / 255, 0x40 / 255, 0x48 / 255); cr.set_line_width(1); cr.stroke()
        cr.set_source_rgb(0xec / 255, 0xef / 255, 0xf3 / 255)
        cr.move_to(x + 10, y + (ch - th) / 2)
        PangoCairo.show_layout(cr, layout)

    # -- input --------------------------------------------------------------
    def _set_pointer(self, p) -> None:
        self.session.pointer = p
        self.session.redraw()

    def _motion(self, _c, lx: float, ly: float) -> None:
        rx, ry = self.to_root(lx, ly)
        s = self.session
        s.pointer = (rx, ry)
        if s.mode == "window":
            s.hover_window = s.window_at(rx, ry)
        elif self._drag_mode is None and s.selection:
            self.set_cursor(Gdk.Cursor.new_from_name(s.selection.cursor_for(s.selection.hit(rx, ry))))
        s.redraw()

    def _drag_begin(self, gesture: Gtk.GestureDrag, lx: float, ly: float) -> None:
        self.area.grab_focus()
        rx, ry = self.to_root(lx, ly)
        s = self.session
        if s.mode != "region":
            return
        hit = s.selection.hit(rx, ry) if s.selection else None
        self._anchor = (rx, ry)
        self._last = (rx, ry)
        if hit == "inside":
            self._drag_mode, self._drag_start = "move", s.selection
        elif hit:
            self._drag_mode, self._drag_start = hit, s.selection.normalised()
        else:
            self._drag_mode = "new"
            s.selection = Selection(rx, ry, rx, ry)
        s.redraw()

    def _drag_update(self, gesture: Gtk.GestureDrag, dx: float, dy: float) -> None:
        s = self.session
        if self._drag_mode is None or s.selection is None:
            return
        ax, ay = self._anchor
        rx, ry = ax + dx * self.scale, ay + dy * self.scale
        state = gesture.get_current_event_state()
        square = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if self._space and self._drag_mode in ("new", "move"):
            mdx, mdy = rx - self._last[0], ry - self._last[1]
            s.selection = s.selection.moved(mdx, mdy)
        elif self._drag_mode == "new":
            ex, ey = (square_end(ax, ay, rx, ry) if square else (rx, ry))
            s.selection = Selection(s.selection.x1, s.selection.y1, ex, ey)
        elif self._drag_mode == "move":
            s.selection = self._drag_start.moved(rx - ax, ry - ay)
        else:
            s.selection = self._drag_start.resized(self._drag_mode, rx, ry, square)
        s.selection = s.selection.clamped(0, 0, s.surface.get_width(), s.surface.get_height()) if self._drag_mode == "move" or self._space else s.selection
        self._last = (rx, ry)
        s.redraw()

    def _drag_end(self, *_a) -> None:
        s = self.session
        if s.selection and s.selection.is_empty and self._drag_mode == "new":
            s.selection = None
        elif s.selection:
            s.selection = s.selection.normalised()
        self._drag_mode = None
        s.redraw()

    def _click(self, gesture: Gtk.GestureClick, n_press: int, lx: float, ly: float) -> None:
        s = self.session
        rx, ry = self.to_root(lx, ly)
        if s.mode == "window":
            win = s.window_at(rx, ry)
            if win:
                x, y, w, h = win.rect
                s.selection = Selection(x, y, x + w, y + h).clamped(0, 0, s.surface.get_width(), s.surface.get_height())
                s.confirm()
        elif n_press >= 2 and s.selection and s.selection.hit(rx, ry):
            s.confirm()

    def _key(self, _c, keyval: int, _code: int, state: Gdk.ModifierType) -> bool:
        s = self.session
        step = 10 if state & Gdk.ModifierType.SHIFT_MASK else 1
        if keyval == Gdk.KEY_Escape:
            s.cancel()
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            s.confirm()
        elif keyval == Gdk.KEY_space:
            self._space = True
        elif keyval == Gdk.KEY_Left:
            s.nudge(-step, 0)
        elif keyval == Gdk.KEY_Right:
            s.nudge(step, 0)
        elif keyval == Gdk.KEY_Up:
            s.nudge(0, -step)
        elif keyval == Gdk.KEY_Down:
            s.nudge(0, step)
        elif keyval in (Gdk.KEY_a, Gdk.KEY_A) and state & Gdk.ModifierType.CONTROL_MASK:
            s.selection = Selection(0, 0, s.surface.get_width(), s.surface.get_height()); s.redraw()
        else:
            return False
        return True

    def _key_up(self, _c, keyval: int, *_a) -> None:
        if keyval == Gdk.KEY_space:
            self._space = False
