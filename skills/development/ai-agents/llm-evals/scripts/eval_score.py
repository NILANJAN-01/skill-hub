#!/usr/bin/env python3
"""Score LLM / agent outputs against an eval case set.

Usage:
    python eval_score.py cases.jsonl outputs.jsonl [--report out.json]
                         [--baseline old_report.json] [--min-pass 0.9] [--no-regressions] [--json]

cases.jsonl:   {"id", "input", "tags": [...], "checks": [{"type": ..., "value": ...}, ...]}
outputs.jsonl: {"id", "output" | "response" | "completion", "tool_calls": [...], "judge_pass", "judge": {...}}

Standard library only. Exit codes: 0 ok, 1 below --min-pass or regressions
with --no-regressions, 2 unreadable input.
"""
import argparse
import json
import re
import sys
from collections import OrderedDict, defaultdict

CHECK_TYPES = ("exact", "contains", "icontains", "not_contains", "regex", "not_regex", "one_of", "json_valid",
               "json_field", "min_chars", "max_chars", "tool_called", "tool_not_called", "judge")


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise ValueError("%s line %d: %s" % (path, n, exc))
    return rows


def _output_text(rec):
    for key in ("output", "response", "completion"):
        if key in rec:
            val = rec[key]
            return val if isinstance(val, str) else json.dumps(val)
    return ""


def _parse_json(text):
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def _get_path(obj, path):
    for part in str(path).split("."):
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            obj = obj[part]
        else:
            raise KeyError(part)
    return obj


def _tool_names(rec):
    names = []
    for call in rec.get("tool_calls") or []:
        if isinstance(call, dict):
            name = call.get("name") or (call.get("function") or {}).get("name")
            if name:
                names.append(name)
        elif isinstance(call, str):
            names.append(call)
    return names


def run_check(check, rec):
    """Return (status, reason) where status is 'pass', 'fail' or 'pending'."""
    ctype = check.get("type")
    value = check.get("value")
    text = _output_text(rec)
    if ctype == "exact":
        ok = text.strip() == str(value).strip()
        return ("pass" if ok else "fail"), "output is not exactly %r" % value
    if ctype == "contains":
        return ("pass" if str(value) in text else "fail"), "missing %r" % value
    if ctype == "icontains":
        return ("pass" if str(value).lower() in text.lower() else "fail"), "missing %r (case-insensitive)" % value
    if ctype == "not_contains":
        return ("pass" if str(value).lower() not in text.lower() else "fail"), "must not contain %r" % value
    if ctype in ("regex", "not_regex"):
        found = re.search(str(value), text, re.IGNORECASE | re.MULTILINE) is not None
        ok = found if ctype == "regex" else not found
        return ("pass" if ok else "fail"), ("no match for /%s/" if ctype == "regex" else "matched /%s/") % value
    if ctype == "one_of":
        options = [str(v).strip().lower() for v in (value or [])]
        return ("pass" if text.strip().lower() in options else "fail"), "output not one of %s" % value
    if ctype == "json_valid":
        try:
            _parse_json(text)
            return "pass", ""
        except ValueError as exc:
            return "fail", "invalid JSON: %s" % exc
    if ctype == "json_field":
        try:
            actual = _get_path(_parse_json(text), check.get("path", ""))
        except ValueError as exc:
            return "fail", "invalid JSON: %s" % exc
        except (KeyError, IndexError, TypeError):
            return "fail", "field %r not found" % check.get("path")
        return ("pass" if actual == value else "fail"), "field %r is %r, expected %r" % (check.get("path"), actual, value)
    if ctype == "min_chars":
        return ("pass" if len(text) >= int(value) else "fail"), "%d chars < %s" % (len(text), value)
    if ctype == "max_chars":
        return ("pass" if len(text) <= int(value) else "fail"), "%d chars > %s" % (len(text), value)
    if ctype == "tool_called":
        names = _tool_names(rec)
        return ("pass" if value in names else "fail"), "tool %r not called (called: %s)" % (value, names or "none")
    if ctype == "tool_not_called":
        return ("pass" if value not in _tool_names(rec) else "fail"), "tool %r was called" % value
    if ctype == "judge":
        rubric = check.get("rubric") or check.get("value") or ""
        verdict = (rec.get("judge") or {}).get(rubric) if isinstance(rec.get("judge"), dict) else None
        if verdict is None:
            verdict = rec.get("judge_pass")
        if verdict is None:
            return "pending", "no judge result for %r" % rubric
        return ("pass" if verdict else "fail"), "judge failed: %s" % rubric
    return "fail", "unknown check type %r (known: %s)" % (ctype, ", ".join(CHECK_TYPES))


def score(cases, outputs):
    by_id = {}
    for rec in outputs:
        if "id" in rec:
            by_id[str(rec["id"])] = rec
    results = OrderedDict()
    for case in cases:
        cid = str(case.get("id"))
        rec = by_id.get(cid)
        checks = case.get("checks") or []
        if rec is None:
            results[cid] = {"status": "fail", "tags": case.get("tags") or [], "failures": ["missing output"],
                            "pending": [], "checks": {}}
            continue
        failures, pending, per_type = [], [], {}
        for check in checks:
            status, reason = run_check(check, rec)
            per_type.setdefault(check.get("type"), []).append(status)
            if status == "fail":
                failures.append("%s: %s" % (check.get("type"), reason))
            elif status == "pending":
                pending.append(reason)
        if not checks:
            pending.append("case has no checks")
        status = "fail" if failures else ("pending" if pending else "pass")
        results[cid] = {"status": status, "tags": case.get("tags") or [], "failures": failures,
                        "pending": pending, "checks": per_type}
    extra = sorted(set(by_id) - set(results))
    return results, extra


