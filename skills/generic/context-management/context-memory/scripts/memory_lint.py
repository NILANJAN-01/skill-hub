#!/usr/bin/env python3
"""Lint and index a folder of AI agent memory files (one fact per Markdown file).

Usage:
  python memory_lint.py lint  <memory-dir> [--index MEMORY.md] [--root PROJECT] [--json]
  python memory_lint.py index <memory-dir> [--index MEMORY.md] [--write]
  python memory_lint.py new   <memory-dir> --name SLUG --type TYPE --description TEXT [--write]

Memory file format:
  ---
  name: short-kebab-slug
  description: one line used to decide relevance
  type: user | feedback | project | reference     (or under metadata:)
  ---
  The fact. For feedback/project add **Why:** and **How to apply:** lines.

`lint` is read-only. `index` and `new` are dry runs unless --write is given;
they never delete or overwrite. Exit code 1 when lint finds errors.
Python 3.8+, standard library only. Token counts are estimates (chars / 4).
"""
import argparse
import json
import os
import re
import sys

TYPES = ("user", "feedback", "project", "reference")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
INDEX_LINE = re.compile(r"^\s*[-*]\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:[-:—–]+\s*(.*))?$")
PATH_RE = re.compile(r"`([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,8})`")
RELATIVE_TIME = re.compile(r"\b(?:yesterday|today|tomorrow|last (?:week|month|night)|next (?:week|month)|"
                           r"this (?:week|month|sprint)|recently|currently|right now)\b", re.I)
SECRET = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|"
    r"xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?i:(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"<>]{8,}))")
STOP = set("a an the and or of to in on for with is are be it this that use when user project file "
           "files from by as at not do does should".split())
MAX_BODY_LINES = 40
MAX_INDEX_LINE = 200
MAX_INDEX_LINES = 200


def tokens(text):
    return (len(text) + 3) // 4


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse(text):
    """Return (frontmatter dict, body, error). Supports flat keys and one nested map level."""
    if not text.startswith("---"):
        return {}, text, "no frontmatter (file must start with ---)"
    end = re.search(r"^---\s*$", text[3:], re.M)
    if not end:
        return {}, text, "frontmatter is not closed with ---"
    raw, body = text[3:3 + end.start()], text[3 + end.end():]
    fm, parent = {}, None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        indent, key, value = m.group(1), m.group(2), m.group(3).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if indent and parent is not None:
            fm[parent][key] = value
        elif value == "":
            fm[key], parent = {}, key
        else:
            fm[key], parent = value, None
    return fm, body.strip(), None


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


def load(mem_dir, index_name):
    items = []
    for fn in sorted(os.listdir(mem_dir)):
        if not fn.endswith(".md") or fn == index_name:
            continue
        text = read(os.path.join(mem_dir, fn))
        fm, body, err = parse(text)
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        items.append({"file": fn, "name": fm.get("name") if isinstance(fm.get("name"), str) else None,
                      "description": fm.get("description") if isinstance(fm.get("description"), str) else None,
                      "type": fm.get("type") or meta.get("type"), "body": body, "error": err,
                      "tokens": tokens(text)})
    return items


def read_index(mem_dir, index_name):
    path = os.path.join(mem_dir, index_name)
    if not os.path.exists(path):
        return None
    entries, other = [], []
    for n, line in enumerate(read(path).splitlines(), 1):
        m = INDEX_LINE.match(line)
        if m:
            entries.append({"line": n, "title": m.group(1), "target": m.group(2).split("#")[0],
                            "text": line})
        elif line.strip() and not line.lstrip().startswith("#"):
            other.append(n)
    return {"entries": entries, "other": other, "text": read(path)}


