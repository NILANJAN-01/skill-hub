#!/usr/bin/env python3
"""Repo architecture: draft ARCHITECTURE.md (HLD diagram, code flows, health audit) from the code.

    analyze  read the repository (folder or git URL) and write model.json, annotations.json and
             ARCHITECTURE.md with a Mermaid high-level design, one sequence diagram per entry point,
             components, a scored health audit, commands, dependencies and a reading order
    render   rebuild ARCHITECTURE.md from model.json and annotations.json (keeps your text)
    check    exit 0 only when every TODO(architecture) is replaced and the file is up to date
    audit    print only the health audit; with --fail-under N, exit 1 below that score (for CI)

Python 3.8+, standard library only. It never runs code from the repository.

    python repo_architecture.py analyze path/to/repo
    python repo_architecture.py analyze https://github.com/owner/project.git
    python repo_architecture.py render repo-architecture/project
    python repo_architecture.py check repo-architecture/project
    python repo_architecture.py audit path/to/repo --fail-under 70
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_model as rm  # noqa: E402

TODO = "TODO(architecture)"
MODEL, ANN, DOC = "model.json", "annotations.json", "ARCHITECTURE.md"


# ---------------------------------------------------------------------------- annotations

def new_annotations(model, old=None):
    """Annotation skeleton for this model; text already written in `old` is kept."""
    old = old or {}
    comps = {}
    for c in model["components"]:
        if c.get("hld"):
            prev = (old.get("components") or {}).get(c["id"], {})
            comps[c["id"]] = {"title": prev.get("title", ""),
                              "description": prev.get("description") or "%s: what %s does and why it exists, "
                              "and who calls it." % (TODO, c["name"])}
    flows = {}
    for f in model["flows"]:
        flows[f["key"]] = (old.get("flows") or {}).get(f["key"]) or \
            "%s: what this flow does, in one to three sentences, from the code you read." % TODO
    return {
        "summary": old.get("summary") or "%s: what the repository is, who uses it, how it is built and shipped." % TODO,
        "components": comps,
        "flows": flows,
        "extra_flows": old.get("extra_flows") or [],
        "notes": old.get("notes") or [],
        "dismissed": old.get("dismissed") or {},
    }


def load_annotations(out, model):
    path = os.path.join(out, ANN)
    if not os.path.exists(path):
        return new_annotations(model)
    try:
        return new_annotations(model, rm.load_json(path))
    except ValueError as e:
        raise SystemExit("error: %s is not valid JSON: %s" % (path, e))


def missing(model, ann):
    out = []
    if TODO in ann["summary"]:
        out.append("summary")
    for cid, v in ann["components"].items():
        if TODO in v.get("description", ""):
            out.append("component %s" % (cid or "(root)"))
    for k, v in ann["flows"].items():
        if TODO in v:
            out.append("flow %s" % k)
    return out


# ---------------------------------------------------------------------------- ARCHITECTURE.md

def render_md(model, ann):
    cindex = {c["id"]: c for c in model["components"]}
    titles = {cid: v.get("title", "") for cid, v in ann["components"].items() if v.get("title")}
    h = rm.health(model, ann.get("dismissed"))
    g = model.get("git", {})
    L = ["# Architecture: %s" % model["name"], "",
         "> Drafted by repo-architecture on %s from `%s`%s, then described by a reader of the code. Diagrams come "
         "from static imports and calls; see *Notes and limits*." % (
             model["generated"], g.get("remote") or model["source"], " at %s" % g["head"] if g.get("head") else ""),
         "", "## Summary", "", ann["summary"], "", "## At a glance", "", rm.glance_md(model, h), ""]
    hld = rm.hld_mermaid(model, titles)
    L += ["## High-level design", ""]
    if hld:
        L += ["```mermaid", hld, "```", "", rm.hld_legend(), ""]
    else:
        L += ["No code components were found, so there is no diagram.", ""]
    deps, used_by = {}, {}
    for e in model["edges"]:
        deps.setdefault(e["from"], []).append(e["to"])
        used_by.setdefault(e["to"], []).append(e["from"])
    L += ["## Components", "", "| Component | Kind | Languages | Code lines | Depends on | Used by | What it does |",
          "|---|---|---|---|---|---|---|"]
    order = sorted(model["components"], key=lambda c: (not c.get("hld"), c.get("tier", 9), -c["code_lines"], c["id"]))
    for c in order:
        if not c["files"]:
            continue
        name = lambda x: cindex[x]["name"] if x in cindex else x  # noqa: E731
        desc = ann["components"].get(c["id"], {}).get("description", "")
        L.append("| **%s** `%s` | %s | %s | %s | %s | %s | %s |" % (
            rm.md_cell(c["name"]), c["id"] or ".", c["kind"], ", ".join(c["langs"]) or "-", rm.fmt(c["code_lines"]),
            rm.md_cell(", ".join(name(x) for x in deps.get(c["id"], [])[:6])) or "-",
            rm.md_cell(", ".join(name(x) for x in used_by.get(c["id"], [])[:6])) or "-", rm.md_cell(desc)))
    L += ["", "## Code flows", ""]
    if not model["flows"] and not ann["extra_flows"]:
        L += ["No entry point with calls into the repository's own code was found. Describe the main flows in "
              "`extra_flows` of annotations.json.", ""]
    for n, f in enumerate(model["flows"], 1):
        L += ["### %d. %s" % (n, f["title"]), "", ann["flows"].get(f["key"], ""), "",
              "```mermaid", rm.flow_mermaid(f), "```", "",
              "<details><summary>Steps: where each call is defined and made</summary>", "", rm.flow_table(f), "",
              "</details>", ""]
    for n, f in enumerate(ann["extra_flows"], len(model["flows"]) + 1):
        L += ["### %d. %s" % (n, f.get("title", "Flow")), ""]
        L += ["%d. %s" % (k, s) for k, s in enumerate(f.get("steps", []), 1)] + [""]
    if model["entries"]:
        L += ["### Entry points", "", "| Kind | Entry | Where |", "|---|---|---|"]
        for e in model["entries"][:20]:
            L.append("| %s | `%s`%s | `%s:%d` |" % (e["kind"], rm.md_cell(e["name"]),
                                                   " %s" % rm.md_cell(e["label"]) if e.get("label") else "",
                                                   e["file"], e["line"]))
        L.append("")
    L += [rm.audit_md(model, ann.get("dismissed"), "##"), ""]
    L += ["## Build, run and test", ""]
    if model["commands"]:
        L += ["| Command | Found in |", "|---|---|"]
        L += ["| `%s` | `%s` |" % (rm.md_cell(c["cmd"]), c["source"]) for c in model["commands"]]
    else:
        L.append("No build file with commands was found.")
    if model["ci"]:
        L += ["", "CI: " + ", ".join("`%s`" % p for p in model["ci"])]
    L += ["", "## Dependencies", ""]
    by_eco = {}
    for d in model["deps"]:
        by_eco.setdefault((d["eco"], d["file"]), []).append(d)
    if by_eco:
        L += ["| Manifest | Packages |", "|---|---|"]
        for (eco, f), ds in sorted(by_eco.items(), key=lambda kv: kv[0][1]):
            names = ", ".join("%s%s" % (d["name"], " " + d["spec"] if d["spec"] and not d["spec"].startswith("(")
                                        else "") for d in ds[:25])
            L.append("| `%s` (%s) | %s%s |" % (f, eco, rm.md_cell(names), " ..." if len(ds) > 25 else ""))
    ext = [(c["name"], c["packages"]) for c in order if c.get("packages") and c["kind"] in ("source", "web", "tooling")]
    if ext:
        L += ["", "Outside packages imported by each component (most used first):", ""]
        L += ["- **%s**: %s" % (rm.md_cell(n), ", ".join("`%s`" % p for p in pk)) for n, pk in ext[:20]]
    if not by_eco and not ext:
        L.append("No dependencies were found.")
    L += ["", "## Reading order", ""]
    steps = []
    readme = next((f["path"] for f in model["files"] if "/" not in f["path"] and f["path"].lower().startswith("readme")),
                  None)
    if readme:
        steps.append("`%s`: what the project says it is." % readme)
    if model["manifests"]:
        steps.append("Build files: %s." % ", ".join("`%s`" % p for p in model["manifests"][:5]))
    for f in model["flows"]:
        steps.append("`%s:%d`: start of flow \"%s\"." % (f["entry"]["file"], f["entry"]["line"], f["entry"]["label"]))
    for c in sorted((c for c in model["components"] if c.get("hld")), key=lambda c: (c["tier"], -c["code_lines"]))[:10]:
        if c["key_files"]:
            steps.append("**%s**: %s." % (c["name"], ", ".join("`%s`" % p for p in c["key_files"][:3])))
    L += ["%d. %s" % (k, s) for k, s in enumerate(steps, 1)]
    L += ["", "## Notes and limits", ""]
    L += ["- %s" % n for n in ann["notes"]]
    L += ["- Arrows and flows come from imports and calls written in the code. Calls through interfaces, callbacks, "
          "reflection, dependency injection, dynamic imports, message queues and network calls between services are "
          "not followed, so a flow can stop early.",
          "- %s of %s calls resolved to the repository's own functions; the rest go to the standard library, outside "
          "packages, or could not be told apart (same name in several places)." % (
              rm.fmt(model["stats"]["calls_resolved"]), rm.fmt(model["stats"]["calls"]))]
    L += ["- %s" % n for n in model["notes"]]
    skipped = {}
    for f in model["files"]:
        if f["status"] != "read":
            skipped[f["reason"]] = skipped.get(f["reason"], 0) + 1
    if skipped:
        L.append("- Not read: " + ", ".join("%d %s" % (n, r) for r, n in sorted(skipped.items())) +
                 ". Sensitive files were never opened.")
    return "\n".join(L).rstrip() + "\n"


# ---------------------------------------------------------------------------- commands

def out_dir(args, src):
    name = args.name or rm.repo_name(src if rm.URL.match(src) else os.path.abspath(src))
    return os.path.abspath(args.out or os.path.join("repo-architecture", name)), name


def do_analyze(args):
    out, name = out_dir(args, args.repo)
    root = rm.open_source(args.repo, out, args.branch)
    os.makedirs(out, exist_ok=True)
    model = rm.analyze(root, name=name, source=args.repo, depth=args.depth, granularity=args.granularity,
                       flows=args.flows, steps=args.steps, only=args.only, exclude=args.exclude,
                       use_git=not args.no_git, skip=[os.path.relpath(out, root).replace(os.sep, "/")]
                       if not os.path.relpath(out, root).startswith("..") else ())
    if not model["files"]:
        raise SystemExit("error: no readable files found in %s" % root)
    rm.save_json(os.path.join(out, MODEL), model)
    ann = load_annotations(out, model)
    rm.save_json(os.path.join(out, ANN), ann)
    rm.write_text(os.path.join(out, DOC), render_md(model, ann))
    st, h = model["stats"], rm.health(model, ann["dismissed"])
    print("Repository: %s (%s)" % (name, root))
    print("Read: %s files, %s code lines in %s; %s functions, %s calls resolved (%.1fs)" % (
        rm.fmt(st["read_files"]), rm.fmt(st["code_lines"]), ", ".join(list(st["languages"])[:6]) or "no code",
        rm.fmt(st["functions"]), rm.fmt(st["calls_resolved"]), st["seconds"]))
    print("Components: %d (%d in the diagram), dependencies: %d, entry points: %d, flows drawn: %d" % (
        len(model["components"]), sum(1 for c in model["components"] if c.get("hld")), len(model["edges"]),
        len(model["entries"]), len(model["flows"])))
    print("External systems: %s" % (", ".join(s["label"] for s in model["systems"]) or "none detected"))
    print("Health: %d/100 (%s); %d high, %d medium, %d low findings" % (
        h["score"], h["grade"], h["sev"]["HIGH"], h["sev"]["MEDIUM"], h["sev"]["LOW"]))
    print("Wrote: %s" % os.path.join(out, DOC))
    print("       %s (fill the %s markers, then run render and check)" % (os.path.join(out, ANN), TODO))
    return 0


def load_model(out):
    path = os.path.join(out, MODEL)
    if not os.path.exists(path):
        raise SystemExit("error: %s not found. Run the analyze command first." % path)
    return rm.load_json(path)


def do_render(args):
    model = load_model(args.out)
    ann = load_annotations(args.out, model)
    rm.save_json(os.path.join(args.out, ANN), ann)
    rm.write_text(os.path.join(args.out, DOC), render_md(model, ann))
    print("Wrote: %s" % os.path.join(args.out, DOC))
    return 0


def do_check(args):
    model = load_model(args.out)
    ann = load_annotations(args.out, model)
    todo = missing(model, ann)
    doc = os.path.join(args.out, DOC)
    current = io.open(doc, encoding="utf-8").read() if os.path.exists(doc) else ""
    stale = current != render_md(model, ann)
    for t in todo:
        print("Not described yet: %s" % t)
    if stale:
        print("%s is older than annotations.json: run render." % DOC)
    h = rm.health(model, ann.get("dismissed"))
    print("Health: %d/100 (%s), %d findings, %d dismissed" % (h["score"], h["grade"], len(h["active"]),
                                                               len(h["dismissed"])))
    ok = not todo and not stale
    print("Result: %s" % ("complete" if ok else "not complete"))
    return 0 if ok else 1


def do_audit(args):
    if os.path.isfile(os.path.join(args.repo, MODEL)):
        model = rm.load_json(os.path.join(args.repo, MODEL))
        ann = load_annotations(args.repo, model)
        dismissed = ann.get("dismissed")
    else:
        root = rm.open_source(args.repo, os.path.abspath(args.out or os.path.join("repo-architecture", "audit")))
        model = rm.analyze(root, name=rm.repo_name(os.path.abspath(root)), flows=0, only=args.only,
                           exclude=args.exclude, use_git=not args.no_git)
        dismissed = rm.load_json(args.dismissed).get("dismissed", {}) if args.dismissed else {}
    h = rm.health(model, dismissed)
    if args.json:
        print(json.dumps({"score": h["score"], "grade": h["grade"], "areas": h["areas"],
                          "findings": h["active"]}, indent=1))
    else:
        print(rm.audit_md(model, dismissed, "#"))
    if args.fail_under is not None and h["score"] < args.fail_under:
        sys.stderr.write("health score %d is below %d\n" % (h["score"], args.fail_under))
        return 1
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Draft ARCHITECTURE.md (HLD, code flows, health audit) from a repository.")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("analyze", help="read the repository and write the draft")
    a.add_argument("repo", help="folder of a repository, or a git URL to clone")
    a.add_argument("--out", help="output folder (default: repo-architecture/<name>)")
    a.add_argument("--name", help="name used in titles")
    a.add_argument("--depth", type=int, default=2, help="container folders (src, packages, ...) to open (default 2)")
    a.add_argument("--granularity", choices=("auto", "folder", "file"), default="auto",
                   help="components are folders, files, or decided per repository (default auto)")
    a.add_argument("--flows", type=int, default=3, help="code-flow diagrams to draw (default 3)")
    a.add_argument("--steps", type=int, default=30, help="calls per flow diagram (default 30)")
    a.add_argument("--branch", help="branch or tag to clone when the source is a URL")
    a.add_argument("--only", action="append", default=[], metavar="PATH", help="analyze only this folder (repeatable)")
    a.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="leave out paths (repeatable)")
    a.add_argument("--no-git", action="store_true", help="walk the folder instead of asking git for the file list")
    a.set_defaults(func=do_analyze)
    for name, func, text in (("render", do_render, "rebuild ARCHITECTURE.md from model.json and annotations.json"),
                             ("check", do_check, "report what is still undescribed")):
        q = sub.add_parser(name, help=text)
        q.add_argument("out", help="output folder of analyze")
        q.set_defaults(func=func)
    u = sub.add_parser("audit", help="print the health audit only")
    u.add_argument("repo", help="repository folder or git URL, or an analyze output folder")
    u.add_argument("--fail-under", type=int, help="exit 1 when the score is below this")
    u.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    u.add_argument("--dismissed", help="annotations.json whose 'dismissed' entries to apply")
    u.add_argument("--out", help="where to clone a URL")
    u.add_argument("--only", action="append", default=[], metavar="PATH")
    u.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    u.add_argument("--no-git", action="store_true")
    u.set_defaults(func=do_audit)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (IOError, OSError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
