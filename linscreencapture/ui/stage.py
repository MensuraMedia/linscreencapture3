"""Centre stage: empty-state placeholder now, the document canvas from Phase 4."""
from __future__ import annotations
from gi.repository import Gtk

from ..services import icon_loader
from ..app.view_state import ViewState
from ..model.captures_index import CapturesIndex
from .library_page import LibraryPage


def _kind(text: str) -> Gtk.Label:
    l = Gtk.Label(label=text)
    l.add_css_class("kind")
    return l


class Stage(Gtk.Overlay):
    def __init__(self, state: ViewState, captures: CapturesIndex):
        super().__init__(hexpand=True, vexpand=True)
        self.state = state
        self.add_css_class("stage")
        self.pages = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        self.pages.add_named(self._build_empty(), "empty")
        self.library = LibraryPage(captures)
        self.pages.add_named(self.library, "library")
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
        state.connect("notify::library", self._library_changed)
        self._editor_page = "empty"

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

    def _library_changed(self, *_a) -> None:
        if self.state.library:
            if self.pages.get_visible_child_name() != "library":
                self._editor_page = self.pages.get_visible_child_name()
            self.pages.set_visible_child_name("library")
            self.hud.set_visible(False)
        else:
            self.pages.set_visible_child_name(self._editor_page)
            self.hud.set_visible(True)
