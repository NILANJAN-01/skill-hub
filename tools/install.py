#!/usr/bin/env python3
"""Set up skill-hub for the AI coding agents / IDEs on this machine: skills and the skill-hub MCP server.

ONE COMMAND: detects your agents, installs every skill, registers the MCP server, shows the plan,
and changes nothing until you confirm.

    python install.py --setup
    curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 - --setup
    python install.py --doctor                                          # what is set up, and is it healthy
    python install.py --uninstall                                       # remove everything it set up

GUIDED MODE: run with no options for a menu (everything / choose / doctor / remove).

SCRIPTED MODE (CI, dotfiles, power users):
    python install.py --setup --yes                                     # everything, no questions
    python install.py --agent cursor --plugin ai-agent-tools --mcp      # some skills + the MCP server
    python install.py --agent detected --mcp --global                   # only the MCP server
    python install.py --list                                            # agents (+ detected), plugins, skills
    python install.py --detect                                          # just show which agents are installed
    python install.py --agent detected --plugin git-skills --global --yes
    python install.py --agent cursor --skill git-rebasing               # into ./.cursor/skills
    python install.py --agent copilot,claude-code --plugin hub-tools --global
    python install.py --zip dist --plugin git-branching                 # .zip per skill (upload UIs)
    python install.py --installed --global                              # what is installed, and which version

Standard library only (Python 3.8+). Nothing is written without confirmation (or --yes).
Existing skills are never overwritten unless you agree (or pass --force). Agent MCP config files are
merged: only the "skill-hub" entry changes, and the first edit of each file keeps a .skillhub-backup.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_REPO = "NILANJAN-01/skill-hub"
# Forks can set SKILLHUB_REPO=owner/name (or pass --repo). Release builds replace DEFAULT_REF with
# the release tag, so an install.py downloaded from a release installs that same release.
DEFAULT_REF = "main"
REPO = os.environ.get("SKILLHUB_REPO") or DEFAULT_REPO
# Written into every folder the installer copies skills to: which hub skills are there, at which version.
MANIFEST = ".skill-hub.json"

# --------------------------------------------------------------------------------------------
# Every agent the hub supports. SOURCE OF TRUTH: build_catalog.py copies this table into
# catalog.json and the agent tables in README.md / GUIDE.md. Only change it from vendor docs.
#   project / global         where the agent's own skills folder is (global: None = none on disk)
#   also_reads               other PROJECT folders the agent also scans
#   global_also_reads        other USER folders the agent also scans
#   detect.commands          executables on PATH that show the agent is installed
#   detect.paths             files/folders that show it is installed (~ and %VARS% expanded; a
#                            folder that only holds "skills/" does not count, since we create those)
#   mcp                      where the agent reads MCP servers: project file, user file (a str, or
#                            {"nt": ..., "posix": ...} when it differs by OS), "format" (json or
#                            toml), the JSON "key" holding the servers, and the vendor "docs" page
# --------------------------------------------------------------------------------------------
AGENTS = {
    "claude-code": {
        "name": "Claude Code", "project": ".claude/skills", "global": "~/.claude/skills",
        "also_reads": [], "global_also_reads": [],
        "native": "/plugin marketplace add NILANJAN-01/skill-hub",
        "docs": "https://code.claude.com/docs/en/skills",
        "detect": {"commands": ["claude"], "paths": ["~/.claude"]},
        "mcp": {"project": ".mcp.json", "global": "~/.claude.json", "format": "json", "key": "mcpServers",
                "docs": "https://code.claude.com/docs/en/mcp"},
    },
    "antigravity": {
        "name": "Google Antigravity", "project": ".agents/skills", "global": "~/.gemini/config/skills",
        "also_reads": [".agent/skills"], "global_also_reads": [],
        "docs": "https://antigravity.google/docs/skills",
        "mcp": {"project": ".agents/mcp_config.json", "global": "~/.gemini/config/mcp_config.json",
                "format": "json", "key": "mcpServers", "docs": "https://antigravity.google/docs/mcp"},
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
        "mcp": {"project": ".devin/mcp_config.json",
                "global": {"nt": "%APPDATA%/devin/mcp_config.json", "posix": "~/.config/devin/mcp_config.json"},
                "format": "json", "key": "mcpServers",
                "docs": "https://docs.devin.ai/cli/extensibility/mcp/configuration"},
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
        # The portable Copilot format; the older .vscode/mcp.json ("servers" key) is deprecated.
        "mcp": {"project": ".mcp.json", "global": "~/.copilot/mcp-config.json", "format": "json",
                "key": "mcpServers", "docs": "https://code.visualstudio.com/docs/agents/reference/mcp-configuration"},
    },
    "cursor": {
        "name": "Cursor", "project": ".cursor/skills", "global": "~/.cursor/skills",
        "also_reads": [".claude/skills", ".codex/skills"],
        "global_also_reads": ["~/.claude/skills", "~/.codex/skills"],
        "docs": "https://cursor.com/docs/skills",
        "detect": {"commands": ["cursor", "cursor-agent"],
                   "paths": ["~/.cursor", "%LOCALAPPDATA%/Programs/cursor", "/Applications/Cursor.app"]},
        "mcp": {"project": ".cursor/mcp.json", "global": "~/.cursor/mcp.json", "format": "json",
                "key": "mcpServers", "docs": "https://cursor.com/docs/context/mcp"},
    },
    "windsurf": {
        "name": "Windsurf (Devin Local)", "project": ".devin/skills", "global": "~/.config/devin/skills",
        "also_reads": [".windsurf/skills"], "global_also_reads": ["~/.agents/skills"],
        "note": "Windsurf Cascade is now Devin Local; .windsurf/skills is still read as a legacy path.",
        "docs": "https://docs.devin.ai/desktop/cascade/skills",
        "detect": {"commands": ["windsurf"],
                   "paths": ["~/.codeium/windsurf", "~/.windsurf", "%LOCALAPPDATA%/Programs/Windsurf",
                             "/Applications/Windsurf.app"]},
        "mcp": {"project": ".devin/mcp_config.json",
                "global": {"nt": "%APPDATA%/devin/mcp_config.json", "posix": "~/.config/devin/mcp_config.json"},
                "format": "json", "key": "mcpServers", "docs": "https://docs.devin.ai/desktop/cascade/mcp"},
    },
    "codex": {
        "name": "OpenAI Codex", "project": ".agents/skills", "global": "~/.agents/skills",
        "also_reads": [], "global_also_reads": [],
        "docs": "https://learn.chatgpt.com/docs/build-skills",
        "detect": {"commands": ["codex"], "paths": ["~/.codex"]},
        # Project-level .codex/config.toml is read only in projects the user marked as trusted.
        "mcp": {"project": ".codex/config.toml", "global": "~/.codex/config.toml", "format": "toml",
                "key": "mcp_servers", "docs": "https://developers.openai.com/codex/mcp"},
    },
    "gemini-cli": {
        "name": "Gemini CLI", "project": ".gemini/skills", "global": "~/.gemini/skills",
        "also_reads": [".agents/skills"], "global_also_reads": ["~/.agents/skills"],
        "docs": "https://geminicli.com/docs/cli/skills/",
        "detect": {"commands": ["gemini"], "paths": []},
        "mcp": {"project": ".gemini/settings.json", "global": "~/.gemini/settings.json", "format": "json",
                "key": "mcpServers", "docs": "https://geminicli.com/docs/tools/mcp-server/"},
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


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "skill-hub-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def checksum_ok(data: bytes, sums: str, name: str) -> bool | None:
    """True/False if SHA256SUMS lists `name`; None if it does not."""
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return hashlib.sha256(data).hexdigest() == parts[0].lower()
    return None


def release_zip(ref: str) -> bytes | None:
    """The release's own archive, checked against its SHA256SUMS. None if the release has no such assets."""
    base = f"https://github.com/{REPO}/releases/download/{ref}/"
    name = f"skill-hub-{ref[1:]}.zip"
    try:
        sums = _fetch(base + "SHA256SUMS").decode("utf-8", "replace")
        data = _fetch(base + name)
    except (urllib.error.URLError, OSError):
        return None
    ok = checksum_ok(data, sums, name)
    if ok is None:
        return None
    if not ok:
        sys.exit(f"Checksum mismatch for {name}: the download does not match the release's SHA256SUMS. "
                 "Nothing was installed.")
    print(f"Checksum verified ({name}).")
    return data


