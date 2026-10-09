"""A bounded undo/redo stack of reversible document commands. No GTK."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Protocol

import cairo

from .annotations import Annotation, Style
from .document import Document, Layer, copy_surface

LIMIT = 20


class Command(Protocol):
    label: str

    def apply(self, doc: Document) -> None: ...
    def revert(self, doc: Document) -> None: ...


@dataclass
class AddLayer:
    annotation: Annotation
    index: int | None = None
    label: str = "Add layer"
    _layer: Layer | None = None

    def apply(self, doc: Document) -> None:
        if self._layer is None:
            self._layer = doc.add_layer(self.annotation, self.index)
        else:  # redo: reinsert the same layer object so ids and selection survive
            doc.layers.insert(self.index if self.index is not None else len(doc.layers), self._layer)
            doc.dirty = True

    def revert(self, doc: Document) -> None:
        self.index = doc.remove_layer(self._layer)

    @property
    def layer(self) -> Layer | None:
        return self._layer


@dataclass
class RemoveLayer:
    layer: Layer
    label: str = "Delete layer"
    _index: int = 0

    def apply(self, doc: Document) -> None:
        self._index = doc.remove_layer(self.layer)

    def revert(self, doc: Document) -> None:
        doc.layers.insert(self._index, self.layer)
        doc.dirty = True


@dataclass
class MoveLayer:
    layer: Layer
    index: int
    label: str = "Reorder layer"
    _old: int = 0

    def apply(self, doc: Document) -> None:
        self._old = doc.layers.index(self.layer)
        doc.move_layer(self.layer, self.index)

    def revert(self, doc: Document) -> None:
        doc.move_layer(self.layer, self._old)


@dataclass
class EditAnnotation:
    """Replace an annotation's fields; ``changes`` are dataclass field values (style may be a Style)."""
    layer: Layer
    changes: dict
    label: str = "Edit"
    _before: dict | None = None

    def apply(self, doc: Document) -> None:
        a = self.layer.annotation
        self._before = {k: getattr(a, k) for k in self.changes}
        for k, v in self.changes.items():
            setattr(a, k, v)
        doc.dirty = True

    def revert(self, doc: Document) -> None:
        for k, v in (self._before or {}).items():
            setattr(self.layer.annotation, k, v)
        doc.dirty = True


@dataclass
class SetVisible:
    layer: Layer
    visible: bool
    label: str = "Toggle visibility"

    def apply(self, doc: Document) -> None:
        self.layer.visible = self.visible

    def revert(self, doc: Document) -> None:
        self.layer.visible = not self.visible


@dataclass
class ReplaceBase:
    """An image operation (crop, resize, rotate, brightness, flatten): swap the base surface."""
    new_base: cairo.ImageSurface
    label: str = "Image operation"
    layers_after: list[Layer] | None = None   # flatten clears layers; None keeps them
    _old_base: cairo.ImageSurface | None = None
    _old_layers: list[Layer] | None = None

    def apply(self, doc: Document) -> None:
        self._old_base = doc.base
        self._old_layers = list(doc.layers)
        doc.base = self.new_base
        if self.layers_after is not None:
            doc.layers = list(self.layers_after)
        doc.dirty = True

    def revert(self, doc: Document) -> None:
        doc.base = self._old_base
        doc.layers = list(self._old_layers or [])
        doc.dirty = True


class UndoStack:
    def __init__(self, doc: Document, limit: int = LIMIT, on_change: Callable[[], None] | None = None):
        self.doc = doc
        self.limit = limit
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self.on_change = on_change

    def do(self, cmd: Command) -> Command:
        cmd.apply(self.doc)
        self._undo.append(cmd)
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()
        self._notify()
        return cmd

    def undo(self) -> Command | None:
        if not self._undo:
            return None
        cmd = self._undo.pop()
        cmd.revert(self.doc)
        self._redo.append(cmd)
        self._notify()
        return cmd

    def redo(self) -> Command | None:
        if not self._redo:
            return None
        cmd = self._redo.pop()
        cmd.apply(self.doc)
        self._undo.append(cmd)
        self._notify()
        return cmd

    def clear(self) -> None:
        self._undo.clear(); self._redo.clear(); self._notify()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def depth(self) -> int:
        return len(self._undo)

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()