def summarize(results, extra, baseline=None):
    total = len(results)
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    pending = sum(1 for r in results.values() if r["status"] == "pending")
    graded = total - pending
    tags = defaultdict(lambda: [0, 0])
    types = defaultdict(lambda: [0, 0])
    for r in results.values():
        for tag in r["tags"] or ["(untagged)"]:
            if r["status"] != "pending":
                tags[tag][1] += 1
                tags[tag][0] += r["status"] == "pass"
        for ctype, statuses in r["checks"].items():
            for s in statuses:
                if s != "pending":
                    types[ctype][1] += 1
                    types[ctype][0] += s == "pass"
    summary = {
        "cases": total, "passed": passed, "failed": graded - passed, "pending": pending,
        "pass_rate": round(passed / float(graded), 4) if graded else 0.0,
        "by_tag": {t: {"passed": p, "total": n, "pass_rate": round(p / float(n), 4)} for t, (p, n) in sorted(tags.items())},
        "by_check": {t: {"passed": p, "total": n} for t, (p, n) in sorted(types.items())},
        "outputs_without_case": extra,
        "results": results,
    }
    if baseline is not None:
        old = baseline.get("results", {})
        summary["regressions"] = [cid for cid, r in results.items()
                                  if r["status"] == "fail" and old.get(cid, {}).get("status") == "pass"]
        summary["fixed"] = [cid for cid, r in results.items()
                            if r["status"] == "pass" and old.get(cid, {}).get("status") == "fail"]
        summary["baseline_pass_rate"] = baseline.get("pass_rate")
    return summary


def format_text(s):
    out = ["Pass rate: %.1f%% (%d/%d graded, %d pending)" % (s["pass_rate"] * 100, s["passed"],
                                                              s["passed"] + s["failed"], s["pending"])]
    if "baseline_pass_rate" in s and s["baseline_pass_rate"] is not None:
        out.append("Baseline:  %.1f%%  (delta %+.1f points)" % (s["baseline_pass_rate"] * 100,
                                                               (s["pass_rate"] - s["baseline_pass_rate"]) * 100))
    if s["by_tag"]:
        out.append("\nBy tag:")
        for tag, v in s["by_tag"].items():
            out.append("  %-20s %5.1f%%  (%d/%d)" % (tag, v["pass_rate"] * 100, v["passed"], v["total"]))
    if s["by_check"]:
        out.append("\nBy check type:")
        for ctype, v in s["by_check"].items():
            out.append("  %-20s %d/%d passed" % (ctype, v["passed"], v["total"]))
    failing = [(cid, r) for cid, r in s["results"].items() if r["status"] == "fail"]
    if failing:
        out.append("\nFailing cases:")
        for cid, r in failing:
            out.append("  %s: %s" % (cid, "; ".join(r["failures"])))
    pend = [(cid, r) for cid, r in s["results"].items() if r["status"] == "pending"]
    if pend:
        out.append("\nPending (need judge results):")
        for cid, r in pend:
            out.append("  %s: %s" % (cid, "; ".join(r["pending"])))
    if s.get("regressions") is not None:
        out.append("\nRegressions (passed in baseline, fail now): %s" % (", ".join(s["regressions"]) or "none"))
        out.append("Fixed (failed in baseline, pass now): %s" % (", ".join(s["fixed"]) or "none"))
    if s["outputs_without_case"]:
        out.append("\nOutputs with no matching case id: %s" % ", ".join(s["outputs_without_case"]))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cases")
    parser.add_argument("outputs")
    parser.add_argument("--report", help="write the full report as JSON to this file")
    parser.add_argument("--baseline", help="previous report JSON to compare against")
    parser.add_argument("--min-pass", type=float, help="fail (exit 1) if pass rate is below this, e.g. 0.9")
    parser.add_argument("--no-regressions", action="store_true", help="fail (exit 1) on any regression")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    opts = parser.parse_args(argv)
    try:
        cases = read_jsonl(opts.cases)
        outputs = read_jsonl(opts.outputs)
        baseline = None
        if opts.baseline:
            with open(opts.baseline, encoding="utf-8-sig") as fh:
                baseline = json.load(fh)
    except (OSError, ValueError) as exc:
        print("cannot read input: %s" % exc, file=sys.stderr)
        return 2
    ids = [str(c.get("id")) for c in cases]
    if len(set(ids)) != len(ids):
        print("duplicate case ids in %s" % opts.cases, file=sys.stderr)
        return 2
    results, extra = score(cases, outputs)
    summary = summarize(results, extra, baseline)
    if opts.report:
        with open(opts.report, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2) if opts.json else format_text(summary))
    if opts.min_pass is not None and summary["pass_rate"] < opts.min_pass:
        return 1
    if opts.no_regressions and summary.get("regressions"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
