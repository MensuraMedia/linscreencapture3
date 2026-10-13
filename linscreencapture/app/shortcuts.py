"""Editing and tool shortcuts that must never steal keys from a text field.

GTK runs application accelerators in the CAPTURE phase, before the focused widget, so a
single-letter accelerator such as "a" for Arrow fires while the user is typing in the inline
text editor or a spin button. Keys that compete with typing are therefore handled here, in a
BUBBLE-phase controller on the window: they only run when nothing editable has focus and no
drag is in progress. Global chords (Ctrl+N, Ctrl+S, Ctrl+L, Ctrl+[, zoom, Ctrl+,, Ctrl+Q) stay
as application accelerators because they do not collide with text entry.
"""
from __future__ import annotations
from gi.repository import Gdk, Gtk

TOOL_KEYS = {
    Gdk.KEY_v: "select", Gdk.KEY_a: "arrow", Gdk.KEY_l: "line", Gdk.KEY_b: "box", Gdk.KEY_c: "circle",
    Gdk.KEY_t: "text", Gdk.KEY_p: "pen", Gdk.KEY_m: "marker", Gdk.KEY_u: "blur", Gdk.KEY_x: "pixelate",
    Gdk.KEY_n: "step", Gdk.KEY_k: "crop",
}
TOOL_KEY_LABELS = {"V": "Select", "A": "Arrow", "L": "Line", "B": "Box", "C": "Circle", "T": "Text", "P": "Pen",
                   "M": "Marker", "U": "Blur", "X": "Pixelate", "N": "Step number", "K": "Crop"}


def focus_is_editable(window: Gtk.Window) -> bool:
    focus = window.get_focus()
    if focus is None:
        return False
    if isinstance(focus, (Gtk.Editable, Gtk.Text, Gtk.TextView)):
        return True
    return focus.get_ancestor(Gtk.SpinButton) is not None or focus.get_ancestor(Gtk.Entry) is not None


class ShortcutRouter:
    def __init__(self, window):
        self.window = window
        ctl = Gtk.EventControllerKey()
        ctl.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        ctl.connect("key-pressed", lambda c, keyval, code, state: self.handle(keyval, state))
        window.add_controller(ctl)

    def handle(self, keyval: int, state: Gdk.ModifierType) -> bool:
        win = self.window
        if focus_is_editable(win) or win.stage.text_entry.get_visible():
            return False                                  # typing wins, always
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        lower = Gdk.keyval_to_lower(keyval)
        act = lambda name: (win.activate_action(f"win.{name}", None), True)[1]  # noqa: E731
        if ctrl and not alt:
            if lower == Gdk.KEY_z:
                return act("redo" if shift else "undo")
            if lower == Gdk.KEY_y:
                return act("redo")
            if lower == Gdk.KEY_d:
                return act("duplicate-layer")
            if lower == Gdk.KEY_c:
                return act("copy")
            if lower == Gdk.KEY_v:
                return act("paste")
            return False
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            return act("library-delete" if win.state.library else "delete-layer")
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return win.editor.apply_crop()
        if keyval == Gdk.KEY_Escape:
            if win.state.library:
                return act("library")
            if win.editor.cancel_crop():
                return True
            if win.editor.eyedropper:
                win.editor.eyedropper = False
                return True
            if win.editor.selected_id is not None:
                win.editor.select(None)
                return True
            return False
        if not alt and not shift and lower in TOOL_KEYS:
            if win.editor._mode is not None or win.state.library:
                return True                               # swallow: never switch tools mid-drag
            win.state.tool = TOOL_KEYS[lower]
            return True
        return False
