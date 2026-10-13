"""Editing and tool shortcuts that must never steal keys from a text field.

GTK runs application accelerators in the CAPTURE phase, before the focused widget, so a
single-letter accelerator such as "a" for Arrow fires while the user is typing in the inline
text editor. Keys that compete with typing are therefore handled here, in a controller on the
window that yields whenever a real text field (the inline text entry, the hex entry, anything
inside a popover) has focus and no drag is in progress.

The controller runs in the CAPTURE phase because of spin buttons: after a click on the header
strip's Width spin the focus sits in its text field, whose own bindings swallow Ctrl+Z and tool
letters before they could bubble up. In a spin button only the editing chords (Ctrl+Z/Y/C/V/D),
tool letters and Escape are taken, and the focus is handed back to the canvas; digits, Enter,
Delete and arrows still reach the spin. Global chords (Ctrl+N, Ctrl+S, Ctrl+L, Ctrl+[, zoom,
Ctrl+,, Ctrl+Q) stay as application accelerators because they do not collide with text entry.
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


def focus_kind(window: Gtk.Window) -> str:
    """'text' (a real text field or a popover: typing wins), 'spin' (a numeric spin button), or 'other'."""
    focus = window.get_focus()
    if focus is None:
        return "other"
    if focus.get_ancestor(Gtk.Popover) is not None:
        return "text"
    if focus.get_ancestor(Gtk.SpinButton) is not None:
        return "spin"
    if isinstance(focus, (Gtk.Editable, Gtk.Text, Gtk.TextView)) or focus.get_ancestor(Gtk.Entry) is not None:
        return "text"
    return "other"


def focus_is_editable(window: Gtk.Window) -> bool:
    """True when keystrokes must go to the focused widget untouched."""
    return focus_kind(window) == "text"


class ShortcutRouter:
    def __init__(self, window):
        self.window = window
        ctl = Gtk.EventControllerKey()
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctl.connect("key-pressed", lambda c, keyval, code, state: self.handle(keyval, state))
        window.add_controller(ctl)

    def _leave_spin(self) -> None:
        self.window.stage.canvas.grab_focus()

    def handle(self, keyval: int, state: Gdk.ModifierType) -> bool:
        win = self.window
        kind = focus_kind(win)
        if kind == "text" or win.stage.text_entry.get_visible():
            return False                                  # typing wins, always
        in_spin = kind == "spin"
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        lower = Gdk.keyval_to_lower(keyval)

        def act(name: str) -> bool:
            if in_spin:
                self._leave_spin()
            win.activate_action(f"win.{name}", None)
            return True

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
        if in_spin:
            if keyval == Gdk.KEY_Escape:
                self._leave_spin()
                return True
            if not alt and not shift and lower in TOOL_KEYS and win.editor._mode is None and not win.state.library:
                self._leave_spin()
                win.state.tool = TOOL_KEYS[lower]
                return True
            return False                                  # digits, Enter, Delete, arrows edit the number
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
