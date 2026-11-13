#!/usr/bin/env python3
"""Create a new document from a bundled template.

    python new_doc.py --list
    python new_doc.py blog my-post.md [--title "Title"] [--force]

Templates live in ../assets/ (blog-post.md, cv.md, technical-doc.md, readme.md, cover-letter.md).
Never overwrites an existing file unless --force is given. Standard library only (Python 3.8+).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TEMPLATES = {
    "blog": "blog-post.md",
    "cv": "cv.md",
    "doc": "technical-doc.md",
    "readme": "readme.md",
    "cover-letter": "cover-letter.md",
}


def create(kind: str, out: Path, title: str | None = None, force: bool = False) -> Path:
    if kind not in TEMPLATES:
        raise SystemExit(f"Unknown template {kind!r}. Choose from: {', '.join(TEMPLATES)}")
    src = ASSETS / TEMPLATES[kind]
    if not src.is_file():
        raise SystemExit(f"Template file missing: {src}")
    if out.exists() and not force:
        raise SystemExit(f"{out} already exists. Choose another name or pass --force to replace it.")
    text = src.read_text(encoding="utf-8")
    if title:
        text = text.replace("{{TITLE}}", title)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", nargs="?", help="template: " + ", ".join(TEMPLATES))
    ap.add_argument("output", nargs="?", type=Path, help="file to create")
    ap.add_argument("--title", help="replaces {{TITLE}} in the template")
    ap.add_argument("--force", action="store_true", help="replace an existing file")
    ap.add_argument("--list", action="store_true", help="list templates")
    args = ap.parse_args()
    if args.list or not (args.kind and args.output):
        for k, v in TEMPLATES.items():
            print(f"  {k:<13} {v}")
        if not args.list:
            sys.exit("usage: new_doc.py KIND OUTPUT [--title T]")
        return
    print(f"created {create(args.kind, args.output, args.title, args.force)}")


if __name__ == "__main__":
    main()
