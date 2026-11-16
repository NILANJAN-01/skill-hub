#!/usr/bin/env python3
"""Read test results and coverage (Python 3.8+, standard library only).

- JUnit XML: Gradle (build/test-results/<task>/TEST-*.xml), Maven Surefire/Failsafe (target/*-reports/TEST-*.xml),
  the JUnit Platform console launcher, Kotest and Android unit-test tasks all write this format.
- Coverage XML in the JaCoCo format: Gradle `jacocoTestReport`, Maven `jacoco:report`, and Kover `koverXmlReport`.
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SKIP_DIRS = {".git", ".gradle", ".idea", "node_modules", ".kotlin", "ktest-report", "__pycache__"}
PARAM_SUFFIX = re.compile(r"^(?P<base>.*?)(?:\((?P<args>[^()]*)\))?(?P<inv>\[\d+\])?$")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def find_junit_files(root, since=None):
    out = []
    for p in walk(root):
        if p.suffix.lower() != ".xml":
            continue
        s = p.as_posix()
        if not (p.name.startswith("TEST-") or "/test-results/" in s or "/junit-xml/" in s):
            continue
        if since is not None and p.stat().st_mtime < since:
            continue
        out.append(p)
    return sorted(out)


def find_coverage_files(root, since=None):
    out = []
    for p in walk(root):
        if p.suffix.lower() != ".xml":
            continue
        s = p.as_posix().lower()
        if not ("jacoco" in s or "/kover/" in s or "coverage" in p.name.lower()):
            continue
        if since is not None and p.stat().st_mtime < since:
            continue
        try:
            with open(p, "rb") as fh:
                head = fh.read(600)
        except OSError:
            continue
        if b"<report" in head or b"jacoco" in head.lower():
            out.append(p)
    return sorted(out)


def test_key(name):
    """Normalise a reported test name to the source function name: 'add(int, int)[2]' -> 'add', 'adds()' -> 'adds'."""
    name = name.strip()
    m = PARAM_SUFFIX.match(name)
    base = m.group("base") if m else name
    if re.match(r"^\[\d+\]", base):                   # JUnit display name of a parameterized invocation
        return None
    return base.strip()


def parse_junit(files):
    cases, warnings = [], []
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except (ET.ParseError, OSError) as e:
            warnings.append(f"{f}: not readable JUnit XML ({e})")
            continue
        suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
        for s in suites:
            sname = s.get("name", "")
            for tc in s.findall("testcase"):
                status, msg, typ, details = "passed", "", "", ""
                for tag in ("failure", "error", "skipped"):
                    el = tc.find(tag)
                    if el is not None:
                        status = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                        msg = el.get("message", "") or ""
                        typ = el.get("type", "") or ""
                        details = (el.text or "").strip()
                        break
                classname = tc.get("classname") or sname
                out = tc.find("system-out")
                err = tc.find("system-err")
                try:
                    t = float(tc.get("time") or 0)
                except ValueError:
                    t = 0.0
                cases.append({"classname": classname, "name": tc.get("name", ""), "time": t, "status": status,
                              "message": msg[:4000], "type": typ, "details": details[:20000],
                              "stdout": ((out.text or "") if out is not None else "")[:4000],
                              "stderr": ((err.text or "") if err is not None else "")[:4000],
                              "file": str(f)})
    return cases, warnings


def _counters(el):
    out = {}
    for c in el.findall("counter"):
        try:
            out[c.get("type")] = (int(c.get("missed", 0)), int(c.get("covered", 0)))
        except ValueError:
            pass
    return out


def parse_coverage(files):
    """{'classes': {'com.acme.Foo': {'source': 'Foo.kt', 'counters': {...}, 'methods': [...]}}, 'total': {...}}"""
    classes, total, warnings = {}, {}, []
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except (ET.ParseError, OSError) as e:
            warnings.append(f"{f}: not readable coverage XML ({e})")
            continue
        if root.tag != "report":
            continue
        for k, (mi, co) in _counters(root).items():
            a, b = total.get(k, (0, 0))
            total[k] = (a + mi, b + co)
        for pkg in root.iter("package"):
            for cl in pkg.findall("class"):
                name = (cl.get("name") or "").replace("/", ".")
                methods = []
                for me in cl.findall("method"):
                    mname = me.get("name", "")
                    try:
                        line = int(me.get("line") or 0)
                    except ValueError:
                        line = 0
                    methods.append({"name": mname, "desc": me.get("desc", ""), "line": line,
                                    "counters": _counters(me)})
                entry = classes.setdefault(name, {"source": cl.get("sourcefilename", ""), "counters": {},
                                                  "methods": []})
                for k, (mi, co) in _counters(cl).items():
                    a, b = entry["counters"].get(k, (0, 0))
                    entry["counters"][k] = (a + mi, b + co)
                entry["methods"].extend(methods)
    return {"classes": classes, "total": total, "files": [str(f) for f in files]}, warnings


def pct(pair):
    if not pair:
        return None
    missed, covered = pair
    return round(100.0 * covered / (missed + covered), 1) if missed + covered else None


SYNTHETIC = re.compile(r"^(<init>|<clinit>|access\$|lambda\$|.*\$default$|.*\$lambda)")


def class_candidates(fqcn):
    """JVM class names for a Kotlin class name: com.a.Outer.Inner -> com.a.Outer$Inner (also for Companion)."""
    parts = fqcn.split(".")
    cands = [fqcn]
    for i in range(len(parts) - 1, 0, -1):
        if parts[i][:1].isupper() and parts[i - 1][:1].isupper():
            cands.append(".".join(parts[:i]) + "$" + "$".join(parts[i:]))
    return cands


def coverage_for(cov, fqcn, method_name, line_from, line_to):
    """Coverage counters of one source method (matched by JVM class, name and line range)."""
    if not cov:
        return None
    for c in class_candidates(fqcn):
        entry = cov["classes"].get(c)
        if not entry:
            continue
        best = None
        for me in entry["methods"]:
            n = me["name"].split("$")[0] if not SYNTHETIC.match(me["name"]) else None
            if n != method_name:
                continue
            if me["line"] and line_from <= me["line"] <= line_to:
                return me["counters"]
            best = best or me
        if best:
            return best["counters"]
    return None
