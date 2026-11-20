#!/usr/bin/env python3
"""One command per repository chore, with short output, for humans and AI agents.

    python tools/hub.py check                      everything CI runs, in parallel; prints only what failed
    python tools/hub.py check --changed [REF]      only the tests affected by changes since REF (default HEAD)
    python tools/hub.py new-skill <area>/<group>/<name> --plugin NAME [options]
                                                   scaffold a skill and register it everywhere

check runs `build_catalog.py` (regenerates the generated files) and then, in parallel:
validate_skills.py, build_catalog.py --check, compileall, the tools and MCP server tests and every
skill's scripts/test_*.py. It prints one line per step group, the output of failed steps only, and
the command to rerun each failure. Exit code 1 if any step failed.
  --no-build        verify only, write nothing (what CI does)
  --verbose         one line per step, and validator warnings in full
  --max-lines N     lines of output shown per failed step (default 40)
  --jobs N          parallel steps (default: CPU count, at most 8)

new-skill copies template/ to skills/<area>/<group>/<name>/, writes its frontmatter, adds it to the
plugin in .claude-plugin/marketplace.json (and to --also-plugin bundles), adds example prompts to
examples/prompts.json, creates the plugin and its CATEGORY_TITLES entry when --plugin-title is given,
then rebuilds the generated files. Placeholders left for you to fill start with "TODO"; the validator
fails until they are replaced.
  --title T              display title (default: from the name)
  --description D        what it does + "Use when ..." (default: a TODO placeholder)
  --license L            SPDX id or terms (default MIT)
  --prompt P             an example prompt; repeat (at least 2 needed; default: TODO placeholders)
  --also-plugin NAME     also list the skill in this bundle plugin; repeat
  --plugin-title T       create --plugin as a new plugin with this display title ...
  --plugin-description D ... and this description (required with --plugin-title)
  --no-build             do not run build_catalog.py afterwards
  --dry-run              print what would change, write nothing

    python tools/hub.py hook post-edit|stop|pre-commit
    python tools/hub.py setup-hooks [--git | --agent] [--remove] [--yes]

hook is what agent hooks and git call (the event JSON comes on stdin). post-edit rebuilds the generated
files after an edit to one of their sources and is silent unless the build fails or a generated file was
edited by hand. stop runs `check --changed` when the agent is about to finish and, if it fails, blocks
once per failing state with the short report (at most 3 times per session). pre-commit verifies the
changes without writing. setup-hooks installs the git pre-commit hook (never replacing one it did not
write) and merges the post-edit and stop hooks into the project's .claude/settings.json, keeping every
other setting; it is a dry run unless --yes. HUB_HOOKS=off disables all of them.

Standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Skill test suites that need packages outside the standard library (module names to import).
OPTIONAL_DEPS = {"image-inspector": ["PIL", "cv2"], "video-inspector": ["PIL", "cv2"]}


# ============================================================================ check
class Step:
    def __init__(self, label: str, args: list[str], group: str = ""):
        self.label, self.args, self.group = label, args, group or label
        self.code, self.output, self.seconds, self.skipped = 0, "", 0.0, ""

    @property
    def command(self) -> str:
        return "python " + " ".join(f'"{a}"' if re.search(r"[\s*?]", a) else a for a in self.args)


def _git(root: Path, *args: str) -> str | None:
    try:
        res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def changed_paths(root: Path, ref: str) -> list[str] | None:
    """Paths changed since ref (committed or not) plus untracked files; None if git or the ref fails."""
    if ref == "HEAD":  # one `git status` call instead of two (hooks run this on every stop)
        out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if out is None:
            return None
        paths, tokens, i = set(), out.split("\0"), 0
        while i < len(tokens):
            entry, i = tokens[i], i + 1
            if len(entry) < 4:
                continue
            paths.add(entry[3:])
            if entry[0] in "RC" and i < len(tokens):  # rename/copy: the next token is the old path
                paths.add(tokens[i])
                i += 1
        return sorted(paths)
    diff = _git(root, "diff", "--name-only", ref)
    if diff is None:
        return None
    untracked = _git(root, "ls-files", "--others", "--exclude-standard") or ""
    return sorted({p.strip() for p in (diff + "\n" + untracked).splitlines() if p.strip()})


def skill_test_dirs(root: Path) -> list[Path]:
    return sorted(d for d in (root / "skills").glob("*/*/*/scripts") if any(d.glob("test_*.py")))


# Which shared suites a change can affect. The tools tests read every skill, so they run for any skill change.
SUITE_TRIGGERS = {
    "tools": ("tools/", "skills/", ".claude-plugin/", "examples/", "rule/", "CHANGELOG.md", "catalog.json"),
    "mcp-server": ("mcp-server/", "catalog.json", ".claude-plugin/", "tools/hublib.py"),
    "skill-hub-mcp": ("skill-hub-mcp/", "catalog.json", ".claude-plugin/", "tools/hublib.py", "tools/install.py"),
}


def plan_checks(root: Path, changed: list[str] | None, build: bool = True) -> tuple[Step | None, list[Step]]:
    """The build step (or None) and the steps that can run in parallel after it.

    changed=None means everything; otherwise only test suites touched by those paths run.
    """
    first = Step("build generated files", ["tools/build_catalog.py"]) if build else None
    steps = [Step("validate skills", ["tools/validate_skills.py"]),
             Step("generated files up to date", ["tools/build_catalog.py", "--check"]),
             Step("byte-compile", ["-m", "compileall", "-q", "tools", "skills", "mcp-server", "skill-hub-mcp"])]

    def wanted(prefixes) -> bool:
        return changed is None or any(p.startswith(prefixes) for p in changed)

    if wanted(SUITE_TRIGGERS["tools"]):  # one step per file, so the files run in parallel
        for test in sorted((root / "tools").glob("test_*.py")):
            steps.append(Step(f"tools tests: {test.name}",
                              ["-m", "unittest", "discover", "-s", "tools", "-p", test.name], group="tools tests"))
    for suite in ("mcp-server", "skill-hub-mcp"):
        if wanted(SUITE_TRIGGERS[suite]):
            steps.append(Step(f"{suite} tests", ["-m", "unittest", "discover", "-s", f"{suite}/tests"]))
    for d in skill_test_dirs(root):
        rel = d.relative_to(root).as_posix()
        skill_rel = rel[: -len("/scripts")] + "/"
        if changed is not None and not any(p.startswith(skill_rel) for p in changed):
            continue
        step = Step(f"tests: {d.parent.name}", ["-m", "unittest", "discover", "-s", rel, "-p", "test_*.py"],
                    group="skill tests")
        missing = [m for m in OPTIONAL_DEPS.get(d.parent.name, []) if importlib.util.find_spec(m) is None]
        if missing:
            step.skipped = f"needs {', '.join(missing)} (pip install Pillow opencv-python-headless)"
        steps.append(step)
    return first, steps


def run_step(step: Step, root: Path) -> Step:
    if step.skipped:
        return step
    start = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        res = subprocess.run([sys.executable, *step.args], cwd=root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=env, timeout=900)
        step.code, step.output = res.returncode, (res.stdout + res.stderr).strip()
    except subprocess.TimeoutExpired:
        step.code, step.output = 124, "timed out after 900s"
    step.seconds = time.time() - start
    return step


def failure_excerpt(output: str, max_lines: int) -> str:
    """The useful part of a failed step's output: unittest failure blocks, ERROR lines, or the tail."""
    lines = output.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(("======", "ERROR:", "FAIL:"))), None)
    if start is None:
        errors = [l for l in lines if l.startswith("ERROR")]
        picked = errors if errors else lines
    else:
        picked = lines[start:]
    if len(picked) > max(max_lines, 5):
        head = max(max_lines, 5) - 3
        hidden = len(picked) - head - 2
        picked = picked[:head] + [f"... {hidden} more lines (rerun the command to see all) ..."] + picked[-2:]
    return "\n".join(picked)


