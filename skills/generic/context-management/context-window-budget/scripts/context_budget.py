#!/usr/bin/env python3
"""Analyse, budget and trim the context window of an LLM conversation.

Usage:
  python context_budget.py analyze <transcript.json|.jsonl> [--window N] [--keep-last N] [--top N] [--json]
  python context_budget.py trim    <transcript.json|.jsonl> --budget N [--keep-last N] [--tool-max N]
                                   [--strategies truncate-tools,clear-tools,drop-oldest] [--summary TEXT]
                                   [--out FILE]
  python context_budget.py plan    --window N [--system N] [--tools N] [--output N] [--retrieval N]
                                   [--margin 0.1] [--json]

Transcripts: a JSON list of messages, an object with "messages" (and optional
"system" and "tools"), or JSONL with one message per line. Messages use
role/content, where content is a string or a list of blocks (text, image,
tool_use, tool_result), or the tool_calls / role "tool" style.

`analyze` and `plan` are read-only. `trim` writes only to --out (never over
the input or an existing file) and never splits a tool call from its result.
Python 3.8+, standard library only. Token counts are estimates (chars / 4,
images ~1600): use your provider's token counter for exact numbers.
"""
import argparse
import copy
import hashlib
import json
import os
import sys

IMAGE_TOKENS = 1600
STRATEGIES = ("truncate-tools", "clear-tools", "drop-oldest")


def tokens(text):
    return (len(text) + 3) // 4


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- loading
def load(path):
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    try:
        data = json.loads(raw)
    except ValueError:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(data, dict):
        convo = {"messages": data.get("messages") or [], "system": data.get("system"), "tools": data.get("tools")}
        convo["extra"] = {k: v for k, v in data.items() if k not in ("messages", "system", "tools")}
    elif isinstance(data, list):
        convo = {"messages": data, "system": None, "tools": None, "extra": {}, "list": True}
    else:
        raise ValueError("transcript must be a JSON list, an object with 'messages', or JSONL")
    for i, m in enumerate(convo["messages"]):
        if not isinstance(m, dict) or "role" not in m:
            raise ValueError("message %d has no 'role'" % i)
    return convo


def save(convo):
    if convo.get("list"):
        return convo["messages"]
    out = dict(convo.get("extra") or {})
    if convo.get("system") is not None:
        out["system"] = convo["system"]
    if convo.get("tools") is not None:
        out["tools"] = convo["tools"]
    out["messages"] = convo["messages"]
    return out


# ---------------------------------------------------------------- measuring
def block_text(block):
    """(kind, text, image_count) for one content block."""
    if isinstance(block, str):
        return "text", block, 0
    if not isinstance(block, dict):
        return "other", dumps(block), 0
    t = block.get("type", "")
    if t in ("text", "input_text", "output_text"):
        return "text", block.get("text", ""), 0
    if t in ("image", "image_url", "input_image"):
        return "image", "", 1
    if t == "tool_use":
        return "tool_call", (block.get("name") or "") + dumps(block.get("input", {})), 0
    if t == "tool_result":
        inner, images = [], 0
        content = block.get("content", "")
        for b in content if isinstance(content, list) else [content]:
            _, txt, img = block_text(b)
            inner.append(txt)
            images += img
        return "tool_result", "\n".join(inner), images
    if t in ("thinking", "reasoning"):
        return "thinking", block.get("thinking") or block.get("text") or "", 0
    return "other", dumps(block), 0


def parts(msg):
    """List of (kind, text, images) for a message."""
    role = msg.get("role")
    content = msg.get("content")
    out = []
    if role == "tool":
        _, txt, img = block_text({"type": "tool_result", "content": content})
        out.append(("tool_result", txt, img))
    elif isinstance(content, list):
        out.extend(block_text(b) for b in content)
    elif content is not None:
        out.append(("text", str(content), 0))
    for call in msg.get("tool_calls") or []:
        fn = call.get("function", {}) if isinstance(call, dict) else {}
        out.append(("tool_call", (fn.get("name") or "") + str(fn.get("arguments", "")), 0))
    return out


def msg_tokens(msg):
    return 4 + sum(tokens(t) + img * IMAGE_TOKENS for _, t, img in parts(msg))


def system_tokens(convo):
    s = convo.get("system")
    if s is None:
        return 0
    return tokens(s if isinstance(s, str) else "".join(block_text(b)[1] for b in s))


