"""Right rail. Top row: collapse caret and the Library toggle (mirroring the left rail's Capture button). Middle, for the
editor: colour palette, view (zoom, the Page dialog), edit (copy, flatten), arrange (the selected layer's place in the
stack), navigator; while the Library is open, the Library panel instead (``ui/library_panel.py``). Bottom: Settings.
There is no layer list: layers are picked on the canvas (Ctrl+click: the one beneath)."""
from __future__ import annotations
import cairo
from gi.repository import Gtk

from .widgets import rail_button, group_label, hairline, SwatchGrid, PALETTE, rail_page, pin_width, ZoomPill
from ..services import icon_loader
from ..app.view_state import ViewState
from .library_panel import LibraryPanel, LibraryColumn

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56
EDIT_ITEMS = (("copy", "Copy the image with its annotations", "win.copy", "Ctrl+C"), ("stack-simple", "Flatten", "win.flatten", None))
LIBRARY_ITEM = ("images", "Library", "win.library", "Ctrl+L")                    # top right, a toggle
PAGE_ITEM = ("frame-corners", "Page: size, fill and stage colour", "win.page-settings", None)   # beside Fit in VIEW
# low to high, left to right; the filled square in each glyph is the selected layer (data/icons/custom)
ARRANGE_ITEMS = (("layer-back", "Send to back", "win.layer-back", "Ctrl+Shift+Page Down"),
                 ("layer-backward", "Send backward", "win.layer-backward", "Ctrl+Page Down"),
                 ("layer-forward", "Bring forward", "win.layer-forward", "Ctrl+Page Up"),
                 ("layer-front", "Bring to front", "win.layer-front", "Ctrl+Shift+Page Up"))


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
        state.connect("notify::library", self._mode)
        self._sync()
        self._mode()

    # -- open page ---------------------------------------------------------
    def _build_open(self) -> Gtk.Box:
        box = rail_page(OPEN_WIDTH)
        box.add_css_class("rail")
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_bottom=10)   # as the left rail's top row
        top.append(rail_button("caret-right", "Collapse panels", "win.toggle-right-rail", key="Ctrl+]"))
        top.append(Gtk.Box(hexpand=True))
        icon, label, action, key = LIBRARY_ITEM
        self.library_btn = rail_button(icon, label, action, toggle=True, key=key)
        top.append(self.library_btn)
        box.append(top)
        self.middle = Gtk.Stack(vhomogeneous=False, hhomogeneous=False, vexpand=True,   # sized by the visible page only
                                transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.middle.add_named(editor, "editor")
        self.library_panel = LibraryPanel()
        self.middle.add_named(self.library_panel, "library")
        box.append(self.middle)
        self._build_editor_groups(editor)
        self._build_settings(box)
        self.state.connect("notify::zoom", lambda s, _p: self.zoom.set_zoom(s.zoom))
        return box

    def _build_editor_groups(self, box: Gtk.Box) -> None:
        self.palette = ColourPalette(self.state)
        self.palette.set_margin_bottom(10)
        box.append(self.palette)
        box.append(hairline())
        lbl = group_label("View")
        lbl.set_margin_top(10)
        box.append(lbl)
        view = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, margin_top=4)
        self.zoom = ZoomPill()
        self.zoom.set_halign(Gtk.Align.START)
        view.append(self.zoom)
        icon, label, action, key = PAGE_ITEM
        self.page_btn = rail_button(icon, label, action, key=key)
        self.page_btn.set_valign(Gtk.Align.CENTER)
        view.append(self.page_btn)
        box.append(view)
        lbl = group_label("Edit")
        lbl.set_margin_top(10)
        box.append(lbl)
        edit = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=4, margin_bottom=10)
        self.edit_buttons = [rail_button(icon, label, action, key=key) for icon, label, action, key in EDIT_ITEMS]
        for b in self.edit_buttons:
            edit.append(b)
        box.append(edit)
        box.append(hairline())
        lbl = group_label("Arrange")
        lbl.set_margin_top(10)
        lbl.set_tooltip_text("The selected layer's place in the stack · Ctrl+click picks the layer beneath")
        box.append(lbl)
        arrange = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=4, margin_bottom=10)
        arrange.update_property([Gtk.AccessibleProperty.LABEL], ["Arrange the selected layer"])
        self.arrange_buttons = [rail_button(icon, label, action, key=key) for icon, label, action, key in ARRANGE_ITEMS]
        for b in self.arrange_buttons:
            arrange.append(b)
        box.append(arrange)
        box.append(Gtk.Box(vexpand=True))            # the navigator sits at the bottom
        self.navigator = Navigator()
        self.navigator.set_margin_top(6)
        box.append(self.navigator)

    def _build_settings(self, box: Gtk.Box) -> None:
        # the bottom group mirrors the left rail's ACTIONS (hairline, group label, a 30 px button row), so the two
        # rails' bottom hairlines sit at the same height
        hl = hairline()
        hl.set_margin_top(10)
        box.append(hl)
        lbl = group_label("Settings")
        lbl.set_margin_top(8)
        box.append(lbl)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.settings_btn = rail_button("gear", "Settings", "app.preferences", key="Ctrl+,")
        self.settings_btn.set_hexpand(True)
        self.settings_btn.set_halign(Gtk.Align.END)
        row.append(self.settings_btn)
        box.append(row)
        self.bottom_hairline = hl

    def attach_stage(self, stage) -> None:
        self.navigator.attach(stage)

    def set_document(self, doc, selected_id: int | None = None) -> None:
        """Nothing to rebuild since the layer list went; kept for the window's calls after every edit."""

    def bind_editor(self, editor) -> None:
        self.editor = editor

    def bind_library(self, library, tags) -> None:
        self.library_panel.bind(library, tags)
        self.library_column.bind(library)

    # -- collapsed page ----------------------------------------------------
    def _build_collapsed(self) -> Gtk.Box:
        box = rail_page(COLLAPSED_WIDTH, 8)
        box.add_css_class("rail")
        box.add_css_class("collapsed")
        exp = rail_button("caret-left", "Expand panels", "win.toggle-right-rail", classes=("outlined",), key="Ctrl+]")
        exp.set_halign(Gtk.Align.CENTER)
        box.append(exp)
        icon, label, action, key = LIBRARY_ITEM
        lib = rail_button(icon, label, action, toggle=True, key=key)
        lib.set_halign(Gtk.Align.CENTER)
        box.append(lib)
        self.middle_collapsed = Gtk.Stack(vhomogeneous=False, hhomogeneous=False, vexpand=True)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
        self.middle_collapsed.add_named(editor, "editor")
        self.library_column = LibraryColumn()
        self.middle_collapsed.add_named(self.library_column, "library")
        box.append(self.middle_collapsed)
        outer, box = box, editor
        box.append(hairline(30))
        self.dots = SwatchGrid(PALETTE[:6], on_select=lambda hx: setattr(self.state, "colour", hx), per_row=1)
        self.dots.set_halign(Gtk.Align.CENTER)
        self.dots.set_row_spacing(8)                  # 8, not 10: the column also holds the Library button
        box.append(self.dots)
        ed = rail_button("eyedropper", "Eyedropper", "win.eyedropper")
        ed.set_halign(Gtk.Align.CENTER)
        box.append(ed)
        box.append(hairline(30))
        for icon, label, action, key in (("minus", "Zoom out", "win.zoom-out", "Ctrl+−"), ("plus", "Zoom in", "win.zoom-in", "Ctrl++"),
                                         ("arrows-in", "Fit to window", "win.zoom-fit", "Ctrl+0"), PAGE_ITEM):
            b = rail_button(icon, label, action, key=key)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(hairline(30))
        for n, (icon, label, action, key) in enumerate(EDIT_ITEMS + ARRANGE_ITEMS):
            if n == len(EDIT_ITEMS):
                box.append(hairline(30))
            b = rail_button(icon, label, action, key=key)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box = outer
        box.append(hairline(30))
        slot = Gtk.Box()                              # the left rail has Discard + Save under its line: an empty
        slot.set_size_request(30, 30)                 # 30 px slot keeps both lines level and the gear beside Save
        box.append(slot)
        gear = rail_button("gear", "Settings", "app.preferences", key="Ctrl+,")
        gear.set_halign(Gtk.Align.CENTER)
        box.append(gear)
        self._colour_changed()
        return box

    # -- state sync --------------------------------------------------------
    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.right_collapsed else "open")

    def _mode(self, *_a) -> None:
        """The Library open: its panel replaces the editor groups (open and collapsed)."""
        name = "library" if self.state.library else "editor"
        self.middle.set_visible_child_name(name)
        self.middle_collapsed.set_visible_child_name(name)

    def _colour_changed(self, *_a) -> None:
        self.dots.select(self.state.colour)