def warnings_of(step: Step) -> list[str]:
    return [l for l in step.output.splitlines() if l.startswith("WARN")]


def run_check(root: Path, ref: str | None = None, build: bool = True, verbose: bool = False,
              max_lines: int = 40, jobs: int = 0) -> tuple[int, str]:
    """Run the checks and return (exit code, report). ref=None checks everything, else changes since ref."""
    out: list[str] = []
    changed = None
    if ref is not None:
        changed = changed_paths(root, ref)
        if changed is None:
            return 2, f"check: --changed needs a git work tree and a valid ref ({ref})"
    first, steps = plan_checks(root, changed, build=build)
    start = time.time()
    if first:
        run_step(first, root)
        if first.code:
            out.append(f"FAIL  {first.label}  ->  {first.command}")
            out.append(_indent(failure_excerpt(first.output, max_lines)))
            out.append("check FAILED: the build step failed, so nothing else was run.")
            return 1, "\n".join(out)
    workers = max(1, jobs or min(8, os.cpu_count() or 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda s: run_step(s, root), steps))
    every = ([first] if first else []) + steps
    wall = time.time() - start

    scope = "everything" if changed is None else f"changes since {ref} ({len(changed)} paths)"
    out.append(f"check: {scope}, {len([s for s in every if not s.skipped])} steps, {wall:.1f}s")
    groups: dict[str, list[Step]] = {}
    for s in every:
        groups.setdefault(s.label if verbose else s.group, []).append(s)
    for name, members in groups.items():
        ran = [s for s in members if not s.skipped]
        bad = [s for s in ran if s.code]
        status = "FAIL" if bad else "ok" if ran else "skip"
        count = f" ({len(ran)} suites)" if len(members) > 1 else ""
        secs = max((s.seconds for s in ran), default=0.0)
        out.append(f"  {status:5} {name}{count}  {secs:.1f}s")
    for s in every:
        if s.skipped:
            out.append(f"  skip  {s.label}: {s.skipped}")
    for s in steps:
        warns = warnings_of(s) if s.label == "validate skills" else []
        if warns:
            shown = warns if verbose else warns[:10]
            out.append(f"  {len(warns)} validator warning(s):")
            out.append(_indent("\n".join(shown)))
    failed = [s for s in every if s.code and not s.skipped]
    for s in failed:
        out.append(f"\nFAIL  {s.label}  (exit {s.code})  ->  {s.command}")
        out.append(_indent(failure_excerpt(s.output, max_lines)))
    if failed:
        out.append(f"\ncheck FAILED: {len(failed)} of {len(every)} steps.")
        return 1, "\n".join(out)
    if changed is not None and len(steps) < len(plan_checks(root, None, build=False)[1]):
        out.append("check OK for these changes. Run `python tools/hub.py check` (no --changed) before a release.")
    else:
        out.append("check OK.")
    return 0, "\n".join(out)


