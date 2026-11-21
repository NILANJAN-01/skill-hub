#!/usr/bin/env python3
"""Set up skill-hub for the AI coding agents / IDEs on this machine: skills and the skill-hub MCP server.

ONE COMMAND: detects your agents, installs every skill, registers the MCP server and the skill-dispatcher
hook (Claude Code, Codex, Antigravity, Copilot), shows the plan, and changes nothing until you confirm.

    python install.py --setup
    curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py | python3 - --setup
    python install.py --doctor                                          # what is set up, and is it healthy
    python install.py --uninstall                                       # remove everything it set up

GUIDED MODE: run with no options for a menu (everything / choose / doctor / remove).

SCRIPTED MODE (CI, dotfiles, power users):
    python install.py --setup --yes                                     # everything, no questions
    python install.py --agent cursor --plugin ai-agent-tools --mcp      # some skills + the MCP server
    python install.py --agent detected --mcp --global                   # only the MCP server
    python install.py --agent detected --prompt-hook --global           # only the skill-dispatcher hooks

OTHER MCP SERVERS, into every detected agent at once (user-level; merged, with backups):
    python install.py --list-mcp                                        # what each agent has + presets
    python install.py --add-mcp playwright --mcp-test                   # a preset; test it first
    python install.py --add-mcp filesystem --mcp-arg C:/work            # presets that need arguments
    python install.py --add-mcp github --mcp-env GITHUB_PERSONAL_ACCESS_TOKEN   # secret copied from env
    python install.py --add-mcp mydb --mcp-command "uvx my-db-mcp --readonly"   # any other server
    python install.py --remove-mcp playwright
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
#   prompt_hook              how to register skill-dispatcher as a hook, from the vendor's hook docs:
#                            "style" (nested / named / file, see the prompt hook section), the JSON
#                            file ("project": a personal, uncommitted file, or None; "global"; optional
#                            "home_env" + "home_rel" when an env var moves the user folder), the hook
#                            "event", the dispatcher "args" (output format the agent expects), "docs"
#   token_hooks              how to register token-optimizer's hooks (--token-hooks), from the vendor's
#                            hook docs: the JSON file ("project", "global"), and "hooks", a list of
#                            {"event", optional "matcher", "args" for token_hook.py}, plus "docs"
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
        # UserPromptSubmit: the command's stdout is added to the model's context for that prompt.
        "prompt_hook": {"style": "nested", "project": ".claude/settings.local.json",
                        "global": "~/.claude/settings.json", "event": "UserPromptSubmit",
                        "args": ["--hook", "--no-briefs"], "docs": "https://code.claude.com/docs/en/hooks"},
        # PreToolUse can deny a tool call with a reason the model reads; SessionEnd gets transcript_path.
        "token_hooks": {"project": ".claude/settings.local.json", "global": "~/.claude/settings.json",
                        "hooks": [{"event": "PreToolUse", "matcher": "Read", "args": ["read-guard"]},
                                  {"event": "SessionEnd", "args": ["session-end", "--agent", "claude-code"]}],
                        "docs": "https://code.claude.com/docs/en/hooks"},
    },
    "antigravity": {
        "name": "Google Antigravity", "project": ".agents/skills", "global": "~/.gemini/config/skills",
        "also_reads": [".agent/skills"], "global_also_reads": [],
        "docs": "https://antigravity.google/docs/skills",
        "mcp": {"project": ".agents/mcp_config.json", "global": "~/.gemini/config/mcp_config.json",
                "format": "json", "key": "mcpServers", "docs": "https://antigravity.google/docs/mcp"},
        # No per-prompt event: PreInvocation runs before each model call (stdin lastUserInput), and
        # {"injectSteps": [{"ephemeralMessage": ...}]} adds a transient message. The dispatcher sends
        # the plan once per prompt. Same file for the App, CLI and IDE.
        "prompt_hook": {"style": "named", "project": None, "global": "~/.gemini/config/hooks.json",
                        "event": "PreInvocation", "args": ["--hook", "--hook-format", "injectsteps", "--no-briefs"],
                        "docs": "https://antigravity.google/docs/hooks"},
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
        # Output of a userPromptSubmitted command hook is ignored, so a sessionStart hook (top-level
        # {"additionalContext": ...}) adds a standing instruction to run the dispatcher. Every *.json in
        # the user hooks folder is loaded; VS Code, the Copilot app and the CLI share it.
        "prompt_hook": {"style": "file", "project": None, "global": "~/.copilot/hooks/skill-hub.json",
                        "home_env": "COPILOT_HOME", "home_rel": "hooks/skill-hub.json", "event": "sessionStart",
                        "args": ["--hook", "--hook-format", "session"],
                        "note": "once per session: tells the agent when to run the dispatcher",
                        "docs": "https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-hooks-reference"},
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
        # UserPromptSubmit with hookSpecificOutput.additionalContext. New hooks run only after the user
        # trusts them once in /hooks. Project .codex/hooks.json is shared (committed), so user-level only.
        "prompt_hook": {"style": "nested", "project": None, "global": "~/.codex/hooks.json",
                        "home_env": "CODEX_HOME", "home_rel": "hooks.json", "event": "UserPromptSubmit",
                        "args": ["--hook", "--hook-format", "json", "--no-briefs"],
                        "note": "trust it once in Codex's /hooks", "docs": "https://developers.openai.com/codex/hooks"},
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


_REQUIRES = re.compile(r"^[ \t]+requires:[ \t]*[\"']?([^\"'\r\n]*)", re.M)


def skill_requires(root: Path, name: str) -> list:
    """Skills this one needs installed next to it: `metadata.requires` in its SKILL.md (comma-separated)."""
    try:
        text = (skill_src(root, name) / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return []
    fm = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.S)
    m = _REQUIRES.search(fm.group(1)) if fm else None
    return [s.strip() for s in m.group(1).split(",") if s.strip()] if m else []


def with_requirements(root: Path, names: list) -> list:
    """`names` plus every skill they require, directly or through another, each added once and announced."""
    out, known = list(names), set(all_skills(root))
    i = 0
    while i < len(out):
        for need in skill_requires(root, out[i]):
            if need in known and need not in out:
                print(f"  + {need}  (needed by {out[i]})")
                out.append(need)
        i += 1
    return out


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


# ---- TOML configs (Codex). Only the one [mcp_servers.<name>] table being changed is touched, as text.
def _toml_table(line: str):
    """For a table header line, its dotted key parts; None for any other line."""
    s = line.strip()
    if not s.startswith("["):
        return None
    m = re.match(r'^\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$', s)
    if not m:
        return []
    return [p.strip().strip('"').strip("'") for p in m.group(1).split(".")]


def toml_split(text: str, key: str, name: str = MCP_NAME):
    """(text without the [key.name] table and its sub-tables, that table's text or None)."""
    keep, ours, inside = [], [], False
    for line in text.splitlines(True):
        parts = _toml_table(line)
        if parts is not None:
            inside = len(parts) >= 2 and parts[0] == key and parts[1] == name
        (ours if inside else keep).append(line)
    return "".join(keep), ("".join(ours) if ours else None)


def toml_server_names(text: str, key: str) -> list:
    names = []
    for line in text.splitlines():
        parts = _toml_table(line)
        if parts and len(parts) == 2 and parts[0] == key and parts[1] not in names:
            names.append(parts[1])
    return names


def toml_render(key: str, entry: dict, name: str = MCP_NAME) -> str:
    q = json.dumps                                    # JSON strings are valid TOML basic strings
    lines = [f"[{key}.{name}]", f"command = {q(entry['command'])}",
             "args = [" + ", ".join(q(a) for a in entry["args"]) + "]"]
    if entry.get("env"):
        lines.append("env = { " + ", ".join(f"{k} = {q(v)}" for k, v in entry["env"].items()) + " }")
    return "\n".join(lines) + "\n"


# ---- planning and applying
def mcp_status(path: Path, info: dict, entry: dict, name: str = MCP_NAME) -> str:
    """'missing', 'same', 'differs' or 'unreadable: <why>' for one server entry in one config file."""
    try:
        if info["format"] == "toml":
            text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
            _, ours = toml_split(text, info["key"], name)
            if ours is None:
                return "missing"
            return "same" if ours.strip() == toml_render(info["key"], entry, name).strip() else "differs"
        servers = read_json_config(path).get(info["key"]) or {}
        if not isinstance(servers, dict):
            return f"unreadable: '{info['key']}' is not an object"
        if name not in servers:
            return "missing"
        return "same" if _same_entry(servers[name], entry) else "differs"
    except (OSError, ValueError) as exc:
        return f"unreadable: {exc}"


def configured_servers(path: Path, info: dict) -> list:
    """Names of every MCP server in one config file ([] if missing or unreadable)."""
    try:
        if info["format"] == "toml":
            return toml_server_names(path.read_text(encoding="utf-8-sig"), info["key"]) if path.is_file() else []
        servers = read_json_config(path).get(info["key"]) or {}
        return list(servers) if isinstance(servers, dict) else []
    except (OSError, ValueError):
        return []


def make_mcp_plan(agents: list, use_global: bool, project: Path, entry: dict, name: str = MCP_NAME) -> list:
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
        rows[path] = {"path": path, "agents": [a], "info": info, "status": mcp_status(path, info, entry, name)}
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


def write_mcp_entry(path: Path, info: dict, entry: dict | None, name: str = MCP_NAME) -> None:
    """Add/replace one server entry (entry=None removes it), keeping everything else in the file."""
    if info["format"] == "toml":
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        rest, _ = toml_split(text, info["key"], name)
        if entry is not None:
            rest = rest.rstrip("\n") + ("\n\n" if rest.strip() else "") + toml_render(info["key"], entry, name)
        _write_atomic(path, rest, backup_first=entry is not None)
        return
    data = read_json_config(path)
    servers = data.get(info["key"])
    if not isinstance(servers, dict):
        servers = {}
    if entry is None:
        servers.pop(name, None)
    else:
        servers[name] = entry
    data[info["key"]] = servers
    _write_atomic(path, json.dumps(data, indent=2) + "\n", backup_first=entry is not None)


def manual_snippet(info: dict, entry: dict, name: str = MCP_NAME) -> str:
    if info["format"] == "toml":
        return toml_render(info["key"], entry, name)
    return json.dumps({info["key"]: {name: entry}}, indent=2)


def show_mcp_plan(rows: list, snap: str | None, removing: bool = False, name: str = MCP_NAME) -> int:
    """Print the MCP part of the plan; return how many config files would change. snap=None: no hub copy."""
    work = 0
    print(f"\nMCP server ({name}):")
    if not removing and snap is not None:
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


def apply_mcp_plan(root: Path, rows: list, entry: dict | None, snap: str | None, dry: bool,
                   name: str = MCP_NAME) -> int:
    """entry=None removes. Returns files changed. Unreadable files get a manual snippet instead."""
    pre = "would " if dry else ""
    if entry is not None and snap not in (None, "current"):
        print(f"  {pre}copy hub  ->  {fmt(snapshot_dir())}")
        if not dry:
            write_snapshot(root)
    n = 0
    for r in rows:
        st = r["status"]
        if st.startswith("unreadable"):
            if entry is not None:
                print(f"  skip  {fmt(r['path'])}: add this by hand ({r['info']['docs']}):\n"
                      + "\n".join("        " + line for line in manual_snippet(r["info"], entry, name).splitlines()))
            continue
        if (entry is None and st == "missing") or (entry is not None and st == "same"):
            continue
        verb = "remove" if entry is None else ("add" if st == "missing" else "update")
        print(f"  {pre}{verb} mcp  {name}  in  {fmt(r['path'])}")
        if not dry:
            write_mcp_entry(r["path"], r["info"], entry, name)
        n += 1
    return n


# ============================================================================ prompt hook
# skill-dispatcher reads what the user asks and tells the agent which skills fit and what can run in
# parallel. Agents with a "prompt_hook" entry in AGENTS get it registered as a hook. Three config styles:
#   nested  {"hooks": {EVENT: [{"hooks": [handler]}]}}   merged with the user's other hooks
#   named   {NAME: {EVENT: [handler]}}                    our own named entry in a shared file
#   file    a whole hook file of our own                  {"version": 1, "hooks": {EVENT: [handler]}}
HOOK_SKILL = "skill-dispatcher"
HOOK_NEEDS = ("skill-dispatcher", "skill-router")      # the dispatcher imports the router's matcher
HOOK_NAME = "skill-hub-dispatcher"                      # our entry's name in "named" files
HOOK_TIMEOUT = 15


def hook_info(agent: str) -> dict | None:
    return AGENTS[agent].get("prompt_hook")


def hook_config_path(agent: str, use_global: bool, project: Path) -> Path | None:
    """The file the hook goes in; None when the agent has no such file at this scope."""
    info = hook_info(agent)
    if not info:
        return None
    if not use_global:
        return project / info["project"] if info.get("project") else None
    home = os.environ.get(info["home_env"]) if info.get("home_env") else None
    return Path(home) / info["home_rel"] if home else _expand(info["global"])


def _quoted(part: str) -> str:
    return f'"{part}"' if re.search(r"\s", part) else part


def hook_commands(info: dict, skill_dir: Path) -> tuple:
    """(posix-shell command, PowerShell command) running this Python on the installed dispatcher. Paths without
    spaces stay unquoted, so the same text also works in cmd and PowerShell."""
    py = Path(sys.executable).as_posix() if sys.executable else "python"
    parts = [py, (skill_dir / "scripts" / "dispatch.py").as_posix(), *info["args"]]
    cmd = " ".join(_quoted(p) for p in parts)
    return cmd, ("& " + cmd if cmd.startswith('"') else cmd)


def hook_entry(info: dict, skill_dir: Path):
    """What we write for this agent: a handler (nested), an event map (named) or a whole file (file)."""
    cmd, ps = hook_commands(info, skill_dir)
    if info["style"] == "file":
        return {"version": 1, "hooks": {info["event"]: [{"type": "command", "bash": cmd, "powershell": ps,
                                                         "timeoutSec": HOOK_TIMEOUT}]}}
    handler = {"type": "command", "command": cmd, "timeout": HOOK_TIMEOUT}
    return {info["event"]: [handler]} if info["style"] == "named" else handler


def _is_our_hook(h) -> bool:
    cmd = h.get("command", "") if isinstance(h, dict) else ""
    return isinstance(cmd, str) and HOOK_SKILL in cmd and "dispatch.py" in cmd


def _hook_groups(data: dict, event: str) -> list:
    hooks = data.get("hooks")
    groups = hooks.get(event) if isinstance(hooks, dict) else None
    return groups if isinstance(groups, list) else []


def hook_status(path: Path, info: dict, entry) -> str:
    """missing / same / differs / unreadable: <why>."""
    try:
        data = read_json_config(path)
    except (OSError, ValueError) as exc:
        return f"unreadable: {exc}"
    if info["style"] == "file":
        return "missing" if not path.is_file() else ("same" if data == entry else "differs")
    if info["style"] == "named":
        return "missing" if HOOK_NAME not in data else ("same" if data[HOOK_NAME] == entry else "differs")
    ours = [h for g in _hook_groups(data, info["event"]) if isinstance(g, dict) and isinstance(g.get("hooks"), list)
            for h in g["hooks"] if _is_our_hook(h)]
    if not ours:
        return "missing"
    return "same" if ours == [entry] else "differs"


def write_hook(path: Path, info: dict, entry) -> None:
    """Add or replace our hook (entry=None removes it), keeping every other hook and setting in the file."""
    if info["style"] == "file":
        if entry is None:
            if path.is_file():
                path.unlink()
        else:
            _write_atomic(path, json.dumps(entry, indent=2) + "\n")
        return
    data = read_json_config(path)
    if info["style"] == "named":
        if entry is None:
            data.pop(HOOK_NAME, None)
        else:
            data[HOOK_NAME] = entry
        _write_atomic(path, json.dumps(data, indent=2) + "\n", backup_first=entry is not None)
        return
    groups = []
    for g in _hook_groups(data, info["event"]):
        if isinstance(g, dict) and isinstance(g.get("hooks"), list) and any(_is_our_hook(h) for h in g["hooks"]):
            kept = [h for h in g["hooks"] if not _is_our_hook(h)]
            if kept:
                groups.append(dict(g, hooks=kept))
        else:
            groups.append(g)
    if entry is not None:
        groups.append({"hooks": [entry]})
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    if groups:
        hooks[info["event"]] = groups
    else:
        hooks.pop(info["event"], None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    _write_atomic(path, json.dumps(data, indent=2) + "\n", backup_first=entry is not None)


def hook_skills_folder(agent: str, use_global: bool, project: Path) -> Path | None:
    """Where this agent finds skill-dispatcher: the first folder it reads that has it, else its own folder
    (where the installer puts it). Agents that read another agent's folder get no second copy."""
    for folder in reads(agent, use_global, project):
        if (folder / HOOK_SKILL / "SKILL.md").is_file():
            return folder
    return own_dir(agent, use_global, project)


def make_hook_plan(agents: list, use_global: bool, project: Path, names: list, removing: bool = False) -> list:
    """One row per hook file. When adding, only for agents that will have both needed skills."""
    rows = {}
    for a in agents:
        path, folder = hook_config_path(a, use_global, project), hook_skills_folder(a, use_global, project)
        if path is None or folder is None or path in rows:
            continue
        if not removing and not all(n in names or (folder / n / "SKILL.md").is_file() for n in HOOK_NEEDS):
            continue
        info = hook_info(a)
        entry = hook_entry(info, folder / HOOK_SKILL)
        rows[path] = {"path": path, "agent": a, "info": info, "entry": entry,
                      "status": hook_status(path, info, entry)}
    return list(rows.values())


def show_hook_plan(rows: list, removing: bool = False) -> int:
    """Print the prompt-hook part of the plan; return how many files would change."""
    if not rows or (removing and all(r["status"] == "missing" for r in rows)):
        return 0
    work = 0
    print(f"\nPrompt hook ({HOOK_SKILL}: routes requests to skills, plans parallel work):")
    for r in rows:
        st, where = r["status"], fmt(r["path"])
        who = AGENTS[r["agent"]]["name"] + (f"; {r['info']['note']}" if r["info"].get("note") else "")
        if st.startswith("unreadable"):
            print(f"  ! {where} ({AGENTS[r['agent']]['name']}) can't be read safely ({st[12:]}); it will be left alone")
        elif removing:
            if st != "missing":
                print(f"  - remove the hook from {where}   ({AGENTS[r['agent']]['name']})")
                work += 1
        elif st == "missing":
            print(f"  + add the hook to {where}   ({who})")
            work += 1
        elif st == "differs":
            print(f"  ~ update the hook in {where}   ({who})")
            work += 1
        else:
            print(f"  = already set up in {where}   ({AGENTS[r['agent']]['name']})")
    return work


def apply_hook_plan(rows: list, removing: bool, dry: bool) -> int:
    pre, n = "would " if dry else "", 0
    for r in rows:
        st = r["status"]
        if st.startswith("unreadable"):
            if not removing:
                print(f"  skip  {fmt(r['path'])}: add this {r['info']['event']} hook by hand ({r['info']['docs']}):\n"
                      + "\n".join("        " + line for line in json.dumps(r["entry"], indent=2).splitlines()))
            continue
        if (removing and st == "missing") or (not removing and st == "same"):
            continue
        verb = "remove" if removing else ("add" if st == "missing" else "update")
        print(f"  {pre}{verb} hook  {HOOK_SKILL}  in  {fmt(r['path'])}")
        if not dry:
            write_hook(r["path"], r["info"], None if removing else r["entry"])
        n += 1
    return n


# ============================================================================ token hooks
# --token-hooks registers token-optimizer's hook script, for agents with a "token_hooks" entry in AGENTS:
# a read guard before file reads (blocks a whole read of a big file once, pointing the agent to a short
# version) and a usage import at session end. Opt-in: not part of --setup; --uninstall removes it.
TOKEN_SKILL = "token-optimizer"
TOKEN_SCRIPT = "token_hook.py"
TOKEN_HOOK_TIMEOUT = 30


def token_hook_path(agent: str, use_global: bool, project: Path) -> Path | None:
    info = AGENTS[agent].get("token_hooks")
    if not info:
        return None
    if not use_global:
        return project / info["project"] if info.get("project") else None
    return _expand(info["global"])


def token_handlers(info: dict, skill_dir: Path) -> list:
    """[(event, matcher or None, handler)] running this Python on the installed token_hook.py."""
    py = Path(sys.executable).as_posix() if sys.executable else "python"
    out = []
    for h in info["hooks"]:
        parts = [py, (skill_dir / "scripts" / TOKEN_SCRIPT).as_posix(), *h["args"]]
        out.append((h["event"], h.get("matcher"),
                    {"type": "command", "command": " ".join(_quoted(p) for p in parts), "timeout": TOKEN_HOOK_TIMEOUT}))
    return out


def _is_token_hook(h) -> bool:
    cmd = h.get("command", "") if isinstance(h, dict) else ""
    return isinstance(cmd, str) and TOKEN_SKILL in cmd and TOKEN_SCRIPT in cmd


def _our_token_hooks(data: dict) -> list:
    """[(event, matcher, handler)] of our hooks already in a nested hooks file."""
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    return [(event, g.get("matcher"), h) for event in hooks for g in _hook_groups(data, event)
            if isinstance(g, dict) and isinstance(g.get("hooks"), list) for h in g["hooks"] if _is_token_hook(h)]


def token_hook_status(path: Path, handlers: list) -> str:
    """missing / same / differs / unreadable: <why>."""
    try:
        data = read_json_config(path)
    except (OSError, ValueError) as exc:
        return f"unreadable: {exc}"
    ours = _our_token_hooks(data)
    if not ours:
        return "missing"
    def key(x):
        return json.dumps(x, sort_keys=True)
    return "same" if sorted(map(key, ours)) == sorted(map(key, handlers)) else "differs"


def write_token_hooks(path: Path, handlers) -> None:
    """Replace our hooks with `handlers` (None removes them), keeping every other hook and setting."""
    data = read_json_config(path)
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    for event in list(dict.fromkeys(list(hooks) + [e for e, _, _ in handlers or []])):
        groups = []
        for g in _hook_groups(data, event):
            if isinstance(g, dict) and isinstance(g.get("hooks"), list) and any(_is_token_hook(h) for h in g["hooks"]):
                kept = [h for h in g["hooks"] if not _is_token_hook(h)]
                if kept:
                    groups.append(dict(g, hooks=kept))
            else:
                groups.append(g)
        for e, matcher, handler in handlers or []:
            if e == event:
                groups.append(dict({"matcher": matcher} if matcher else {}, hooks=[handler]))
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    _write_atomic(path, json.dumps(data, indent=2) + "\n", backup_first=handlers is not None)


def make_token_hook_plan(agents: list, use_global: bool, project: Path, names: list, removing: bool = False) -> list:
    """One row per hook file. When adding, only for agents that will have token-optimizer."""
    rows = {}
    for a in agents:
        path = token_hook_path(a, use_global, project)
        if path is None or path in rows:
            continue
        folder = next((f for f in reads(a, use_global, project) if (f / TOKEN_SKILL / "SKILL.md").is_file()),
                      own_dir(a, use_global, project))
        if folder is None or (not removing and TOKEN_SKILL not in names
                              and not (folder / TOKEN_SKILL / "SKILL.md").is_file()):
            continue
        handlers = token_handlers(AGENTS[a]["token_hooks"], folder / TOKEN_SKILL)
        rows[path] = {"path": path, "agent": a, "handlers": handlers, "status": token_hook_status(path, handlers)}
    return list(rows.values())


def show_token_hook_plan(rows: list, removing: bool = False) -> int:
    """Print the token-hook part of the plan; return how many files would change."""
    if not rows or (removing and all(r["status"] == "missing" for r in rows)):
        return 0
    work = 0
    print(f"\nToken hooks ({TOKEN_SKILL}: read guard for big files, usage import at session end):")
    for r in rows:
        st, where, who = r["status"], fmt(r["path"]), AGENTS[r["agent"]]["name"]
        if st.startswith("unreadable"):
            print(f"  ! {where} ({who}) can't be read safely ({st[12:]}); it will be left alone")
        elif removing:
            print(f"  - remove the token hooks from {where}   ({who})")
            work += 1
        elif st == "same":
            print(f"  = already set up in {where}   ({who})")
        else:
            print(f"  {'+ add' if st == 'missing' else '~ update'} the token hooks in {where}   ({who})")
            work += 1
    return work


def apply_token_hook_plan(rows: list, removing: bool, dry: bool) -> int:
    pre, n = "would " if dry else "", 0
    for r in rows:
        st = r["status"]
        if st.startswith("unreadable"):
            if not removing:
                print(f"  skip  {fmt(r['path'])}: add these hooks by hand "
                      f"({AGENTS[r['agent']]['token_hooks']['docs']}):")
                for event, matcher, handler in r["handlers"]:
                    print(f"        {event}" + (f" (matcher {matcher})" if matcher else "") + f": {handler['command']}")
            continue
        if (removing and st == "missing") or (not removing and st == "same"):
            continue
        print(f"  {pre}{'remove' if removing else 'set'} token hooks  in  {fmt(r['path'])}")
        if not dry:
            write_token_hooks(r["path"], None if removing else r["handlers"])
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


# ============================================================================ other MCP servers
# --add-mcp writes any stdio MCP server into every chosen agent's config, with the same merging and
# backups as the skill-hub entry. Presets are well-known servers from their maintainers' docs; any
# other server works with --mcp-command. Secrets: --mcp-env NAME copies the value from your environment.
MCP_PRESETS = {
    "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                   "needs_args": "the folders it may read and write (--mcp-arg <folder>, repeatable)",
                   "description": "Read, write and search files in the folders you allow",
                   "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem"},
    "memory": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"],
               "description": "Persistent knowledge-graph memory across sessions",
               "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory"},
    "sequential-thinking": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                            "description": "Step-by-step problem solving with revisable thoughts",
                            "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking"},
    "fetch": {"command": "uvx", "args": ["mcp-server-fetch"],
              "description": "Fetch web pages and convert them to markdown",
              "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch"},
    "git": {"command": "uvx", "args": ["mcp-server-git"],
            "description": "Read, search and change local git repositories",
            "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/git"},
    "time": {"command": "uvx", "args": ["mcp-server-time"],
             "description": "Current time and time-zone conversion",
             "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/time"},
    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"],
                   "description": "Drive a browser: open pages, click, fill forms, take snapshots",
                   "docs": "https://github.com/microsoft/playwright-mcp"},
    "github": {"command": "docker",
               "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server"],
               "env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
               "description": "GitHub issues, pull requests, code search and repos (needs Docker and a token)",
               "docs": "https://github.com/github/github-mcp-server"},
    "everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"],
                   "description": "Reference server exposing every MCP feature, for testing clients",
                   "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/everything"},
}
SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
RUNTIME_HINTS = {"npx": "Node.js (https://nodejs.org)", "uvx": "uv (https://docs.astral.sh/uv/)",
                 "docker": "Docker (https://docs.docker.com/get-docker/)"}


