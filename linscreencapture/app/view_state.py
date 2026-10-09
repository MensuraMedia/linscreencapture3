"""Observable view state: zoom, rail collapse, active panel and tool."""
from __future__ import annotations
from gi.repository import GObject

TOOLS = ("select", "arrow", "line", "box", "circle", "text", "pen", "marker",
         "blur", "pixelate", "fill", "step", "callout", "crop", "move")
PANELS = ("layers", "props")
ZOOM_STEPS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 8.0, 10.0)


class ViewState(GObject.Object):
    __gtype_name__ = "LscViewState"

    zoom = GObject.Property(type=float, default=1.0, minimum=0.1, maximum=10.0)
    left_collapsed = GObject.Property(type=bool, default=False)
    right_collapsed = GObject.Property(type=bool, default=False)
    left_manual = GObject.Property(type=bool, default=False)
    right_manual = GObject.Property(type=bool, default=False)
    panel = GObject.Property(type=str, default="layers")
    tool = GObject.Property(type=str, default="arrow")
    colour = GObject.Property(type=str, default="#e5484d")
    status = GObject.Property(type=str, default="Ready")
    status_kind = GObject.Property(type=str, default="ok")  # ok | attention | error
    title = GObject.Property(type=str, default="LinScreenCapture")
    subtitle = GObject.Property(type=str, default="")
    library = GObject.Property(type=bool, default=False)  # the Library page covers the stage

    def zoom_step(self, direction: int) -> None:
        steps = ZOOM_STEPS
        if direction > 0:
            nxt = next((s for s in steps if s > self.zoom + 1e-9), steps[-1])
        else:
            nxt = next((s for s in reversed(steps) if s < self.zoom - 1e-9), steps[0])
        self.zoom = nxt

    def toggle_rail(self, side: str, manual: bool = True) -> None:
        prop = f"{side}_collapsed"
        self.set_property(prop, not self.get_property(prop))
        if manual:
            self.set_property(f"{side}_manual", True)
