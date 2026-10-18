"""Turns pointer input on the stage into annotations, selections and undoable edits."""
from __future__ import annotations
import logging
from typing import Callable

import cairo
from gi.repository import Gdk, GLib, Gtk, Graphene

from . import tools
from ..model.annotations import (Annotation, Style, draw, _paint_eraser_ghost, area_path, constrain_square,
                                 image_corners, normalise_angle)
from ..model.document import expansion_for, expanded_base, resized_page
from ..model.undo import (AddLayer, RemoveLayer, RemoveLayers, EditAnnotation, SetVisible, MoveLayer, TransformBase,
                          SetPageFill, Compound)

LOG = logging.getLogger("linscreencapture.editor")
ACCENT = (0x4c / 255, 0x9d / 255, 1.0)
HANDLE_PX = 9          # on-screen handle diameter (round handles)
HIT_PX = 7             # on-screen hit tolerance around a handle


class EditorController:
    def __init__(self, window):
        self.win = window
        self.stage = window.stage
        self.state = window.state
        self.settings = window.settings
        self.selected_id: int | None = None
        self.on_selection: list[Callable[[int | None], None]] = []
        self.preview: Annotation | None = None
        self._points: list[tuple[float, float]] = []
        self._mode: str | None = None          # draw | stroke | move | handle:<name> | crop | pan
        self.all_selected = False               # Ctrl+A: every layer (Ctrl+C copies the flattened image, Delete removes all)
        self.space_pan = False                  # Space held: a drag pans instead of drawing
        self._pan_from = (0.0, 0.0)
        self._pan_start = (0.0, 0.0)
        self.area: Annotation | None = None     # a marked region (kind "cutout": shape box | round | points)
        self._chain: list[tuple[float, float]] = []   # Point chain in progress
        self._hover: tuple[float, float] | None = None
        self._start = (0.0, 0.0)
        self._orig: Annotation | None = None   # copy of the selected annotation when a move/handle drag began
        self._hidden_layer = None
        self._pending_callout: Annotation | None = None
        self.crop_rect: tuple[int, int, int, int] | None = None   # pending crop (image px)
        self.eyedropper = False                                    # next click samples a colour
        self._suppress_click = False                               # a drag just ended: its release is not a click

        canvas = self.stage.canvas
        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        canvas.add_controller(drag)
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", self._click)
        canvas.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        canvas.add_controller(motion)
        self.stage.extra_draw = self._draw_overlay
        self.stage.on_click_outside = self.clicked_outside
        self.state.connect("notify::tool", lambda *_: self._tool_changed())
        self.state.connect("notify::colour", lambda *_: self._colour_changed())

    # -- helpers -----------------------------------------------------------
    @property
    def doc(self):
        return self.win.document

    @property
    def undo(self):
        return self.win.undo

    def _ready(self) -> bool:
        return self.doc is not None and not self.doc.empty and self.undo is not None and not self.state.library

    def to_image(self, cx: float, cy: float) -> tuple[float, float]:
        ox, oy = self.stage.image_origin()
        z = self.state.zoom
        return (cx - ox) / z, (cy - oy) / z

    def style_for(self, tool: str) -> Style:
        st = self.settings.tool_style(tool)
        st.colour = self.state.colour
        return st

    def selected_layer(self):
        return self.doc.find_layer(self.selected_id) if (self.doc and self.selected_id is not None) else None

    def select(self, layer_id: int | None, notify: bool = True) -> None:
        if layer_id == self.selected_id and not self.all_selected:
            return
        self.all_selected = False
        self.selected_id = layer_id
        self.stage.canvas.queue_draw()
        if notify:
            for cb in list(self.on_selection):
                cb(layer_id)

    def select_all(self) -> bool:
        """Ctrl+A: mark every layer; Ctrl+C then copies the whole flattened image, Delete removes all layers."""
        if not self._ready() or not self.doc.layers:
            return False
        self.stage.cancel_text_entry()
        self.selected_id = None
        self.all_selected = True
        if self.state.tool not in ("select", "move"):
            self.state.tool = "select"           # _tool_changed keeps all_selected for Select
        self.stage.canvas.queue_draw()
        for cb in list(self.on_selection):
            cb(None)
        return True

    def set_space_pan(self, on: bool) -> None:
        self.space_pan = on
        if self._mode is None:
            self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name("grab") if on else None)

    def _commit(self, cmd, select_new: bool = True) -> None:
        self.all_selected = False
        self.undo.do(cmd)
        self._grow_page_for(getattr(cmd, "layer", None))
        if select_new and isinstance(cmd, AddLayer) and cmd.layer is not None:
            self.selected_id = cmd.layer.id
        self.win.refresh_document()
        for cb in list(self.on_selection):
            cb(self.selected_id)

    def _grow_page_for(self, layer) -> bool:
        """An image layer that now reaches past the page grows the page to hold it (plus ``EXPAND_PADDING``),
        in the same undo step as the edit that moved it there (docs/EDITOR-CANVAS-EXPANSION.md)."""
        doc = self.doc
        if layer is None or layer.annotation.kind != "image" or doc is None or doc.base is None:
            return False
        left, top, right, bottom = expansion_for(doc.width, doc.height, layer.annotation.bounding_box())
        if not (left or top or right or bottom):
            return False
        new = expanded_base(doc.base, left, top, right, bottom)
        self.undo.amend(TransformBase(new, lambda x, y: (x + left, y + top), label="Enlarge page"))
        if self.area is not None:
            self.area.move_by(left, top)
        if self.crop_rect is not None:
            x, y, w, h = self.crop_rect
            self.crop_rect = (x + left, y + top, w, h)
        z = self.state.zoom
        if left or top:                                   # keep the picture still on screen
            GLib.idle_add(lambda: (self.stage.scroll_by(left * z, top * z), False)[1])
        LOG.debug("page grown by l%d t%d r%d b%d to %dx%d", left, top, right, bottom, doc.width, doc.height)
        if not getattr(self, "_grew_once", False):
            self._grew_once = True
            self.win.toast("Page enlarged to fit the image · Ctrl+Z undoes", timeout=3)
        return True

    def _modifiers(self, gesture) -> tuple[bool, bool]:
        st = gesture.get_current_event_state()
        return bool(st & Gdk.ModifierType.SHIFT_MASK), bool(st & Gdk.ModifierType.CONTROL_MASK)

    # -- pointer -----------------------------------------------------------
    def _layer_at(self, x: float, y: float, below=None):
        """The topmost visible layer at (x, y); with ``below`` (a layer), the next one under it there, wrapping
        to the top (Ctrl+click picks a layer hidden beneath another)."""
        hits = [l for l in reversed(self.doc.layers) if l.visible and l.annotation.contains(x, y)]
        if below is not None and below in hits and len(hits) > 1:
            return hits[(hits.index(below) + 1) % len(hits)]
        return hits[0] if hits else None

    def _drag_begin(self, gesture, cx: float, cy: float) -> None:
        if not self._ready():
            return
        self.stage.cancel_text_entry()
        x, y = self.to_image(cx, cy)
        self._start = (x, y)
        tool = self.state.tool
        if tool in ("area_box", "area_round"):
            self._mode = "area"
            self.area = None
            self.preview = None
            return
        if tool == "hand" or self.space_pan:
            self._mode = "pan"
            self._pan_from = self.stage.pan_origin()
            self._pan_start = self._to_scroller(cx, cy)
            self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name("grabbing"))
            return
        if tool in ("select", "move"):
            layer = self.selected_layer()
            tol = HIT_PX / self.state.zoom
            hit = tools.handle_at(layer.annotation, x, y, tol, self.state.zoom) if layer is not None else None
            if hit:
                self._mode = "handle:" + hit
            else:
                _shift, ctrl = self._modifiers(gesture)
                layer = self._layer_at(x, y, below=self.selected_layer() if ctrl else None)
                self.select(layer.id if layer else None)
                self._mode = "move" if layer else None
            if layer is not None and self._mode:
                self._orig = layer.annotation.copy()
                self.preview = layer.annotation.copy()
                self._hidden_layer = layer
                layer.visible = False
                self.stage.refresh()
            return
        if tool in tools.STROKE_TOOLS:
            self._mode = "stroke"
            self._points = [(x, y)]
            self.preview = tools.annotation_from_points(tool, self._points, self.style_for(tool))
        elif tool in tools.DRAG_TOOLS:
            self._mode = "crop" if tool == "crop" else "draw"
            self.preview = None
        self.stage.canvas.queue_draw()

    def _drag_update(self, gesture, dx: float, dy: float) -> None:
        if self._mode is None:
            return
        if self._mode == "pan":
            _ok, sx, sy = gesture.get_start_point()
            nx, ny = self._to_scroller(sx + dx, sy + dy)
            self.stage.scroll_by(self._pan_start[0] - nx, self._pan_start[1] - ny, self._pan_from)
            return
        z = self.state.zoom
        x, y = self._start[0] + dx / z, self._start[1] + dy / z
        shift, ctrl = self._modifiers(gesture)
        tool = self.state.tool
        if self._mode == "area":
            x2, y2 = (constrain_square(self._start[0], self._start[1], x, y) if shift else (x, y))
            self.preview = Annotation("cutout", self._start[0], self._start[1], x2, y2, shape=tools.AREA_TOOLS[tool])
        elif self._mode == "stroke":
            self._points.append((x, y))
            self.preview = tools.annotation_from_points(tool, self._points, self.style_for(tool))
        elif self._mode == "draw":
            self.preview = tools.annotation_from_drag(tool, self._start[0], self._start[1], x, y, self.style_for(tool), shift, ctrl)
        elif self._mode == "crop":
            self.preview = Annotation("box", self._start[0], self._start[1], x, y, style=Style(colour="#4c9dff", width=1))
        elif self._mode == "move" and self._orig is not None:
            self.preview = self._orig.copy()
            self.preview.move_by(x - self._start[0], y - self._start[1])
        elif self._mode.startswith("handle:") and self._orig is not None:
            self.preview = self._orig.copy()
            for k, v in tools.handle_changes(self._orig, self._mode[7:], x, y, ctrl, shift).items():
                setattr(self.preview, k, v)
        self.stage.canvas.queue_draw()

    def _drag_end(self, gesture, dx: float, dy: float) -> None:
        mode, self._mode = self._mode, None
        if abs(dx) + abs(dy) > 2:
            # the button release that ends a drag also reaches the click gestures (same event, same
            # main-loop iteration); ignore it as a click, then forget the flag at the next idle
            self._suppress_click = True
            GLib.idle_add(self._clear_suppress)
        if mode is None:
            return
        if mode == "pan":
            self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name("grab") if (self.space_pan or self.state.tool == "hand") else None)
            return
        tool = self.state.tool
        preview, self.preview = self.preview, None
        if mode == "area":
            if preview is not None and preview.rect[2] >= 2 and preview.rect[3] >= 2:
                self.set_area(preview)
            else:
                self.cancel_area()
            self.stage.canvas.queue_draw()
            return
        if mode in ("draw", "stroke"):
            if preview is not None:
                if tool == "callout":
                    self._pending_callout = preview
                    self.stage.show_text_entry(preview.x1, preview.y1, "", self._callout_committed, self._text_cancelled)
                else:
                    self._commit(AddLayer(preview))
                    LOG.debug("added %s layer", preview.kind)
        elif mode == "crop":
            if preview is not None and preview.rect[2] >= 2 and preview.rect[3] >= 2:
                x, y, w, h = preview.rect
                self.crop_rect = (int(x), int(y), int(w), int(h))
                self.win.toast("Enter applies the crop · Esc cancels", timeout=2)
            else:
                self.crop_rect = None
        elif mode in ("move",) or mode.startswith("handle:"):
            layer = self._hidden_layer
            self._hidden_layer = None
            if layer is not None:
                layer.visible = True
                if preview is not None and (dx or dy):
                    changes = {k: getattr(preview, k) for k in ("x1", "y1", "x2", "y2")}
                    if preview.angle != layer.annotation.angle:
                        changes["angle"] = preview.angle
                    if preview.points:
                        changes["points"] = preview.points
                    label = "Move" if mode == "move" else "Rotate" if mode == "handle:rotate" else "Resize"
                    self._commit(EditAnnotation(layer, changes, label=label), select_new=False)
                else:
                    self.stage.refresh()
            self._orig = None
        self.stage.canvas.queue_draw()

    def _clear_suppress(self) -> bool:
        self._suppress_click = False
        return False

    def _to_scroller(self, cx: float, cy: float) -> tuple[float, float]:
        """Canvas point -> stage scroller coordinates (which do not move while the view scrolls)."""
        ok, pt = self.stage.canvas.compute_point(self.stage.scroller, Graphene.Point().init(cx, cy))
        return (pt.x, pt.y) if ok else (cx, cy)

    def clicked_outside(self) -> None:
        """A plain click on the empty stage: back to Select, nothing selected, pending text dropped."""
        if self._suppress_click or self._mode is not None or not self._ready():
            return
        self.stage.cancel_text_entry()
        self.eyedropper = False
        if self.state.tool != "select":
            self.state.tool = "select"          # _tool_changed also drops any pending crop
        self.select(None)
        self.stage.canvas.grab_focus()

    def _click(self, gesture, n_press: int, cx: float, cy: float) -> None:
        if not self._ready() or self._mode is not None:
            return
        x, y = self.to_image(cx, cy)
        if not self.stage.point_in_image(cx, cy) and not self.eyedropper:
            self.clicked_outside()              # the margin inside the canvas counts as empty stage too
            return
        if self.eyedropper:
            self.eyedropper = False
            colour = self.sample(x, y)
            if colour:
                self.state.colour = colour
                self.win.toast(f"Picked {colour.upper()}", timeout=2)
            self.stage.canvas.set_cursor(None)
            return
        tool = self.state.tool
        if tool == "area_points":
            self._chain_click(x, y, n_press)
            return
        if tool == "bucket":
            self.bucket_fill(x, y)
            return
        if tool == "text":
            self.stage.cancel_text_entry()
            self._pending_callout = None
            self.stage.show_text_entry(x, y, "", lambda text: self._text_committed(x, y, text), self._text_cancelled)
        elif tool == "step":
            n = sum(1 for l in self.doc.layers if l.annotation.kind == "step") + 1
            self._commit(AddLayer(tools.annotation_from_click("step", x, y, self.style_for("step"), number=n)))
        elif tool in ("select", "move") and n_press >= 2:
            layer = self._layer_at(x, y)
            if layer is not None and layer.annotation.kind in ("text", "callout"):
                a = layer.annotation
                self.stage.show_text_entry(a.x1, a.y1, a.text, lambda text, l=layer: self._retext(l, text), self._text_cancelled)

    def _motion(self, _c, cx: float, cy: float) -> None:
        if not self._ready():
            return
        tool = self.state.tool
        if self._chain:
            self._hover = self.to_image(cx, cy)
            self.stage.canvas.queue_draw()
        name = "crosshair"
        if self._mode == "pan":
            name = "grabbing"
        elif tool == "hand" or self.space_pan:
            name = "grab"
        elif tool == "text":
            name = "text"
        elif tool in ("select", "move"):
            x, y = self.to_image(cx, cy)
            layer = self.selected_layer()
            tol = HIT_PX / self.state.zoom
            h = tools.handle_at(layer.annotation, x, y, tol, self.state.zoom) if layer else None
            if h == "rotate":
                name = "grab"
            elif h and layer.annotation.kind == "image" and layer.annotation.angle:
                name = "move"                   # a turned frame: the axis cursors would point the wrong way
            elif h in ("nw", "se"):
                name = "nwse-resize"
            elif h in ("ne", "sw"):
                name = "nesw-resize"
            elif h in ("n", "s"):
                name = "ns-resize"
            elif h in ("e", "w"):
                name = "ew-resize"
            elif h:
                name = "move"
            else:
                name = "move" if self._layer_at(x, y) else "default"
        self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name(name))

    # -- area tool (box / round / point chain) ----------------------------------
    CHAIN_CLOSE_PX = 9

    def _chain_click(self, x: float, y: float, n_press: int) -> None:
        if not self._chain:
            self.cancel_area()
            self._chain = [(x, y)]
            self.win.toast("Click more points · click the first point (or double-click) to close the chain · Esc cancels", timeout=4)
            self.stage.canvas.queue_draw()
            return
        fx, fy = self._chain[0]
        near_first = abs(x - fx) <= self.CHAIN_CLOSE_PX / self.state.zoom and abs(y - fy) <= self.CHAIN_CLOSE_PX / self.state.zoom
        if (near_first or n_press >= 2) and len(self._chain) >= 3:
            pts = list(self._chain)
            if n_press >= 2 and len(pts) > 3 and abs(pts[-1][0] - pts[-2][0]) < 1 and abs(pts[-1][1] - pts[-2][1]) < 1:
                pts.pop()                      # the first click of a double-click already added this point
            self._chain = []
            self._hover = None
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            self.set_area(Annotation("cutout", min(xs), min(ys), max(xs), max(ys), shape="points", points=pts))
            return
        if n_press >= 2:
            return
        self._chain.append((x, y))
        self.stage.canvas.queue_draw()

    def chain_pop(self) -> bool:
        """Backspace: remove the last point of the chain in progress."""
        if not self._chain:
            return False
        self._chain.pop()
        self.stage.canvas.queue_draw()
        return True

    def set_area(self, a: Annotation) -> None:
        self.area = a
        self.select(None)
        self.stage.canvas.queue_draw()
        self.win.toast("Area marked · Ctrl+C copies it · Enter crops to it · Delete clears it · Esc drops it", timeout=4)

    def cancel_area(self) -> bool:
        had = self.area is not None or bool(self._chain)
        self.area = None
        self._chain = []
        self._hover = None
        if had:
            self.stage.canvas.queue_draw()
        return had

    def area_bounds(self) -> tuple[int, int, int, int] | None:
        """Integer (x, y, w, h) of the marked area clamped to the image, or None."""
        a = self.area
        if a is None or self.doc is None:
            return None
        if a.shape == "points":
            xs = [p[0] for p in a.points]; ys = [p[1] for p in a.points]
            x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        else:
            x, y, w, h = a.rect
        import math
        x0, y0 = max(0, int(math.floor(x))), max(0, int(math.floor(y)))
        x1, y1 = min(self.doc.width, int(math.ceil(x + w))), min(self.doc.height, int(math.ceil(y + h)))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return None
        return x0, y0, x1 - x0, y1 - y0

    def area_surface(self):
        """The marked region of the composite as its own surface (outside the shape: transparent)."""
        b = self.area_bounds()
        comp = self.stage.composite
        if b is None or comp is None:
            return None
        x, y, w, h = b
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(out)
        cr.set_source_surface(comp, -x, -y)
        cr.paint()
        if self.area.shape != "box":
            cr.translate(-x, -y)
            cr.set_operator(cairo.OPERATOR_DEST_IN)
            cr.set_source_rgba(0, 0, 0, 1)
            if area_path(cr, self.area):
                cr.fill()
        out.flush()
        return out

    def clear_area(self) -> bool:
        """Delete with an area: the pixels inside become transparent (a Cutout layer, undoable)."""
        if self.area is None or not self._ready():
            return False
        a = self.area.copy()
        a.style = Style(opacity=1.0)
        self.cancel_area()
        self._commit(AddLayer(a, label="Clear area"))
        self.win.toast("Cleared the area · Ctrl+Z restores it", timeout=2)
        return True

    def crop_to_area(self) -> bool:
        if self.area is None or not self._ready():
            return False
        a, _ = self.area, self.cancel_area()
        self.win.image_op("crop-area", a)
        return True

    def _draw_area_overlay(self, cr, ox: float, oy: float, z: float) -> None:
        cr.save()
        cr.translate(ox, oy)
        cr.scale(z, z)
        if self.area is not None:
            if area_path(cr, self.area):
                cr.set_source_rgba(*ACCENT, 0.12)
                cr.fill_preserve()
                cr.set_source_rgba(*ACCENT, 0.95)
                cr.set_line_width(1.5 / z)
                cr.set_dash([6 / z, 4 / z])
                cr.stroke()
        if self._chain:
            cr.set_source_rgba(*ACCENT, 0.95)
            cr.set_line_width(1.5 / z)
            cr.move_to(*self._chain[0])
            for p in self._chain[1:]:
                cr.line_to(*p)
            if self._hover is not None:
                cr.line_to(*self._hover)
            cr.stroke()
            r = 4 / z
            for n, (px, py) in enumerate(self._chain):
                cr.arc(px, py, r * (1.6 if n == 0 else 1.0), 0, 6.2832)
                cr.set_source_rgb(1, 1, 1) if n == 0 else cr.set_source_rgba(*ACCENT, 1)
                cr.fill_preserve()
                cr.set_source_rgba(*ACCENT, 1)
                cr.set_line_width(1.5 / z)
                cr.stroke()
        cr.restore()

    # -- text ----------------------------------------------------------------
    def _text_committed(self, x: float, y: float, text: str) -> None:
        if text.strip():
            self._commit(AddLayer(tools.annotation_from_click("text", x, y, self.style_for("text"), text=text)))

    def _callout_committed(self, text: str) -> None:
        a, self._pending_callout = self._pending_callout, None
        if a is not None and text.strip():
            a.text = text
            self._commit(AddLayer(a))

    def _retext(self, layer, text: str) -> None:
        if text.strip() and text != layer.annotation.text:
            self._commit(EditAnnotation(layer, {"text": text}, label="Edit text"), select_new=False)

    def _text_cancelled(self) -> None:
        self._pending_callout = None

    def bucket_fill(self, x: float, y: float) -> bool:
        """Paint bucket at image point (x, y): flood what is visible there (``app/bucket.py``) in the current colour,
        as a ``bucket`` layer (undoable; the pixels beneath stay as they were)."""
        from . import bucket
        from ..model.annotations import parse_hex
        comp = self.stage.composite
        if comp is None or not self._ready():
            return False
        style = self.style_for("bucket")
        s = self.settings
        result = bucket.fill(comp, int(x), int(y), parse_hex(style.colour), s.bucket_tolerance, s.bucket_contiguous,
                             style.opacity)
        if result is None:
            return False
        surf, x0, y0 = result
        a = Annotation("bucket", x0, y0, x0 + surf.get_width(), y0 + surf.get_height(), style=style, surface=surf)
        self._commit(AddLayer(a, label="Bucket fill"), select_new=False)
        return True

    def sample(self, x: float, y: float) -> str | None:
        comp = self.stage.composite
        if comp is None:
            return None
        ix, iy = int(x), int(y)
        if not (0 <= ix < comp.get_width() and 0 <= iy < comp.get_height()):
            return None
        comp.flush()
        i = iy * comp.get_stride() + ix * 4
        b, g, r = comp.get_data()[i:i + 3]
        return f"#{r:02x}{g:02x}{b:02x}"

    def start_eyedropper(self) -> None:
        if self._ready():
            self.eyedropper = True
            self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name("crosshair"))
            self.win.toast("Click the image to pick a colour", timeout=2)

    def apply_crop(self) -> bool:
        if self.area is not None:
            return self.crop_to_area()
        if self.crop_rect is None or not self._ready():
            return False
        rect, self.crop_rect = self.crop_rect, None
        self.win.image_op("crop", *rect)
        return True

    def cancel_crop(self) -> bool:
        if self.crop_rect is None:
            return False
        self.crop_rect = None
        self.stage.canvas.queue_draw()
        return True

    # -- commands from the UI ---------------------------------------------
    def delete_selected(self) -> bool:
        if self.area is not None:
            return self.clear_area()
        if self.all_selected and self.doc is not None and self.doc.layers:
            layers = list(self.doc.layers)
            self.selected_id = None
            self._commit(RemoveLayers(layers), select_new=False)
            self.win.toast(f"Deleted {len(layers)} layers · Ctrl+Z restores them", timeout=3)
            return True
        layer = self.selected_layer()
        if layer is None:
            return False
        self.selected_id = None
        self._commit(RemoveLayer(layer), select_new=False)
        return True

    def duplicate_selected(self) -> bool:
        layer = self.selected_layer()
        if layer is None:
            return False
        self._commit(AddLayer(tools.duplicate(layer.annotation)))
        return True

    def set_visible(self, layer_id: int, visible: bool) -> None:
        layer = self.doc.find_layer(layer_id) if self.doc else None
        if layer is not None and layer.visible != visible:
            self._commit(SetVisible(layer, visible), select_new=False)

    # -- arrange (right rail EDIT: to front, forward, backward, to back) -------------
    ARRANGE = ("front", "forward", "backward", "back")

    def _arrange_index(self, where: str) -> int | None:
        layer = self.selected_layer()
        if layer is None or not self._ready():
            return None
        i, top = self.doc.layers.index(layer), len(self.doc.layers) - 1
        target = {"front": top, "forward": i + 1, "backward": i - 1, "back": 0}[where]
        target = max(0, min(top, target))
        return None if target == i else target

    def can_arrange(self, where: str) -> bool:
        return self._arrange_index(where) is not None

    def arrange_selected(self, where: str) -> bool:
        """Move the selected layer in the stack (layers[0] is the bottom); one undo step."""
        index = self._arrange_index(where)
        if index is None:
            return False
        labels = {"front": "Bring to front", "forward": "Bring forward", "backward": "Send backward", "back": "Send to back"}
        self._commit(MoveLayer(self.selected_layer(), index, label=labels[where]), select_new=False)
        return True

    def move_layer(self, layer_id: int, index: int) -> None:
        layer = self.doc.find_layer(layer_id) if self.doc else None
        if layer is not None:
            self._commit(MoveLayer(layer, index), select_new=False)

    # -- image layer size (the header strip's W / H / % controls) -----------------
    def set_layer_size(self, w: float, h: float) -> bool:
        """Resize the selected layer to ``w`` × ``h`` image px, anchored at its top-left corner."""
        layer = self.selected_layer()
        if layer is None or self.undo is None:
            return False
        x, y, cw, ch = layer.annotation.rect
        w, h = max(1.0, round(w)), max(1.0, round(h))
        if (round(cw), round(ch)) == (w, h):
            return False
        if layer.annotation.angle:                        # a turned layer keeps its centre (its corner has moved)
            x, y = x + (cw - w) / 2, y + (ch - h) / 2
        self._commit(EditAnnotation(layer, {"x1": x, "y1": y, "x2": x + w, "y2": y + h}, label="Resize"), select_new=False)
        return True

    def set_layer_angle(self, degrees: float) -> bool:
        """Turn the selected image layer to ``degrees`` clockwise about its centre."""
        layer = self.selected_layer()
        if layer is None or self.undo is None or layer.annotation.kind != "image":
            return False
        deg = normalise_angle(degrees)
        if abs(deg - layer.annotation.angle) < 0.005:
            return False
        self._commit(EditAnnotation(layer, {"angle": deg}, label="Rotate"), select_new=False)
        return True

    def rotate_selected(self, delta: float) -> bool:
        layer = self.selected_layer()
        return layer is not None and self.set_layer_angle(layer.annotation.angle + delta)

    # -- the page (right panel: Page) ----------------------------------------------
    def apply_page(self, width: int, height: int, fill: str | None,
                   anchor: tuple[float, float] = (0.5, 0.5)) -> bool:
        """The Page dialog's Apply: the page size (the picture stays at ``anchor``; layers keep their place on it)
        and the fill behind its transparent parts (None: transparent), as one undo step."""
        doc = self.doc
        if not self._ready():
            return False
        steps = []
        if (int(width), int(height)) != (doc.width, doc.height):
            new, dx, dy = resized_page(doc.base, width, height, anchor)
            steps.append(TransformBase(new, lambda x, y: (x + dx, y + dy), label="Page size"))
        if fill != doc.background:
            steps.append(SetPageFill(fill))
        if not steps:
            return False
        self.cancel_crop()
        self.cancel_area()
        self.all_selected = False
        self.undo.do(steps[0] if len(steps) == 1 else Compound(steps, label="Page settings"))
        self.win.refresh_document()
        return True

    def set_page_size(self, width: int, height: int, anchor: tuple[float, float] = (0.5, 0.5)) -> bool:
        return self.apply_page(width, height, self.doc.background if self.doc else None, anchor)

    def set_page_fill(self, colour: str | None) -> bool:
        doc = self.doc
        return doc is not None and self.apply_page(doc.width, doc.height, colour)

    def natural_size(self) -> tuple[int, int] | None:
        """The selected image layer's own pixel size (100 %)."""
        layer = self.selected_layer()
        s = layer.annotation.surface if layer is not None and layer.annotation.kind == "image" else None
        return (s.get_width(), s.get_height()) if s is not None else None

    def fit_selected(self) -> bool:
        """Scale the selected image layer to fit the canvas, keeping its proportions, and centre it."""
        layer = self.selected_layer()
        if layer is None or self.undo is None or not self._ready():
            return False
        a = layer.annotation
        _x, _y, w, h = a.rect
        if w <= 0 or h <= 0:
            return False
        _sx, _sy, aw, ah = tools.selection_rect(a)           # the picture's own extent (turned, if it is)
        _bx, _by, bw, _bh = a.bounding_box()
        e = max(0.0, (bw - aw) / 2)                          # its shadow fits inside the page too (no growth)
        s = min(max(1.0, self.doc.width - 2 * e) / aw, max(1.0, self.doc.height - 2 * e) / ah)
        nw, nh = w * s, h * s
        x, y = (self.doc.width - nw) / 2, (self.doc.height - nh) / 2
        self._commit(EditAnnotation(layer, {"x1": x, "y1": y, "x2": x + nw, "y2": y + nh}, label="Fit"), select_new=False)
        return True

    def nudge_selected(self, dx: float, dy: float) -> bool:
        """Arrow keys: move the selected layer by (dx, dy) image px."""
        layer = self.selected_layer()
        if layer is None or self.undo is None or self._mode is not None:
            return False
        self._commit(EditAnnotation(layer, tools.move_changes(layer.annotation, dx, dy), label="Move"), select_new=False)
        return True

    def apply_style(self, changes: dict) -> None:
        """Change style fields of the selected annotation (from the header strip or the palette)."""
        layer = self.selected_layer()
        if layer is None or self.undo is None:
            return
        st = layer.annotation.style.copy()
        for k, v in changes.items():
            setattr(st, k, v)
        self._commit(EditAnnotation(layer, {"style": st}, label="Style"), select_new=False)

    def _tool_changed(self) -> None:
        self.stage.cancel_text_entry()
        self.eyedropper = False
        if self.state.tool != "crop":
            self.cancel_crop()
        if self.state.tool not in tools.AREA_TOOLS:
            self.cancel_area()
        if self.state.tool not in ("select", "move"):
            self.select(None)
        if self.state.tool == "hand":
            self.stage.canvas.set_cursor(Gdk.Cursor.new_from_name("grab"))

    def _colour_changed(self) -> None:
        layer = self.selected_layer()
        if layer is not None and layer.annotation.kind not in ("blur", "pixelate"):
            self.apply_style({"colour": self.state.colour})

    # -- overlay drawing ----------------------------------------------------
    @staticmethod
    def _frame_path(cr: cairo.Context, a: Annotation, ox: float, oy: float, z: float) -> None:
        """An image layer's (turned) frame in canvas px."""
        pts = [(ox + px * z, oy + py * z) for px, py in image_corners(a)]
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.close_path()

    def _draw_size_readout(self, cr: cairo.Context, a: Annotation, ox: float, oy: float, z: float, angle: bool = False) -> None:
        """While an image layer is resized or turned: its frame and a "W × H px · N %" (or "N°") label under it."""
        x, y, w, h = a.rect
        cr.save()
        cr.set_source_rgba(*ACCENT, 0.95)
        cr.set_line_width(1)
        self._frame_path(cr, a, ox, oy, z)
        cr.stroke()
        text = f"{round(w)} × {round(h)} px"
        if a.surface is not None and a.surface.get_width() > 0:
            text += f" · {round(100 * w / a.surface.get_width())} %"
        if angle:
            text = f"{a.angle:g}°"
        x, y, w, h = tools.selection_rect(a)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)
        ext = cr.text_extents(text)
        bx, by = ox + (x + w / 2) * z - ext.width / 2 - 6, oy + (y + h) * z + 8
        cr.set_source_rgba(0.08, 0.09, 0.11, 0.85)
        cr.rectangle(bx, by, ext.width + 12, 18)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(bx + 6 - ext.x_bearing, by + 9 - ext.height / 2 - ext.y_bearing)
        cr.show_text(text)
        cr.restore()

    def _draw_overlay(self, cr: cairo.Context, ox: float, oy: float, z: float) -> None:
        """Preview and selection, drawn on top of the composite in canvas coordinates."""
        if self.preview is not None:
            cr.save()
            cr.translate(ox, oy)
            cr.scale(z, z)
            p = self.preview
            if p.kind == "cutout":                   # an area being dragged
                if area_path(cr, p):
                    cr.set_source_rgba(*ACCENT, 0.12); cr.fill_preserve()
                    cr.set_source_rgba(*ACCENT, 0.95); cr.set_line_width(1.5 / z); cr.set_dash([6 / z, 4 / z]); cr.stroke()
            elif p.kind in ("blur", "pixelate") or self._mode == "crop":
                x, y, w, h = p.rect
                cr.set_source_rgba(*ACCENT, 0.9)
                cr.set_line_width(1.5 / z)
                cr.set_dash([6 / z, 4 / z])
                cr.rectangle(x, y, w, h)
                cr.stroke()
            elif p.kind == "eraser":
                _paint_eraser_ghost(p, cr)          # clearing the canvas would also clear the checkerboard
            else:
                if (self._mode in ("draw", "stroke", "handle:rotate")) and p.style.shadow:
                    # full colour while drawing; only the shadow waits for release: its blur changes with every
                    # motion and costs 15-20 ms a frame on large shapes (moves reuse the cached shadow instead;
                    # a turn changes the silhouette every frame, so it waits too)
                    p = p.copy()
                    p.style.shadow = False
                draw(p, cr, None)                   # the real style: what is drawn is what is committed
            cr.restore()
            if p.kind == "image" and self._mode is not None and self._mode.startswith("handle:"):
                self._draw_size_readout(cr, p, ox, oy, z, angle=self._mode == "handle:rotate")
        if (self.area is not None or self._chain) and self._ready():
            self._draw_area_overlay(cr, ox, oy, z)
        if self.all_selected and self._mode is None and self._ready():
            comp = self.stage.composite
            cr.save()
            cr.set_source_rgba(*ACCENT, 0.9)
            cr.set_line_width(1.5)
            cr.set_dash([6, 4])
            cr.rectangle(ox + 0.75, oy + 0.75, comp.get_width() * z - 1.5, comp.get_height() * z - 1.5)
            cr.stroke()
            cr.set_line_width(1)
            cr.set_dash([3, 3])
            for l in self.doc.layers:
                if l.visible:
                    x, y, w, h = tools.selection_rect(l.annotation)
                    cr.rectangle(ox + x * z + 0.5, oy + y * z + 0.5, w * z, h * z)
            cr.stroke()
            cr.restore()
        if self.crop_rect is not None and self._mode is None:
            x, y, w, h = self.crop_rect
            cr.save()
            cr.set_source_rgba(0, 0, 0, 0.45)                       # veil outside the pending crop
            comp = self.stage.composite
            cr.rectangle(ox, oy, comp.get_width() * z, comp.get_height() * z)
            cr.rectangle(ox + x * z, oy + y * z, w * z, h * z)
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.fill()
            cr.set_fill_rule(cairo.FILL_RULE_WINDING)
            cr.set_source_rgb(*ACCENT)
            cr.set_line_width(1.5)
            cr.rectangle(ox + x * z + 0.75, oy + y * z + 0.75, w * z, h * z)
            cr.stroke()
            cr.restore()
        layer = self.selected_layer() if (self._mode is None and self._ready()) else None
        if layer is None:
            return
        a = layer.annotation
        x, y, w, h = tools.selection_rect(a)
        handles = tools.handles_for(a, z)
        cr.save()
        cr.set_source_rgba(*ACCENT, 0.9)
        cr.set_line_width(1)
        if self.settings.selection_frame:                  # optional dashed frame (off by default)
            cr.set_dash([5, 3])
            cr.rectangle(ox + x * z + 0.5, oy + y * z + 0.5, w * z, h * z)
            cr.stroke()
            cr.set_dash([])
        elif not handles:                                  # no handles to show: four quiet corner ticks
            t = 7
            x0, y0, x1, y1 = ox + x * z + 0.5, oy + y * z + 0.5, ox + (x + w) * z - 0.5, oy + (y + h) * z - 0.5
            for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                cr.move_to(cx, cy + sy * t); cr.line_to(cx, cy); cr.line_to(cx + sx * t, cy)
            cr.stroke()
        if a.kind == "image":                              # the picture's own (turned) frame, and the rotate stem
            if not self.settings.selection_frame:
                self._frame_path(cr, a, ox, oy, z)
                cr.stroke()
            if "rotate" in handles:
                tx, ty = handles["n"]
                rx, ry = handles["rotate"]
                cr.move_to(ox + tx * z, oy + ty * z)
                cr.line_to(ox + rx * z, oy + ry * z)
                cr.stroke()
        for name, (hx, hy) in handles.items():
            sx, sy = ox + hx * z, oy + hy * z
            cr.new_sub_path()
            cr.arc(sx, sy, HANDLE_PX / 2 + (0.5 if name == "rotate" else 0), 0, 6.2832)   # round handles
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgb(*ACCENT)
            cr.set_line_width(1.5)
            cr.stroke()
        cr.restore()