class McpError(Exception):
    """A server definition that cannot be written (bad name, missing argument or secret)."""


def _split_command(cmd: str) -> list:
    import shlex
    if os.name == "nt":                       # keep backslashes in Windows paths; drop wrapping quotes
        return [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in shlex.split(cmd, posix=False)]
    return shlex.split(cmd)


def build_server(name: str, command: str | None = None, extra_args: list | None = None,
                 env_pairs: list | None = None, environ: dict | None = None) -> tuple:
    """(entry, notes) for a preset or a custom command. Raises McpError when something required is missing."""
    environ = os.environ if environ is None else environ
    if not SERVER_NAME_RE.match(name or ""):
        raise McpError(f"server name {name!r} must be letters, digits, '-' or '_' (max 64)")
    if name == MCP_NAME:
        raise McpError("the skill-hub server is managed with --mcp (or --setup)")
    preset = MCP_PRESETS.get(name) if not command else None
    if preset is None and not command:
        raise McpError(f"{name!r} is not a preset. Pass --mcp-command \"<command> <args>\" "
                       f"(presets: {', '.join(MCP_PRESETS)})")
    parts = _split_command(command) if command else [preset["command"]] + list(preset["args"])
    if not parts:
        raise McpError("--mcp-command is empty")
    args = parts[1:] + list(extra_args or [])
    if preset and preset.get("needs_args") and not extra_args:
        raise McpError(f"{name} needs {preset['needs_args']}")
    env, notes = {}, []
    wanted = [(p.split("=", 1) if "=" in p else [p, None]) for p in (env_pairs or [])]
    named = {k for k, _ in wanted}
    wanted += [[k, None] for k in (preset or {}).get("env", []) if k not in named]
    for key, value in wanted:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            raise McpError(f"bad environment variable name {key!r}")
        if value is None:
            value = environ.get(key)
            if not value:
                raise McpError(f"{name} needs {key}. Set it in your environment first (it is copied from "
                               f"there, so it stays out of your shell history), or pass --mcp-env {key}=<value>")
        env[key] = value
    exe = parts[0]
    found = shutil.which(exe)
    if not found:
        notes.append(f"'{exe}' is not on PATH yet; install {RUNTIME_HINTS.get(exe, exe)} before using this server")
    if os.name == "nt" and found and found.lower().endswith((".cmd", ".bat")):
        args, exe = ["/c", exe] + args, "cmd"     # agents start servers without a shell; .cmd needs cmd /c
    entry = {"command": exe, "args": args}
    if env:
        entry["env"] = env
        notes.append("secrets are written into the agents' config files: keep those files private")
    return entry, notes


