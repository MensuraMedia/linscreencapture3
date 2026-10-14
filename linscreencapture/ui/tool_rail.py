"""Left rail: capture modes, tools, actions, clipboard tray, Library. Open (220 px) and collapsed (56 px) pages."""
from __future__ import annotations
from dataclasses import dataclass

from gi.repository import Gtk

from .widgets import rail_button, group_label, hairline, flow_group, rail_page, pin_width
from .clip_tray import ClipTray, ClipTrayButton
from ..services import icon_loader
from ..app.view_state import ViewState
from ..app.shortcuts import KEY_FOR_TOOL

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
    key: str | None = None       # shortcut shown under the tooltip caption


def _tool(icon: str, label: str, tool: str, collapsed: bool, group: str) -> Item:
    return Item(icon, label, "win.tool", tool, collapsed, True, (), group, KEY_FOR_TOOL.get(tool))


CAPTURE = (
    Item("selection", "Region", "win.capture-mode", "region", True, True, (), "capture", "Ctrl+N captures"),
    Item("app-window", "Window", "win.capture-mode", "window", False, True, (), "capture"),
    Item("monitor", "Full screen", "win.capture-mode", "screen", True, True, (), "capture", "Ctrl+Shift+N"),
    Item("arrows-vertical", "Scrolling", "win.capture-mode", "scrolling", False, True, (), "capture"),
    Item("timer", "Delay the capture (seconds set in Settings) · click again to turn the delay off",
         "win.capture-delayed", None, True, True, (), "capture"),
    Item("push-pin", "Pin to screen", "app.pin", None, False, False, (), "capture"),
)
TOOLS_A = (
    _tool("cursor", "Select", "select", False, "tools"),
    _tool("arrow-up-right", "Arrow", "arrow", True, "tools"),
    _tool("line-segment", "Line", "line", False, "tools"),
    _tool("square", "Box", "box", True, "tools"),
    _tool("circle", "Circle", "circle", False, "tools"),
    _tool("text-t", "Text", "text", True, "tools"),
    _tool("pencil-simple", "Pen", "pen", True, "tools"),
    _tool("highlighter", "Marker", "marker", False, "tools"),
    _tool("eraser", "Eraser (clears to transparent)", "eraser", False, "tools"),
    _tool("hand", "Hand · drag to pan the view", "hand", False, "tools"),
)
TOOLS_B = (
    _tool("bounding-box", "Box area · mark a rectangle", "area_box", False, "edit"),
    _tool("circle-dashed", "Round area · mark an oval", "area_round", False, "edit"),
    _tool("polygon", "Point chain · click points, close on the first", "area_points", False, "edit"),
    _tool("drop-half", "Blur", "blur", True, "edit"),
    _tool("checkerboard", "Pixelate", "pixelate", False, "edit"),
    _tool("paint-bucket", "Fill", "fill", False, "edit"),
    _tool("number-circle-one", "Step number", "step", True, "edit"),
    _tool("chat-teardrop", "Callout", "callout", False, "edit"),
    _tool("crop", "Crop", "crop", True, "edit"),
    Item("arrows-out", "Resize", "win.resize", None, False, False, (), "edit"),
    Item("arrow-clockwise", "Rotate", "win.rotate", None, False, False, (), "edit"),
    Item("sun", "Brightness", "win.adjust", None, False, False, (), "edit"),
    _tool("arrows-out-cardinal", "Move", "move", False, "edit"),
    Item("copy-simple", "Duplicate", "win.duplicate-file", None, False, False, (), "edit"),
)
LIBRARY = Item("images", "Library", "win.library", None, True, True, (), "library", "Ctrl+L")
ACTIONS = (
    Item("trash", "Discard", "win.discard", None, True, False, ("danger",), "actions"),
    Item("download-simple", "Save", "win.save", None, True, False, ("primary",), "actions", "Ctrl+S"),
)
ALL_ITEMS = CAPTURE + TOOLS_A + TOOLS_B + (LIBRARY,) + ACTIONS


def make(item: Item) -> Gtk.Button:
    return rail_button(item.icon, item.label, item.action, item.target, item.classes, toggle=item.toggle, key=item.key)


def capture_button() -> Gtk.Button:
    """The Capture button: a 30 px accent icon in both rail states (never a full-width button)."""
    return rail_button("camera", "Capture a new screenshot", "app.capture", classes=("primary",), key="Ctrl+N")


class ToolRail(Gtk.Stack):
    def __init__(self, state: ViewState, clips=None, on_paste=None):
        super().__init__(hhomogeneous=False, vhomogeneous=True, interpolate_size=True,
                         transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.set_hexpand(False)  # explicit: children with hexpand must not widen the rail
        self.set_vexpand(True)
        self.state = state
        self.clips = clips
        self.on_paste = on_paste
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
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_bottom=10)
        self.capture = capture_button()
        top.append(self.capture)
        top.append(Gtk.Box(hexpand=True))
        top.append(rail_button("caret-left", "Collapse tools", "win.toggle-left-rail", key="Ctrl+["))
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
        if self.clips is not None:                       # clipboard tray: navigator-sized, above Library
            lbl = group_label("Clipboard")
            lbl.set_margin_top(8)
            box.append(lbl)
            self.tray = ClipTray(self.clips, self.on_paste)
            self.tray.set_margin_top(4)
            self.tray.set_margin_bottom(10)
            box.append(self.tray)
        self.library = make(LIBRARY)                 # always visible, just above the Actions line
        self.library.set_halign(Gtk.Align.START)
        self.library.set_margin_bottom(10)
        box.append(self.library)
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
        exp = rail_button("caret-right", "Expand tools", "win.toggle-left-rail", classes=("outlined",), key="Ctrl+[")
        exp.set_halign(Gtk.Align.CENTER)
        box.append(exp)
        cap = capture_button()
        cap.set_halign(Gtk.Align.CENTER)
        box.append(cap)
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
        if self.clips is not None:
            self.tray_button = ClipTrayButton(self.clips, self.on_paste)
            self.tray_button.set_halign(Gtk.Align.CENTER)
            box.append(self.tray_button)
        lib = make(LIBRARY)
        lib.set_halign(Gtk.Align.CENTER)
        box.append(lib)
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

    def button_for(self, action: str):
        """The visible rail button bound to ``action`` (open page preferred), or None."""
        page = self.get_visible_child()
        for root in (page, self):
            stack = [root]
            while stack:
                w = stack.pop()
                if isinstance(w, Gtk.Button) and w.get_action_name() == action and w.get_mapped():
                    return w
                c = w.get_first_child()
                while c is not None:
                    stack.append(c)
                    c = c.get_next_sibling()
        return None

    def _sync(self, *_a) -> None:
        self.set_visible_child_name("collapsed" if self.state.left_collapsed else "open")
