#!/usr/bin/env python3
"""Chunk documents for RAG and score retrieval results.

Usage:
    python rag_tool.py chunk <file-or-dir>... [--size 1200] [--overlap 150] [--out chunks.jsonl]
    python rag_tool.py score queries.jsonl results.jsonl [--k 1,3,5,10] [--match exact|source] [--json]

Standard library only. Exit codes: 0 ok, 2 bad input.
"""
import argparse
import json
import os
import re
import sys

TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".adoc", ".text"}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


# ---------------------------------------------------------------- chunking

def iter_files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path, os.path.basename(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() in TEXT_EXT:
                        full = os.path.join(root, name)
                        yield full, os.path.relpath(full, path).replace(os.sep, "/")
        else:
            raise OSError("not found: %s" % path)


def split_sections(text):
    """Yield (heading_path, blocks) where blocks are paragraphs or whole fenced code blocks."""
    headings, blocks, para, fence = [], [], [], None
    sections = []

    def flush_para():
        if para:
            blocks.append("\n".join(para).strip())
            del para[:]

    def flush_section():
        flush_para()
        if any(b.strip() for b in blocks):
            sections.append((list(headings), [b for b in blocks if b.strip()]))
        del blocks[:]

    for line in text.splitlines():
        stripped = line.strip()
        if fence is not None:
            para.append(line)
            if stripped.startswith(fence):
                fence = None
                flush_para()
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_para()
            fence = stripped[:3]
            para.append(line)
            continue
        m = HEADING_RE.match(line)
        if m:
            flush_section()
            level = len(m.group(1))
            del headings[level - 1:]
            while len(headings) < level - 1:
                headings.append("")
            headings.append(m.group(2).strip())
            continue
        if not stripped:
            flush_para()
        else:
            para.append(line)
    flush_section()
    return [([h for h in hs if h], bs) for hs, bs in sections]


def _split_long(block, size):
    if len(block) <= size:
        return [block]
    if block.lstrip().startswith(("```", "~~~")):
        lines, out, cur = block.splitlines(), [], ""
        for line in lines:
            if cur and len(cur) + len(line) + 1 > size:
                out.append(cur)
                cur = ""
            cur = cur + "\n" + line if cur else line
        if cur:
            out.append(cur)
        return [p[i:i + size] for p in out for i in range(0, len(p), size)]
    pieces, cur = [], ""
    for sent in SENTENCE_RE.split(block):
        if cur and len(cur) + len(sent) + 1 > size:
            pieces.append(cur)
            cur = ""
        cur = (cur + " " + sent).strip()
    if cur:
        pieces.append(cur)
    out = []
    for p in pieces:
        out.extend(p[i:i + size] for i in range(0, len(p), size))
    return out


def _tail(text, overlap):
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    cut = text[-overlap:]
    space = cut.find(" ")
    return cut[space + 1:] if 0 <= space < overlap // 2 else cut


def chunk_text(text, size=1200, overlap=150):
    """Return a list of (headings, chunk_text)."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks = []
    for headings, blocks in split_sections(text):
        prefix = " > ".join(headings)
        budget = max(size - len(prefix) - 2, size // 2) if prefix else size
        parts = []
        for block in blocks:
            parts.extend(_split_long(block, budget))
        cur = ""
        for part in parts:
            if cur and len(cur) + len(part) + 2 > budget:
                chunks.append((headings, cur))
                tail = _tail(cur, overlap)
                cur = tail + "\n\n" + part if tail and len(tail) + len(part) + 2 <= budget else part
            else:
                cur = cur + "\n\n" + part if cur else part
        if cur:
            chunks.append((headings, cur))
    return [(h, ((" > ".join(h) + "\n\n") if h else "") + body) for h, body in chunks]


def cmd_chunk(opts):
    records = []
    try:
        for full, rel in iter_files(opts.paths):
            with open(full, encoding="utf-8-sig", errors="replace") as fh:
                text = fh.read()
            for n, (headings, body) in enumerate(chunk_text(text, opts.size, opts.overlap), 1):
                records.append({"id": "%s#%d" % (rel, n), "source": rel, "headings": headings, "text": body,
                                "chars": len(body), "approx_tokens": max(1, len(body) // 4)})
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if opts.out:
        with open(opts.out, "w", encoding="utf-8") as fh:
            fh.write(lines)
    else:
        sys.stdout.write(lines)
    sizes = [r["chars"] for r in records]
    if sizes:
        tiny = sum(1 for s in sizes if s < 100)
        print("%d chunks from %d files; chars avg %d, min %d, max %d; %d tiny (<100 chars)"
              % (len(sizes), len({r["source"] for r in records}), sum(sizes) // len(sizes), min(sizes),
                 max(sizes), tiny), file=sys.stderr)
    else:
        print("no chunks produced (supported: %s)" % ", ".join(sorted(TEXT_EXT)), file=sys.stderr)
    return 0


# ---------------------------------------------------------------- scoring

def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for n, line in enumerate(fh, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as exc:
                    raise ValueError("%s line %d: %s" % (path, n, exc))
    return rows


def _key(item, match):
    item = str(item)
    return item.split("#", 1)[0] if match == "source" else item


def score_retrieval(queries, results, ks=(1, 3, 5, 10), match="exact"):
    retrieved_by_id = {str(r.get("id")): r.get("retrieved") or [] for r in results}
    per_query, missing = [], []
    for q in queries:
        qid = str(q.get("id"))
        relevant = {_key(x, match) for x in q.get("relevant") or []}
        if qid not in retrieved_by_id:
            missing.append(qid)
        ranked, seen = [], set()
        for item in retrieved_by_id.get(qid, []):
            key = _key(item, match)
            if key not in seen:
                seen.add(key)
                ranked.append(key)
        first = next((i + 1 for i, item in enumerate(ranked) if item in relevant), None)
        row = {"id": qid, "query": q.get("query"), "first_relevant_rank": first,
               "rr": (1.0 / first) if first else 0.0}
        for k in ks:
            found = len(relevant & set(ranked[:k]))
            row["recall@%d" % k] = (found / float(len(relevant))) if relevant else 0.0
            row["hit@%d" % k] = 1.0 if found else 0.0
        per_query.append(row)
    n = float(len(per_query)) or 1.0
    summary = {"queries": len(per_query), "mrr": round(sum(r["rr"] for r in per_query) / n, 4),
               "missing_results": missing}
    for k in ks:
        summary["recall@%d" % k] = round(sum(r["recall@%d" % k] for r in per_query) / n, 4)
        summary["hit_rate@%d" % k] = round(sum(r["hit@%d" % k] for r in per_query) / n, 4)
    max_k = max(ks)
    summary["not_found_in_top_%d" % max_k] = [r["id"] for r in per_query if r["hit@%d" % max_k] == 0.0]
    summary["per_query"] = per_query
    return summary


def cmd_score(opts):
    try:
        ks = sorted({int(k) for k in opts.k.split(",") if k.strip()})
        if not ks or ks[0] < 1:
            raise ValueError("--k values must be positive integers")
        summary = score_retrieval(read_jsonl(opts.queries), read_jsonl(opts.results), ks, opts.match)
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if opts.json:
        print(json.dumps(summary, indent=2))
        return 0
    print("Queries: %d   MRR: %.3f" % (summary["queries"], summary["mrr"]))
    for k in ks:
        print("  k=%-3d recall %.3f   hit rate %.3f" % (k, summary["recall@%d" % k], summary["hit_rate@%d" % k]))
    miss = summary["not_found_in_top_%d" % ks[-1]]
    if miss:
        print("\nNo relevant result in top %d:" % ks[-1])
        for row in summary["per_query"]:
            if row["id"] in miss:
                print("  %s: %s" % (row["id"], row["query"]))
    if summary["missing_results"]:
        print("\nQueries with no results record: %s" % ", ".join(summary["missing_results"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    c = sub.add_parser("chunk", help="split Markdown/text files into chunks (JSONL)")
    c.add_argument("paths", nargs="+")
    c.add_argument("--size", type=int, default=1200, help="max characters per chunk (default 1200)")
    c.add_argument("--overlap", type=int, default=150, help="characters carried into the next chunk (default 150)")
    c.add_argument("--out", help="write JSONL here instead of stdout")
    s = sub.add_parser("score", help="score retrieval results against labelled queries")
    s.add_argument("queries")
    s.add_argument("results")
    s.add_argument("--k", default="1,3,5,10", help="comma-separated cut-offs (default 1,3,5,10)")
    s.add_argument("--match", choices=["exact", "source"], default="exact",
                   help="source: compare ids before '#', so labels can be whole documents")
    s.add_argument("--json", action="store_true")
    opts = parser.parse_args(argv)
    if opts.cmd == "chunk":
        if opts.size < 100:
            parser.error("--size must be at least 100")
        return cmd_chunk(opts)
    if opts.cmd == "score":
        return cmd_score(opts)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