def find_probe(root: Path):
    """The mcp_probe module from the mcp-server-builder skill, or None."""
    import importlib.util
    path = skill_index(root).get("mcp-server-builder")
    script = path / "scripts" / "mcp_probe.py" if path else None
    if not script or not script.is_file():
        return None
    spec = importlib.util.spec_from_file_location("skillhub_mcp_probe", str(script))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_server(root: Path, entry: dict, timeout: float = 120) -> tuple:
    """(ok, summary): start the server, handshake, list tools. Uses mcp-server-builder's probe."""
    probe = find_probe(root)
    if probe is None:
        return False, "the mcp-server-builder skill (with its probe) is not in this hub"
    saved = dict(os.environ)
    os.environ.update(entry.get("env") or {})
    try:
        report = probe.run_probe([entry["command"]] + entry["args"], timeout=timeout)
    except probe.ProbeError as exc:
        return False, str(exc).splitlines()[0]
    finally:
        os.environ.clear()
        os.environ.update(saved)
    errors = [m for lv, m in report["findings"] if lv == "ERROR"]
    tools = [t.get("name") for t in report.get("tools", []) if isinstance(t, dict)]
    summary = f"{(report.get('server') or {}).get('name', '?')}: {len(tools)} tool(s)" + \
              (f" ({', '.join(tools[:6])}{', ...' if len(tools) > 6 else ''})" if tools else "")
    return not errors, summary + ("; " + "; ".join(errors[:3]) if errors else "")


