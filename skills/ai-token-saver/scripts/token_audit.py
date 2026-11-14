#!/usr/bin/env python3
"""Audit a project for AI token waste. Standard library only, model-neutral.

Usage: python token_audit.py [DIR] [--top N] [--json] [--limit-tokens N]

Tokens are estimated as characters / 4 (a rough average for English and code
across common tokenizers, accurate to about +-25%). Nothing is executed or modified.
"""
import argparse
import fnmatch
import json
import os
import sys

HEAVY_DIRS = {"node_modules", "dist", "build", "out", "target", ".venv", "venv", "env",
              "__pycache__", ".next", ".nuxt", ".gradle", "Pods", "vendor", "coverage",
              ".tox", ".mypy_cache", ".pytest_cache", ".idea", ".terraform", "bin", "obj"}
ALWAYS_SKIP = {".git", ".hg", ".svn"}
NOISE_PATTERNS = [
    ("lockfile", ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock",
                  "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum", "gradle.lockfile"]),
    ("minified/bundle", ["*.min.js", "*.min.css", "*.bundle.js", "*.map"]),
    ("log", ["*.log"]),
    ("data dump", ["*.csv", "*.tsv", "*.jsonl", "*.sql", "*.dump", "*.ndjson"]),
    ("generated", ["*_pb2.py", "*.pb.go", "*.generated.*", "*.snap"]),
]
INSTRUCTION_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules",
                     ".github/copilot-instructions.md", "CONVENTIONS.md", "QWEN.md"]
IGNORE_FILES = [".gitignore", ".cursorignore", ".aiderignore", ".codeiumignore", ".geminiignore",
                ".copilotignore", ".clineignore", ".continueignore"]
INSTRUCTION_WARN = 2000   # tokens loaded on every request
FILE_WARN = 8000          # tokens for one file


def est_tokens(nchars):
    return (nchars + 3) // 4


def is_text(path):
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
    except OSError:
        return False
    return b"\0" not in chunk


def noise_kind(name):
    for kind, pats in NOISE_PATTERNS:
        if any(fnmatch.fnmatch(name, p) for p in pats):
            return kind
    return None


def audit(root, top, limit):
    files, heavy, noise, skipped_bin = [], {}, [], 0
    for dirpath, dirs, names in os.walk(root):
        keep = []
        for d in dirs:
            if d in ALWAYS_SKIP:
                continue
            if d in HEAVY_DIRS:
                heavy[os.path.relpath(os.path.join(dirpath, d), root)] = None
                continue
            keep.append(d)
        dirs[:] = keep
        for n in names:
            p = os.path.join(dirpath, n)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if not is_text(p):
                skipped_bin += 1
                continue
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            tokens = est_tokens(size)  # bytes ~ chars for code
            files.append((rel, tokens))
            kind = noise_kind(n)
            if kind and tokens > 500:
                noise.append((rel, tokens, kind))
    files.sort(key=lambda x: -x[1])
    noise.sort(key=lambda x: -x[1])
    instr = [(f, est_tokens(os.path.getsize(os.path.join(root, f))))
             for f in INSTRUCTION_FILES if os.path.isfile(os.path.join(root, f))]
    ignores = [f for f in IGNORE_FILES if os.path.isfile(os.path.join(root, f))]
    total = sum(t for _, t in files)
    tips = []
    for f, t in instr:
        if t > INSTRUCTION_WARN:
            tips.append(f"{f} is ~{t} tokens and is sent with every request; trim it below {INSTRUCTION_WARN} "
                        "and move detail into files read on demand.")
    if heavy:
        tips.append("Exclude from the AI tool's index/context: " + ", ".join(sorted({os.path.basename(h) for h in heavy})) + ".")
    for f, t, k in noise[:5]:
        tips.append(f"Exclude {k} file {f} (~{t} tokens); never paste it whole.")
    for f, t in files[:top]:
        if t > FILE_WARN:
            tips.append(f"{f} is ~{t} tokens; ask for a function or line range instead of the whole file, or split it.")
    if not [i for i in ignores if i != ".gitignore"]:
        tips.append("No AI-tool ignore file found (see references/tools.md for the one your IDE reads).")
    if limit and total > limit:
        tips.append(f"Project text is ~{total} tokens, above your {limit} budget: never load it all; "
                    "search first, then open small slices.")
    return {"root": os.path.abspath(root), "text_files": len(files), "binary_files_skipped": skipped_bin,
            "total_tokens_est": total, "largest": [{"file": f, "tokens": t} for f, t in files[:top]],
            "noise": [{"file": f, "tokens": t, "kind": k} for f, t, k in noise[:top]],
            "heavy_dirs": sorted(heavy), "instruction_files": [{"file": f, "tokens": t} for f, t in instr],
            "ignore_files": ignores, "tips": tips}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", nargs="?", default=".")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit-tokens", type=int, default=0, help="warn if project text exceeds this")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.dir):
        print(f"error: not a directory: {a.dir}", file=sys.stderr)
        return 2
    r = audit(a.dir, a.top, a.limit_tokens)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print(f"Project: {r['root']}\nText files: {r['text_files']}  (binary skipped: {r['binary_files_skipped']})")
    print(f"Estimated tokens if everything were loaded: ~{r['total_tokens_est']:,} (chars/4, +-25%)\n")
    print("Largest files:")
    for x in r["largest"]:
        print(f"  {x['tokens']:>8,}  {x['file']}")
    if r["noise"]:
        print("\nLow-value files:")
        for x in r["noise"]:
            print(f"  {x['tokens']:>8,}  {x['file']}  [{x['kind']}]")
    print("\nInstruction files (sent every request): " +
          (", ".join(f"{x['file']} ~{x['tokens']}" for x in r["instruction_files"]) or "none"))
    print("Ignore files: " + (", ".join(r["ignore_files"]) or "none"))
    print("\nRecommendations:")
    for t in r["tips"] or ["Nothing obvious to fix."]:
        print(f"  - {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
