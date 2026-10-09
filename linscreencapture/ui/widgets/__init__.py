"""Small reusable widgets: rail buttons, labels, chips, swatches, layer rows."""
from __future__ import annotations
import re
from typing import Callable, Iterable

from gi.repository import Gdk, GLib, Gtk

from ...services import icon_loader

PALETTE = ("#e5484d", "#f76b15", "#ffb224", "#46a758", "#00a2c7", "#0091ff",
           "#6e56cf", "#d6409f", "#e58fb1", "#ffffff", "#85909b", "#1b1b1b")
_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")

# ---- per-colour CSS classes (generated once per colour) ----------------------
_colour_provider: Gtk.CssProvider | None = None
_colour_rules: dict[str, str] = {}


def normalise_hex(text: str) -> str | None:
    m = _HEX.match(text.strip())
    return f"#{m.group(1).lower()}" if m else None


def colour_class(hex_colour: str) -> str:
    """Return a CSS class whose background is ``hex_colour``, creating it on demand."""
    global _colour_provider
    hx = normalise_hex(hex_colour) or "#000000"
    cls = f"bg-{hx[1:]}"
    if cls not in _colour_rules:
        _colour_rules[cls] = f".{cls} {{ background-color: {hx}; background-image: none; }}"
        if _colour_provider is None:
            _colour_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), _colour_provider,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        _colour_provider.load_from_string("\n".join(_colour_rules.values()))
    return cls


def set_colour_class(widget: Gtk.Widget, hex_colour: str) -> None:
    for c in list(widget.get_css_classes()):
        if c.startswith("bg-"):
            widget.remove_css_class(c)
    widget.add_css_class(colour_class(hex_colour))


# ---- buttons -----------------------------------------------------------------
def rail_button(icon: str, tooltip: str, action: str | None = None, target: str | None = None,
                classes: Iterable[str] = (), size: int = 18, toggle: bool = False) -> Gtk.Button:
    btn = Gtk.ToggleButton() if toggle else Gtk.Button()
    btn.set_child(icon_loader.icon(icon, size))
    btn.add_css_class("rail-btn")
    for c in classes:
        btn.add_css_class(c)
    btn.set_tooltip_text(tooltip)
    btn.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    btn.set_can_focus(True)
    btn.set_focus_on_click(False)
    if action:
        btn.set_action_name(action)
        if target is not None:
            btn.set_action_target_value(GLib.Variant("s", target))
    btn.lsc_icon = icon  # type: ignore[attr-defined]
    return btn


def group_label(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text.upper(), xalign=0.0, halign=Gtk.Align.START)
    lbl.add_css_class("group-label")
    return lbl


def hairline(width: int | None = None) -> Gtk.Separator:
    sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    sep.add_css_class("hairline")
    if width:
        sep.set_size_request(width, 1)
        sep.set_halign(Gtk.Align.CENTER)
    return sep


