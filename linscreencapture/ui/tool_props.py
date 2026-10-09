"""The header's tool-properties strip: one control set per tool, switching with ``ViewState.tool``.

Phase 4 binds these controls to ``Settings.tools``; here they hold working values only.
"""
from __future__ import annotations
from gi.repository import Gtk

from .widgets import compact_spin, labelled, segmented, scale_with_value, switch
from ..app.view_state import ViewState

TOOL_TITLES = {"select": "Select", "arrow": "Arrow", "line": "Line", "box": "Box", "circle": "Circle", "text": "Text",
               "pen": "Pen", "marker": "Marker", "blur": "Blur", "pixelate": "Pixelate", "fill": "Fill",
               "step": "Step number", "callout": "Callout", "crop": "Crop", "move": "Move"}
# which control set each tool shows
GROUP = {"arrow": "shape", "line": "shape", "box": "shape", "circle": "shape", "pen": "stroke", "marker": "stroke",
         "text": "text", "callout": "text", "step": "step", "fill": "fill", "blur": "redact", "pixelate": "redact",
         "crop": "crop", "select": "select", "move": "select"}
FONTS = ("Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans", "Noto Sans")


def _hint(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text, valign=Gtk.Align.CENTER)
    lbl.add_css_class("sublabel")
    return lbl


class ToolProps(Gtk.Box):
    def __init__(self, state: ViewState):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=14, valign=Gtk.Align.CENTER)
        self.add_css_class("tool-props")
        self.state = state
        self.title = Gtk.Label(xalign=0.0, valign=Gtk.Align.CENTER)
        self.title.add_css_class("group-label")
        self.title.set_size_request(72, -1)
        self.append(self.title)
        self.sets = Gtk.Stack(hhomogeneous=False, vhomogeneous=True,
                              transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.sets.set_valign(Gtk.Align.CENTER)
        self.sets.add_named(self._shape(), "shape")
        self.sets.add_named(self._stroke(), "stroke")
        self.sets.add_named(self._text(), "text")
        self.sets.add_named(self._step(), "step")
        self.sets.add_named(self._row(_hint("Drag a rectangle · fills with the current colour")), "fill")
        self.sets.add_named(self._redact(), "redact")
        self.sets.add_named(self._row(_hint("Drag to crop · Enter applies · Esc cancels")), "crop")
        self.sets.add_named(self._row(_hint("Click to select · drag to move · Delete removes · Ctrl+D duplicates")), "select")
        self.append(self.sets)
        state.connect("notify::tool", self._sync)
        self._sync()

    @staticmethod
    def _row(*widgets: Gtk.Widget) -> Gtk.Box:
        b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14, valign=Gtk.Align.CENTER)
        for w in widgets:
            b.append(w)
        return b

    def _shape(self) -> Gtk.Box:
        self.width_spin = compact_spin(1, 20, 4, tooltip="Line width")
        self.shadow = switch(True, "Shadow")
        self.intensity, inten = scale_with_value(0, 1, 0.6, digits=2, width=80, tooltip="Shadow intensity")
        self.fill = switch(False, "Fill the shape")
        self.fill_row = labelled("Fill", self.fill)
        return self._row(labelled("Width", self.width_spin), labelled("Shadow", self.shadow),
                         labelled("Intensity", inten), self.fill_row)

    def _stroke(self) -> Gtk.Box:
        self.stroke_width = compact_spin(1, 20, 4, tooltip="Stroke width")
        self.stroke_shadow = switch(False, "Shadow")
        return self._row(labelled("Width", self.stroke_width), labelled("Shadow", self.stroke_shadow),
                         _hint("Marker paints at 4× width, 40 % opacity"))

    def _text(self) -> Gtk.Box:
        self.font = Gtk.DropDown.new_from_strings(list(FONTS))
        self.font.set_valign(Gtk.Align.CENTER)
        self.font.set_tooltip_text("Font family")
        self.size = compact_spin(6, 96, 18, tooltip="Font size")
        self.bold = Gtk.ToggleButton(label="B", active=True, valign=Gtk.Align.CENTER)
        self.bold.add_css_class("tbtn"); self.bold.set_tooltip_text("Bold")
        self.italic = Gtk.ToggleButton(label="I", valign=Gtk.Align.CENTER)
        self.italic.add_css_class("tbtn"); self.italic.set_tooltip_text("Italic")
        self.text_shadow = switch(True, "Text shadow")
        style = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, valign=Gtk.Align.CENTER)
        style.append(self.bold); style.append(self.italic)
        return self._row(self.font, labelled("Size", self.size), style, labelled("Shadow", self.text_shadow))

    def _step(self) -> Gtk.Box:
        self.step_size = compact_spin(8, 48, 14, tooltip="Badge size")
        return self._row(labelled("Size", self.step_size), _hint("Each click places the next number"))

    def _redact(self) -> Gtk.Box:
        self.mode = segmented(("Pixelate", "Blur"), tooltip="Redaction")
        self.block, blk = scale_with_value(2, 32, 12, width=90, tooltip="Block size")
        return self._row(labelled("Mode", self.mode), labelled("Block", blk))

    def _sync(self, *_a) -> None:
        tool = self.state.tool
        self.title.set_label(TOOL_TITLES.get(tool, tool).upper())
        self.sets.set_visible_child_name(GROUP.get(tool, "select"))
        if GROUP.get(tool) == "shape":
            self.fill_row.set_visible(tool in ("box", "circle"))
        if GROUP.get(tool) == "redact" and hasattr(self, "mode"):
            btn = self.mode.get_first_child() if tool == "pixelate" else self.mode.get_last_child()
            btn.set_active(True)
