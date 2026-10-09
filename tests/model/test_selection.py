from linscreencapture.services.selection import Selection, square_end, HANDLES


def test_rect_normalises_and_handles():
    s = Selection(100, 80, 20, 30)
    assert s.rect == (20, 30, 80, 50)
    n = s.normalised()
    assert (n.x1, n.y1, n.x2, n.y2) == (20, 30, 100, 80)
    hp = n.handle_positions()
    assert set(hp) == set(HANDLES) and hp["nw"] == (20, 30) and hp["se"] == (100, 80) and hp["e"] == (100, 55)


def test_hit_testing():
    s = Selection(20, 30, 100, 80)
    assert s.hit(20, 30) == "nw" and s.hit(102, 55) == "e" and s.hit(60, 50) == "inside"
    assert s.hit(5, 5) is None and s.hit(60, 95) is None
    assert s.cursor_for("se") == "se-resize" and s.cursor_for(None) == "crosshair"


def test_resize_keeps_opposite_edge():
    s = Selection(20, 30, 100, 80)
    r = s.resized("se", 140, 120)
    assert r.rect == (20, 30, 120, 90)
    r = s.resized("n", 0, 10)
    assert r.rect == (20, 10, 80, 70)
    r = s.resized("nw", 90, 70, square=True)   # anchor is the se corner (100, 80)
    assert r.rect == (90, 70, 10, 10)
    r = s.resized("se", 160, 100, square=True)  # side = max(140, 70): the dominant axis wins, nw corner fixed
    assert r.rect == (20, 30, 140, 140)


def test_move_clamp_and_square_end():
    s = Selection(20, 30, 100, 80).moved(-50, 0)
    assert s.rect == (-30, 30, 80, 50)
    c = s.clamped(0, 0, 200, 100)
    assert c.rect == (0, 30, 80, 50)
    assert Selection(0, 0, 500, 50).clamped(0, 0, 200, 100).rect == (0, 0, 200, 50)
    assert square_end(10, 10, 40, 20) == (40, 40) and square_end(10, 10, -5, 30) == (-10, 30)
    assert Selection(1, 1, 2, 2).is_empty and not Selection(0, 0, 5, 5).is_empty