def manage_server(root: Path, name: str, agents: list, use_global: bool, project: Path, entry: dict | None,
                  yes: bool = False, dry: bool = False, test: bool = False) -> int:
    """Add/update (entry) or remove (entry=None) one server for the agents. Returns config files changed."""
    probe_entry = entry
    if entry is None:                            # removing: any entry with that name counts
        probe_entry = {"command": "", "args": []}
    rows = make_mcp_plan(agents, use_global, project, probe_entry, name)
    if entry is None:
        for r in rows:
            if r["status"] == "differs":
                r["status"] = "present"
    work = show_mcp_plan(rows, None, removing=entry is None, name=name)
    if not work:
        print("\nNothing to change." if entry is not None else f"\n{name} is not set up for these agents.")
        return 0
    if test and entry is not None:
        print(f"\nTesting {name} (starts it, runs the MCP handshake, lists its tools) ...")
        ok, summary = test_server(root, entry)
        print(("  ok: " if ok else "  FAILED: ") + summary)
        if not ok:
            print("Nothing was changed. Fix the server, or run without --mcp-test to add it anyway.")
            return 0
    if not dry and not yes and not yes_no("\nGo ahead?", True):
        print("Cancelled. Nothing was changed.")
        return 0
    print()
    n = apply_mcp_plan(root, rows, entry, None, dry, name)
    print(f"\n{'Would change' if dry else 'Changed'} {n} MCP config file(s)."
          + ("" if dry else " Restart or reload your agents to pick it up."))
    return n


