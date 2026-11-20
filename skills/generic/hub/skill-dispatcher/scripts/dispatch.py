#!/usr/bin/env python3
"""Turn a user's prompt into a parallel plan: which skills to run, which can run at the same time, and a brief for each.

    python dispatch.py "request text" [--root DIR]... [--run-dir DIR] [--json]
    python dispatch.py --file request.txt
    python dispatch.py --hook            # read the prompt an agent's prompt-submit hook sends on stdin

It splits the request into parts and matches each part to an installed skill (using the skill-router skill's
matcher), works out which parts depend on others, and groups the parts into waves. Every task in a wave can run
at the same time as its own sub-agent; a wave starts when the one before it is done. Each task gets a
self-contained brief to hand to a sub-agent.

--hook mode never fails the prompt: it prints nothing for trivial prompts, slash commands or when no skill fits,
and always exits 0. Set SKILL_DISPATCH=off to silence it.

Standard library only (Python 3.8+). Read-only: it never installs, runs or writes anything.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_HOME = HERE.parent.parent           # the folder holding this skill and its siblings
ROUTER_CANDIDATES = [SKILLS_HOME / "skill-router" / "scripts" / "route.py"]
WORKFLOW_CANDIDATES = [SKILLS_HOME / "skill-orchestrator" / "references" / "workflows.json"]

# Skills that plan work rather than do it; never dispatch a part to them.
META_SKILLS = {"skill-dispatcher", "skill-router", "skill-orchestrator"}

# Words between two parts that mean "the second waits for the first".
SEQUENTIAL = re.compile(r"\b(then|after that|afterwards|next|finally|once (?:that|this|it)(?:'s| is)? (?:done|finished)|"
                        r"when (?:that|this|it)(?:'s| is)? (?:done|finished))\b", re.I)
# Wording in a part that uses an earlier part's result.
USES_EARLIER = re.compile(r"\b(the (?:results?|outputs?|findings|report|summary|analysis|list|locators|answer|above)|"
                          r"based on (?:it|that|this|those|these|them|the)|using (?:that|those|these|them|the results?|"
                          r"the outputs?|the findings)|from (?:that|those|the) (?:step|results?|outputs?|analysis)|"
                          r"the above|with (?:the|those|these) (?:results|findings))\b", re.I)
HOOK_PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "input", "message", "text")


# ----------------------------------------------------------------------------- loading
def load_router(candidates=ROUTER_CANDIDATES):
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("skill_router_route", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def workflow_order(candidates=WORKFLOW_CANDIDATES) -> set:
    """Pairs (a, b) where a known workflow runs skill a before skill b."""
    pairs = set()
    for path in candidates:
        try:
            flows = json.loads(path.read_text(encoding="utf-8")).get("workflows", {})
        except (OSError, ValueError):
            continue
        for flow in flows.values():
            skills = [s.get("skill") for s in flow.get("steps", []) if s.get("skill")]
            pairs.update((a, b) for i, a in enumerate(skills) for b in skills[i + 1:] if a != b)
    return pairs


# ----------------------------------------------------------------------------- planning
def gaps(text: str, parts: list) -> list:
    """The text just before each part (the connector words), found by locating the parts in order."""
    out, cursor = [], 0
    for p in parts:
        at = text.find(p, cursor)
        if at < 0:
            out.append("")
            continue
        out.append(text[cursor:at])
        cursor = at + len(p)
    return out


def plan(text: str, routed: dict, order_pairs: set = frozenset()) -> dict:
    parts = routed["parts"]
    before = gaps(text, [p["part"] for p in parts])
    tasks, dispatched = [], []
    for p in parts:                                  # a low-confidence guess is a hint, not an assignment
        if p["skill"] and p["confidence"] == "low":
            p = dict(p, skill=None, possible=p["skill"], missing_inputs=[], missing_tools=[])
        dispatched.append(p)
    parts = dispatched
    for i, p in enumerate(parts):
        deps, why = set(), []
        if i > 0:
            lead = re.match(r"\s*(?:and\s+)?(" + SEQUENTIAL.pattern + r")", p["part"], re.I)
            m = USES_EARLIER.search(p["part"])
            if lead or m:                            # "Then ..." / "from the findings": waits for everything so far
                deps.update(range(i))
                why.append(f'"{lead.group(1)}" starts a new step' if lead
                           else f'uses earlier results ("{m.group(0)}")')
            elif SEQUENTIAL.search(before[i]):       # "A then B" inside one sentence: B waits for A
                deps.add(i - 1)
                why.append(f'"{SEQUENTIAL.search(before[i]).group(0).strip()}" links it to task {i}')
        for j in range(i):
            other = parts[j]["skill"]
            if p["skill"] and other == p["skill"]:
                deps.add(j)
                why.append(f"same skill as task {j + 1}, so they do not clash")
            elif p["skill"] and other and (other, p["skill"]) in order_pairs:
                deps.add(j)
                why.append(f"{other} usually feeds {p['skill']}")
        tasks.append({"id": i + 1, "part": p["part"], "skill": p["skill"], "confidence": p["confidence"],
                      "level": p["level"], "possible_skill": p.get("possible"), "alternatives": p["alternatives"],
                      "missing_inputs": p["missing_inputs"], "missing_tools": p["missing_tools"], "depends_on": sorted(d + 1 for d in deps),
                      "why": list(dict.fromkeys(why))})
    for t in tasks:                                  # deps always point backwards, so one pass is enough
        t["wave"] = 1 + max((tasks[d - 1]["wave"] for d in t["depends_on"]), default=0)
    waves = {}
    for t in tasks:
        waves.setdefault(t["wave"], []).append(t["id"])
    ask = list(dict.fromkeys(m for t in tasks for m in t["missing_inputs"]))
    return {"request": text, "tasks": tasks, "waves": [waves[k] for k in sorted(waves)],
            "parallel": any(len(w) > 1 for w in waves.values()), "ask_user_first": ask}


def brief(task: dict, result: dict, run_dir: str = "") -> str:
    """A self-contained instruction for the sub-agent that runs one task."""
    wave = result["waves"][task["wave"] - 1]
    peers = [i for i in wave if i != task["id"]]
    lines = [f"Task {task['id']} of {len(result['tasks'])} (wave {task['wave']}"
             + (f", runs at the same time as task {', '.join(map(str, peers))})" if peers else ")"),
             f"Goal: {task['part']}",
             f"Whole request, for context only: {result['request']}"]
    if task["skill"]:
        where = f" (instructions: {task['skill_path']})" if task.get("skill_path") else ""
        lines.append(f"Skill: load the `{task['skill']}` skill{where} and follow its procedure and safety rules.")
    else:
        lines.append("Skill: none fits well; do this part directly"
                     + (f" (the `{task['possible_skill']}` skill might help)." if task["possible_skill"] else "."))
    if task["depends_on"]:
        src = ", ".join(f"task {d}" for d in task["depends_on"])
        lines.append(f"Inputs: the results of {src}" + (f" (files in {run_dir})" if run_dir else "") + ".")
    if task["missing_inputs"]:
        lines.append("Needs from the user (get these before starting): " + "; ".join(task["missing_inputs"]))
    if run_dir:
        name = f"{task['id']:02d}-{task['skill'] or 'direct'}.md"
        lines.append(f"Write your result to {run_dir}/{name}: a short summary first, then details.")
    lines += ["Rules: do not edit files another task in this wave may edit; do not ask the user directly, "
              "put open questions in your result instead.",
              "Return: a short summary, the files you created or changed, and open questions."]
    return "\n".join(lines)


def attach_briefs(result: dict, run_dir: str = "", paths: dict = None) -> dict:
    for t in result["tasks"]:
        t["skill_path"] = (paths or {}).get(t["skill"])
        t["brief"] = brief(t, result, run_dir)
    return result


# ----------------------------------------------------------------------------- output
def render(result: dict, with_briefs: bool = True) -> str:
    tasks = {t["id"]: t for t in result["tasks"]}
    lines = ["Skill dispatch plan (generated from the prompt; advisory, drop it if it does not fit)", ""]
    if result["ask_user_first"]:
        lines += ["Ask the user first, in one message: " + "; ".join(result["ask_user_first"]), ""]
    for n, wave in enumerate(result["waves"], 1):
        label = "in parallel" if len(wave) > 1 else "single task"
        lines.append(f"Wave {n} ({label}):")
        for i in wave:
            t = tasks[i]
            who = (f"{t['skill']} ({t['confidence']})" if t["skill"] else "no skill, do directly"
                   + (f" (maybe {t['possible_skill']})" if t["possible_skill"] else ""))
            lines.append(f"  [{i}] {who}: {t['part']}")
            if t["depends_on"]:
                lines.append(f"      waits for {', '.join(map(str, t['depends_on']))}: {'; '.join(t['why'])}")
            if t["missing_tools"]:
                lines.append("      missing tools: " + ", ".join(t["missing_tools"]))
    lines.append("")
    if result["parallel"]:
        lines.append("How to run: start every task in a wave at the same time, each as its own sub-agent or "
                     "parallel worker with its brief. Wait for the wave to finish, then start the next one with "
                     "the earlier results. If you cannot run sub-agents, do the tasks in order.")
    elif len(result["tasks"]) > 1:
        lines.append("How to run: the tasks depend on each other, so run them in order and pass each result on.")
    else:
        lines.append("How to run: one task; load the skill and do it directly.")
    if with_briefs and len(result["tasks"]) > 1:
        lines += ["", "Briefs:"]
        for t in result["tasks"]:
            lines += ["", "\n".join("  " + ln for ln in t["brief"].splitlines())]
    return "\n".join(lines)


def worth_showing(result: dict) -> bool:
    """Hook mode stays quiet unless at least one part matched a skill with medium or high confidence."""
    return any(t["skill"] and t["confidence"] in ("high", "medium") for t in result["tasks"])


def prompt_from_hook(raw: str):
    """(prompt, cwd) from a hook payload: JSON with a prompt field, or the raw text."""
    try:
        data = json.loads(raw)
    except ValueError:
        return raw.strip(), None
    if isinstance(data, str):
        return data.strip(), None
    if not isinstance(data, dict):
        return "", None
    for k in HOOK_PROMPT_KEYS:
        if isinstance(data.get(k), str):
            return data[k].strip(), data.get("cwd") if isinstance(data.get("cwd"), str) else None
    return "", None


# ----------------------------------------------------------------------------- main
def promote_alternatives(routed: dict, router, reg: dict, hints: dict) -> dict:
    """When the top pick won on one weak word but the router also offers a medium/high alternative
    (for example a matched phrase), use the alternative."""
    for p in routed["parts"]:
        if not (p["skill"] and p["confidence"] == "low" and p["alternatives"]):
            continue
        alt = p["alternatives"][0]
        needs = hints.get(alt, {}).get("needs", [])
        p.update(skill=alt, confidence="medium", alternatives=p["alternatives"][1:],
                 missing_inputs=router.missing_inputs(p["part"], routed["request"], needs),
                 missing_tools=[t for t in router.requirements_of(reg[alt].get("compatibility", ""))
                                if not router.have(t)])
    return routed


def dispatch(text: str, router, roots=(), defaults: bool = True, run_dir: str = "") -> dict:
    reg = {k: v for k, v in router.scan(list(roots), defaults).items() if k not in META_SKILLS}
    hints = router.load_hints()
    routed = promote_alternatives(router.route(text, reg, hints), router, reg, hints)
    return attach_briefs(plan(text, routed, workflow_order()), run_dir, skill_paths(router, roots, defaults))


def skill_paths(router, roots=(), defaults: bool = True) -> dict:
    """name -> path of its SKILL.md, first root wins (the same order the router scans in)."""
    out = {}
    for root in router.roots_to_scan(list(roots), defaults):
        if root.is_dir():
            for folder in router.skill_folders(root):
                out.setdefault(folder.name, str(folder / "SKILL.md"))
    return out


def run_hook(args, router) -> int:
    if os.environ.get("SKILL_DISPATCH", "").lower() in ("off", "0", "false"):
        return 0
    try:
        text, cwd = prompt_from_hook(sys.stdin.read())
        if not text or text.startswith("/") or len(text.split()) < 3 or router is None:
            return 0
        if cwd and Path(cwd).is_dir():
            os.chdir(cwd)
        result = dispatch(text, router, args.root, not args.no_default_roots, args.run_dir)
        if worth_showing(result):
            print(json.dumps(result, indent=2) if args.json else render(result, not args.no_briefs))
    except Exception:                                # a hook must never block the user's prompt
        pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("request", nargs="?", help="the user's request text")
    ap.add_argument("--file", type=Path, help="read the request from a file")
    ap.add_argument("--hook", action="store_true", help="read a hook payload (JSON or text) from stdin; quiet, exit 0")
    ap.add_argument("--root", action="append", default=[], help="extra skills folder to scan (repeatable)")
    ap.add_argument("--no-default-roots", action="store_true", help="scan only the --root folders")
    ap.add_argument("--run-dir", default="", help="folder the briefs tell each task to write its result to")
    ap.add_argument("--no-briefs", action="store_true", help="print only the waves")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    router = load_router()
    if args.hook:
        return run_hook(args, router)
    if router is None:
        sys.exit("skill-router is not installed next to this skill; install it (it provides the matcher)")
    text = args.file.read_text(encoding="utf-8") if args.file else (args.request or "")
    if not text.strip():
        sys.exit("Give the request text, --file FILE, or --hook with the prompt on stdin")
    result = dispatch(text, router, args.root, not args.no_default_roots, args.run_dir)
    print(json.dumps(result, indent=2) if args.json else render(result, not args.no_briefs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