def download_hub(ref: str) -> Path:
    print(f"Downloading {REPO}@{ref} ...")
    data = release_zip(ref) if re.fullmatch(r"v\d+(\.\d+)*", ref) else None
    if data is None:
        data = _fetch(f"https://codeload.github.com/{REPO}/zip/{ref}")      # works for branches and tags
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


_INDEX: dict = {}


def skill_index(root: Path) -> dict:
    """{skill name: its folder in the hub}. A skill is skills/<area>/<group>/<name>/ (older hubs: skills/<name>/)."""
    key = str(root)
    if key not in _INDEX:
        found: dict = {}

        def walk(folder: Path, left: int) -> None:
            try:
                children = sorted(p for p in folder.iterdir() if p.is_dir())
            except OSError:
                return
            for p in children:
                if p.name.startswith(".") or p.name == "__pycache__":
                    continue
                if (p / "SKILL.md").is_file():
                    found.setdefault(p.name, p)
                elif left > 1:
                    walk(p, left - 1)

        walk(root / "skills", 3)
        _INDEX[key] = found
    return _INDEX[key]


def skill_src(root: Path, name: str) -> Path:
    try:
        return skill_index(root)[name]
    except KeyError:
        sys.exit(f"Unknown skill {name!r}. Run with --list to see skills.")


