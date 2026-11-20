#!/usr/bin/env python3
"""token-optimizer: shrink what an AI agent reads, log token usage with timestamps, and show it on a dashboard.
Standard library only.

Reduce tokens (each prints the smaller text and records the before/after token counts in the ledger):
  log FILE                       keep errors with their context, the head and the tail; fold repeated lines
  outline FILE                   classes, functions and headings with line ranges, without their bodies
  slice FILE (--symbol NAME | --lines A-B)
                                 print only the function, class or line range you need
  json FILE                      shorten long arrays and strings, drop keys, or show only the shape
  pack PATH... --budget N        one context pack under N tokens: small files whole, big files as outlines

Track usage:
  record --skill NAME --input N --output N [--task TEXT]
                                 add one usage entry by hand (numbers from the agent's usage display)
  import [LOG...] [--auto]       read agent session logs: tokens per session and day, models, skills used
  stats [--days N]               totals, per day, per skill, and advice
  dashboard [-o FILE]            self-contained HTML dashboard (charts and tables, no internet needed)

Ledger: ~/.skill-hub/token-usage.jsonl, or $TOKEN_OPTIMIZER_LEDGER, or --ledger FILE. It holds numbers, skill,
tool and model names, file base names and short notes you type: never file or conversation content.
The dashboard also reads the skill-token-meter ledger (~/.skill-hub/token-ledger.jsonl) when it exists.

Token counts of files are estimates: characters / 4 for prose, / 3.3 for code (about +-20%).
Numbers imported from session logs are the ones the agent recorded.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_NAME = "token-optimizer"

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".ps1", ".json", ".jsonl",
            ".html", ".htm", ".xml", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".css", ".scss", ".java", ".kt",
            ".kts", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sql", ".swift",
            ".scala", ".lua", ".pl", ".r", ".dart", ".vue", ".svelte", ".gradle", ".groovy"}
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build",
             "out", "target", ".next", ".nuxt", ".gradle", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
             ".tox", "coverage", ".cache", "vendor", "Pods", "DerivedData"}
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "Cargo.lock",
             "composer.lock", "Gemfile.lock", "go.sum", "bun.lockb", "uv.lock", "gradle.lockfile"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".pdf", ".zip", ".gz", ".tgz",
            ".7z", ".rar", ".jar", ".war", ".class", ".so", ".dll", ".exe", ".bin", ".dat", ".db", ".sqlite",
            ".mp3", ".mp4", ".mov", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".map", ".pyc", ".lock",
            ".apk", ".aab", ".ipa", ".parquet", ".pkl", ".npy", ".onnx", ".pt"}
MAX_PACK_FILE_BYTES = 2_000_000


# ================================================================ counting and reading
def est_tokens(text: str, code: bool = False) -> int:
    """Estimated tokens: characters / 4 for prose, / 3.3 for code and markup."""
    if not text:
        return 0
    return int(math.ceil(len(text) / (3.3 if code else 4.0)))


def is_code(path) -> bool:
    return Path(path).suffix.lower() in CODE_EXT


def read_text(path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}")


def looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\0" in fh.read(8192)
    except OSError:
        return True


# ================================================================ 1. logs
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
IMPORTANT = re.compile(
    r"(?i)\b(error|errors|exception|traceback|fatal|fail|failed|failure|failures|panic|critical|severe|"
    r"assert|assertion|assertionerror|denied|refused|timeout|timed out|caused by|segmentation fault|"
    r"killed|oom|warn|warning|unhandled|undefined reference|cannot|could not|not found)\b"
    r"|^\s+at\s|^\s*File \".*\", line \d+")
FRAME = re.compile(r"^\s+at\s|^\s*File \".*\", line \d+|^\s+\.\.\. \d+ more")
VOLATILE = [
    (re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?"), "<ts>"),
    (re.compile(r"\b\d\d:\d\d:\d\d(?:[.,]\d+)?\b"), "<time>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<hex>"),
    (re.compile(r"\b[0-9a-f]{8,}\b"), "<id>"),
    (re.compile(r"\d+"), "<n>"),
]


def line_key(line: str) -> str:
    """The line with timestamps, ids and numbers replaced, so near-identical lines compare equal."""
    for rx, rep in VOLATILE:
        line = rx.sub(rep, line)
    return line.strip()


def compress_log(text: str, head: int = 5, tail: int = 10, context: int = 2, max_repeats: int = 3,
                 max_stack: int = 12) -> dict:
    """Keep the head, the tail, each problem line with `context` lines around it, and fold repeats.

    A problem line already shown `max_repeats` times (ignoring timestamps and numbers) is folded into a
    count at the end. Stack traces longer than `max_stack` lines keep their top 8 and bottom 4 lines.
    """
    lines = [ANSI.sub("", ln).rstrip() for ln in text.splitlines()]
    n = len(lines)
    keep = set(range(min(head, n))) | set(range(max(0, n - tail), n))
    seen = Counter()
    folded = Counter()
    folded_text = {}
    folded_frames = 0
    for i, line in enumerate(lines):
        if not IMPORTANT.search(line):
            continue
        key = line_key(line)
        seen[key] += 1
        if seen[key] > max_repeats:
            if FRAME.search(line):
                folded_frames += 1
            else:
                folded[key] += 1
                folded_text.setdefault(key, line.strip())
            continue
        keep.update(range(max(0, i - context), min(n, i + context + 1)))

    # Trim the middle of long stack traces (a run of indented lines that contains frames).
    i = 0
    while i < n:
        if lines[i][:1] in (" ", "\t") and FRAME.search(lines[i]):
            j = i
            while j + 1 < n and lines[j + 1][:1] in (" ", "\t"):
                j += 1
            if j - i + 1 > max_stack:
                keep.difference_update(range(i + 8, j - 3))
            i = j + 1
        else:
            i += 1

    out = []
    gap = 0
    prev_key = None
    repeat = 0

    def flush_repeat():
        nonlocal repeat
        if repeat:
            out.append(f"    [+{repeat} similar lines (same text, other numbers or ids)]")
            repeat = 0

    for i, line in enumerate(lines):
        if i not in keep:
            gap += 1
            continue
        if gap:
            flush_repeat()
            out.append(f"... [{gap} lines omitted]")
            gap = 0
            prev_key = None
        key = line_key(line)
        if key and key == prev_key:
            repeat += 1
            continue
        flush_repeat()
        out.append(line)
        prev_key = key
    flush_repeat()
    if gap:
        out.append(f"... [{gap} lines omitted]")
    if folded or folded_frames:
        out.append("")
        out.append(f"--- repeated problem lines (each already shown {max_repeats} times above) ---")
        for key, count in folded.most_common(20):
            out.append(f"x{count}  {folded_text[key][:200]}")
        if len(folded) > 20:
            out.append(f"... and {len(folded) - 20} more distinct repeated lines")
        if folded_frames:
            out.append(f"x{folded_frames}  repeated stack-frame lines")
    problems = sum(1 for ln in lines if IMPORTANT.search(ln) and not FRAME.search(ln))
    header = f"[token-optimizer log: {n} lines -> {len(out)} lines, {problems} problem lines]"
    result = header + "\n" + "\n".join(out) + "\n"
    return {"text": result, "lines_before": n, "lines_after": len(out), "problem_lines": problems}


# ================================================================ 2. outline and slice
DECL = re.compile(r"""^(?P<indent>[ \t]*)(?P<decl>
      (?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+[\w$]+
    | (?:export\s+)?(?:(?:abstract|final|open|data|sealed|public|private|protected|internal|static|partial|inner|enum)\s+)*
        (?:class|interface|enum|object|struct|trait|record|module|namespace|impl|protocol|extension)\s+[\w$.]+
    | (?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+\w+
    | func\s+(?:\([^)]*\)\s*)?\w+
    | (?:(?:public|private|protected|internal|override|suspend|inline|open|static|final|abstract|operator|tailrec)\s+)*fun\s+(?:<[^>]*>\s*)?[\w.]+
    | (?:export\s+)?(?:const|let|var)\s+[\w$]+\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*(?::[^=]+)?=>
    | (?:(?:public|private|protected|static|final|abstract|synchronized|override|virtual|async|internal|sealed|extern)\s+)+
        [\w<>\[\],.?]+(?:\s*<[^>]*>)?\s+\w+\s*\(
    | def\s+\w+ | sub\s+\w+ | (?:function|Function|filter)\s+[\w-]+
    )""", re.X)
DECL_NAME = re.compile(r"([\w$]+)\s*(?:\(|=|<|:|\{|$)")
MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _brace_end(lines: list, start: int) -> int:
    """Index of the line that closes the first `{` opened at or after `start`, or -1."""
    depth = 0
    opened = False
    for i in range(start, len(lines)):
        line = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|//.*$", "", lines[i])
        for ch in line:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
                if opened and depth <= 0:
                    return i
        if not opened and i - start >= 2:
            return -1
    return -1


def _python_outline(text: str) -> list:
    tree = ast.parse(text)
    lines = text.splitlines()
    items = []

    def signature(node) -> str:
        sig = []
        for ln in lines[node.lineno - 1: node.lineno + 7]:
            sig.append(ln.strip())
            if ln.rstrip().endswith(":"):
                break
        return " ".join(sig)

    def visit(nodes, depth, prefix):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                doc = (ast.get_docstring(node) or "").strip().splitlines()
                name = f"{prefix}{node.name}"
                items.append({"name": name, "short": node.name, "start": start,
                              "end": getattr(node, "end_lineno", None) or start, "depth": depth,
                              "sig": signature(node), "doc": doc[0][:100] if doc else ""})
                if isinstance(node, ast.ClassDef):
                    visit(node.body, depth + 1, name + ".")
    visit(tree.body, 0, "")
    return items


def _generic_outline(text: str, path: Path) -> list:
    lines = text.splitlines()
    items = []
    if path.suffix.lower() in (".md", ".markdown", ".rst", ".txt"):
        in_fence = False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            m = None if in_fence else MD_HEADING.match(ln)
            if m:
                items.append({"name": m.group(2), "short": m.group(2), "start": i + 1, "end": None,
                              "depth": len(m.group(1)) - 1, "sig": ln.strip(), "doc": "", "level": len(m.group(1))})
        for k, it in enumerate(items):
            nxt = next((o["start"] for o in items[k + 1:] if o["level"] <= it["level"]), len(lines) + 1)
            it["end"] = nxt - 1
        return items
    decls = []
    for i, ln in enumerate(lines):
        m = DECL.match(ln)
        if not m or ln.strip().startswith(("//", "#", "*", "/*", "return ", "new ")):
            continue
        words = re.sub(r"\b(?:export|default|async|function|class|interface|enum|object|struct|trait|record|module|"
                       r"namespace|impl|protocol|extension|pub|fn|func|fun|const|let|var|def|sub|filter|public|"
                       r"private|protected|internal|static|final|abstract|open|data|sealed|override|suspend|"
                       r"inline|synchronized|virtual|partial|inner|unsafe|operator|tailrec|extern)\b", " ",
                       m.group("decl"))
        names = DECL_NAME.findall(words.strip())
        name = names[-1] if names else m.group("decl").split()[-1]
        indent = len(m.group("indent").expandtabs(4))
        decls.append({"i": i, "indent": indent, "name": name, "sig": ln.strip()[:160]})
    for k, d in enumerate(decls):
        end = _brace_end(lines, d["i"])
        if end < 0:
            nxt = next((o["i"] for o in decls[k + 1:] if o["indent"] <= d["indent"]), len(lines))
            end = nxt - 1
            while end > d["i"] and not lines[end].strip():
                end -= 1
        parents = [o for o in items if o["depth"] < 9 and o["start"] <= d["i"] + 1 <= o["end"] and o is not d]
        depth = len(parents)
        qual = ".".join([parents[-1]["name"], d["name"]]) if parents else d["name"]
        items.append({"name": qual, "short": d["name"], "start": d["i"] + 1, "end": end + 1, "depth": depth,
                      "sig": d["sig"], "doc": ""})
    return items


def outline_items(text: str, path: Path) -> list:
    if path.suffix.lower() == ".py":
        try:
            return _python_outline(text)
        except (SyntaxError, ValueError):
            pass
    return _generic_outline(text, path)


def outline(path: Path, text: str = None) -> dict:
    text = read_text(path) if text is None else text
    items = outline_items(text, path)
    n_lines = len(text.splitlines())
    out = [f"# outline of {path.name}: {n_lines} lines, ~{est_tokens(text, is_code(path))} tokens. "
           f"Read a part with: slice {path.name} --symbol NAME (or --lines A-B)"]
    if items:
        for it in items:
            rng = f"L{it['start']}-{it['end']}"
            doc = f"  # {it['doc']}" if it.get("doc") else ""
            out.append(f"{'  ' * it['depth']}{rng:<12} {it['sig'][:160]}{doc}")
    else:
        lines = text.splitlines()
        out.append(f"(no declarations or headings found; first {min(10, len(lines))} lines)")
        out += [ln[:200] for ln in lines[:10]]
    result = "\n".join(out) + "\n"
    return {"text": result, "items": items, "lines": n_lines}


def slice_file(path: Path, symbol: str = None, lines_spec: str = None) -> dict:
    text = read_text(path)
    lines = text.splitlines()
    ranges = []
    if lines_spec:
        m = re.match(r"^\s*(\d+)\s*(?:[-:,]\s*(\d+))?\s*$", lines_spec)
        if not m:
            raise SystemExit("error: --lines must look like 120-180")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        ranges.append((max(1, min(a, b)), min(len(lines), max(a, b)), f"lines {a}-{b}"))
    if symbol:
        items = outline_items(text, path)
        hits = [it for it in items if symbol in (it["name"], it["short"])]
        if not hits:
            hits = [it for it in items if it["name"].lower().endswith(symbol.lower())]
        if not hits:
            near = difflib.get_close_matches(symbol, [it["name"] for it in items], n=5, cutoff=0.4)
            hint = f"; close names: {', '.join(near)}" if near else ""
            raise SystemExit(f"error: no symbol {symbol!r} in {path.name}{hint}")
        for it in hits:
            ranges.append((it["start"], it["end"], it["name"]))
    if not ranges:
        raise SystemExit("error: give --symbol NAME or --lines A-B")
    out = []
    for a, b, label in ranges:
        out.append(f"# {path.name} L{a}-{b} ({label}) of {len(lines)} lines")
        out += lines[a - 1:b]
    return {"text": "\n".join(out) + "\n", "ranges": [(a, b) for a, b, _ in ranges]}


# ================================================================ 3. json
def load_json_or_jsonl(text: str):
    try:
        return json.loads(text), False
    except ValueError:
        rows = []
        bad = 0
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except ValueError:
                bad += 1
        if not rows:
            raise SystemExit("error: not valid JSON or JSON Lines")
        if bad:
            print(f"note: skipped {bad} line(s) that are not JSON", file=sys.stderr)
        return rows, True


def shrink_json(obj, max_items: int = 3, max_str: int = 200, drop=()):
    """Keep the structure, cut long lists to `max_items` and long strings to `max_str` characters."""
    if isinstance(obj, dict):
        return {k: shrink_json(v, max_items, max_str, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        kept = [shrink_json(v, max_items, max_str, drop) for v in obj[:max_items]]
        if len(obj) > max_items:
            kept.append(f"... {len(obj) - max_items} more items")
        return kept
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + f"...(+{len(obj) - max_str} chars)"
    return obj


def json_shape(obj, depth: int = 0):
    """The keys and value types only: what an agent needs to write code against the data."""
    if depth > 12:
        return "..."
    if isinstance(obj, dict):
        return {k: json_shape(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return []
        merged = {}
        if all(isinstance(v, dict) for v in obj[:50]):
            for v in obj[:50]:
                for k, val in v.items():
                    merged.setdefault(k, json_shape(val, depth + 1))
            return [f"<{len(obj)} items>", merged]
        return [f"<{len(obj)} items>", json_shape(obj[0], depth + 1)]
    if obj is None:
        return "null"
    return type(obj).__name__.replace("str", "string").replace("float", "number").replace("int", "number")


def compact_json(text: str, max_items: int = 3, max_str: int = 200, drop=(), shape: bool = False,
                 indent: int = None) -> dict:
    data, jsonl = load_json_or_jsonl(text)
    result = json_shape(data) if shape else shrink_json(data, max_items, max_str, set(drop))
    sep = (",", ":") if indent is None else (",", ": ")
    if jsonl and not shape and isinstance(result, list):
        body = "\n".join(json.dumps(r, ensure_ascii=False, separators=sep) for r in result)
    else:
        body = json.dumps(result, ensure_ascii=False, separators=sep, indent=indent)
    return {"text": body + "\n", "jsonl": jsonl}


# ================================================================ 4. context pack
def _git_files(directory: Path):
    try:
        res = subprocess.run(["git", "-C", str(directory), "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return [directory / p for p in res.stdout.splitlines() if p.strip()]


def _walk_files(directory: Path):
    out = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        out += [Path(root) / f for f in sorted(files)]
    return out


def collect_files(paths, use_git: bool = True) -> list:
    found = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_file():
            found.append(p)
        elif p.is_dir():
            files = _git_files(p) if use_git else None
            found += files if files is not None else _walk_files(p)
        else:
            raise SystemExit(f"error: {raw} not found")
    out = []
    seen = set()
    for f in found:
        key = str(f.resolve())
        if key in seen or not f.is_file():
            continue
        seen.add(key)
        if (f.name in LOCKFILES or f.suffix.lower() in SKIP_EXT or f.name.endswith((".min.js", ".min.css"))
                or any(part in SKIP_DIRS for part in f.parts)):
            continue
        try:
            if f.stat().st_size > MAX_PACK_FILE_BYTES or looks_binary(f):
                continue
        except OSError:
            continue
        out.append(f)
    return out


def _rel(path: Path, bases) -> str:
    for b in bases:
        try:
            return path.resolve().relative_to(Path(b).resolve()).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def build_pack(paths, budget: int, focus=(), use_git: bool = True) -> dict:
    """Fit as much as possible into `budget` tokens: every file starts as an outline (or just its name),
    then files are upgraded to full text, files matching `focus` first, then the smallest first."""
    files = collect_files(paths, use_git)
    bases = [p for p in paths if Path(p).is_dir()] or [Path.cwd()]
    entries = []
    for f in files:
        text = read_text(f)
        rel = _rel(f, bases)
        code = is_code(f)
        full = f"## {rel}\n```\n{text.rstrip()}\n```\n"
        ol = outline(f, text)["text"]
        outl = f"## {rel} (outline)\n```\n{ol.rstrip()}\n```\n"
        name = f"- {rel} (~{est_tokens(text, code)} tokens, not included)\n"
        hits = sum(text.lower().count(t.lower()) for t in focus) if focus else 0
        entries.append({"rel": rel, "full": full, "outline": outl, "name": name, "mode": "outline", "hits": hits,
                        "cost": {"full": est_tokens(full, code), "outline": est_tokens(outl, code),
                                 "name": est_tokens(name)}, "original": est_tokens(text, code)})

    def used():
        return sum(e["cost"][e["mode"]] for e in entries)

    for e in sorted(entries, key=lambda e: -e["cost"]["outline"]):
        if used() <= budget:
            break
        e["mode"] = "name"
    for e in sorted(entries, key=lambda e: (-e["hits"], e["cost"]["full"])):
        extra = e["cost"]["full"] - e["cost"][e["mode"]]
        if used() + extra <= budget:
            e["mode"] = "full"
    total = used()
    original = sum(e["original"] for e in entries)
    counts = Counter(e["mode"] for e in entries)
    parts = [f"# context pack: ~{total} of {budget} tokens; {counts['full']} files whole, "
             f"{counts['outline']} as outlines, {counts['name']} listed only (all files: ~{original} tokens)\n"]
    for mode in ("full", "outline"):
        parts += [e[mode] for e in sorted(entries, key=lambda e: e["rel"]) if e["mode"] == mode]
    listed = [e["name"] for e in sorted(entries, key=lambda e: e["rel"]) if e["mode"] == "name"]
    if listed:
        parts.append("## not included (ask for a slice if needed)\n" + "".join(listed))
    return {"text": "\n".join(parts), "tokens": total, "original": original, "files": len(entries),
            "full": counts["full"], "outlined": counts["outline"], "listed": counts["name"]}


# ================================================================ ledger
def ledger_path(explicit=None) -> Path:
    return Path(explicit or os.environ.get("TOKEN_OPTIMIZER_LEDGER")
                or Path.home() / ".skill-hub" / "token-usage.jsonl").expanduser()


def meter_ledger_path(explicit=None) -> Path:
    return Path(explicit or os.environ.get("SKILL_TOKEN_LEDGER")
                or Path.home() / ".skill-hub" / "token-ledger.jsonl").expanduser()


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_events(path: Path) -> list:
    events = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict):
                events.append(e)
    return events


def append_event(event: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_events(events: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def optimize_event(tool: str, source: str, before: int, after: int, skill: str = SKILL_NAME, note: str = "") -> dict:
    e = {"time": now_iso(), "kind": "optimize", "tool": tool, "skill": skill or SKILL_NAME,
         "source": Path(source).name if source else "", "before": int(before), "after": int(after),
         "saved": int(before) - int(after)}
    if note:
        e["note"] = note[:200]
    return e


# ================================================================ session-log import
IN_KEYS = ("input_tokens", "prompt_tokens", "promptTokenCount", "inputTokens", "prompt_token_count")
OUT_KEYS = ("output_tokens", "completion_tokens", "candidatesTokenCount", "outputTokens", "completion_token_count")
CACHE_READ_KEYS = ("cache_read_input_tokens", "cachedContentTokenCount", "cache_read_tokens")
CACHE_WRITE_KEYS = ("cache_creation_input_tokens", "cache_write_tokens")
TIME_KEYS = ("timestamp", "time", "created_at", "createdAt", "ts", "date")
CALL_TYPES = {"tool_use", "function_call", "tool_call", "toolcall", "functioncall", "server_tool_use",
              "custom_tool_call", "local_shell_call"}
SKILL_PATH = re.compile(r"[\\/]+([a-z0-9][a-z0-9-]{1,63})[\\/]+SKILL\.md")
SKILL_SCRIPT = re.compile(r"skills[\\/]+(?:[\w.-]+[\\/]+){0,3}?([a-z0-9][a-z0-9-]{1,63})[\\/]+scripts[\\/]+\w")
ISO = re.compile(r"(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d)(?::(\d\d))?(?:[.,]\d+)?)?\s*(Z|[+-]\d\d:?\d\d)?$")

# Where some agents keep their session logs (JSON / JSONL with usage records). Used by `import --auto`.
KNOWN_LOG_DIRS = {
    "claude-code": "~/.claude/projects",
    "codex": "~/.codex/sessions",
    "gemini-cli": "~/.gemini/tmp",
    "opencode": "~/.local/share/opencode/storage",
}


def parse_time(value):
    """An aware datetime from an ISO string or epoch seconds / milliseconds, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:
            value /= 1000.0
        if 1e9 < value < 1e11:
            return dt.datetime.fromtimestamp(value, dt.timezone.utc)
        return None
    if not isinstance(value, str):
        return None
    m = ISO.match(value.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, tz = m.groups()
    try:
        base = dt.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    except ValueError:
        return None
    if tz in (None, ""):
        return base.astimezone()
    if tz == "Z":
        return base.replace(tzinfo=dt.timezone.utc)
    sign = 1 if tz[0] == "+" else -1
    hh, mm = int(tz[1:3]), int(tz[-2:])
    return base.replace(tzinfo=dt.timezone(sign * dt.timedelta(hours=hh, minutes=mm)))


def _find_time(obj):
    if not isinstance(obj, dict):
        return None
    for k in TIME_KEYS:
        t = parse_time(obj.get(k))
        if t:
            return t
    for k in ("message", "payload", "response", "data"):
        sub = obj.get(k)
        if isinstance(sub, dict):
            for key in TIME_KEYS:
                t = parse_time(sub.get(key))
                if t:
                    return t
    return None


def _usage_dicts(obj):
    if isinstance(obj, dict):
        if any(k in obj for k in IN_KEYS + OUT_KEYS):
            yield obj
            return
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith(("total_", "cumulative")):
                continue    # running totals repeat the per-turn numbers
            yield from _usage_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _usage_dicts(v)


def _first_num(d: dict, keys) -> int:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return 0


def _record_id(obj):
    if not isinstance(obj, dict):
        return None
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    return msg.get("id") or obj.get("requestId") or obj.get("response_id")


def _model_of(obj):
    if not isinstance(obj, dict):
        return None
    for holder in (obj, obj.get("message"), obj.get("payload"), obj.get("response")):
        if isinstance(holder, dict):
            m = holder.get("model") or holder.get("modelVersion")
            if isinstance(m, str) and m and not m.startswith("<"):
                return m[:60]
    return None


def _tool_calls(obj):
    """Yield each tool / function call dict found in a record."""
    if isinstance(obj, dict):
        t = obj.get("type")
        if isinstance(t, str) and t.lower() in CALL_TYPES:
            yield obj
            return
        if "functionCall" in obj and isinstance(obj["functionCall"], dict):
            yield obj["functionCall"]
            return
        for v in obj.values():
            yield from _tool_calls(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _tool_calls(v)


def skills_in_call(call: dict) -> set:
    """Skill names a tool call used: an explicit `skill` argument, a path to a skill's SKILL.md,
    or a script run from a skill's scripts/ folder."""
    args = None
    for k in ("input", "arguments", "args", "parameters", "action"):
        if k in call:
            args = call[k]
            break
    if args is None and isinstance(call.get("function"), dict):
        args = call["function"].get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            pass
    found = set()
    if isinstance(args, dict):
        val = args.get("skill") or args.get("skill_name")
        if isinstance(val, str) and val.strip():
            found.add(val.strip().lstrip("/").split()[0][:64])
    raw = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    found.update(SKILL_PATH.findall(raw))
    found.update(SKILL_SCRIPT.findall(raw))
    return found


def _iter_records(text: str):
    try:
        data = json.loads(text)
    except ValueError:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(("{", "[")):
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
        return
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict) and isinstance(data.get("messages"), list):
        for m in data["messages"]:
            yield m
    else:
        yield data


def scan_session(path: Path, agent: str = "unknown") -> list:
    """One usage event per (session file, local day) with tokens, models, tool calls and skills used."""
    text = read_text(path)
    session = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    fallback = dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    buckets = {}
    seen_ids = set()
    last_time = None
    for rec in _iter_records(text):
        t = _find_time(rec) or last_time
        if t is not None:
            last_time = t
        local = (t or fallback).astimezone()
        day = local.date().isoformat()
        b = buckets.get(day)
        if b is None:
            b = buckets[day] = {"start": local, "end": local, "input": 0, "output": 0, "cache_read": 0,
                                "cache_write": 0, "messages": 0, "tool_calls": 0, "skills": Counter(),
                                "models": Counter()}
        b["start"] = min(b["start"], local)
        b["end"] = max(b["end"], local)
        rid = _record_id(rec)
        if not (rid and rid in seen_ids):
            got = False
            for u in _usage_dicts(rec):
                got = True
                b["input"] += _first_num(u, IN_KEYS)
                b["output"] += _first_num(u, OUT_KEYS)
                b["cache_read"] += _first_num(u, CACHE_READ_KEYS)
                b["cache_write"] += _first_num(u, CACHE_WRITE_KEYS)
            if got:
                b["messages"] += 1
                model = _model_of(rec)
                if model:
                    b["models"][model] += 1
                if rid:
                    seen_ids.add(rid)
        for call in _tool_calls(rec):
            b["tool_calls"] += 1
            for s in skills_in_call(call):
                b["skills"][s] += 1
    events = []
    for day, b in sorted(buckets.items()):
        total = b["input"] + b["output"] + b["cache_read"] + b["cache_write"]
        if not total and not b["tool_calls"]:
            continue
        events.append({"time": b["start"].isoformat(timespec="seconds"),
                       "end": b["end"].isoformat(timespec="seconds"), "kind": "usage",
                       "id": f"{session}:{day}", "session": session, "agent": agent,
                       "input": b["input"], "output": b["output"], "cache_read": b["cache_read"],
                       "cache_write": b["cache_write"], "total": total, "messages": b["messages"],
                       "tool_calls": b["tool_calls"], "skills": dict(b["skills"]),
                       "models": dict(b["models"])})
    return events


def find_logs(paths=(), auto: bool = False, since_days: float = None) -> list:
    """(path, agent) pairs for every JSON / JSONL log under the given paths and, with auto, the known dirs."""
    targets = [(Path(p).expanduser(), None) for p in paths]
    if auto:
        targets += [(Path(d).expanduser(), agent) for agent, d in KNOWN_LOG_DIRS.items()]
    cutoff = None
    if since_days is not None:
        cutoff = dt.datetime.now().timestamp() - since_days * 86400
    out = []
    for p, agent in targets:
        if p.is_file():
            files = [p]
        elif p.is_dir():
            files = sorted(f for f in p.rglob("*") if f.suffix.lower() in (".jsonl", ".json") and f.is_file())
        else:
            if not auto or agent is None:
                raise SystemExit(f"error: {p} not found")
            continue
        for f in files:
            try:
                if cutoff and f.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            out.append((f, agent))
    return out


def import_logs(logs, ledger: Path, agent: str = None) -> dict:
    """Scan session logs and replace their earlier entries in the ledger (re-importing is safe)."""
    new = []
    for f, found_agent in logs:
        try:
            new += scan_session(f, agent or found_agent or "unknown")
        except (OSError, RecursionError):
            continue
    ids = {e["id"] for e in new}
    kept = [e for e in read_events(ledger) if e.get("id") not in ids]
    events = sorted(kept + new, key=lambda e: e.get("time", ""))
    write_events(events, ledger)
    return {"files": len(logs), "events": len(new), "tokens": sum(e["total"] for e in new),
            "skills": dict(sum((Counter(e["skills"]) for e in new), Counter())), "ledger": str(ledger)}


# ================================================================ summary and advice
def _local_day(iso: str) -> str:
    t = parse_time(iso or "")
    return t.astimezone().date().isoformat() if t else (iso or "")[:10]


def summarize(events: list, meter_events=(), days: float = None) -> dict:
    """Everything the stats command and the dashboard show, from ledger events."""
    if days is not None:
        cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=days)

        def recent(e):
            t = parse_time(e.get("time", ""))
            return t is not None and t >= cutoff
        events = [e for e in events if recent(e)]
        meter_events = [e for e in meter_events if recent(e)]
    usage = [e for e in events if e.get("kind") == "usage"]
    opt = [e for e in events if e.get("kind") == "optimize"]
    tok_keys = ("input", "output", "cache_read", "cache_write")
    totals = {k: sum(int(e.get(k) or 0) for e in usage) for k in tok_keys}
    totals["total"] = sum(totals.values())
    totals["sessions"] = len({e.get("session") or e.get("id") for e in usage})
    totals["messages"] = sum(int(e.get("messages") or 0) for e in usage)
    totals["tool_calls"] = sum(int(e.get("tool_calls") or 0) for e in usage)
    totals["opt_runs"] = len(opt)
    totals["opt_before"] = sum(int(e.get("before") or 0) for e in opt)
    totals["opt_saved"] = sum(int(e.get("saved") or 0) for e in opt)
    totals["meter_saved"] = sum(int(e.get("saved") or 0) for e in meter_events)

    per_day = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0,
                                   "opt_saved": 0, "meter_saved": 0, "sessions": 0})
    for e in usage:
        d = per_day[_local_day(e.get("time"))]
        for k in tok_keys:
            d[k] += int(e.get(k) or 0)
        d["total"] += int(e.get("total") or 0)
        d["sessions"] += 1
    for e in opt:
        per_day[_local_day(e.get("time"))]["opt_saved"] += int(e.get("saved") or 0)
    for e in meter_events:
        per_day[_local_day(e.get("time"))]["meter_saved"] += int(e.get("saved") or 0)

    skills = {}

    def skill_row(name):
        return skills.setdefault(name, {"skill": name, "uses": 0, "sessions": set(), "tokens": 0, "opt_runs": 0,
                                        "opt_saved": 0, "meter_uses": 0, "meter_saved": 0, "first": "",
                                        "last": ""})

    def touch(row, *times):
        for t in times:
            if t:
                row["first"] = min(row["first"] or t, t)
                row["last"] = max(row["last"], t)

    for e in usage:
        for name, count in (e.get("skills") or {}).items():
            r = skill_row(name)
            r["uses"] += int(count)
            r["sessions"].add(e.get("session") or e.get("id"))
            r["tokens"] += int(e.get("total") or 0)
            touch(r, e.get("time"), e.get("end"))
    for e in opt:
        r = skill_row(e.get("skill") or SKILL_NAME)
        r["opt_runs"] += 1
        r["opt_saved"] += int(e.get("saved") or 0)
        touch(r, e.get("time"))
    for e in meter_events:
        r = skill_row(e.get("skill") or "?")
        r["meter_uses"] += 1
        r["meter_saved"] += int(e.get("saved") or 0)
        touch(r, e.get("time"))
    skill_rows = []
    for r in skills.values():
        r["sessions"] = len(r["sessions"])
        skill_rows.append(r)
    skill_rows.sort(key=lambda r: (-(r["uses"] + r["opt_runs"] + r["meter_uses"]), r["skill"]))

    tools = {}
    for e in opt:
        t = tools.setdefault(e.get("tool", "?"), {"tool": e.get("tool", "?"), "runs": 0, "before": 0, "after": 0,
                                                  "saved": 0})
        t["runs"] += 1
        t["before"] += int(e.get("before") or 0)
        t["after"] += int(e.get("after") or 0)
        t["saved"] += int(e.get("saved") or 0)
    tool_rows = sorted(tools.values(), key=lambda t: -t["saved"])
    for t in tool_rows:
        t["percent"] = round(100.0 * t["saved"] / t["before"], 1) if t["before"] else 0.0

    models = Counter()
    agents = Counter()
    for e in usage:
        for m, c in (e.get("models") or {}).items():
            models[m] += int(c)
        agents[e.get("agent") or "unknown"] += int(e.get("total") or 0)

    activity = []
    for e in events:
        activity.append(dict(e))
    for e in meter_events:
        activity.append({"time": e.get("time", ""), "kind": "skill-saving", "skill": e.get("skill"),
                         "saved": e.get("saved"), "total": e.get("with"), "note": e.get("task", ""),
                         "method": e.get("method")})
    activity.sort(key=lambda e: e.get("time", ""), reverse=True)

    times = [e.get("time") for e in events + list(meter_events) if e.get("time")]
    summary = {"totals": totals, "days": dict(sorted(per_day.items())), "skills": skill_rows, "tools": tool_rows,
               "models": dict(models.most_common()), "agents": dict(agents.most_common()),
               "recent": activity[:50], "first": min(times) if times else "", "last": max(times) if times else ""}
    summary["advice"] = advice(summary, usage)
    return summary


