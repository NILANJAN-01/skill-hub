"""Shared helpers for skill-hub tooling (standard library only)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
CATALOG = ROOT / "catalog.json"
SKILLS_README = SKILLS_DIR / "README.md"

_FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


class FrontmatterError(ValueError):
    pass


def _scalar(raw: str, where: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise FrontmatterError(f"{where}: bad double-quoted string ({e})") from None
    if raw.startswith("'"):
        if not raw.endswith("'") or len(raw) < 2:
            raise FrontmatterError(f"{where}: unterminated single-quoted string")
        return raw[1:-1].replace("''", "'")
    if raw[0] in "|>[{&*!":
        raise FrontmatterError(f"{where}: block/flow YAML values are not supported; use a single-line string")
    if ": " in raw:
        raise FrontmatterError(f"{where}: unquoted value contains ': ' (invalid YAML); wrap it in double quotes")
    return raw


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse the simple YAML subset used by SKILL.md files.

    Supports `key: value` scalars (plain, "double" or 'single' quoted) and one level of
    nested maps (e.g. `metadata:` followed by indented `key: value` lines).
    Returns (frontmatter, body).
    """
    m = _FM.match(text)
    if not m:
        raise FrontmatterError("SKILL.md must start with a '---' YAML frontmatter block")
    data: dict = {}
    parent: str | None = None
    for n, line in enumerate(m.group(1).splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line[0] in " \t"
        km = re.match(r"\s*([A-Za-z0-9_-]+):(?:\s+(.*))?$", line)
        if not km:
            raise FrontmatterError(f"line {n}: expected 'key: value', got {line.strip()!r}")
        key, val = km.group(1), km.group(2) or ""
        val = re.sub(r"\s+#.*$", "", val) if not val.lstrip().startswith(("'", '"')) else val
        if indented:
            if parent is None:
                raise FrontmatterError(f"line {n}: unexpected indentation")
            data[parent][key] = _scalar(val, f"line {n}")
        elif val.strip() == "":
            parent = key
            data[key] = {}
        else:
            parent = None
            data[key] = _scalar(val, f"line {n}")
    return data, text[m.end():]


def load_marketplace() -> dict:
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith("."))


def plugin_skill_names(plugin: dict) -> list[str]:
    """Skill folder names referenced by a marketplace plugin entry."""
    return [Path(s).name for s in plugin.get("skills", [])]
