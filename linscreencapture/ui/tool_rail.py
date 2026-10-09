"""Left rail: capture modes, tools, actions. Open (220 px) and collapsed (56 px) pages."""
from __future__ import annotations
from dataclasses import dataclass

from gi.repository import Gtk

from .widgets import rail_button, group_label, hairline, flow_group, rail_page, pin_width
from ..app.view_state import ViewState

OPEN_WIDTH, COLLAPSED_WIDTH = 220, 56


@dataclass(frozen=True)
class Item:
    icon: str
    label: str
    action: str
    target: str | None = None
    collapsed: bool = False
    toggle: bool = False
    classes: tuple[str, ...] = ()
    group: str = ""


CAPTURE = (
    Item("selection", "Region", "win.capture-mode", "region", True, True, (), "capture"),
    Item("app-window", "Window", "win.capture-mode", "window", False, True, (), "capture"),
    Item("monitor", "Full screen", "win.capture-mode", "screen", True, True, (), "capture"),
    Item("arrows-vertical", "Scrolling", "win.capture-mode", "scrolling", False, True, (), "capture"),
    Item("timer", "Delayed 3 s", "win.capture-mode", "delayed", True, True, (), "capture"),
    Item("push-pin", "Pin to screen", "app.pin", None, False, False, (), "capture"),
)
TOOLS_A = (
    Item("cursor", "Select", "win.tool", "select", False, True, (), "tools"),
    Item("arrow-up-right", "Arrow", "win.tool", "arrow", True, True, (), "tools"),
    Item("line-segment", "Line", "win.tool", "line", False, True, (), "tools"),
    Item("square", "Box", "win.tool", "box", True, True, (), "tools"),
    Item("circle", "Circle", "win.tool", "circle", False, True, (), "tools"),
    Item("text-t", "Text", "win.tool", "text", True, True, (), "tools"),
    Item("pencil-simple", "Pen", "win.tool", "pen", True, True, (), "tools"),
    Item("highlighter", "Marker", "win.tool", "marker", False, True, (), "tools"),
)
TOOLS_B = (
    Item("circle-dashed", "Blur", "win.tool", "blur", True, True, (), "edit"),
    Item("checkerboard", "Pixelate", "win.tool", "pixelate", False, True, (), "edit"),
    Item("paint-bucket", "Fill", "win.tool", "fill", False, True, (), "edit"),
    Item("number-circle-one", "Step number", "win.tool", "step", True, True, (), "edit"),
    Item("chat-teardrop", "Callout", "win.tool", "callout", False, True, (), "edit"),
    Item("crop", "Crop", "win.tool", "crop", True, True, (), "edit"),
    Item("arrows-out", "Resize", "win.resize", None, False, False, (), "edit"),
    Item("arrow-clockwise", "Rotate", "win.rotate", None, False, False, (), "edit"),
    Item("sun", "Brightness", "win.adjust", None, False, False, (), "edit"),
    Item("arrows-out-cardinal", "Move", "win.tool", "move", False, True, (), "edit"),
    Item("copy-simple", "Duplicate", "win.duplicate-file", None, False, False, (), "edit"),
)
ACTIONS = (
    Item("trash", "Discard", "win.discard", None, True, False, ("danger",), "actions"),
    Item("stack-simple", "Flatten", "win.flatten", None, False, False, (), "actions"),
    Item("images", "Captures", "win.panel", "captures", False, False, (), "actions"),
    Item("copy", "Copy", "win.copy", None, True, False, (), "actions"),
    Item("download-simple", "Save", "win.save", None, True, False, ("primary",), "actions"),
)
ALL_ITEMS = CAPTURE + TOOLS_A + TOOLS_B + ACTIONS


def make(item: Item) -> Gtk.Button:
    return rail_button(item.icon, item.label, item.action, item.target, item.classes, toggle=item.toggle)


class ToolRail(Gtk.Stack):
    def __init__(self, state: ViewState):
        super().__init__(hhomogeneous=False, vhomogeneous=True, interpolate_size=True,
                         transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.set_hexpand(False)  # explicit: children with hexpand must not widen the rail
        self.set_vexpand(True)
        self.state = state
        self.add_css_class("tool-rail")
        self.add_named(pin_width(self._build_open(), OPEN_WIDTH), "open")
        self._collapsed_box: Gtk.Box | None = None
        self.add_named(pin_width(self._build_collapsed(), COLLAPSED_WIDTH), "collapsed")
        self.buttons: list[Gtk.Button] = []
        state.connect("notify::left-collapsed", self._sync)
        state.connect("notify::tool", lambda *_: self._rebuild_collapsed_tools())
        self._sync()

    # -- pages -------------------------------------------------------------
    def _build_open(self) -> Gtk.Box:
        box = rail_page(OPEN_WIDTH)
        box.add_css_class("rail")
        top = Gtk.Box(halign=Gtk.Align.END, margin_bottom=6)
        top.append(rail_button("caret-double-left", "Collapse tools", "win.toggle-left-rail"))
        box.append(top)
        box.append(group_label("Capture"))
        cap = flow_group(make(i) for i in CAPTURE)
        cap.set_margin_bottom(10)
        box.append(cap)
        box.append(hairline())
        lbl = group_label("Tools")
        lbl.set_margin_top(8)
        box.append(lbl)
        box.append(flow_group(make(i) for i in TOOLS_A))
        hl = hairline()
        hl.set_margin_top(8)
        hl.set_margin_bottom(8)
        box.append(hl)
        box.append(flow_group(make(i) for i in TOOLS_B))
        box.append(Gtk.Box(vexpand=True))
        box.append(hairline())
        lbl = group_label("Actions")
        lbl.set_margin_top(8)
        box.append(lbl)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        items = list(ACTIONS)
        for n, item in enumerate(items):
            b = make(item)
            if n < len(items) - 1:
                b.set_hexpand(True)
                b.set_halign(Gtk.Align.START)
            else:
                b.set_halign(Gtk.Align.END)
            row.append(b)
        box.append(row)
        return box

    def _build_collapsed(self) -> Gtk.Box:
        box = rail_page(COLLAPSED_WIDTH, 8)
        box.add_css_class("rail")
        box.add_css_class("collapsed")
        exp = rail_button("caret-double-right", "Expand tools", "win.toggle-left-rail", classes=("outlined",))
        exp.set_halign(Gtk.Align.CENTER)
        box.append(exp)
        box.append(hairline(30))
        for item in CAPTURE:
            if item.collapsed:
                b = make(item)
                b.set_halign(Gtk.Align.CENTER)
                box.append(b)
        box.append(hairline(30))
        self._collapsed_tools = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(self._collapsed_tools)
        box.append(Gtk.Box(vexpand=True))
        box.append(hairline(30))
        for item in ACTIONS:
            if item.collapsed:
                b = make(item)
                b.set_halign(Gtk.Align.CENTER)
                box.append(b)
        self._rebuild_collapsed_tools()
        return box

    def collapsed_tool_items(self) -> list[Item]:
        """Subset for the collapsed rail; the active tool is always present."""
        subset = [i for i in TOOLS_A + TOOLS_B if i.collapsed]
        active = self.state.tool
        if active not in [i.target for i in subset]:
            for i in TOOLS_A + TOOLS_B:
                if i.target == active:
                    subset[-1] = i
        return subset

    def _rebuild_collapsed_tools(self) -> None:
        box = self._collapsed_tools
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        for item in self.collapsed_tool_items():
            b = make(item)
            b.set_halign(Gtk.Align.CENTER)
            box.append(b)

    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.left_collapsed else "open")
