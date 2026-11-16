#!/usr/bin/env python3
"""Unit-test any Python file and suggest fixes. Standard library only (Python 3.8+).

Commands:
  plan FILE       list functions/classes/methods, linked tests, static findings
  scaffold FILE   write a unittest skeleton for untested functions (never overwrites)
  run FILE        run the linked tests (pytest if installed, else unittest), then diagnose failures
  diagnose        re-print the diagnosis from the last run
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

REPORT_DIR = "pyunit-report"
ASSERT_CALLS = ("assert", "raises", "warns", "approx", "fail")


# ---------------------------------------------------------------- source parsing
def read_tree(path):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    return src, ast.parse(src, filename=path)


def _name_of(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def units_of(tree, include_private=False):
    """Top-level functions and class methods (not nested functions)."""
    out = []

    def add(fn, cls):
        name = fn.name
        if (name.startswith("_") and not include_private) or (name.startswith("__") and name != "__init__" and not include_private):
            if name != "__init__":
                return
        args = [a.arg for a in fn.args.args + fn.args.kwonlyargs if a.arg not in ("self", "cls")]
        raises = sorted({_name_of(n.exc.func if isinstance(n.exc, ast.Call) else n.exc)
                         for n in ast.walk(fn) if isinstance(n, ast.Raise) and n.exc is not None} - {""})
        branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.IfExp, ast.BoolOp)) for n in ast.walk(fn))
        out.append({"name": name, "qualname": f"{cls}.{name}" if cls else name, "cls": cls, "line": fn.lineno,
                    "end": getattr(fn, "end_lineno", fn.lineno), "args": args, "raises": raises,
                    "branches": branches, "node": fn})

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, None)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(sub, node.name)
    return out


def static_findings(units):
    """Common bugs visible without running anything, each with a fix."""
    found = []
    for u in units:
        fn = u["node"]
        for d in fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                found.append((u, d.lineno, "PY001", "mutable default argument is shared between calls",
                              "use `=None` and create the list/dict inside the function"))
        for n in ast.walk(fn):
            if isinstance(n, ast.ExceptHandler):
                if n.type is None:
                    found.append((u, n.lineno, "PY002", "bare `except:` also catches KeyboardInterrupt/SystemExit",
                                  "catch the specific exception, e.g. `except ValueError:`"))
                if len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                    found.append((u, n.lineno, "PY004", "exception is swallowed silently",
                                  "handle it, log it, or let it propagate"))
            if isinstance(n, ast.Compare):
                for op, c in zip(n.ops, n.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(c, ast.Constant) and c.value is None:
                        found.append((u, n.lineno, "PY003", "comparison to None with ==/!=", "use `is None` / `is not None`"))
                    if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(c, ast.Constant) and isinstance(c.value, (int, str, bytes)) \
                            and not isinstance(c.value, bool):
                        found.append((u, n.lineno, "PY006", "`is` compared with a literal", "use `==` / `!=`"))
        rets = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]
        if rets and not isinstance(fn.body[-1], (ast.Return, ast.Raise, ast.While)) and not (
                isinstance(fn.body[-1], ast.If) and fn.body[-1].orelse):
            found.append((u, u["end"], "PY005", "some paths return a value, the end of the function returns None",
                          "add an explicit final `return` (or raise) so every path is intentional"))
    return found


# ---------------------------------------------------------------- tests discovery
def module_info(path):
    """(root_dir, dotted_module) where root_dir is the first folder above the package."""
    path = os.path.abspath(path)
    d, parts = os.path.dirname(path), [os.path.splitext(os.path.basename(path))[0]]
    while os.path.exists(os.path.join(d, "__init__.py")):
        parts.insert(0, os.path.basename(d))
        d = os.path.dirname(d)
    return d, ".".join(parts)


def find_test_files(path, explicit=None):
    if explicit:
        return [os.path.abspath(p) for p in explicit]
    path = os.path.abspath(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    root, _ = module_info(path)
    dirs = {os.path.dirname(path), root}
    for base in list(dirs):
        for sub in ("tests", "test"):
            dirs.add(os.path.join(base, sub))
    found = []
    for d in sorted(dirs):
        for n in (f"test_{stem}.py", f"{stem}_test.py"):
            p = os.path.join(d, n)
            if os.path.isfile(p) and p not in found:
                found.append(p)
    return found


def collect_tests(test_files):
    tests = []
    for tf in test_files:
        _, tree = read_tree(tf)
        for node in tree.body:
            funcs = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                funcs = [(None, node)]
            elif isinstance(node, ast.ClassDef):
                funcs = [(node.name, f) for f in node.body
                         if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name.startswith("test")]
            for cls, f in funcs:
                calls = {_name_of(n.func) for n in ast.walk(f) if isinstance(n, ast.Call)}
                text = ast.dump(f)
                tests.append({"file": tf, "cls": cls, "name": f.name, "line": f.lineno, "calls": calls,
                              "problems": test_problems(f, text)})
    return tests


def test_problems(fn, dump):
    body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    probs = []
    if not body or all(isinstance(s, ast.Pass) for s in body):
        return [("PT02", "empty test")]
    if "TODO" in dump:
        probs.append(("PT03", "TODO test (never finished)"))
    has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(fn)) or any(
        isinstance(n, ast.Call) and any(k in _name_of(n.func).lower() for k in ASSERT_CALLS) for n in ast.walk(fn))
    if not has_assert:
        probs.append(("PT01", "no assertion: the test cannot fail on a wrong result"))
    for n in ast.walk(fn):
        if isinstance(n, ast.Assert) and isinstance(n.test, ast.Constant) and n.test.value is True:
            probs.append(("PT05", "`assert True` proves nothing"))
        if isinstance(n, ast.Call) and _name_of(n.func) == "assertTrue" and n.args and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value is True:
            probs.append(("PT05", "`assertTrue(True)` proves nothing"))
    for d in fn.decorator_list:
        if "skip" in ast.dump(d).lower() or "xfail" in ast.dump(d).lower():
            probs.append(("PT04", "test is skipped/xfail"))
    return probs


def link(units, tests):
    for u in units:
        u["tests"] = [t for t in tests if u["name"] in t["calls"] or (u["name"].strip("_") and u["name"].strip("_") in t["name"])
                      or (u["cls"] and u["name"] == "__init__" and u["cls"] in t["calls"])]


# ---------------------------------------------------------------- commands: plan / scaffold
def cmd_plan(a):
    src, tree = read_tree(a.file)
    units = units_of(tree, a.include_private)
    tests = collect_tests(find_test_files(a.file, a.test_file))
    link(units, tests)
    findings = static_findings(units)
    if a.json:
        print(json.dumps({"units": [{k: v for k, v in u.items() if k not in ("node", "tests")} | {"tests": [t["name"] for t in u["tests"]]}
                                    for u in units],
                          "findings": [[u["qualname"], ln, c, m, f] for u, ln, c, m, f in findings]}, indent=2))
        return 0
    print(f"{a.file}: {len(units)} testable units, {len(tests)} linked tests")
    for u in units:
        mark = "x" if u["tests"] else " "
        extra = f" raises {','.join(u['raises'])}" if u["raises"] else ""
        print(f"  [{mark}] {u['qualname']}({', '.join(u['args'])})  line {u['line']}  branches={u['branches']}{extra}"
              f"  tests={len(u['tests'])}")
    if findings:
        print("\nStatic findings in the source:")
        for u, ln, code, msg, fix in findings:
            print(f"  {code} {u['qualname']} line {ln}: {msg}\n        fix: {fix}")
    bad = [(t, p) for t in tests for p in t["problems"]]
    if bad:
        print("\nTest quality findings:")
        for t, (code, msg) in bad:
            print(f"  {code} {os.path.basename(t['file'])}::{t['name']}: {msg}")
    return 0


def cmd_scaffold(a):
    _, tree = read_tree(a.file)
    units = units_of(tree, a.include_private)
    tests = collect_tests(find_test_files(a.file))
    link(units, tests)
    todo = [u for u in units if not u["tests"]]
    root, mod = module_info(a.file)
    names = sorted({u["cls"] or u["name"] for u in todo})
    out = ['"""Generated skeleton. Replace every TODO with a real test of the INTENDED behaviour."""', "import unittest", "",
           f"from {mod} import {', '.join(names) if names else '*'}", ""]
    for u in todo:
        cname = "Test" + "".join(p.title() for p in u["qualname"].replace(".", "_").split("_"))
        out += [f"class {cname}(unittest.TestCase):"]
        setup = f"        obj = {u['cls']}()  # TODO constructor arguments\n" if u["cls"] else ""
        call = f"obj.{u['name']}" if u["cls"] else u["name"]
        out += [f"    def test_{u['name'].strip('_')}_normal(self):", setup + f"        # TODO: call {call}({', '.join(u['args'])}) with typical input",
                '        self.fail("TODO: assert the expected result")', ""]
        out += [f"    def test_{u['name'].strip('_')}_edge_cases(self):",
                "        # TODO: empty / None / zero / boundary values", '        self.fail("TODO: edge cases")', ""]
        for r in u["raises"]:
            out += [f"    def test_{u['name'].strip('_')}_raises_{r.lower()}(self):",
                    f"        with self.assertRaises({r}):", f"            pass  # TODO: input that makes {u['qualname']} raise {r}", ""]
        out.append("")
    text = "\n".join(out).replace("\n\n\n\n", "\n\n\n")
    if not todo:
        print("every unit already has a linked test; nothing to scaffold")
        return 0
    base = os.path.splitext(os.path.basename(a.file))[0]
    tdir = os.path.join(root, "tests") if os.path.isdir(os.path.join(root, "tests")) else os.path.dirname(os.path.abspath(a.file))
    dest = a.output or os.path.join(tdir, f"test_{base}.py")
    if os.path.exists(dest):
        print(f"{dest} exists and will not be overwritten. Add this skeleton by hand:\n\n{text}")
        return 0
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {dest} with {len(todo)} unit(s) to test; the TODO tests fail until you finish them")
    return 0


# ---------------------------------------------------------------- running
def _worker(out_json, files):
    """unittest fallback: run test files and write JSON results (used when pytest is missing)."""
    import unittest
    results = []

    class R(unittest.TextTestResult):
        def _add(self, test, status, err=None):
            tb = self._exc_info_to_string(err, test) if err else ""
            msg = str(err[1]) if err else ""
            results.append({"id": test.id(), "status": status, "message": msg, "traceback": tb})

        def addSuccess(self, t): super().addSuccess(t); self._add(t, "passed")
        def addFailure(self, t, e): super().addFailure(t, e); self._add(t, "failed", e)
        def addError(self, t, e): super().addError(t, e); self._add(t, "error", e)
        def addSkip(self, t, r): super().addSkip(t, r); self._add(t, "skipped")

    suite = unittest.TestSuite()
    for f in files:
        suite.addTests(unittest.defaultTestLoader.discover(os.path.dirname(f), pattern=os.path.basename(f)))
    unittest.TextTestRunner(resultclass=R, verbosity=0, stream=open(os.devnull, "w")).run(suite)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh)


def have_module(name):
    return subprocess.run([sys.executable, "-c", f"import {name}"], capture_output=True).returncode == 0


def run_tests(files, root, k, timeout, with_cov, source):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([root, os.environ.get("PYTHONPATH", "")]).strip(os.pathsep))
    tmp = tempfile.mkdtemp(prefix="pyunit-")
    use_pytest = have_module("pytest")
    cov = with_cov and have_module("coverage")
    covrun = [sys.executable, "-m", "coverage", "run", f"--include={source}"]
    if use_pytest:
        xml = os.path.join(tmp, "junit.xml")
        cmd = (covrun if cov else [sys.executable]) + ["-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"] + (["-k", k] if k else []) + files
    else:
        js = os.path.join(tmp, "results.json")
        cmd = (covrun if cov else [sys.executable]) + [os.path.abspath(__file__), "_worker", js] + files
    try:
        p = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"engine": "pytest" if use_pytest else "unittest", "results": [], "error": f"timed out after {timeout}s (infinite loop?)",
                "output": "", "coverage": None}
    results, error = [], None
    if use_pytest and os.path.exists(xml):
        for tc in ET.parse(xml).getroot().iter("testcase"):
            st, msg, tb = "passed", "", ""
            for tag, name in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
                el = tc.find(tag)
                if el is not None:
                    st, msg, tb = name, el.get("message") or "", el.text or ""
            results.append({"id": f"{tc.get('classname')}::{tc.get('name')}", "status": st, "message": msg, "traceback": tb})
    elif not use_pytest and os.path.exists(js):
        with open(js, encoding="utf-8") as fh:
            results = json.load(fh)
    else:
        error = (p.stdout + p.stderr)[-2000:] or "the test run produced no results"
    coverage = None
    if cov:
        cj = os.path.join(tmp, "cov.json")
        subprocess.run([sys.executable, "-m", "coverage", "json", "-o", cj, f"--include={source}"], cwd=root, capture_output=True)
        if os.path.exists(cj):
            with open(cj, encoding="utf-8") as fh:
                files_cov = json.load(fh).get("files", {})
            for v in files_cov.values():
                coverage = {"percent": v["summary"]["percent_covered"], "missing": v["missing_lines"]}
    return {"engine": "pytest" if use_pytest else "unittest", "results": results, "error": error,
            "output": (p.stdout + p.stderr)[-4000:], "coverage": coverage}


# ---------------------------------------------------------------- diagnosis
RULES = [
    (r"TODO", "test", "Unfinished skeleton test. Replace the TODO with a real call and an assertion on the intended result."),
    (r"not raised", "code",
     "The test expects an exception that the code did not raise. If the input really is invalid, add the validation (`raise ValueError(...)`) "
     "to the function; otherwise correct the test input."),
    (r"ModuleNotFoundError|ImportError", "setup",
     "The module cannot be imported. Check the name, the package layout (`__init__.py`), that the dependency is installed, or a circular import."),
    (r"takes \d+ positional arguments? but \d+ (were|was) given|missing \d+ required|unexpected keyword", "test-or-code",
     "The call does not match the function signature. If the signature changed on purpose, update the test; otherwise restore the parameters."),
    (r"'NoneType' object|NoneType", "code",
     "A value is None where an object is expected. Return a real value on every path, or guard the input (`if x is None: ...`)."),
    (r"ZeroDivisionError", "code", "Division by zero. Check the divisor first and raise a clear `ValueError`, or return a defined result."),
    (r"KeyError", "code", "Missing dict key. Use `.get(key, default)` or validate the input before indexing."),
    (r"IndexError", "code", "Index out of range. Check `len()` first or handle the empty sequence."),
    (r"AttributeError", "code", "The object has no such attribute. Check the type returned by the previous call and the attribute spelling."),
    (r"NameError", "code", "A name is used before it is defined or is misspelled. Define or import it."),
    (r"unsupported operand|can only concatenate|not supported between", "code",
     "Mixed types in an operation. Convert explicitly (`int()`, `str()`) or validate the input types."),
    (r"ValueError", "code", "Invalid value reached a conversion. Validate the input and raise a descriptive error, or handle it."),
    (r"FileNotFoundError|PermissionError", "test",
     "The unit touches the real file system. Use a temporary directory (`tempfile`, pytest `tmp_path`) or mock `open`."),
    (r"ConnectionError|URLError|timeout|socket", "test",
     "The unit reaches the network. Replace the call with a fake or `unittest.mock.patch`."),
    (r"RecursionError", "code", "Unbounded recursion. Add or fix the base case."),
    (r"AssertionError|!=|assert ", "unknown",
     "Actual and expected values differ. Decide which one is right by reading the function's intended behaviour: fix the code if the result is wrong, "
     "fix the test only if the expectation was wrong."),
]


def frames(tb):
    return [(f, int(n), fn) for f, n, fn in re.findall(r'File "([^"]+)", line (\d+), in (\S+)', tb)] or \
           [(f, int(n), "") for f, n in re.findall(r"([\w./\\:-]+\.py):(\d+):", tb)]


def snippet(path, line, radius=2):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    lo, hi = max(0, line - 1 - radius), min(len(lines), line + radius)
    return "\n".join(f"{'>' if i + 1 == line else ' '} {i + 1:4} {lines[i]}" for i in range(lo, hi))


def diagnose(result, source_path):
    text = result["message"] + "\n" + result["traceback"]
    fr = frames(result["traceback"])
    src_abs = os.path.abspath(source_path)
    src_frames = [(f, n, fn) for f, n, fn in fr if os.path.abspath(f) == src_abs]
    where = "code" if src_frames else "test"
    for pat, blame, advice in RULES:
        if re.search(pat, text):
            break
    else:
        blame, advice = "unknown", "Read the traceback; reproduce with the smallest input."
    d = {"test": result["id"], "status": result["status"], "message": (result["message"] or "").strip().splitlines()[0:1],
         "likely_cause": blame if blame != "unknown" else ("test or code (decide)"), "advice": advice}
    if src_frames:
        f, n, fn = src_frames[-1]
        d["location"] = f"{os.path.basename(f)}:{n}" + (f" in {fn}" if fn else "")
        d["code"] = snippet(f, n)
    elif fr:
        f, n, _ = fr[-1]
        d["location"] = f"{os.path.basename(f)}:{n} (in the test)"
        d["code"] = snippet(f, n)
    d["error_origin"] = where
    return d


def print_diagnosis(rep):
    bad = [d for d in rep["diagnoses"]]
    if not bad:
        return
    print("\nFailures and suggested fixes:")
    for d in bad:
        print(f"\n  {d['status'].upper()} {d['test']}")
        if d["message"]:
            print(f"    message: {d['message'][0][:200]}")
        print(f"    likely cause: {d['likely_cause']}" + (f"  at {d['location']}" if d.get("location") else ""))
        if d.get("code"):
            print("    " + d["code"].replace("\n", "\n    "))
        print(f"    suggested fix: {d['advice']}")


def cmd_run(a):
    src_abs = os.path.abspath(a.file)
    _, tree = read_tree(src_abs)
    units = units_of(tree, a.include_private)
    test_files = find_test_files(src_abs, a.test_file)
    if not test_files:
        print(f"no tests found for {a.file}. Run: python {os.path.basename(__file__)} scaffold {a.file}")
        return 2
    tests = collect_tests(test_files)
    link(units, tests)
    root, _ = module_info(src_abs)
    run = run_tests(test_files, root, a.k, a.timeout, a.coverage, src_abs)
    res = run["results"]
    if run["error"] or not res:
        print("The test run did not produce results:\n" + (run["error"] or run["output"] or "no tests were collected"))
        return 2
    counts = {s: sum(r["status"] == s for r in res) for s in ("passed", "failed", "error", "skipped")}
    diags = [diagnose(r, src_abs) for r in res if r["status"] in ("failed", "error")]
    findings = static_findings(units)
    quality = [{"test": t["name"], "code": c, "message": m} for t in tests for c, m in t["problems"]]
    untested = [u["qualname"] for u in units if not u["tests"]]
    rep = {"file": a.file, "engine": run["engine"], "counts": counts, "untested": untested, "coverage": run["coverage"],
           "diagnoses": diags, "static_findings": [{"unit": u["qualname"], "line": ln, "code": c, "message": m, "fix": f}
                                                   for u, ln, c, m, f in findings], "test_quality": quality}
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(f"engine={run['engine']}  passed={counts['passed']} failed={counts['failed']} errors={counts['error']} skipped={counts['skipped']}")
    if run["coverage"]:
        print(f"coverage of {os.path.basename(a.file)}: {run['coverage']['percent']:.0f}%  missing lines: {run['coverage']['missing']}")
    if untested:
        print("untested: " + ", ".join(untested))
    for q in quality:
        print(f"  {q['code']} {q['test']}: {q['message']}")
    for f in rep["static_findings"]:
        print(f"  {f['code']} {f['unit']} line {f['line']}: {f['message']} -> {f['fix']}")
    print_diagnosis(rep)
    print(f"\nreport: {os.path.join(REPORT_DIR, 'report.json')}")
    return 1 if (counts["failed"] or counts["error"]) else 0


def cmd_diagnose(a):
    p = os.path.join(REPORT_DIR, "report.json")
    if not os.path.exists(p):
        print("no previous run; use the run command first")
        return 2
    with open(p, encoding="utf-8") as fh:
        rep = json.load(fh)
    print_diagnosis(rep)
    if not rep["diagnoses"]:
        print("no failures in the last run")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        _worker(argv[1], argv[2:])
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("plan", cmd_plan), ("scaffold", cmd_scaffold), ("run", cmd_run)):
        s = sub.add_parser(name)
        s.add_argument("file")
        s.add_argument("--include-private", action="store_true")
        s.add_argument("--test-file", action="append", help="use this test file instead of auto-discovery (repeatable)")
        if name == "plan":
            s.add_argument("--json", action="store_true")
        if name == "scaffold":
            s.add_argument("--output")
        if name == "run":
            s.add_argument("-k", help="only tests matching this expression (pytest only)")
            s.add_argument("--coverage", action="store_true", help="measure line coverage (needs the coverage package)")
            s.add_argument("--timeout", type=int, default=300)
        s.set_defaults(fn=fn)
    s = sub.add_parser("diagnose")
    s.set_defaults(fn=cmd_diagnose)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
