#!/usr/bin/env python3
"""Summarise Robot Framework results: output.xml (RF 4-7) or output.json (RF 7.2+).

Usage:
    python rf_results.py <output.xml|output.json> [--rerun rerun.xml] [--baseline old-output.xml]
                         [--slowest 10] [--json]

Prints totals, each failed test with cause category, the failing keyword chain and message,
failures by cause and tag, execution errors/warnings, slowest tests and keywords, and optionally
flaky tests (failed, then passed in a --rerunfailed run) and new failures against a baseline.
Read-only; standard library only.

Exit codes: 0 report read (whatever the results), 2 unreadable input.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime

CATEGORIES = [
    ("setup", re.compile(r"Parent suite setup failed|Setup failed|Suite setup failed", re.I)),
    ("teardown", re.compile(r"Teardown failed|Also teardown failed", re.I)),
    ("timeout", re.compile(r"timeout .* exceeded|Timeout \d+ms exceeded|timed out", re.I)),
    ("keyword-not-found", re.compile(r"No keyword with name|Keyword '.*' expected \d+|got \d+ arguments", re.I)),
    ("variable", re.compile(r"Variable '[$@&%]\{.*\}' not found|Resolving variable", re.I)),
    ("import", re.compile(r"Importing (library|test library|resource|variable)|Library '.*' (has no|failed)|No module named", re.I)),
    ("ui-element", re.compile(r"Element .* (not|was not|did not)|TimeoutError|waiting for (locator|selector|element)|locator|"
                              r"StaleElementReference|ElementNotInteractable|ElementClickIntercepted|strict mode violation|"
                              r"NoSuchElement|not visible|not found after", re.I)),
    ("connection", re.compile(r"ConnectionError|Max retries exceeded|Connection refused|Name or service not known|"
                              r"getaddrinfo failed|HTTPError|status code \d{3}|SSL", re.I)),
    ("assertion", re.compile(r"!=|should|Expected|does not contain|is not|AssertionError|did not answer", re.I)),
]
CONTROL_TAGS = {"for", "iter", "if", "branch", "try", "while", "group", "kw", "return", "break", "continue", "variable", "error"}


def categorize(message):
    for name, rx in CATEGORIES:
        if rx.search(message or ""):
            return name
    return "other"


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:220]
    return ""


def _rf6_time(value):
    try:
        return datetime.strptime(value, "%Y%m%d %H:%M:%S.%f")
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- XML

def _xml_elapsed(status):
    if status is None:
        return 0.0
    if status.get("elapsed") is not None:
        return float(status.get("elapsed"))
    start, end = _rf6_time(status.get("starttime")), _rf6_time(status.get("endtime"))
    return (end - start).total_seconds() if start and end else 0.0


def _own_status(elem):
    statuses = [c for c in elem if c.tag == "status"]
    return statuses[-1] if statuses else None


def _xml_fail_chain(elem):
    chain = []
    node = elem
    while True:
        failing = [c for c in node if c.tag in CONTROL_TAGS and (_own_status(c) is not None) and _own_status(c).get("status") == "FAIL"]
        if not failing:
            return chain
        node = failing[-1]                      # earlier failures inside TRY are usually handled
        if node.tag == "kw":
            name = node.get("name", "")
            owner = node.get("owner") or node.get("library")
            kind = node.get("type")
            label = f"{owner}.{name}" if owner else name
            chain.append(f"{kind.lower()}: {label}" if kind in ("SETUP", "TEARDOWN") else label)
        elif node.tag in ("for", "while", "try", "if", "group"):
            chain.append(node.tag.upper() + (f" {node.get('name')}" if node.get("name") else ""))


def _xml_keywords(elem, totals):
    for c in elem:
        if c.tag == "kw":
            owner = c.get("owner") or c.get("library")
            name = f"{owner}.{c.get('name')}" if owner else c.get("name", "")
            totals[name][0] += _xml_elapsed(_own_status(c))
            totals[name][1] += 1
        if c.tag in CONTROL_TAGS:
            _xml_keywords(c, totals)


def read_xml(root):
    tests, kw_totals = [], defaultdict(lambda: [0.0, 0])

    def walk(suite, path):
        name = suite.get("name", "")
        here = path + [name]
        for child in suite:
            if child.tag == "suite":
                walk(child, here)
            elif child.tag == "test":
                status = _own_status(child)
                tests.append({
                    "id": ".".join(here + [child.get("name", "")]),
                    "name": child.get("name", ""), "suite": ".".join(here), "line": child.get("line"),
                    "status": status.get("status") if status is not None else "NOT RUN",
                    "message": (status.text or "") if status is not None else "",
                    "elapsed": _xml_elapsed(status),
                    "tags": [t.text for t in child if t.tag == "tag"],
                    "chain": _xml_fail_chain(child),
                })
                _xml_keywords(child, kw_totals)
    top = root.find("suite")
    if top is not None:
        walk(top, [])
    section = root.find("errors")
    errors = [{"level": m.get("level"), "message": first_line(m.text)}
              for m in (list(section) if section is not None else []) if m.tag == "msg"]
    gen = root.get("generator", "")
    return tests, errors, kw_totals, gen


# ---------------------------------------------------------------- JSON

def _json_children(node):
    kids = []
    for key in ("setup",):
        if isinstance(node.get(key), dict):
            kids.append(("SETUP", node[key]))
    for item in node.get("body") or []:
        if isinstance(item, dict) and item.get("type") != "MESSAGE":
            kids.append((item.get("type"), item))
    if isinstance(node.get("teardown"), dict):
        kids.append(("TEARDOWN", node["teardown"]))
    return kids


def _json_fail_chain(test):
    chain, node = [], test
    while True:
        failing = [(k, c) for k, c in _json_children(node) if c.get("status") == "FAIL"]
        if not failing:
            return chain
        kind, node = failing[-1]
        if kind in (None, "KEYWORD", "SETUP", "TEARDOWN") and node.get("name"):
            label = f"{node['owner']}.{node['name']}" if node.get("owner") else node["name"]
            chain.append(f"{kind.lower()}: {label}" if kind in ("SETUP", "TEARDOWN") else label)
        elif kind and kind not in ("ITERATION", "BRANCH"):
            chain.append(kind.split("/")[0] + (f" {node['name']}" if node.get("name") and kind == "GROUP" else ""))


def _json_keywords(node, totals):
    for kind, c in _json_children(node):
        if kind in (None, "KEYWORD", "SETUP", "TEARDOWN") and c.get("name"):
            name = f"{c['owner']}.{c['name']}" if c.get("owner") else c["name"]
            totals[name][0] += float(c.get("elapsed_time") or 0)
            totals[name][1] += 1
        _json_keywords(c, totals)


def read_json(data):
    tests, kw_totals = [], defaultdict(lambda: [0.0, 0])

    def walk(suite, path):
        here = path + [suite.get("name", "")]
        for t in suite.get("tests") or []:
            tests.append({"id": ".".join(here + [t.get("name", "")]), "name": t.get("name", ""), "suite": ".".join(here),
                          "line": t.get("lineno"), "status": t.get("status", "NOT RUN"), "message": t.get("message", ""),
                          "elapsed": float(t.get("elapsed_time") or 0), "tags": t.get("tags") or [],
                          "chain": _json_fail_chain(t)})
            _json_keywords(t, kw_totals)
        for s in suite.get("suites") or []:
            walk(s, here)
    walk(data.get("suite") or {}, [])
    errors = [{"level": e.get("level"), "message": first_line(e.get("message"))} for e in data.get("errors") or []]
    return tests, errors, kw_totals, data.get("generator", "")


def load(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig", errors="replace").lstrip()
    if text.startswith("<"):
        root = ET.fromstring(text)
        if root.tag != "robot":
            raise ValueError("not a Robot Framework output.xml (root element is not <robot>)")
        return read_xml(root)
    data = json.loads(text)
    if "suite" not in data:
        raise ValueError("not a Robot Framework output.json (no 'suite')")
    return read_json(data)


# ---------------------------------------------------------------- summary

def summarize(tests, errors, kw_totals, generator, slowest=10, rerun=None, baseline=None):
    counts = Counter(t["status"] for t in tests)
    failed = [t for t in tests if t["status"] == "FAIL"]
    for t in failed:
        t["category"] = categorize(t["message"])
    tag_stats = defaultdict(lambda: Counter())
    for t in tests:
        for tag in t["tags"]:
            tag_stats[tag][t["status"]] += 1
    s = {
        "generator": generator, "total": len(tests), "passed": counts.get("PASS", 0), "failed": len(failed),
        "skipped": counts.get("SKIP", 0), "not_run": counts.get("NOT RUN", 0),
        "elapsed_s": round(sum(t["elapsed"] for t in tests), 2),
        "failures": [{"test": t["id"], "line": t["line"], "category": t["category"], "message": first_line(t["message"]),
                      "failing_keywords": t["chain"], "tags": t["tags"]} for t in failed],
        "skipped_tests": [{"test": t["id"], "reason": first_line(t["message"])} for t in tests if t["status"] == "SKIP"],
        "by_category": dict(Counter(t["category"] for t in failed).most_common()),
        "by_tag": {tag: dict(c) for tag, c in sorted(tag_stats.items()) if c.get("FAIL")},
        "execution_errors": errors,
        "slowest_tests": [{"test": t["id"], "seconds": round(t["elapsed"], 2)}
                          for t in sorted(tests, key=lambda t: -t["elapsed"])[:slowest]],
        "slowest_keywords": [{"keyword": k, "seconds": round(v[0], 2), "calls": v[1]}
                             for k, v in sorted(kw_totals.items(), key=lambda kv: -kv[1][0])[:slowest]],
    }
    if rerun is not None:
        again = {t["id"]: t["status"] for t in rerun}
        s["flaky"] = [t["id"] for t in failed if again.get(t["id"]) == "PASS"]
        s["failed_again"] = [t["id"] for t in failed if again.get(t["id"]) == "FAIL"]
        s["not_rerun"] = [t["id"] for t in failed if t["id"] not in again]
    if baseline is not None:
        before = {t["id"]: t["status"] for t in baseline}
        s["new_failures"] = [t["id"] for t in failed if before.get(t["id"]) == "PASS"]
        s["fixed"] = [t["id"] for t in tests if t["status"] == "PASS" and before.get(t["id"]) == "FAIL"]
        s["still_failing"] = [t["id"] for t in failed if before.get(t["id"]) == "FAIL"]
    return s


def format_text(s):
    out = [f"{s['generator'] or 'Robot Framework'}",
           f"Tests: {s['total']}  passed {s['passed']}  failed {s['failed']}  skipped {s['skipped']}"
           + (f"  not run {s['not_run']}" if s["not_run"] else "") + f"  ({s['elapsed_s']}s)"]
    if s["execution_errors"]:
        out.append("\nExecution errors and warnings (imports, syntax, deprecations):")
        out.extend(f"  {e['level']:<5} {e['message']}" for e in s["execution_errors"])
    if s["failures"]:
        out.append("\nFailed:")
        for f in s["failures"]:
            out.append(f"  [{f['category']}] {f['test']}" + (f"  (line {f['line']})" if f["line"] else ""))
            if f["failing_keywords"]:
                out.append(f"      at: {' > '.join(f['failing_keywords'])}")
            out.append(f"      {f['message']}")
        out.append("\nFailures by cause: " + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()))
        if s["by_tag"]:
            out.append("Failures by tag:   " + ", ".join(f"{t} {c.get('FAIL', 0)}/{sum(c.values())}" for t, c in s["by_tag"].items()))
    if s["skipped_tests"]:
        out.append("\nSkipped:")
        out.extend(f"  {t['test']}: {t['reason']}" for t in s["skipped_tests"])
    if "flaky" in s:
        out.append("\nRerun of failed tests:")
        out.append("  flaky (passed on rerun): " + (", ".join(s["flaky"]) or "none"))
        out.append("  failed again:            " + (", ".join(s["failed_again"]) or "none"))
        if s["not_rerun"]:
            out.append("  not in the rerun:        " + ", ".join(s["not_rerun"]))
    if "new_failures" in s:
        out.append("\nCompared with the baseline:")
        out.append("  new failures:  " + (", ".join(s["new_failures"]) or "none"))
        out.append("  fixed:         " + (", ".join(s["fixed"]) or "none"))
        out.append("  still failing: " + (", ".join(s["still_failing"]) or "none"))
    if s["slowest_tests"]:
        out.append("\nSlowest tests:")
        out.extend(f"  {t['seconds']:>8.2f}s  {t['test']}" for t in s["slowest_tests"] if t["seconds"] > 0)
    if s["slowest_keywords"]:
        out.append("Slowest keywords (total time, including nested calls):")
        out.extend(f"  {k['seconds']:>8.2f}s  {k['keyword']}  x{k['calls']}" for k in s["slowest_keywords"] if k["seconds"] > 0)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("output", help="output.xml or output.json")
    ap.add_argument("--rerun", help="output of a --rerunfailed run, to find flaky tests")
    ap.add_argument("--baseline", help="an earlier output to compare with")
    ap.add_argument("--slowest", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args(argv)
    try:
        tests, errors, kws, gen = load(opts.output)
        rerun = load(opts.rerun)[0] if opts.rerun else None
        baseline = load(opts.baseline)[0] if opts.baseline else None
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"cannot read output: {exc}", file=sys.stderr)
        return 2
    s = summarize(tests, errors, kws, gen, opts.slowest, rerun, baseline)
    print(json.dumps(s, indent=2) if opts.json else format_text(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