def cmd_check(args) -> int:
    code, report = run_check(Path(args.root), args.changed, not args.no_build, args.verbose, args.max_lines,
                             args.jobs)
    print(report, file=sys.stderr if code == 2 else sys.stdout)
    return code


def _indent(text: str) -> str:
    return "\n".join("    " + l for l in text.splitlines())


# ======================================================================== new-skill
def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _areas(root: Path) -> list[str]:
    text = (root / "tools" / "hublib.py").read_text(encoding="utf-8")
    block = re.search(r"^AREAS = \{(.*?)^\}", text, re.S | re.M)
    return re.findall(r'^\s*"([a-z0-9-]+)"\s*:', block.group(1), re.M) if block else []


def _titleize(name: str) -> str:
    return name.replace("-", " ").capitalize()


def skill_frontmatter(name: str, description: str, license_: str, title: str, plugin: str) -> str:
    return (f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n"
            f"license: {license_}\nmetadata:\n  title: {json.dumps(title, ensure_ascii=False)}\n"
            f"  category: {plugin}\n---\n")


def add_category_title(text: str, plugin: str, title: str) -> str:
    """Insert `"plugin": "title",` into CATEGORY_TITLES, before the git-* family entries (or at the end)."""
    m = re.search(r"^CATEGORY_TITLES = \{\n(.*?)^\}", text, re.S | re.M)
    if not m:
        raise ValueError("CATEGORY_TITLES not found in tools/build_catalog.py")
    if re.search(rf'^\s*"{re.escape(plugin)}"\s*:', m.group(1), re.M):
        return text
    line = f"    {json.dumps(plugin)}: {json.dumps(title, ensure_ascii=False)},\n"
    body = m.group(1)
    git = re.search(r'^\s*"git-', body, re.M)
    pos = m.start(1) + (git.start() if git else len(body))
    return text[:pos] + line + text[pos:]


