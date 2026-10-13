"""Popovers for Resize, Rotate and Brightness, anchored to their rail buttons."""
from __future__ import annotations
from gi.repository import Gtk

from .widgets import compact_spin, labelled, switch, scale_with_value, rail_button
from ..services import icon_loader


def _box(title: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12)
    lbl = Gtk.Label(label=title.upper(), xalign=0.0)
    lbl.add_css_class("group-label")
    box.append(lbl)
    return box


def _buttons(apply_cb, cancel_cb, apply_label: str = "Apply") -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END, margin_top=4)
    cancel = Gtk.Button(label="Cancel")
    cancel.add_css_class("text-btn")
    cancel.connect("clicked", lambda *_: cancel_cb())
    apply = Gtk.Button(label=apply_label)
    apply.add_css_class("primary-pill")
    apply.connect("clicked", lambda *_: apply_cb())
    row.append(cancel)
    row.append(apply)
    return row


class ResizePopover(Gtk.Popover):
    def __init__(self, window):
        super().__init__(autohide=True)
        self.window = window
        self.add_css_class("studio-popover")
        box = _box("Resize")
        self.width = compact_spin(1, 20000, 100, tooltip="Width in px")
        self.height = compact_spin(1, 20000, 100, tooltip="Height in px")
        self.percent = compact_spin(1, 1000, 100, tooltip="Percent of the current size")
        self.lock = switch(True, "Keep aspect ratio")
        self._guard = False
        box.append(labelled("Width", self.width))
        box.append(labelled("Height", self.height))
        box.append(labelled("Percent", self.percent))
        box.append(labelled("Keep ratio", self.lock))
        box.append(_buttons(self._apply, self.popdown))
        self.set_child(box)
        self.width.connect("value-changed", lambda w: self._changed("w"))
        self.height.connect("value-changed", lambda w: self._changed("h"))
        self.percent.connect("value-changed", lambda w: self._changed("p"))
        self.connect("show", lambda *_: self._load())

    def _load(self) -> None:
        doc = self.window.document
        if doc is None or doc.empty:
            return
        self._guard = True
        self.width.set_value(doc.width)
        self.height.set_value(doc.height)
        self.percent.set_value(100)
        self._guard = False

    def _changed(self, which: str) -> None:
        if self._guard:
            return
        doc = self.window.document
        if doc is None or doc.empty:
            return
        self._guard = True
        try:
            if which == "p":
                f = self.percent.get_value() / 100.0
                self.width.set_value(max(1, round(doc.width * f)))
                self.height.set_value(max(1, round(doc.height * f)))
            elif self.lock.get_active():
                if which == "w":
                    self.height.set_value(max(1, round(self.width.get_value() * doc.height / doc.width)))
                else:
                    self.width.set_value(max(1, round(self.height.get_value() * doc.width / doc.height)))
                self.percent.set_value(max(1, round(self.width.get_value() * 100 / doc.width)))
        finally:
            self._guard = False

    def _apply(self) -> None:
        self.popdown()
        self.window.image_op("scale", int(self.width.get_value()), int(self.height.get_value()))


class RotatePopover(Gtk.Popover):
    def __init__(self, window):
        super().__init__(autohide=True)
        self.window = window
        box = _box("Rotate · flip")
        grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for icon, label, args in (("arrow-clockwise", "Rotate 90° clockwise", ("rotate", 90)),
                                  ("arrow-counter-clockwise", "Rotate 90° counter-clockwise", ("rotate", 270)),
                                  ("arrows-clockwise", "Rotate 180°", ("rotate", 180)),
                                  ("arrows-horizontal", "Flip horizontal", ("flip", True)),
                                  ("arrows-vertical", "Flip vertical", ("flip", False))):
            b = rail_button(icon, label)
            b.connect("clicked", lambda _b, a=args: (self.popdown(), window.image_op(*a)))
            grid.append(b)
        box.append(grid)
        self.set_child(box)


class AdjustPopover(Gtk.Popover):
    """Brightness, contrast, grayscale, invert with a live preview on the stage."""

    def __init__(self, window):
        super().__init__(autohide=True)
        self.window = window
        box = _box("Brightness · colour")
        self.brightness, b = scale_with_value(-100, 100, 0, width=160, tooltip="Brightness")
        self.contrast, c = scale_with_value(-100, 100, 0, width=160, tooltip="Contrast")
        self.gray = switch(False, "Grayscale")
        self.invert = switch(False, "Invert colours")
        box.append(labelled("Bright", b))
        box.append(labelled("Contrast", c))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        row.append(labelled("Grayscale", self.gray))
        row.append(labelled("Invert", self.invert))
        box.append(row)
        box.append(_buttons(self._apply, self._cancel))
        self.set_child(box)
        for w, sig in ((self.brightness, "value-changed"), (self.contrast, "value-changed"),
                       (self.gray, "notify::active"), (self.invert, "notify::active")):
            w.connect(sig, lambda *_: self._preview())
        self.connect("closed", lambda *_: self.window.preview_base(None))
        self.connect("show", lambda *_: self._reset())

    def params(self) -> dict:
        return {"brightness": self.brightness.get_value(), "contrast": self.contrast.get_value(),
                "grayscale": self.gray.get_active(), "invert": self.invert.get_active()}

    def _reset(self) -> None:
        self.brightness.set_value(0); self.contrast.set_value(0)
        self.gray.set_active(False); self.invert.set_active(False)

    def _preview(self) -> None:
        if not self.get_visible():
            return
        doc = self.window.document
        if doc is None or doc.empty:
            return
        from ..app import image_ops
        self.window.preview_base(image_ops.adjust(doc.base, **self.params()))

    def _apply(self) -> None:
        params = self.params()
        self.window.preview_base(None)
        self.popdown()
        self.window.image_op("adjust", params)

    def _cancel(self) -> None:
        self.window.preview_base(None)
        self.popdown()