def print_servers(agents: list, project: Path) -> None:
    """Every MCP server configured for the agents, user-level and for this project, then the presets."""
    for use_global, label in ((True, "user-level"), (False, f"project {fmt(project)}")):
        print(f"\nMCP servers, {label}:")
        seen = False
        for a in agents:
            path = mcp_config_path(a, use_global, project)
            if path is None:
                continue
            names = configured_servers(path, mcp_info(a))
            if names:
                seen = True
                print(f"  {AGENTS[a]['name']:<26} {', '.join(names)}   ({fmt(path)})")
        if not seen:
            print("  (none)")
    print("\nPresets for --add-mcp <name>:")
    for k, p in MCP_PRESETS.items():
        extra = "  [needs " + ", ".join(p["env"]) + "]" if p.get("env") else ""
        extra += "  [needs --mcp-arg]" if p.get("needs_args") else ""
        print(f"  {k:<20} {p['description']}{extra}")
    print('  any other:          --add-mcp <name> --mcp-command "<command> <args>"')


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
                uninstall=choice == "4", tidy=True, hook=True)
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
    names = all_skills(root) if "__all__" in chosen else with_requirements(root, resolve(root, chosen, []))

    print("\nAlso set up the skill-hub MCP server? It lets the agents search the whole hub and load any skill\n"
          "on demand, even ones you did not install.")
    mcp = yes_no("Set up the MCP server?", True)
    hook = False
    if any(hook_info(a) for a in agents) and all(n in names for n in HOOK_NEEDS):
        print(f"\nAlso route every prompt to skills automatically? A prompt hook runs {HOOK_SKILL} on each\n"
              "prompt and tells the agent which skills fit and what can run in parallel.")
        hook = yes_no("Set up the prompt hook?", True)
    if not names and not mcp and not hook:
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
    execute(root, agents, names, use_global, project, mcp=mcp, ask_options=True, hook=hook)


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
            hook_txt, hook_path = "", hook_config_path(a, use_global, project)
            folder = hook_skills_folder(a, use_global, project)
            if hook_path is not None and folder is not None:
                st = hook_status(hook_path, hook_info(a), hook_entry(hook_info(a), folder / HOOK_SKILL))
                hook_txt = "  hook: " + {"same": "set up", "missing": "off",
                                         "differs": "set up, but out of date"}.get(st, st)
            print(f"  {AGENTS[a]['name']:<26} skills: {skills:<29} MCP: {mcp}{hook_txt}")
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
            ask_options: bool = False, hook: bool = False, token_hook: bool = False) -> None:
    """Plan everything (skills + MCP server + prompt hook + token hooks), show it, confirm once, then apply."""
    if remove:
        remove_all(names, agents, use_global, project, mcp, uninstall, yes, dry, hook=hook, token_hook=token_hook)
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
    hook_rows = make_hook_plan(agents, use_global, project, names) if hook else []
    hook_work = show_hook_plan(hook_rows)
    token_rows = make_token_hook_plan(agents, use_global, project, names) if token_hook else []
    hook_work += show_token_hook_plan(token_rows)
    if not skill_work and not mcp_work and not hook_work:
        print("\nNothing to change. Everything selected is already set up.")
        return
    if not dry and not yes and not yes_no("\nGo ahead?", True):
        print("Cancelled. Nothing was changed.")
        return
    print()
    n = apply_plan(root, plan, force, tidy, dry) if plan else 0
    m = apply_mcp_plan(root, rows, entry, snap, dry) if mcp else 0
    if hook and not dry:                         # skills are in place now: point each hook at the real copy
        hook_rows = make_hook_plan(agents, use_global, project, names)
    h = apply_hook_plan(hook_rows, False, dry)
    if token_hook and not dry:
        token_rows = make_token_hook_plan(agents, use_global, project, names)
    t = apply_token_hook_plan(token_rows, False, dry)
    hooks = (f" and {h} prompt hook(s)" if hook_rows else "") + (f", {t} token hook file(s)" if token_rows else "")
    if dry:
        print(f"\nWould write {n} skill folder(s), {m} MCP config file(s){hooks}.")
        return
    print(f"\nDone: {n} skill folder(s), {m} MCP config file(s){hooks} written. "
          "Restart or reload your agents, then just describe your task.")
    if mcp:
        print("Check the setup any time with:  python install.py --doctor")