def lint(mem_dir, index_name="MEMORY.md", root=None):
    errors, warnings, notes = [], [], []
    items = load(mem_dir, index_name)
    names = {}
    for it in items:
        f = it["file"]
        if it["error"]:
            errors.append("%s: %s" % (f, it["error"]))
            continue
        if not it["name"]:
            errors.append("%s: frontmatter 'name' is missing" % f)
        else:
            names.setdefault(it["name"], []).append(f)
            if not SLUG.match(it["name"]):
                warnings.append("%s: name %r should be a lowercase-kebab slug" % (f, it["name"]))
            elif it["name"] != f[:-3]:
                warnings.append("%s: name %r differs from the file name" % (f, it["name"]))
        if not it["description"]:
            errors.append("%s: frontmatter 'description' is missing" % f)
        elif len(it["description"]) > 150:
            warnings.append("%s: description is %d chars; keep it to one short line" % (f, len(it["description"])))
        if it["type"] not in TYPES:
            warnings.append("%s: type %r is not one of %s" % (f, it["type"], ", ".join(TYPES)))
        body = it["body"]
        if not body:
            errors.append("%s: body is empty" % f)
        elif it["type"] in ("feedback", "project") and not re.search(r"\bwhy\b\s*[:*]", body, re.I):
            warnings.append("%s: %s memory has no 'Why:' line; without the reason it cannot be judged later"
                            % (f, it["type"]))
        if body.count("\n") + 1 > MAX_BODY_LINES:
            warnings.append("%s: %d lines; one fact per file (split it)" % (f, body.count("\n") + 1))
        m = RELATIVE_TIME.search(body + " " + (it["description"] or ""))
        if m:
            warnings.append("%s: relative time %r; write an absolute date" % (f, m.group(0)))
        if re.search(r"<(?:the fact|reason|when and how)>", body):
            warnings.append("%s: has unfilled <...> markers from 'new'" % f)
        if SECRET.search(body):
            errors.append("%s: looks like it stores a secret; remove it" % f)
        if root:
            for p in sorted(set(PATH_RE.findall(body))):
                if not os.path.exists(os.path.join(root, p)):
                    warnings.append("%s: names `%s`, which no longer exists; verify or update the memory" % (f, p))
    for name, files in sorted(names.items()):
        if len(files) > 1:
            errors.append("duplicate name %r in %s" % (name, ", ".join(files)))
    known = set(names)
    for it in items:
        for target in sorted(set(LINK.findall(it["body"]))):
            if target.strip() not in known:
                notes.append("%s: [[%s]] has no memory yet (fine if planned)" % (it["file"], target.strip()))
    # near-duplicates
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            wa, wb = words((a["description"] or "") + " " + (a["name"] or "")), \
                words((b["description"] or "") + " " + (b["name"] or ""))
            if wa and wb and len(wa & wb) / float(len(wa | wb)) >= 0.6:
                warnings.append("%s and %s look like the same fact; merge them" % (a["file"], b["file"]))
    idx = read_index(mem_dir, index_name)
    index_tokens = 0
    if idx is None:
        errors.append("%s is missing; run: memory_lint.py index %s --write" % (index_name, mem_dir))
    else:
        index_tokens = tokens(idx["text"])
        listed = {}
        for e in idx["entries"]:
            listed.setdefault(e["target"], []).append(e["line"])
            if not os.path.exists(os.path.join(mem_dir, e["target"])):
                errors.append("%s line %d: points to missing file %s" % (index_name, e["line"], e["target"]))
            if len(e["text"]) > MAX_INDEX_LINE:
                warnings.append("%s line %d: %d chars; index lines are pointers, keep them short"
                                % (index_name, e["line"], len(e["text"])))
        for target, lines in sorted(listed.items()):
            if len(lines) > 1:
                warnings.append("%s lists %s %d times" % (index_name, target, len(lines)))
        for it in items:
            if it["file"] not in listed:
                errors.append("%s: not listed in %s, so it will never be recalled" % (it["file"], index_name))
        if idx["other"]:
            warnings.append("%s has %d non-pointer lines (e.g. line %d); keep facts in memory files, not the index"
                            % (index_name, len(idx["other"]), idx["other"][0]))
        n = idx["text"].count("\n") + 1
        if n > MAX_INDEX_LINES:
            warnings.append("%s has %d lines; agents may truncate long indexes, prune or merge memories"
                            % (index_name, n))
    return {"dir": mem_dir, "memories": len(items), "index_tokens": index_tokens,
            "total_tokens": sum(i["tokens"] for i in items) + index_tokens,
            "by_type": {t: sum(1 for i in items if i["type"] == t) for t in TYPES},
            "errors": errors, "warnings": warnings, "notes": notes}


