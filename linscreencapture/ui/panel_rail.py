"""Right rail: Layers / Captures / Props panels, colour card, navigator."""
from __future__ import annotations
from gi.repository import Gdk, Gio, Gtk, Pango

from .widgets import (rail_button, group_label, hairline, SwatchGrid, LayerRow, PALETTE,
                      colour_class, set_colour_class, normalise_hex, rail_page, pin_width)
from ..services import icon_loader
from ..app.view_state import ViewState
from ..model.captures_index import CapturesIndex, CaptureEntry

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56
PANEL_ITEMS = (("stack", "Layers", "layers"), ("images", "Captures", "captures"), ("sliders-horizontal", "Props", "props"))
TOOL_NAMES = {"select": "Select", "arrow": "Arrow", "line": "Line", "box": "Box", "circle": "Circle", "text": "Text",
              "pen": "Pen", "marker": "Marker", "blur": "Blur", "pixelate": "Pixelate", "fill": "Fill", "step": "Step number",
              "callout": "Callout", "crop": "Crop", "move": "Move"}


def _panel_buttons() -> list[Gtk.ToggleButton]:
    return [rail_button(icon, label, "win.panel", target, toggle=True) for icon, label, target in PANEL_ITEMS]


class ColourCard(Gtk.Box):
    def __init__(self, state: ViewState):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("card")
        self.state = state
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.well = Gtk.Box(valign=Gtk.Align.CENTER)
        self.well.add_css_class("colour-well")
        row.append(self.well)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.hex = Gtk.Label(xalign=0.0)
        self.hex.add_css_class("hex")
        sub = Gtk.Label(label="Foreground", xalign=0.0)
        sub.add_css_class("sublabel")
        txt.append(self.hex)
        txt.append(sub)
        row.append(txt)
        self.append(row)
        self.swatches = SwatchGrid(PALETTE, on_select=self._chosen)
        self.append(self.swatches)
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bottom.append(rail_button("eyedropper", "Eyedropper", "win.eyedropper"))
        self.entry = Gtk.Entry(hexpand=True, max_length=7, width_chars=6, max_width_chars=8)
        self.entry.add_css_class("hex-entry")
        self.entry.set_tooltip_text("Hex colour")
        self.entry.update_property([Gtk.AccessibleProperty.LABEL], ["Hex colour"])
        self.entry.connect("activate", self._entry_activate)
        bottom.append(self.entry)
        self.append(bottom)
        state.connect("notify::colour", self._sync)
        self._sync()

    def _chosen(self, hx: str) -> None:
        self.state.colour = hx

    def _entry_activate(self, entry: Gtk.Entry) -> None:
        hx = normalise_hex(entry.get_text())
        if hx:
            self.state.colour = hx
        else:
            self._sync()

    def _sync(self, *_a) -> None:
        hx = self.state.colour
        set_colour_class(self.well, hx)
        self.hex.set_label(hx.upper())
        self.entry.set_text(hx.upper())
        self.swatches.select(hx)


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
    def __init__(self, state: ViewState, captures: CapturesIndex):
        super().__init__(hhomogeneous=False, vhomogeneous=True, interpolate_size=True,
                         transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.set_hexpand(False)  # explicit: children with hexpand must not widen the rail
        self.set_vexpand(True)
        self.state = state
        self.captures = captures
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
        self.panels.add_named(self._build_captures(), "captures")
        self.panels.add_named(self._build_props(), "props")
        self.panels.set_visible_child_name(self.state.panel)
        box.append(self.panels)
        self.colour_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.colour_section.append(hairline())
        lbl = group_label("Colour")
        lbl.set_margin_top(8)
        self.colour_section.append(lbl)
        self.colour = ColourCard(self.state)
        self.colour_section.append(self.colour)
        box.append(self.colour_section)
        box.append(Gtk.Box(vexpand=True))
        self.navigator_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.navigator_section.append(group_label("Navigator"))
        self.navigator_section.append(Navigator())
        box.append(self.navigator_section)
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

    def _build_captures(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4, margin_bottom=10)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2, margin_bottom=8)
        self.captures_label = group_label("0 captures")
        self.captures_label.set_hexpand(True)
        self.captures_label.set_valign(Gtk.Align.CENTER)
        head.append(self.captures_label)
        head.append(rail_button("arrows-clockwise", "Refresh", "win.captures-refresh", classes=("small",), size=16))
        head.append(rail_button("trash", "Delete selected", "win.captures-delete", classes=("small", "danger"), size=16))
        box.append(head)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._cap_setup)
        factory.connect("bind", self._cap_bind)
        self.captures_selection = Gtk.SingleSelection(model=self.captures.store, autoselect=False)
        self.captures_view = Gtk.GridView(model=self.captures_selection, factory=factory,
                                          min_columns=2, max_columns=2, single_click_activate=False)
        self.captures_view.add_css_class("captures-grid")
        self.captures_view.set_hexpand(False)
        self.captures_view.set_accessible_role(Gtk.AccessibleRole.GRID)
        scroller = Gtk.ScrolledWindow(child=self.captures_view, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, propagate_natural_height=True,
                                      max_content_height=380)
        box.append(scroller)
        hint = Gtk.Label(label="Double-click opens · Delete removes", xalign=0.0, margin_top=8)
        hint.add_css_class("sublabel")
        box.append(hint)
        self.captures.connect("scanned", lambda _i, n: self.captures_label.set_label(f"{n} CAPTURES"))
        return box

    def _cap_setup(self, _f, item: Gtk.ListItem) -> None:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_bottom=6)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        pic.set_size_request(94, 64)
        pic.add_css_class("cap-thumb")
        pic.set_overflow(Gtk.Overflow.HIDDEN)
        name = Gtk.Label(xalign=0.0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=9, width_chars=6)
        name.add_css_class("cap-name")
        cell.append(pic)
        cell.append(name)
        item.set_child(cell)

    def _cap_bind(self, _f, item: Gtk.ListItem) -> None:
        entry: CaptureEntry = item.get_item()
        cell = item.get_child()
        pic, name = cell.get_first_child(), cell.get_last_child()
        pic.set_paintable(entry.texture)
        name.set_label(entry.name)
        cell.set_tooltip_text(entry.name)

    def _build_props(self) -> Gtk.Widget:
        box = self._build_props_content()
        return Gtk.ScrolledWindow(child=box, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                  vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, propagate_natural_height=True,
                                  vexpand=True)

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
        box.append(Gtk.Box(vexpand=True))
        prefs = Gtk.Button()
        pb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pb.append(icon_loader.icon("gear", 18))
        pb.append(Gtk.Label(label="Preferences…"))
        prefs.set_child(pb)
        prefs.add_css_class("text-btn")
        prefs.set_halign(Gtk.Align.START)
        prefs.set_action_name("app.preferences")
        prefs.set_margin_top(10)
        box.append(prefs)
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
        self.chips: dict[str, Gtk.Box] = {}
        for hx in PALETTE[:6]:
            chip = Gtk.Box(halign=Gtk.Align.CENTER)
            chip.add_css_class("chip-swatch")
            chip.add_css_class(colour_class(hx))
            chip.set_tooltip_text(hx.upper())
            click = Gtk.GestureClick()
            click.connect("released", lambda g, *_a, h=hx: setattr(self.state, "colour", h))
            chip.add_controller(click)
            self.chips[hx] = chip
            box.append(chip)
        box.append(hairline(30))
        ed = rail_button("eyedropper", "Eyedropper", "win.eyedropper")
        ed.set_halign(Gtk.Align.CENTER)
        box.append(ed)
        self._colour_changed()
        return box

    # -- state sync --------------------------------------------------------
    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.right_collapsed else "open")

    def _panel_changed(self, *_a) -> None:
        self.panels.set_visible_child_name(self.state.panel)
        props = self.state.panel == "props"
        self.colour_section.set_visible(not props)
        self.navigator_section.set_visible(not props)

    def _tool_changed(self, *_a) -> None:
        self.props_tool_label.set_label(f"{TOOL_NAMES.get(self.state.tool, self.state.tool)} · active tool".upper())

    def _colour_changed(self, *_a) -> None:
        for hx, chip in self.chips.items():
            if hx == self.state.colour:
                chip.add_css_class("current")
            else:
                chip.remove_css_class("current")
