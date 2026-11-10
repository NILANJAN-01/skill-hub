#!/usr/bin/env python3
"""Install skill-hub skills into any AI coding agent / IDE that reads Agent Skills (SKILL.md).

Works from a clone, or standalone (it downloads the hub from GitHub):

    curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py \
      | python3 - --agent cursor --plugin git-branching

Examples:
    python tools/install.py --list                                   # plugins, skills, agents
    python tools/install.py --agent antigravity --skill git-rebasing # into ./.agents/skills
    python tools/install.py --agent copilot,claude-code --plugin hub-tools
    python tools/install.py --agent claude-code --plugin git-skills --global   # user-wide
    python tools/install.py --agent universal --skill git-hooks --project ~/code/app
    python tools/install.py --zip dist --plugin git-branching        # .zip per skill (Claude.ai upload)

Standard library only (Python 3.8+). Existing skill folders are left alone unless --force.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "NILANJAN-01/skill-hub"

# --------------------------------------------------------------------------------------------
# Where each agent reads skills. SOURCE OF TRUTH: build_catalog.py copies this table into
# catalog.json (website, find-skills skill) and into the README agent matrix.
# "project" is relative to the project root; "global" is under the user's home (None = no
# on-disk user folder). "also_reads" lists other project folders the agent scans, so one
# install can serve several agents.
# --------------------------------------------------------------------------------------------
AGENTS = {
    "claude-code": {
        "name": "Claude Code", "project": ".claude/skills", "global": "~/.claude/skills",
        "also_reads": [],
        "native": "/plugin marketplace add NILANJAN-01/skill-hub",
        "docs": "https://code.claude.com/docs/en/skills",
    },
    "antigravity": {
        "name": "Google Antigravity", "project": ".agents/skills", "global": "~/.gemini/config/skills",
        "also_reads": [".agent/skills"],
        "docs": "https://antigravity.google/docs/skills",
    },
    "devin": {
        "name": "Devin", "project": ".agents/skills", "global": "~/.config/devin/skills",
        "also_reads": [".devin/skills", ".github/skills", ".claude/skills", ".cursor/skills",
                       ".windsurf/skills", ".codex/skills"],
        "note": "Cloud Devin reads skills committed to the repo; the global folder is for Devin Local / CLI.",
        "docs": "https://docs.devin.ai/product-guides/skills",
    },
    "copilot": {
        "name": "GitHub Copilot (VS Code)", "project": ".github/skills", "global": "~/.copilot/skills",
        "also_reads": [".agents/skills", ".claude/skills"],
        "docs": "https://code.visualstudio.com/docs/agent-customization/agent-skills",
    },
    "cursor": {
        "name": "Cursor", "project": ".cursor/skills", "global": "~/.cursor/skills",
        "also_reads": [".claude/skills", ".codex/skills"],
        "docs": "https://cursor.com/docs/skills",
    },
    "windsurf": {
        "name": "Windsurf (Devin Local)", "project": ".devin/skills", "global": "~/.config/devin/skills",
        "also_reads": [".windsurf/skills"],
        "note": "Windsurf Cascade is now Devin Local; .windsurf/skills is still read as a legacy path.",
        "docs": "https://docs.devin.ai/desktop/cascade/skills",
    },
    "codex": {
        "name": "OpenAI Codex", "project": ".agents/skills", "global": "~/.agents/skills",
        "also_reads": [],
        "docs": "https://learn.chatgpt.com/docs/build-skills",
    },
    "gemini-cli": {
        "name": "Gemini CLI", "project": ".gemini/skills", "global": "~/.gemini/skills",
        "also_reads": [".agents/skills"],
        "docs": "https://geminicli.com/docs/cli/skills/",
    },
    "universal": {
        "name": "Any Agent Skills tool (.agents)", "project": ".agents/skills", "global": "~/.agents/skills",
        "also_reads": [],
        "note": "The emerging shared location; read by Antigravity, Devin, Copilot, Codex and others.",
        "docs": "https://agentskills.io",
    },
}


# --------------------------------------------------------------------------------------------
def find_local_root() -> Path | None:
    """The hub checkout this script lives in, if any."""
    try:
        here = Path(__file__).resolve().parent.parent
    except NameError:                     # running from stdin (curl | python)
        return None
    return here if (here / "skills").is_dir() and (here / ".claude-plugin").is_dir() else None


def download_hub(ref: str) -> Path:
    url = f"https://codeload.github.com/{REPO}/zip/refs/heads/{ref}"
    print(f"Downloading {REPO}@{ref} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "skill-hub-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    tmp = Path(tempfile.mkdtemp(prefix="skill-hub-"))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for m in z.namelist():                 # refuse path traversal
            if m.startswith("/") or ".." in Path(m).parts:
                sys.exit(f"Refusing suspicious archive member: {m}")
        z.extractall(tmp)
    roots = [p for p in tmp.iterdir() if p.is_dir()]
    if len(roots) != 1 or not (roots[0] / "skills").is_dir():
        sys.exit("Downloaded archive does not look like skill-hub.")
    return roots[0]


def load_plugins(root: Path) -> dict[str, list[str]]:
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return {p["name"]: [Path(s).name for s in p.get("skills", [])] for p in market.get("plugins", [])}


def all_skills(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "skills").iterdir() if (p / "SKILL.md").is_file())


def resolve(root: Path, plugins_arg: list[str], skills_arg: list[str]) -> list[str]:
    plugins, known = load_plugins(root), set(all_skills(root))
    chosen: list[str] = []
    for p in plugins_arg:
        if p not in plugins:
            sys.exit(f"Unknown plugin {p!r}. Run with --list to see plugins.")
        chosen += plugins[p]
    for s in skills_arg:
        if s not in known:
            sys.exit(f"Unknown skill {s!r}. Run with --list to see skills.")
        chosen.append(s)
    return list(dict.fromkeys(chosen))          # de-duplicate, keep order


def target_dir(agent: str, use_global: bool, project: Path) -> Path:
    a = AGENTS[agent]
    if use_global:
        if not a["global"]:
            sys.exit(f"{a['name']} has no user-level skills folder. {a.get('note', '')} "
                     f"Install into the project instead (omit --global).")
        return Path(os.path.expanduser(a["global"]))
    return project / a["project"]


def plan_project_dirs(agents: list[str]) -> list[tuple[str, list[str]]]:
    """Fewest project folders that every selected agent reads (avoids duplicate skills in agents
    such as Copilot or Devin that scan several folders). Only the selected agents' own folders are
    candidates; ties go to the agent listed first. Returns [(folder, [agents served])]."""
    reads = {a: [AGENTS[a]["project"], *AGENTS[a]["also_reads"]] for a in agents}
    candidates = list(dict.fromkeys(AGENTS[a]["project"] for a in agents))
    uncovered, plan = list(agents), []
    while uncovered:
        best = max(candidates, key=lambda f: (sum(f in reads[a] for a in uncovered), -candidates.index(f)))
        served = [a for a in uncovered if best in reads[a]]
        plan.append((best, served))
        uncovered = [a for a in uncovered if a not in served]
    return plan


def install(root: Path, names: list[str], dest: Path, force: bool, dry: bool) -> tuple[int, int]:
    done = skipped = 0
    for n in names:
        src, dst = root / "skills" / n, dest / n
        if dst.exists() and not force:
            print(f"  skip  {dst}  (exists; use --force to replace)")
            skipped += 1
            continue
        print(f"  {'would install' if dry else 'install'}  {n}  ->  {dst}")
        if not dry:
            if dst.exists():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        done += 1
    return done, skipped


def make_zips(root: Path, names: list[str], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for n in names:
        zpath = out / f"{n}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted((root / "skills" / n).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, Path(n) / f.relative_to(root / "skills" / n))
        print(f"  zip  {zpath}")


def print_list(root: Path) -> None:
    print("Agents (--agent):")
    for k, a in AGENTS.items():
        print(f"  {k:<12} {a['name']:<32} project: {a['project']:<18} global: {a['global'] or '-'}")
    print("\nPlugins (--plugin):")
    for p, skills in load_plugins(root).items():
        print(f"  {p:<22} {len(skills):>3} skills")
    print("\nSkills (--skill):")
    for s in all_skills(root):
        print(f"  {s}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Install skill-hub skills into AI coding agents.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Agents: " + ", ".join(AGENTS))
    ap.add_argument("--agent", help="comma-separated agent ids (see --list)")
    ap.add_argument("--plugin", action="append", default=[], help="install every skill of a plugin/category")
    ap.add_argument("--skill", action="append", default=[], help="install one skill (repeatable)")
    ap.add_argument("--global", dest="use_global", action="store_true", help="install for the user, not the project")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    ap.add_argument("--dest", type=Path, help="install into this exact folder instead of an agent's folder")
    ap.add_argument("--zip", type=Path, metavar="DIR", help="write one .zip per skill into DIR (for upload UIs)")
    ap.add_argument("--each", action="store_true",
                    help="project installs: copy into every agent's own folder instead of the fewest shared folders")
    ap.add_argument("--force", action="store_true", help="replace skill folders that already exist")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    ap.add_argument("--ref", default="main", help="branch to download when not run from a clone")
    ap.add_argument("--list", action="store_true", help="list agents, plugins and skills")
    args = ap.parse_args()

    root = find_local_root() or download_hub(args.ref)
    if args.list:
        print_list(root)
        return

    plugins_arg = [x.strip() for v in args.plugin for x in v.split(",") if x.strip()]
    skills_arg = [x.strip() for v in args.skill for x in v.split(",") if x.strip()]
    if not plugins_arg and not skills_arg:
        ap.error("choose what to install with --plugin and/or --skill (see --list)")
    names = resolve(root, plugins_arg, skills_arg)

    if args.zip:
        make_zips(root, names, args.zip)
        return

    dests: list[tuple[str, Path]] = []          # (label, folder)
    if args.dest:
        dests = [("custom folder", args.dest)]
    else:
        if not args.agent:
            ap.error("choose --agent (or --dest / --zip). Agents: " + ", ".join(AGENTS))
        agents = list(dict.fromkeys(a.strip() for a in args.agent.split(",") if a.strip()))
        for a in agents:
            if a not in AGENTS:
                ap.error(f"unknown agent {a!r}. Agents: {', '.join(AGENTS)}")
        project = args.project.expanduser().resolve()
        if args.use_global or args.each:
            seen: dict[Path, list[str]] = {}
            for a in agents:                   # agents sharing a folder get one install
                seen.setdefault(target_dir(a, args.use_global, project), []).append(a)
            groups = list(seen.items())
        else:
            groups = [(project / f, served) for f, served in plan_project_dirs(agents)]
        dests = [(", ".join(AGENTS[a]["name"] for a in served), d) for d, served in groups]

    total = 0
    for label, d in dests:
        print(f"\n{label}: {d}")
        done, _ = install(root, names, d, args.force, args.dry_run)
        total += done
    print(f"\n{'Would install' if args.dry_run else 'Installed'} {total} skill folder(s). "
          "Restart or reload the agent, then just describe your task - it loads a skill when the "
          "request matches the skill's description.")


if __name__ == "__main__":
    main()
