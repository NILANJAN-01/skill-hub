#!/usr/bin/env python3
"""Scaffold and check a "design it twice" note before writing a module.

Usage:
  python design_note.py new "<title>" [--alternatives N] [--out FILE]
  python design_note.py check FILE [--json]

`new` prints a note with N (default 2, maximum 4) alternative designs to fill
in, or writes it to --out (never overwriting). `check` reports:
  ERROR  fewer than two alternatives; an alternative without an interface
         sketch, pros or cons; no decision, or a decision that names no
         alternative; empty interface comments; unfilled <fill: ...> markers
  WARN   alternatives whose interface sketches are nearly the same (not really
         different designs); an empty "Hides" section; unchecked red-flag items
Exit codes: 0 no errors, 1 errors, 2 usage error. Python 3.8+, standard library only.
"""
import argparse
import json
import os
import re
import sys

LETTERS = "ABCD"
FILL = "<fill: %s>"
FILL_RE = re.compile(r"<fill:[^>]*>")
RED_FLAGS = [
    "Shallow module: the interface is nearly as complex as the implementation",
    "Information leakage: a design decision is known by more than one module",
    "Temporal decomposition: modules follow execution order, not knowledge",
    "Overexposure: common use requires learning rare features",
    "Pass-through methods or variables between layers",
    "Special-general mixture: general mechanism holds special-case code",
    "Errors and special cases pushed to callers that could be defined away",
    "Hard to name or hard to describe in a short interface comment",
]


def template(title, n):
    """Return a blank design note for title with n alternatives, full of <fill: ...> markers."""
    parts = ["# Design: %s" % title, "",
             "## Problem", FILL % "what callers need, in their words; who the callers are", "",
             "## Constraints and non-goals", FILL % "limits, performance needs, what this will NOT do", ""]
    for k in range(n):
        letter = LETTERS[k]
        parts += [
            "## Alternative %s: %s" % (letter, FILL % "short name"), "",
            "### Interface sketch",
            "```",
            FILL % "the few most important signatures; must differ in shape from the other alternatives",
            "```", "",
            "### How a caller uses it",
            "```",
            FILL % "the common case in a few lines of calling code",
            "```", "",
            "### Hides", FILL % "design decisions and details callers never see", "",
            "### Pros", "- " + FILL % "pro", "",
            "### Cons", "- " + FILL % "con", ""]
    header = "| Question | " + " | ".join(LETTERS[k] for k in range(n)) + " |"
    rule = "|---|" + "---|" * n
    rows = [
        "Simplest interface for the common case?",
        "General enough for likely uses, without hurting today's use?",
        "What does it hide? What leaks to callers?",
        "Errors and special cases callers must handle",
        "Cost on the critical path",
    ]
    parts += ["## Comparison", "", header, rule]
    parts += ["| %s |" % r + " |" * n for r in rows]
    parts += ["", "## Decision",
              "Chosen: " + FILL % "letter(s), or a combination such as A+C",
              "Why: " + FILL % "the deciding trade-off", "",
              "## Interface comments (write before the code)",
              "```", FILL % "the interface comment of each public class and method", "```", "",
              "## Red-flag review",
              "Tick each item, or write `n/a: reason` after it."]
    parts += ["- [ ] %s" % flag for flag in RED_FLAGS]
    return "\n".join(parts) + "\n"


def sections(text, level):
    """Split markdown into (heading, body) for headings of exactly `level` hashes."""
    rx = re.compile(r"^%s (.+)$" % ("#" * level), re.M)
    marks = list(rx.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1).strip(), text[m.end():end]))
    return out


def content(body):
    """Body text without code fences, comments and fill markers."""
    body = FILL_RE.sub("", body)
    body = re.sub(r"```\w*", "", body)
    body = re.sub(r"^\s*[-*]\s*$", "", body, flags=re.M)
    return body.strip()


def tokens(text):
    return set(re.findall(r"[A-Za-z_]\w+", text.lower()))


def check(text):
    """Validate a design note. Returns (errors, warnings), two lists of messages; any error
    means the note is not ready to implement from."""
    errors, warns = [], []
    top = sections(text, 2)
    alts = [(h, b) for h, b in top if re.match(r"Alternative\s+\w", h)]
    if len(alts) < 2:
        errors.append("needs at least two alternatives (## Alternative A, ## Alternative B)")
    sketches = {}
    for head, body in alts:
        letter = re.match(r"Alternative\s+(\w+)", head).group(1)
        subs = {h.lower(): b for h, b in sections(body, 3)}
        for need in ("interface sketch", "pros", "cons"):
            if not content(subs.get(need, "")):
                errors.append("Alternative %s: '%s' is empty" % (letter, need))
        if not content(subs.get("hides", "")):
            warns.append("Alternative %s: 'Hides' is empty; a module that hides nothing is shallow"
                         % letter)
        sketches[letter] = tokens(content(subs.get("interface sketch", "")))
    letters = sorted(sketches)
    for i, a in enumerate(letters):
        for b in letters[i + 1:]:
            sa, sb = sketches[a], sketches[b]
            if sa and sb and len(sa & sb) / len(sa | sb) > 0.8:
                warns.append("Alternatives %s and %s have nearly the same interface; "
                             "make them genuinely different" % (a, b))
    named = {h: b for h, b in top}
    decision = content(named.get("Decision", ""))
    if not decision:
        errors.append("'Decision' is empty")
    else:
        m = re.search(r"Chosen:\s*(.+)", decision)
        chosen = m.group(1) if m else decision
        if letters and not any(re.search(r"\b%s\b" % l, chosen) for l in letters) \
                and "combination" not in chosen.lower():
            errors.append("'Decision' does not name an alternative (%s)" % ", ".join(letters))
        if not re.search(r"Why:\s*\S", decision):
            warns.append("'Decision' gives no reason (add 'Why: ...')")
    iface = next((b for h, b in top if h.lower().startswith("interface comments")), "")
    if not content(iface):
        errors.append("'Interface comments' is empty: write them before the code")
    review = next((b for h, b in top if h.lower().startswith("red-flag review")), "")
    open_items = [ln.strip() for ln in review.splitlines()
                  if ln.strip().startswith("- [ ]") and "n/a:" not in ln]
    if open_items:
        warns.append("%d red-flag item(s) not ticked or marked n/a" % len(open_items))
    for m in FILL_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        errors.append("line %d: unfilled marker %s" % (line, m.group(0)))
    return errors, warns


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("title")
    p_new.add_argument("--alternatives", type=int, default=2)
    p_new.add_argument("--out")
    p_check = sub.add_parser("check")
    p_check.add_argument("file")
    p_check.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "new":
        if not 2 <= args.alternatives <= 4:
            print("--alternatives must be 2, 3 or 4", file=sys.stderr)
            return 2
        note = template(args.title, args.alternatives)
        if not args.out:
            sys.stdout.write(note)
            return 0
        if os.path.exists(args.out):
            print("refusing to overwrite %s" % args.out, file=sys.stderr)
            return 2
        folder = os.path.dirname(args.out)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(note)
        print("wrote %s" % args.out)
        return 0

    try:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print("cannot read %s: %s" % (args.file, exc), file=sys.stderr)
        return 2
    errors, warns = check(text)
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warns}, indent=2))
    else:
        for e in errors:
            print("ERROR %s" % e)
        for w in warns:
            print("WARN  %s" % w)
        print("%d error(s), %d warning(s)" % (len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
