#!/usr/bin/env python3
"""Install the software-design rules into a project so every coding agent follows them.

Usage:
  python install_guardrails.py status  [--project DIR]
  python install_guardrails.py install [--project DIR] [--vendor DIR | --no-vendor]
                                       [--hook] [--also FILE ...] [--yes]
  python install_guardrails.py remove  [--project DIR] [--hook] [--yes]

install writes one marked block (assets/guardrails-block.md) into AGENTS.md,
creating it if needed, and into every other agent instruction file the project
already has unless that file just points at AGENTS.md. It copies
design_check.py into the project (default tools/) so the rules, CI and
teammates all run the same checker, and with --hook adds a git pre-commit hook
that checks staged lines. Running it again updates the block in place.

Nothing is written without --yes: without it the plan is printed (dry run).
An existing pre-commit hook that this script did not write is never replaced.
Python 3.8+, standard library only.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_FILE = os.path.join(HERE, os.pardir, "assets", "guardrails-block.md")
CHECKER = os.path.join(HERE, "design_check.py")
START = "<!-- software-design-guardrails:start -->"
END = "<!-- software-design-guardrails:end -->"
HOOK_MARK = "# software-design-guardrails pre-commit hook"
CENTRAL = "AGENTS.md"
# Agent-specific instruction files. Each gets the block only if it exists and
# does not already defer to AGENTS.md.
OTHER_FILES = [
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".windsurfrules",
    ".cursorrules",
    ".clinerules",
]


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def render_block(check_cmd):
    with open(BLOCK_FILE, encoding="utf-8") as fh:
        body = fh.read().strip().replace("{check}", check_cmd)
    return "%s\n%s\n%s" % (START, body, END)


def with_block(text, block):
    """Return text with the guardrails block inserted or replaced."""
    if text is None or not text.strip():
        return "# Project instructions for AI agents\n\n%s\n" % block
    start, end = text.find(START), text.find(END)
    if start >= 0 and end > start:
        return text[:start] + block + text[end + len(END):]
    return text.rstrip("\n") + "\n\n" + block + "\n"


def without_block(text):
    start, end = text.find(START), text.find(END)
    if start < 0 or end < start:
        return text
    before, after = text[:start].rstrip("\n"), text[end + len(END):].lstrip("\n")
    return (before + "\n\n" + after).strip("\n") + "\n" if after else before + "\n"


def targets(project, also):
    """Instruction files that should carry the block, central file first."""
    found = [CENTRAL]
    for name in OTHER_FILES:
        text = read(os.path.join(project, name))
        if text is not None and (CENTRAL not in text or START in text):
            found.append(name)
    for name in also or []:
        if name not in found:
            found.append(name)
    return found


def hooks_dir(project):
    try:
        out = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=project,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    path = out.stdout.strip()
    return path if os.path.isabs(path) else os.path.join(project, path)


def hook_script(checker_path):
    return (
        "#!/bin/sh\n"
        "%s\n"
        "# Blocks commits whose staged lines add software-design red flags (warnings).\n"
        "# Bypass once with: git commit --no-verify\n"
        "PY=$(command -v python3 || command -v python)\n"
        "[ -z \"$PY\" ] && { echo 'design-check: python not found, skipping'; exit 0; }\n"
        "exec \"$PY\" \"%s\" --staged --fail-on warning\n" % (HOOK_MARK, checker_path))


def plan(args):
    project = os.path.abspath(args.project)
    actions = []  # (description, function)
    if args.command == "install":
        if args.no_vendor:
            checker_cmd_path = CHECKER.replace(os.sep, "/")
            hook_checker = checker_cmd_path
        else:
            rel = os.path.join(args.vendor, "design_check.py").replace(os.sep, "/")
            dest = os.path.join(project, rel)
            current = read(dest)
            with open(CHECKER, encoding="utf-8") as fh:
                fresh = fh.read()
            if current != fresh:
                if current is not None and "Flag software-design red flags" not in current:
                    sys.exit("refusing to overwrite %s: it is not a copy of design_check.py" % rel)
                actions.append(("%s %s" % ("update" if current else "copy checker to", rel),
                                lambda d=dest, t=fresh: write(d, t)))
            checker_cmd_path = rel
            hook_checker = rel
        block = render_block('python %s --diff' % checker_cmd_path)
        for name in targets(project, args.also):
            path = os.path.join(project, name)
            old = read(path)
            new = with_block(old, block)
            if new != old:
                verb = "create" if old is None else ("update block in" if START in old else "add block to")
                actions.append(("%s %s" % (verb, name), lambda p=path, t=new: write(p, t)))
        if args.hook:
            actions.extend(plan_hook(project, hook_checker))
    else:  # remove
        for name in [CENTRAL] + OTHER_FILES + (args.also or []):
            path = os.path.join(project, name)
            old = read(path)
            if old and START in old:
                actions.append(("remove block from %s" % name,
                                lambda p=path, t=without_block(old): write(p, t)))
        hdir = hooks_dir(project)
        hook = os.path.join(hdir, "pre-commit") if hdir else None
        if args.hook and hook and HOOK_MARK in (read(hook) or ""):
            actions.append(("delete %s" % os.path.relpath(hook, project), lambda h=hook: os.remove(h)))
    return actions


def plan_hook(project, checker_rel):
    hdir = hooks_dir(project)
    if not hdir:
        print("note: %s is not a git repository; skipping the pre-commit hook" % project)
        return []
    hook = os.path.join(hdir, "pre-commit")
    existing = read(hook)
    script = hook_script(checker_rel)
    if existing is not None and HOOK_MARK not in existing:
        print("note: %s already exists and was not written by this script; add this line to it:\n"
              "  python %s --staged --fail-on warning || exit 1"
              % (os.path.relpath(hook, project), checker_rel))
        return []
    if existing == script:
        return []

    def install_hook():
        write(hook, script)
        os.chmod(hook, 0o755)
    return [("write %s" % os.path.relpath(hook, project), install_hook)]


def status(project):
    project = os.path.abspath(project)
    print("project: %s" % project)
    for name in [CENTRAL] + OTHER_FILES:
        text = read(os.path.join(project, name))
        if text is None:
            state = "absent"
        elif START in text:
            state = "has rules block"
        elif name != CENTRAL and CENTRAL in text:
            state = "points at AGENTS.md (reads the block there)"
        else:
            state = "no rules block"
        print("  %-34s %s" % (name, state))
    vendored = [os.path.relpath(os.path.join(root, f), project)
                for root, _, files in os.walk(project)
                if ".git" not in root.split(os.sep) and "node_modules" not in root
                for f in files if f == "design_check.py"]
    print("  checker copies: %s" % (", ".join(vendored) or "none"))
    hdir = hooks_dir(project)
    hook = read(os.path.join(hdir, "pre-commit")) if hdir else None
    print("  pre-commit hook: %s" % ("installed" if hook and HOOK_MARK in hook
                                     else "other hook present" if hook else "none"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("status", "install", "remove"))
    ap.add_argument("--project", default=".")
    ap.add_argument("--vendor", default="tools", help="folder for the checker copy (default tools)")
    ap.add_argument("--no-vendor", action="store_true",
                    help="reference this skill's checker by absolute path instead of copying it")
    ap.add_argument("--hook", action="store_true", help="also install or remove the pre-commit hook")
    ap.add_argument("--also", nargs="*", help="extra instruction files to put the block in")
    ap.add_argument("--yes", action="store_true", help="apply the plan (default: dry run)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.project):
        print("not a folder: %s" % args.project, file=sys.stderr)
        return 2
    if args.command == "status":
        status(args.project)
        return 0
    actions = plan(args)
    if not actions:
        print("nothing to do: the project is already up to date")
        return 0
    print("%s:" % ("applying" if args.yes else "plan (dry run; add --yes to apply)"))
    for desc, fn in actions:
        print("  - %s" % desc)
        if args.yes:
            fn()
    if args.yes and args.command == "install":
        print("done. Agents read the rules at session start; restart open sessions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
