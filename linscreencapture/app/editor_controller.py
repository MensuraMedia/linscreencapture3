"""Turns pointer input on the stage into annotations, selections and undoable edits."""
from __future__ import annotations
import logging
from typing import Callable

import cairo
from gi.repository import Gdk, Gtk

from . import tools
from ..model.annotations import Annotation, Style, draw
from ..model.undo import AddLayer, RemoveLayer, EditAnnotation, SetVisible, MoveLayer

LOG = logging.getLogger("linscreencapture.editor")
ACCENT = (0x4c / 255, 0x9d / 255, 1.0)
HANDLE_PX = 8          # on-screen handle size
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
        self._mode: str | None = None          # draw | stroke | move | handle:<name> | crop
        self._start = (0.0, 0.0)
        self._orig: Annotation | None = None   # copy of the selected annotation when a move/handle drag began
        self._hidden_layer = None
        self._pending_callout: Annotation | None = None

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
        if layer_id == self.selected_id:
            return
        self.selected_id = layer_id
        self.stage.canvas.queue_draw()
        if notify:
            for cb in list(self.on_selection):
                cb(layer_id)

    def _commit(self, cmd, select_new: bool = True) -> None:
        self.undo.do(cmd)
        if select_new and isinstance(cmd, AddLayer) and cmd.layer is not None:
            self.selected_id = cmd.layer.id
        self.win.refresh_document()
        for cb in list(self.on_selection):
            cb(self.selected_id)

    def _modifiers(self, gesture) -> tuple[bool, bool]:
        st = gesture.get_current_event_state()
        return bool(st & Gdk.ModifierType.SHIFT_MASK), bool(st & Gdk.ModifierType.CONTROL_MASK)

    # -- pointer -----------------------------------------------------------
    def _layer_at(self, x: float, y: float):
        for layer in reversed(self.doc.layers):
            if layer.visible and layer.annotation.contains(x, y):
                return layer
        return None

    def _drag_begin(self, gesture, cx: float, cy: float) -> None:
        if not self._ready():
            return
        self.stage.cancel_text_entry()
        x, y = self.to_image(cx, cy)
        self._start = (x, y)
        tool = self.state.tool
        if tool in ("select", "move"):
            layer = self.selected_layer()
            tol = HIT_PX / self.state.zoom
            if layer is not None and tools.handle_at(layer.annotation, x, y, tol):
                self._mode = "handle:" + tools.handle_at(layer.annotation, x, y, tol)
            else:
                layer = self._layer_at(x, y)
                self.select(layer.id if layer else None)
                self._mode = "move" if layer else None
            if layer is not None and self._mode:
                self._orig = Annotation.from_dict(layer.annotation.to_dict())
                self.preview = Annotation.from_dict(layer.annotation.to_dict())
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
        z = self.state.zoom
        x, y = self._start[0] + dx / z, self._start[1] + dy / z
        shift, ctrl = self._modifiers(gesture)
        tool = self.state.tool
        if self._mode == "stroke":
            self._points.append((x, y))
            self.preview = tools.annotation_from_points(tool, self._points, self.style_for(tool))
        elif self._mode == "draw":
            self.preview = tools.annotation_from_drag(tool, self._start[0], self._start[1], x, y, self.style_for(tool), shift, ctrl)
        elif self._mode == "crop":
            self.preview = Annotation("box", self._start[0], self._start[1], x, y, style=Style(colour="#4c9dff", width=1))
        elif self._mode == "move" and self._orig is not None:
            self.preview = Annotation.from_dict(self._orig.to_dict())
            self.preview.move_by(x - self._start[0], y - self._start[1])
        elif self._mode.startswith("handle:") and self._orig is not None:
            self.preview = Annotation.from_dict(self._orig.to_dict())
            for k, v in tools.handle_changes(self._orig, self._mode[7:], x, y, ctrl).items():
                setattr(self.preview, k, v)
        self.stage.canvas.queue_draw()

    def _drag_end(self, gesture, dx: float, dy: float) -> None:
        mode, self._mode = self._mode, None
        if mode is None:
            return
        tool = self.state.tool
        preview, self.preview = self.preview, None
        if mode in ("draw", "stroke"):
            if preview is not None:
                if tool == "callout":
                    self._pending_callout = preview
                    self.stage.show_text_entry(preview.x1, preview.y1, "", self._callout_committed, self._text_cancelled)
                else:
                    self._commit(AddLayer(preview))
                    LOG.debug("added %s layer", preview.kind)
        elif mode == "crop":
            self.win.toast("Crop applies in Phase 5")
        elif mode in ("move",) or mode.startswith("handle:"):
            layer = self._hidden_layer
            self._hidden_layer = None
            if layer is not None:
                layer.visible = True
                if preview is not None and (dx or dy):
                    changes = {k: getattr(preview, k) for k in ("x1", "y1", "x2", "y2")}
                    if preview.points:
                        changes["points"] = preview.points
                    self._commit(EditAnnotation(layer, changes, label="Move" if mode == "move" else "Resize"), select_new=False)
                else:
                    self.stage.refresh()
            self._orig = None
        self.stage.canvas.queue_draw()

    def _click(self, gesture, n_press: int, cx: float, cy: float) -> None:
        if not self._ready() or self._mode is not None:
            return
        x, y = self.to_image(cx, cy)
        tool = self.state.tool
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
        name = "crosshair"
        if tool == "text":
            name = "text"
        elif tool in ("select", "move"):
            x, y = self.to_image(cx, cy)
            layer = self.selected_layer()
            tol = HIT_PX / self.state.zoom
            h = tools.handle_at(layer.annotation, x, y, tol) if layer else None
            if h in ("nw", "se"):
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

    # -- commands from the UI ---------------------------------------------
    def delete_selected(self) -> bool:
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

    def move_layer(self, layer_id: int, index: int) -> None:
        layer = self.doc.find_layer(layer_id) if self.doc else None
        if layer is not None:
            self._commit(MoveLayer(layer, index), select_new=False)

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
        if self.state.tool not in ("select", "move"):
            self.select(None)

    def _colour_changed(self) -> None:
        layer = self.selected_layer()
        if layer is not None and layer.annotation.kind not in ("blur", "pixelate"):
            self.apply_style({"colour": self.state.colour})

    # -- overlay drawing ----------------------------------------------------
    def _draw_overlay(self, cr: cairo.Context, ox: float, oy: float, z: float) -> None:
        """Preview and selection, drawn on top of the composite in canvas coordinates."""
        if self.preview is not None:
            cr.save()
            cr.translate(ox, oy)
            cr.scale(z, z)
            p = self.preview
            if p.kind in ("blur", "pixelate") or self._mode == "crop":
                x, y, w, h = p.rect
                cr.set_source_rgba(*ACCENT, 0.9)
                cr.set_line_width(1.5 / z)
                cr.set_dash([6 / z, 4 / z])
                cr.rectangle(x, y, w, h)
                cr.stroke()
            else:
                st = p.style.copy()
                st.opacity = 0.6 if self._mode in ("draw", "stroke") else 1.0
                draw(Annotation.from_dict({**p.to_dict(), "style": st.__dict__}), cr, None)
            cr.restore()
        layer = self.selected_layer() if (self._mode is None and self._ready()) else None
        if layer is None:
            return
        a = layer.annotation
        x, y, w, h = tools.selection_rect(a)
        cr.save()
        cr.set_source_rgba(*ACCENT, 0.9)
        cr.set_line_width(1)
        cr.set_dash([5, 3])
        cr.rectangle(ox + x * z + 0.5, oy + y * z + 0.5, w * z, h * z)
        cr.stroke()
        cr.set_dash([])
        for hx, hy in tools.handles_for(a).values():
            sx, sy = ox + hx * z, oy + hy * z
            cr.rectangle(sx - HANDLE_PX / 2, sy - HANDLE_PX / 2, HANDLE_PX, HANDLE_PX)
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgb(*ACCENT)
            cr.set_line_width(1.5)
            cr.stroke()
        cr.restore()
