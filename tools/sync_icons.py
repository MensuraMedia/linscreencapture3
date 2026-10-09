#!/usr/bin/env python3
"""Copy the Phosphor icons the app names into data/icons as GTK symbolic SVGs
and regenerate the GResource manifest.

    python3 tools/sync_icons.py --source ~/projects/assets/icons/regular
"""
from __future__ import annotations
import argparse, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "icons" / "icons.txt"
OUT = ROOT / "data" / "icons" / "scalable" / "actions"
XML = ROOT / "data" / "linscreencapture.gresource.xml"
PREFIX = "/com/mensuramedia/linscreencapture"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(pathlib.Path.home() / "projects/assets/icons/regular"))
    ap.add_argument("--weight", default="", help="optional second weight folder name, e.g. fill")
    args = ap.parse_args()
    src = pathlib.Path(args.source).expanduser()
    if not src.is_dir():
        print(f"icon source not found: {src}", file=sys.stderr)
        return 2
    names = [n.strip() for n in LIST.read_text().splitlines() if n.strip() and not n.startswith("#")]
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [n for n in names if not (src / f"{n}.svg").is_file()]
    if missing:
        print("missing icons: " + ", ".join(missing), file=sys.stderr)
        return 1
    files = []
    for n in names:
        dest = OUT / f"lsc-{n}-symbolic.svg"
        shutil.copyfile(src / f"{n}.svg", dest)
        files.append(dest.relative_to(ROOT / "data").as_posix())
    for lic in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        cand = src.parent / lic
        if cand.is_file():
            shutil.copyfile(cand, ROOT / "data" / "icons" / "LICENSE.phosphor")
            break
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<gresources>", f'  <gresource prefix="{PREFIX}">',
             '    <file compressed="true">style.css</file>']
    lines += [f"    <file>{f}</file>" for f in files]
    lines += ["  </gresource>", "</gresources>", ""]
    XML.write_text("\n".join(lines))
    print(f"synced {len(files)} icons -> {OUT.relative_to(ROOT)}; wrote {XML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