def cmd_new_skill(args) -> int:
    root = Path(args.root)
    parts = args.path.strip("/").split("/")
    if parts[0] == "skills":
        parts = parts[1:]
    if len(parts) != 3:
        return _fail("path must be <area>/<group>/<name>, for example development/code-quality/lint-checker")
    area, group, name = parts
    areas = _areas(root)
    if area not in areas:
        return _fail(f"unknown area {area!r}; areas are {', '.join(areas)} (AREAS in tools/hublib.py)")
    for part in (group, name):
        if not NAME_RE.match(part) or len(part) > 64:
            return _fail(f"{part!r} must be lowercase letters, digits and single hyphens (max 64)")
    existing = {p.parent.name: p.parent for p in (root / "skills").glob("*/*/*/SKILL.md")}
    if name in existing:
        return _fail(f"a skill named {name!r} already exists at {existing[name].relative_to(root).as_posix()}")

    market_path = root / ".claude-plugin" / "marketplace.json"
    prompts_path = root / "examples" / "prompts.json"
    titles_path = root / "tools" / "build_catalog.py"
    market = _load_json(market_path)
    plugins = {p["name"]: p for p in market.get("plugins", [])}
    new_plugin = args.plugin not in plugins
    if new_plugin and not args.plugin_title:
        close = difflib.get_close_matches(args.plugin, list(plugins), n=3, cutoff=0.4)
        hint = f" Did you mean {', '.join(close)}?" if close else ""
        return _fail(f"no plugin {args.plugin!r} in marketplace.json.{hint} To create it, add "
                     "--plugin-title and --plugin-description.")
    if new_plugin and (not args.plugin_description or not NAME_RE.match(args.plugin)):
        return _fail("a new plugin needs a kebab-case --plugin name and a --plugin-description")
    for extra in args.also_plugin:
        if extra not in plugins:
            return _fail(f"no plugin {extra!r} in marketplace.json (for --also-plugin)")

    title = args.title or _titleize(name)
    description = args.description or (f"TODO: what {name} does, in the words users type. "
                                       "Use when <tasks, keywords, commands, error messages>.")
    prompts = args.prompt or [f"TODO: a realistic request that should use {name}",
                              f"TODO: a second, differently worded request for {name}"]
    rel = f"skills/{area}/{group}/{name}"
    dest = root / rel

    plan = [f"create {rel}/ from template/ (SKILL.md, references/)",
            f"add ./{rel} to plugin {args.plugin}" + (" (new plugin)" if new_plugin else "")]
    plan += [f"add ./{rel} to plugin {p}" for p in args.also_plugin]
    if new_plugin:
        plan.append(f"add {args.plugin!r}: {args.plugin_title!r} to CATEGORY_TITLES in tools/build_catalog.py")
    plan.append(f"add {len(prompts)} example prompts to examples/prompts.json")
    if not (args.no_build or args.dry_run):
        plan.append("rebuild the generated files (tools/build_catalog.py)")
    if args.dry_run:
        print("new-skill (dry run, nothing written):\n" + "\n".join("  - " + p for p in plan))
        return 0

    shutil.copytree(root / "template", dest)
    md = dest / "SKILL.md"
    body = re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", md.read_text(encoding="utf-8"), count=1, flags=re.S)
    body = body.replace("# Template Skill", f"# {title}", 1)
    md.write_text(skill_frontmatter(name, description, args.license, title, args.plugin) + body,
                  encoding="utf-8", newline="\n")

    entry = f"./{rel}"
    if new_plugin:
        market.setdefault("plugins", []).append({"name": args.plugin, "description": args.plugin_description,
                                                 "source": "./", "strict": False, "category": args.plugin,
                                                 "skills": [entry]})
        titles_path.write_text(add_category_title(titles_path.read_text(encoding="utf-8"), args.plugin,
                                                  args.plugin_title), encoding="utf-8", newline="\n")
    else:
        plugins[args.plugin].setdefault("skills", []).append(entry)
    for extra in args.also_plugin:
        plugins[extra].setdefault("skills", []).append(entry)
    _dump_json(market_path, market)
    examples = _load_json(prompts_path)
    examples[name] = prompts
    _dump_json(prompts_path, examples)

    print("new-skill:\n" + "\n".join("  - " + p for p in plan))
    if not args.no_build:
        res = subprocess.run([sys.executable, "tools/build_catalog.py"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        if res.returncode:
            print("build_catalog.py failed:\n" + _indent(res.stdout + res.stderr))
            return 1
    todo = [w for w, v in (("the description", not args.description), ("the example prompts", not args.prompt)) if v]
    print("\nNext:")
    step = 1
    if todo:
        print(f"  {step}. Replace the TODO placeholders in {' and '.join(todo)}.")
        step += 1
    print(f"  {step}. Write the body of {rel}/SKILL.md (it still has template text) and its references/ "
          "(delete references/details.md if unused).")
    print(f"  {step + 1}. python tools/hub.py check --changed")
    return 0


def _fail(msg: str) -> int:
    print(f"new-skill: {msg}", file=sys.stderr)
    return 2


# ============================================================================ hooks
# Generated outputs (rule 01). The rebuild replaces any edit to them, so the agent is told.
GENERATED_FILES = {"catalog.json", "skills/README.md", "examples/PROMPTS.md", "prompts.html", "user-guide.html"}
# What build_catalog.py reads: editing any of these makes the generated files stale.
BUILD_SOURCES = ("skills/", "template/", ".claude-plugin/", "examples/prompts.json", "tools/build_catalog.py",
                 "tools/hublib.py", "tools/install.py", "tools/prompts_template.html",
                 "tools/user_guide_template.html", "rule/", "CHANGELOG.md", "mcp-server/", "skill-hub-mcp/")
MAX_STOP_BLOCKS = 3          # per session; each distinct failing state blocks at most once
HOOKS_OFF_ENV = "HUB_HOOKS"  # HUB_HOOKS=off disables every hook
PRE_COMMIT_MARK = "# skill-hub: tools/hub.py pre-commit hook"


def hooks_off() -> bool:
    return os.environ.get(HOOKS_OFF_ENV, "").strip().lower() in ("off", "0", "false", "no")


def _hook_input() -> dict:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_build(root: Path) -> tuple[int, str]:
    res = subprocess.run([sys.executable, "tools/build_catalog.py"], cwd=root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=300)
    return res.returncode, (res.stdout + res.stderr).strip()


def edited_path(root: Path, data: dict) -> str | None:
    """The edited file from a post-edit hook payload, relative to root ('/'-separated), or None."""
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    response = data.get("tool_response") if isinstance(data.get("tool_response"), dict) else {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or response.get("filePath")
    if not raw or not isinstance(raw, str):
        return None
    msys = re.match(r"^/([a-zA-Z])/", raw)
    if os.name == "nt" and msys:  # Git Bash / MSYS style: /c/Users/... is C:/Users/...
        raw = f"{msys.group(1)}:/{raw[3:]}"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(data.get("cwd") or root) / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def hook_post_edit(root: Path, data: dict) -> int:
    """Rebuild the generated files after an edit to one of their sources. Silent unless something is wrong."""
    rel = edited_path(root, data)
    if rel is None or "__pycache__" in rel:
        return 0
    generated = rel in GENERATED_FILES
    if not generated and not rel.startswith(BUILD_SOURCES):
        return 0
    code, output = _run_build(root)
    if code:
        print(f"tools/build_catalog.py failed after the edit to {rel}:\n{_indent(failure_excerpt(output, 30))}",
              file=sys.stderr)
        return 2
    if generated:
        print(f"{rel} is a generated file (rule/01-generated-files.md): the rebuild replaced your edit. "
              "Change its sources instead (rule/02-sources-of-truth.md); the files are rebuilt automatically.",
              file=sys.stderr)
        return 2
    return 0


def _fingerprint(root: Path, changed: list[str], head: str) -> str:
    """Identifies the current state of the changes: HEAD plus size and mtime of every changed path."""
    digest = hashlib.sha256(head.encode())
    for rel in changed:
        try:
            st = (root / rel).stat()
            digest.update(f"{rel}:{st.st_size}:{st.st_mtime_ns}\n".encode())
        except OSError:
            digest.update(f"{rel}:gone\n".encode())
    return digest.hexdigest()


def _repo_info(root: Path) -> tuple[Path | None, str]:
    """(hook state file inside .git, HEAD commit) with one git call ('' for HEAD in a repo with no commits)."""
    out = _git(root, "rev-parse", "--absolute-git-dir", "HEAD")
    if out is None:
        out = (_git(root, "rev-parse", "--absolute-git-dir") or "") + "\n"
    lines = out.splitlines()
    state = Path(lines[0].strip()) / "hub-hook-state.json" if lines and lines[0].strip() else None
    return state, (lines[1].strip() if len(lines) > 1 else "")


def hook_stop(root: Path, data: dict) -> int:
    """Before the agent finishes: run `check --changed`; if it fails, block once per failing state with the report.

    A state that passed, or that already blocked once, is not checked again, so an agent that has
    explained an intended failure (work in progress) can stop, and repeated stops cost nothing.
    """
    changed = changed_paths(root, "HEAD")
    if not changed:
        return 0
    state_file, head = _repo_info(root)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file and state_file.exists() else {}
    except (ValueError, OSError):
        state = {}
    sessions = state.setdefault("sessions", {})
    session = sessions.setdefault(str(data.get("session_id") or "default"), [])
    before = _fingerprint(root, changed, head)
    if before == state.get("passed") or before in session:
        return 0
    code, report = run_check(root, "HEAD", max_lines=25)
    after = _fingerprint(root, changed_paths(root, "HEAD") or [], head)  # the build may have rewritten files
    message = None
    if code == 0:
        state["passed"] = after
    elif code == 1:
        if len(session) >= MAX_STOP_BLOCKS:
            message = {"systemMessage": f"hub.py check still fails after {MAX_STOP_BLOCKS} attempts in this "
                                        "session; stopping anyway. Run: python tools/hub.py check --changed"}
        else:
            session.append(after)
            message = {"decision": "block", "reason": (
                "`python tools/hub.py check --changed` fails on the current changes. Fix the failures below "
                "before finishing. If they are intended (for example work in progress), say so to the user "
                "and stop again; the same state does not block twice.\n\n" + report)}
    if state_file:
        for old in list(sessions)[:-20]:
            del sessions[old]
        try:
            state_file.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            pass
    if message:
        print(json.dumps(message))
    return 0


def hook_pre_commit(root: Path) -> int:
    """git pre-commit: verify (without writing) that the working tree passes `check --changed`."""
    code, report = run_check(root, "HEAD", build=False)
    if code == 1:
        print(report + "\n\nCommit blocked by the skill-hub pre-commit hook. Fix the failures (stale generated "
              "files: run python tools/build_catalog.py and stage them). Skip once with HUB_HOOKS=off.",
              file=sys.stderr)
        return 1
    return 0


def cmd_hook(args) -> int:
    if hooks_off():
        return 0
    root = Path(args.root)
    try:
        if args.event == "pre-commit":
            return hook_pre_commit(root)
        data = _hook_input()
        return hook_post_edit(root, data) if args.event == "post-edit" else hook_stop(root, data)
    except Exception as e:  # a hook must never break the agent or the commit because of a bug in the hook
        print(f"hub.py hook {args.event}: internal error ignored ({type(e).__name__}: {e})", file=sys.stderr)
        return 0


def pre_commit_script(python: str) -> str:
    return (f"#!/bin/sh\n{PRE_COMMIT_MARK}\n# Remove with: python tools/hub.py setup-hooks --remove --yes\n"
            f'exec "{python}" tools/hub.py hook pre-commit\n')


def setup_git_hook(root: Path, remove: bool, yes: bool) -> int:
    """Install (or remove) the git pre-commit hook. Never replaces a hook it did not write."""
    hooks_dir = _git(root, "rev-parse", "--git-path", "hooks")
    if not hooks_dir:
        print("git hook: not a git work tree", file=sys.stderr)
        return 2
    target = Path(hooks_dir.strip())
    target = (target if target.is_absolute() else root / target) / "pre-commit"
    ours = target.exists() and PRE_COMMIT_MARK in target.read_text(encoding="utf-8", errors="replace")
    if target.exists() and not ours:
        print(f"git hook: {target} exists and was not written by hub.py; leaving it alone. Add this line to it "
              "instead:\n    python tools/hub.py hook pre-commit || exit 1")
        return 1
    if remove:
        if not ours:
            print("git hook: none from hub.py to remove.")
        elif not yes:
            print(f"git hook (dry run): would delete {target}.")
        else:
            target.unlink()
            print(f"git hook: removed {target}")
        return 0
    script = pre_commit_script(Path(sys.executable).as_posix())
    if ours and target.read_text(encoding="utf-8") == script:
        print(f"git hook: {target} is up to date.")
        return 0
    if not yes:
        print(f"git hook (dry run): would {'update' if ours else 'write'} {target}:\n{_indent(script)}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8", newline="\n")
    target.chmod(0o755)
    print(f"git hook: wrote {target}. Commits now run `hub.py check --changed --no-build` first.")
    return 0


# Project agent settings that wire the hooks in (the format agents with Claude-style hooks read).
AGENT_SETTINGS = Path(".claude") / "settings.json"
AGENT_HOOKS = {  # event: (matcher, hub.py hook event, timeout seconds, status message)
    "PostToolUse": ("Edit|Write|MultiEdit|NotebookEdit", "post-edit", 120, None),
    "Stop": (None, "stop", 600, "hub.py check --changed"),
}
OUR_COMMAND = re.compile(r"tools/hub\.py\"? hook ")


def agent_hook_command(event: str) -> str:
    # python3 where it works (macOS, Linux), else python (Windows); $CLAUDE_PROJECT_DIR is the repo root.
    return f'PY=python3; "$PY" -c "" 2>/dev/null || PY=python; "$PY" "$CLAUDE_PROJECT_DIR/tools/hub.py" hook {event}'


def merged_agent_settings(existing: dict, remove: bool = False) -> dict:
    """existing settings with hub.py's hooks added (or removed); every other setting and hook is kept."""
    data = json.loads(json.dumps(existing))
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    for event, (matcher, name, timeout, status) in AGENT_HOOKS.items():
        groups = []
        for group in hooks.get(event, []) if isinstance(hooks.get(event), list) else []:
            if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                group = dict(group, hooks=[h for h in group["hooks"]
                                           if not OUR_COMMAND.search(str(h.get("command", "")))])
                if not group["hooks"]:
                    continue
            groups.append(group)
        if not remove:
            entry = {"type": "command", "command": agent_hook_command(name), "timeout": timeout}
            if status:
                entry["statusMessage"] = status
            ours = {"matcher": matcher} if matcher else {}
            ours["hooks"] = [entry]
            groups.append(ours)
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    return data


def setup_agent_hooks(root: Path, remove: bool, yes: bool) -> int:
    path = root / AGENT_SETTINGS
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError as e:
        print(f"agent hooks: {AGENT_SETTINGS.as_posix()} is not valid JSON ({e}); fix it first.", file=sys.stderr)
        return 1
    if not isinstance(existing, dict):
        print(f"agent hooks: {AGENT_SETTINGS.as_posix()} is not a JSON object; fix it first.", file=sys.stderr)
        return 1
    new = merged_agent_settings(existing, remove)
    rel = AGENT_SETTINGS.as_posix()
    if new == existing:
        print(f"agent hooks: {rel} is up to date.")
        return 0
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    if not yes:
        print(f"agent hooks (dry run): would {'update' if path.exists() else 'create'} {rel}, keeping its other "
              f"settings:\n{_indent(json.dumps(new.get('hooks', {}), indent=2))}")
        return 0
    if remove and not new and path.exists():
        path.unlink()
        print(f"agent hooks: removed {rel} (it held only hub.py's hooks)")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"agent hooks: {'removed hub.py hooks from' if remove else 'wrote'} {rel}. Restart the agent session "
          "(or reload its hooks) to pick the change up.")
    return 0


def cmd_setup_hooks(args) -> int:
    """Install or remove the git pre-commit hook and the agent hooks. Dry run unless --yes."""
    root = Path(args.root)
    both = not (args.git or args.agent)
    codes = []
    if args.git or both:
        codes.append(setup_git_hook(root, args.remove, args.yes))
    if args.agent or both:
        codes.append(setup_agent_hooks(root, args.remove, args.yes))
    if not args.yes:
        print("Nothing was written. Add --yes to apply.")
    return max(codes)


# ============================================================================== CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="hub.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="run every CI check in parallel; print only failures")
    c.add_argument("--changed", nargs="?", const="HEAD", default=None, metavar="REF",
                   help="only tests affected by changes since REF (default HEAD), plus untracked files")
    c.add_argument("--no-build", action="store_true", help="verify only; do not regenerate files")
    c.add_argument("--verbose", action="store_true", help="one line per step and every validator warning")
    c.add_argument("--max-lines", type=int, default=40, help="output lines shown per failed step")
    c.add_argument("--jobs", type=int, default=0, help="parallel steps (default: CPUs, max 8)")

    n = sub.add_parser("new-skill", help="scaffold a skill and register it")
    n.add_argument("path", help="<area>/<group>/<name>")
    n.add_argument("--plugin", required=True, help="plugin (category) that lists the skill")
    n.add_argument("--title")
    n.add_argument("--description")
    n.add_argument("--license", default="MIT")
    n.add_argument("--prompt", action="append", default=[])
    n.add_argument("--also-plugin", action="append", default=[])
    n.add_argument("--plugin-title")
    n.add_argument("--plugin-description")
    n.add_argument("--no-build", action="store_true")
    n.add_argument("--dry-run", action="store_true")

    h = sub.add_parser("hook", help="handlers called by agent hooks and git (read the event JSON on stdin)")
    h.add_argument("event", choices=["post-edit", "stop", "pre-commit"])

    s = sub.add_parser("setup-hooks", help="install the git pre-commit hook and the agent hooks (dry run unless --yes)")
    s.add_argument("--git", action="store_true", help="only the git pre-commit hook")
    s.add_argument("--agent", action="store_true", help=f"only the agent hooks in {AGENT_SETTINGS.as_posix()}")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--yes", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return {"check": cmd_check, "new-skill": cmd_new_skill, "hook": cmd_hook,
            "setup-hooks": cmd_setup_hooks}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
