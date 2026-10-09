"""Centre stage: empty-state placeholder now, the document canvas from Phase 4."""
from __future__ import annotations
import cairo
from gi.repository import Gdk, Gtk

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
        # canvas page: the document, scaled by ViewState.zoom, centred in a scrolled viewport
        self.document = None
        self._composite = None
        self.on_change: list = []   # callbacks when the composite or document changes (navigator)
        self.canvas = Gtk.DrawingArea(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.canvas.set_draw_func(self._draw_canvas)
        self.scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.canvas)
        self.pages.add_named(self.scroller, "canvas")
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._scroll)
        self.scroller.add_controller(scroll)
        self.pages.set_visible_child_name("empty")
        self.set_child(self.pages)

        self.hud = Gtk.Label(label="—", halign=Gtk.Align.START, valign=Gtk.Align.END,
                             margin_start=16, margin_bottom=16)
        self.hud.add_css_class("hud")
        self.add_overlay(self.hud)
        state.connect("notify::zoom", self._update_hud)
        state.connect("notify::zoom", lambda *_: self._resize_canvas())
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
        if self._composite is None:
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

    # -- document ---------------------------------------------------------
    MARGIN = 40

    def set_document(self, doc) -> None:
        self.document = doc
        self._composite = doc.flatten() if doc is not None and not doc.empty else None
        self._editor_page = "canvas" if self._composite is not None else "empty"
        if not self.state.library:
            self.pages.set_visible_child_name(self._editor_page)
        self._resize_canvas()
        self._update_hud()
        self._notify()

    def refresh(self) -> None:
        """Re-composite after the document changed (Phase 4 calls this on every edit)."""
        if self.document is not None and not self.document.empty:
            self._composite = self.document.flatten()
        self.canvas.queue_draw()
        self._notify()

    def _notify(self) -> None:
        for cb in list(self.on_change):
            cb()

    @property
    def composite(self):
        return self._composite

    def image_origin(self) -> tuple[float, float]:
        """Where the image's top-left sits inside the canvas widget (it is centred with a margin)."""
        if self._composite is None:
            return 0.0, 0.0
        z = self.state.zoom
        return ((self.canvas.get_width() - self._composite.get_width() * z) / 2,
                (self.canvas.get_height() - self._composite.get_height() * z) / 2)

    def fit_zoom(self) -> float:
        """Zoom that fits the document in the viewport (never above 1:1)."""
        if self._composite is None:
            return 1.0
        vw = max(1, self.scroller.get_width() - self.MARGIN)
        vh = max(1, self.scroller.get_height() - self.MARGIN)
        return max(0.1, min(1.0, vw / self._composite.get_width(), vh / self._composite.get_height()))

    def _resize_canvas(self) -> None:
        if self._composite is None:
            return
        z = self.state.zoom
        self.canvas.set_content_width(int(self._composite.get_width() * z) + self.MARGIN)
        self.canvas.set_content_height(int(self._composite.get_height() * z) + self.MARGIN)
        self.canvas.queue_draw()

    def _draw_canvas(self, _area, cr, w: int, h: int) -> None:
        if self._composite is None:
            return
        z = self.state.zoom
        iw, ih = self._composite.get_width() * z, self._composite.get_height() * z
        x, y = (w - iw) / 2, (h - ih) / 2
        # soft drop shadow outside the image; the image itself is painted pixel-exact, square-cornered
        for i, a in ((12, 0.10), (6, 0.14), (2, 0.18)):
            cr.set_source_rgba(0, 0, 0, a)
            cr.rectangle(x - i / 2, y + 4 + i / 2, iw + i, ih + i)
            cr.fill()
        cr.save()
        cr.rectangle(x, y, iw, ih)
        cr.clip()
        cr.translate(x, y)
        cr.scale(z, z)
        cr.set_source_surface(self._composite, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD if z < 1 else cairo.FILTER_NEAREST if z >= 4 else cairo.FILTER_BILINEAR)
        cr.paint()
        cr.restore()

    @staticmethod
    def _rounded(cr, x, y, w, h, r) -> None:
        import math
        r = min(r, w / 2, h / 2)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _scroll(self, controller, _dx: float, dy: float) -> bool:
        if controller.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            self.state.zoom_step(-1 if dy > 0 else +1)
            return True
        return False