def tools_tokens(convo):
    return tokens(dumps(convo["tools"])) if convo.get("tools") else 0


def total_tokens(convo):
    return system_tokens(convo) + tools_tokens(convo) + sum(msg_tokens(m) for m in convo["messages"])


def is_real_user(msg):
    """A user turn typed by a person, not a message carrying only tool results."""
    if msg.get("role") != "user":
        return False
    kinds = [k for k, _, _ in parts(msg)]
    return not kinds or any(k != "tool_result" for k in kinds)


def turn_starts(messages):
    return [i for i, m in enumerate(messages) if is_real_user(m)]


def protected_from(messages, keep_last):
    """Index from which messages are kept untouched: snapped back to a turn start."""
    if keep_last <= 0:
        return len(messages)
    cut = max(0, len(messages) - keep_last)
    starts = [s for s in turn_starts(messages) if s <= cut]
    return starts[-1] if starts else 0


def analyze(convo, window=None, keep_last=6, top=10):
    msgs = convo["messages"]
    by_role, by_kind, items, seen = {}, {}, [], {}
    dup_tokens = 0
    for i, m in enumerate(msgs):
        role = m.get("role", "?")
        for kind, text, img in parts(m):
            t = tokens(text) + img * IMAGE_TOKENS
            by_role[role] = by_role.get(role, 0) + t
            by_kind[kind] = by_kind.get(kind, 0) + t
            items.append({"index": i, "role": role, "kind": kind, "tokens": t,
                          "preview": " ".join(text.split())[:70]})
            if kind == "tool_result" and t > 50:
                h = hashlib.sha1(text.encode("utf-8")).hexdigest()
                if h in seen:
                    dup_tokens += t
                seen[h] = True
    sys_t, tools_t = system_tokens(convo), tools_tokens(convo)
    total = total_tokens(convo)
    cut = protected_from(msgs, keep_last)
    old_tool = sum(it["tokens"] for it in items if it["kind"] == "tool_result" and it["index"] < cut)
    report = {"messages": len(msgs), "turns": len(turn_starts(msgs)), "total_tokens": total,
              "system_tokens": sys_t, "tool_definition_tokens": tools_t,
              "by_role": by_role, "by_kind": by_kind,
              "largest": sorted(items, key=lambda x: -x["tokens"])[:top],
              "duplicate_tool_result_tokens": dup_tokens,
              "old_tool_result_tokens": old_tool, "keep_last": keep_last, "recommendations": []}
    if window:
        report["window"] = window
        report["used_pct"] = round(100.0 * total / window, 1)
    rec = report["recommendations"]
    tool_res = by_kind.get("tool_result", 0)
    if total and tool_res / float(total) > 0.4:
        rec.append("Tool results are %d%% of the context: cap tool output size and clear old results"
                   % (100 * tool_res // total))
    if old_tool > 0.2 * total and old_tool > 1000:
        rec.append("%d tokens of tool results are older than the last %d messages: 'trim --strategies clear-tools'"
                   % (old_tool, keep_last))
    if dup_tokens > 500:
        rec.append("%d tokens are repeated tool results (the same file or output read twice): cache or dedupe"
                   % dup_tokens)
    if total and (sys_t + tools_t) / float(total) > 0.5 and total > 4000:
        rec.append("System prompt and tool definitions are over half the context: shorten them or load tools on demand")
    if tools_t > 5000:
        rec.append("Tool definitions use %d tokens on every call: expose fewer tools per request" % tools_t)
    if window and total > 0.8 * window:
        rec.append("Over 80%% of the window: compact or trim now ('trim --budget %d')" % int(0.6 * window))
    big = [it for it in items if it["tokens"] > 8000]
    if big:
        rec.append("%d single items exceed 8000 tokens (largest: message %d, %s): truncate or summarise them"
                   % (len(big), big[0]["index"], big[0]["kind"]))
    return report


# ---------------------------------------------------------------- trimming
def _replace_tool_results(msg, fn):
    """Apply fn(text, tokens) -> new_text|None to every tool result in msg. Returns tokens saved."""
    saved = 0
    if msg.get("role") == "tool":
        _, txt, _ = block_text({"type": "tool_result", "content": msg.get("content")})
        new = fn(txt, tokens(txt))
        if new is not None:
            saved += tokens(txt) - tokens(new)
            msg["content"] = new
        return saved
    content = msg.get("content")
    if not isinstance(content, list):
        return 0
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            _, txt, img = block_text(b)
            new = fn(txt, tokens(txt) + img * IMAGE_TOKENS)
            if new is not None:
                saved += tokens(txt) + img * IMAGE_TOKENS - tokens(new)
                b["content"] = new
    return saved


def trim(convo, budget, keep_last=6, tool_max=2000, strategies=STRATEGIES, summary=None):
    convo = copy.deepcopy(convo)
    msgs = convo["messages"]
    actions = []
    before = total_tokens(convo)
    cut = protected_from(msgs, keep_last)

    def over():
        return total_tokens(convo) > budget

    if "truncate-tools" in strategies and over():
        keep_chars = tool_max * 4 // 2

        def shorten(text, t):
            if t <= tool_max:
                return None
            return "%s\n[... %d tokens trimmed to fit the context budget ...]\n%s" % (
                text[:keep_chars], t - tool_max, text[-keep_chars:])
        saved = sum(_replace_tool_results(m, shorten) for m in msgs[:cut])
        if saved:
            actions.append("truncate-tools: tool results over %d tokens cut to head and tail (-%d tokens)"
                           % (tool_max, saved))
    if "clear-tools" in strategies and over():
        saved, n = 0, 0
        for m in msgs[:cut]:
            s = _replace_tool_results(m, lambda text, t: None if t < 40 else
                                      "[tool result cleared to save context: %d tokens; re-run the tool if needed]" % t)
            if s > 0:
                saved += s
                n += 1
            if not over():
                break
        if saved:
            actions.append("clear-tools: cleared old tool results in %d message(s) (-%d tokens)" % (n, saved))
    if "drop-oldest" in strategies and over():
        starts = turn_starts(msgs)
        # Turn 0 holds the task; never drop it or anything in the protected tail.
        droppable = [(s, e) for s, e in zip(starts, starts[1:] + [len(msgs)]) if s != starts[0] and e <= cut] \
            if starts else []
        dropped, dropped_tokens = set(), 0
        for s, e in droppable:
            if not over():
                break
            for i in range(s, e):
                dropped.add(i)
                dropped_tokens += msg_tokens(msgs[i])
            # measure as if removed
            convo["messages"] = [m for i, m in enumerate(msgs) if i not in dropped]
            still_over = over()
            convo["messages"] = msgs
            if not still_over:
                break
        if dropped:
            first_kept = min((i for i in range(len(msgs)) if i not in dropped and i > min(dropped)), default=None)
            note = "[%d earlier messages (~%d tokens) were removed to fit the context window.%s]" % (
                len(dropped), dropped_tokens, (" Summary: " + summary) if summary else "")
            target = None if first_kept is None else msgs[first_kept]
            if target is None:
                msgs.append({"role": "user", "content": note})
            elif isinstance(target.get("content"), list):
                target["content"] = [{"type": "text", "text": note}] + target["content"]
            else:
                target["content"] = note + "\n\n" + str(target.get("content") or "")
            convo["messages"] = [m for i, m in enumerate(msgs) if i not in dropped]
            actions.append("drop-oldest: removed %d message(s) in whole turns (-%d tokens), first task turn kept"
                           % (len(dropped), dropped_tokens))
    after = total_tokens(convo)
    return convo, {"before": before, "after": after, "budget": budget, "fits": after <= budget,
                   "protected_messages": len(msgs) - cut, "actions": actions}


# ---------------------------------------------------------------- planning
def plan(window, system=0, tools=0, output=4096, retrieval=0, margin=0.1):
    reserve = int(window * margin)
    fixed = system + tools
    available = window - output - reserve - fixed
    rows = [("system prompt", system), ("tool definitions", tools), ("output reserve", output),
            ("safety margin", reserve), ("retrieved documents", retrieval),
            ("conversation history", max(0, available - retrieval))]
    warnings = []
    if available - retrieval < 0:
        warnings.append("Fixed parts and retrieval exceed the window: cut retrieval top-k or chunk size")
    if fixed > 0.25 * window:
        warnings.append("System prompt + tools exceed 25% of the window: shorten or load tools on demand")
    if output > 0.25 * window:
        warnings.append("Output reserve is over 25% of the window: is that much output needed?")
    history = max(0, available - retrieval)
    return {"window": window, "rows": [{"part": p, "tokens": t, "pct": round(100.0 * t / window, 1)}
                                       for p, t in rows],
            "compact_at": fixed + retrieval + int(0.7 * history),
            "trim_to": fixed + retrieval + int(0.4 * history),
            "warnings": warnings}


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    a1 = sub.add_parser("analyze", help="where the tokens go")
    a1.add_argument("transcript")
    a1.add_argument("--window", type=int)
    a1.add_argument("--keep-last", type=int, default=6)
    a1.add_argument("--top", type=int, default=10)
    a1.add_argument("--json", action="store_true")
    t1 = sub.add_parser("trim", help="fit a transcript into a token budget")
    t1.add_argument("transcript")
    t1.add_argument("--budget", type=int, required=True)
    t1.add_argument("--keep-last", type=int, default=6, help="recent messages never changed (snapped to a turn)")
    t1.add_argument("--tool-max", type=int, default=2000, help="max tokens per old tool result")
    t1.add_argument("--strategies", default=",".join(STRATEGIES))
    t1.add_argument("--summary", help="summary text to put where old turns were removed")
    t1.add_argument("--out", help="write the trimmed transcript here (never the input, never overwrites)")
    p1 = sub.add_parser("plan", help="split a context window into budgets")
    p1.add_argument("--window", type=int, required=True)
    p1.add_argument("--system", type=int, default=0)
    p1.add_argument("--tools", type=int, default=0)
    p1.add_argument("--output", type=int, default=4096)
    p1.add_argument("--retrieval", type=int, default=0)
    p1.add_argument("--margin", type=float, default=0.1)
    p1.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        r = plan(a.window, a.system, a.tools, a.output, a.retrieval, a.margin)
        if a.json:
            print(json.dumps(r, indent=2))
            return 0
        print("Context budget for a %d-token window" % a.window)
        for row in r["rows"]:
            print("  %-22s %9d  %5.1f%%" % (row["part"], row["tokens"], row["pct"]))
        print("  compact or summarise when the prompt passes ~%d tokens; trim back to ~%d"
              % (r["compact_at"], r["trim_to"]))
        for w in r["warnings"]:
            print("  WARN " + w)
        return 0
    if a.cmd not in ("analyze", "trim"):
        ap.print_help()
        return 2
    try:
        convo = load(a.transcript)
    except (OSError, ValueError) as e:
        print("cannot read %s: %s" % (a.transcript, e), file=sys.stderr)
        return 2
    if a.cmd == "analyze":
        r = analyze(convo, a.window, a.keep_last, a.top)
        if a.json:
            print(json.dumps(r, indent=2))
            return 0
        head = "%d messages, %d turns, ~%d tokens" % (r["messages"], r["turns"], r["total_tokens"])
        if a.window:
            head += " (%.1f%% of %d)" % (r["used_pct"], a.window)
        print(head)
        print("  system ~%d, tool definitions ~%d" % (r["system_tokens"], r["tool_definition_tokens"]))
        print("  by kind: " + ", ".join("%s %d" % kv for kv in sorted(r["by_kind"].items(), key=lambda x: -x[1])))
        print("  largest items:")
        for it in r["largest"]:
            print("    #%-4d %-9s %-11s %7d  %s" % (it["index"], it["role"], it["kind"], it["tokens"], it["preview"]))
        for rec in r["recommendations"]:
            print("  TIP  " + rec)
        return 0
    strategies = [s.strip() for s in a.strategies.split(",") if s.strip()]
    bad = [s for s in strategies if s not in STRATEGIES]
    if bad:
        print("unknown strategy: %s (choose from %s)" % (", ".join(bad), ", ".join(STRATEGIES)), file=sys.stderr)
        return 2
    new, r = trim(convo, a.budget, a.keep_last, a.tool_max, strategies, a.summary)
    print("~%d -> ~%d tokens (budget %d, last %d messages untouched)"
          % (r["before"], r["after"], r["budget"], r["protected_messages"]))
    for act in r["actions"] or ["nothing to do"]:
        print("  " + act)
    if not r["fits"]:
        print("  STILL OVER BUDGET: lower --keep-last or --tool-max, add a --summary and drop more, "
              "or shorten the system prompt and tools")
    if a.out:
        if os.path.exists(a.out) or os.path.abspath(a.out) == os.path.abspath(a.transcript):
            print("refusing to overwrite %s" % a.out, file=sys.stderr)
            return 2
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(save(new), fh, ensure_ascii=False, indent=1)
        print("  wrote " + a.out)
    return 0 if r["fits"] else 1


if __name__ == "__main__":
    sys.exit(main())
