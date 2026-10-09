"""Right rail: layers, colour palette, view (zoom), edit (copy, flatten), navigator, Settings."""
from __future__ import annotations
import cairo
from gi.repository import Gtk

from .widgets import (rail_button, group_label, hairline, SwatchGrid, LayerRow, PALETTE,
                      colour_class, rail_page, pin_width, ZoomPill)
from ..services import icon_loader
from ..app.view_state import ViewState

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56
EDIT_ITEMS = (("copy", "Copy", "win.copy"), ("stack-simple", "Flatten", "win.flatten"))


def _settings_button() -> Gtk.Button:
    b = Gtk.Button()
    bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    bb.append(icon_loader.icon("gear", 18))
    bb.append(Gtk.Label(label="Settings"))
    b.set_child(bb)
    b.add_css_class("text-btn")
    b.set_tooltip_text("Settings")
    b.update_property([Gtk.AccessibleProperty.LABEL], ["Settings"])
    b.set_action_name("app.preferences")
    b.set_halign(Gtk.Align.END)
    return b


def _layer_thumbnail(doc, layer):
    """A 40×28 texture: the annotation alone (or the base image) scaled to fit."""
    from gi.repository import Gdk, GLib
    from ..model.annotations import draw
    w, h = max(1, doc.width), max(1, doc.height)
    scale = min(40 / w, 28 / h)
    tw, th = max(1, int(w * scale)), max(1, int(h * scale))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 28)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0x2f / 255, 0x34 / 255, 0x3b / 255)
    cr.paint()
    cr.translate((40 - tw) / 2, (28 - th) / 2)
    cr.scale(scale, scale)
    if layer is None:
        if doc.base is not None:
            cr.set_source_surface(doc.base, 0, 0)
            cr.get_source().set_filter(cairo.FILTER_GOOD)
            cr.paint()
    else:
        a = layer.annotation
        if a.kind in ("blur", "pixelate"):
            x, y, bw, bh = a.rect
            cr.set_source_rgba(1, 1, 1, 0.5)
            cr.rectangle(x, y, bw, bh)
            cr.fill()
        else:
            draw(a, cr, None)
    surf.flush()
    return Gdk.MemoryTexture.new(40, 28, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                 GLib.Bytes.new(bytes(surf.get_data())), surf.get_stride())


class ColourPalette(Gtk.Box):
    """Quiet label row (eyedropper, custom colour) over round swatches; no card, no well."""

    def __init__(self, state: ViewState):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.state = state
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        lbl = group_label("Colour")
        lbl.set_hexpand(True)
        lbl.set_valign(Gtk.Align.CENTER)
        row.append(lbl)
        self.custom = rail_button("plus", "Custom colour", "win.custom-colour", classes=("small",), size=14)
        row.append(self.custom)
        row.append(rail_button("eyedropper", "Eyedropper", "win.eyedropper", classes=("small",), size=16))
        self.append(row)
        self.swatches = SwatchGrid(PALETTE, on_select=self._chosen)
        self.swatches.set_margin_start(2)
        self.append(self.swatches)
        state.connect("notify::colour", self._sync)
        self._sync()

    @property
    def current(self) -> str:
        return self.state.colour

    def _chosen(self, hx: str) -> None:
        self.state.colour = hx

    def _sync(self, *_a) -> None:
        self.swatches.select(self.state.colour)
        self.custom.set_tooltip_text(f"Custom colour · current {self.state.colour.upper()}")


