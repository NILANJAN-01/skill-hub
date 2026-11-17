#!/usr/bin/env python3
"""Summarise a Playwright test report (JSON reporter or JUnit XML).

Usage:
    python pw_report.py <results.json|results.xml> [--slowest 10] [--baseline old-report] [--json]

Prints totals, failed tests with cause category, flaky tests (failed then passed on retry), failures
by cause and by project, the slowest tests, trace attachments, and (with --baseline) new failures
and fixes. Standard library only. Read-only.

Exit codes: 0 report read (whatever the test results), 2 unreadable input.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CATEGORIES = [
    ("strict-mode", re.compile(r"strict mode violation", re.I)),
    ("screenshot", re.compile(r"Screenshot comparison failed|pixels? \(ratio|toHaveScreenshot|toMatchSnapshot", re.I)),
    ("closed", re.compile(r"(Target|page|context|browser)[^\n]*(has been )?closed|Target crashed", re.I)),
    ("navigation", re.compile(r"net::ERR_|NS_ERROR_|page\.goto:|Navigation failed|ERR_CONNECTION|ECONNREFUSED", re.I)),
    ("timeout", re.compile(r"Timeout \d+ms exceeded|Test timeout of \d+ms|timed? ?out", re.I)),
    ("locator", re.compile(r"waiting for (get_?by|locator|selector)|element is not (visible|enabled|stable|attached)|"
                           r"outside of the viewport|intercepts pointer events|resolved to 0 elements", re.I)),
    ("assertion", re.compile(r"expect\(|Expected:|Received:|AssertionError|toBe|toEqual|to_have|to_be", re.I)),
]


def categorize(message):
    for name, rx in CATEGORIES:
        if rx.search(message or ""):
            return name
    return "other"


def first_line(message):
    for line in ANSI.sub("", message or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


# ---------------------------------------------------------------- readers

def _walk_suites(suites, path, out):
    for suite in suites or []:
        title = suite.get("title") or ""
        sub = path + [title] if title and not title.endswith((".ts", ".js", ".mjs", ".tsx", ".py")) else path
        for spec in suite.get("specs") or []:
            for test in spec.get("tests") or []:
                results = test.get("results") or []
                errors, attachments = [], []
                for r in results:
                    for err in (r.get("errors") or ([r["error"]] if r.get("error") else [])):
                        msg = err.get("message") or err.get("value") or ""
                        if msg:
                            errors.append(ANSI.sub("", msg))
                    for att in r.get("attachments") or []:
                        if att.get("name") == "trace" and att.get("path"):
                            attachments.append(att["path"])
                status = test.get("status") or ("expected" if spec.get("ok") else "unexpected")
                out.append({
                    "id": "%s > %s [%s]" % (spec.get("file") or suite.get("file") or "", " > ".join(sub + [spec.get("title", "")]),
                                            test.get("projectName") or ""),
                    "title": " > ".join(sub + [spec.get("title", "")]),
                    "file": spec.get("file") or suite.get("file") or "",
                    "line": spec.get("line"),
                    "project": test.get("projectName") or "",
                    "status": {"expected": "passed", "unexpected": "failed", "flaky": "flaky", "skipped": "skipped"}.get(status, status),
                    "retries": max([r.get("retry", 0) for r in results] or [0]),
                    "duration_ms": sum(r.get("duration", 0) or 0 for r in results),
                    "error": errors[-1] if errors else "",
                    "traces": attachments,
                })
        _walk_suites(suite.get("suites"), sub, out)


def read_json_report(data):
    tests = []
    _walk_suites(data.get("suites"), [], tests)
    global_errors = [ANSI.sub("", e.get("message", "")) for e in data.get("errors") or []]
    return tests, global_errors


def read_junit(root):
    tests = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        skipped = case.find("skipped") is not None
        msg = ""
        if failure is not None:
            msg = (failure.get("message") or "") + "\n" + (failure.text or "")
        name, classname = case.get("name", ""), case.get("classname", "")
        traces = re.findall(r"\[\[ATTACHMENT\|([^\]]*trace[^\]]*\.zip)\]\]", ET.tostring(case, encoding="unicode"))
        tests.append({"id": "%s > %s" % (classname, name), "title": name, "file": case.get("file") or classname,
                      "line": None, "project": "", "status": "skipped" if skipped else ("failed" if failure is not None else "passed"),
                      "retries": 0, "duration_ms": int(float(case.get("time") or 0) * 1000),
                      "error": ANSI.sub("", msg).strip(), "traces": traces})
    return tests, []


def load(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig", errors="replace").lstrip()
    if text.startswith("<"):
        return read_junit(ET.fromstring(text))
    start = text.find("{")
    if start < 0:
        raise ValueError("neither JSON nor JUnit XML")
    return read_json_report(json.loads(text[start:]))


# ---------------------------------------------------------------- summary

def summarize(tests, global_errors, slowest=10, baseline=None):
    counts = Counter(t["status"] for t in tests)
    failed = [t for t in tests if t["status"] == "failed"]
    flaky = [t for t in tests if t["status"] == "flaky"]
    for t in failed + flaky:
        t["category"] = categorize(t["error"])
        t["message"] = first_line(t["error"])
    s = {
        "total": len(tests), "passed": counts.get("passed", 0), "failed": len(failed), "flaky": len(flaky),
        "skipped": counts.get("skipped", 0),
        "duration_s": round(sum(t["duration_ms"] for t in tests) / 1000.0, 1),
        "global_errors": [first_line(e) for e in global_errors],
        "failures": [{k: t[k] for k in ("title", "file", "line", "project", "retries", "category", "message", "traces")} for t in failed],
        "flaky_tests": [{k: t[k] for k in ("title", "file", "line", "project", "retries", "category", "message")} for t in flaky],
        "by_category": dict(Counter(t["category"] for t in failed).most_common()),
        "by_project": dict(Counter(t["project"] or "(default)" for t in failed).most_common()),
        "slowest": [{"title": t["title"], "project": t["project"], "seconds": round(t["duration_ms"] / 1000.0, 1)}
                    for t in sorted(tests, key=lambda t: -t["duration_ms"])[:slowest] if t["duration_ms"]],
    }
    if baseline is not None:
        before = {t["id"]: t["status"] for t in baseline}
        s["new_failures"] = [t["id"] for t in failed if before.get(t["id"]) in ("passed", "flaky")]
        s["fixed"] = [t["id"] for t in tests if t["status"] == "passed" and before.get(t["id"]) == "failed"]
        s["still_failing"] = [t["id"] for t in failed if before.get(t["id"]) == "failed"]
    return s


def format_text(s):
    out = [f"Tests: {s['total']}  passed {s['passed']}  failed {s['failed']}  flaky {s['flaky']}  "
           f"skipped {s['skipped']}  ({s['duration_s']}s of test time)"]
    if s["global_errors"]:
        out.append("\nErrors outside tests (setup, config, webServer):")
        out.extend(f"  {e}" for e in s["global_errors"])
    if s["failures"]:
        out.append("\nFailed:")
        for f in s["failures"]:
            where = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            proj = f" [{f['project']}]" if f["project"] else ""
            out.append(f"  [{f['category']}] {f['title']}{proj}  ({where}, retries {f['retries']})")
            if f["message"]:
                out.append(f"      {f['message']}")
            for tr in f["traces"][-1:]:
                out.append(f"      trace: npx playwright show-trace \"{tr}\"")
    if s["flaky_tests"]:
        out.append("\nFlaky (failed, then passed on retry):")
        for f in s["flaky_tests"]:
            proj = f" [{f['project']}]" if f["project"] else ""
            out.append(f"  [{f['category']}] {f['title']}{proj}  ({f['file']})  {f['message']}")
    if s["by_category"]:
        out.append("\nFailures by cause:   " + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()))
        out.append("Failures by project: " + ", ".join(f"{k} {v}" for k, v in s["by_project"].items()))
    if s["slowest"]:
        out.append("\nSlowest:")
        out.extend(f"  {t['seconds']:>7.1f}s  {t['title']}" + (f" [{t['project']}]" if t["project"] else "") for t in s["slowest"])
    if "new_failures" in s:
        out.append("\nCompared with the baseline:")
        out.append("  new failures:  " + (", ".join(s["new_failures"]) or "none"))
        out.append("  fixed:         " + (", ".join(s["fixed"]) or "none"))
        out.append("  still failing: " + (", ".join(s["still_failing"]) or "none"))
    if not s["failures"] and not s["flaky_tests"] and not s["global_errors"]:
        out.append("\nNo failures or flaky tests.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report", help="Playwright JSON report or JUnit XML")
    ap.add_argument("--slowest", type=int, default=10, help="how many slowest tests to list (default 10)")
    ap.add_argument("--baseline", help="an earlier report (JSON or JUnit) to compare with")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    opts = ap.parse_args(argv)
    try:
        tests, global_errors = load(opts.report)
        baseline = load(opts.baseline)[0] if opts.baseline else None
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"cannot read report: {exc}", file=sys.stderr)
        return 2
    s = summarize(tests, global_errors, opts.slowest, baseline)
    print(json.dumps(s, indent=2) if opts.json else format_text(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