def all_skills(root: Path) -> list:
    return sorted(skill_index(root))


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


def skill_files(base: Path) -> dict:
    """{relative path: file} for everything the installer copies from a skill folder."""
    return {p.relative_to(base).as_posix(): p for p in base.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def same_skill(src: Path, dst: Path) -> bool:
    """True if dst holds the same files as the hub copy (SKILL.md, scripts, references, assets).
    Line endings are ignored, so a Windows clone and a downloaded copy compare equal."""
    try:
        a, b = skill_files(src), skill_files(dst)
        return a.keys() == b.keys() and all(
            a[k].read_bytes().replace(b"\r\n", b"\n") == b[k].read_bytes().replace(b"\r\n", b"\n") for k in a)
    except OSError:
        return False


def hub_version(root: Path) -> str:
    try:
        market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        return str(market.get("metadata", {}).get("version", ""))
    except (OSError, ValueError):
        return ""


def read_manifest(folder: Path) -> dict:
    try:
        data = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        return data if isinstance(data.get("skills"), dict) else {"skills": {}}
    except (OSError, ValueError, AttributeError):
        return {"skills": {}}


def record(folder: Path, skill: str, version: str | None) -> None:
    """Note in the folder's manifest that `skill` was installed (version=None: it was removed)."""
    data = read_manifest(folder)
    if version is None:
        if skill not in data["skills"]:
            return
        del data["skills"][skill]
    else:
        data["skills"][skill] = {"version": version, "repo": REPO}
    path = folder / MANIFEST
    if data["skills"]:
        data["note"] = "Written by the skill-hub installer. Lists the hub skills in this folder."
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()


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
        src = skill_src(root, s)
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
    shutil.copytree(skill_src(root, s), dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    record(folder, s, hub_version(root))


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
                    record(f, s, None)
    return n


# ============================================================================ MCP server
# The installer also registers the hub's own MCP server (skill-hub-mcp) with each agent. It runs from
# a snapshot of the hub in ~/.skill-hub/hub (or $SKILLHUB_HOME/hub), so it keeps working when the clone
# moves or there never was one, and works offline. Agent configs are merged, never replaced: only the
# "skill-hub" entry is added, updated or removed, and the first change to a file keeps a backup.
MCP_NAME = "skill-hub"
SNAPSHOT_SKIP = (".git", ".github", "__pycache__", "*.pyc", "dist", "build", "node_modules", ".venv", "venv",
                 ".pytest_cache", ".mypy_cache", ".idea", ".vscode")
BACKUP_SUFFIX = ".skillhub-backup"


def hub_home() -> Path:
    return _expand(os.environ.get("SKILLHUB_HOME") or "~/.skill-hub")


def snapshot_dir() -> Path:
    return hub_home() / "hub"


def tree_hash(root: Path) -> str:
    """Hash of every file the snapshot copies (paths + contents, line endings normalised)."""
    h = hashlib.sha256()
    skip_dirs = {p for p in SNAPSHOT_SKIP if "*" not in p}
    for dirpath, dirs, files in os.walk(str(root)):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs)
        for name in sorted(files):
            if name.endswith(".pyc") or name == ".snapshot.json":
                continue
            p = Path(dirpath) / name
            h.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0")
            try:
                h.update(p.read_bytes().replace(b"\r\n", b"\n"))
            except OSError:
                pass
    return h.hexdigest()


def snapshot_state(root: Path) -> str:
    """'missing', 'current' or 'outdated' compared with the hub at `root`."""
    snap = snapshot_dir()
    if not (snap / "skill-hub-mcp" / "skill_hub_mcp" / "__main__.py").is_file():
        return "missing"
    try:
        if snap.resolve() == root.resolve():
            return "current"
        meta = json.loads((snap / ".snapshot.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "outdated"
    return "current" if meta.get("hash") == tree_hash(root) else "outdated"


def write_snapshot(root: Path) -> None:
    snap = snapshot_dir()
    if snap.exists() and snap.resolve() == root.resolve():
        return
    snap.parent.mkdir(parents=True, exist_ok=True)
    tmp = snap.parent / "hub.new"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(str(root), str(tmp), ignore=shutil.ignore_patterns(*SNAPSHOT_SKIP))
    (tmp / ".snapshot.json").write_text(json.dumps(
        {"version": hub_version(root), "repo": REPO, "hash": tree_hash(root),
         "note": "Snapshot of skill-hub used by the skill-hub MCP server. Managed by install.py."}, indent=2) + "\n",
        encoding="utf-8")
    if snap.exists():
        shutil.rmtree(snap)
    tmp.rename(snap)


def server_entry(allow_install: bool = False) -> dict:
    """The MCP server entry written into agent configs: this Python, the snapshot, stdio."""
    args = ["-m", "skill_hub_mcp"] + (["--allow-install"] if allow_install else [])
    return {"command": sys.executable or "python", "args": args,
            "env": {"PYTHONPATH": str(snapshot_dir() / "skill-hub-mcp")}}


def mcp_info(agent: str) -> dict | None:
    return AGENTS[agent].get("mcp")


def mcp_config_path(agent: str, use_global: bool, project: Path) -> Path | None:
    info = mcp_info(agent)
    if not info:
        return None
    raw = info["global"] if use_global else info["project"]
    if isinstance(raw, dict):
        raw = raw["nt" if os.name == "nt" else "posix"]
    if not raw:
        return None
    return _expand(raw) if use_global else project / raw


# ---- JSON configs
def read_json_config(path: Path) -> dict:
    """{} for a missing or empty file. ValueError if it is not a JSON object (comments, syntax errors)."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("top level is not a JSON object")
    return data


def _same_entry(a, b) -> bool:
    def norm(e):
        if not isinstance(e, dict):
            return e
        e = dict(e)
        if e.get("type") == "stdio":            # some agents add this when they save
            del e["type"]
        if not e.get("env"):
            e.pop("env", None)
        return e
    return norm(a) == norm(b)


# ---- TOML configs (Codex). Only our own [mcp_servers.skill-hub] table is touched, as text.
def _toml_header_is_ours(line: str, key: str) -> bool | None:
    """True for our table header (or its sub-tables), False for another header, None for a non-header."""
    s = line.strip()
    if not s.startswith("["):
        return None
    m = re.match(r'^\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$', s)
    if not m:
        return False
    parts = [p.strip().strip('"').strip("'") for p in m.group(1).split(".")]
    return len(parts) >= 2 and parts[0] == key and parts[1] == MCP_NAME


def toml_split(text: str, key: str):
    """(text without our table, our table's text or None)."""
    keep, ours, inside = [], [], False
    for line in text.splitlines(True):
        state = _toml_header_is_ours(line, key)
        if state is not None:
            inside = state
        (ours if inside else keep).append(line)
    return "".join(keep), ("".join(ours) if ours else None)


def toml_render(key: str, entry: dict) -> str:
    q = json.dumps                                    # JSON strings are valid TOML basic strings
    lines = [f"[{key}.{MCP_NAME}]", f"command = {q(entry['command'])}",
             "args = [" + ", ".join(q(a) for a in entry["args"]) + "]"]
    if entry.get("env"):
        lines.append("env = { " + ", ".join(f"{k} = {q(v)}" for k, v in entry["env"].items()) + " }")
    return "\n".join(lines) + "\n"


# ---- planning and applying
def mcp_status(path: Path, info: dict, entry: dict) -> str:
    """'missing', 'same', 'differs' or 'unreadable: <why>' for our entry in one config file."""
    try:
        if info["format"] == "toml":
            text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
            _, ours = toml_split(text, info["key"])
            if ours is None:
                return "missing"
            return "same" if ours.strip() == toml_render(info["key"], entry).strip() else "differs"
        servers = read_json_config(path).get(info["key"]) or {}
        if not isinstance(servers, dict):
            return f"unreadable: '{info['key']}' is not an object"
        if MCP_NAME not in servers:
            return "missing"
        return "same" if _same_entry(servers[MCP_NAME], entry) else "differs"
    except (OSError, ValueError) as exc:
        return f"unreadable: {exc}"


def make_mcp_plan(agents: list, use_global: bool, project: Path, entry: dict) -> list:
    """One row per config file: {"path", "agents", "info", "status"}. Agents sharing a file share a row."""
    rows: dict = {}
    for a in agents:
        path = mcp_config_path(a, use_global, project)
        if path is None:
            continue
        if path in rows:
            rows[path]["agents"].append(a)
            continue
        info = mcp_info(a)
        rows[path] = {"path": path, "agents": [a], "info": info, "status": mcp_status(path, info, entry)}
    return list(rows.values())


def _write_atomic(path: Path, text: str, backup_first: bool = True) -> None:
    """Write via a temp file. Before the first change to an existing file, keep a .skillhub-backup copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if backup_first and path.is_file() and not backup.exists():
        shutil.copy2(str(path), str(backup))
    tmp = path.with_name(path.name + ".skillhub-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def write_mcp_entry(path: Path, info: dict, entry: dict | None) -> None:
    """Add/replace our entry (entry=None removes it), keeping everything else in the file."""
    if info["format"] == "toml":
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        rest, _ = toml_split(text, info["key"])
        if entry is not None:
            rest = rest.rstrip("\n") + ("\n\n" if rest.strip() else "") + toml_render(info["key"], entry)
        _write_atomic(path, rest, backup_first=entry is not None)
        return
    data = read_json_config(path)
    servers = data.get(info["key"])
    if not isinstance(servers, dict):
        servers = {}
    if entry is None:
        servers.pop(MCP_NAME, None)
    else:
        servers[MCP_NAME] = entry
    data[info["key"]] = servers
    _write_atomic(path, json.dumps(data, indent=2) + "\n", backup_first=entry is not None)


def manual_snippet(info: dict, entry: dict) -> str:
    if info["format"] == "toml":
        return toml_render(info["key"], entry)
    return json.dumps({info["key"]: {MCP_NAME: entry}}, indent=2)


def show_mcp_plan(rows: list, snap: str, removing: bool = False) -> int:
    """Print the MCP part of the plan; return how many config files would change."""
    work = 0
    print("\nMCP server (skill-hub):")
    if not removing:
        if snap == "missing":
            print(f"  + copy the hub to {fmt(snapshot_dir())} (the server runs from there)")
        elif snap == "outdated":
            print(f"  ~ refresh the hub copy in {fmt(snapshot_dir())} (it differs from this hub)")
        else:
            print(f"  = hub copy in {fmt(snapshot_dir())} is up to date")
    for r in rows:
        who = ", ".join(AGENTS[a]["name"] for a in r["agents"])
        st, where = r["status"], fmt(r["path"])
        if st.startswith("unreadable"):
            print(f"  ! {where} ({who}) can't be read safely ({st[12:]}); it will be left alone")
        elif removing:
            if st != "missing":
                print(f"  - remove the entry from {where}   ({who})")
                work += 1
        elif st == "missing":
            print(f"  + add the server to {where}   ({who})")
            work += 1
        elif st == "differs":
            print(f"  ~ update the server entry in {where}   ({who})")
            work += 1
        else:
            print(f"  = already set up in {where}   ({who})")
    if not rows:
        print("  (none of the chosen agents has a known MCP config location)")
    return work


def apply_mcp_plan(root: Path, rows: list, entry: dict | None, snap: str, dry: bool) -> int:
    """entry=None removes. Returns files changed. Unreadable files get a manual snippet instead."""
    pre = "would " if dry else ""
    if entry is not None and snap != "current":
        print(f"  {pre}copy hub  ->  {fmt(snapshot_dir())}")
        if not dry:
            write_snapshot(root)
    n = 0
    for r in rows:
        st = r["status"]
        if st.startswith("unreadable"):
            if entry is not None:
                print(f"  skip  {fmt(r['path'])}: add this by hand ({r['info']['docs']}):\n"
                      + "\n".join("        " + line for line in manual_snippet(r["info"], entry).splitlines()))
            continue
        if (entry is None and st == "missing") or (entry is not None and st == "same"):
            continue
        verb = "remove" if entry is None else ("add" if st == "missing" else "update")
        print(f"  {pre}{verb} mcp  {MCP_NAME}  in  {fmt(r['path'])}")
        if not dry:
            write_mcp_entry(r["path"], r["info"], entry)
        n += 1
    return n


def check_server(timeout: int = 60) -> str:
    """Start the snapshot's server with --check. Returns its one-line summary or an error."""
    import subprocess
    entry = server_entry()
    env = dict(os.environ, **entry["env"])
    try:
        out = subprocess.run([entry["command"]] + entry["args"] + ["--check"], env=env, timeout=timeout,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"FAILED: {exc}"
    msg = (out.stderr or out.stdout).strip().splitlines()
    return ("ok: " if out.returncode == 0 else "FAILED: ") + (msg[-1] if msg else f"exit {out.returncode}")


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
    print("skill-hub installer: skills and the skill-hub MCP server for your AI coding agents.\n")
    found = detect_agents()
    print("Agents found on this machine:")
    if not found:
        print("  (none detected)")
    for k, ev in found.items():
        print(f"  [x] {AGENTS[k]['name']:<28} ({'; '.join(ev[:2])})")
    missing = [k for k in AGENTS if k not in found and k != "universal"]
    if missing:
        print("  Not found: " + ", ".join(AGENTS[k]["name"] for k in missing))

    print("\nWhat would you like to do?\n"
          f"   1) Set up everything: all {len(all_skills(root))} skills + the MCP server, for the detected agents"
          "  [default]\n"
          "   2) Choose agents, skills and options\n"
          "   3) Check what is set up (doctor)\n"
          "   4) Remove everything skill-hub set up")
    choice = ask("Your choice [1-4]: ", "1").strip()
    project = (args.project or Path.cwd()).expanduser().resolve()
    if choice in ("1", "4"):
        if not found:
            print("No agents detected, so there is nothing to do. Use option 2 to pick agents by hand.")
            return
        agents = [a for a in found if AGENTS[a]["global"]]
        execute(root, agents, all_skills(root), True, project, mcp=True, remove=choice == "4",
                uninstall=choice == "4", tidy=True)
        return
    if choice == "3":
        doctor(root, list(found) or [k for k in AGENTS if k != "universal"], project)
        return

    print("\nWhich agents?")
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
    names = all_skills(root) if "__all__" in chosen else resolve(root, chosen, [])

    print("\nAlso set up the skill-hub MCP server? It lets the agents search the whole hub and load any skill\n"
          "on demand, even ones you did not install.")
    mcp = yes_no("Set up the MCP server?", True)
    if not names and not mcp:
        print("Nothing chosen. Nothing was changed.")
        return

    print("\nWhere?\n   1) For me, in every project (user-level)  [default]\n"
          "   2) Only this project: " + str(project))
    use_global = ask("Your choice [1/2]: ", "1").strip() != "2"
    if use_global:
        nohome = [k for k in agents if not AGENTS[k]["global"]]
        if nohome:
            print("  Skipping (no user-level folder): " + ", ".join(AGENTS[k]["name"] for k in nohome))
            agents = [a for a in agents if a not in nohome]
    execute(root, agents, names, use_global, project, mcp=mcp, ask_options=True)


def doctor(root: Path, agents: list, project: Path) -> int:
    """Report skills and MCP setup per agent, user-level and for this project. Returns problems found."""
    problems = 0
    known = set(all_skills(root))
    print(f"\nskill-hub {hub_version(root) or '(unknown version)'}: {len(known)} skills, Python {sys.version.split()[0]}")
    snap = snapshot_state(root)
    print(f"Hub copy for the MCP server: {fmt(snapshot_dir())}  ({snap})")
    if snap != "missing":
        result = check_server()
        print(f"MCP server self-check: {result}")
        problems += result.startswith("FAILED")
    entry = server_entry()
    stale_total, mcp_bad = set(), 0
    user_skills, user_mcp = {}, {}              # per agent, from the user-level pass, to explain project rows
    for use_global, label in ((True, "user-level (applies to every project)"),
                              (False, f"project {fmt(project)} (only this folder; optional)")):
        print(f"\n{label}:")
        for a in agents:
            folders = reads(a, use_global, project) if (AGENTS[a]["global"] or not use_global) else []
            pairs = [(f, s) for f in folders for s in known if (f / s / "SKILL.md").is_file()]
            names = {s for _, s in pairs}
            stale = {s for f, s in pairs if not same_skill(skill_src(root, s), f / s)}
            path = mcp_config_path(a, use_global, project)
            if path is None:
                mcp = "no known MCP config"
            else:
                st = mcp_status(path, mcp_info(a), entry)
                mcp = {"same": "set up", "missing": "not set up", "differs": "set up, but out of date"}.get(st, st)
                mcp_bad += st == "differs" or st.startswith("unreadable")
            skills = f"{len(names)}" + (f" ({len(stale)} differ from the hub)" if stale else "")
            stale_total |= stale
            if use_global:
                user_skills[a], user_mcp[a] = len(names), mcp == "set up"
            else:
                if not names and user_skills.get(a):
                    skills = "0 (user-level covers it)"
                if mcp == "not set up" and user_mcp.get(a):
                    mcp = "not needed (user-level covers it)"
            print(f"  {AGENTS[a]['name']:<26} skills: {skills:<29} MCP: {mcp}")
    if stale_total:
        print(f"\nSkills that differ from the hub (an older hub version, or edited locally): "
              f"{', '.join(sorted(stale_total))}.\n"
              "  Fix: python install.py --setup --update   (replaces them with the hub version; asks first)")
    if mcp_bad:
        print("\nAn MCP entry is out of date or unreadable.\n  Fix: python install.py --setup")
    problems += len(stale_total) + mcp_bad
    print("\nAll good." if not problems else f"\n{problems} thing(s) to fix (see above).")
    return problems


def execute(root: Path, agents: list, names: list, use_global: bool, project: Path, mcp: bool = False,
            allow_install: bool = False, force: bool = False, tidy: bool = False, each: bool = False,
            yes: bool = False, dry: bool = False, remove: bool = False, uninstall: bool = False,
            ask_options: bool = False) -> None:
    """Plan everything (skills + MCP server), show it, confirm once, then apply."""
    if remove:
        remove_all(names, agents, use_global, project, mcp, uninstall, yes, dry)
        return
    plan = make_plan(root, names, agents, use_global, project, each=each) if names else None
    skill_work = 0
    if plan:
        show_plan(plan, agents)
        if ask_options:
            force = bool(plan["outdated"]) and yes_no("\nReplace the skills that differ with the hub version?", False)
            tidy = bool(plan["redundant"]) and yes_no("Remove the redundant identical copies?", True)
        else:
            if plan["outdated"] and not force:
                print("  (use --update to replace the skills that differ)")
            if plan["redundant"] and not tidy:
                print("  (use --tidy to remove the redundant copies)")
        skill_work = len(plan["install"]) + (force and len(plan["outdated"])) + (tidy and len(plan["redundant"]))
    rows, entry, snap, mcp_work = [], None, "current", 0
    if mcp:
        entry = server_entry(allow_install)
        snap = snapshot_state(root)
        rows = make_mcp_plan(agents, use_global, project, entry)
        mcp_work = show_mcp_plan(rows, snap) + (snap != "current")
    if not skill_work and not mcp_work:
        print("\nNothing to change. Everything selected is already set up.")
        return
    if not dry and not yes and not yes_no("\nGo ahead?", True):
        print("Cancelled. Nothing was changed.")
        return
    print()
    n = apply_plan(root, plan, force, tidy, dry) if plan else 0
    m = apply_mcp_plan(root, rows, entry, snap, dry) if mcp else 0
    if dry:
        print(f"\nWould write {n} skill folder(s) and {m} MCP config file(s).")
        return
    print(f"\nDone: {n} skill folder(s) and {m} MCP config file(s) written. "
          "Restart or reload your agents, then just describe your task.")
    if mcp:
        print("Check the setup any time with:  python install.py --doctor")


def remove_all(names: list, agents: list, use_global: bool, project: Path, mcp: bool, uninstall: bool,
               yes: bool, dry: bool) -> None:
    """Delete installed copies of the named hub skills, and (mcp) our MCP entries, after one confirmation."""
    folders = list(dict.fromkeys(f for a in agents for f in reads(a, use_global, project)))
    found = [(f, s) for f in folders for s in names if (f / s / "SKILL.md").is_file()]
    rows = make_mcp_plan(agents, use_global, project, server_entry()) if mcp else []
    drop_snapshot = uninstall and snapshot_dir().exists()
    if found:
        print("\nInstalled skill copies:")
        for f, s in found:
            print(f"  - {fmt(f / s)}")
    mcp_work = show_mcp_plan(rows, "current", removing=True) if mcp else 0
    if drop_snapshot:
        print(f"  - delete the hub copy {fmt(snapshot_dir())}")
    if not found and not mcp_work and not drop_snapshot:
        print("Nothing to remove. None of the selected items are set up for these agents.")
        return
    if dry:
        print(f"\nWould remove {len(found)} skill folder(s) and {mcp_work} MCP server entries.")
        return
    if not yes and not yes_no("\nRemove these?", False):
        print("Cancelled. Nothing was changed.")
        return
    for f, s in found:
        shutil.rmtree(f / s)
        record(f, s, None)
    m = apply_mcp_plan(Path("."), rows, None, "current", False) if mcp else 0
    if drop_snapshot:
        shutil.rmtree(snapshot_dir())
    print(f"\nRemoved {len(found)} skill folder(s) and {m} MCP server entries."
          + (f" Deleted {fmt(snapshot_dir())}." if drop_snapshot else ""))


# ============================================================================ CLI


def print_installed(root: Path, agents: list, use_global: bool, project: Path) -> None:
    """Hub skills in the folders these agents read: installed version, and whether it matches this hub."""
    current, known = hub_version(root), set(all_skills(root))
    folders = list(dict.fromkeys(f for a in agents for f in reads(a, use_global, project)))
    total = 0
    for f in folders:
        versions = read_manifest(f)["skills"]
        names = sorted(s for s in known if (f / s / "SKILL.md").is_file())
        if not names:
            continue
        print(f"\n{fmt(f)}")
        for s in names:
            v = versions.get(s, {}).get("version") or "unknown version"
            state = "up to date" if same_skill(skill_src(root, s), f / s) else "differs from the hub"
            print(f"  {s:<42} {v:<16} {state}")
            total += 1
    print(f"\n{total} hub skill(s) installed. This hub is version {current or 'unknown'}."
          + (" Use --update to refresh the ones that differ." if total else ""))


def make_zips(root: Path, names: list, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for n in names:
        zpath = out / f"{n}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            src = skill_src(root, n)
            for f in sorted(src.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, Path(n) / f.relative_to(src))
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
    global REPO
    ap = argparse.ArgumentParser(description="Install skill-hub skills into AI coding agents. "
                                             "Run with no options for the guided mode.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Agents: " + ", ".join(AGENTS) + ", detected")
    ap.add_argument("--agent", help="comma-separated agent ids, or 'detected' for every installed agent")
    ap.add_argument("--plugin", action="append", default=[], help="install every skill of a plugin/category")
    ap.add_argument("--skill", action="append", default=[], help="install one skill (repeatable)")
    ap.add_argument("--all", action="store_true", help="install every skill in the hub")
    ap.add_argument("--setup", action="store_true",
                    help="set up everything in one go: every skill plus the MCP server, for every detected agent, "
                         "user-level (narrow it with --agent, --plugin, --skill or --project)")
    ap.add_argument("--doctor", action="store_true", help="check what is set up: skills, MCP config, server self-check")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove everything skill-hub set up: skills, MCP entries and the hub copy")
    ap.add_argument("--mcp", action="store_true",
                    help="also register the skill-hub MCP server with the chosen agents (alone: only the server)")
    ap.add_argument("--mcp-allow-install", action="store_true",
                    help="let the MCP server install skills (after you approve each plan in the agent)")
    ap.add_argument("--global", dest="use_global", action="store_true", help="install for the user, not the project")
    ap.add_argument("--project", type=Path, default=None, help="project root (default: current directory)")
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
    ap.add_argument("--installed", action="store_true",
                    help="list the hub skills already installed, with their version (for --agent, default: detected)")
    ap.add_argument("--ref", default=os.environ.get("SKILLHUB_REF") or DEFAULT_REF,
                    help="branch or release tag to download when not run from a clone (or $SKILLHUB_REF)")
    ap.add_argument("--repo", metavar="OWNER/NAME", help="GitHub repository to download from (default: %s, or $SKILLHUB_REPO)" % REPO)
    ap.add_argument("--list", action="store_true", help="list agents, plugins and skills")
    args = ap.parse_args()
    if args.repo:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
            ap.error("--repo must look like owner/name")
        REPO = args.repo

    if args.detect:
        print_detect()
        return
    root = find_local_root() or download_hub(args.ref)
    if args.list:
        print_list(root)
        return
    project = (args.project or Path.cwd()).expanduser().resolve()
    if args.setup or args.uninstall:             # one-shot modes: sensible defaults, all overridable
        args.agent = args.agent or "detected"
        args.mcp = True
        args.tidy = args.tidy or args.setup
        if not (args.plugin or args.skill):
            args.all = True
        if args.project is None:
            args.use_global = True
        args.remove = args.remove or args.uninstall
    if args.doctor:
        if args.agent and args.agent.strip() != "detected":
            agents = [a.strip() for a in args.agent.split(",") if a.strip()]
        else:
            agents = list(detect_agents()) or [k for k in AGENTS if k != "universal"]
        sys.exit(1 if doctor(root, agents, project) else 0)
    if args.installed:
        if args.agent and args.agent.strip() != "detected":
            agents = [a.strip() for a in args.agent.split(",") if a.strip()]
            for a in agents:
                if a not in AGENTS:
                    ap.error(f"unknown agent {a!r}. Agents: {', '.join(AGENTS)}, detected")
        else:
            agents = list(detect_agents()) or list(AGENTS)
        if args.use_global:
            agents = [a for a in agents if AGENTS[a]["global"]]
        print_installed(root, agents, args.use_global, project)
        return

    plugins_arg = [x.strip() for v in args.plugin for x in v.split(",") if x.strip()]
    skills_arg = [x.strip() for v in args.skill for x in v.split(",") if x.strip()]
    nothing_chosen = not (args.agent or args.dest or args.zip or plugins_arg or skills_arg or args.all or args.mcp)
    if nothing_chosen:
        guided(root, args)
        return

    if not plugins_arg and not skills_arg and not args.all and not args.mcp:
        ap.error("choose what to install with --plugin, --skill, --all or --mcp "
                 "(or use --setup for everything, or run with no options for guided mode)")
    names = all_skills(root) if args.all else resolve(root, plugins_arg, skills_arg)
    if (args.zip or args.dest) and not names:
        ap.error("--zip and --dest need --plugin, --skill or --all")

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
    if args.use_global:
        nohome = [a for a in agents if not AGENTS[a]["global"]]
        if nohome:
            sys.exit(", ".join(AGENTS[a]["name"] for a in nohome) + " has no user-level skills folder. "
                     "Install into the project instead (omit --global).")

    execute(root, agents, names, args.use_global, project, mcp=args.mcp, allow_install=args.mcp_allow_install,
            force=args.force or args.update, tidy=args.tidy, each=args.each, yes=args.yes, dry=args.dry_run,
            remove=args.remove, uninstall=args.uninstall)


if __name__ == "__main__":
    main()
