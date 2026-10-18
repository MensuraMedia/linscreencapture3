"""Right rail: colour palette, view (zoom), edit (copy, flatten, arrange the selected layer), page (size, fill,
stage), navigator, Settings. There is no layer list: layers are picked on the canvas (Ctrl+click: the one beneath)."""
from __future__ import annotations
import cairo
from gi.repository import Gdk, Gtk

from .widgets import (rail_button, group_label, hairline, SwatchGrid, PALETTE, rail_page, pin_width, ZoomPill,
                      compact_spin, switch)
from ..services import icon_loader
from ..app.view_state import ViewState

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56
EDIT_ITEMS = (("copy", "Copy the image with its annotations", "win.copy", "Ctrl+C"), ("stack-simple", "Flatten", "win.flatten", None))
ARRANGE_ITEMS = (("arrow-line-up", "Bring to front", "win.layer-front", "Ctrl+Shift+Page Up"),
                 ("arrow-up", "Bring forward", "win.layer-forward", "Ctrl+Page Up"),
                 ("arrow-down", "Send backward", "win.layer-backward", "Ctrl+Page Down"),
                 ("arrow-line-down", "Send to back", "win.layer-back", "Ctrl+Shift+Page Down"))


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


def _rgba(hx: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hx)
    return c


def _hex(c: Gdk.RGBA) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in (c.red, c.green, c.blue))


class PageSection(Gtk.Box):
    """The page: its size (set about the centre), a fill colour behind its transparent parts (kept when saved or
    flattened) and the stage colour around it. Size and fill are undoable document edits; the stage colour and the
    last fill colour are settings."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=4, margin_bottom=10)
        self.editor = None
        self._loading = False
        size = Gtk.Grid(row_spacing=4, column_spacing=8)
        self.width = compact_spin(1, 16384, 1, tooltip="Page width (px) · set about the centre")
        self.height = compact_spin(1, 16384, 1, tooltip="Page height (px) · set about the centre")
        for row, (text, spin) in enumerate((("Width", self.width), ("Height", self.height))):
            lbl = Gtk.Label(label=text, xalign=0.0, hexpand=True)
            lbl.add_css_class("sublabel")
            size.attach(lbl, 0, row, 1, 1)
            size.attach(spin, 1, row, 1, 1)
        self.append(size)
        for spin in (self.width, self.height):
            spin.connect("value-changed", lambda *_: self._size_changed())
        fill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label="Fill", xalign=0.0, hexpand=True)
        lbl.add_css_class("sublabel")
        fill.append(lbl)
        self.fill = switch(False, "Fill the page's transparent parts (kept when saved or flattened)")
        self.fill.connect("notify::active", lambda *_: self._fill_changed())
        fill.append(self.fill)
        self.fill_colour = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Page fill", with_alpha=False),
                                                 valign=Gtk.Align.CENTER, tooltip_text="Page fill colour")
        self.fill_colour.add_css_class("page-colour")
        self.fill_colour.connect("notify::rgba", lambda *_: self._fill_colour_changed())
        fill.append(self.fill_colour)
        self.append(fill)
        stage = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label="Stage", xalign=0.0, hexpand=True)
        lbl.add_css_class("sublabel")
        stage.append(lbl)
        self.stage_reset = rail_button("arrow-counter-clockwise", "Stage colour: back to the theme's", "win.stage-colour-reset",
                                       classes=("small",), size=14)
        self.stage_reset.set_valign(Gtk.Align.CENTER)
        stage.append(self.stage_reset)
        self.stage_colour = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Stage colour", with_alpha=False),
                                                  valign=Gtk.Align.CENTER, tooltip_text="Stage colour (around the page)")
        self.stage_colour.add_css_class("page-colour")
        self.stage_colour.connect("notify::rgba", lambda b, _p: self._loading or self._set_stage(_hex(b.get_rgba())))
        stage.append(self.stage_colour)
        self.append(stage)

    def bind(self, editor) -> None:
        self.editor = editor
        self._loading = True
        try:
            s = editor.settings
            self.fill_colour.set_rgba(_rgba(s.page_fill))
            self.stage_colour.set_rgba(_rgba(s.stage_colour or "#242424"))
            self.stage_reset.set_sensitive(bool(s.stage_colour))
        finally:
            self._loading = False
        editor.stage.set_stage_colour(editor.settings.stage_colour)

    def set_document(self, doc) -> None:
        """Show ``doc``'s size and fill (no document: the size and fill rows are insensitive)."""
        has = doc is not None and not doc.empty
        self._loading = True
        try:
            for w in (self.width, self.height, self.fill, self.fill_colour):
                w.set_sensitive(has)
            if has:
                self.width.set_value(doc.width)
                self.height.set_value(doc.height)
                self.fill.set_active(doc.background is not None)
                if doc.background:
                    self.fill_colour.set_rgba(_rgba(doc.background))
        finally:
            self._loading = False

    def _size_changed(self) -> None:
        if not self._loading and self.editor is not None:
            self.editor.set_page_size(int(self.width.get_value()), int(self.height.get_value()))

    def _fill_changed(self) -> None:
        if not self._loading and self.editor is not None:
            self.editor.set_page_fill(_hex(self.fill_colour.get_rgba()) if self.fill.get_active() else None)

    def _fill_colour_changed(self) -> None:
        if self._loading or self.editor is None:
            return
        hx = _hex(self.fill_colour.get_rgba())
        s = self.editor.settings
        s.page_fill = hx
        _save(s)
        if self.fill.get_active():
            self.editor.set_page_fill(hx)
        else:
            self.fill.set_active(True)          # choosing a colour turns the fill on

    def reset_stage(self) -> None:
        self._set_stage("")

    def _set_stage(self, hx: str) -> None:
        if self.editor is None:
            return
        s = self.editor.settings
        s.stage_colour = hx
        _save(s)
        self.stage_reset.set_sensitive(bool(hx))
        if not hx:
            self._loading = True
            try:
                self.stage_colour.set_rgba(_rgba("#242424"))
            finally:
                self._loading = False
        self.editor.stage.set_stage_colour(hx)


