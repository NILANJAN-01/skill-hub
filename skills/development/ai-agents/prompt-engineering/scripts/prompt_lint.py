#!/usr/bin/env python3
"""Lint a prompt or prompt template for problems that measurably change LLM output. Python 3.8+, standard library.

    python prompt_lint.py PROMPT_FILE [...]        # .txt/.md/.prompt, or .json chat messages
    python prompt_lint.py -                        # read the prompt from stdin
    python prompt_lint.py prompt.txt --json --fail-on medium

Checks (from "The Prompt Report", Schulhoff et al. 2024, and the papers it surveys):
  few-shot   label imbalance, labels grouped together or all at the end, mixed exemplar formats, duplicates,
             more than about 20 exemplars
  answer     a labeling task without a stated answer space; reasoning requested without a final-answer marker
  wording    the user's opinion or a false presupposition in the prompt (models tend to agree: sycophancy)
  input      template variables inserted without delimiters; personal data (emails, phone numbers)
  directive  no instruction or question at all
Exit codes: 0 nothing at or above --fail-on (default medium), 1 findings, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

LEVELS = {"high": 3, "medium": 2, "low": 1, "info": 0}
VAR = re.compile(r"\{\{\s*[\w.\-]+\s*\}\}|\$\{[\w.\-]+\}|(?<![{\\])\{[A-Za-z_][\w.\-]*\}(?!\})")
DIRECTIVE_VERBS = (
    "act", "add", "analy", "answer", "ask", "assess", "build", "calculate", "categor", "check", "choose", "classify",
    "compare", "complete", "convert", "create", "decide", "describe", "detect", "determine", "draft", "edit",
    "evaluate", "explain", "extract", "find", "fix", "format", "generate", "give", "help", "identify", "imagine",
    "label", "list", "make", "map", "name", "output", "plan", "predict", "pretend", "produce", "provide", "rank",
    "rate", "read", "recommend", "refactor", "reply", "respond", "return", "review", "rewrite", "score", "select",
    "solve", "sort", "suggest", "summar", "tell", "translate", "use", "verify", "write", "you are", "your task")
LABEL_TASK = re.compile(r"(?i)\b(classif|label|categori[sz]e|sentiment|is (this|it|the following)\b|yes or no|"
                        r"true or false|which (one|of)|decide whether|determine whether)")
ANSWER_SPACE = re.compile(r"(?i)(\bone of\b|\boptions?\b|\bchoices?\b|\(a\)|\bA\)|\byes or no\b|\byes/no\b|"
                          r"true or false|\b\w+ or \w+\b[^.\n]{0,20}[.:?]|\bjson\b|\bschema\b|answer with|respond with|"
                          r"output (only|the word|one)|reply with|return (only|one)|\blabels?:|\bcategories:)")
THOUGHT = re.compile(r"(?i)step[- ]by[- ]step|think (it )?through|show (your )?(work|reasoning)|explain your reasoning|"
                     r"reason (about|through)|let'?s think|chain[- ]of[- ]thought|work this out")
FINAL_MARKER = re.compile(r"(?i)final answer|the answer is|answer:|\banswer\s*(\(|in|on|as)|end with|last line|"
                          r"conclude with|output (the|your) (label|answer)|<answer>|\"answer\"")
OPINION = re.compile(r"(?i)\b(i (really )?(think|believe|feel|like|love|hate|dislike|prefer)|i'?m (sure|confident|"
                     r"certain)|in my opinion|obviously|clearly (wrong|right|correct|better)|are you sure|"
                     r"i am confident you are wrong|everyone knows)\b")
PRESUPPOSE = re.compile(r"(?i)\b((detect|find|list|identify|highlight) (all (the )?|every |the )(instances?|places?|parts?|"
                        r"bugs?|errors?|mistakes?|problems?|issues?|flaws?)[^.\n]{0,40}\b(is|are|where|in)\b|"
                        r"explain why [^.\n]{0,60}\b(is|are) (wrong|bad|harmful|incorrect|better|worse)|"
                        r"why is [^.\n]{0,40}\b(better|worse|wrong|bad)\b)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
PHONE = re.compile(r"(?<![\w.])\+?\d[\d ()-]{8,}\d(?![\w.])")
DELIMS = ("```", '"""', "'''", "---", "###", "<", "[", "'", '"', "`", "====", "~~~")
# Exemplar shapes: "text: label" lines, or Q:/A: (Input:/Output:, Question:/Answer:) blocks.
PAIR_SEPS = [(" => ", "=>"), (" -> ", "->"), ("===", "==="), (" | ", "|"), (": ", ":"), ("\t", "tab")]
BLOCK_Q = re.compile(r"(?i)^(q|question|input|text|review|tweet|post|sentence|example)\s*:\s*(.*)$")
BLOCK_A = re.compile(r"(?i)^(a|answer|output|label|sentiment|category|class)\s*:\s*(.*)$")


def finding(rule, sev, line, msg, fix):
    return {"rule": rule, "severity": sev, "line": line, "message": msg, "fix": fix}