def flow_group(buttons: Iterable[Gtk.Widget], per_line: int = 5) -> Gtk.Grid:
    """Buttons laid out left-to-right, ``per_line`` per row, 6 px gaps (the rail is a fixed 220 px)."""
    grid = Gtk.Grid(column_spacing=6, row_spacing=6, halign=Gtk.Align.START)
    for n, b in enumerate(buttons):
        grid.attach(b, n % per_line, n // per_line, 1, 1)
    return grid


def rail_page(width: int, spacing: int = 0) -> Gtk.Box:
    """A rail page: vertical box that never inherits hexpand from its children (pin it with ``pin_width``)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, hexpand=False)
    box.set_size_request(width, -1)
    return box


def pin_width(page: Gtk.Widget, width: int) -> Gtk.ScrolledWindow:
    """Wrap ``page`` so its allocated width is exactly ``width`` whatever its children ask for.

    A scrolled window with an EXTERNAL horizontal policy reports no natural width of its
    own, so the rail cannot grow; vertically it scrolls only if the window is shorter than
    the page's minimum (600 px floor)."""
    sw = Gtk.ScrolledWindow(child=page, hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, hexpand=False, vexpand=True)
    sw.set_size_request(width, -1)
    sw.add_css_class("rail-pin")
    return sw


# ---- header pieces -----------------------------------------------------------
class StatusChip(Gtk.Box):
    def __init__(self, text: str = "Ready", kind: str = "ok"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, valign=Gtk.Align.CENTER)
        self.add_css_class("chip")
        self._dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self._dot.add_css_class("dot")
        self._label = Gtk.Label(label=text)
        self.append(self._dot)
        self.append(self._label)
        self.set_kind(kind)

    def set_text(self, text: str) -> None:
        self._label.set_label(text)

    def set_kind(self, kind: str) -> None:
        for k in ("attention", "error"):
            self.remove_css_class(k)
        if kind in ("attention", "error"):
            self.add_css_class(kind)


class ZoomPill(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, valign=Gtk.Align.CENTER)
        self.add_css_class("pill")
        self.minus = rail_button("minus", "Zoom out", "win.zoom-out")
        self.value = Gtk.Label(label="100%", xalign=0.5)
        self.value.add_css_class("zoom-value")
        self.plus = rail_button("plus", "Zoom in", "win.zoom-in")
        self.fit = rail_button("arrows-in", "Fit to window", "win.zoom-fit")
        for w in (self.minus, self.value, self.plus, self.fit):
            self.append(w)

    def set_zoom(self, zoom: float) -> None:
        self.value.set_label(f"{round(zoom * 100):d}%")


# ---- colour ------------------------------------------------------------------
class SwatchGrid(Gtk.Grid):
    """Round 18 px swatches, 6 per row, 8 px gaps; ``on_select(hex)`` fires on user choice."""

    def __init__(self, colours: Iterable[str] = PALETTE, on_select: Callable[[str], None] | None = None,
                 per_row: int = 6):
        super().__init__(column_spacing=8, row_spacing=8, halign=Gtk.Align.START)
        self.per_row = per_row
        self._on_select = on_select
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        self._updating = False
        first: Gtk.ToggleButton | None = None
        for i, hx in enumerate(colours):
            hx = normalise_hex(hx) or hx
            b = Gtk.ToggleButton()
            b.add_css_class("swatch")
            b.add_css_class(colour_class(hx))
            b.set_tooltip_text(hx.upper())
            b.update_property([Gtk.AccessibleProperty.LABEL], [f"Colour {hx.upper()}"])
            b.set_focus_on_click(False)
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.connect("toggled", self._toggled, hx)
            self._buttons[hx] = b
            b.set_valign(Gtk.Align.CENTER)
            self.attach(b, i % per_row, i // per_row, 1, 1)

    def _toggled(self, btn: Gtk.ToggleButton, hx: str) -> None:
        if btn.get_active() and not self._updating and self._on_select:
            self._on_select(hx)

    def select(self, hx: str) -> None:
        hx = normalise_hex(hx) or hx
        self._updating = True
        try:
            if hx in self._buttons:
                self._buttons[hx].set_active(True)
            else:
                for b in self._buttons.values():
                    b.set_active(False)
        finally:
            self._updating = False

    @property
    def colours(self) -> list[str]:
        return list(self._buttons)


# ---- layers ------------------------------------------------------------------
class LayerRow(Gtk.ListBoxRow):
    def __init__(self, name: str, kind: str, thumb_colour: str = "#8fb7e8", thumbnail=None):
        super().__init__()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if thumbnail is not None:
            self.thumb = Gtk.Picture(paintable=thumbnail, content_fit=Gtk.ContentFit.COVER, can_shrink=False)
            self.thumb.set_size_request(40, 28)
            self.thumb.set_overflow(Gtk.Overflow.HIDDEN)
        else:
            self.thumb = Gtk.Box()
            self.thumb.add_css_class(colour_class(thumb_colour))
        self.thumb.add_css_class("thumb")
        self.thumb.set_valign(Gtk.Align.CENTER)
        self.name = Gtk.Label(label=name, xalign=0.0, hexpand=True, ellipsize=3, max_width_chars=10)  # Pango.EllipsizeMode.END
        self.name.add_css_class("layer-name")
        self.kind = Gtk.Label(label=kind.upper(), valign=Gtk.Align.CENTER)
        self.kind.add_css_class("kind")
        self.eye = rail_button("eye", "Toggle visibility", classes=("small", "eye"), size=16, toggle=True)
        self.eye.set_active(True)
        self.eye.set_valign(Gtk.Align.CENTER)
        self.eye.connect("toggled", self._eye_toggled)
        for w in (self.thumb, self.name, self.kind, self.eye):
            box.append(w)
        self.set_child(box)
        self.update_property([Gtk.AccessibleProperty.LABEL], [f"{name} layer"])

    def _eye_toggled(self, btn: Gtk.ToggleButton) -> None:
        btn.set_child(icon_loader.icon("eye" if btn.get_active() else "eye-slash", 16))


# ---- compact controls shared by the header strip ----------------------------
def compact_spin(lo: float, hi: float, value: float, step: float = 1, tooltip: str = "") -> Gtk.SpinButton:
    sb = Gtk.SpinButton.new_with_range(lo, hi, step)
    sb.set_value(value)
    sb.add_css_class("compact")
    sb.set_valign(Gtk.Align.CENTER)
    if tooltip:
        sb.set_tooltip_text(tooltip)
        sb.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    return sb


def labelled(text: str, widget: Gtk.Widget) -> Gtk.Box:
    """``text`` (11 px muted) followed by ``widget``, vertically centred."""
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, valign=Gtk.Align.CENTER)
    b.add_css_class("props-row")
    lbl = Gtk.Label(label=text, xalign=0.0, valign=Gtk.Align.CENTER)
    b.append(lbl)
    b.append(widget)
    return b


def segmented(options: tuple[str, ...], active: int = 0, tooltip: str = "") -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
    first = None
    for n, o in enumerate(options):
        tb = Gtk.ToggleButton(label=o, active=(n == active))
        tb.add_css_class("seg")
        if tooltip:
            tb.set_tooltip_text(f"{tooltip}: {o}")
        if first is None:
            first = tb
        else:
            tb.set_group(first)
        b.append(tb)
    return b


def scale_with_value(lo: float, hi: float, value: float, digits: int = 0, width: int = 90, tooltip: str = ""):
    """A horizontal scale with a monospace value label; returns (scale, box)."""
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, valign=Gtk.Align.CENTER)
    s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1 if digits == 0 else 0.05)
    s.set_value(value)
    s.set_size_request(width, -1)
    s.set_draw_value(False)
    s.set_valign(Gtk.Align.CENTER)
    if tooltip:
        s.set_tooltip_text(tooltip)
        s.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    b.append(s)
    fmt = (lambda v: f"{v:.{digits}f}".lstrip("0") or "0") if digits else (lambda v: f"{int(v)}")
    v = Gtk.Label(label=fmt(value), xalign=1.0)
    v.add_css_class("value")
    v.set_size_request(28, -1)
    b.append(v)
    s.connect("value-changed", lambda sc: v.set_label(fmt(sc.get_value())))
    return s, b


def switch(active: bool, tooltip: str) -> Gtk.Switch:
    sw = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
    sw.set_tooltip_text(tooltip)
    sw.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    return sw