def _save(settings) -> None:
    try:
        settings.save()
    except Exception as exc:  # noqa: BLE001
        print(f"settings not saved: {exc}")


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
        top.append(rail_button("caret-right", "Collapse panels", "win.toggle-right-rail", key="Ctrl+]"))
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
        self.edit_buttons = [rail_button(icon, label, action, key=key) for icon, label, action, key in EDIT_ITEMS]
        for b in self.edit_buttons:
            edit.append(b)
        box.append(edit)
        arrange = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_bottom=10)
        arrange.update_property([Gtk.AccessibleProperty.LABEL], ["Arrange the selected layer"])
        self.arrange_buttons = [rail_button(icon, label, action, key=key) for icon, label, action, key in ARRANGE_ITEMS]
        for b in self.arrange_buttons:
            arrange.append(b)
        edit.set_margin_bottom(4)
        box.append(arrange)
        box.append(hairline())
        lbl = group_label("Page")
        lbl.set_margin_top(10)
        box.append(lbl)
        self.page = PageSection()
        box.append(self.page)
        box.append(Gtk.Box(vexpand=True))            # the navigator sits at the bottom
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

    def set_document(self, doc, selected_id: int | None = None) -> None:
        """A new or changed document: refresh the Page section (``selected_id`` is kept for the window's calls)."""
        self.page.set_document(doc)

    def bind_editor(self, editor) -> None:
        self.editor = editor
        self.page.bind(editor)

    # -- collapsed page ----------------------------------------------------
    def _build_collapsed(self) -> Gtk.Box:
        box = rail_page(COLLAPSED_WIDTH, 8)
        box.add_css_class("rail")
        box.add_css_class("collapsed")
        exp = rail_button("caret-left", "Expand panels", "win.toggle-right-rail", classes=("outlined",), key="Ctrl+]")
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
        for icon, label, action, key in (("minus", "Zoom out", "win.zoom-out", "Ctrl+−"), ("plus", "Zoom in", "win.zoom-in", "Ctrl++"),
                                         ("arrows-in", "Fit to window", "win.zoom-fit", "Ctrl+0")):
            b = rail_button(icon, label, action, key=key)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(hairline(30))
        for icon, label, action, key in EDIT_ITEMS + ARRANGE_ITEMS:
            b = rail_button(icon, label, action, key=key)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(Gtk.Box(vexpand=True))
        box.append(hairline(30))
        gear = rail_button("gear", "Settings", "app.preferences", key="Ctrl+,")
        gear.set_halign(Gtk.Align.CENTER)
        box.append(gear)
        self._colour_changed()
        return box

    # -- state sync --------------------------------------------------------
    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.right_collapsed else "open")

    def _colour_changed(self, *_a) -> None:
        self.dots.select(self.state.colour)
