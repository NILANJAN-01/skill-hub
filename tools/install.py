#!/usr/bin/env python3
"""Install skill-hub skills into the AI coding agents / IDEs on this machine.

GUIDED MODE (recommended): run with no options. It detects which agents are installed, asks
which of them to use (all / pick by number / none), asks which skills, shows the exact plan,
and installs only after you confirm.

    python install.py
    curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 -

SCRIPTED MODE (CI, dotfiles, power users):
    python install.py --list                                            # agents (+ detected), plugins, skills
    python install.py --detect                                          # just show which agents are installed
    python install.py --agent detected --plugin git-skills --global --yes
    python install.py --agent cursor --skill git-rebasing               # into ./.cursor/skills
    python install.py --agent copilot,claude-code --plugin hub-tools --global
    python install.py --zip dist --plugin git-branching                 # .zip per skill (upload UIs)

Standard library only (Python 3.8+). Nothing is written without confirmation (or --yes).
Existing skills are never overwritten unless you agree (or pass --force).
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
# Every agent the hub supports. SOURCE OF TRUTH: build_catalog.py copies this table into
# catalog.json and the agent tables in README.md / GUIDE.md. Only change it from vendor docs.
#   project / global         where the agent's own skills folder is (global: None = none on disk)
#   also_reads               other PROJECT folders the agent also scans
#   global_also_reads        other USER folders the agent also scans
#   detect.commands          executables on PATH that show the agent is installed
#   detect.paths             files/folders that show it is installed (~ and %VARS% expanded; a
#                            folder that only holds "skills/" does not count, since we create those)
# --------------------------------------------------------------------------------------------
AGENTS = {
    "claude-code": {
        "name": "Claude Code", "project": ".claude/skills", "global": "~/.claude/skills",
        "also_reads": [], "global_also_reads": [],
        "native": "/plugin marketplace add NILANJAN-01/skill-hub",
        "docs": "https://code.claude.com/docs/en/skills",
        "detect": {"commands": ["claude"], "paths": ["~/.claude"]},
    },
    "antigravity": {
        "name": "Google Antigravity", "project": ".agents/skills", "global": "~/.gemini/config/skills",
        "also_reads": [".agent/skills"], "global_also_reads": [],
        "docs": "https://antigravity.google/docs/skills",
        "detect": {"commands": ["antigravity", "agy"],
                   "paths": ["~/.gemini/antigravity", "~/.gemini/antigravity-cli",
                             "%LOCALAPPDATA%/Programs/Antigravity", "/Applications/Antigravity.app"]},
    },
    "devin": {
        "name": "Devin", "project": ".agents/skills", "global": "~/.config/devin/skills",
        "also_reads": [".devin/skills", ".github/skills", ".claude/skills", ".cursor/skills",
                       ".windsurf/skills", ".codex/skills"],
        "global_also_reads": ["~/.agents/skills"],
        "note": "Cloud Devin reads skills committed to the repo; the global folder is for Devin Local / CLI.",
        "docs": "https://docs.devin.ai/product-guides/skills",
        "detect": {"commands": ["devin"], "paths": ["~/.config/devin", "/Applications/Devin.app"]},
    },
    "copilot": {
        "name": "GitHub Copilot (VS Code)", "project": ".github/skills", "global": "~/.copilot/skills",
        "also_reads": [".agents/skills", ".claude/skills"],
        "global_also_reads": ["~/.agents/skills", "~/.claude/skills"],
        "docs": "https://code.visualstudio.com/docs/agent-customization/agent-skills",
        "detect": {"commands": ["code", "code-insiders", "copilot"],
                   "paths": ["~/.copilot", "~/.vscode", "~/.vscode-insiders",
                             "%LOCALAPPDATA%/Programs/Microsoft VS Code", "%ProgramFiles%/Microsoft VS Code",
                             "/Applications/Visual Studio Code.app", "/usr/share/code", "/snap/bin/code"]},
    },
    "cursor": {
        "name": "Cursor", "project": ".cursor/skills", "global": "~/.cursor/skills",
        "also_reads": [".claude/skills", ".codex/skills"],
        "global_also_reads": ["~/.claude/skills", "~/.codex/skills"],
        "docs": "https://cursor.com/docs/skills",
        "detect": {"commands": ["cursor", "cursor-agent"],
                   "paths": ["~/.cursor", "%LOCALAPPDATA%/Programs/cursor", "/Applications/Cursor.app"]},
    },
    "windsurf": {
        "name": "Windsurf (Devin Local)", "project": ".devin/skills", "global": "~/.config/devin/skills",
        "also_reads": [".windsurf/skills"], "global_also_reads": ["~/.agents/skills"],
        "note": "Windsurf Cascade is now Devin Local; .windsurf/skills is still read as a legacy path.",
        "docs": "https://docs.devin.ai/desktop/cascade/skills",
        "detect": {"commands": ["windsurf"],
                   "paths": ["~/.codeium/windsurf", "~/.windsurf", "%LOCALAPPDATA%/Programs/Windsurf",
                             "/Applications/Windsurf.app"]},
    },
    "codex": {
        "name": "OpenAI Codex", "project": ".agents/skills", "global": "~/.agents/skills",
        "also_reads": [], "global_also_reads": [],
        "docs": "https://learn.chatgpt.com/docs/build-skills",
        "detect": {"commands": ["codex"], "paths": ["~/.codex"]},
    },
    "gemini-cli": {
        "name": "Gemini CLI", "project": ".gemini/skills", "global": "~/.gemini/skills",
        "also_reads": [".agents/skills"], "global_also_reads": ["~/.agents/skills"],
        "docs": "https://geminicli.com/docs/cli/skills/",
        "detect": {"commands": ["gemini"], "paths": []},
    },
    "universal": {
        "name": "Any Agent Skills tool (.agents)", "project": ".agents/skills", "global": "~/.agents/skills",
        "also_reads": [], "global_also_reads": [],
        "note": "The emerging shared location; read by Antigravity, Devin, Copilot, Codex and others.",
        "docs": "https://agentskills.io",
        "detect": {"commands": [], "paths": []},
    },
}


# ============================================================================ hub source
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


def load_plugins(root: Path) -> dict:
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return {p["name"]: {"description": p.get("description", ""),
                        "skills": [Path(s).name for s in p.get("skills", [])]}
            for p in market.get("plugins", [])}


def all_skills(root: Path) -> list:
    return sorted(p.name for p in (root / "skills").iterdir() if (p / "SKILL.md").is_file())


def resolve(root: Path, plugins_arg: list, skills_arg: list) -> list:
    plugins, known = load_plugins(root), set(all_skills(root))
    chosen = []
    for p in plugins_arg:
        if p not in plugins:
            sys.exit(f"Unknown plugin {p!r}. Run with --list to see plugins.")
        chosen += plugins[p]["skills"]
    for s in skills_arg:
        if s not in known:
            sys.exit(f"Unknown skill {s!r}. Run with --list to see skills.")
        chosen.append(s)
    return list(dict.fromkeys(chosen))          # de-duplicate, keep order


# ============================================================================ detection
def _expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def _is_evidence(p: Path) -> bool:
    if p.is_file():
        return True
    if p.is_dir():
        try:
            return any(child.name != "skills" for child in p.iterdir())
        except OSError:
            return False
    return False


def detect_agents() -> dict:
    """{agent id: [evidence, ...]} for every agent that looks installed. Read fresh on every run."""
    found = {}
    for k, a in AGENTS.items():
        ev = []
        for c in a["detect"]["commands"]:
            hit = shutil.which(c)
            if hit:
                ev.append(f"command `{c}`")
        for raw in a["detect"]["paths"]:
            if "%" in raw and os.name != "nt":
                continue
            p = _expand(raw)
            if "%" not in str(p) and _is_evidence(p):
                ev.append(str(p))
        if ev:
            found[k] = ev
    return found


# ============================================================================ planning
def reads(agent: str, use_global: bool, project: Path) -> list:
    """Folders the agent reads skills from, its own folder first."""
    a = AGENTS[agent]
    if use_global:
        return [_expand(p) for p in [a["global"], *a["global_also_reads"]] if p]
    return [project / p for p in [a["project"], *a["also_reads"]]]


def own_dir(agent: str, use_global: bool, project: Path) -> Path | None:
    a = AGENTS[agent]
    if use_global:
        return _expand(a["global"]) if a["global"] else None
    return project / a["project"]


def same_skill(src: Path, dst: Path) -> bool:
    """True if dst holds the same SKILL.md as the hub copy."""
    try:
        return (src / "SKILL.md").read_bytes() == (dst / "SKILL.md").read_bytes()
    except OSError:
        return False


def make_plan(root: Path, names: list, agents: list, use_global: bool, project: Path,
              each: bool = False) -> dict:
    """Decide, per skill, which folders to write so every agent can see it, reusing existing copies.

    Returns {"install": {folder: [skill]}, "outdated": {folder: [skill]}, "uptodate": n,
             "redundant": {folder: [skill]}, "dupes": {agent: [skill]}, "served": {folder: [agent]}}"""
    plan = {"install": {}, "outdated": {}, "uptodate": 0, "redundant": {}, "dupes": {}, "served": {}}
    rd = {a: reads(a, use_global, project) for a in agents}
    candidates = list(dict.fromkeys(own_dir(a, use_global, project) for a in agents))
    for f in candidates:
        plan["served"][f] = [a for a in agents if f in rd[a]]
    for s in names:
        src = root / "skills" / s
        existing = [f for f in dict.fromkeys(x for a in agents for x in rd[a]) if (f / s / "SKILL.md").is_file()]
        if each:
            targets = [own_dir(a, use_global, project) for a in agents]
            new = [f for f in dict.fromkeys(targets) if f not in existing]
        else:
            need = [a for a in agents if not any(f in existing for f in rd[a])]
            new = []
            while need:                       # fewest new folders that cover everyone left
                best = max(candidates, key=lambda f: (sum(f in rd[a] for a in need), -candidates.index(f)))
                new.append(best)
                need = [a for a in need if best not in rd[a]]
        for f in new:
            plan["install"].setdefault(f, []).append(s)
        for f in existing:
            if same_skill(src, f / s):
                plan["uptodate"] += 1
            else:
                plan["outdated"].setdefault(f, []).append(s)
        final = set(existing) | set(new)
        # an existing identical copy is redundant if everyone who reads it can still see another copy
        for f in existing:
            if same_skill(src, f / s) and all(any(g in final - {f} for g in rd[a]) for a in agents if f in rd[a]):
                plan["redundant"].setdefault(f, []).append(s)
                final.discard(f)
        for a in agents:
            if sum(f in final for f in rd[a]) > 1:
                plan["dupes"].setdefault(a, []).append(s)
    return plan


def copy_skill(root: Path, s: str, folder: Path) -> None:
    dst = folder / s
    if dst.exists():
        shutil.rmtree(dst)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "skills" / s, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def fmt(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return "~" + s[len(home):] if s.startswith(home) else s


def show_plan(plan: dict, agents: list) -> int:
    names = {a: AGENTS[a]["name"] for a in agents}
    work = 0
    print("\nPlan:")
    for f, skills in plan["install"].items():
        who = ", ".join(names[a] for a in plan["served"].get(f, [])) or "selected agents"
        print(f"  + install {len(skills):>3} skill(s) into {fmt(f)}   (read by {who})")
        work += len(skills)
    for f, skills in plan["outdated"].items():
        print(f"  ~ {len(skills):>3} installed skill(s) in {fmt(f)} differ from the hub (newer hub version or local edits)")
    for f, skills in plan["redundant"].items():
        print(f"  - {len(skills):>3} identical copy(ies) in {fmt(f)} become redundant (another folder covers them)")
    if plan["uptodate"]:
        print(f"  = {plan['uptodate']} skill copy(ies) already installed and up to date")
    for a, skills in plan["dupes"].items():
        print(f"  ! {names[a]} will find {len(skills)} skill(s) in more than one folder. This is unavoidable with "
              "this agent mix, because their folders overlap. If it lists a skill twice, that's why.")
    if not work and not plan["outdated"] and not plan["redundant"]:
        print("  Nothing to do. Everything selected is already installed.")
    return work


def apply_plan(root: Path, plan: dict, update: bool, remove_redundant: bool, dry: bool) -> int:
    n = 0
    pre = "would " if dry else ""
    for f, skills in plan["install"].items():
        for s in skills:
            print(f"  {pre}install  {s}  ->  {fmt(f / s)}")
            if not dry:
                copy_skill(root, s, f)
            n += 1
    if update:
        for f, skills in plan["outdated"].items():
            for s in skills:
                print(f"  {pre}update   {s}  in  {fmt(f)}")
                if not dry:
                    copy_skill(root, s, f)
                n += 1
    if remove_redundant:
        for f, skills in plan["redundant"].items():
            for s in skills:
                print(f"  {pre}remove   redundant copy  {fmt(f / s)}")
                if not dry:
                    shutil.rmtree(f / s)
    return n


# ============================================================================ prompting
_TTY = None


def _console():
    """Read answers from the terminal even when the script itself arrived on stdin (curl | python)."""
    global _TTY
    if _TTY is None:
        script = globals().get("__file__")
        script_on_stdin = not script or script == "<stdin>"
        if sys.stdin is not None and (sys.stdin.isatty() or not script_on_stdin):
            _TTY = sys.stdin                   # a terminal, or answers piped into a script file
        else:
            try:
                _TTY = open("CONIN$" if os.name == "nt" else "/dev/tty", encoding="utf-8")
            except OSError:
                _TTY = False
    return _TTY


def ask(prompt: str, default: str = "") -> str:
    con = _console()
    if not con:
        sys.exit("No terminal available for questions. Re-run with options instead, e.g.\n"
                 "  --agent detected --plugin git-skills --global --yes")
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = con.readline()
    if not line:
        sys.exit("\nCancelled. Nothing was changed.")
    if not con.isatty():                       # answers were piped in: echo them so the log reads well
        print(line.strip())
    return line.strip() or default


def yes_no(prompt: str, default: bool = False) -> bool:
    ans = ask(f"{prompt} [{'Y/n' if default else 'y/N'}] ", "y" if default else "n").lower()
    return ans in ("y", "yes")


def pick(prompt: str, options: list, all_keys: list | None = None, all_label: str = "all") -> list:
    """options: [(key, label)]. Accepts a (= all_keys), n/none, numbers, ranges (1-3) or keys.
    all_keys=None disables the 'a' shortcut. Returns the chosen keys."""
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i:>2}) {label}")
    hint = f"a = {all_label}, " if all_keys else ""
    hint += "numbers like 1,3 or 2-4, n = none"
    while True:
        ans = ask(f"{prompt} ({hint}): ").strip().lower()
        if ans in ("n", "none", "q", "quit"):
            return []
        if all_keys and ans in ("a", "all", "y", "yes"):
            return list(all_keys)
        keys, ok = [], True
        for part in ans.replace(" ", ",").split(","):
            if not part:
                continue
            try:
                if "-" in part and part.replace("-", "").isdigit():
                    lo, hi = (int(x) for x in part.split("-", 1))
                    keys += [options[i - 1][0] for i in range(lo, hi + 1)]
                elif part.isdigit():
                    keys.append(options[int(part) - 1][0])
                elif part in {k for k, _ in options}:
                    keys.append(part)
                else:
                    ok = False
            except (IndexError, ValueError):
                ok = False
        if ok and keys:
            return list(dict.fromkeys(keys))
        print("  Didn't understand that. Try again.")


def guided(root: Path, args) -> None:
    print("skill-hub installer: let's set up skills for your AI coding agents.\n")
    found = detect_agents()
    print("Agents found on this machine:")
    if not found:
        print("  (none detected)")
    for k, ev in found.items():
        print(f"  [x] {AGENTS[k]['name']:<28} ({'; '.join(ev[:2])})")
    missing = [k for k in AGENTS if k not in found and k != "universal"]
    if missing:
        print("  Not found: " + ", ".join(AGENTS[k]["name"] for k in missing))

    print("\nWhich agents should get the skills?")
    opts = [(k, AGENTS[k]["name"] + ("" if k in found else "   (not detected)"))
            for k in list(found) + [k for k in AGENTS if k not in found]]
    agents = pick("Your choice", opts, all_keys=list(found), all_label=f"all {len(found)} detected")
    if not agents:
        print("No agents chosen. Nothing was changed.")
        return

    plugins = load_plugins(root)
    total = len(all_skills(root))
    print(f"\nWhich skills? ({total} available)")
    opts = [("__all__", f"Everything ({total} skills)")] + \
           [(p, f"{p:<22} {len(v['skills']):>3} skills  {v['description'][:60]}") for p, v in plugins.items()]
    chosen = pick("Your choice", opts, all_keys=["__all__"], all_label="everything")
    if not chosen:
        print("No skills chosen. Nothing was changed.")
        return
    names = all_skills(root) if "__all__" in chosen else resolve(root, chosen, [])

    print("\nWhere?\n   1) For me, in every project (user-level folders)  [default]\n"
          "   2) Only this project: " + str(args.project.resolve()))
    use_global = ask("Your choice [1/2]: ", "1").strip() != "2"
    if use_global:
        nohome = [k for k in agents if not AGENTS[k]["global"]]
        if nohome:
            print("  Skipping (no user-level folder): " + ", ".join(AGENTS[k]["name"] for k in nohome))
            agents = [a for a in agents if a not in nohome]

    plan = make_plan(root, names, agents, use_global, args.project.resolve())
    show_plan(plan, agents)
    update = bool(plan["outdated"]) and yes_no("\nReplace the skills that differ with the hub version?", False)
    tidy = bool(plan["redundant"]) and yes_no("Remove the redundant identical copies?", True)
    if not plan["install"] and not update and not tidy:
        print("\nNothing to change.")
        return
    if not yes_no("\nGo ahead?", True):
        print("Cancelled. Nothing was changed.")
        return
    n = apply_plan(root, plan, update, tidy, dry=False)
    print(f"\nDone: {n} skill folder(s) written. Restart or reload your agents, then just describe your task.")


# ============================================================================ CLI
def remove_skills(names: list, agents: list, use_global: bool, project: Path, yes: bool, dry: bool) -> None:
    """Delete installed copies of the named hub skills from every folder the agents read."""
    folders = list(dict.fromkeys(f for a in agents for f in reads(a, use_global, project)))
    found = [(f, s) for f in folders for s in names if (f / s / "SKILL.md").is_file()]
    if not found:
        print("Nothing to remove. None of the selected skills are installed for these agents.")
        return
    print("\nInstalled copies found:")
    for f, s in found:
        print(f"  - {fmt(f / s)}")
    if dry:
        print(f"\nWould remove {len(found)} skill folder(s).")
        return
    if not yes and not yes_no("\nDelete these skill folders?", False):
        print("Cancelled. Nothing was changed.")
        return
    for f, s in found:
        shutil.rmtree(f / s)
    print(f"\nRemoved {len(found)} skill folder(s).")


def make_zips(root: Path, names: list, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for n in names:
        zpath = out / f"{n}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted((root / "skills" / n).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, Path(n) / f.relative_to(root / "skills" / n))
        print(f"  zip  {zpath}")


def print_detect() -> dict:
    found = detect_agents()
    print("Agents detected on this machine:")
    for k, a in AGENTS.items():
        if k == "universal":
            continue
        mark = "x" if k in found else " "
        why = "; ".join(found.get(k, [])[:2])
        print(f"  [{mark}] {k:<12} {a['name']:<28} {why}")
    return found


def print_list(root: Path) -> None:
    print_detect()
    print("\nAgents (--agent), with their folders:")
    for k, a in AGENTS.items():
        print(f"  {k:<12} project: {a['project']:<18} user: {a['global'] or '-'}")
    print("  detected     every agent marked [x] above")
    print("\nPlugins (--plugin):")
    for p, v in load_plugins(root).items():
        print(f"  {p:<22} {len(v['skills']):>3} skills")
    print("\nSkills (--skill):")
    for s in all_skills(root):
        print(f"  {s}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Install skill-hub skills into AI coding agents. "
                                             "Run with no options for the guided mode.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Agents: " + ", ".join(AGENTS) + ", detected")
    ap.add_argument("--agent", help="comma-separated agent ids, or 'detected' for every installed agent")
    ap.add_argument("--plugin", action="append", default=[], help="install every skill of a plugin/category")
    ap.add_argument("--skill", action="append", default=[], help="install one skill (repeatable)")
    ap.add_argument("--all", action="store_true", help="install every skill in the hub")
    ap.add_argument("--global", dest="use_global", action="store_true", help="install for the user, not the project")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    ap.add_argument("--dest", type=Path, help="install into this exact folder instead of an agent's folder")
    ap.add_argument("--zip", type=Path, metavar="DIR", help="write one .zip per skill into DIR (for upload UIs)")
    ap.add_argument("--each", action="store_true",
                    help="copy into every agent's own folder instead of the fewest shared folders")
    ap.add_argument("--force", action="store_true", help="replace installed skills that differ from the hub")
    ap.add_argument("--update", action="store_true", help="same as --force: refresh installed skills from the hub")
    ap.add_argument("--remove", action="store_true", help="uninstall the selected skills from the selected agents")
    ap.add_argument("--tidy", action="store_true", help="remove redundant identical copies the plan finds")
    ap.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ap.add_argument("--detect", action="store_true", help="only show which agents are installed")
    ap.add_argument("--ref", default="main", help="branch to download when not run from a clone")
    ap.add_argument("--list", action="store_true", help="list agents, plugins and skills")
    args = ap.parse_args()

    if args.detect:
        print_detect()
        return
    root = find_local_root() or download_hub(args.ref)
    if args.list:
        print_list(root)
        return

    plugins_arg = [x.strip() for v in args.plugin for x in v.split(",") if x.strip()]
    skills_arg = [x.strip() for v in args.skill for x in v.split(",") if x.strip()]
    nothing_chosen = not (args.agent or args.dest or args.zip or plugins_arg or skills_arg or args.all)
    if nothing_chosen:
        guided(root, args)
        return

    if not plugins_arg and not skills_arg and not args.all:
        ap.error("choose what to install with --plugin, --skill or --all (or run with no options for guided mode)")
    names = all_skills(root) if args.all else resolve(root, plugins_arg, skills_arg)

    if args.zip:
        make_zips(root, names, args.zip)
        return
    if args.dest:
        print(f"\ncustom folder: {args.dest}")
        for s in names:
            if (args.dest / s).exists() and not args.force:
                print(f"  skip  {s}  (exists; use --force to replace)")
            elif args.dry_run:
                print(f"  would install  {s}  ->  {args.dest / s}")
            else:
                print(f"  install  {s}  ->  {args.dest / s}")
                copy_skill(root, s, args.dest)
        return

    if not args.agent:
        ap.error("choose --agent (an id, a comma list, or 'detected'), --dest or --zip")
    if args.agent.strip() == "detected":
        agents = list(detect_agents())
        if not agents:
            sys.exit("No supported agents detected. Pass --agent explicitly (see --list).")
        print("Detected: " + ", ".join(AGENTS[a]["name"] for a in agents))
    else:
        agents = list(dict.fromkeys(a.strip() for a in args.agent.split(",") if a.strip()))
        for a in agents:
            if a not in AGENTS:
                ap.error(f"unknown agent {a!r}. Agents: {', '.join(AGENTS)}, detected")
    project = args.project.expanduser().resolve()
    if args.use_global:
        nohome = [a for a in agents if not AGENTS[a]["global"]]
        if nohome:
            sys.exit(", ".join(AGENTS[a]["name"] for a in nohome) + " has no user-level skills folder. "
                     "Install into the project instead (omit --global).")

    if args.remove:
        remove_skills(names, agents, args.use_global, project, args.yes, args.dry_run)
        return
    args.force = args.force or args.update
    plan = make_plan(root, names, agents, args.use_global, project, each=args.each)
    show_plan(plan, agents)
    if plan["outdated"] and not args.force:
        print("  (use --force to replace the skills that differ)")
    if plan["redundant"] and not args.tidy:
        print("  (use --tidy to remove the redundant copies)")
    if not plan["install"] and not (args.force and plan["outdated"]) and not (args.tidy and plan["redundant"]):
        return
    if not args.dry_run and not args.yes and not yes_no("\nGo ahead?", True):
        print("Cancelled. Nothing was changed.")
        return
    print()
    n = apply_plan(root, plan, args.force, args.tidy, args.dry_run)
    print(f"\n{'Would write' if args.dry_run else 'Done:'} {n} skill folder(s)."
          + ("" if args.dry_run else " Restart or reload your agents, then just describe your task."))


if __name__ == "__main__":
    main()
