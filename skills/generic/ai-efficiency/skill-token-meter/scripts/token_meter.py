#!/usr/bin/env python3
"""skill-token-meter: how many tokens does a skill cost, and how many does it save? Standard library only.

Commands
  scan     [--skills-dir DIR]          what every skill costs: description (every session), SKILL.md body
                                       (when used), references, and bundled scripts (code the agent need not write)
  estimate --skill NAME [inputs...]    tokens WITH the skill vs WITHOUT it for one task, from real files
  measure  --skill NAME (--with-tokens N --without-tokens N | --with-log F --without-log F)
                                       exact savings from two real runs of the same task
  usage    LOG [LOG...]                add up the token usage recorded in JSON / JSONL session logs
  report   [--ledger FILE]             totals per skill from the central ledger

Add --record to estimate or measure to append the result to the central ledger
(default ~/.skill-hub/token-ledger.jsonl, or $SKILL_TOKEN_LEDGER). Add --json for machine output.

Token counts from files are estimates: characters / 4 for prose, / 3.3 for code and markup (about +-20%
against real tokenizers). Numbers from `measure` and `usage` are exact when the logs are.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
CODE_EXT = {".py", ".js", ".ts", ".sh", ".ps1", ".json", ".jsonl", ".html", ".htm", ".xml", ".yml", ".yaml",
            ".toml", ".css", ".java", ".kt", ".go", ".rs", ".c", ".cpp", ".h", ".rb", ".php", ".sql", ".vtt", ".srt"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
DEFAULTS = {"iterations": 1.5, "research_factor": 2.0, "command_tokens": 150}


# ---------------------------------------------------------------- counting
def est_tokens(text: str, kind: str = "prose") -> int:
    if not text:
        return 0
    return int(math.ceil(len(text) / (3.3 if kind == "code" else 4.0)))


def file_tokens(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return est_tokens(text, "code" if path.suffix.lower() in CODE_EXT else "prose")


def files_tokens(paths) -> int:
    return sum(file_tokens(p) for p in paths)


def split_frontmatter(text: str):
    """Return (frontmatter dict of top-level scalars, body)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            val = kv.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[kv.group(1)] = val
    return meta, m.group(2)


# ---------------------------------------------------------------- skills
def default_skill_roots() -> list:
    """Where to look for skills: the hub's skills/ folder if this runs inside the hub, and the folder this skill
    is installed in (installed skills sit side by side)."""
    roots = []
    for p in [SKILL_DIR, *SKILL_DIR.parents]:
        if p.name == "skills" and p.is_dir():
            roots.append(p)
            break
    roots.append(SKILL_DIR.parent)
    out = []
    for r in roots:
        if r not in out:
            out.append(r)
    return out


def find_skills(root: Path, depth: int = 4) -> list:
    found = []

    def walk(d: Path, level: int):
        if (d / "SKILL.md").is_file():
            found.append(d)
            return
        if level >= depth:
            return
        try:
            kids = sorted(p for p in d.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith("."))
        except OSError:
            return
        for k in kids:
            walk(k, level + 1)
    walk(root, 0)
    return found


def resolve_skill(name: str, roots=None) -> Path:
    p = Path(name).expanduser()
    if (p / "SKILL.md").is_file():
        return p.resolve()
    for root in roots or default_skill_roots():
        for d in find_skills(Path(root)):
            if d.name == name:
                return d.resolve()
    raise SystemExit(f"error: skill {name!r} not found; pass its folder path or --skills-dir")


def scripts_of(skill: Path) -> list:
    sd = skill / "scripts"
    if not sd.is_dir():
        return []
    return sorted(p for p in sd.rglob("*") if p.is_file() and p.suffix.lower() in CODE_EXT - {".json", ".jsonl", ".vtt", ".srt", ".html", ".htm"}
                  and not p.name.startswith("test_") and "fixtures" not in p.parts and "__pycache__" not in p.parts)


