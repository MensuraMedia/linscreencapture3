"""Right rail: layers, colour palette, view (zoom), edit (copy, flatten), navigator, Settings."""
from __future__ import annotations
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
    def __init__(self):
        super().__init__(content_height=116, hexpand=True)
        self.add_css_class("navigator")
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, w, h) -> None:
        # Phase 1: static document thumbnail + viewport rectangle (live in Phase 7)
        tw, th = 150, 96
        x, y = (w - tw) / 2, (h - th) / 2
        cr.set_source_rgb(0xdf / 255, 0xe4 / 255, 0xea / 255)
        cr.rectangle(x, y, tw, th)
        cr.fill()
        vw, vh = 92, 58
        cr.set_source_rgb(0x4c / 255, 0x9d / 255, 1.0)
        cr.set_line_width(1.5)
        cr.rectangle((w - vw) / 2 + 0.75, (h - vh) / 2 + 0.75, vw, vh)
        cr.stroke()


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
        box.append(group_label("Layers"))
        box.append(self._build_layers())
        box.append(hairline())
        self.palette = ColourPalette(self.state)
        self.palette.set_margin_top(10)
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
        edit = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=4)
        self.edit_buttons = [rail_button(icon, label, action) for icon, label, action in EDIT_ITEMS]
        for b in self.edit_buttons:
            edit.append(b)
        box.append(edit)
        box.append(Gtk.Box(vexpand=True))
        box.append(group_label("Navigator"))
        box.append(Navigator())
        self.settings_btn = _settings_button()
        self.settings_btn.set_margin_top(6)
        box.append(self.settings_btn)
        self.state.connect("notify::zoom", lambda s, _p: self.zoom.set_zoom(s.zoom))
        return box

    def _build_layers(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=6, margin_bottom=10)
        self.layers = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.layers.add_css_class("layer-list")
        self.layers.set_accessible_role(Gtk.AccessibleRole.LIST)
        r1 = LayerRow("Arrow", "anno", "#8fb7e8")
        r2 = LayerRow("Base capture", "img", "#c6cedb")
        self.layers.append(r1)
        self.layers.append(r2)
        self.layers.select_row(r1)
        box.append(self.layers)
        return box

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
