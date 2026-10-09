"""Right rail: Layers / Props panels, colour palette, navigator, Settings."""
from __future__ import annotations
from gi.repository import Gtk

from .widgets import (rail_button, group_label, hairline, SwatchGrid, LayerRow, PALETTE,
                      colour_class, rail_page, pin_width)
from ..services import icon_loader
from ..app.view_state import ViewState

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56
PANEL_ITEMS = (("stack", "Layers", "layers"), ("sliders-horizontal", "Props", "props"))
TOOL_NAMES = {"select": "Select", "arrow": "Arrow", "line": "Line", "box": "Box", "circle": "Circle", "text": "Text",
              "pen": "Pen", "marker": "Marker", "blur": "Blur", "pixelate": "Pixelate", "fill": "Fill", "step": "Step number",
              "callout": "Callout", "crop": "Crop", "move": "Move"}


def _panel_buttons() -> list[Gtk.ToggleButton]:
    return [rail_button(icon, label, "win.panel", target, toggle=True) for icon, label, target in PANEL_ITEMS]


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
        state.connect("notify::panel", self._panel_changed)
        state.connect("notify::tool", self._tool_changed)
        state.connect("notify::colour", self._colour_changed)
        self._sync()

    # -- open page ---------------------------------------------------------
    def _build_open(self) -> Gtk.Box:
        box = rail_page(OPEN_WIDTH)
        box.add_css_class("rail")
        top = Gtk.Box(halign=Gtk.Align.START, margin_bottom=6)
        top.append(rail_button("caret-double-right", "Collapse panels", "win.toggle-right-rail"))
        box.append(top)
        switch = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_bottom=4, homogeneous=True)
        for b in _panel_buttons():
            switch.append(b)
        box.append(switch)
        self.panels = Gtk.Stack(vhomogeneous=False, hhomogeneous=False,
                                transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.panels.add_named(self._build_layers(), "layers")
        self.panels.add_named(self._build_props(), "props")
        self.panels.set_visible_child_name(self.state.panel)
        box.append(self.panels)
        box.append(hairline())
        self.palette = ColourPalette(self.state)
        self.palette.set_margin_top(10)
        self.palette.set_margin_bottom(6)
        box.append(self.palette)
        box.append(Gtk.Box(vexpand=True))
        box.append(group_label("Navigator"))
        box.append(Navigator())
        self.settings_btn = _settings_button()
        self.settings_btn.set_margin_top(6)
        box.append(self.settings_btn)
        self._panel_changed()
        return box

    def _build_layers(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4, margin_bottom=10)
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

    def _build_props(self) -> Gtk.Widget:
        box = self._build_props_content()
        return Gtk.ScrolledWindow(child=box, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, propagate_natural_height=True,
                                  vexpand=False)

    def _build_props_content(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=6, margin_bottom=10)
        self.props_tool_label = group_label("Blur · active tool")
        box.append(self.props_tool_label)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        card.append(self._row("Mode", self._segmented(("Pixelate", "Blur"))))
        self.block_scale, blk = self._scale(4, 32, 12, "12")
        card.append(self._row("Block", blk))
        box.append(card)
        lbl = group_label("Shapes · line, arrow, box, circle")
        lbl.set_margin_top(10)
        box.append(lbl)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        self.width_spin = Gtk.SpinButton.new_with_range(1, 20, 1)
        self.width_spin.set_value(4)
        self.width_spin.add_css_class("compact")
        self.width_spin.set_tooltip_text("Line width")
        card.append(self._row("Width", self.width_spin))
        sw = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        sw.set_tooltip_text("Shadow")
        card.append(self._row("Shadow", self._with_label(sw, "on")))
        self.intensity_scale, inten = self._scale(0, 1, 0.6, ".60", digits=2)
        card.append(self._row("Intensity", inten))
        uni = Gtk.Switch(active=False, valign=Gtk.Align.CENTER)
        uni.set_tooltip_text("Apply colour, width and shadow to all tools")
        card.append(self._row("Universal", self._with_label(uni, "all tools")))
        box.append(card)
        lbl = group_label("Text")
        lbl.set_margin_top(10)
        box.append(lbl)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.font_dd = Gtk.DropDown.new_from_strings(["Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans", "Noto Sans"])
        self.font_dd.set_hexpand(True)
        self.font_dd.set_tooltip_text("Font family")
        r.append(self.font_dd)
        self.size_spin = Gtk.SpinButton.new_with_range(6, 96, 1)
        self.size_spin.set_value(18)
        self.size_spin.add_css_class("compact")
        self.size_spin.set_tooltip_text("Font size")
        r.append(self.size_spin)
        card.append(r)
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bold = Gtk.ToggleButton(label="B", active=True)
        bold.add_css_class("tbtn")
        bold.set_tooltip_text("Bold")
        italic = Gtk.ToggleButton(label="I")
        italic.add_css_class("tbtn")
        italic.set_tooltip_text("Italic")
        r.append(bold)
        r.append(italic)
        tsw = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        tsw.set_tooltip_text("Text shadow")
        r.append(self._with_label(tsw, "shadow"))
        card.append(r)
        box.append(card)
        return box

    @staticmethod
    def _row(label: str, widget: Gtk.Widget) -> Gtk.Box:
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        r.add_css_class("props-row")
        l = Gtk.Label(label=label, xalign=0.0)
        l.set_size_request(56, -1)
        r.append(l)
        widget.set_hexpand(True)
        r.append(widget)
        return r

    @staticmethod
    def _with_label(widget: Gtk.Widget, text: str) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b.append(widget)
        l = Gtk.Label(label=text, xalign=0.0)
        l.add_css_class("sublabel")
        b.append(l)
        return b

    @staticmethod
    def _segmented(options: tuple[str, ...]) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, halign=Gtk.Align.START)
        first = None
        for n, o in enumerate(options):
            t = Gtk.ToggleButton(label=o, active=(n == 0))
            t.add_css_class("seg")
            if first is None:
                first = t
            else:
                t.set_group(first)
            b.append(t)
        return b

    @staticmethod
    def _scale(lo: float, hi: float, value: float, text: str, digits: int = 0):
        b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1 if digits == 0 else 0.05)
        s.set_value(value)
        s.set_hexpand(True)
        s.set_draw_value(False)
        b.append(s)
        v = Gtk.Label(label=text, xalign=1.0)
        v.add_css_class("value")
        v.set_size_request(28, -1)
        b.append(v)
        s.connect("value-changed", lambda sc: v.set_label(f"{sc.get_value():.{digits}f}".lstrip("0") if digits else f"{int(sc.get_value())}"))
        return s, b

    # -- collapsed page ----------------------------------------------------
    def _build_collapsed(self) -> Gtk.Box:
        box = rail_page(COLLAPSED_WIDTH, 8)
        box.add_css_class("rail")
        box.add_css_class("collapsed")
        exp = rail_button("caret-double-left", "Expand panels", "win.toggle-right-rail", classes=("outlined",))
        exp.set_halign(Gtk.Align.CENTER)
        box.append(exp)
        box.append(hairline(30))
        for b in _panel_buttons():
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)
        box.append(hairline(30))
        self.dots = SwatchGrid(PALETTE[:6], on_select=lambda hx: setattr(self.state, "colour", hx), per_row=1)
        self.dots.set_halign(Gtk.Align.CENTER)
        self.dots.set_row_spacing(10)
        box.append(self.dots)
        box.append(hairline(30))
        ed = rail_button("eyedropper", "Eyedropper", "win.eyedropper")
        ed.set_halign(Gtk.Align.CENTER)
        box.append(ed)
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

    def _panel_changed(self, *_a) -> None:
        self.panels.set_visible_child_name(self.state.panel)

    def _tool_changed(self, *_a) -> None:
        self.props_tool_label.set_label(f"{TOOL_NAMES.get(self.state.tool, self.state.tool)} · active tool".upper())

    def _colour_changed(self, *_a) -> None:
        self.dots.select(self.state.colour)
