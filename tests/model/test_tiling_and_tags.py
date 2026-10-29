"""Library → Combine layout and the tag store (headless)."""
from linscreencapture.app.tiling import GAP, MARGIN, columns_for, tile
from linscreencapture.services.tags import TagStore, clean


def _overlaps(a, b):
    (ax, ay, aw, ah), (bx, by, bw, bh) = a, b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _rects(sizes):
    w, h, places = tile(sizes)
    return w, h, [(x, y, sw, sh) for (x, y), (sw, sh) in zip(places, sizes)]


def test_two_images_sit_side_by_side_ten_px_apart():
    w, h, rects = _rects([(400, 300), (200, 300)])
    (ax, ay, aw, ah), (bx, by, _bw, _bh) = rects
    assert (ax, ay) == (MARGIN, MARGIN) and bx == ax + aw + GAP and by == ay
    assert (w, h) == (MARGIN * 2 + 400 + GAP + 200, MARGIN * 2 + 300)


def test_two_portraits_still_go_side_by_side():
    assert columns_for([(100, 900), (100, 900)]) == 2


def test_four_equal_images_make_a_two_by_two_grid():
    w, h, rects = _rects([(400, 300)] * 4)
    assert columns_for([(400, 300)] * 4) == 2
    assert (w, h) == (2 * MARGIN + 800 + GAP, 2 * MARGIN + 600 + GAP)
    assert rects[3][:2] == (MARGIN + 400 + GAP, MARGIN + 300 + GAP)


def test_three_landscape_shots_form_a_row_and_nine_a_square_grid():
    assert columns_for([(400, 300)] * 3) == 3
    assert columns_for([(400, 300)] * 9) == 3


def test_tiles_never_overlap_and_keep_gap_and_margin():
    sizes = [(640, 400), (300, 500), (800, 200), (120, 120), (500, 500), (333, 222), (90, 600)]
    w, h, rects = _rects(sizes)
    for i, a in enumerate(rects):
        x, y, rw, rh = a
        assert x >= MARGIN and y >= MARGIN and x + rw <= w - MARGIN and y + rh <= h - MARGIN
        for b in rects[i + 1:]:
            grown = (b[0] - GAP + 1, b[1] - GAP + 1, b[2] + 2 * GAP - 2, b[3] + 2 * GAP - 2)
            assert not _overlaps(a, grown), (a, b)        # at least GAP px between any two images


def test_smaller_images_are_centred_in_their_cell():
    _w, _h, rects = _rects([(400, 300), (200, 100)])
    assert rects[1][1] == MARGIN + (300 - 100) // 2


def test_one_and_none():
    assert tile([(50, 40)]) == (50 + 2 * MARGIN, 40 + 2 * MARGIN, [(MARGIN, MARGIN)])
    assert tile([]) == (2 * MARGIN, 2 * MARGIN, [])


# ---------------------------------------------------------------- tags
def test_tags_add_remove_query_and_persist(tmp_path):
    a, b = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    s = TagStore.load(str(tmp_path))
    assert s.add([a, b], " #Bug report ") and not s.add([a], "bug REPORT")     # trimmed; case-insensitive duplicate
    s.add([a], "ui")
    assert s.get(a) == ["Bug report", "ui"] and s.get(b) == ["Bug report"]
    assert s.matches(a, "repo") and not s.matches(b, "ui") and not s.matches(a, " ")
    assert s.all_tags() == ["Bug report", "ui"]
    s.remove([a, b], "bug report")
    again = TagStore.load(str(tmp_path))
    assert again.get(a) == ["ui"] and again.get(b) == []


def test_tags_follow_rename_copy_and_forget(tmp_path):
    a, b, c = (str(tmp_path / n) for n in ("a.png", "b.png", "c.png"))
    s = TagStore.load(str(tmp_path))
    s.add([a], "x")
    s.rename(a, b)
    assert s.get(a) == [] and s.get(b) == ["x"]
    s.copy(b, c)
    assert s.get(c) == ["x"]
    s.forget(b)
    assert TagStore.load(str(tmp_path)).get(b) == [] and TagStore.load(str(tmp_path)).get(c) == ["x"]


def test_a_broken_tags_file_starts_empty(tmp_path):
    p = tmp_path / "linscreencapture" / "tags.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert TagStore.load(str(tmp_path)).all_tags() == []
    assert clean("  #a   b ") == "a b"