def skill_costs(skill: Path) -> dict:
    """Token cost of one skill, by when the agent pays it."""
    text = (skill / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    meta, body = split_frontmatter(text)
    name = meta.get("name") or skill.name
    refs = sorted(p for p in (skill / "references").rglob("*") if p.is_file()) if (skill / "references").is_dir() else []
    assets = sorted(p for p in (skill / "assets").rglob("*") if p.is_file()) if (skill / "assets").is_dir() else []
    scripts = scripts_of(skill)
    return {
        "skill": name, "path": str(skill),
        "description": est_tokens(f"{name}: {meta.get('description', '')}"),   # in context every session
        "body": est_tokens(body),                                                # when the skill is used
        "references": files_tokens(refs), "reference_files": len(refs),          # only when read
        "scripts": files_tokens(scripts), "script_files": len(scripts),          # code the agent need not write
        "assets": files_tokens([a for a in assets if a.suffix.lower() in CODE_EXT | {".md", ".txt"}]),
    }


# ---------------------------------------------------------------- estimate / measure
def _paths(items, base: Path) -> list:
    out = []
    for it in items or []:
        p = Path(it).expanduser()
        if not p.is_absolute() and not p.exists() and (base / it).exists():
            p = base / it
        if p.is_dir():
            out += [q for q in sorted(p.rglob("*")) if q.is_file() and "__pycache__" not in q.parts]
        elif p.is_file():
            out.append(p)
        else:
            raise SystemExit(f"error: {it} not found")
    return out


def estimate(skill: Path, raw=(), read=(), outputs=(), ran=None, iterations=None, research_factor=None,
             command_tokens=None, research_tokens=None) -> dict:
    """Tokens for one task WITH the skill vs WITHOUT it.

    WITH:    description + SKILL.md body + references read + script output read (input)
             + the commands the agent types (output)
    WITHOUT: raw inputs the agent would read itself + learning the know-how (body x research_factor, or
             research_tokens) (input) + writing equivalent code for the scripts used, x iterations (output)
    """
    it = DEFAULTS["iterations"] if iterations is None else iterations
    rf = DEFAULTS["research_factor"] if research_factor is None else research_factor
    ct = DEFAULTS["command_tokens"] if command_tokens is None else command_tokens
    c = skill_costs(skill)
    refs = _paths(["references"] if read == ["all"] else read, skill)
    outs = _paths(outputs, Path.cwd())
    raws = _paths(raw, Path.cwd())
    all_scripts = scripts_of(skill)
    if ran is None:
        used = all_scripts
    else:
        used = [s for s in all_scripts if s.name in ran or s.stem in ran]
        missing = set(ran) - {s.name for s in used} - {s.stem for s in used}
        if missing:
            raise SystemExit(f"error: no script named {', '.join(sorted(missing))} in {skill / 'scripts'}")
    code = files_tokens(used)
    research = int(research_tokens) if research_tokens is not None else int(c["body"] * rf)
    with_in = {"skill description": c["description"], "SKILL.md body": c["body"],
               "references read": files_tokens(refs), "script output read": files_tokens(outs)}
    with_out = {"commands typed": ct if used else 0}
    without_in = {"raw inputs read directly": files_tokens(raws), "learning the know-how": research}
    without_out = {"writing equivalent code": int(code * it)}
    w_in, w_out = sum(with_in.values()), sum(with_out.values())
    wo_in, wo_out = sum(without_in.values()), sum(without_out.values())
    return {
        "skill": c["skill"], "method": "estimate",
        "with": {"input": w_in, "output": w_out, "total": w_in + w_out, "parts": {**with_in, **with_out}},
        "without": {"input": wo_in, "output": wo_out, "total": wo_in + wo_out, "parts": {**without_in, **without_out}},
        "saved": {"input": wo_in - w_in, "output": wo_out - w_out, "total": (wo_in + wo_out) - (w_in + w_out)},
        "idle_cost_per_session": c["description"],
        "assumptions": {"iterations": it, "research_factor": None if research_tokens is not None else rf,
                        "research_tokens": research, "command_tokens": ct,
                        "scripts_counted": [s.name for s in used], "raw_files": [str(p) for p in raws],
                        "references_read": [str(p) for p in refs], "outputs_read": [str(p) for p in outs],
                        "token_estimate": "chars/4 prose, chars/3.3 code (+-20%)"},
    }


def measure(skill_name: str, with_tokens=None, without_tokens=None, with_log=None, without_log=None) -> dict:
    parts = {}
    if with_log:
        u = usage_from_logs([with_log])
        parts["with_log"] = u
        with_tokens = u["total"]
    if without_log:
        u = usage_from_logs([without_log])
        parts["without_log"] = u
        without_tokens = u["total"]
    if with_tokens is None or without_tokens is None:
        raise SystemExit("error: give --with-tokens and --without-tokens, or --with-log and --without-log")
    w, wo = int(with_tokens), int(without_tokens)
    return {"skill": skill_name, "method": "measured", "with": {"total": w}, "without": {"total": wo},
            "saved": {"total": wo - w}, "saved_percent": round(100.0 * (wo - w) / wo, 1) if wo else 0.0, **parts}


# ---------------------------------------------------------------- session logs
IN_KEYS = ("input_tokens", "prompt_tokens", "promptTokenCount", "inputTokens", "prompt_token_count")
OUT_KEYS = ("output_tokens", "completion_tokens", "candidatesTokenCount", "outputTokens", "completion_token_count")
CACHE_READ_KEYS = ("cache_read_input_tokens", "cachedContentTokenCount", "cache_read_tokens")
CACHE_WRITE_KEYS = ("cache_creation_input_tokens", "cache_write_tokens")


def _usage_dicts(obj):
    """Yield every dict that looks like a token-usage record."""
    if isinstance(obj, dict):
        if any(k in obj for k in IN_KEYS + OUT_KEYS):
            yield obj
            return
        for v in obj.values():
            yield from _usage_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _usage_dicts(v)


def _record_id(obj):
    if not isinstance(obj, dict):
        return None
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    return msg.get("id") or obj.get("requestId") or obj.get("response_id") or obj.get("id")


def usage_from_logs(paths) -> dict:
    """Sum token usage in JSON or JSONL logs. A record repeated with the same message id is counted once."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "records": 0, "files": 0}
    seen = set()
    for path in paths:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        tot["files"] += 1
        try:
            objs = [json.loads(text)]
        except ValueError:
            objs = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith(("{", "[")):
                    try:
                        objs.append(json.loads(line))
                    except ValueError:
                        continue
        for obj in objs:
            items = obj if isinstance(obj, list) else [obj]
            for item in items:
                rid = _record_id(item)
                if rid and rid in seen:
                    continue
                found = False
                for u in _usage_dicts(item):
                    found = True
                    tot["input"] += int(next((u[k] for k in IN_KEYS if isinstance(u.get(k), (int, float))), 0))
                    tot["output"] += int(next((u[k] for k in OUT_KEYS if isinstance(u.get(k), (int, float))), 0))
                    tot["cache_read"] += int(next((u[k] for k in CACHE_READ_KEYS if isinstance(u.get(k), (int, float))), 0))
                    tot["cache_write"] += int(next((u[k] for k in CACHE_WRITE_KEYS if isinstance(u.get(k), (int, float))), 0))
                    tot["records"] += 1
                if found and rid:
                    seen.add(rid)
    tot["total"] = tot["input"] + tot["output"] + tot["cache_read"] + tot["cache_write"]
    return tot


# ---------------------------------------------------------------- ledger
def ledger_path(explicit=None) -> Path:
    return Path(explicit or os.environ.get("SKILL_TOKEN_LEDGER") or Path.home() / ".skill-hub" / "token-ledger.jsonl")


def record(result: dict, task: str = "", ledger=None) -> Path:
    path = ledger_path(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "skill": result["skill"],
             "method": result["method"], "task": task, "with": result["with"].get("total"),
             "without": result["without"].get("total"), "saved": result["saved"]["total"]}
    if result["method"] == "estimate":
        entry["assumptions"] = {k: v for k, v in result["assumptions"].items()
                                if k in ("iterations", "research_tokens", "scripts_counted")}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def report(ledger=None) -> dict:
    path = ledger_path(ledger)
    rows = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            r = rows.setdefault(e.get("skill", "?"), {"skill": e.get("skill", "?"), "uses": 0, "measured": 0,
                                                       "estimated": 0, "saved": 0, "with": 0, "without": 0, "last": ""})
            r["uses"] += 1
            r["measured" if e.get("method") == "measured" else "estimated"] += 1
            r["saved"] += int(e.get("saved") or 0)
            r["with"] += int(e.get("with") or 0)
            r["without"] += int(e.get("without") or 0)
            r["last"] = max(r["last"], e.get("time", ""))
    skills = sorted(rows.values(), key=lambda r: -r["saved"])
    for r in skills:
        r["average_saved"] = r["saved"] // r["uses"] if r["uses"] else 0
        r["saved_percent"] = round(100.0 * r["saved"] / r["without"], 1) if r["without"] else 0.0
    total = {k: sum(r[k] for r in skills) for k in ("uses", "saved", "with", "without")}
    return {"ledger": str(path), "skills": skills, "total": total}


# ---------------------------------------------------------------- printing
def n(x) -> str:
    return f"{int(x):,}"


def money(tokens_in, tokens_out, price_in, price_out):
    if price_in is None and price_out is None:
        return None
    return round(tokens_in / 1e6 * (price_in or 0) + tokens_out / 1e6 * (price_out or 0), 4)


def print_scan(rows, sessions=None):
    w = max([len(r["skill"]) for r in rows] + [5])
    print(f"{'skill':<{w}}  {'every session':>13}  {'when used':>9}  {'references':>10}  {'scripts':>8}")
    print(f"{'':<{w}}  {'(description)':>13}  {'(body)':>9}  {'(if read)':>10}  {'(code)':>8}")
    for r in rows:
        print(f"{r['skill']:<{w}}  {n(r['description']):>13}  {n(r['body']):>9}  {n(r['references']):>10}  {n(r['scripts']):>8}")
    idle = sum(r["description"] for r in rows)
    print(f"\n{len(rows)} skills. If all are installed, their descriptions use ~{n(idle)} tokens in every session.")
    print("Body, references and scripts cost nothing until a skill is used. Scripts save the agent writing that code.")
    print("Estimates: chars/4 prose, chars/3.3 code (+-20%).")


def print_estimate(r, price_in=None, price_out=None):
    print(f"Skill: {r['skill']}  (estimate)\n")
    for side, title in (("with", "WITH the skill"), ("without", "WITHOUT the skill")):
        print(f"{title}: {n(r[side]['total'])} tokens  (input {n(r[side]['input'])}, output {n(r[side]['output'])})")
        for k, v in r[side]["parts"].items():
            print(f"    {k:<28} {n(v):>9}")
    s = r["saved"]
    pct = round(100.0 * s["total"] / r["without"]["total"], 1) if r["without"]["total"] else 0.0
    verb = "SAVED" if s["total"] >= 0 else "EXTRA COST"
    print(f"\n{verb}: {n(abs(s['total']))} tokens ({abs(pct)}%)  -  input {n(s['input'])}, output {n(s['output'])}")
    c = money(s["input"], s["output"], price_in, price_out)
    if c is not None:
        print(f"Money saved at your prices: ${c}")
    if r["idle_cost_per_session"] and s["total"] > 0:
        print(f"The description costs {n(r['idle_cost_per_session'])} tokens every session, so one use pays for "
              f"~{n(s['total'] // r['idle_cost_per_session'])} sessions of having it installed.")
    a = r["assumptions"]
    factor = "" if a["research_factor"] is None else f" (= body x {a['research_factor']})"
    scripts = ", ".join(a["scripts_counted"]) or "none"
    print(f"\nAssumptions: code written {a['iterations']}x (write + fix); know-how {n(a['research_tokens'])} tokens"
          f"{factor}; scripts counted: {scripts}. Change them with --iterations, --research-factor, "
          "--research-tokens, --ran. For real numbers use `measure`.")


def print_measure(r):
    s = r["saved"]["total"]
    print(f"Skill: {r['skill']}  (measured)\n")
    for side, title, log in (("with", "WITH the skill:   ", "with_log"), ("without", "WITHOUT the skill:", "without_log")):
        line = f"{title} {n(r[side]['total'])} tokens"
        if log in r:
            u = r[log]
            line += (f"  (input {n(u['input'])}, output {n(u['output'])}, cache read {n(u['cache_read'])}, "
                     f"cache write {n(u['cache_write'])})")
        print(line)
    if "with_log" in r:
        print("Cache reads are context re-read on every turn; most providers bill them far below normal input.")
    print(f"\n{'SAVED' if s >= 0 else 'EXTRA COST'}: {n(abs(s))} tokens ({abs(r['saved_percent'])}%)")


def print_report(rep):
    print(f"Ledger: {rep['ledger']}\n")
    if not rep["skills"]:
        print("No results yet. Run `estimate` or `measure` with --record after using a skill.")
        return
    w = max(len(r["skill"]) for r in rep["skills"])
    print(f"{'skill':<{w}}  {'uses':>4}  {'saved':>10}  {'avg/use':>9}  {'saved %':>7}  measured/estimated")
    for r in rep["skills"]:
        print(f"{r['skill']:<{w}}  {r['uses']:>4}  {n(r['saved']):>10}  {n(r['average_saved']):>9}  "
              f"{r['saved_percent']:>6}%  {r['measured']}/{r['estimated']}")
    t = rep["total"]
    print(f"\nAll skills: {n(t['saved'])} tokens saved over {t['uses']} uses "
          f"({n(t['with'])} used with skills vs {n(t['without'])} without).")


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="How many tokens a skill costs and saves.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="token cost of every skill")
    s.add_argument("--skills-dir", action="append", help="folder with skills (repeatable); default: auto")
    s.add_argument("--sort", choices=["name", "description", "body", "scripts"], default="description")
    s.add_argument("--json", action="store_true")

    e = sub.add_parser("estimate", help="tokens with vs without a skill for one task")
    e.add_argument("--skill", required=True, help="skill name or folder")
    e.add_argument("--skills-dir", action="append")
    e.add_argument("--raw", nargs="*", default=[], help="raw inputs the agent would read itself without the skill")
    e.add_argument("--read", nargs="*", default=[], help="reference files the agent read (or 'all')")
    e.add_argument("--output", nargs="*", default=[], help="script output files the agent read")
    e.add_argument("--ran", nargs="*", help="scripts used (default: all non-test scripts)")
    e.add_argument("--iterations", type=float, help=f"times the agent would write/fix the code (default {DEFAULTS['iterations']})")
    e.add_argument("--research-factor", type=float, help=f"know-how cost as a multiple of the body (default {DEFAULTS['research_factor']})")
    e.add_argument("--research-tokens", type=int, help="know-how cost in tokens (overrides --research-factor)")
    e.add_argument("--command-tokens", type=int, help=f"tokens for typing the commands (default {DEFAULTS['command_tokens']})")
    e.add_argument("--price-in", type=float, help="your price per 1M input tokens, to show money saved")
    e.add_argument("--price-out", type=float, help="your price per 1M output tokens")

    m = sub.add_parser("measure", help="exact savings from two real runs")
    m.add_argument("--skill", required=True)
    m.add_argument("--with-tokens", type=int)
    m.add_argument("--without-tokens", type=int)
    m.add_argument("--with-log")
    m.add_argument("--without-log")

    for p in (e, m):
        p.add_argument("--record", action="store_true", help="append the result to the central ledger")
        p.add_argument("--task", default="", help="short note about the task, saved with --record")
        p.add_argument("--ledger", help="ledger file (default ~/.skill-hub/token-ledger.jsonl)")
        p.add_argument("--json", action="store_true")

    u = sub.add_parser("usage", help="sum token usage in JSON/JSONL session logs")
    u.add_argument("logs", nargs="+")
    u.add_argument("--json", action="store_true")

    r = sub.add_parser("report", help="totals per skill from the ledger")
    r.add_argument("--ledger")
    r.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "scan":
        roots = [Path(d) for d in a.skills_dir] if a.skills_dir else default_skill_roots()
        seen, rows = set(), []
        for root in roots:
            for d in find_skills(root):
                if d.resolve() not in seen:
                    seen.add(d.resolve())
                    rows.append(skill_costs(d))
        rows.sort(key=lambda x: x["skill"] if a.sort == "name" else -x[a.sort])
        if a.json:
            print(json.dumps({"skills": rows, "description_total": sum(x["description"] for x in rows)}, indent=2))
        else:
            print_scan(rows)
        return 0
    if a.cmd == "estimate":
        roots = [Path(d) for d in a.skills_dir] if a.skills_dir else None
        res = estimate(resolve_skill(a.skill, roots), a.raw, a.read, a.output, a.ran, a.iterations,
                       a.research_factor, a.command_tokens, a.research_tokens)
        res["money_saved"] = money(res["saved"]["input"], res["saved"]["output"], a.price_in, a.price_out)
    elif a.cmd == "measure":
        res = measure(a.skill, a.with_tokens, a.without_tokens, a.with_log, a.without_log)
    elif a.cmd == "usage":
        res = usage_from_logs(a.logs)
        if a.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"{res['files']} file(s), {res['records']} usage records\n"
                  f"input {n(res['input'])}, output {n(res['output'])}, cache read {n(res['cache_read'])}, "
                  f"cache write {n(res['cache_write'])}\ntotal {n(res['total'])} tokens")
        return 0
    else:
        rep = report(a.ledger)
        if a.json:
            print(json.dumps(rep, indent=2))
        else:
            print_report(rep)
        return 0
    if a.record:
        res["recorded_to"] = str(record(res, a.task, a.ledger))
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print_estimate(res, a.price_in, a.price_out) if a.cmd == "estimate" else print_measure(res)
        if a.record:
            print(f"\nRecorded to {res['recorded_to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
