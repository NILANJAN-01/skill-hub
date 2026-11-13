#!/usr/bin/env python3
"""Connect installed skills: find them, match a task, check requirements, plan a chain, track hand-offs.

    python orchestrate.py scan   [--root DIR]... [--json]
    python orchestrate.py match  "task text" [--top 5] [--root DIR]...
    python orchestrate.py check  SKILL [SKILL ...] [--root DIR]...
    python orchestrate.py workflows
    python orchestrate.py plan   "task text" [--workflow NAME] [--root DIR]...
    python orchestrate.py run init   RUNDIR (--workflow NAME | --skills a,b,c) [--task TEXT]
    python orchestrate.py run done   RUNDIR STEP [--output FILE]... [--note TEXT]
    python orchestrate.py run status RUNDIR

Skills never call each other. This script gives the agent a shared picture: which skills exist, what each one
needs, which order fits a task, and a run folder where each step's output files are recorded for the next step.
Standard library only (Python 3.8+). It only reads skill folders; it writes only inside a run folder.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKFLOWS_FILE = HERE.parent / "references" / "workflows.json"

# Folders agents read skills from (project-relative, then user-level). Kept in sync with tools/install.py AGENTS.
PROJECT_DIRS = [".claude/skills", ".agents/skills", ".agent/skills", ".github/skills", ".cursor/skills",
                ".devin/skills", ".windsurf/skills", ".codex/skills", ".gemini/skills"]
USER_DIRS = ["~/.claude/skills", "~/.agents/skills", "~/.gemini/config/skills", "~/.gemini/skills",
             "~/.copilot/skills", "~/.cursor/skills", "~/.config/devin/skills", "~/.codex/skills"]

STOP = set("""a an and are as at be by can do for from has have how i in is it its me my of on or our so that the
their them then this to use used using want was we what when where which who will with you your please help make
need needs get give show tell about into out up""".split())

# requirement name -> how to detect it. "cmd" = executable on PATH, "py" = importable module, "python" = interpreter.
REQUIREMENTS = {
    "python": ("python", None), "adb": ("cmd", "adb"), "java": ("cmd", "java"), "jdk": ("cmd", "javac"),
    "gradle": ("cmd", "gradle"), "maven": ("cmd", "mvn"), "kotlinc": ("cmd", "kotlinc"),
    "ffmpeg": ("cmd", "ffmpeg"), "ffprobe": ("cmd", "ffprobe"), "docker": ("cmd", "docker"),
    "node": ("cmd", "node"), "npm": ("cmd", "npm"), "git": ("cmd", "git"), "tesseract": ("cmd", "tesseract"),
    "opencv": ("py", "cv2"), "pillow": ("py", "PIL"), "numpy": ("py", "numpy"),
}
ALIASES = {"opencv-python": "opencv", "cv2": "opencv", "pil": "pillow", "android platform-tools": "adb",
           "platform-tools": "adb", "jvm": "java", "javac": "jdk", "mvn": "maven", "ocr": "tesseract"}


# ----------------------------------------------------------------------------- registry
def parse_frontmatter(text: str) -> dict:
    """Tiny YAML-subset reader: top-level 'key: value' pairs, quoted or not, and one nested 'metadata:' level."""
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", text, re.S)
    if not m:
        return {}
    out, parent = {}, None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        kv = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if indent == 0:
            if val == "":
                out[key], parent = {}, key
            else:
                out[key], parent = val, None
        elif parent and isinstance(out.get(parent), dict):
            out[parent][key] = val
    return out


def default_roots(extra: list, defaults: bool = True) -> list:
    roots = [Path(r).expanduser() for r in extra]
    if not defaults:
        return roots
    roots += [Path.cwd() / d for d in PROJECT_DIRS]
    roots += [Path(d).expanduser() for d in USER_DIRS]
    hub = Path.cwd() / "skills"                     # a skill-hub clone
    if (hub / "README.md").is_file() or (Path.cwd() / ".claude-plugin").is_dir():
        roots.append(hub)
    return roots


def scan(extra_roots: list = (), defaults: bool = True) -> dict:
    """{name: {name, description, title, path, compatibility, root}} for every readable skill; first root wins."""
    reg = {}
    for root in default_roots(list(extra_roots), defaults):
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            try:
                fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = fm.get("name") or d.name
            if name in reg:
                continue
            meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
            reg[name] = {"name": name, "description": fm.get("description", ""), "title": meta.get("title", name),
                         "compatibility": fm.get("compatibility", ""), "path": str(d), "root": str(root)}
    return reg


# ----------------------------------------------------------------------------- matching
def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z][a-z0-9+#]*", text.lower()) if t not in STOP and len(t) > 1]


def stem(t: str) -> str:
    for suf in ("ing", "es", "s", "ed"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    return t


def match(task: str, reg: dict, top: int = 5, workflows: dict | None = None) -> list:
    """Rank skills for a task: weighted term overlap with name (x3) and description, rarer terms count more."""
    q = list(dict.fromkeys(stem(t) for t in tokens(task)))
    if not q or not reg:
        return []
    docs = {}
    for name, s in reg.items():
        docs[name] = ({stem(t) for t in tokens(name.replace("-", " "))}, {stem(t) for t in tokens(s["description"])})
    n = len(docs)
    scored = []
    for name, (name_t, desc_t) in docs.items():
        score, why = 0.0, []
        for t in q:
            df = sum(1 for nt, dt in docs.values() if t in nt or t in dt)
            idf = math.log((n + 1) / (df + 0.5)) if df else 0
            w = (3.0 if t in name_t else 0) + (1.0 if t in desc_t else 0)
            if w:
                score += w * idf
                why.append(t)
        if score > 0:
            scored.append({"skill": name, "score": round(score, 2), "matched": why, "title": reg[name]["title"]})
    scored.sort(key=lambda r: (-r["score"], r["skill"]))
    return scored[:top]


# ----------------------------------------------------------------------------- requirements
def requirements_of(compat: str) -> list:
    low = compat.lower()
    found = []
    for key in REQUIREMENTS:
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", low):
            found.append(key)
    for alias, key in ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) and key not in found:
            found.append(key)
    if re.search(r"python\s*3", low) and "python" not in found:
        found.append("python")
    return found


def have(req: str) -> bool:
    kind, target = REQUIREMENTS[req]
    if kind == "python":
        return sys.version_info >= (3, 8)
    if kind == "cmd":
        return shutil.which(target) is not None
    try:
        return importlib.util.find_spec(target) is not None
    except (ImportError, ValueError):
        return False


def check(skill_names: list, reg: dict) -> list:
    out = []
    for name in skill_names:
        s = reg.get(name)
        if not s:
            out.append({"skill": name, "installed": False, "requirements": {}, "ready": False,
                        "note": "not installed; install it from the hub (see the find-skills skill)"})
            continue
        reqs = {r: have(r) for r in requirements_of(s["compatibility"])}
        missing = [r for r, ok in reqs.items() if not ok]
        note = ""
        if missing:
            note = ("missing: " + ", ".join(missing) + ". The skill may still work for features that don't need "
                    "them; read its 'compatibility' line.")
        out.append({"skill": name, "installed": True, "requirements": reqs, "ready": not missing, "note": note,
                    "compatibility": s["compatibility"]})
    return out


# ----------------------------------------------------------------------------- workflows
def load_workflows(path: Path = WORKFLOWS_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["workflows"]


def pick_workflow(task: str, workflows: dict) -> list:
    q = {stem(t) for t in tokens(task)}
    ranked = []
    for name, w in workflows.items():
        words = {stem(t) for t in tokens(" ".join([name.replace("-", " "), w["description"], *w.get("triggers", [])]))}
        score = len(q & words)
        if score:
            ranked.append((score, name))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return [n for _, n in ranked]


def build_plan(task: str, reg: dict, workflow: str | None, workflows: dict) -> dict:
    chosen = workflow or (pick_workflow(task, workflows) or [None])[0]
    if workflow and workflow not in workflows:
        raise SystemExit(f"Unknown workflow {workflow!r}. Known: {', '.join(workflows)}")
    if chosen:
        w = workflows[chosen]
        steps = [dict(s, n=i + 1) for i, s in enumerate(w["steps"])]
        source = f"workflow '{chosen}': {w['description']}"
    else:
        ranked = match(task, reg, top=3)
        steps = [{"n": i + 1, "skill": r["skill"], "purpose": f"best match for the task ({', '.join(r['matched'])})",
                  "input": "task", "output": f"{i + 1:02d}-{r['skill']}.md"} for i, r in enumerate(ranked[:1])]
        source = "no named workflow fits; using the best single skill. Alternatives: " + (
            ", ".join(r["skill"] for r in ranked[1:]) or "none")
    status = {r["skill"]: r for r in check([s["skill"] for s in steps], reg)}
    for s in steps:
        s["installed"] = status[s["skill"]]["installed"]
        s["ready"] = status[s["skill"]]["ready"]
        s["note"] = status[s["skill"]]["note"]
    return {"task": task, "workflow": chosen, "source": source, "steps": steps,
            "can_run": bool(steps) and all(s["installed"] for s in steps)}


def validate_handoffs(steps: list) -> list:
    """Warn when a step's declared input names an output that no earlier step produces."""
    produced, problems = {"task"}, []
    for s in steps:
        for inp in s.get("input_from", []):
            if inp not in produced:
                problems.append(f"step {s['n']} ({s['skill']}) expects '{inp}', which no earlier step produces")
        out = s.get("output")
        if out:
            produced.add(out)
            produced.add(Path(out).stem)
    return problems


