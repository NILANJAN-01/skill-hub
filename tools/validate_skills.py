#!/usr/bin/env python3
"""Validate every skill in skills/ against the Agent Skills spec and the hub conventions.

    python tools/validate_skills.py            # report errors and warnings
    python tools/validate_skills.py --strict   # treat warnings as errors

Exit code 1 if any error is found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from hublib import (EXAMPLES, MARKETPLACE, MIN_EXAMPLES, ROOT, FrontmatterError, load_examples,
                    load_marketplace, parse_frontmatter, plugin_skill_names, skill_dirs)

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KNOWN_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MAX_LINES = 500
# Skills must work in every agent. Agent-specific wording needs a `compatibility` note.
AGENT_SPECIFIC = re.compile(
    r"\bClaude Code\b|\bClaude\.ai\b|~/\.claude\b|\.claude/skills|/plugin install|\bCLAUDE\.md\b|"
    r"\bAntigravity\b|\bGitHub Copilot\b|\bCursor IDE\b|\bWindsurf\b|\bDevin\b|\bCodex CLI\b|\bGemini CLI\b|"
    r"\bSkill tool\b|\bTodoWrite\b|\bAskUserQuestion\b")


def check_skill(d: Path, plugin_names: set[str], listed: set[str]) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    md = d / "SKILL.md"
    if not md.is_file():
        return [f"missing SKILL.md"], warns
    text = md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except FrontmatterError as e:
        return [f"frontmatter: {e}"], warns

    name = fm.get("name", "")
    if not name:
        errors.append("frontmatter: 'name' is required")
    else:
        if not NAME_RE.match(name):
            errors.append(f"name {name!r} must be lowercase letters, digits and single hyphens")
        if len(name) > 64:
            errors.append(f"name is longer than 64 characters ({len(name)})")
        if name != d.name:
            errors.append(f"name {name!r} does not match folder {d.name!r}")

    desc = fm.get("description", "")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("frontmatter: 'description' is required")
    elif len(desc) > 1024:
        errors.append(f"description is longer than 1024 characters ({len(desc)})")
    elif "use when" not in desc.lower() and "use this" not in desc.lower():
        warns.append("description should say when to use the skill (e.g. 'Use when ...')")

    if "compatibility" in fm and len(str(fm["compatibility"])) > 500:
        errors.append("compatibility is longer than 500 characters")
    meta = fm.get("metadata", {})
    if "metadata" in fm and not isinstance(meta, dict):
        errors.append("metadata must be a map of key: value pairs")
        meta = {}
    for k in sorted(set(fm) - KNOWN_FIELDS):
        warns.append(f"unknown frontmatter field {k!r} (put custom fields under metadata:)")

    if not meta.get("title"):
        warns.append("metadata.title is missing (used as the display title)")
    cat = meta.get("category")
    if cat and cat not in plugin_names:
        errors.append(f"metadata.category {cat!r} is not a plugin in marketplace.json")
    if meta.get("source") and not fm.get("license"):
        errors.append("skills derived from a source document must declare a license")
    if d.name not in listed:
        errors.append("not listed in any plugin in .claude-plugin/marketplace.json")

    if not fm.get("compatibility"):
        hits = sorted(set(AGENT_SPECIFIC.findall(body)))
        if hits:
            warns.append(f"agent-specific wording ({', '.join(hits)}); make the body agent-neutral or "
                         "declare it in a 'compatibility' field")

    n_lines = text.count("\n") + 1
    if n_lines > MAX_LINES:
        warns.append(f"SKILL.md has {n_lines} lines (> {MAX_LINES}); move detail into references/")

    in_code = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for target in LINK_RE.findall(line):
            if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|/)", target, re.I):
                continue
            path = target.split("#", 1)[0]
            if path and not (d / path).exists():
                errors.append(f"broken relative link: {target}")
    return errors, warns


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    n_err = n_warn = 0

    def report(level: str, where: str, msg: str) -> None:
        nonlocal n_err, n_warn
        print(f"{level:<5} {where}: {msg}")
        if level == "ERROR":
            n_err += 1
        else:
            n_warn += 1

    market = load_marketplace()
    plugins = market.get("plugins", [])
    plugin_names = {p.get("name", "") for p in plugins}
    mk = MARKETPLACE.relative_to(ROOT).as_posix()
    if not market.get("name") or not NAME_RE.match(market["name"]):
        report("ERROR", mk, "marketplace 'name' must be kebab-case")
    if not market.get("owner", {}).get("name"):
        report("ERROR", mk, "marketplace 'owner.name' is required")
    seen = set()
    listed: set[str] = set()
    for p in plugins:
        pn = p.get("name", "")
        if not NAME_RE.match(pn):
            report("ERROR", mk, f"plugin name {pn!r} must be kebab-case")
        if pn in seen:
            report("ERROR", mk, f"duplicate plugin name {pn!r}")
        seen.add(pn)
        if not p.get("description"):
            report("WARN", mk, f"plugin {pn!r} has no description")
        for s in p.get("skills", []):
            if not (ROOT / s / "SKILL.md").is_file():
                report("ERROR", mk, f"plugin {pn!r}: marketplace lists missing skill {s}")
        listed.update(plugin_skill_names(p))

    dirs = skill_dirs()
    ex_where = EXAMPLES.relative_to(ROOT).as_posix()
    try:
        examples = load_examples()
    except ValueError as e:
        report("ERROR", ex_where, f"invalid JSON: {e}")
        examples = {}
    for k in sorted(set(examples) - {d.name for d in dirs}):
        report("ERROR", ex_where, f"prompts for unknown skill {k!r}")
    for d in dirs:
        prompts = examples.get(d.name, [])
        if not isinstance(prompts, list) or not all(isinstance(p, str) and p.strip() for p in prompts):
            report("ERROR", ex_where, f"{d.name}: prompts must be a list of non-empty strings")
        elif len(prompts) < MIN_EXAMPLES:
            report("ERROR", ex_where, f"{d.name}: needs at least {MIN_EXAMPLES} example prompts (has {len(prompts)})")
    for d in dirs:
        errors, warns = check_skill(d, plugin_names, listed)
        where = d.relative_to(ROOT).as_posix()
        for e in errors:
            report("ERROR", where, e)
        for w in warns:
            report("WARN", where, w)

    print(f"\n{len(dirs)} skills, {len(plugins)} plugins: {n_err} error(s), {n_warn} warning(s)")
    sys.exit(1 if n_err or (args.strict and n_warn) else 0)


if __name__ == "__main__":
    main()
