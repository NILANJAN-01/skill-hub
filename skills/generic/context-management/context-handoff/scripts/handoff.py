#!/usr/bin/env python3
"""Draft and check session handoff notes and sub-task briefs for AI agents.

Usage:
  python handoff.py draft [--root DIR] [--goal TEXT] [--out FILE]
  python handoff.py check NOTE.md [--kind handoff|brief] [--root DIR] [--max-tokens N] [--json]

`draft` reads git state (branch, changed files, recent commits, new TODOs)
and prints a handoff note with the facts filled in and `<fill: ...>` markers
for what only the agent knows. It writes a file only with --out, and never
overwrites one. `check` is read-only: it reports missing sections, unfilled
markers, words that only make sense with the old history, relative dates,
missing files and secrets. Exit code 1 when there are errors.
Python 3.8+, standard library only. Token counts are estimates (chars / 4).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

# Section name -> words that count as that section in a heading or "Name:" line.
SECTIONS = {
    "goal": ["goal", "objective", "task", "aim"],
    "done": ["done", "state", "status", "progress", "completed", "current state"],
    "decisions": ["decisions", "decision", "decided", "choices"],
    "next": ["next", "next step", "next steps", "todo next", "remaining"],
    "open": ["open questions", "questions", "open", "unknowns", "blockers", "risks"],
    "files": ["files", "key files", "where", "locations"],
    "verify": ["verify", "how to verify", "checks", "test", "tests", "done when", "definition of done"],
    "context": ["context", "background"],
    "constraints": ["constraints", "rules", "limits", "do not", "don't"],
    "return": ["return", "output", "deliverable", "report back", "reply with"],
}
KINDS = {
    "handoff": {"required": ["goal", "done", "next"], "recommended": ["decisions", "open", "files", "verify"]},
    "brief": {"required": ["goal", "context", "verify", "return"], "recommended": ["constraints", "files"]},
}
# Phrases that point at a history the next reader does not have.
DANGLING = [
    r"as discussed", r"as (?:mentioned|said|noted) (?:above|before|earlier)", r"see above",
    r"the same as before", r"like before", r"we talked about", r"you know", r"the earlier (?:fix|idea|plan|approach)",
    r"the previous (?:approach|attempt|fix|plan|version)", r"that (?:bug|issue|error|file) (?:again|from before)",
    r"the thing", r"continue from where", r"as before",
]
RELATIVE_TIME = [r"\byesterday\b", r"\btomorrow\b", r"\blast (?:week|night|time)\b", r"\bnext week\b",
                 r"\bthis (?:morning|afternoon|week)\b", r"\bearlier today\b", r"\ba few (?:minutes|hours) ago\b"]
PLACEHOLDER = re.compile(r"<fill:[^>]*>|\bTBD\b|\?\?\?|^\s*\.\.\.\s*$", re.M)
SECRET = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|"
    r"xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?i:(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"<>]{8,}))")
PATH_RE = re.compile(r"`([^`\s]+\.[A-Za-z0-9]{1,8})(?::\d+)?`")
HEAD_RE = re.compile(r"^\s*(?:#{1,6}\s*(.+?)\s*#*\s*$|(?:[-*]\s*)?\*{0,2}([A-Za-z][A-Za-z '/]{1,30}?)\*{0,2}\s*:(.*)$)")


def tokens(text):
    return (len(text) + 3) // 4


def section_of(label):
    label = re.sub(r"[^a-z' /]", "", label.lower()).strip()
    label = re.sub(r"\s*\(.*$", "", label)
    for key, words in SECTIONS.items():
        if label in words:
            return key
    for key, words in SECTIONS.items():
        if any(label.startswith(w + " ") for w in words):
            return key
    return None


def split_sections(text):
    """Return {section: body} for every recognised heading or 'Name:' line."""
    found, current, lines = {}, None, []

    def flush():
        if current is not None:
            found[current] = (found.get(current, "") + "\n" + "\n".join(lines)).strip()

    for line in text.splitlines():
        m = HEAD_RE.match(line)
        key = None
        inline = ""
        if m:
            label = m.group(1) or m.group(2) or ""
            key = section_of(label)
            inline = (m.group(3) or "").strip() if m.group(2) else ""
        if key:
            flush()
            current, lines = key, ([inline] if inline else [])
        elif current is not None:
            lines.append(line)
    flush()
    return found


def check_text(text, kind="handoff", root=None, max_tokens=800):
    errors, warnings = [], []
    sections = split_sections(text)
    spec = KINDS[kind]
    for key in spec["required"]:
        if key not in sections:
            errors.append("missing required section: %s" % key)
        elif not re.sub(r"[\s\-*>]", "", sections[key]):
            errors.append("section is empty: %s" % key)
    for key in spec["recommended"]:
        if key == "files" and PATH_RE.search(text):
            continue  # files are already named in another section
        if key not in sections:
            warnings.append("missing recommended section: %s" % key)
    for m in PLACEHOLDER.finditer(text):
        warnings.append("unfilled placeholder: %r (line %d)" % (m.group(0).strip(), text[:m.start()].count("\n") + 1))
    low = text.lower()
    for pat in DANGLING:
        for m in re.finditer(pat, low):
            warnings.append("refers to history the reader does not have: %r (line %d); say it explicitly"
                            % (m.group(0), low[:m.start()].count("\n") + 1))
    for pat in RELATIVE_TIME:
        for m in re.finditer(pat, low):
            warnings.append("relative time %r (line %d); write an absolute date"
                            % (m.group(0), low[:m.start()].count("\n") + 1))
    if SECRET.search(text):
        errors.append("looks like it contains a secret (key, token or password); remove it")
    missing = []
    if root:
        for p in sorted(set(PATH_RE.findall(text))):
            if "://" in p or p.startswith("<"):
                continue
            if not os.path.exists(os.path.join(root, p)):
                missing.append(p)
        for p in missing:
            warnings.append("file not found under root: %s" % p)
    t = tokens(text)
    if t > max_tokens:
        warnings.append("note is about %d tokens (limit %d); keep facts, drop narrative" % (t, max_tokens))
    return {"kind": kind, "tokens": t, "sections": sorted(sections), "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------- draft
def git(root, *args):
    try:
        out = subprocess.run(["git"] + list(args), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.rstrip("\n") if out.returncode == 0 else None


def git_facts(root, max_files=25):
    if git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    facts = {"branch": git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?",
             "head": git(root, "log", "-1", "--format=%h %s") or "(no commits yet)",
             "commits": [], "changed": [], "todos": [], "diffstat": ""}
    log = git(root, "log", "-5", "--format=%h %s")
    facts["commits"] = log.splitlines() if log else []
    status = git(root, "status", "--porcelain", "--untracked-files=all") or ""
    for line in status.splitlines():
        code, path = line[:2].strip() or "?", line[3:]
        facts["changed"].append("%s %s" % (code, path))
    facts["changed_total"] = len(facts["changed"])
    facts["changed"] = facts["changed"][:max_files]
    facts["diffstat"] = (git(root, "diff", "--shortstat", "HEAD") or "").strip()
    diff = git(root, "diff", "-U0", "HEAD") or ""
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and current and re.search(r"\b(TODO|FIXME|XXX|HACK)\b", line):
            facts["todos"].append("%s: %s" % (current, line[1:].strip()[:120]))
    facts["todos"] = facts["todos"][:15]
    return facts


def draft(root, goal=None, today=None):
    today = today or datetime.date.today().isoformat()
    facts = git_facts(root)
    out = ["# Handoff (%s)" % today, "",
           "## Goal", goal or "<fill: the outcome the user asked for, in one or two sentences>", "",
           "## Done", "<fill: what is finished and verified; name files and functions>"]
    if facts:
        out += ["", "Repository state (from git):",
                "- Branch `%s`, HEAD `%s`" % (facts["branch"], facts["head"])]
        if facts["diffstat"]:
            out.append("- Uncommitted: %s" % facts["diffstat"])
        if facts["changed"]:
            more = facts["changed_total"] - len(facts["changed"])
            out.append("- Changed files: " + ", ".join("`%s`" % c.split(" ", 1)[1] for c in facts["changed"])
                       + (" (+%d more)" % more if more > 0 else ""))
        if facts["commits"]:
            out.append("- Recent commits: " + "; ".join(facts["commits"]))
    else:
        out += ["", "(No git repository found: list changed files by hand.)"]
    out += ["", "## Decisions", "<fill: each choice made and why, and options rejected so they are not retried>",
            "", "## Next step", "<fill: the single next action, concrete enough to start without asking>",
            "", "## Open questions", "<fill: what is unknown or waiting on the user; write 'None' if nothing>"]
    if facts and facts["todos"]:
        out += ["", "New TODO/FIXME lines in the working tree:"] + ["- %s" % t for t in facts["todos"]]
    out += ["", "## Verify", "<fill: the command(s) that prove the work is correct, and their current result>", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("draft", help="print a handoff note pre-filled from git state")
    d.add_argument("--root", default=".")
    d.add_argument("--goal")
    d.add_argument("--out", help="write the note to this file (refuses to overwrite)")
    c = sub.add_parser("check", help="check a handoff note or sub-task brief")
    c.add_argument("note")
    c.add_argument("--kind", choices=sorted(KINDS), default="handoff")
    c.add_argument("--root", help="project folder, to check that named files exist")
    c.add_argument("--max-tokens", type=int, default=800)
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "draft":
        text = draft(a.root, a.goal)
        if a.out:
            if os.path.exists(a.out):
                print("refusing to overwrite %s" % a.out, file=sys.stderr)
                return 2
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("wrote %s (%d tokens). Fill every <fill: ...> marker, then run check." % (a.out, tokens(text)))
        else:
            print(text)
        return 0
    if a.cmd == "check":
        try:
            with open(a.note, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            print("cannot read %s: %s" % (a.note, e), file=sys.stderr)
            return 2
        r = check_text(text, a.kind, a.root, a.max_tokens)
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            print("%s check: %s (~%d tokens, sections: %s)" % (r["kind"], a.note, r["tokens"],
                                                                ", ".join(r["sections"]) or "none"))
            for e in r["errors"]:
                print("  ERROR  " + e)
            for w in r["warnings"]:
                print("  WARN   " + w)
            if not r["errors"] and not r["warnings"]:
                print("  OK: a fresh session can start from this note")
        return 1 if r["errors"] else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
