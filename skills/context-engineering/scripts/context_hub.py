#!/usr/bin/env python3
"""Centralize project context: one source file, thin pointers for every agent.

Usage:
  python context_hub.py check <project-dir> [--json]
  python context_hub.py sync  <project-dir> [--write]

`check` is read-only. `sync` is a dry run unless --write is given, and it
never overwrites an existing file. Python 3.8+, standard library only.
"""
import argparse
import json
import os
import sys

CENTRAL = "AGENTS.md"
# Agent-specific instruction files that should only point at the central file.
POINTERS = [
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".windsurfrules",
    ".cursorrules",
]
POINTER_TEXT = (
    "# Project context\n\n"
    "The single source of project context is `AGENTS.md`. Read it first.\n"
    "Do not add rules here: edit `AGENTS.md` so every tool sees the same context.\n"
)
POINTER_MAX_CHARS = 600  # longer than this is a copy, not a pointer
CENTRAL_WARN_TOKENS = 2000  # always-loaded text should stay short


def tokens(text):
    return (len(text) + 3) // 4


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def classify(root):
    central_text = read(os.path.join(root, CENTRAL))
    central_lines = set()
    if central_text:
        central_lines = {l.strip() for l in central_text.splitlines() if len(l.strip()) > 25}
    report = {"central": None, "pointers": [], "warnings": [], "always_loaded_tokens": 0}
    total = 0
    if central_text is None:
        report["warnings"].append("%s is missing: create it as the single source of context" % CENTRAL)
    else:
        t = tokens(central_text)
        total += t
        report["central"] = {"path": CENTRAL, "tokens": t}
        if t > CENTRAL_WARN_TOKENS:
            report["warnings"].append(
                "%s is ~%d tokens, sent on every request: move details to linked files" % (CENTRAL, t))
    for rel in POINTERS:
        text = read(os.path.join(root, *rel.split("/")))
        if text is None:
            report["pointers"].append({"path": rel, "state": "missing", "tokens": 0})
            continue
        t = tokens(text)
        total += t
        mentions = CENTRAL in text or "@" + CENTRAL in text
        dup = sum(1 for l in text.splitlines() if l.strip() in central_lines)
        if len(text) <= POINTER_MAX_CHARS and mentions:
            state = "pointer"
        elif dup:
            state = "duplicate"
            report["warnings"].append(
                "%s repeats %d line(s) of %s: replace with a pointer" % (rel, dup, CENTRAL))
        else:
            state = "divergent"
            report["warnings"].append(
                "%s holds its own rules: merge them into %s, then replace with a pointer" % (rel, CENTRAL))
        report["pointers"].append({"path": rel, "state": state, "tokens": t})
    report["always_loaded_tokens"] = total
    return report


def cmd_check(args):
    report = classify(args.dir)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    c = report["central"]
    print("central: %s" % (("%s (~%d tokens)" % (c["path"], c["tokens"])) if c else "MISSING"))
    for p in report["pointers"]:
        print("  %-34s %-9s ~%d tokens" % (p["path"], p["state"], p["tokens"]))
    print("always-loaded total: ~%d tokens (estimate)" % report["always_loaded_tokens"])
    for w in report["warnings"]:
        print("WARN: " + w)
    return 1 if report["warnings"] else 0


def cmd_sync(args):
    root = args.dir
    if read(os.path.join(root, CENTRAL)) is None:
        print("ERROR: %s not found in %s. Create it first." % (CENTRAL, root))
        return 2
    planned = []
    for rel in POINTERS:
        path = os.path.join(root, *rel.split("/"))
        if os.path.exists(path):
            print("skip   %s (exists; not overwritten)" % rel)
        else:
            planned.append((rel, path))
            print("%s %s" % ("create" if args.write else "would create", rel))
    if args.write:
        for rel, path in planned:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(POINTER_TEXT)
    elif planned:
        print("Dry run. Re-run with --write to create these files.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report central/pointer state and drift (read-only)")
    c.add_argument("dir")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)
    s = sub.add_parser("sync", help="create missing pointer files (dry run by default)")
    s.add_argument("dir")
    s.add_argument("--write", action="store_true")
    s.set_defaults(fn=cmd_sync)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
