#!/usr/bin/env python3
"""Repo learnings: plan a complete read of a repository and check that the notes cover it.

The script does the bookkeeping, the reader does the reading:

    scan      read the repository's structure (folder or git URL): list every file, decide what is
              worth reading, order and batch the files, and write reading-plan.md, manifest.json,
              model.json and a LEARNINGS.md skeleton that already holds the facts, the commands, a
              Mermaid high-level design, code-flow diagrams and a scored health audit
    next      print the next batch that has no notes yet
    batch N   print one batch
    assemble  copy the per-batch notes into the appendix of LEARNINGS.md
    coverage  report files the notes do not mention and sections still unfinished

Python 3.8+, standard library only. It never runs code from the repository.

    python repo_learnings.py scan path/to/repo
    python repo_learnings.py scan https://github.com/owner/project.git
    python repo_learnings.py next repo-learnings/project
    python repo_learnings.py coverage repo-learnings/project
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_model as rm  # noqa: E402

MANIFEST, MODEL, PLAN, LEARNINGS, NOTES_DIR = "manifest.json", "model.json", "reading-plan.md", "LEARNINGS.md", "notes"
TODO = "TODO(learnings)"
NOTES_START, NOTES_END = "<!-- file-notes:start -->", "<!-- file-notes:end -->"
DOC_NAMES = ("readme", "contributing", "architecture", "agents", "claude", "design", "overview", "guide",
             "changelog", "security", "code_of_conduct", "license", "notice")
ENTRY_STEMS = {"main", "index", "app", "cli", "__main__", "manage", "server", "program", "application", "bootstrap",
               "run", "start", "wsgi", "asgi", "mainactivity", "lib", "mod"}


# ---------------------------------------------------------------------------- plan

def reading_priority(f, entry_files):
    """Lower comes first: README, root docs, build files, docs, entry points, source, tests, the rest."""
    rel = f["path"]
    parts = rel.split("/")
    name = parts[-1].lower()
    stem = name.split(".", 1)[0]
    if len(parts) == 1 and stem == "readme":
        return 0
    if len(parts) == 1 and stem in DOC_NAMES:
        return 1
    if f.get("role") == "build":
        return 2
    if parts[0].lower() in ("docs", "doc", "documentation") or stem == "readme":
        return 3
    if f.get("role") == "test":
        return 6
    if f.get("role") == "code":
        return 4 if rel in entry_files or stem in ENTRY_STEMS else 5
    return 7


def make_batches(files, batch_lines):
    """Group files (already ordered) into batches of about batch_lines lines. Long files are split."""
    batches, cur, used = [], [], 0
    for f in files:
        peek = f["status"] == "peek"
        total = f.get("peek", 40) if peek else f["lines"]
        if total > batch_lines:
            if cur:
                batches.append(cur)
                cur, used = [], 0
            for start in range(1, total + 1, batch_lines):
                batches.append([{"path": f["path"], "start": start, "end": min(start + batch_lines - 1, total),
                                 "of": f["lines"], "peek": peek}])
            continue
        if cur and used + total > batch_lines:
            batches.append(cur)
            cur, used = [], 0
        cur.append({"path": f["path"], "start": 1, "end": total, "of": f["lines"], "peek": peek})
        used += total
    if cur:
        batches.append(cur)
    return batches


def build_manifest(model, batch_lines):
    entry_files = {e["file"] for e in model["entries"]}
    files = model["files"]
    ordered = sorted((f for f in files if f["status"] in ("read", "peek")),
                     key=lambda f: (reading_priority(f, entry_files), f["path"].count("/") != 0, f["path"].lower()))
    batches = make_batches(ordered, batch_lines)
    langs = {}
    for f in files:
        if f["status"] == "read" and f.get("lang"):
            v = langs.setdefault(f["lang"], {"files": 0, "lines": 0})
            v["files"] += 1
            v["lines"] += f["lines"]
    skipped = {}
    for f in files:
        if f["status"] == "skip":
            skipped[f["reason"]] = skipped.get(f["reason"], 0) + 1
    return {
        "name": model["name"], "root": model["root"], "listed_with": model["listed_with"], "git": model["git"],
        "batch_lines": batch_lines,
        "totals": {"files": len(files), "read_files": sum(1 for f in files if f["status"] == "read"),
                   "peek_files": sum(1 for f in files if f["status"] == "peek"),
                   "skipped_files": sum(1 for f in files if f["status"] == "skip"),
                   "read_lines": sum(f["lines"] for f in files if f["status"] == "read"), "batches": len(batches)},
        "languages": langs, "not_read": skipped, "files": files, "batches": batches,
    }


def batch_md(batch, checkbox=True):
    out = []
    for e in batch:
        rng = "lines %d-%d of %d" % (e["start"], e["end"], e["of"]) if (e["start"] > 1 or e["end"] < e["of"]) \
            else "%d lines" % e["of"]
        out.append("%s`%s`: %s%s" % ("- [ ] " if checkbox else "- ", e["path"], rng,
                                     " (generated or data: first lines only)" if e["peek"] else ""))
    return out


def render_plan(m):
    t = m["totals"]
    L = ["# Reading plan: %s" % m["name"], "",
         "%s files listed with %s. To read: %s files, %s lines, in %d batches of about %s lines. First lines only: "
         "%d files. Not read: %d files." % (rm.fmt(t["files"]), m["listed_with"], rm.fmt(t["read_files"]),
                                           rm.fmt(t["read_lines"]), t["batches"], rm.fmt(m["batch_lines"]),
                                           t["peek_files"], t["skipped_files"]), "",
         "Read the batches in order. For each batch, read every listed line range, then write `%s/batch-NNN.md` "
         "with one `### path` heading per file." % NOTES_DIR, ""]
    for i, b in enumerate(m["batches"], 1):
        L += ["## Batch %03d (%s lines)" % (i, rm.fmt(sum(e["end"] - e["start"] + 1 for e in b))), ""]
        L += batch_md(b) + [""]
    skipped = [f for f in m["files"] if f["status"] == "skip"]
    if skipped:
        by = {}
        for f in skipped:
            by.setdefault(f["reason"], []).append(f["path"])
        L += ["## Not read", "", "| Reason | Files | Examples |", "|---|---|---|"]
        for reason in sorted(by):
            ex = ", ".join("`%s`" % p for p in by[reason][:5]) + (" ..." if len(by[reason]) > 5 else "")
            L.append("| %s | %d | %s |" % (reason, len(by[reason]), ex))
        L += ["", "Files marked sensitive must not be opened or quoted.", ""]
    return "\n".join(L).rstrip() + "\n"


# ---------------------------------------------------------------------------- LEARNINGS.md

def auto_blocks(model, m):
    """The parts of LEARNINGS.md the scan writes. A re-scan replaces them and keeps everything else."""
    t, g = m["totals"], m["git"]
    h = rm.health(model)
    facts = [rm.glance_md(model, h), "", "| Read | |", "|---|---|",
             "| Files | %s (%s read, %d first lines only, %d not read) |" % (
                 rm.fmt(t["files"]), rm.fmt(t["read_files"]), t["peek_files"], t["skipped_files"]),
             "| Lines to read | %s in %d batches |" % (rm.fmt(t["read_lines"]), t["batches"])]
    if g.get("commits"):
        facts.append("| History | %s commits%s, %s to %s |" % (
            rm.fmt(g["commits"]), " (shallow clone, so incomplete)" if g.get("shallow") else "",
            g.get("first_commit", "?"), g.get("last_commit", "?")))
    cmds = ["| Command | Found in |", "|---|---|"] + ["| `%s` | `%s` |" % (rm.md_cell(c["cmd"]), c["source"])
                                                     for c in model["commands"]] if model["commands"] else \
        ["No build file with commands was found."]
    arch = []
    hld = rm.hld_mermaid(model)
    if hld:
        arch += ["**High-level design**", "", "```mermaid", hld, "```", "", rm.hld_legend(), ""]
    for n, f in enumerate(model["flows"], 1):
        arch += ["**Flow %d: %s**" % (n, f["title"]), "", "```mermaid", rm.flow_mermaid(f), "```", "",
                 "<details><summary>Steps: where each call is defined and made</summary>", "", rm.flow_table(f), "",
                 "</details>", ""]
    if not hld and not model["flows"]:
        arch.append("No code structure was found to draw.")
    deps = []
    if model["systems"]:
        deps += ["External systems reached from the code:", ""]
        deps += ["- **%s** via %s, used by %s" % (s["label"], ", ".join("`%s`" % v for v in s["via"][:4]),
                                                  ", ".join("`%s`" % (u or "(root)") for u in s["used_by"][:5]))
                 for s in model["systems"]] + [""]
    by_file = {}
    for d in model["deps"]:
        by_file.setdefault((d["file"], d["eco"]), []).append(d["name"])
    if by_file:
        deps += ["| Manifest | Packages |", "|---|---|"]
        deps += ["| `%s` (%s) | %s%s |" % (f, eco, rm.md_cell(", ".join(n[:25])), " ..." if len(n) > 25 else "")
                 for (f, eco), n in sorted(by_file.items())]
    if not deps:
        deps = ["No manifests or outside packages were found."]
    return {"facts": "\n".join(facts), "commands": "\n".join(cmds), "architecture": "\n".join(arch).rstrip(),
            "dependencies": "\n".join(deps).rstrip(), "health": rm.audit_md(model, None, "###")}


def block(name, body):
    return "<!-- auto:%s -->\n%s\n<!-- /auto:%s -->" % (name, body, name)


def refresh_blocks(text, blocks):
    for name, body in blocks.items():
        rx = re.compile(r"<!-- auto:%s -->.*?<!-- /auto:%s -->" % (name, name), re.S)
        if rx.search(text):
            text = rx.sub(lambda _: block(name, body), text)
    return text


def render_learnings(model, m):
    b = auto_blocks(model, m)
    folders = ["| Component | Path | Kind | Files | Lines | What lives here |", "|---|---|---|---|---|---|"]
    for c in model["components"]:
        if c["files"]:
            folders.append("| %s | `%s` | %s | %d | %s | |" % (rm.md_cell(c["name"]), c["id"] or ".", c["kind"],
                                                               c["files"], rm.fmt(c["lines"])))
    L = ["# Learnings: %s" % m["name"], "",
         "> Written from a full read of the repository. Blocks marked `auto` were drawn by the scan from imports and "
         "calls (a re-scan refreshes them); everything else was written from the files themselves.", "",
         "## Facts", "", block("facts", b["facts"]), "",
         "## 1. What this repository is", "",
         "%s: what it does, who uses it, and the problem it solves, in a few sentences." % TODO, "",
         "## 2. How to build, run and test", "", block("commands", b["commands"]), "",
         "%s: the exact steps, with what each needs (tools, versions, services, environment)." % TODO, "",
         "## 3. Folder map", ""] + folders + ["", "%s: fill the last column for every row." % TODO, "",
         "## 4. Architecture and main flows", "", block("architecture", b["architecture"]), "",
         "%s: the main parts and how they call each other; for each flow above, what it does and what the diagram "
         "misses (callbacks, injection, network calls). Mark guesses as guesses." % TODO, "",
         "## 5. Key files", "",
         "%s: the files a newcomer must know, each with one line on why it matters." % TODO, ""]
    if m["git"].get("most_changed"):
        L += ["Most often changed in the last 1000 commits:", ""]
        L += ["- `%s` (%d commits)" % (x["path"], x["commits"]) for x in m["git"]["most_changed"][:10]] + [""]
    L += ["## 6. Conventions and patterns", "",
          "%s: naming, structure, error handling, configuration and other patterns the code repeats." % TODO, "",
          "## 7. Dependencies and external services", "", block("dependencies", b["dependencies"]), "",
          "%s: what each important dependency and service is used for, and where." % TODO, "",
          "## 8. Tests and quality", "", block("health", b["health"]), "",
          "%s: what is tested and how, what is not, lint and CI; which audit findings you confirmed in the code and "
          "which are false alarms." % TODO, "",
          "## 9. Gotchas, risks and open questions", "",
          "%s: surprises, fragile places, dead code, things the code does not explain." % TODO, "",
          "## 10. Where to start for common changes", "",
          "%s: for the likely kinds of change, which files to open first." % TODO, "",
          "## Appendix: file-by-file notes", "",
          NOTES_START, "_Filled by the `assemble` command from the batch notes._", NOTES_END, ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------- commands

def cmd_scan(args):
    src = args.repo
    name = args.name or rm.repo_name(src if rm.URL.match(src) else os.path.abspath(src))
    out = os.path.abspath(args.out or os.path.join("repo-learnings", name))
    root = os.path.abspath(rm.open_source(src, out, full_history=args.full_history))
    os.makedirs(os.path.join(out, NOTES_DIR), exist_ok=True)
    rel = os.path.relpath(out, root).replace(os.sep, "/")
    model = rm.analyze(root, name=name, source=src, flows=args.flows, only=args.only, exclude=args.exclude,
                       include=args.include, use_git=not args.no_git, skip=[] if rel.startswith("..") else [rel])
    m = build_manifest(model, args.batch_lines)
    if not m["batches"]:
        raise ValueError("no readable text files found in %s" % root)
    rm.save_json(os.path.join(out, MANIFEST), m)
    rm.save_json(os.path.join(out, MODEL), model)
    rm.write_text(os.path.join(out, PLAN), render_plan(m))
    lpath = os.path.join(out, LEARNINGS)
    kept = os.path.exists(lpath) and not args.force
    if kept:
        rm.write_text(lpath, refresh_blocks(read(lpath), auto_blocks(model, m)))
    else:
        rm.write_text(lpath, render_learnings(model, m))
    t, h = m["totals"], rm.health(model)
    print("Repository: %s (%s)" % (m["name"], m["root"]))
    print("Files: %s listed with %s" % (rm.fmt(t["files"]), m["listed_with"]))
    print("To read: %s files, %s lines, %d batches of about %s lines" % (
        rm.fmt(t["read_files"]), rm.fmt(t["read_lines"]), t["batches"], rm.fmt(m["batch_lines"])))
    if t["peek_files"]:
        print("First lines only: %d generated or large data files" % t["peek_files"])
    if m["not_read"]:
        print("Not read: " + ", ".join("%d %s" % (n, r) for r, n in sorted(m["not_read"].items())))
    print("Drawn: %d components, %d code flows; health %d/100 (%s)" % (
        sum(1 for c in model["components"] if c.get("hld")), len(model["flows"]), h["score"], h["grade"]))
    print("Wrote: %s" % os.path.join(out, PLAN))
    print("       %s%s" % (lpath, " (kept your text, refreshed the auto blocks; --force starts over)" if kept else ""))
    if t["read_lines"] > args.warn_lines:
        print("Note: this is a large read (%s lines). Tell the user the size before starting, and offer --only "
              "<folder> to read part of it." % rm.fmt(t["read_lines"]))
    print("Next: python %s next %s" % (os.path.basename(__file__), out))
    return 0


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def load(out):
    path = os.path.join(out, MANIFEST)
    if not os.path.exists(path):
        raise ValueError("%s not found. Run the scan command first." % path)
    return rm.load_json(path)


def notes_path(out, i):
    return os.path.normpath(os.path.join(out, NOTES_DIR, "batch-%03d.md" % i))


def batch_done(out, i, batch):
    p = notes_path(out, i)
    return os.path.exists(p) and all(e["path"] in read(p) for e in batch)


def print_batch(out, m, i):
    b = m["batches"][i - 1]
    print("Batch %03d of %03d, repository root: %s" % (i, len(m["batches"]), m["root"]))
    print("Read every line of each range below:")
    print("\n".join(batch_md(b, checkbox=False)))
    by = {f["path"]: f for f in m["files"]}
    syms = [(e["path"], by[e["path"]].get("symbols")) for e in b if by.get(e["path"], {}).get("symbols")]
    if syms:
        print("Functions the scan found (the notes should explain the important ones):")
        for p, s in syms:
            print("  %s: %s%s" % (p, ", ".join(s[:12]), " ..." if len(s) > 12 else ""))
    print("Then write %s with one '### <path>' heading per file above." % notes_path(out, i))


def cmd_next(args):
    m = load(args.out)
    done = [batch_done(args.out, i, b) for i, b in enumerate(m["batches"], 1)]
    for i, ok in enumerate(done, 1):
        if not ok:
            print("%d of %d batches have notes." % (sum(done), len(done)))
            print_batch(args.out, m, i)
            return 0
    print("All %d batches have notes. Now write the numbered sections of %s, then run 'assemble' and 'coverage'."
          % (len(done), os.path.join(args.out, LEARNINGS)))
    return 0


def cmd_batch(args):
    m = load(args.out)
    if not 1 <= args.number <= len(m["batches"]):
        raise ValueError("batch number must be 1 to %d" % len(m["batches"]))
    print_batch(args.out, m, args.number)
    return 0


def all_notes(out, m):
    return [read(notes_path(out, i)).strip() for i in range(1, len(m["batches"]) + 1)
            if os.path.exists(notes_path(out, i))]


def cmd_assemble(args):
    m = load(args.out)
    lpath = os.path.join(args.out, LEARNINGS)
    if not os.path.exists(lpath):
        raise ValueError("%s not found. Run the scan command first." % lpath)
    chunks = all_notes(args.out, m)
    if not chunks:
        raise ValueError("no notes found in %s" % os.path.join(args.out, NOTES_DIR))
    text = read(lpath)
    body = NOTES_START + "\n\n" + "\n\n".join(chunks) + "\n\n" + NOTES_END
    if NOTES_START in text and NOTES_END in text:
        text = text[:text.index(NOTES_START)] + body + text[text.index(NOTES_END) + len(NOTES_END):]
    else:
        text = text.rstrip() + "\n\n## Appendix: file-by-file notes\n\n" + body + "\n"
    rm.write_text(lpath, text)
    print("Copied %d of %d batch notes into %s" % (len(chunks), len(m["batches"]), lpath))
    return 0


def cmd_coverage(args):
    m = load(args.out)
    lpath = os.path.join(args.out, LEARNINGS)
    learn = read(lpath) if os.path.exists(lpath) else ""
    notes = "\n".join(all_notes(args.out, m))   # the skeleton itself names files, so only the notes count
    appendix = learn[learn.index(NOTES_START):learn.index(NOTES_END)] if NOTES_START in learn and NOTES_END in learn \
        else ""
    wanted = [f["path"] for f in m["files"] if f["status"] in ("read", "peek")]
    missing = [p for p in wanted if p not in notes]
    covered = len(wanted) - len(missing)
    pct = 100.0 * covered / len(wanted) if wanted else 100.0
    todo = learn.count(TODO)
    open_batches = [i for i, b in enumerate(m["batches"], 1) if not batch_done(args.out, i, b)]
    in_final = sum(1 for p in wanted if p in appendix)
    print("Files mentioned in the notes: %d of %d (%.1f%%)" % (covered, len(wanted), pct))
    print("Files mentioned in %s itself: %d of %d" % (LEARNINGS, in_final, len(wanted)))
    print("Batches without complete notes: %s" % (", ".join("%03d" % i for i in open_batches) or "none"))
    print("Unfinished sections in %s (%s markers): %d" % (LEARNINGS, TODO, todo))
    if missing:
        print("Not mentioned anywhere:")
        for p in missing[:args.show]:
            print("  " + p)
        if len(missing) > args.show:
            print("  ... and %d more" % (len(missing) - args.show))
    if in_final < covered:
        print("Run 'assemble' so that %s contains the file-by-file notes." % LEARNINGS)
    ok = pct >= args.min and todo == 0 and in_final == covered
    print("Result: %s" % ("complete" if ok else "not complete"))
    return 0 if ok else 1


def build_parser():
    p = argparse.ArgumentParser(description="Plan a complete read of a repository and check the notes cover it.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="list the files, make the reading plan and the LEARNINGS.md skeleton")
    s.add_argument("repo", help="folder of a repository, or a git URL to clone")
    s.add_argument("--out", help="output folder (default: repo-learnings/<name>)")
    s.add_argument("--name", help="name used in titles (default: the folder or repository name)")
    s.add_argument("--batch-lines", type=int, default=1200, help="lines per batch (default 1200)")
    s.add_argument("--flows", type=int, default=3, help="code-flow diagrams to draw (default 3)")
    s.add_argument("--only", action="append", default=[], metavar="PATH", help="read only this folder or file (repeatable)")
    s.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="leave out matching paths (repeatable)")
    s.add_argument("--include", action="append", default=[], metavar="GLOB",
                   help="read matching files in full even if they look generated, vendored or like data (repeatable)")
    s.add_argument("--no-git", action="store_true", help="walk the folder instead of asking git for the file list")
    s.add_argument("--full-history", action="store_true", help="when cloning a URL, clone all history")
    s.add_argument("--warn-lines", type=int, default=60000, help="print a size note above this many lines")
    s.add_argument("--force", action="store_true", help="replace an existing LEARNINGS.md")
    s.set_defaults(func=cmd_scan)
    for name, func, text in (("next", cmd_next, "print the next batch that has no notes"),
                             ("assemble", cmd_assemble, "copy the batch notes into LEARNINGS.md"),
                             ("coverage", cmd_coverage, "check that the notes cover every file")):
        q = sub.add_parser(name, help=text)
        q.add_argument("out", help="output folder of the scan")
        q.set_defaults(func=func)
        if name == "coverage":
            q.add_argument("--min", type=float, default=100.0, help="percent of files that must be mentioned")
            q.add_argument("--show", type=int, default=40, help="how many missing files to list")
    b = sub.add_parser("batch", help="print one batch")
    b.add_argument("out", help="output folder of the scan")
    b.add_argument("number", type=int)
    b.set_defaults(func=cmd_batch)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (IOError, OSError, ValueError) as ex:
        sys.stderr.write("error: %s\n" % ex)
        return 2


if __name__ == "__main__":
    sys.exit(main())
