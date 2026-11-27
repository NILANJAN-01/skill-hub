#!/usr/bin/env python3
"""Build, run and score LLM labeling/classification prompts. Python 3.8+, standard library only, any model.

  build      fill a template with few-shot exemplars and each input -> prompts.jsonl
             python prompt_bench.py build --template t.txt --data dev.jsonl --exemplars train.jsonl --k 8 \
                 --select balanced --orders 3 --out prompts.jsonl
  run        send each prompt to any model command on stdin, keep stdout -> outputs.jsonl (resumable)
             python prompt_bench.py run prompts.jsonl --cmd "ollama run llama3.2" --samples 3 --jobs 4 --out out.jsonl
  score      extract the label from each output and report accuracy, precision/recall/F1, unparsed rate
             python prompt_bench.py score out.jsonl --labels yes,no --positive yes --extract last --compare
  autodicot  Automatic Directed CoT: ask "Why?" (right) or "It is actually X, please explain why." (wrong),
             then turn the explanations into reasoning exemplars
             python prompt_bench.py autodicot out.jsonl --labels yes,no --out followups.jsonl
             python prompt_bench.py autodicot --merge followup_out.jsonl --out exemplars.jsonl

Data files are JSON Lines with "input" and "label" (and optional "id", "reasoning").
Templates use {EXEMPLARS} and {INPUT}; exemplars are rendered with --format (default "Q: {input}\\nA: {label}").
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_FORMAT = "Q: {input}\nA: {label}"
REASONING_FORMAT = "Q: {input}\nR: {reasoning}\nA: {label}"


# --------------------------------------------------------------------------------------------- io
def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for no, line in enumerate(f, 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError as e:
                    raise SystemExit(f"error: {path}:{no}: not JSON ({e})")
    return out


def write_jsonl(path, rows, mode="w"):
    with open(path, mode, encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def need(rows, keys, path):
    for i, r in enumerate(rows, 1):
        missing = [k for k in keys if k not in r]
        if missing:
            raise SystemExit(f"error: {path} line {i} has no {', '.join(missing)}")


# ------------------------------------------------------------------------------------------ build
def words(text):
    return re.findall(r"[a-z0-9']+", str(text).lower())


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def select(pool, k, how, rng, query=None):
    if k <= 0 or not pool:
        return []
    if how == "first":
        return pool[:k]
    if how == "random":
        return rng.sample(pool, min(k, len(pool)))
    if how == "balanced":
        by = defaultdict(list)
        for ex in pool:
            by[str(ex["label"])].append(ex)
        for lst in by.values():
            rng.shuffle(lst)
        out, labels = [], sorted(by)
        while len(out) < min(k, len(pool)):
            for lab in labels:
                if by[lab] and len(out) < k:
                    out.append(by[lab].pop())
        return out
    if how == "similar":                                           # kNN by bag-of-words cosine
        q = Counter(words(query))
        ranked = sorted(pool, key=lambda ex: -cosine(q, Counter(words(ex["input"]))))
        return ranked[:k]
    raise SystemExit(f"error: unknown --select {how}")


def render(exs, fmt):
    return "\n\n".join(fmt.format(input=e["input"], label=e["label"], reasoning=e.get("reasoning", "")) for e in exs)


def cmd_build(a):
    template = Path(a.template).read_text(encoding="utf-8")
    if "{INPUT}" not in template:
        raise SystemExit("error: the template has no {INPUT} placeholder")
    data = read_jsonl(a.data)
    need(data, ["input"], a.data)
    pool = read_jsonl(a.exemplars) if a.exemplars else []
    need(pool, ["input", "label"], a.exemplars or "")
    fmt = (a.format or (REASONING_FORMAT if pool and all(p.get("reasoning") for p in pool) else DEFAULT_FORMAT))
    fmt = fmt.replace("\\n", "\n")
    rng = random.Random(a.seed)
    fixed = None if a.select == "similar" else select(pool, a.k, a.select, rng)
    used = {str(e["input"]) for e in (fixed or [])}
    rows, skipped = [], 0
    for i, item in enumerate(data):
        if str(item["input"]) in used:                            # never test on an exemplar
            skipped += 1
            continue
        exs = fixed if fixed is not None else select([p for p in pool if p["input"] != item["input"]], a.k,
                                                     "similar", rng, item["input"])
        for v in range(a.orders):
            order = list(exs)
            if a.orders > 1 or a.shuffle:
                random.Random(f"{a.seed}-{v}").shuffle(order)
            prompt = template.replace("{EXEMPLARS}", render(order, fmt)).replace("{INPUT}", str(item["input"]))
            rows.append({"id": item.get("id", i), "variant": v, "input": item["input"], "label": item.get("label"),
                         "prompt": prompt})
    write_jsonl(a.out, rows)
    print(f"Wrote {len(rows)} prompt(s) for {len(rows) // max(a.orders, 1)} input(s) x {a.orders} order(s) to {a.out}"
          + (f"; skipped {skipped} input(s) used as exemplars" if skipped else "")
          + (f"; {len(fixed)} exemplar(s) each" if fixed is not None else f"; {a.k} similar exemplar(s) per input"))
    return 0


# -------------------------------------------------------------------------------------------- run
def call(cmd, prompt, timeout):
    try:
        r = subprocess.run(cmd, shell=True, input=prompt.encode("utf-8"), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if r.returncode != 0:
        return None, f"exit {r.returncode}: {r.stderr.decode('utf-8', 'replace').strip()[:300]}"
    return r.stdout.decode("utf-8", "replace").strip(), None


def cmd_run(a):
    rows = read_jsonl(a.prompts)
    need(rows, ["prompt"], a.prompts)
    out = Path(a.out)
    done = set()
    if out.exists() and not a.restart:
        done = {(r.get("id"), r.get("variant", 0)) for r in read_jsonl(out) if not r.get("errors")}
    todo = [r for r in rows if (r.get("id"), r.get("variant", 0)) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} prompt(s) to run ({len(rows) - len(todo)} already done), {a.samples} sample(s) each",
          file=sys.stderr)
    lock, failures = threading.Lock(), [0]
    if a.restart and out.exists():
        out.unlink()

    def work(row):
        outputs, errors = [], []
        for _ in range(a.samples):
            text, err = call(a.cmd, row["prompt"], a.timeout)
            (errors.append(err) if err else outputs.append(text))
        rec = dict(row, outputs=outputs)
        if errors:
            rec["errors"] = errors
        with lock:
            write_jsonl(out, [rec], "a")
            if errors:
                failures[0] += 1
                if failures[0] <= 3:
                    print(f"  id {row.get('id')}: {errors[0]}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        list(pool.map(work, todo))
    print(f"Wrote {out} ({failures[0]} prompt(s) with errors; rerun the same command to retry them)")
    return 1 if failures[0] else 0


# ------------------------------------------------------------------------------------------ score
def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]", " ", str(text).lower())).strip()


def verbalizer(labels, mapping):
    """[(surface form, label)] longest first, so 'not entrapment' wins over 'entrapment'."""
    forms = [(norm(l), l) for l in labels]
    for lab, syns in (mapping or {}).items():
        if lab not in labels:
            raise SystemExit(f"error: --map label '{lab}' is not in --labels")
        forms += [(norm(s), lab) for s in ([syns] if isinstance(syns, str) else syns)]
    return sorted(set(forms), key=lambda f: -len(f[0]))


def extract(output, forms, how):
    """The label in one output, or None (unparsed)."""
    text = norm(output)
    if not text:
        return None
    if how == "exact":
        return next((lab for f, lab in forms if text == f), None)
    if how == "start":
        return next((lab for f, lab in forms if text == f or text.startswith(f + " ")), None)
    if how.startswith("regex:"):
        m = list(re.finditer(how[6:], str(output), re.I | re.S))
        if not m:
            return None
        got = norm(m[-1].group(1) if m[-1].groups() else m[-1].group(0))
        return next((lab for f, lab in forms if got == f), None)
    rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(f) for f, _ in forms) + r")(?![\w-])")
    hits = [m.group(1) for m in rx.finditer(text)]
    if not hits:
        return None
    pick = hits[0] if how == "first" else hits[-1]
    return next(lab for f, lab in forms if f == pick)


def vote(preds):
    """Majority over parsed predictions (ties: the earliest); None if nothing parsed."""
    parsed = [p for p in preds if p is not None]
    if not parsed:
        return None
    counts = Counter(parsed)
    best = max(counts.values())
    return next(p for p in parsed if counts[p] == best)


def metrics(pairs, labels, default=None):
    """pairs: [(gold, pred or None)]. 'unparsed' counts outputs with no label, before --default fills them."""
    unparsed = sum(1 for _, p in pairs if p is None)
    pairs = [(g, p if p is not None else default) for g, p in pairs]
    n = len(pairs)
    per = {}
    for lab in labels:
        tp = sum(1 for g, p in pairs if g == lab and p == lab)
        fp = sum(1 for g, p in pairs if g != lab and p == lab)
        fn = sum(1 for g, p in pairs if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per[lab] = {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
                    "support": tp + fn}
    return {"n": n, "accuracy": sum(1 for g, p in pairs if g == p) / n if n else 0.0,
            "unparsed": unparsed, "per_label": per,
            "macro_f1": sum(v["f1"] for v in per.values()) / len(per) if per else 0.0,
            "confusion": Counter((g, p if p is not None else "(unparsed)") for g, p in pairs)}


def scored(rows, labels, forms, how, mode):
    """[(id, gold, pred)] where mode 'variant' scores each (id, variant) and 'ensemble' votes across variants."""
    groups = defaultdict(list)
    for r in rows:
        key = r.get("id") if mode == "ensemble" else (r.get("id"), r.get("variant", 0))
        groups[key].append(r)
    out = []
    for key, rs in groups.items():
        gold = str(rs[0].get("label"))
        preds = [extract(o, forms, how) for r in rs for o in r.get("outputs", [])]
        out.append((key, gold, vote(preds), rs[0]))
    return out


def cmd_score(a):
    rows = read_jsonl(a.outputs)
    need(rows, ["label", "outputs"], a.outputs)
    labels = [l.strip() for l in a.labels.split(",") if l.strip()]
    mapping = json.loads(Path(a.map).read_text(encoding="utf-8")) if a.map else None
    forms = verbalizer(labels, mapping)
    unknown = {str(r["label"]) for r in rows} - set(labels)
    if unknown:
        raise SystemExit(f"error: gold labels not in --labels: {', '.join(sorted(unknown))}")
    variants = len({r.get("variant", 0) for r in rows})
    samples = max((len(r.get("outputs", [])) for r in rows), default=0)
    hows = ["exact", "start", "first", "last"] if a.compare else [a.extract]
    result = {"file": a.outputs, "items": len({r.get("id") for r in rows}), "variants": variants,
              "samples": samples, "extractors": {}}
    for how in hows:
        res = scored(rows, labels, forms, how, "ensemble" if a.vote or variants == 1 else "variant")
        m = metrics([(g, p) for _, g, p, _ in res], labels, a.default)
        if variants > 1 and not a.vote:                      # spread across exemplar orders
            byv = defaultdict(list)
            for key, g, p, _ in res:
                byv[key[1]].append((g, p))
            m["by_variant"] = {v: metrics(pp, labels, a.default)["accuracy"] for v, pp in sorted(byv.items())}
        m["errors"] = [{"id": key, "gold": g, "pred": p, "output": (r.get("outputs") or [""])[-1][:200]}
                       for key, g, p, r in res if (p if p is not None else a.default) != g][:a.show_errors]
        result["extractors"][how] = m
    if a.against:
        prev = {k: p for k, _, p, _ in scored(read_jsonl(a.against), labels, forms, hows[-1],
                                              "ensemble" if a.vote or variants == 1 else "variant")}
        now = scored(rows, labels, forms, hows[-1], "ensemble" if a.vote or variants == 1 else "variant")
        result["against"] = {"fixed": [k for k, g, p, _ in now if k in prev and prev[k] != g and p == g],
                             "broken": [k for k, g, p, _ in now if k in prev and prev[k] == g and p != g]}
    if a.json:
        for m in result["extractors"].values():
            m["confusion"] = [{"gold": g, "pred": p, "count": c} for (g, p), c in sorted(m["confusion"].items())]
        print(json.dumps(result, indent=2, default=str))
        return 0
    print(f"{a.outputs}: {result['items']} item(s), {variants} variant(s), {samples} sample(s) per prompt"
          + (" (majority vote)" if samples > 1 or (a.vote and variants > 1) else ""))
    pos = a.positive
    head = f"  {'extractor':9} {'acc':>6} {'macroF1':>8} {'unparsed':>9}"
    head += f"  {pos + ' P':>8} {'R':>6} {'F1':>6}" if pos else ""
    print(head)
    for how, m in result["extractors"].items():
        line = f"  {how:9} {m['accuracy']:6.3f} {m['macro_f1']:8.3f} {m['unparsed']:4d} ({m['unparsed'] / m['n']:4.0%})"
        if pos:
            p = m["per_label"][pos]
            line += f"  {p['precision']:8.3f} {p['recall']:6.3f} {p['f1']:6.3f}"
        print(line)
    m = result["extractors"][hows[-1]]
    if "by_variant" in m:
        accs = list(m["by_variant"].values())
        print(f"  accuracy by exemplar order: {', '.join(f'{x:.3f}' for x in accs)} (spread {max(accs) - min(accs):.3f})")
    print("  confusion (gold -> pred): " + ", ".join(f"{g}->{p}: {c}" for (g, p), c in sorted(m["confusion"].items())))
    if m["errors"]:
        print(f"  first {len(m['errors'])} error(s) [{hows[-1]}]:")
        for e in m["errors"]:
            print(f"    id {e['id']}: gold {e['gold']}, got {e['pred']}: {e['output']!r}")
    if a.against:
        f, b = result["against"]["fixed"], result["against"]["broken"]
        print(f"  vs {a.against}: {len(f)} fixed {f[:10]}, {len(b)} broken {b[:10]}")
    return 0


# -------------------------------------------------------------------------------------- autodicot
def cmd_autodicot(a):
    if a.merge:
        rows = read_jsonl(a.merge)
        need(rows, ["input", "label", "outputs"], a.merge)
        ex = [{"input": r["input"], "label": r["label"], "reasoning": " ".join(r["outputs"][-1].split())}
              for r in rows if r.get("outputs")]
        write_jsonl(a.out, ex)
        print(f"Wrote {len(ex)} reasoning exemplar(s) to {a.out}. Build with --exemplars {a.out} "
              "(the reasoning format Q/R/A is chosen automatically). Read them first: drop explanations that are wrong.")
        return 0
    rows = read_jsonl(a.outputs)
    need(rows, ["prompt", "label", "outputs"], a.outputs)
    labels = [l.strip() for l in a.labels.split(",")]
    forms = verbalizer(labels, json.loads(Path(a.map).read_text(encoding="utf-8")) if a.map else None)
    out, right = [], 0
    for r in rows:
        if not r["outputs"]:
            continue
        pred = extract(r["outputs"][0], forms, a.extract)
        ok = pred == str(r["label"])
        right += ok
        ask = "Why?" if ok else f"It is actually {r['label']}, please explain why."
        out.append({"id": r.get("id"), "variant": r.get("variant", 0), "input": r["input"], "label": r["label"],
                    "correct": ok, "prompt": f"{r['prompt']}\n{r['outputs'][0]}\n\n{ask}"})
    write_jsonl(a.out, out)
    print(f"Wrote {len(out)} follow-up prompt(s) ({right} answered right -> 'Why?', {len(out) - right} wrong -> "
          f"'It is actually ...') to {a.out}. Next: run them, then autodicot --merge.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build, run and score LLM classification prompts.")
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--template", required=True)
    b.add_argument("--data", required=True, help="JSONL of inputs to label (with gold 'label' for scoring)")
    b.add_argument("--exemplars", help="JSONL pool of labelled exemplars (may be the same file as --data)")
    b.add_argument("--k", type=int, default=0, help="exemplars per prompt (0 = zero-shot)")
    b.add_argument("--select", choices=["first", "random", "balanced", "similar"], default="balanced")
    b.add_argument("--orders", type=int, default=1, help="variants with different exemplar orders")
    b.add_argument("--shuffle", action="store_true", help="shuffle exemplar order (also with --orders 1)")
    b.add_argument("--format", help=f"exemplar format (default {DEFAULT_FORMAT!r})")
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("prompts")
    r.add_argument("--cmd", required=True, help="shell command that reads the prompt on stdin and prints the answer")
    r.add_argument("--samples", type=int, default=1, help="outputs per prompt (for self-consistency voting)")
    r.add_argument("--jobs", type=int, default=1)
    r.add_argument("--timeout", type=int, default=180)
    r.add_argument("--limit", type=int, default=0, help="run only the first N remaining prompts")
    r.add_argument("--restart", action="store_true", help="ignore earlier results in --out")
    r.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("outputs")
    s.add_argument("--labels", required=True, help="comma-separated allowed labels, as in the gold data")
    s.add_argument("--positive", help="label to report precision/recall/F1 for")
    s.add_argument("--extract", default="last", help="exact | start | first | last | regex:PATTERN (group 1)")
    s.add_argument("--map", help="JSON {label: [other words that mean it]} (a verbalizer)")
    s.add_argument("--default", help="label to use when nothing can be extracted")
    s.add_argument("--compare", action="store_true", help="score with every built-in extractor")
    s.add_argument("--vote", action="store_true", help="majority vote across exemplar-order variants (ensemble)")
    s.add_argument("--against", help="earlier outputs.jsonl: list items fixed and broken by this run")
    s.add_argument("--show-errors", type=int, default=5)
    s.add_argument("--json", action="store_true")
    d = sub.add_parser("autodicot")
    d.add_argument("outputs", nargs="?")
    d.add_argument("--labels")
    d.add_argument("--extract", default="last")
    d.add_argument("--map")
    d.add_argument("--merge", help="outputs of the follow-up prompts: write reasoning exemplars")
    d.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.command == "autodicot" and not a.merge and not (a.outputs and a.labels):
        ap.error("autodicot needs OUTPUTS and --labels (or --merge)")
    try:
        return {"build": cmd_build, "run": cmd_run, "score": cmd_score, "autodicot": cmd_autodicot}[a.command](a)
    except (OSError, SystemExit) as e:
        if isinstance(e, SystemExit) and isinstance(e.code, int):
            raise
        print(e if isinstance(e, SystemExit) else f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
