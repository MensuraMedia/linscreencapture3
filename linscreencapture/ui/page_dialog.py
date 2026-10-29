"""Page settings: the page size (with an anchor for where the picture stays), the fill behind its transparent parts
and the stage colour around it. Opened from the right rail's Page button (``win.page-settings``).

Nothing changes until Apply: size and fill become one undo step (``EditorController.apply_page``); the stage colour
and the last fill colour are settings (``[Stage]``).
"""
from __future__ import annotations
from gi.repository import Adw, Gdk, Gtk

ANCHORS = [(ax, ay) for ay in (0.0, 0.5, 1.0) for ax in (0.0, 0.5, 1.0)]   # reading order, centre at index 4
_ANCHOR_NAMES = ("top left", "top", "top right", "left", "centre", "right", "bottom left", "bottom", "bottom right")
THEME_STAGE = "#242424"   # the stylesheet's @stage, shown when no stage colour is set


def _rgba(hx: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hx)
    return c


def _hex(c: Gdk.RGBA) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in (c.red, c.green, c.blue))


def _colour_button(title: str, hx: str) -> Gtk.ColorDialogButton:
    b = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title=title, with_alpha=False), valign=Gtk.Align.CENTER)
    b.set_rgba(_rgba(hx))
    return b


class PageDialog(Adw.Dialog):
    def __init__(self, editor):
        super().__init__(title="Page", content_width=420)
        self.editor = editor
        doc, s = editor.doc, editor.settings
        self._ratio = doc.width / doc.height if doc.height else 1.0
        self._syncing = False

        page = Adw.PreferencesPage()
        size = Adw.PreferencesGroup(title="Size", description=f"Now {doc.width} × {doc.height} px")
        self.width = Adw.SpinRow.new_with_range(1, 16384, 1)
        self.width.set_title("Width")
        self.width.set_value(doc.width)
        self.height = Adw.SpinRow.new_with_range(1, 16384, 1)
        self.height.set_title("Height")
        self.height.set_value(doc.height)
        self.keep = Adw.SwitchRow(title="Keep proportions", active=False)
        self.width.connect("notify::value", lambda *_: self._linked(self.width))
        self.height.connect("notify::value", lambda *_: self._linked(self.height))
        anchor = Adw.ActionRow(title="Anchor", subtitle="Where the picture stays when the page grows or shrinks")
        grid = Gtk.Grid(row_spacing=2, column_spacing=2, valign=Gtk.Align.CENTER)
        self.anchors: list[Gtk.ToggleButton] = []
        for n, name in enumerate(_ANCHOR_NAMES):
            b = Gtk.ToggleButton(active=(n == 4), tooltip_text=f"Anchor {name}")
            b.add_css_class("anchor-cell")
            b.set_size_request(18, 18)
            if self.anchors:
                b.set_group(self.anchors[0])
            grid.attach(b, n % 3, n // 3, 1, 1)
            self.anchors.append(b)
        anchor.add_suffix(grid)
        for row in (self.width, self.height, self.keep, anchor):
            size.add(row)
        page.add(size)

        fill = Adw.PreferencesGroup(title="Fill", description="Painted behind the page's transparent parts; "
                                                              "kept when you save, copy or flatten")
        self.fill = Adw.SwitchRow(title="Fill transparent areas", active=doc.background is not None)
        self.fill_colour = _colour_button("Page fill", doc.background or s.page_fill)
        colour = Adw.ActionRow(title="Colour")
        colour.add_suffix(self.fill_colour)
        self.fill.bind_property("active", colour, "sensitive", 2)   # GObject.BindingFlags.SYNC_CREATE
        self.fill_colour.connect("notify::rgba", lambda *_: self.fill.set_active(True))
        fill.add(self.fill)
        fill.add(colour)
        page.add(fill)

        stage = Adw.PreferencesGroup(title="Stage", description="The workspace around the page; not part of the image")
        self.stage_colour = _colour_button("Stage colour", s.stage_colour or THEME_STAGE)
        self._stage_custom = bool(s.stage_colour)
        self.stage_colour.connect("notify::rgba", lambda *_: setattr(self, "_stage_custom", True) if not self._syncing else None)
        reset = Gtk.Button(icon_name="lsc-arrow-counter-clockwise-symbolic", valign=Gtk.Align.CENTER,
                           tooltip_text="Back to the theme's colour")
        reset.add_css_class("flat")
        reset.connect("clicked", lambda *_: self._reset_stage())
        row = Adw.ActionRow(title="Colour")
        row.add_suffix(reset)
        row.add_suffix(self.stage_colour)
        stage.add(row)
        page.add(stage)

        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", lambda *_: self.apply())
        header.pack_start(cancel)
        header.pack_end(self.apply_btn)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(header)
        self.set_child(view)
        self.set_default_widget(self.apply_btn)

    # -- helpers --------------------------------------------------------------
    def _linked(self, changed: Adw.SpinRow) -> None:
        if self._syncing or not self.keep.get_active():
            return
        self._syncing = True
        try:
            if changed is self.width:
                self.height.set_value(max(1, round(self.width.get_value() / self._ratio)))
            else:
                self.width.set_value(max(1, round(self.height.get_value() * self._ratio)))
        finally:
            self._syncing = False

    def _reset_stage(self) -> None:
        self._syncing = True
        try:
            self.stage_colour.set_rgba(_rgba(THEME_STAGE))
        finally:
            self._syncing = False
        self._stage_custom = False

    @property
    def anchor(self) -> tuple[float, float]:
        return next((ANCHORS[n] for n, b in enumerate(self.anchors) if b.get_active()), (0.5, 0.5))

    def set_anchor(self, n: int) -> None:
        self.anchors[n].set_active(True)

    # -- apply ----------------------------------------------------------------
    def apply(self) -> None:
        ed, s = self.editor, self.editor.settings
        fill_hex = _hex(self.fill_colour.get_rgba())
        stage = _hex(self.stage_colour.get_rgba()) if self._stage_custom else ""
        changed = (s.page_fill, s.stage_colour) != (fill_hex, stage)
        s.page_fill, s.stage_colour = fill_hex, stage
        if changed:
            try:
                s.save()
            except Exception as exc:  # noqa: BLE001
                print(f"settings not saved: {exc}")
        ed.stage.set_stage_colour(stage)
        ed.apply_page(int(self.width.get_value()), int(self.height.get_value()),
                      fill_hex if self.fill.get_active() else None, self.anchor)
        self.close()
