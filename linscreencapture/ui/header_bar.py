"""The 52 px Graphite header, which is also the window's title bar (CSD)."""
from __future__ import annotations
from gi.repository import Gtk

from .widgets import StatusChip, ZoomPill
from ..services import icon_loader
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

        # title block (left), status chip
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        block.set_size_request(150, -1)
        self.title = Gtk.Label(label=state.title, xalign=0.0)
        self.title.add_css_class("title")
        self.subtitle = Gtk.Label(label=state.subtitle, xalign=0.0)
        self.subtitle.add_css_class("subtitle")
        block.append(self.title)
        block.append(self.subtitle)
        self.pack_start(block)
        self.chip = StatusChip(state.status, state.status_kind)
        self.chip.set_margin_start(14)
        self.pack_start(self.chip)
        self.set_title_widget(Gtk.Box())  # empty centre: the mockup's flexible spacer

        # capture button (rightmost), zoom pill before it
        self.capture = Gtk.Button()
        cb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cb.append(icon_loader.icon("camera", 18))
        cb.append(Gtk.Label(label="Capture"))
        self.capture.set_child(cb)
        self.capture.add_css_class("primary-pill")
        self.capture.set_tooltip_text("Capture a new screenshot")
        self.capture.update_property([Gtk.AccessibleProperty.LABEL], ["Capture a new screenshot"])
        self.capture.set_action_name("app.capture-region")
        self.capture.set_valign(Gtk.Align.CENTER)
        self.pack_end(self.capture)
        self.zoom = ZoomPill()
        self.zoom.set_margin_end(14)
        self.pack_end(self.zoom)

        state.connect("notify::title", lambda s, _p: self.title.set_label(s.title))
        state.connect("notify::subtitle", lambda s, _p: self.subtitle.set_label(s.subtitle))
        state.connect("notify::status", lambda s, _p: self.chip.set_text(s.status))
        state.connect("notify::status-kind", lambda s, _p: self.chip.set_kind(s.status_kind))
        state.connect("notify::zoom", lambda s, _p: self.zoom.set_zoom(s.zoom))
