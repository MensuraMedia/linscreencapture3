import pytest

from linscreencapture.app import tools
from linscreencapture.model.annotations import Annotation, Style


def test_drag_tools_build_annotations_and_reject_tiny_drags():
    st = Style(colour="#0091ff", width=3)
    a = tools.annotation_from_drag("arrow", 10, 10, 100, 40, st)
    assert a.kind == "arrow" and (a.x2, a.y2) == (100, 40) and a.style.colour == "#0091ff" and a.style is not st
    assert tools.annotation_from_drag("arrow", 10, 10, 11, 11, st) is None
    assert tools.annotation_from_drag("box", 10, 10, 50, 12, st) is None
    s = tools.annotation_from_drag("line", 0, 0, 100, 10, st, shift=True)
    assert s.y2 == pytest.approx(0) and s.x2 == pytest.approx((100 ** 2 + 10 ** 2) ** 0.5)
    b = tools.annotation_from_drag("box", 0, 0, 40, 10, st, ctrl=True)
    assert b.rect == (0, 0, 40, 40)
    assert tools.annotation_from_drag("crop", 0, 0, 40, 40, st) is None
    assert tools.annotation_from_drag("callout", 5, 5, 6, 6, st).kind == "callout"


def test_strokes_and_clicks():
    st = Style()
    p = tools.annotation_from_points("pen", [(0, 0), (0.2, 0.1), (10, 10), (20, 5)], st)
    assert p.points == [(0, 0), (10, 10), (20, 5)] and (p.x2, p.y2) == (20, 5)
    assert tools.annotation_from_points("box", [(0, 0)], st) is None
    t = tools.annotation_from_click("text", 4, 5, st, text="hi")
    assert t.kind == "text" and t.text == "hi"
    assert tools.annotation_from_click("step", 4, 5, st, number=7).number == 7
    assert tools.annotation_from_click("box", 0, 0, st) is None


def test_handles_hit_and_changes():
    box = Annotation("box", 10, 10, 110, 60)
    h = tools.handles_for(box)
    assert set(h) == {"nw", "n", "ne", "e", "se", "s", "sw", "w"} and h["se"] == (110, 60)
    assert tools.handle_at(box, 111, 59, 3) == "se" and tools.handle_at(box, 60, 35, 3) is None
    assert tools.handle_changes(box, "se", 150, 100) == {"x1": 10, "y1": 10, "x2": 150, "y2": 100}
    assert tools.handle_changes(box, "n", 0, 20)["y1"] == 20
    sq = tools.handle_changes(box, "se", 150, 100, ctrl=True)
    assert sq["x2"] - sq["x1"] == sq["y2"] - sq["y1"] == 140
    arrow = Annotation("arrow", 0, 0, 50, 50)
    assert tools.handles_for(arrow) == {"start": (0, 0), "end": (50, 50)}
    assert tools.handle_changes(arrow, "start", 5, 6) == {"x1": 5, "y1": 6}
    pen = Annotation("pen", points=[(1, 1), (2, 2)])
    assert tools.handles_for(pen) == {}
    mv = tools.move_changes(pen, 10, 20)
    assert mv["points"] == [(11, 21), (12, 22)]
    d = tools.duplicate(box)
    assert (d.x1, d.y1) == (22, 22) and d is not box
    assert tools.selection_rect(Annotation("step", 50, 50))[2] == 2 * max(10, 18 * 0.75)