class Navigator(Gtk.DrawingArea):
    """Thumbnail of the document with the visible viewport; click or drag to scroll the stage."""

    PAD = 8

    def __init__(self):
        super().__init__(content_height=116, hexpand=True)
        self.add_css_class("navigator")
        self.set_tooltip_text("Navigator · drag to move the view")
        self.stage = None
        self._thumb = None
        self._thumb_key = None
        self.set_draw_func(self._draw)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", lambda g, x, y: self._go(x, y))
        drag.connect("drag-update", lambda g, dx, dy: self._go(g.get_start_point()[1] + dx, g.get_start_point()[2] + dy))
        self.add_controller(drag)

    def attach(self, stage) -> None:
        self.stage = stage
        stage.on_change.append(self.queue_draw)
        stage.state.connect("notify::zoom", lambda *_: self.queue_draw())
        for adj in (stage.scroller.get_hadjustment(), stage.scroller.get_vadjustment()):
            adj.connect("value-changed", lambda *_: self.queue_draw())
            adj.connect("changed", lambda *_: self.queue_draw())
        stage.canvas.connect("resize", lambda *_: self.queue_draw())

    # -- geometry -------------------------------------------------------------
    def _frame(self):
        """(scale, tx, ty, tw, th) of the thumbnail inside the widget, or None without a document."""
        comp = self.stage.composite if self.stage else None
        if comp is None:
            return None
        w, h = self.get_width(), self.get_height()
        cw, ch = comp.get_width(), comp.get_height()
        scale = min((w - 2 * self.PAD) / cw, (h - 2 * self.PAD) / ch)
        tw, th = cw * scale, ch * scale
        return scale, (w - tw) / 2, (h - th) / 2, tw, th

    def visible_image_rect(self) -> tuple[float, float, float, float] | None:
        """The part of the image (in image px) currently inside the stage viewport."""
        st = self.stage
        comp = st.composite if st else None
        if comp is None:
            return None
        z = st.state.zoom
        ox, oy = st.image_origin()
        h, v = st.scroller.get_hadjustment(), st.scroller.get_vadjustment()
        vx0, vy0 = h.get_value(), v.get_value()
        vx1, vy1 = vx0 + h.get_page_size(), vy0 + v.get_page_size()
        x0, y0 = max(0.0, (vx0 - ox) / z), max(0.0, (vy0 - oy) / z)
        x1, y1 = min(float(comp.get_width()), (vx1 - ox) / z), min(float(comp.get_height()), (vy1 - oy) / z)
        if x1 <= x0 or y1 <= y0:      # not laid out yet: show everything
            return 0.0, 0.0, float(comp.get_width()), float(comp.get_height())
        return x0, y0, x1 - x0, y1 - y0

    # -- drawing --------------------------------------------------------------
    def _thumbnail(self, comp, tw: int, th: int):
        key = (id(comp), tw, th)
        if self._thumb_key != key:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, tw), max(1, th))
            cr = cairo.Context(surf)
            cr.scale(tw / comp.get_width(), th / comp.get_height())
            cr.set_source_surface(comp, 0, 0)
            cr.get_source().set_filter(cairo.FILTER_GOOD)
            cr.paint()
            self._thumb, self._thumb_key = surf, key
        return self._thumb

    def _draw(self, _area, cr, w, h) -> None:
        frame = self._frame()
        if frame is None:
            return
        scale, tx, ty, tw, th = frame
        thumb = self._thumbnail(self.stage.composite, int(tw), int(th))
        cr.set_source_surface(thumb, tx, ty)
        cr.paint()
        vis = self.visible_image_rect()
        if vis is None:
            return
        x, y, vw, vh = vis
        cr.set_source_rgba(0, 0, 0, 0.35)                      # dim what is outside the viewport
        cr.rectangle(tx, ty, tw, th)
        cr.rectangle(tx + x * scale, ty + y * scale, vw * scale, vh * scale)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.fill()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)
        cr.set_source_rgb(0x4c / 255, 0x9d / 255, 1.0)
        cr.set_line_width(1.5)
        cr.rectangle(tx + x * scale + 0.75, ty + y * scale + 0.75, max(2, vw * scale - 1.5), max(2, vh * scale - 1.5))
        cr.stroke()

    # -- navigation -----------------------------------------------------------
    def _go(self, px: float, py: float) -> None:
        """Centre the stage viewport on the image point under the pointer."""
        frame = self._frame()
        if frame is None:
            return
        scale, tx, ty, _tw, _th = frame
        st = self.stage
        z = st.state.zoom
        ox, oy = st.image_origin()
        ix, iy = (px - tx) / scale, (py - ty) / scale
        for adj, origin, coord in ((st.scroller.get_hadjustment(), ox, ix), (st.scroller.get_vadjustment(), oy, iy)):
            target = origin + coord * z - adj.get_page_size() / 2
            adj.set_value(max(adj.get_lower(), min(target, adj.get_upper() - adj.get_page_size())))