def index_lines(mem_dir, index_name="MEMORY.md"):
    """Index lines for memory files that the index does not list yet."""
    idx = read_index(mem_dir, index_name)
    listed = {e["target"] for e in idx["entries"]} if idx else set()
    out = []
    for it in load(mem_dir, index_name):
        if it["file"] in listed or it["error"]:
            continue
        title = (it["name"] or it["file"][:-3]).replace("-", " ").capitalize()
        out.append("- [%s](%s) — %s" % (title, it["file"], it["description"] or "TODO: describe"))
    return out


def new_memory(name, mtype, description, body=None):
    if not SLUG.match(name):
        raise ValueError("name must be a lowercase-kebab slug")
    if mtype not in TYPES:
        raise ValueError("type must be one of " + ", ".join(TYPES))
    body = body or ("<the fact>\n\n**Why:** <reason>\n\n**How to apply:** <when and how>"
                    if mtype in ("feedback", "project") else "<the fact>")
    return "---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n---\n\n%s\n" % (name, description, mtype, body)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    for cmd in ("lint", "index", "new"):
        p = sub.add_parser(cmd)
        p.add_argument("dir")
        p.add_argument("--index", default="MEMORY.md", help="index file name inside the folder")
        if cmd == "lint":
            p.add_argument("--root", help="project folder, to find memories that name deleted files")
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("--write", action="store_true")
        if cmd == "new":
            p.add_argument("--name", required=True)
            p.add_argument("--type", required=True, choices=TYPES)
            p.add_argument("--description", required=True)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    if a.cmd != "new" and not os.path.isdir(a.dir):
        print("not a folder: %s" % a.dir, file=sys.stderr)
        return 2
    if a.cmd == "lint":
        r = lint(a.dir, a.index, a.root)
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            print("%d memories, index ~%d tokens (loaded every session), all files ~%d tokens; %s" % (
                r["memories"], r["index_tokens"], r["total_tokens"],
                ", ".join("%s %d" % kv for kv in r["by_type"].items())))
            for kind, rows in (("ERROR", r["errors"]), ("WARN ", r["warnings"]), ("NOTE ", r["notes"])):
                for row in rows:
                    print("  %s %s" % (kind, row))
            if not (r["errors"] or r["warnings"]):
                print("  OK")
        return 1 if r["errors"] else 0
    if a.cmd == "index":
        lines = index_lines(a.dir, a.index)
        if not lines:
            print("%s already lists every memory file" % a.index)
            return 0
        path = os.path.join(a.dir, a.index)
        if a.write:
            existing = read(path) if os.path.exists(path) else ""
            with open(path, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write("\n".join(lines) + "\n")
            print("appended %d line(s) to %s" % (len(lines), path))
        else:
            print("Would append to %s (run with --write):" % path)
            print("\n".join(lines))
        return 0
    try:
        text = new_memory(a.name, a.type, a.description)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    path = os.path.join(a.dir, a.name + ".md")
    if os.path.exists(path):
        print("%s exists; update that file instead of creating a duplicate" % path, file=sys.stderr)
        return 2
    if not a.write:
        print("Would create %s (run with --write):\n%s" % (path, text))
        return 0
    os.makedirs(a.dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("created %s; replace the <...> markers, then run: memory_lint.py index %s --write" % (path, a.dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
