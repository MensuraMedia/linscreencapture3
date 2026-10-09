import hashlib
import random
import cairo

from linscreencapture.model.annotations import Annotation, Style
from linscreencapture.model.document import Document, surface_from_pil, copy_surface
from linscreencapture.model.undo import UndoStack, AddLayer, RemoveLayer, MoveLayer, EditAnnotation, SetVisible, ReplaceBase
from tests.model.test_document import gradient, digest


def snapshot(doc: Document):
    return digest(doc.flatten()), [l.id for l in doc.layers], [l.visible for l in doc.layers]


def random_command(rng: random.Random, doc: Document):
    kinds = ["add"]
    if doc.layers:
        kinds += ["remove", "move", "edit", "visible"]
    kinds.append("base")
    k = rng.choice(kinds)
    if k == "add":
        kind = rng.choice(["box", "arrow", "step", "line", "fill"])
        return AddLayer(Annotation(kind, rng.randint(0, 40), rng.randint(0, 30), rng.randint(10, 60), rng.randint(10, 45),
                                   style=Style(colour=rng.choice(["#e5484d", "#46a758", "#0091ff"]), width=rng.randint(1, 6))))
    if k == "base":
        new = copy_surface(doc.base)
        cr = cairo.Context(new); cr.set_source_rgba(rng.random(), rng.random(), rng.random(), 0.5); cr.paint()
        return ReplaceBase(new, layers_after=None if rng.random() < 0.5 else [])
    layer = rng.choice(doc.layers)
    if k == "remove":
        return RemoveLayer(layer)
    if k == "move":
        return MoveLayer(layer, rng.randint(0, len(doc.layers) - 1))
    if k == "edit":
        return EditAnnotation(layer, {"x1": rng.randint(0, 30), "style": Style(colour="#ffffff", width=2)})
    return SetVisible(layer, not layer.visible)


def test_random_sequences_undo_to_the_start():
    for seed in range(6):
        rng = random.Random(seed)
        doc = Document(surface_from_pil(gradient()))
        stack = UndoStack(doc, limit=50)
        states = [snapshot(doc)]
        for _ in range(12):
            stack.do(random_command(rng, doc))
            states.append(snapshot(doc))
        for expected in reversed(states[:-1]):
            stack.undo()
            assert snapshot(doc) == expected
        assert not stack.can_undo
        for expected in states[1:]:
            stack.redo()
            assert snapshot(doc) == expected


def test_limit_and_redo_clearing():
    doc = Document(surface_from_pil(gradient()))
    stack = UndoStack(doc, limit=20)
    for i in range(25):
        stack.do(AddLayer(Annotation("box", 0, 0, 10, 10)))
    assert stack.depth == 20 and len(doc.layers) == 25
    for _ in range(30):
        stack.undo()
    assert len(doc.layers) == 5 and not stack.can_undo      # the five oldest are beyond the limit
    stack.redo(); assert len(doc.layers) == 6 and stack.can_redo
    stack.do(AddLayer(Annotation("line", 0, 0, 10, 10)))
    assert not stack.can_redo and stack.undo_label == "Add layer"


def test_on_change_fires():
    doc = Document(surface_from_pil(gradient()))
    calls = []
    stack = UndoStack(doc, on_change=lambda: calls.append(1))
    stack.do(AddLayer(Annotation("box")))
    stack.undo(); stack.redo(); stack.clear()
    assert len(calls) == 4