# ----------------------------------------------------------------------------- run state
def run_init(run_dir: Path, steps: list, task: str, workflow: str | None) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    f = run_dir / "run.json"
    if f.exists():
        raise SystemExit(f"{f} already exists. Use a new folder, or `run status` to continue it.")
    state = {"task": task, "workflow": workflow,
             "steps": [{"n": i + 1, "skill": s["skill"], "purpose": s.get("purpose", ""), "status": "pending",
                        "expects": s.get("input", ""), "output_hint": s.get("output", ""), "outputs": [], "note": ""}
                       for i, s in enumerate(steps)]}
    f.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return f


def load_run(run_dir: Path) -> dict:
    f = run_dir / "run.json"
    if not f.is_file():
        raise SystemExit(f"No run found in {run_dir}. Start one with `run init`.")
    return json.loads(f.read_text(encoding="utf-8"))


def run_done(run_dir: Path, step: int, outputs: list, note: str) -> dict:
    state = load_run(run_dir)
    target = next((s for s in state["steps"] if s["n"] == step), None)
    if not target:
        raise SystemExit(f"No step {step}. Steps are 1-{len(state['steps'])}.")
    earlier = [s for s in state["steps"] if s["n"] < step and s["status"] != "done"]
    if earlier:
        raise SystemExit(f"Step {earlier[0]['n']} ({earlier[0]['skill']}) is not done yet. Finish steps in order.")
    missing = [o for o in outputs if not (run_dir / o).exists() and not Path(o).exists()]
    if missing:
        raise SystemExit("Output file(s) not found: " + ", ".join(missing))
    target.update(status="done", outputs=outputs, note=note)
    (run_dir / "run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def render_status(state: dict) -> str:
    lines = [f"Task: {state['task']}", f"Workflow: {state['workflow'] or '(custom)'}", ""]
    nxt = next((s for s in state["steps"] if s["status"] != "done"), None)
    for s in state["steps"]:
        mark = {"done": "[x]", "pending": "[ ]"}.get(s["status"], "[?]")
        arrow = "  <- next" if nxt and s["n"] == nxt["n"] else ""
        lines.append(f"{mark} {s['n']}. {s['skill']}: {s['purpose']}{arrow}")
        if s["outputs"]:
            lines.append(f"      outputs: {', '.join(s['outputs'])}")
        if s["note"]:
            lines.append(f"      note: {s['note']}")
    if nxt:
        prev = [o for s in state["steps"] if s["n"] < nxt["n"] for o in s["outputs"]]
        lines += ["", f"Next: use '{nxt['skill']}'. Give it: {', '.join(prev) or 'the task text'}."]
    else:
        lines += ["", "All steps are done."]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- CLI
def fmt_plan(plan: dict) -> str:
    lines = [f"Task: {plan['task']}", f"Plan from {plan['source']}", ""]
    for s in plan["steps"]:
        flag = "ok" if s["installed"] and s["ready"] else ("NOT INSTALLED" if not s["installed"] else "check requirements")
        lines.append(f"{s['n']}. {s['skill']}  [{flag}]")
        lines.append(f"     do: {s.get('purpose', '')}")
        lines.append(f"     takes: {s.get('input', 'task')}   produces: {s.get('output', '')}")
        if s["note"]:
            lines.append(f"     note: {s['note']}")
    problems = validate_handoffs(plan["steps"])
    for p in problems:
        lines.append(f"WARNING: {p}")
    lines.append("")
    lines.append("Ready to run." if plan["can_run"] else "Some skills are not installed. Install them first.")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def roots(p):
        p.add_argument("--root", action="append", default=[], help="extra skills folder to scan (repeatable)")
        p.add_argument("--no-default-roots", action="store_true", help="scan only the --root folders")

    p = sub.add_parser("scan"); roots(p); p.add_argument("--json", action="store_true")
    p = sub.add_parser("match"); p.add_argument("task"); p.add_argument("--top", type=int, default=5); roots(p)
    p = sub.add_parser("check"); p.add_argument("skills", nargs="+"); roots(p)
    sub.add_parser("workflows")
    p = sub.add_parser("plan"); p.add_argument("task"); p.add_argument("--workflow"); roots(p)
    p = sub.add_parser("run"); rs = p.add_subparsers(dest="action", required=True)
    q = rs.add_parser("init"); q.add_argument("dir", type=Path); q.add_argument("--workflow"); q.add_argument("--skills")
    q.add_argument("--task", default=""); roots(q)
    q = rs.add_parser("done"); q.add_argument("dir", type=Path); q.add_argument("step", type=int)
    q.add_argument("--output", action="append", default=[]); q.add_argument("--note", default="")
    q = rs.add_parser("status"); q.add_argument("dir", type=Path)
    args = ap.parse_args()

    if args.cmd == "workflows":
        for name, w in load_workflows().items():
            print(f"{name}: {w['description']}")
            print("   " + " -> ".join(s["skill"] for s in w["steps"]))
        return
    if args.cmd == "run" and args.action in ("done", "status"):
        if args.action == "done":
            state = run_done(args.dir, args.step, args.output, args.note)
        else:
            state = load_run(args.dir)
        print(render_status(state))
        return

    reg = scan(getattr(args, "root", []), not getattr(args, "no_default_roots", False))
    if args.cmd == "scan":
        if args.json:
            print(json.dumps(list(reg.values()), indent=2))
        else:
            print(f"{len(reg)} skill(s) found")
            for s in sorted(reg.values(), key=lambda x: x["name"]):
                print(f"  {s['name']:<40} {s['root']}")
    elif args.cmd == "match":
        res = match(args.task, reg, args.top)
        if not res:
            print("No installed skill matches. Try the find-skills skill to search the hub catalog.")
        for r in res:
            print(f"{r['score']:>6}  {r['skill']}  (matched: {', '.join(r['matched'])})")
    elif args.cmd == "check":
        for r in check(args.skills, reg):
            state = "NOT INSTALLED" if not r["installed"] else ("ready" if r["ready"] else "missing requirements")
            print(f"{r['skill']}: {state}")
            for k, ok in r["requirements"].items():
                print(f"    {'ok     ' if ok else 'MISSING'} {k}")
            if r["note"]:
                print(f"    {r['note']}")
    elif args.cmd == "plan":
        print(fmt_plan(build_plan(args.task, reg, args.workflow, load_workflows())))
    elif args.cmd == "run" and args.action == "init":
        if args.workflow:
            wf = load_workflows()
            if args.workflow not in wf:
                sys.exit(f"Unknown workflow {args.workflow!r}. Known: {', '.join(wf)}")
            steps = wf[args.workflow]["steps"]
        elif args.skills:
            steps = [{"skill": s.strip(), "purpose": "", "input": "task", "output": f"{i + 1:02d}-{s.strip()}.md"}
                     for i, s in enumerate(args.skills.split(",")) if s.strip()]
        else:
            sys.exit("Give --workflow NAME or --skills a,b,c")
        f = run_init(args.dir, steps, args.task, args.workflow)
        print(f"created {f}")
        print(render_status(load_run(args.dir)))


if __name__ == "__main__":
    main()
