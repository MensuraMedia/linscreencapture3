"""The 52 px Graphite header, which is also the window's title bar (CSD).

Left: the title block. Centre: the tool-properties strip for the active tool. Right: window controls.
"""
from __future__ import annotations
from gi.repository import Gtk

from .tool_props import ToolProps
from ..app.view_state import ViewState


def _system_layout() -> str:
    """System decoration layout without the app-icon/menu tokens GTK 4 cannot draw here."""
    settings = Gtk.Settings.get_default()
    layout = settings.get_property("gtk-decoration-layout") if settings else "menu:minimize,maximize,close"
    left, _, right = (layout or "").partition(":")
    keep = lambda part: ",".join(t for t in part.split(",") if t and t not in ("icon", "menu"))
    return f"{keep(left)}:{keep(right)}"


class HeaderBar(Gtk.HeaderBar):
    def __init__(self, state: ViewState):
        super().__init__(show_title_buttons=True)
        self.add_css_class("studio-header")
        self.set_decoration_layout(_system_layout())
        self.state = state

        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        block.set_size_request(150, -1)
        self.title = Gtk.Label(label=state.title, xalign=0.0)
        self.title.add_css_class("title")
        self.subtitle = Gtk.Label(label=state.subtitle, xalign=0.0, visible=bool(state.subtitle))
        self.subtitle.add_css_class("subtitle")
        block.append(self.title)
        block.append(self.subtitle)
        self.pack_start(block)

        self.props = ToolProps(state)
        self.set_title_widget(self.props)

        state.connect("notify::title", lambda s, _p: self.title.set_label(s.title))
        state.connect("notify::subtitle", self._subtitle_changed)

    def _subtitle_changed(self, s: ViewState, _p) -> None:
        self.subtitle.set_label(s.subtitle)
        self.subtitle.set_visible(bool(s.subtitle))