def remove_all(names: list, agents: list, use_global: bool, project: Path, mcp: bool, uninstall: bool,
               yes: bool, dry: bool, hook: bool = False, token_hook: bool = False) -> None:
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
    hook_rows = make_hook_plan(agents, use_global, project, names, removing=True) if hook else []
    hook_work = show_hook_plan(hook_rows, removing=True)
    token_rows = make_token_hook_plan(agents, use_global, project, names, removing=True) if token_hook else []
    hook_work += show_token_hook_plan(token_rows, removing=True)
    if drop_snapshot:
        print(f"  - delete the hub copy {fmt(snapshot_dir())}")
    if not found and not mcp_work and not hook_work and not drop_snapshot:
        print("Nothing to remove. None of the selected items are set up for these agents.")
        return
    if dry:
        print(f"\nWould remove {len(found)} skill folder(s), {mcp_work} MCP server entries and "
              f"{hook_work} hook file(s).")
        return
    if not yes and not yes_no("\nRemove these?", False):
        print("Cancelled. Nothing was changed.")
        return
    for f, s in found:
        shutil.rmtree(f / s)
        record(f, s, None)
    m = apply_mcp_plan(Path("."), rows, None, "current", False) if mcp else 0
    h = apply_hook_plan(hook_rows, True, False) + apply_token_hook_plan(token_rows, True, False)
    if drop_snapshot:
        shutil.rmtree(snapshot_dir())
    print(f"\nRemoved {len(found)} skill folder(s), {m} MCP server entries and {h} hook file(s)."
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


def choose_agents(ap, spec: str) -> list:
    """Agent ids from --agent: 'detected' or a comma list. Exits with a message on unknown ids."""
    if spec.strip() == "detected":
        agents = list(detect_agents())
        if not agents:
            sys.exit("No supported agents detected. Pass --agent explicitly (see --list).")
        print("Detected: " + ", ".join(AGENTS[a]["name"] for a in agents))
        return agents
    agents = list(dict.fromkeys(a.strip() for a in spec.split(",") if a.strip()))
    for a in agents:
        if a not in AGENTS:
            ap.error(f"unknown agent {a!r}. Agents: {', '.join(AGENTS)}, detected")
    return agents


def build_parser() -> argparse.ArgumentParser:
    """The installer's command line. Option groups also drive the reference in user-guide.html."""
    ap = argparse.ArgumentParser(description="Install skill-hub skills into AI coding agents. "
                                             "Run with no options for the guided mode.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Agents: " + ", ".join(AGENTS) + ", detected")
    g = ap.add_argument_group("One command","Set up, check or remove everything at once")
    g.add_argument("--setup", action="store_true",
                   help="set up everything in one go: every skill plus the MCP server, for every detected agent, "
                        "user-level (narrow it with --agent, --plugin, --skill or --project)")
    g.add_argument("--doctor", action="store_true",
                   help="check what is set up: skills, MCP config, prompt hook, server self-check")
    g.add_argument("--uninstall", action="store_true",
                   help="remove everything skill-hub set up: skills, MCP entries and the hub copy")

    g = ap.add_argument_group("Choose agents and skills","What to install, for which agents, and where")
    g.add_argument("--agent", help="comma-separated agent ids, or 'detected' for every installed agent")
    g.add_argument("--plugin", action="append", default=[], help="install every skill of a plugin/category")
    g.add_argument("--skill", action="append", default=[], help="install one skill (repeatable)")
    g.add_argument("--all", action="store_true", help="install every skill in the hub")
    g.add_argument("--global", dest="use_global", action="store_true", help="install for the user, not the project")
    g.add_argument("--project", type=Path, default=None, help="project root (default: current directory)")
    g.add_argument("--dest", type=Path, help="install into this exact folder instead of an agent's folder")
    g.add_argument("--zip", type=Path, metavar="DIR", help="write one .zip per skill into DIR (for upload UIs)")
    g.add_argument("--each", action="store_true",
                   help="copy into every agent's own folder instead of the fewest shared folders")

    g = ap.add_argument_group("Update and remove","Keep installed skills in step with the hub")
    g.add_argument("--installed", action="store_true",
                   help="list the hub skills already installed, with their version (for --agent, default: detected)")
    g.add_argument("--force", action="store_true", help="replace installed skills that differ from the hub")
    g.add_argument("--update", action="store_true", help="same as --force: refresh installed skills from the hub")
    g.add_argument("--remove", action="store_true", help="uninstall the selected skills from the selected agents")
    g.add_argument("--tidy", action="store_true", help="remove redundant identical copies the plan finds")

    g = ap.add_argument_group("MCP servers","The skill-hub MCP server and any other MCP server, in every agent")
    g.add_argument("--mcp", action="store_true",
                   help="also register the skill-hub MCP server with the chosen agents (alone: only the server)")
    g.add_argument("--mcp-allow-install", action="store_true",
                   help="let the MCP server install skills (after you approve each plan in the agent)")
    g.add_argument("--add-mcp", metavar="NAME",
                   help="add any MCP server to the chosen agents (default: every detected agent, user-level): "
                        "a preset (see --list-mcp) or your own with --mcp-command")
    g.add_argument("--remove-mcp", metavar="NAME", help="remove an MCP server from the chosen agents")
    g.add_argument("--list-mcp", action="store_true", help="list the MCP servers each agent has, and the presets")
    g.add_argument("--mcp-command", metavar='"CMD ARGS"', help='command that starts the server, e.g. "npx -y my-server"')
    g.add_argument("--mcp-arg", action="append", default=[], metavar="ARG",
                   help="extra argument for the server (repeatable), e.g. a folder for the filesystem preset")
    g.add_argument("--mcp-env", action="append", default=[], metavar="NAME[=VALUE]",
                   help="environment variable for the server (repeatable); NAME alone copies it from your environment")
    g.add_argument("--mcp-test", action="store_true",
                   help="with --add-mcp: start the server and check it answers before writing anything")

    g = ap.add_argument_group("Prompt hook", "Route every prompt to the right skills automatically "
                              f"({HOOK_SKILL}), in agents whose prompt hook can add context")
    g.add_argument("--prompt-hook", action="store_true",
                   help=f"register {HOOK_SKILL} as the agent's prompt-submit hook (part of --setup and --uninstall)")
    g.add_argument("--no-prompt-hook", action="store_true",
                   help="with --setup or --uninstall: leave the prompt hook alone")
    g.add_argument("--token-hooks", action="store_true",
                   help=f"register {TOKEN_SKILL}'s hooks: a read guard that sends whole reads of big files to a "
                        "short version, and a usage import at session end (opt-in; --uninstall removes them)")

    g = ap.add_argument_group("Information and safety","Look before you change anything")
    g.add_argument("--detect", action="store_true", help="only show which agents are installed")
    g.add_argument("--list", action="store_true", help="list agents, plugins and skills")
    g.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    g.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")

    g = ap.add_argument_group("Source","Where the skills come from when not run from a clone")
    g.add_argument("--ref", default=os.environ.get("SKILLHUB_REF") or DEFAULT_REF,
                   help="branch or release tag to download when not run from a clone (or $SKILLHUB_REF)")
    g.add_argument("--repo", metavar="OWNER/NAME",
                   help="GitHub repository to download from (default: %s, or $SKILLHUB_REPO)" % DEFAULT_REPO)
    return ap


def main() -> None:
    global REPO
    ap = build_parser()
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
        args.prompt_hook = not args.no_prompt_hook
        args.token_hooks = args.token_hooks or args.uninstall
    if args.doctor:
        if args.agent and args.agent.strip() != "detected":
            agents = [a.strip() for a in args.agent.split(",") if a.strip()]
        else:
            agents = list(detect_agents()) or [k for k in AGENTS if k != "universal"]
        sys.exit(1 if doctor(root, agents, project) else 0)
    if args.add_mcp or args.remove_mcp or args.list_mcp:
        agents = choose_agents(ap, args.agent or "detected")
        if args.list_mcp:
            print_servers(agents, project)
            return
        use_global = args.use_global or args.project is None      # user-level unless --project is given
        if args.remove_mcp:
            manage_server(root, args.remove_mcp, agents, use_global, project, None, args.yes, args.dry_run)
            return
        try:
            entry, notes = build_server(args.add_mcp, args.mcp_command, args.mcp_arg, args.mcp_env)
        except McpError as exc:
            sys.exit(f"Can't add {args.add_mcp}: {exc}")
        print(f"Server {args.add_mcp}: {entry['command']} {' '.join(entry['args'])}")
        for note in notes:
            print(f"  note: {note}")
        if entry.get("env") and not use_global:
            print("  WARNING: this writes the secret into project files that may be committed. "
                  "Prefer user-level (omit --project).")
        manage_server(root, args.add_mcp, agents, use_global, project, entry, args.yes, args.dry_run, args.mcp_test)
        return
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
    nothing_chosen = not (args.agent or args.dest or args.zip or plugins_arg or skills_arg or args.all or args.mcp
                          or args.prompt_hook or args.token_hooks)
    if nothing_chosen:
        guided(root, args)
        return

    if not (plugins_arg or skills_arg or args.all or args.mcp or args.prompt_hook or args.token_hooks):
        ap.error("choose what to install with --plugin, --skill, --all, --mcp, --prompt-hook or --token-hooks "
                 "(or use --setup for everything, or run with no options for guided mode)")
    names = all_skills(root) if args.all else resolve(root, plugins_arg, skills_arg)
    if not args.remove:                         # removing a skill leaves the skills it needed in place
        names = with_requirements(root, names)
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
    agents = choose_agents(ap, args.agent)
    if args.use_global:
        nohome = [a for a in agents if not AGENTS[a]["global"]]
        if nohome:
            sys.exit(", ".join(AGENTS[a]["name"] for a in nohome) + " has no user-level skills folder. "
                     "Install into the project instead (omit --global).")

    execute(root, agents, names, args.use_global, project, mcp=args.mcp, allow_install=args.mcp_allow_install,
            force=args.force or args.update, tidy=args.tidy, each=args.each, yes=args.yes, dry=args.dry_run,
            remove=args.remove, uninstall=args.uninstall, hook=args.prompt_hook, token_hook=args.token_hooks)


if __name__ == "__main__":
    main()
