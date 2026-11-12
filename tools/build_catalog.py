#!/usr/bin/env python3
"""Build catalog.json and skills/README.md from every skills/*/SKILL.md and the plugin marketplace.

Also builds prompts.html and examples/PROMPTS.md (example prompts per skill) from examples/prompts.json,
and the agent tables in README.md and GUIDE.md from tools/install.py.

    python tools/build_catalog.py           # (re)write the files
    python tools/build_catalog.py --check   # exit 1 if they are out of date (used by CI)
"""

from __future__ import annotations

import argparse
import json
import sys

import re

from hublib import (CATALOG, PROMPTS_HTML, PROMPTS_TEMPLATE, ROOT, SKILLS_README, FrontmatterError,
                    load_examples, load_marketplace, parse_frontmatter, plugin_skill_names, skill_dirs)
from install import AGENTS

README = ROOT / "README.md"
GUIDE = ROOT / "GUIDE.md"
PROMPTS_MD = ROOT / "examples" / "PROMPTS.md"


def prompts_markdown(skills: list, categories: list) -> str:
    """examples/PROMPTS.md: every skill's example prompts, readable on GitHub."""
    total = sum(len(s["examples"]) for s in skills)
    out = ["# Example prompts", "",
           "<!-- Generated from examples/prompts.json by tools/build_catalog.py - do not edit by hand. -->", "",
           f"{total} things you can say to your AI coding agent, for all {len(skills)} skills. Install a skill "
           "([guide](../GUIDE.md)), then just ask: the agent loads the skill when your request matches its "
           "description. To force a skill, start with *\"Use the &lt;skill-name&gt; skill: …\"*.", "",
           "**Categories:** " + " · ".join(
               f"[{c['title']}](#{re.sub(r'[^a-z0-9 -]', '', c['title'].lower()).replace(' ', '-')})"
               for c in categories), ""]
    for c in categories:
        out += [f"## {c['title']}", "",
                f"Install the whole category: `--plugin {c['name']}`", ""]
        for s in sorted((s for s in skills if s["category"] == c["name"]), key=lambda s: s["title"].lower()):
            out += [f"### {s['title']}", "",
                    f"[`{s['name']}`](../skills/{s['name']}/SKILL.md) · install: `--skill {s['name']}`", ""]
            out += [f"- “{p}”" for p in s["examples"]] + [""]
    return "\n".join(out)


def agents_table() -> str:
    """Markdown matrix of supported agents, from install.AGENTS."""
    rows = ["| Agent | `--agent` | Project folder | User folder | Also reads |", "|---|---|---|---|---|"]
    for k, a in AGENTS.items():
        also = ", ".join(f"`{p}`" for p in a["also_reads"]) or "-"
        user = f"`{a['global']}`" if a["global"] else "-"
        rows.append(f"| [{a['name']}]({a['docs']}) | `{k}` | `{a['project']}` | {user} | {also} |")
    return "\n".join(rows)


def agents_table_simple() -> str:
    """Short 'where to copy' table for GUIDE.md (agents with their own entry; no 'universal')."""
    rows = ["| Agent | This project | Just me |", "|---|---|---|"]
    for k, a in AGENTS.items():
        if k == "universal":
            continue
        user = f"`{a['global']}/`" if a["global"] else "-"
        rows.append(f"| {a['name']} | `{a['project']}/` | {user} |")
    return "\n".join(rows)


def fill_block(text: str, name: str, table: str, where: str) -> str:
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        sys.exit(f"{where} is missing the {start} ... {end} markers")
    block = f"{start}\n<!-- Generated from tools/install.py AGENTS by tools/build_catalog.py -->\n{table}\n{end}"
    return pat.sub(lambda _: block, text)


def readme_with_agents(text: str) -> str:
    return fill_block(text, "agents", agents_table(), "README.md")

REPOSITORY = "https://github.com/NILANJAN-01/skill-hub"

# Display titles for categories (= focused plugin names), in website order.
CATEGORY_TITLES = {
    "hub-tools": "Hub tools",
    "android-automation": "Android: UI tests & logcat",
    "image-tools": "Images: pixels & description",
    "video-tools": "Video: frames, pixels & description",
    "testing-tools": "Testing: unit tests & reports",
    "git-getting-started": "Git: getting started",
    "git-branching": "Git: branching & merging",
    "git-collaboration": "Git: remotes & collaboration",
    "git-power-tools": "Git: power tools",
    "git-customization": "Git: customization & hooks",
    "git-internals": "Git: internals",
    "git-integrations": "Git: other systems & APIs",
    "git-reference": "Git: full reference",
}


def titleize(name: str) -> str:
    return name.replace("-", " ").capitalize()


