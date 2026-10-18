"""Text tags for Library images, kept beside the settings as ``tags.json`` ({absolute path: [tag, …]}).

Tags belong to files, so the Library keeps them in step: a rename moves them, a duplicate copies them, a trashed
file loses them (``forget``). Tags are trimmed, lower-cased for comparison and stored in the case first typed.
No GTK.
"""
from __future__ import annotations
import json
import os
import pathlib

from gi.repository import GLib

FILE = "tags.json"


def tags_path(root: str | None = None) -> pathlib.Path:
    """``~/.local/share/linscreencapture/tags.json``; under ``root`` (tests) when given."""
    base = pathlib.Path(root) if root else pathlib.Path(GLib.get_user_data_dir())
    return base / "linscreencapture" / FILE


def clean(tag: str) -> str:
    """One tag: no surrounding spaces or ``#``, inner whitespace collapsed."""
    return " ".join(tag.strip().lstrip("#").split())


class TagStore:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self._tags: dict[str, list[str]] = {}

    @classmethod
    def load(cls, root: str | None = None) -> "TagStore":
        store = cls(tags_path(root))
        try:
            data = json.loads(store.path.read_text())
            if isinstance(data, dict):
                store._tags = {str(k): [clean(t) for t in v if clean(t)] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError):
            pass
        return store

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: v for k, v in sorted(self._tags.items()) if v}, indent=1, ensure_ascii=False))
        os.replace(tmp, self.path)

    @staticmethod
    def _key(path: str) -> str:
        return os.path.abspath(path)

    # -- queries --------------------------------------------------------------
    def get(self, path: str) -> list[str]:
        return list(self._tags.get(self._key(path), []))

    def all_tags(self) -> list[str]:
        seen: dict[str, str] = {}
        for tags in self._tags.values():
            for t in tags:
                seen.setdefault(t.lower(), t)
        return sorted(seen.values(), key=str.lower)

    def matches(self, path: str, text: str) -> bool:
        """Does any tag of ``path`` contain ``text`` (case-insensitive)?"""
        needle = clean(text).lower()
        return bool(needle) and any(needle in t.lower() for t in self._tags.get(self._key(path), []))

    # -- edits (each saves) ---------------------------------------------------
    def add(self, paths, tag: str) -> bool:
        tag = clean(tag)
        if not tag:
            return False
        changed = False
        for p in paths:
            tags = self._tags.setdefault(self._key(p), [])
            if tag.lower() not in (t.lower() for t in tags):
                tags.append(tag)
                changed = True
        if changed:
            self.save()
        return changed

    def remove(self, paths, tag: str) -> bool:
        low = clean(tag).lower()
        changed = False
        for p in paths:
            tags = self._tags.get(self._key(p), [])
            keep = [t for t in tags if t.lower() != low]
            if len(keep) != len(tags):
                self._tags[self._key(p)] = keep
                changed = True
        if changed:
            self.save()
        return changed

    def rename(self, old: str, new: str) -> None:
        tags = self._tags.pop(self._key(old), None)
        if tags:
            self._tags[self._key(new)] = tags
            self.save()

    def copy(self, src: str, dst: str) -> None:
        tags = self._tags.get(self._key(src))
        if tags:
            self._tags[self._key(dst)] = list(tags)
            self.save()

    def forget(self, path: str) -> None:
        if self._tags.pop(self._key(path), None) is not None:
            self.save()