def advice(s: dict, usage: list) -> list:
    """Short, data-driven tips; each names the number that triggered it."""
    t = s["totals"]
    tips = []
    if not usage and not t["opt_runs"]:
        return ["No data yet. Run `import --auto` (or `import <session log>`) and use the optimizer commands, "
                "then rebuild the dashboard."]
    prompt_side = t["input"] + t["cache_read"] + t["cache_write"]
    if prompt_side and t["sessions"] >= 3:
        share = t["cache_read"] / prompt_side
        if share < 0.5:
            tips.append(f"Only {share:.0%} of prompt tokens were cache reads. Keep instructions and reference "
                        "files first and unchanged between requests, and put the changing question last, so "
                        "provider caching can reuse them.")
    fresh = t["input"] + t["output"] + t["cache_write"]
    if fresh and t["output"] / fresh > 0.25:
        tips.append(f"Output is {t['output'] / fresh:.0%} of fresh tokens and usually costs several times more "
                    "than input. Ask for diffs or changed parts only, and short answers when detail adds nothing.")
    totals = sorted(int(e.get("total") or 0) for e in usage)
    if len(totals) >= 4:
        median = totals[len(totals) // 2]
        big = [e for e in usage if median and int(e.get("total") or 0) > 4 * median]
        if big:
            worst = max(big, key=lambda e: int(e.get("total") or 0))
            tips.append(f"{len(big)} session-day(s) used over 4x the median ({fmt(median)} tokens); the largest "
                        f"was {fmt(int(worst.get('total') or 0))} on {_local_day(worst.get('time'))}. Long "
                        "sessions resend their whole history: restart with a short handoff note instead.")
    if usage and not t["opt_runs"]:
        tips.append("No optimizer runs recorded. Before pasting a log, a large file or a JSON dump, run "
                    "`log`, `outline` / `slice`, or `json --shape` and read the short version.")
    for tool in s["tools"]:
        if tool["runs"] >= 3 and tool["percent"] < 15:
            tips.append(f"`{tool['tool']}` saved only {tool['percent']}% over {tool['runs']} runs; its inputs "
                        "are already small, so read them directly.")
    if t["tool_calls"] and t["sessions"] >= 3 and not s["skills"]:
        tips.append("No skill use was detected in the imported sessions. Skills with scripts usually save the "
                    "most tokens: search the catalog before writing one-off code.")
    return tips or ["Usage looks lean. Keep using the optimizer commands before reading large inputs."]


def fmt(n) -> str:
    n = int(n or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            return f"{n / div:.1f}{suf}"
    return str(n)


# ================================================================ CLI
def _emit(text: str, out_path) -> None:
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _report_saving(tool, before, after, args, source="", note=""):
    saved = before - after
    pct = 100.0 * saved / before if before else 0.0
    msg = f"[{tool}] ~{before:,} -> ~{after:,} tokens (saved ~{saved:,}, {pct:.0f}%)"
    if not args.no_record:
        path = ledger_path(args.ledger)
        append_event(optimize_event(tool, source, before, after, args.skill, note), path)
        msg += f"; recorded in {path}"
    print(msg, file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ledger", help="ledger file (default ~/.skill-hub/token-usage.jsonl)")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    rec = argparse.ArgumentParser(add_help=False)
    rec.add_argument("-o", "--out", help="write the result to this file instead of printing it")
    rec.add_argument("--no-record", action="store_true", help="do not add this run to the ledger")
    rec.add_argument("--skill", default=SKILL_NAME,
                     help="the skill whose task this run served (shown per skill on the dashboard)")

    p = argparse.ArgumentParser(prog="token_optimizer.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("log", parents=[common, rec], help="compress a log to its problems")
    s.add_argument("file")
    s.add_argument("--head", type=int, default=5)
    s.add_argument("--tail", type=int, default=10)
    s.add_argument("--context", type=int, default=2, help="lines kept around each problem line")
    s.add_argument("--max-repeats", type=int, default=3, help="times a repeated problem line is shown")

    s = sub.add_parser("outline", parents=[common, rec], help="declarations and headings with line ranges")
    s.add_argument("file")

    s = sub.add_parser("slice", parents=[common, rec], help="only one symbol or line range of a file")
    s.add_argument("file")
    s.add_argument("--symbol", help="function, class or heading name (Class.method works)")
    s.add_argument("--lines", help="line range, e.g. 120-180")

    s = sub.add_parser("json", parents=[common, rec], help="shrink JSON / JSON Lines")
    s.add_argument("file")
    s.add_argument("--max-items", type=int, default=3)
    s.add_argument("--max-str", type=int, default=200)
    s.add_argument("--drop", default="", help="comma-separated keys to remove everywhere")
    s.add_argument("--shape", action="store_true", help="keys and value types only")
    s.add_argument("--indent", type=int, help="pretty-print (costs more tokens)")

    s = sub.add_parser("pack", parents=[common, rec], help="context pack of files under a token budget")
    s.add_argument("paths", nargs="+")
    s.add_argument("--budget", type=int, default=8000)
    s.add_argument("--focus", action="append", default=[], help="term; files containing it are kept whole first")
    s.add_argument("--no-git", action="store_true", help="walk folders instead of asking git for the file list")

    s = sub.add_parser("record", parents=[common], help="add one usage entry by hand")
    s.add_argument("--skill", default="", help="skill used in this task (comma-separated for several)")
    s.add_argument("--input", type=int, default=0)
    s.add_argument("--output", type=int, default=0)
    s.add_argument("--cache-read", type=int, default=0)
    s.add_argument("--cache-write", type=int, default=0)
    s.add_argument("--agent", default="unknown")
    s.add_argument("--model", default="")
    s.add_argument("--task", default="", help="short note, no secrets")

    s = sub.add_parser("import", parents=[common], help="import token usage from agent session logs")
    s.add_argument("logs", nargs="*", help="log files or folders (JSON / JSONL)")
    s.add_argument("--auto", action="store_true", help="also scan the known session-log folders")
    s.add_argument("--agent", help="label for these logs (default: from the known folder, else unknown)")
    s.add_argument("--since", type=float, help="only logs changed in the last N days")
    s.add_argument("--list-dirs", action="store_true", help="show the known session-log folders and exit")

    for name, helptext in (("stats", "totals, per day, per skill, advice"), ("dashboard", "write the HTML dashboard")):
        s = sub.add_parser(name, parents=[common], help=helptext)
        s.add_argument("--days", type=float, help="only the last N days")
        s.add_argument("--meter-ledger", help="skill-token-meter ledger (default ~/.skill-hub/token-ledger.jsonl)")
        s.add_argument("--no-meter", action="store_true", help="ignore the skill-token-meter ledger")
        if name == "dashboard":
            s.add_argument("-o", "--out", help="HTML file (default ~/.skill-hub/token-dashboard.html)")
            s.add_argument("--open", action="store_true", help="open it in the default browser")
            s.add_argument("--title", default="Token usage dashboard")
    return p


def _summary_from_args(a) -> dict:
    events = read_events(ledger_path(a.ledger))
    meter = [] if a.no_meter else read_events(meter_ledger_path(a.meter_ledger))
    return summarize(events, meter, a.days)


def print_stats(s: dict) -> None:
    t = s["totals"]
    span = f"{s['first'][:16]} .. {s['last'][:16]}" if s["first"] else "no data"
    print(f"Period: {span}")
    print(f"Tokens used: {t['total']:,}  (input {t['input']:,}, output {t['output']:,}, cache read "
          f"{t['cache_read']:,}, cache write {t['cache_write']:,})")
    print(f"Sessions: {t['sessions']}, model replies: {t['messages']:,}, tool calls: {t['tool_calls']:,}")
    print(f"Optimizer: {t['opt_runs']} runs saved ~{t['opt_saved']:,} tokens; skill-token-meter savings: "
          f"~{t['meter_saved']:,}")
    if s["days"]:
        print("\nPer day                  total      output   opt saved  sessions")
        for day, d in list(s["days"].items())[-14:]:
            print(f"  {day}  {d['total']:>14,} {d['output']:>11,} {d['opt_saved']:>11,} {d['sessions']:>9}")
    if s["skills"]:
        print("\nSkills        uses  sessions   opt saved  meter saved  last used")
        for r in s["skills"][:20]:
            print(f"  {r['skill'][:28]:<28} {r['uses']:>5} {r['sessions']:>9} {r['opt_saved']:>11,} "
                  f"{r['meter_saved']:>12,}  {r['last'][:16]}")
    if s["tools"]:
        print("\nOptimizer tool  runs      before       saved      %")
        for r in s["tools"]:
            print(f"  {r['tool']:<12} {r['runs']:>5} {r['before']:>11,} {r['saved']:>11,} {r['percent']:>6}")
    print("\nAdvice:")
    for tip in s["advice"]:
        print(f"  - {tip}")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    a = build_parser().parse_args(argv)

    if a.cmd == "log":
        text = read_text(a.file)
        r = compress_log(text, a.head, a.tail, a.context, a.max_repeats)
        before, after = est_tokens(text), est_tokens(r["text"])
        if a.json:
            r = {**r, "tokens_before": before, "tokens_after": after}
            _emit(json.dumps(r, indent=2) + "\n", a.out)
        else:
            _emit(r["text"], a.out)
        _report_saving("log", before, after, a, a.file)
    elif a.cmd == "outline":
        path = Path(a.file)
        text = read_text(path)
        r = outline(path, text)
        before, after = est_tokens(text, is_code(path)), est_tokens(r["text"], is_code(path))
        _emit(json.dumps(r["items"], indent=2) + "\n" if a.json else r["text"], a.out)
        _report_saving("outline", before, after, a, a.file)
    elif a.cmd == "slice":
        path = Path(a.file)
        text = read_text(path)
        r = slice_file(path, a.symbol, a.lines)
        before, after = est_tokens(text, is_code(path)), est_tokens(r["text"], is_code(path))
        _emit(json.dumps(r, indent=2) + "\n" if a.json else r["text"], a.out)
        _report_saving("slice", before, after, a, a.file)
    elif a.cmd == "json":
        text = read_text(a.file)
        drop = [k.strip() for k in a.drop.split(",") if k.strip()]
        r = compact_json(text, a.max_items, a.max_str, drop, a.shape, a.indent)
        _emit(r["text"], a.out)
        _report_saving("json-shape" if a.shape else "json", est_tokens(text, True), est_tokens(r["text"], True),
                       a, a.file)
    elif a.cmd == "pack":
        r = build_pack(a.paths, a.budget, a.focus, not a.no_git)
        if a.json:
            _emit(json.dumps({k: v for k, v in r.items() if k != "text"}, indent=2) + "\n", a.out)
        else:
            _emit(r["text"], a.out)
        _report_saving("pack", r["original"], r["tokens"], a,
                       Path(a.paths[0]).resolve().name if len(a.paths) == 1 else "",
                       f"{r['files']} files, budget {a.budget}")
    elif a.cmd == "record":
        skills = [s.strip() for s in a.skill.split(",") if s.strip()]
        total = a.input + a.output + a.cache_read + a.cache_write
        if not total:
            raise SystemExit("error: give at least one of --input, --output, --cache-read, --cache-write")
        stamp = now_iso()
        e = {"time": stamp, "end": stamp, "kind": "usage", "id": f"manual:{stamp}:{hashlib.sha1(os.urandom(8)).hexdigest()[:6]}",
             "agent": a.agent, "input": a.input, "output": a.output, "cache_read": a.cache_read,
             "cache_write": a.cache_write, "total": total, "messages": 1, "tool_calls": 0,
             "skills": {s: 1 for s in skills}, "models": {a.model: 1} if a.model else {}}
        if a.task:
            e["task"] = a.task[:200]
        e["session"] = e["id"]
        path = ledger_path(a.ledger)
        append_event(e, path)
        print(json.dumps(e) if a.json else f"Recorded {total:,} tokens at {stamp} in {path}")
    elif a.cmd == "import":
        if a.list_dirs:
            for agent, d in KNOWN_LOG_DIRS.items():
                p = Path(d).expanduser()
                print(f"{agent:<12} {p}  {'(found)' if p.exists() else '(not found)'}")
            return 0
        if not a.logs and not a.auto:
            raise SystemExit("error: give log files or folders, or --auto")
        logs = find_logs(a.logs, a.auto, a.since)
        r = import_logs(logs, ledger_path(a.ledger), a.agent)
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"Imported {r['events']} session-day entries from {r['files']} log files "
                  f"({r['tokens']:,} tokens) into {r['ledger']}")
            if r["skills"]:
                top = ", ".join(f"{k} x{v}" for k, v in Counter(r["skills"]).most_common(10))
                print(f"Skills detected: {top}")
    elif a.cmd == "stats":
        s = _summary_from_args(a)
        if a.json:
            print(json.dumps(s, indent=2, default=str))
        else:
            print_stats(s)
    elif a.cmd == "dashboard":
        sys.path.insert(0, str(HERE))
        from token_dashboard import render
        s = _summary_from_args(a)
        sources = [str(ledger_path(a.ledger))]
        if not a.no_meter and meter_ledger_path(a.meter_ledger).is_file():
            sources.append(str(meter_ledger_path(a.meter_ledger)))
        html_text = render(s, title=a.title, generated=now_iso(), sources=sources, days=a.days)
        out = Path(a.out).expanduser() if a.out else Path.home() / ".skill-hub" / "token-dashboard.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")
        print(json.dumps({"dashboard": str(out)}) if a.json else f"Dashboard written to {out}")
        if a.open:
            import webbrowser
            webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