def load(path: str) -> str:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8", errors="replace")
    if path.endswith(".json") or text.lstrip().startswith(("[{", "{\"messages\"", "{\"system\"")):
        try:
            data = json.loads(text)
        except ValueError:
            return text
        msgs = data.get("messages", data) if isinstance(data, dict) else data
        parts = []
        if isinstance(data, dict) and isinstance(data.get("system"), str):
            parts.append(data["system"])
        for m in msgs if isinstance(msgs, list) else []:
            c = m.get("content", "") if isinstance(m, dict) else ""
            if isinstance(c, list):
                c = "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
            role = m.get("role", "") if isinstance(m, dict) else ""
            # a user or tool message is already separated from the instructions by its role
            parts.append(f"<{role}>\n{c}\n</{role}>" if role in ("user", "tool", "assistant") else str(c))
        return "\n\n".join(parts)
    return text


def exemplars(lines):
    """[(line_no, input, label, shape)] for few-shot exemplars found in the prompt."""
    out, i = [], 0
    while i < len(lines):                                         # Q:/A: blocks first
        mq = BLOCK_Q.match(lines[i].strip())
        if mq:
            j = i + 1
            while j < len(lines) and j <= i + 6 and not BLOCK_A.match(lines[j].strip()):
                if BLOCK_Q.match(lines[j].strip()):
                    break
                j += 1
            ma = BLOCK_A.match(lines[j].strip()) if j < len(lines) else None
            if ma and ma.group(2).strip() and not VAR.fullmatch(ma.group(2).strip()):
                out.append((i + 1, mq.group(2).strip(), ma.group(2).strip(), mq.group(1).lower() + "/" +
                            ma.group(1).lower()))
                i = j + 1
                continue
        i += 1
    if out:
        return out
    for no, raw in enumerate(lines, 1):                           # "text: label" one-liners
        s = raw.strip()
        if not s or len(s) > 300 or VAR.search(s) or s.endswith(":"):
            continue
        for sep, shape in PAIR_SEPS:
            if sep in s:
                left, right = s.rsplit(sep, 1)
                right = right.strip()
                if left.strip() and right and len(right.split()) <= 3 and not right.endswith((".", "?")) \
                        and not re.match(r"(?i)^(https?|note|example|step)\b", left.strip()):
                    out.append((no, left.strip(), right, shape))
                break
    return out if len(out) >= 3 else []


