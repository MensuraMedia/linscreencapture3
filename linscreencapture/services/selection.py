"""Pure geometry for the capture overlay's selection rectangle (testable without GTK)."""
from __future__ import annotations
from dataclasses import dataclass

HANDLE = 9          # handle square size in px
HIT = 7             # half the hit zone around a handle
HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")


@dataclass
class Selection:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def rect(self) -> tuple[int, int, int, int]:
        x, y = min(self.x1, self.x2), min(self.y1, self.y2)
        return int(round(x)), int(round(y)), int(round(abs(self.x2 - self.x1))), int(round(abs(self.y2 - self.y1)))

    @property
    def is_empty(self) -> bool:
        _x, _y, w, h = self.rect
        return w < 2 or h < 2

    def normalised(self) -> "Selection":
        x, y, w, h = self.rect
        return Selection(x, y, x + w, y + h)

    def handle_positions(self) -> dict[str, tuple[float, float]]:
        x, y, w, h = self.rect
        cx, cy = x + w / 2, y + h / 2
        return {"nw": (x, y), "n": (cx, y), "ne": (x + w, y), "e": (x + w, cy),
                "se": (x + w, y + h), "s": (cx, y + h), "sw": (x, y + h), "w": (x, cy)}

    def hit(self, px: float, py: float) -> str | None:
        """'nw'…'w' for a handle, 'inside' for the body, None outside."""
        for name, (hx, hy) in self.handle_positions().items():
            if abs(px - hx) <= HIT and abs(py - hy) <= HIT:
                return name
        x, y, w, h = self.rect
        if x <= px <= x + w and y <= py <= y + h:
            return "inside"
        return None

    def resized(self, handle: str, px: float, py: float, square: bool = False) -> "Selection":
        """Move ``handle`` to (px, py); the opposite edge (or corner) stays put."""
        x, y, w, h = self.rect
        l, t, r, b = x, y, x + w, y + h
        if "w" in handle:
            l = px
        if "e" in handle:
            r = px
        if "n" in handle:
            t = py
        if "s" in handle:
            b = py
        if square and handle in ("nw", "ne", "sw", "se"):
            side = max(abs(r - l), abs(b - t))
            if "w" in handle:
                l = r - side
            else:
                r = l + side
            if "n" in handle:
                t = b - side
            else:
                b = t + side
        return Selection(l, t, r, b)

    def moved(self, dx: float, dy: float) -> "Selection":
        return Selection(self.x1 + dx, self.y1 + dy, self.x2 + dx, self.y2 + dy)

    def clamped(self, bx: int, by: int, bw: int, bh: int) -> "Selection":
        """Keep the whole rectangle inside the bounds (moving it, not shrinking it)."""
        x, y, w, h = self.rect
        w, h = min(w, bw), min(h, bh)
        x = max(bx, min(x, bx + bw - w))
        y = max(by, min(y, by + bh - h))
        return Selection(x, y, x + w, y + h)

    def cursor_for(self, where: str | None) -> str:
        return {"nw": "nw-resize", "se": "se-resize", "ne": "ne-resize", "sw": "sw-resize", "n": "n-resize",
                "s": "s-resize", "e": "e-resize", "w": "w-resize", "inside": "move"}.get(where or "", "crosshair")


def square_end(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    side = max(abs(x2 - x1), abs(y2 - y1))
    return x1 + (side if x2 >= x1 else -side), y1 + (side if y2 >= y1 else -side)
