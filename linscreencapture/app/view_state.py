"""Observable view state: zoom, rail collapse, library page, active tool, colour, title."""
from __future__ import annotations
import math

from gi.repository import GObject

TOOLS = ("select", "arrow", "line", "box", "circle", "text", "pen", "marker", "eraser",
         "blur", "pixelate", "fill", "step", "callout", "crop", "move", "hand", "area_box", "area_round", "area_points")
ZOOM_STEP = 1.04          # each Ctrl+wheel notch / Ctrl+plus / Ctrl+minus zooms by 4 % of the current zoom
ZOOM_MAX_STEP = 0.05      # never more than 5 % per step (whole-percent rounding could exceed it at low zoom)
ZOOM_MIN, ZOOM_MAX = 0.1, 10.0


def next_zoom(zoom: float, direction: int, step: float = ZOOM_STEP) -> float:
    """The next zoom level, ``step`` (4 %) up or down from ``zoom``, on whole percents.

    Each step moves at least one percent, and a step that crosses 100 % stops there so 1:1 is always reachable."""
    pct = zoom * 100
    if direction > 0:
        nxt = round(pct * step)
        if nxt - pct > ZOOM_MAX_STEP * pct:                # rounding must not push a step past 5 %
            nxt = math.floor(pct * (1 + ZOOM_MAX_STEP))
        nxt = max(nxt, int(pct + 1e-6) + 1)
        if pct < 100 - 1e-6 < nxt:
            nxt = 100
    else:
        nxt = round(pct / step)
        if pct - nxt > ZOOM_MAX_STEP * pct:
            nxt = math.ceil(pct * (1 - ZOOM_MAX_STEP))
        nxt = min(nxt, math.ceil(pct - 1e-6) - 1)
        if nxt < 100 - 1e-6 < pct - 1e-6:
            nxt = 100
    return max(ZOOM_MIN, min(ZOOM_MAX, nxt / 100))


class ViewState(GObject.Object):
    __gtype_name__ = "LscViewState"

    zoom = GObject.Property(type=float, default=1.0, minimum=0.1, maximum=10.0)
    left_collapsed = GObject.Property(type=bool, default=False)
    right_collapsed = GObject.Property(type=bool, default=False)
    left_manual = GObject.Property(type=bool, default=False)
    right_manual = GObject.Property(type=bool, default=False)
    tool = GObject.Property(type=str, default="arrow")
    colour = GObject.Property(type=str, default="#e5484d")
    status = GObject.Property(type=str, default="Ready")
    status_kind = GObject.Property(type=str, default="ok")  # ok | attention | error
    title = GObject.Property(type=str, default="LinScreenCapture")
    subtitle = GObject.Property(type=str, default="")
    library = GObject.Property(type=bool, default=False)  # the Library page covers the stage

    def zoom_step(self, direction: int) -> None:
        self.zoom = next_zoom(self.zoom, direction)

    def toggle_rail(self, side: str, manual: bool = True) -> None:
        prop = f"{side}_collapsed"
        self.set_property(prop, not self.get_property(prop))
        if manual:
            self.set_property(f"{side}_manual", True)
