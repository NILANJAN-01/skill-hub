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

Standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
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

    if wanted(SUITE_TRIGGERS["tools"]):
        steps.append(Step("tools tests", ["-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"]))
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


def cmd_check(args) -> int:
    root = Path(args.root)
    changed = None
    if args.changed is not None:
        changed = changed_paths(root, args.changed)
        if changed is None:
            print(f"check: --changed needs a git work tree and a valid ref ({args.changed})", file=sys.stderr)
            return 2
    first, steps = plan_checks(root, changed, build=not args.no_build)
    start = time.time()
    if first:
        run_step(first, root)
        if first.code:
            print(f"FAIL  {first.label}  ->  {first.command}\n{_indent(failure_excerpt(first.output, args.max_lines))}")
            print("check FAILED: the build step failed, so nothing else was run.")
            return 1
    jobs = max(1, args.jobs or min(8, os.cpu_count() or 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(lambda s: run_step(s, root), steps))
    every = ([first] if first else []) + steps
    wall = time.time() - start

    scope = "everything" if changed is None else f"changes since {args.changed} ({len(changed)} paths)"
    print(f"check: {scope}, {len([s for s in every if not s.skipped])} steps, {wall:.1f}s")
    groups: dict[str, list[Step]] = {}
    for s in every:
        groups.setdefault(s.label if args.verbose else s.group, []).append(s)
    for name, members in groups.items():
        ran = [s for s in members if not s.skipped]
        bad = [s for s in ran if s.code]
        status = "FAIL" if bad else "ok" if ran else "skip"
        count = f" ({len(ran)} suites)" if len(members) > 1 else ""
        secs = max((s.seconds for s in ran), default=0.0)
        print(f"  {status:5} {name}{count}  {secs:.1f}s")
    for s in every:
        if s.skipped:
            print(f"  skip  {s.label}: {s.skipped}")
    for s in steps:
        warns = warnings_of(s) if s.label == "validate skills" else []
        if warns:
            shown = warns if args.verbose else warns[:10]
            print(f"  {len(warns)} validator warning(s):\n" + _indent("\n".join(shown)))
    failed = [s for s in every if s.code and not s.skipped]
    for s in failed:
        print(f"\nFAIL  {s.label}  (exit {s.code})  ->  {s.command}")
        print(_indent(failure_excerpt(s.output, args.max_lines)))
    if failed:
        print(f"\ncheck FAILED: {len(failed)} of {len(every)} steps.")
        return 1
    if changed is not None and len(steps) < len(plan_checks(root, None, build=False)[1]):
        print("check OK for these changes. Run `python tools/hub.py check` (no --changed) before a release.")
    else:
        print("check OK.")
    return 0


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
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return {"check": cmd_check, "new-skill": cmd_new_skill}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