def lint(text: str):
    lines = text.splitlines()
    res = []
    flat = text.strip()
    if not flat:
        return [finding("empty", "high", 1, "The prompt is empty.", "Write the instruction or question.")]
    # directive
    low = flat.lower()
    has_q = "?" in flat
    if not has_q and not any(re.search(r"(?m)(^|[.:!]\s+|\n\s*[-*\d.)]*\s*)" + re.escape(v), low)
                             for v in DIRECTIVE_VERBS):
        ex = exemplars(lines)
        if not ex:
            res.append(finding("no-directive", "medium", 1, "No instruction or question found.",
                               "State the task as an instruction or a question (the directive)."))
    # template variables and delimiters
    variables = sorted(set(m.group(0) for m in VAR.finditer(text)))
    for no, raw in enumerate(lines, 1):
        for m in VAR.finditer(raw):
            prev = lines[no - 2].strip() if no > 1 else ""
            nxt = lines[no].strip() if no < len(lines) else ""
            before, after = raw[:m.start()].strip(), raw[m.end():].strip()
            wrapped = (before.endswith(DELIMS) or after.startswith(tuple(d[::-1] if d == "<" else d for d in DELIMS))
                       or prev.startswith(DELIMS) or nxt.startswith(DELIMS + ("</",)) or before.endswith(":"))
            name = m.group(0).strip("{}$ ").lower()
            if not wrapped and re.search(r"input|text|query|question|message|document|content|post|review|tweet|"
                                         r"user|paragraph|email|data|code|article", name):
                res.append(finding("input-not-delimited", "medium", no,
                                   f"{m.group(0)} is inserted without delimiters.",
                                   "Wrap inserted text in delimiters (e.g. <input>...</input> or triple quotes) and "
                                   "say it is data to work on, not instructions."))
    # few-shot exemplars
    ex = exemplars(lines)
    if ex:
        labels = [e[2].lower().strip(" .") for e in ex]
        counts = Counter(labels)
        n = len(ex)
        if 2 <= len(counts) <= max(2, n // 2) and n >= 4:
            (top, hi), lo = counts.most_common(1)[0], min(counts.values())
            if hi >= 2 * lo and hi - lo >= 2:
                res.append(finding("exemplar-label-imbalance", "medium", ex[0][0],
                                   f"Exemplar labels are unbalanced: {dict(counts)}. The model leans toward '{top}'.",
                                   "Give each label about the same number of exemplars."))
            runs = sum(1 for a, b in zip(labels, labels[1:]) if a != b)
            same_tail = next((k for k, lab in enumerate(reversed(labels)) if lab != labels[-1]), n)
            if runs == len(counts) - 1 and n >= 4:
                res.append(finding("exemplar-labels-grouped", "medium", ex[0][0],
                                   "Exemplars are grouped by label; order changes accuracy a lot.",
                                   "Shuffle the exemplars so labels are mixed (and try 2-3 orders)."))
            elif same_tail >= 3 and same_tail >= n // 2:
                res.append(finding("exemplar-label-run-at-end", "low", ex[-same_tail][0],
                                   f"The last {same_tail} exemplars all have label '{labels[-1]}'; "
                                   "the latest exemplars pull the answer toward their label.",
                                   "Mix the order so the final exemplars cover different labels."))
        shapes = Counter(e[3] for e in ex)
        if len(shapes) > 1:
            res.append(finding("exemplar-format-mixed", "medium", ex[0][0],
                               f"Exemplars use different formats: {', '.join(shapes)}.",
                               "Use one exemplar format throughout, the same one the real input uses."))
        dupes = [k for k, v in Counter(e[1].lower() for e in ex).items() if v > 1]
        if dupes:
            res.append(finding("exemplar-duplicate", "low", ex[0][0], f"{len(dupes)} exemplar input(s) repeat.",
                               "Remove duplicates; use the space for more varied exemplars."))
        if n > 20:
            res.append(finding("exemplar-many", "info", ex[0][0], f"{n} exemplars: gains often flatten after ~20.",
                               "Measure whether the extra exemplars help on a dev set; drop them if not."))
    # answer engineering
    if LABEL_TASK.search(flat) and not ANSWER_SPACE.search(flat) and not ex:
        no = next(i for i, l in enumerate(lines, 1) if LABEL_TASK.search(l))
        res.append(finding("answer-space-unspecified", "medium", no,
                           "A labeling task without the allowed answers, so outputs will vary in form "
                           "(\"It's hate speech\", \"Hate Speech.\", ...).",
                           "List the allowed labels and the exact output form (e.g. 'Answer with one word: Yes or No')."))
    m = THOUGHT.search(flat)
    if m and not FINAL_MARKER.search(flat):
        no = flat[:m.start()].count("\n") + 1
        res.append(finding("reasoning-without-answer-marker", "medium", no,
                           "Reasoning is requested but not where the final answer goes, so it is hard to extract.",
                           "End with a fixed marker ('Final answer: <label>') and extract the LAST match."))
    # wording that biases the model (exemplar lines and delimited input are data, not the author's words)
    data_lines = {e[0] for e in ex} | {e[0] + 1 for e in ex if "/" in e[3]}
    inside = False
    for no, raw in enumerate(lines, 1):
        if raw.strip().startswith(("```", '"""', "'''", "~~~")):
            inside = not inside
            continue
        if inside or no in data_lines:
            continue
        mo = OPINION.search(raw)
        if mo:
            res.append(finding("leading-opinion", "medium", no, f"States an opinion ('{mo.group(0)}').",
                               "Remove your own view from the prompt; models tend to agree with the user."))
        mp = PRESUPPOSE.search(raw)
        if mp:
            res.append(finding("false-presupposition", "low", no,
                               f"Assumes the answer ('{mp.group(0)[:60]}').",
                               "Ask whether, not where: 'Is any part ... ? If so, which?'"))
        for rx, kind in ((EMAIL, "email address"), (PHONE, "phone number")):
            if rx.search(raw) and not VAR.search(raw):
                res.append(finding("personal-data", "low", no, f"Contains an {kind}.",
                                   "Remove or replace personal data before sending prompts to a model."))
                break
    return res, variables, ex


def report(path, text, res, variables, ex, as_json):
    tokens = (len(text) + 3) // 4
    res = sorted(res, key=lambda f: (-LEVELS[f["severity"]], f["line"]))
    if as_json:
        return {"file": path, "tokens": tokens, "variables": variables, "exemplars": len(ex), "findings": res}
    head = f"{path}: ~{tokens} tokens, {len(ex)} exemplar(s)" + (f", variables {' '.join(variables)}" if variables else "")
    if not res:
        return head + "\n  no findings."
    out = [head + f", {len(res)} finding(s)"]
    for f in res:
        out.append(f"  {f['severity'].upper():6} line {f['line']:<4} {f['rule']}: {f['message']}")
        out.append(f"         fix: {f['fix']}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lint prompts and prompt templates.")
    ap.add_argument("files", nargs="+", help="prompt files, or - for stdin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on", choices=list(LEVELS), default="medium")
    a = ap.parse_args(argv)
    worst, out = -1, []
    for f in a.files:
        if f != "-" and not Path(f).is_file():
            print(f"error: no such file: {f}", file=sys.stderr)
            return 2
        text = load(f)
        res, variables, ex = lint(text)
        out.append(report(f, text, res, variables, ex, a.json))
        worst = max([worst] + [LEVELS[r["severity"]] for r in res])
    print(json.dumps(out if len(out) > 1 else out[0], indent=2) if a.json else "\n\n".join(out))
    return 1 if worst >= LEVELS[a.fail_on] else 0


if __name__ == "__main__":
    sys.exit(main())
