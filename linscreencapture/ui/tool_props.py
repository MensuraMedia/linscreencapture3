"""The header's tool-properties strip: one control set per tool, switching with ``ViewState.tool``.

Controls read from and write to ``Settings`` (per-tool width/shadow/intensity/fill, text and blur options);
with a layer selected, a change is also applied to that annotation through the editor.
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
        self.settings = None
        self.editor = None
        self._loading = False
        state.connect("notify::tool", self._sync)
        self._sync()
        self._wire()

    # -- settings binding ---------------------------------------------------
    def bind(self, settings, editor=None) -> None:
        self.settings = settings
        self.editor = editor
        if editor is not None:
            editor.on_selection.append(lambda _id: self._sync())
        self._sync()

    def _selected_annotation(self):
        if self.editor is None or self.state.tool not in ("select", "move"):
            return None
        layer = self.editor.selected_layer()
        return layer.annotation if layer is not None else None

    def effective_tool(self) -> str:
        """The tool whose properties the strip shows: the selected layer's kind under Select/Move."""
        a = self._selected_annotation()
        return a.kind if a is not None else self.state.tool

    def _wire(self) -> None:
        self.width_spin.connect("value-changed", lambda w: self._put("width", w.get_value()))
        self.shadow.connect("notify::active", lambda w, _p: self._put("shadow", w.get_active()))
        self.intensity.connect("value-changed", lambda w: self._put("shadow_intensity", w.get_value()))
        self.fill.connect("notify::active", lambda w, _p: self._put("fill", w.get_active()))
        self.stroke_width.connect("value-changed", lambda w: self._put("width", w.get_value()))
        self.stroke_shadow.connect("notify::active", lambda w, _p: self._put("shadow", w.get_active()))
        self.font.connect("notify::selected", lambda w, _p: self._put_global("text_font_family", FONTS[w.get_selected()], "font_family"))
        self.size.connect("value-changed", lambda w: self._put_global("text_font_size", w.get_value(), "font_size"))
        self.bold.connect("toggled", lambda w: self._put_global("text_bold", w.get_active(), "bold"))
        self.italic.connect("toggled", lambda w: self._put_global("text_italic", w.get_active(), "italic"))
        self.text_shadow.connect("notify::active", lambda w, _p: self._put("shadow", w.get_active()))
        self.step_size.connect("value-changed", lambda w: self._put_global("step_size", w.get_value(), "font_size"))
        self.block.connect("value-changed", lambda w: self._put_global("blur_block", int(w.get_value()), "blur_block"))
        self.mode.get_first_child().connect("toggled", lambda b: b.get_active() and self._set_tool("pixelate"))
        self.mode.get_last_child().connect("toggled", lambda b: b.get_active() and self._set_tool("blur"))

    def _targets(self) -> tuple[str, ...]:
        if self.settings is not None and self.settings.universal:
            from ..model.settings import TOOLS
            return TOOLS
        return (self.effective_tool(),)

    def _put(self, field: str, value) -> None:
        """Per-tool field (width, shadow, shadow_intensity, fill) → settings, then the selected layer."""
        if self._loading or self.settings is None:
            return
        for t in self._targets():
            ts = self.settings.tools.get(t)
            if ts is not None:
                setattr(ts, field, value)
        self._save()
        if self.editor is not None:
            self.editor.apply_style({field: value})

    def _put_global(self, key: str, value, style_field: str) -> None:
        if self._loading or self.settings is None:
            return
        setattr(self.settings, key, value)
        self._save()
        if self.editor is not None:
            self.editor.apply_style({style_field: value})

    def _set_tool(self, tool: str) -> None:
        if not self._loading and self.state.tool != tool:
            self.state.tool = tool

    def _save(self) -> None:
        try:
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            print(f"settings not saved: {exc}")

    def _load(self, tool: str) -> None:
        s = self.settings
        if s is None:
            return
        a = self._selected_annotation()
        self._loading = True
        try:
            if a is not None:   # a selected layer: show its own values
                st = a.style
                width, shadow, inten, fill = st.width, st.shadow, st.shadow_intensity, st.fill
                family, size, bold, italic = st.font_family, st.font_size, st.bold, st.italic
                step, block = st.font_size, st.blur_block
            else:
                ts = s.tools.get(tool) or s.tools["arrow"]
                width, shadow, inten, fill = ts.width, ts.shadow, ts.shadow_intensity, ts.fill
                family, size, bold, italic = s.text_font_family, s.text_font_size, s.text_bold, s.text_italic
                step, block = s.step_size, s.blur_block
            self.width_spin.set_value(width)
            self.shadow.set_active(shadow)
            self.intensity.set_value(inten)
            self.fill.set_active(fill)
            self.stroke_width.set_value(width)
            self.stroke_shadow.set_active(shadow)
            self.font.set_selected(FONTS.index(family) if family in FONTS else 0)
            self.size.set_value(size)
            self.bold.set_active(bold)
            self.italic.set_active(italic)
            self.text_shadow.set_active(shadow)
            self.step_size.set_value(step)
            self.block.set_value(block)
        finally:
            self._loading = False

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
        tool = self.effective_tool()
        selected = self._selected_annotation() is not None
        self.title.set_label(TOOL_TITLES.get(tool, tool).upper() + (" · SELECTED" if selected else ""))
        self.sets.set_visible_child_name(GROUP.get(tool, "select"))
        if GROUP.get(tool) == "shape":
            self.fill_row.set_visible(tool in ("box", "circle"))
        self._load(tool)
        if GROUP.get(tool) == "redact" and hasattr(self, "mode") and not selected:
            self._loading = True
            try:
                btn = self.mode.get_first_child() if tool == "pixelate" else self.mode.get_last_child()
                btn.set_active(True)
            finally:
                self._loading = False