def build() -> tuple[str, str, str, str]:
    market = load_marketplace()
    examples = load_examples()
    plugins = market.get("plugins", [])
    membership: dict[str, list[str]] = {}
    for p in plugins:
        for s in plugin_skill_names(p):
            membership.setdefault(s, []).append(p["name"])
    sizes = {p["name"]: len(p.get("skills", [])) for p in plugins}

    skills = []
    for d in skill_dirs():
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        try:
            fm, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
        except FrontmatterError as e:
            sys.exit(f"{md.relative_to(ROOT)}: {e}  (run tools/validate_skills.py)")
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        in_plugins = sorted(membership.get(d.name, []), key=lambda n: (sizes[n], n))
        category = meta.get("category") or (in_plugins[0] if in_plugins else "uncategorized")
        entry = {
            "name": fm.get("name", d.name),
            "title": meta.get("title") or titleize(d.name),
            "category": category,
            "description": fm.get("description", ""),
            "plugins": in_plugins,
            "path": f"skills/{d.name}",
            "license": fm.get("license", ""),
        }
        for k in ("source", "pages"):
            if meta.get(k):
                entry[k] = meta[k]
        entry["examples"] = examples.get(d.name, [])
        entry["files"] = sorted(p.relative_to(d).as_posix() for p in d.rglob("*.md") if p.name != "SKILL.md")
        skills.append(entry)

    counts: dict[str, int] = {}
    for s in skills:
        counts[s["category"]] = counts.get(s["category"], 0) + 1
    order = list(CATEGORY_TITLES) + sorted(c for c in counts if c not in CATEGORY_TITLES)
    categories = [{"name": c, "title": CATEGORY_TITLES.get(c, titleize(c)), "count": counts[c]}
                  for c in order if c in counts]

    catalog = {
        "name": market.get("name", "skill-hub"),
        "description": market.get("metadata", {}).get("description", ""),
        "repository": REPOSITORY,
        "plugins": [{"name": p["name"], "description": p.get("description", ""),
                     "category": p.get("category", ""), "skills": plugin_skill_names(p)} for p in plugins],
        "categories": categories,
        "agents": [{"id": k, **a} for k, a in AGENTS.items()],
        "skills": skills,
    }
    catalog_text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"

    def cell(s: str, limit: int = 160) -> str:
        s = " ".join(s.split()).replace("|", "\\|")
        return s if len(s) <= limit else s[: limit - 3].rsplit(" ", 1)[0] + "..."

    lines = ["# Skills", "",
             "<!-- Generated by tools/build_catalog.py - do not edit by hand. -->", "",
             f"{len(skills)} skills in {len(categories)} categories. Every skill is a standard Agent Skill and works in "
             "Claude Code, Google Antigravity, Devin, GitHub Copilot, Cursor, Windsurf, Codex and Gemini CLI. Install a "
             "category with `python tools/install.py --agent <agent> --plugin <category>`; see the "
             "[main README](../README.md#install) for every option.",
             ""]
    for c in categories:
        lines += [f"## {c['title']} (`{c['name']}`)", "", "| Skill | Description |", "|---|---|"]
        for s in sorted((s for s in skills if s["category"] == c["name"]), key=lambda s: s["title"].lower()):
            lines.append(f"| [`{s['name']}`]({s['name']}/SKILL.md) | {cell(s['description'])} |")
        lines.append("")
    page_data = {
        "categories": categories,
        "skills": [{"name": s["name"], "title": s["title"], "category": s["category"],
                    "plugin": s["plugins"][0] if s["plugins"] else "", "examples": s["examples"]}
                   for s in sorted(skills, key=lambda s: s["title"].lower()) if s["examples"]],
    }
    data_js = json.dumps(page_data, ensure_ascii=False).replace("</", "<\\/")
    template = PROMPTS_TEMPLATE.read_text(encoding="utf-8")
    if "/*__DATA__*/null" not in template:
        sys.exit("tools/prompts_template.html lost its /*__DATA__*/null placeholder")
    prompts_html = template.replace("/*__DATA__*/null", data_js)
    return catalog_text, "\n".join(lines), prompts_html, prompts_markdown(skills, categories)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = ap.parse_args()
    catalog_text, readme_text, prompts_html, prompts_md = build()
    targets = [(CATALOG, catalog_text), (SKILLS_README, readme_text), (PROMPTS_HTML, prompts_html),
               (PROMPTS_MD, prompts_md),
               (README, readme_with_agents(README.read_text(encoding="utf-8"))),
               (GUIDE, fill_block(GUIDE.read_text(encoding="utf-8"), "agents-simple", agents_table_simple(), "GUIDE.md"))]
    if args.check:
        stale = [p for p, t in targets if not p.exists() or p.read_text(encoding="utf-8") != t]
        for p in stale:
            print(f"ERROR {p.relative_to(ROOT)} is out of date: run python tools/build_catalog.py")
        sys.exit(1 if stale else 0)
    for p, t in targets:
        p.write_text(t, encoding="utf-8", newline="\n")
        print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