class PanelRail(Gtk.Stack):
    def __init__(self, state: ViewState):
        super().__init__(hhomogeneous=False, vhomogeneous=True, interpolate_size=True,
                         transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.set_hexpand(False)  # explicit: children with hexpand must not widen the rail
        self.set_vexpand(True)
        self.state = state
        self.add_css_class("panel-rail")
        self.add_named(pin_width(self._build_open(), OPEN_WIDTH), "open")
        self.add_named(pin_width(self._build_collapsed(), COLLAPSED_WIDTH), "collapsed")
        state.connect("notify::right-collapsed", self._sync)
        state.connect("notify::colour", self._colour_changed)
        self._sync()

    # -- open page ---------------------------------------------------------
    def _build_open(self) -> Gtk.Box:
        box = rail_page(OPEN_WIDTH)
        box.add_css_class("rail")
        top = Gtk.Box(halign=Gtk.Align.START, margin_bottom=6)
        top.append(rail_button("caret-right", "Collapse panels", "win.toggle-right-rail"))
        box.append(top)
        self.palette = ColourPalette(self.state)
        self.palette.set_margin_bottom(10)
        box.append(self.palette)
        box.append(hairline())
        lbl = group_label("View")
        lbl.set_margin_top(10)
        box.append(lbl)
        self.zoom = ZoomPill()
        self.zoom.set_halign(Gtk.Align.START)
        self.zoom.set_margin_top(4)
        box.append(self.zoom)
        lbl = group_label("Edit")
        lbl.set_margin_top(10)
        box.append(lbl)
        edit = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=4, margin_bottom=10)
        self.edit_buttons = [rail_button(icon, label, action) for icon, label, action in EDIT_ITEMS]
        for b in self.edit_buttons:
            edit.append(b)
        box.append(edit)
        box.append(hairline())
        lbl = group_label("Layers")
        lbl.set_margin_top(10)
        box.append(lbl)
        box.append(self._build_layers())             # grows to fill; sits directly above the navigator
        self.navigator = Navigator()
        self.navigator.set_margin_top(6)
        box.append(self.navigator)
        self.settings_btn = _settings_button()
        self.settings_btn.set_margin_top(6)
        box.append(self.settings_btn)
        self.state.connect("notify::zoom", lambda s, _p: self.zoom.set_zoom(s.zoom))
        return box

    def attach_stage(self, stage) -> None:
        self.navigator.attach(stage)

    def _build_layers(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=6, margin_bottom=10)
        self.layers = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.layers.add_css_class("layer-list")
        self.layers.set_accessible_role(Gtk.AccessibleRole.LIST)
        self.layers_empty = Gtk.Label(label="No layers yet", halign=Gtk.Align.FILL, valign=Gtk.Align.START, hexpand=True)
        self.layers_empty.add_css_class("empty-box")
        self.layers_empty.set_size_request(-1, 60)
        scroller = Gtk.ScrolledWindow(child=self.layers, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, vexpand=True, propagate_natural_height=True)
        scroller.add_css_class("rail-pin")
        box.append(scroller)
        box.append(self.layers_empty)
        box.set_vexpand(True)
        self.set_document(None)
        return box

    def set_document(self, doc, selected_id: int | None = None) -> None:
        """Rebuild the layer list: annotation layers top-first, then the base image."""
        self._rebuilding = True
        try:
            child = self.layers.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                self.layers.remove(child)
                child = nxt
            has = doc is not None and not doc.empty
            self.layers.get_parent().get_parent().set_visible(has)  # the scrolled window
            self.layers_empty.set_visible(not has)
            if not has:
                return
            chosen = None
            for layer in reversed(doc.layers):
                row = LayerRow(layer.name, layer.badge, "#5b6572", thumbnail=_layer_thumbnail(doc, layer))
                row.layer_id = layer.id
                row.eye.set_active(layer.visible)
                row.eye.connect("toggled", lambda b, lid=layer.id: self._eye(lid, b.get_active()))
                self.layers.append(row)
                if layer.id == selected_id:
                    chosen = row
            base = LayerRow("Base capture", "img", "#c6cedb", thumbnail=_layer_thumbnail(doc, None))
            base.layer_id = 0
            base.eye.set_sensitive(False)
            self.layers.append(base)
            self.layers.select_row(chosen if chosen is not None else base)
        finally:
            self._rebuilding = False

    def bind_editor(self, editor) -> None:
        self.editor = editor
        editor.on_selection.append(self._editor_selected)
        self.layers.connect("row-selected", self._row_selected)

    def _row_selected(self, _lb, row) -> None:
        if getattr(self, "_rebuilding", False) or self.editor is None or row is None:
            return
        self.editor.select(row.layer_id or None, notify=False)

    def _editor_selected(self, layer_id) -> None:
        if getattr(self, "_rebuilding", False):
            return
        self._rebuilding = True
        try:
            row = self.layers.get_first_child()
            while row is not None:
                if getattr(row, "layer_id", None) == (layer_id or 0):
                    self.layers.select_row(row)
                    break
                row = row.get_next_sibling()
        finally:
            self._rebuilding = False

    def _eye(self, layer_id: int, visible: bool) -> None:
        if not getattr(self, "_rebuilding", False) and self.editor is not None:
            self.editor.set_visible(layer_id, visible)

    # -- collapsed page ----------------------------------------------------
    def _build_collapsed(self) -> Gtk.Box:
        box = rail_page(COLLAPSED_WIDTH, 8)
        box.add_css_class("rail")
        box.add_css_class("collapsed")
        exp = rail_button("caret-left", "Expand panels", "win.toggle-right-rail", classes=("outlined",))
        exp.set_halign(Gtk.Align.CENTER)
        box.append(exp)
        box.append(hairline(30))
        self.dots = SwatchGrid(PALETTE[:6], on_select=lambda hx: setattr(self.state, "colour", hx), per_row=1)
        self.dots.set_halign(Gtk.Align.CENTER)
        self.dots.set_row_spacing(10)
        box.append(self.dots)
        ed = rail_button("eyedropper", "Eyedropper", "win.eyedropper")
        ed.set_halign(Gtk.Align.CENTER)
        box.append(ed)
        box.append(hairline(30))
        for icon, label, action in (("minus", "Zoom out", "win.zoom-out"), ("plus", "Zoom in", "win.zoom-in"),
                                    ("arrows-in", "Fit to window", "win.zoom-fit")):
            b = rail_button(icon, label, action)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(hairline(30))
        for icon, label, action in EDIT_ITEMS:
            b = rail_button(icon, label, action)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(Gtk.Box(vexpand=True))
        box.append(hairline(30))
        gear = rail_button("gear", "Settings", "app.preferences")
        gear.set_halign(Gtk.Align.CENTER)
        box.append(gear)
        self._colour_changed()
        return box

    # -- state sync --------------------------------------------------------
    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.right_collapsed else "open")

    def _colour_changed(self, *_a) -> None:
        self.dots.select(self.state.colour)
