"""Centre stage: empty-state placeholder now, the document canvas from Phase 4."""
from __future__ import annotations
from gi.repository import Gtk

from ..services import icon_loader
from ..app.view_state import ViewState


def _kind(text: str) -> Gtk.Label:
    l = Gtk.Label(label=text)
    l.add_css_class("kind")
    return l


class Stage(Gtk.Overlay):
    def __init__(self, state: ViewState):
        super().__init__(hexpand=True, vexpand=True)
        self.state = state
        self.add_css_class("stage")
        self.pages = Gtk.Stack(hexpand=True, vexpand=True)
        self.pages.add_named(self._build_empty(), "empty")
        # canvas page (Phase 4 draws into it)
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.canvas)
        self.pages.add_named(scroller, "canvas")
        self.pages.set_visible_child_name("empty")
        self.set_child(self.pages)

        self.hud = Gtk.Label(label="—", halign=Gtk.Align.START, valign=Gtk.Align.END,
                             margin_start=16, margin_bottom=16)
        self.hud.add_css_class("hud")
        self.add_overlay(self.hud)
        state.connect("notify::zoom", self._update_hud)

    def _build_empty(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        glyph = icon_loader.icon("camera", 48)
        glyph.add_css_class("empty-glyph")
        box.append(glyph)
        t = Gtk.Label(label="Press PrintScreen or click Capture")
        t.add_css_class("empty-title")
        box.append(t)
        s = Gtk.Label(label="Region · Window · Full screen · Delayed · Pin")
        s.add_css_class("empty-sub")
        box.append(s)
        keys = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.CENTER, margin_top=6)
        for combo, what in (("Ctrl+N", "region"), ("Ctrl+Shift+N", "full screen"), ("Ctrl+V", "paste")):
            k = _kind(combo)
            if what != "region":
                k.set_margin_start(8)
            keys.append(k)
            w = Gtk.Label(label=what)
            w.add_css_class("empty-sub")
            keys.append(w)
        box.append(keys)
        return box

    def _update_hud(self, *_a) -> None:
        if self.pages.get_visible_child_name() == "empty":
            self.hud.set_label("—")
        else:
            self.hud.set_label(f"{round(self.state.zoom * 100):d}%")
