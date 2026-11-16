#!/usr/bin/env python3
"""Plan, run and verify unit tests for Kotlin code, class by class and method by method, and write an HTML report.

Commands (run with --help for options):
  plan      list classes and methods and which tests cover them
  scaffold  write test skeletons for untested methods of a class
  run       run the tests (all, one class or one method) and write the report
  verify    check test quality and existing results without running anything
  report    rebuild the report from existing results
  mutate    put small bugs into a class, one at a time, and check that its tests fail

Build tools: Gradle (wrapper or installed, multi-module, Android unit tests), Maven, or plain kotlinc + the JUnit
console launcher for loose .kt files. Python 3.8+, standard library only.
Exit codes: 0 passed, 1 tests failed or verification errors, 2 usage or tool error.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks  # noqa: E402
import html_report  # noqa: E402
import kotlin_source as ks  # noqa: E402
import results as rs  # noqa: E402

VERSION = "1.0"
IS_WIN = os.name == "nt"
CMD_SPECIAL = re.compile(r"[&|^%!<>\"]")


class KtestError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ build tools

def find_up(start, names, stop=None):
    d = Path(start).resolve()
    while True:
        for n in names:
            if (d / n).exists():
                return d
        if d.parent == d or (stop and d == stop):
            return None
        d = d.parent


def gradle_module(build_root, path):
    """(':a:b', module_dir) for the Gradle module that holds path."""
    d = Path(path).resolve().parent
    build_root = build_root.resolve()
    while True:
        if (d / "build.gradle.kts").exists() or (d / "build.gradle").exists() or d == build_root:
            rel = d.relative_to(build_root).parts if d != build_root else ()
            return (":" + ":".join(rel)) if rel else "", d
        if d.parent == d:
            return "", build_root
        d = d.parent


def read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def build_text(d):
    return read(d / "build.gradle.kts") + read(d / "build.gradle")


def detect_tool(project, opts):
    want = opts.tool
    if want in ("auto", "gradle"):
        wrapper = find_up(project, ["gradlew.bat" if IS_WIN else "gradlew", "gradlew"])
        if wrapper:
            exe = wrapper / ("gradlew.bat" if IS_WIN and (wrapper / "gradlew.bat").exists() else "gradlew")
            return {"tool": "gradle", "exe": str(exe), "root": wrapper}
        settings = find_up(project, ["settings.gradle.kts", "settings.gradle", "build.gradle.kts", "build.gradle"])
        if settings and shutil.which("gradle"):
            return {"tool": "gradle", "exe": shutil.which("gradle"), "root": settings}
        if want == "gradle":
            raise KtestError("no Gradle wrapper (gradlew) or installed gradle found")
    if want in ("auto", "maven"):
        pom = find_up(project, ["pom.xml"])
        if pom:
            for w in (["mvnw.cmd"] if IS_WIN else []) + ["mvnw"]:
                if (pom / w).exists():
                    return {"tool": "maven", "exe": str(pom / w), "root": pom}
            if shutil.which("mvn"):
                return {"tool": "maven", "exe": shutil.which("mvn"), "root": pom}
            raise KtestError("pom.xml found but no mvnw or mvn on PATH")
        if want == "maven":
            raise KtestError("no pom.xml found")
    if want in ("auto", "kotlinc"):
        kc = shutil.which("kotlinc") or shutil.which("kotlinc.bat")
        if kc:
            return {"tool": "kotlinc", "exe": kc, "root": Path(project).resolve()}
        raise KtestError("no build found: no Gradle wrapper/build, no pom.xml, and no kotlinc on PATH. Install a JDK "
                         "and Kotlin (or add a small Gradle build: see references/setup.md)")
    raise KtestError(f"unknown --tool {want}")


# ------------------------------------------------------------------------------------------------ selection

def resolve_selection(model, opts):
    """Return a list of filters {'class': test class fq, 'test': test name or None, 'file': test file}."""
    tcs = model["test_classes"]
    units = model["units"]
    filters = []

    def add(tc_id, test=None):
        tc = tcs[tc_id]
        f = {"class": tc_id, "test": test, "file": tc["file"], "kotest": tc["kotest"]}
        if f not in filters:
            filters.append(f)

    for pat in opts.test or []:
        cls, _, name = pat.partition("#")
        hits = [t for t in tcs if t == cls or t.endswith("." + cls) or t.split(".")[-1] == cls]
        if not hits:
            raise KtestError(f"--test {pat}: no test class '{cls}' found")
        for h in hits:
            add(h, name or None)
    for cname in opts.cls or []:
        us = [u for u in units.values() if cname in (u["id"], u["name"], u["simple"])]
        direct = [t for t in tcs if cname in (t, t.split(".")[-1])]
        if not us and direct:
            for t in direct:
                add(t)
            continue
        if not us:
            raise KtestError(f"--class {cname}: no class with that name in the main sources")
        for u in us:
            methods = [m for m in u["methods"] if not opts.method or m["name"] in opts.method]
            if opts.method and not methods:
                raise KtestError(f"--method {', '.join(opts.method)}: not found in {u['name']} "
                                 f"(methods: {', '.join(sorted({m['name'] for m in u['methods']}))})")
            linked = [x["test"] for m in methods for x in m["tests"]]
            if opts.method:
                if not linked:
                    raise KtestError(f"no tests are linked to {u['name']}.{'/'.join(opts.method)}. Write them first "
                                     f"(scaffold --class {u['simple']}), then run again")
                for tid in linked:
                    cls, _, name = tid.partition("#")
                    add(cls, None if tcs[cls]["kotest"] else name)
            else:
                ids = set(u["test_classes"]) | {tid.split("#")[0] for tid in linked}
                if not ids:
                    raise KtestError(f"no tests found for class {u['name']}. Write them first "
                                     f"(scaffold --class {u['simple']}), then run again")
                for t in sorted(ids):
                    add(t)
    if opts.method and not opts.cls:
        raise KtestError("--method needs --class")
    return filters


def gradle_pattern(f):
    pat = f["class"] + (("." + f["test"]) if f["test"] else "")
    if IS_WIN:
        pat = CMD_SPECIAL.sub("*", pat)                   # cmd.exe would mangle these in gradlew.bat arguments
    return pat


def gradle_command(tool, project_info, filters, opts, clean=True, coverage=True):
    root = tool["root"]
    proj_root = Path(project_info["root"])
    modules = {}
    if filters:
        for f in filters:
            mod, d = gradle_module(root, proj_root / f["file"])
            modules.setdefault((mod, d), []).append(f)
    else:
        for tf in project_info["files"]["test"]:
            mod, d = gradle_module(root, proj_root / tf["rel"])
            modules.setdefault((mod, d), [])
        if not modules:
            mod, d = gradle_module(root, proj_root / "x")
            modules[(mod, d)] = []
    args = []
    root_text = build_text(root)
    for (mod, d), fs in sorted(modules.items(), key=lambda kv: kv[0][0]):
        text = build_text(d)
        android = bool(re.search(r"com\.android\.(application|library)|id\s*\(?\s*[\"']com\.android", text))
        task = f"test{opts.variant[:1].upper()}{opts.variant[1:]}UnitTest" if android else "test"
        if clean:
            args.append(f"{mod}:clean{task[:1].upper()}{task[1:]}")
        args.append(f"{mod}:{task}")
        for f in fs:
            args += ["--tests", gradle_pattern(f)]
        if coverage and opts.coverage:
            if opts.coverage_task:
                args.append(f"{mod}:{opts.coverage_task}")
            elif "kover" in text or ("kover" in root_text and not mod):
                args.append(f"{mod}:koverXmlReport")
            elif "jacoco" in text or ("jacoco" in root_text and re.search(r"subprojects|allprojects", root_text)) \
                    or ("jacoco" in root_text and not mod):
                args.append(f"{mod}:jacocoTestReport")
    return [tool["exe"], *args, "--continue", "--console=plain"] + (opts.build_arg or [])


def maven_command(tool, filters, opts, clean=True):
    args = [tool["exe"], "-B"]
    pom = read(tool["root"] / "pom.xml")
    args.append("test")
    if filters:
        parts = {}
        for f in filters:
            short = f["class"]
            if f["test"] and not re.search(r"[\s,#+]", f["test"]):
                parts.setdefault(short, []).append(f["test"])
            else:
                parts.setdefault(short, [])
        sel = ",".join(c + ("#" + "+".join(ms) if ms else "") for c, ms in parts.items())
        args += [f"-Dtest={sel}", "-Dsurefire.failIfNoSpecifiedTests=false", "-DfailIfNoTests=false"]
    if opts.coverage and "jacoco" in pom:
        args.append("jacoco:report")
    return args + (opts.build_arg or [])


def kotlinc_commands(tool, project_info, filters, opts, out):
    jar = opts.junit_jar or os.environ.get("KTEST_JUNIT_JAR")
    if not jar or not Path(jar).is_file():
        raise KtestError("kotlinc mode needs the JUnit console launcher jar: pass --junit-jar "
                         "junit-platform-console-standalone-<version>.jar (or set KTEST_JUNIT_JAR)")
    java = shutil.which("java") or (str(Path(os.environ["JAVA_HOME"]) / "bin" / "java")
                                    if os.environ.get("JAVA_HOME") else None)
    if not java:
        raise KtestError("java not found: install a JDK and put it on PATH or set JAVA_HOME")
    root = Path(project_info["root"])
    srcs = [str(root / f["rel"]) for k in ("main", "test") for f in project_info["files"][k]
            if f["rel"].endswith(".kt")]
    lib = Path(tool["exe"]).resolve().parent.parent / "lib"
    libs = [str(lib / n) for n in ("kotlin-stdlib.jar", "kotlin-test.jar", "kotlin-test-junit5.jar")
            if (lib / n).exists()]
    extra = opts.classpath.split(os.pathsep) if opts.classpath else []
    classes = out / "build" / "classes"
    xml = out / "junit-xml"
    if xml.exists():
        shutil.rmtree(xml)
    cp = os.pathsep.join([jar, *libs, *extra])
    compile_cmd = [tool["exe"], *srcs, "-cp", cp, "-d", str(classes)]
    run_cmd = [java, "-jar", jar, "--class-path", os.pathsep.join([str(classes), *libs, *extra]),
               "--reports-dir", str(xml), "--disable-banner", "--details=tree"]
    if filters:
        for f in filters:
            run_cmd += (["--select-method", f"{f['class']}#{f['test']}"] if f["test"]
                        else ["--select-class", f["class"]])
    else:
        run_cmd.append("--scan-class-path")
    return [compile_cmd, run_cmd], xml


# ------------------------------------------------------------------------------------------------ execution

def kill_tree(p):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        else:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def execute(cmd, cwd, log, timeout, echo=False):
    """Run cmd, append its output to the log file. Returns (exit_code or None on timeout, seconds)."""
    start = time.time()
    with open(log, "a", encoding="utf-8", errors="replace") as fh:
        fh.write("$ " + subprocess.list2cmdline([str(c) for c in cmd]) + "\n")
        fh.flush()
        kw = {} if IS_WIN else {"start_new_session": True}
        try:
            p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        except OSError as e:
            raise KtestError(f"cannot start {cmd[0]}: {e}")

        def pump():
            for raw in iter(p.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace")
                fh.write(line)
                if echo:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        th = threading.Thread(target=pump, daemon=True)
        th.start()
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(p)
            code = None
            fh.write(f"\n[ktest] stopped after {timeout} s (timeout)\n")
        th.join(5)
    return code, round(time.time() - start, 1)


def build_errors(log_text):
    lines = log_text.splitlines()
    errs = [ln for ln in lines if re.match(r"^e: |^\[ERROR\]|.*error: ", ln)][:15]
    m = re.search(r"\* What went wrong:\n(.*?)(?:\n\* Try:|\Z)", log_text, re.S)
    if m:
        errs.append(m.group(1).strip()[:1500])
    return "\n".join(errs)[:3000]


def run_tests(project, project_info, filters, opts, out, clean=True, coverage=True, log_name="build.log",
              timeout=None):
    tool = detect_tool(project, opts)
    log = out / log_name
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("", encoding="utf-8")
    started = time.time() - 2
    timeout = timeout or opts.timeout
    if tool["tool"] == "gradle":
        cmds, xml_root = [gradle_command(tool, project_info, filters, opts, clean, coverage)], tool["root"]
    elif tool["tool"] == "maven":
        cmds, xml_root = [maven_command(tool, filters, opts, clean)], tool["root"]
    else:
        cmds, xml_root = kotlinc_commands(tool, project_info, filters, opts, out)
    code, dur = None, 0.0
    for c in cmds:
        code, d = execute(c, tool["root"], log, timeout, echo=opts.verbose)
        dur += d
        if code not in (0,) and c is not cmds[-1]:
            break                                          # compile step failed
    files = rs.find_junit_files(xml_root, since=started)
    cases, warns = rs.parse_junit(files)
    cov_files = rs.find_coverage_files(xml_root, since=started) if opts.coverage else []
    log_text = read(log)
    run = {"tool": tool["tool"], "command": " | ".join(subprocess.list2cmdline([str(x) for x in c]) for c in cmds),
           "exit_code": code, "duration_s": round(dur, 1), "log": str(log), "timed_out": code is None,
           "filters": [f["class"] + ("#" + f["test"] if f["test"] else "") for f in filters],
           "log_tail": "\n".join(log_text.splitlines()[-60:]), "warnings": warns}
    if code is None:
        run["build_failed"] = True
        run["build_error"] = f"The test run was stopped after {timeout} s (--timeout)."
    elif code != 0 and not any(c["status"] in ("failed", "error") for c in cases):
        run["build_failed"] = True
        run["build_error"] = build_errors(log_text) or f"{tool['tool']} exited with code {code}; see {log}."
    if opts.coverage and not cov_files and not run.get("build_failed"):
        run.setdefault("warnings", []).append(
            "No coverage XML was produced. Configure JaCoCo or Kover (see references/setup.md) or pass "
            "--coverage-task.")
    return run, cases, files, cov_files


# ------------------------------------------------------------------------------------------------ report

def selection_scope(model, filters, opts):
    """Test classes and production classes that a filtered run is about (None = whole project)."""
    if not filters:
        return None
    tests = {f["class"] for f in filters}
    units = {u["id"] for u in model["units"].values()
             if set(opts.cls or []) & {u["id"], u["name"], u["simple"]}}
    for t in tests:
        units.update(model["test_classes"][t]["primary"])
    return {"tests": tests, "units": units}


def in_scope(f, scope):
    if scope is None:
        return True
    if f.get("test"):
        return f["test"].split("#")[0] in scope["tests"]
    if f.get("test_class"):
        return f["test_class"] in scope["tests"]
    if f.get("unit"):
        return f["unit"] in scope["units"]
    return f["rule"] in ("KT013", "KT015", "KT016", "KT019", "KT029", "KT000")


def analyse(project, opts, run=None, cases=None, files=None, cov_files=None, mutation=None, filters=None):
    info = checks.scan(project, include_private=opts.include_private)
    model = checks.link(info)
    stale = None
    if run is None:                                   # report/verify: use results already on disk
        files = rs.find_junit_files(info["root"]) if opts.results is None else \
            [p for d in opts.results for p in rs.find_junit_files(d)]
        cases, warns = rs.parse_junit(files)
        cov_files = (rs.find_coverage_files(info["root"]) if opts.coverage_xml is None
                     else [Path(p) for p in opts.coverage_xml])
        if files:
            newest_src = max((Path(info["root"], f["rel"]).stat().st_mtime
                              for k in ("main", "test") for f in info["files"][k]), default=0)
            newest_res = max(p.stat().st_mtime for p in files)
            if newest_res < newest_src:
                stale = ("The newest test result is older than the newest source change; run the tests again "
                         "(ktest.py run) for current results.")
        run = {"tool": "existing results", "warnings": warns, "stale": stale}
    cov, cwarn = rs.parse_coverage(cov_files or [])
    run.setdefault("warnings", []).extend(cwarn)
    unmatched = checks.attach_results(model, cases or [])
    run["unmatched"] = unmatched
    fs = checks.static_checks(model, info)
    if cases is not None and (files or run.get("tool") != "existing results"):
        fs += checks.result_checks(model, run, cov if cov["classes"] else None,
                                   {"slow": opts.slow, "min_coverage": opts.min_coverage})
    if mutation:
        for mu in mutation["mutants"]:
            if mu["result"] == "survived":
                fs.append(checks._finding("KT019", "warning", "Bug not caught by the tests (survived mutant)",
                                          f"{mu['method']}: changing '{mu['original']}' to '{mu['mutated']}' on line "
                                          f"{mu['line']} did not make any test fail. Add a test or a stronger "
                                          "assertion for this case.", mu["file"], mu["line"]))
    for e in info["errors"]:
        fs.append(checks._finding("KT000", "warning", "Source file not read", e))
    scope = selection_scope(model, filters, opts)
    fs = checks.sort_findings([f for f in fs if in_scope(f, scope)])
    report = build_report(info, model, run, cases or [], files or [], cov, fs, opts, mutation, scope)
    return report, model, info


def build_report(info, model, run, cases, files, cov, fs, opts, mutation, scope=None):
    classes = []
    for u in sorted(model["units"].values(), key=lambda u: (u["file"], u["line"])):
        if u["private"] and not opts.include_private:
            continue
        if not u["methods"] and not u["test_classes"]:
            continue
        if scope is not None and u["id"] not in scope["units"]:
            continue
        methods = []
        counts = {}
        for m in u["methods"]:
            st = checks.method_status(model, m)
            counts[st] = counts.get(st, 0) + 1
            tests = []
            for x in m["tests"]:
                t = checks.find_test(model, x["test"])
                tests.append({"id": x["test"], "name": (t or {}).get("name", x["test"]), "evidence": x["evidence"],
                              "status": checks.test_status(t) if t else "not run"})
            methods.append({"name": m["name"], "signature": m["signature"], "line": m["line"], "status": st,
                            "skip": m["skip"], "tests": tests, "coverage": m.get("coverage")})
        classes.append({"id": u["id"], "name": u["name"], "kind": u["kind"], "file": u["file"], "line": u["line"],
                        "test_classes": u["test_classes"], "methods": methods, "counts": counts,
                        "coverage": u.get("coverage")})
    tclasses = []
    for tc in sorted(model["test_classes"].values(), key=lambda t: t["id"]):
        if scope is not None and tc["id"] not in scope["tests"]:
            continue
        tests = []
        for t in tc["tests"]:
            st = checks.test_status(t)
            bad = next((r for r in t["results"] if r["status"] in ("failed", "error")), {})
            tests.append({"name": t["name"], "line": t["line"], "status": st,
                          "time": round(sum(r["time"] for r in t["results"]), 3), "message": bad.get("message"),
                          "type": bad.get("type"), "details": bad.get("details"), "stdout": bad.get("stdout"),
                          "disabled": t["disabled"], "runs": len(t["results"]),
                          "targets": sorted({f"{x['unit'].split('.')[-1]}.{x['method']}" for x in t["targets"]})})
        tclasses.append({"id": tc["id"], "file": tc["file"], "tests": tests, "targets": tc["primary"],
                         "time": round(sum(t["time"] for t in tests), 3)})
    st = [c["status"] for c in cases]
    n_err = sum(1 for f in fs if f["severity"] == "error")
    n_warn = sum(1 for f in fs if f["severity"] == "warning")
    all_methods = [m for c in classes for m in c["methods"] if not m["skip"]]
    total = cov.get("total", {}) if cov else {}
    summary = {"tests": len(cases), "passed": st.count("passed"), "failed": st.count("failed"),
               "errors": st.count("error"), "skipped": st.count("skipped"),
               "not_run": sum(1 for tc in tclasses for t in tc["tests"] if t["status"] == "not run"),
               "pass_rate": round(100.0 * st.count("passed") / (len(st) - st.count("skipped")), 1)
               if len(st) - st.count("skipped") > 0 else None,
               "duration_s": round(sum(c["time"] for c in cases), 2), "classes": len(classes),
               "methods_total": len(all_methods),
               "methods_tested": sum(1 for m in all_methods if m["status"] == "tested"),
               "methods_untested": sum(1 for m in all_methods if m["status"] == "untested"),
               "methods_failing": sum(1 for m in all_methods if m["status"] == "failing"),
               "methods_weak": sum(1 for m in all_methods if m["status"] == "weak"),
               "line_coverage": rs.pct(total.get("LINE")), "branch_coverage": rs.pct(total.get("BRANCH")),
               "findings": {"error": n_err, "warning": n_warn, "info": len(fs) - n_err - n_warn}}
    reasons = []
    seen = {}
    for f in fs:
        if f["severity"] == "error" or (opts.strict and f["severity"] == "warning"):
            seen[f["title"]] = seen.get(f["title"], 0) + 1
    for title, n in seen.items():
        reasons.append(f"{n} x {title}")
    verdict = "FAILED" if reasons else "PASSED"
    for w in run.get("warnings") or []:
        reasons.append("Note: " + w) if verdict == "FAILED" else None
    run_out = {k: v for k, v in run.items() if k not in ("unmatched",)}
    return {"generator": {"name": "kotlin-unit-test/ktest.py", "version": VERSION},
            "project": info["root"], "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "build": info["build"], "run": run_out, "summary": summary, "verdict": verdict,
            "verdict_reasons": reasons, "classes": classes, "test_classes": tclasses, "findings": fs,
            "unmatched_results": [{k: c[k] for k in ("classname", "name", "status")} for c in run.get("unmatched", [])],
            "result_files": [str(f) for f in files], "coverage_files": cov.get("files", []) if cov else [],
            "mutation": mutation, "warnings": run.get("warnings") or [],
            "scope": {k: sorted(v) for k, v in scope.items()} if scope else None}


def write_report(report, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    (out / "index.html").write_text(html_report.render(report), encoding="utf-8")
    return out / "index.html"


def print_summary(report, html=None, max_findings=25):
    s = report["summary"]
    print(f"{report['verdict']}: {s['tests']} test(s) run, {s['passed']} passed, {s['failed'] + s['errors']} failed, "
          f"{s['skipped']} skipped, {s['not_run']} declared but not run")
    print(f"Methods: {s['methods_tested']}/{s['methods_total']} tested, {s['methods_untested']} untested, "
          f"{s['methods_failing']} failing, {s['methods_weak']} only weakly tested"
          + (f"; line coverage {s['line_coverage']}%" if s["line_coverage"] is not None else ""))
    f = s["findings"]
    print(f"Findings: {f['error']} error(s), {f['warning']} warning(s), {f['info']} info")
    for x in report["findings"][:max_findings]:
        where = f" {x['file']}:{x['line']}" if x.get("file") and x.get("line") else (f" {x['file']}" if x.get("file")
                                                                                     else "")
        print(f"  {x['severity'].upper():7} {x['rule']} {x['title']}{where}\n          {x['detail'][:300]}")
    if len(report["findings"]) > max_findings:
        print(f"  ... {len(report['findings']) - max_findings} more in the report")
    for w in report.get("warnings") or []:
        print(f"  NOTE {w}")
    if html:
        print(f"Report: {html}")


# ------------------------------------------------------------------------------------------------ commands

def cmd_plan(opts):
    info = checks.scan(opts.project, include_private=opts.include_private)
    model = checks.link(info)
    rows = []
    for u in sorted(model["units"].values(), key=lambda u: (u["file"], u["line"])):
        if (u["private"] and not opts.include_private) or not u["methods"]:
            continue
        if opts.cls and not set(opts.cls) & {u["id"], u["name"], u["simple"]}:
            continue
        rows.append(u)
    if opts.json:
        print(json.dumps([{"class": u["id"], "kind": u["kind"], "file": u["file"], "test_classes": u["test_classes"],
                           "methods": [{"name": m["name"], "line": m["line"], "signature": m["signature"],
                                        "skip": m["skip"], "tests": m["tests"]} for m in u["methods"]]}
                          for u in rows], indent=2))
        return 0
    tested = total = 0
    for u in rows:
        print(f"{u['id']}  [{u['kind']}]  {u['file']}:{u['line']}")
        print(f"    test classes: {', '.join(u['test_classes']) or 'none'}")
        for m in u["methods"]:
            if m["skip"]:
                print(f"    [-] {m['signature']}  ({m['skip']})")
                continue
            total += 1
            tested += bool(m["tests"])
            mark = "x" if m["tests"] else " "
            how = (f"{len(m['tests'])} test(s): " + ", ".join(sorted({x['test'].split('#')[1] for x in m['tests']}))[:120]
                   if m["tests"] else "NO TEST")
            print(f"    [{mark}] {m['signature']}  line {m['line']}  -> {how}")
    print(f"\n{len(rows)} class(es), {tested}/{total} method(s) have at least one linked test. "
          f"Test files: {len(info['files']['test'])}, main files: {len(info['files']['main'])}.")
    return 0


def cmd_run(opts):
    project = Path(opts.project).resolve()
    out = Path(opts.out).resolve()
    info = checks.scan(project, include_private=opts.include_private)
    model = checks.link(info)
    filters = resolve_selection(model, opts)
    if opts.dry_run:
        tool = detect_tool(project, opts)
        if tool["tool"] == "gradle":
            print(subprocess.list2cmdline(gradle_command(tool, info, filters, opts)))
        elif tool["tool"] == "maven":
            print(subprocess.list2cmdline(maven_command(tool, filters, opts)))
        else:
            for c in kotlinc_commands(tool, info, filters, opts, out)[0]:
                print(subprocess.list2cmdline(c))
        return 0
    print(f"Running {'all tests' if not filters else ', '.join(f['class'] + ('#' + f['test'] if f['test'] else '') for f in filters)} ...",
          flush=True)
    run, cases, files, cov_files = run_tests(project, info, filters, opts, out)
    report, _, _ = analyse(project, opts, run, cases, files, cov_files, filters=filters)
    html = write_report(report, out)
    print_summary(report, html)
    return 0 if report["verdict"] == "PASSED" else 1


def cmd_verify(opts, write=False):
    project = Path(opts.project).resolve()
    report, _, _ = analyse(project, opts)
    html = write_report(report, Path(opts.out).resolve()) if write else None
    if opts.json:
        print(json.dumps({k: report[k] for k in ("verdict", "verdict_reasons", "summary", "findings")}, indent=2,
                         default=str))
    else:
        print_summary(report, html)
    return 0 if report["verdict"] == "PASSED" else 1


SCAFFOLD_HEADER = """package {package}

{imports}

/**
 * Unit tests for {target}.
 * Generated by ktest.py scaffold: replace every TODO with a real test (arrange, act, assert).
 * ktest.py verify reports unfinished tests (KT003) until they are written.
 */
class {name} {{
{setup}
"""


def cmd_scaffold(opts):
    project = Path(opts.project).resolve()
    info = checks.scan(project, include_private=opts.include_private)
    model = checks.link(info)
    if not opts.cls:
        raise KtestError("scaffold needs --class NAME (repeatable)")
    build = info["build"]
    written = []
    for cname in opts.cls:
        us = [u for u in model["units"].values() if cname in (u["id"], u["name"], u["simple"])]
        if not us:
            raise KtestError(f"--class {cname}: not found in the main sources")
        for u in us:
            methods = [m for m in u["testable"] if (opts.all_methods or not m["tests"])
                       and (not opts.method or m["name"] in opts.method)]
            if not methods:
                print(f"{u['name']}: every method already has a linked test (use --all-methods to scaffold anyway)")
                continue
            junit4 = build["junit4"] and not build["junit_platform"]
            imports = ["org.junit.Test" if junit4 else "org.junit.jupiter.api.Test"]
            if build["kotlin_test"]:
                imports.append("kotlin.test.assertEquals")
            elif junit4:
                imports.append("org.junit.Assert.assertEquals")
            else:
                imports.append("org.junit.jupiter.api.Assertions.assertEquals")
            if any("suspend" in m["modifiers"] for m in methods):
                imports.append("kotlinx.coroutines.test.runTest")
            facade = u["kind"].startswith("file")
            simple = u["simple"][:-2] if facade and u["simple"].endswith("Kt") else u["simple"]
            name = simple + "Test"
            if u["kind"] == "object" or facade:
                setup = f"    // {('Call the functions directly' if facade else 'Call ' + u['name'] + '.method(...) directly')}.\n"
            else:
                setup = (f"    // TODO: create the object under test; mock its dependencies (e.g. with MockK):\n"
                         f"    // private val subject = {u['name']}(...)\n")
            body = SCAFFOLD_HEADER.format(package=u["package"] or "", imports="\n".join(f"import {i}" for i in imports),
                                          target=f"{u['name']} ({u['file']})", name=name, setup=setup)
            if not u["package"]:
                body = body.split("\n", 2)[2]
            cases = [("returns the expected result for typical input", "Arrange typical input, call it, assert the exact result"),
                     ("handles edge cases", "Empty/zero/null/boundary values; or assertFailsWith/assertThrows for invalid input")]
            for m in methods:
                for title, hint in cases:
                    run_open, run_close = (" = runTest {", "    }") if "suspend" in m["modifiers"] else (" {", "    }")
                    body += (f"\n    @Test\n    fun `{m['name']} {title}`(){run_open}\n"
                             f"        // {hint}\n"
                             f"        TODO(\"Test {u['name']}.{m['signature'].replace(chr(34), chr(39))}\")\n"
                             f"{run_close}\n")
            body += "}\n"
            src = Path(u["file"])
            parts = list(src.parts)
            if "src" in parts and parts.index("src") + 1 < len(parts) and parts[parts.index("src") + 1] == "main":
                i = parts.index("src")
                parts[i + 1] = "test"
                target = project.joinpath(*parts[:-1]) / f"{name}.kt"
            else:
                target = project / src.parent / f"{name}.kt"
            if target.exists() or opts.to_out:
                alt = Path(opts.out).resolve() / "scaffold" / (u["package"].replace(".", "/")) / f"{name}.kt"
                alt.parent.mkdir(parents=True, exist_ok=True)
                alt.write_text(body, encoding="utf-8")
                note = f" ({target.relative_to(project).as_posix()} exists: merge the new tests into it)" \
                    if target.exists() else ""
                written.append(f"{alt}{note}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
                written.append(str(target))
            print(f"{u['name']}: {len(methods)} method(s) -> {written[-1]}")
    return 0


# ------------------------------------------------------------------------------------------------ mutation

MUTATORS = [
    (re.compile(r"(?<=\s)==(?=\s)"), "!="), (re.compile(r"(?<=\s)!=(?=\s)"), "=="),
    (re.compile(r"(?<=\s)<=(?=\s)"), "<"), (re.compile(r"(?<=\s)>=(?=\s)"), ">"),
    (re.compile(r"(?<=\s)<(?=\s)"), "<="), (re.compile(r"(?<=\s)>(?=\s)"), ">="),
    (re.compile(r"(?<=\s)&&(?=\s)"), "||"), (re.compile(r"(?<=\s)\|\|(?=\s)"), "&&"),
    (re.compile(r"(?<=\s)\+(?=\s)"), "-"), (re.compile(r"(?<=\s)-(?=\s)"), "+"),
    (re.compile(r"(?<=\s)\*(?=\s)"), "/"), (re.compile(r"(?<=\s)/(?=\s)"), "*"), (re.compile(r"(?<=\s)%(?=\s)"), "*"),
    (re.compile(r"\btrue\b"), "false"), (re.compile(r"\bfalse\b"), "true"),
    (re.compile(r"(?<=\s)\+=(?=\s)"), "-="), (re.compile(r"(?<=\s)-=(?=\s)"), "+="),
    (re.compile(r"(?<![\w.!)\]])!(?=[\w(])"), ""),
]
BACKUP_SUFFIX = ".ktest-orig"


def restore_leftovers(root):
    restored = []
    for p in rs.walk(root):
        if p.name.endswith(".kt" + BACKUP_SUFFIX):
            orig = p.with_name(p.name[:-len(BACKUP_SUFFIX)])
            shutil.copyfile(p, orig)
            p.unlink()
            restored.append(str(orig))
    return restored


def mutants_for(project, unit, methods, limit):
    path = Path(project) / unit["file"]
    text = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    norm = text.replace("\r\n", "\n")
    parsed = ks.parse(norm, path)
    code = ks.Code(norm)
    per_method = []
    for m in methods:
        fn = next((f for f in parsed["functions"] if f["name"] == m["name"] and f["line"] == m["line"]), None)
        if not fn or not fn["body_kind"]:
            continue
        b0, b1 = fn["body_range"]
        found = []
        seg = code.m[b0:b1 + 1]
        for rx, repl in MUTATORS:
            for mm in rx.finditer(seg):
                pos = b0 + mm.start()
                found.append({"method": f"{unit['name']}.{m['name']}", "pos": pos, "end": b0 + mm.end(),
                              "original": norm[pos:b0 + mm.end()], "mutated": repl, "line": code.line(pos),
                              "file": unit["file"]})
        found.sort(key=lambda x: x["pos"])
        per_method.append(found)
    out = []
    while len(out) < limit and any(per_method):                # round-robin over methods
        for lst in per_method:
            if lst and len(out) < limit:
                out.append(lst.pop(0))
    for x in out:
        ctx_start = norm.rfind("\n", 0, x["pos"]) + 1
        ctx_end = norm.find("\n", x["pos"])
        line = norm[ctx_start:ctx_end if ctx_end >= 0 else None]
        x["code"] = line.strip()[:200]
    return path, norm, nl, out


def cmd_mutate(opts):
    project = Path(opts.project).resolve()
    out = Path(opts.out).resolve()
    left = restore_leftovers(project)
    for p in left:
        print(f"Restored {p} from a backup left by an interrupted mutation run.")
    info = checks.scan(project, include_private=opts.include_private)
    model = checks.link(info)
    if not opts.cls or len(opts.cls) != 1:
        raise KtestError("mutate needs exactly one --class")
    us = [u for u in model["units"].values() if opts.cls[0] in (u["id"], u["name"], u["simple"])]
    if len(us) != 1:
        raise KtestError(f"--class {opts.cls[0]}: {'not found' if not us else 'ambiguous, use the full name'}")
    unit = us[0]
    methods = [m for m in unit["testable"] if not opts.method or m["name"] in opts.method]
    sel = argparse.Namespace(**vars(opts))
    sel.method = None
    filters = resolve_selection(model, sel)
    path, original, nl, mutants = mutants_for(project, unit, methods, opts.max_mutants)
    if not mutants:
        raise KtestError(f"no mutable operators found in {unit['name']} (it may have only trivial methods)")
    print(f"Baseline: running the tests of {unit['name']} ...", flush=True)
    base_opts = argparse.Namespace(**vars(opts))
    base_opts.coverage = False
    run, cases, files, _ = run_tests(project, info, filters, base_opts, out, clean=True, coverage=False,
                                     log_name="mutation-baseline.log")
    bad = [c for c in cases if c["status"] in ("failed", "error")]
    if run.get("build_failed") or not cases or bad:
        raise KtestError("the tests must pass before a mutation check "
                         f"({len(bad)} failing, {len(cases)} run; see {run['log']})")
    per_timeout = max(60, int(run["duration_s"] * 3) + 30)
    raw_original = path.read_bytes()
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    shutil.copyfile(path, backup)
    results = []
    try:
        for i, mu in enumerate(mutants, 1):
            mutated = original[:mu["pos"]] + mu["mutated"] + original[mu["end"]:]
            path.write_bytes(mutated.replace("\n", nl).encode("utf-8"))
            r, c2, _, _ = run_tests(project, info, filters, base_opts, out, clean=False, coverage=False,
                                    log_name=f"mutants/mutant-{i:03d}.log", timeout=per_timeout)
            if r.get("timed_out"):
                res = "timeout"
            elif any(c["status"] in ("failed", "error") for c in c2):
                res = "killed"
            elif r.get("build_failed") or not c2:
                res = "compile error"
            else:
                res = "survived"
            killers = sorted({f"{c['classname'].split('.')[-1]}.{c['name']}" for c in c2
                              if c["status"] in ("failed", "error")})[:5]
            results.append({**{k: mu[k] for k in ("method", "original", "mutated", "line", "file", "code")},
                            "result": res, "killed_by": killers})
            print(f"  [{i}/{len(mutants)}] line {mu['line']}: '{mu['original']}' -> '{mu['mutated']}'  {res}",
                  flush=True)
            path.write_bytes(raw_original)
    finally:
        path.write_bytes(raw_original)
        if path.read_bytes() == raw_original:
            backup.unlink()
        else:
            print(f"WARNING could not restore {path}; the original is in {backup}", file=sys.stderr)
    killed = sum(1 for r in results if r["result"] in ("killed", "timeout"))
    survived = sum(1 for r in results if r["result"] == "survived")
    summary = {"killed": sum(1 for r in results if r["result"] == "killed"), "survived": survived,
               "timeout": sum(1 for r in results if r["result"] == "timeout"),
               "invalid": sum(1 for r in results if r["result"] == "compile error"),
               "score": round(100.0 * killed / (killed + survived), 1) if killed + survived else None}
    mutation = {"unit": unit["id"], "file": unit["file"], "mutants": results, "summary": summary}
    out.mkdir(parents=True, exist_ok=True)
    (out / "mutation.json").write_text(json.dumps(mutation, indent=2), encoding="utf-8")
    print("Re-running the tests on the restored source ...", flush=True)
    run, cases, files, cov_files = run_tests(project, info, filters, opts, out, clean=True)
    report, _, _ = analyse(project, opts, run, cases, files, cov_files, mutation, filters=filters)
    html = write_report(report, out)
    print(f"Mutation score {summary['score']}%: {summary['killed']} killed, {survived} survived, "
          f"{summary['timeout']} timed out, {summary['invalid']} did not compile.")
    print_summary(report, html)
    if any(c["status"] in ("failed", "error") for c in cases):
        print("WARNING tests fail on the restored source: check the file and the build", file=sys.stderr)
        return 1
    return 0 if (summary["score"] or 0) >= opts.min_score and report["verdict"] == "PASSED" else 1


# ------------------------------------------------------------------------------------------------ CLI

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("project", nargs="?", default=".", help="project folder (default: current folder)")
    common.add_argument("--out", default="ktest-report", help="report folder (default ./ktest-report)")
    common.add_argument("--include-private", action="store_true", help="also plan/check private methods")
    common.add_argument("--json", action="store_true", help="JSON output (plan, verify)")
    sel = argparse.ArgumentParser(add_help=False)
    sel.add_argument("--class", dest="cls", action="append", metavar="NAME",
                     help="production class (simple or full name), repeatable; a test class name also works")
    sel.add_argument("--method", action="append", metavar="NAME", help="only this method of --class (repeatable)")
    sel.add_argument("--test", action="append", metavar="TESTCLASS[#test]", help="run this test class/test directly")
    runp = argparse.ArgumentParser(add_help=False)
    runp.add_argument("--tool", choices=["auto", "gradle", "maven", "kotlinc"], default="auto")
    runp.add_argument("--variant", default="debug", help="Android build variant for unit tests (default debug)")
    runp.add_argument("--coverage", action="store_true", help="also produce coverage (JaCoCo/Kover must be set up)")
    runp.add_argument("--coverage-task", help="Gradle task that writes coverage XML (if not jacocoTestReport/koverXmlReport)")
    runp.add_argument("--junit-jar", help="kotlinc mode: junit-platform-console-standalone jar")
    runp.add_argument("--classpath", help="kotlinc mode: extra jars (MockK, ...) separated by the OS path separator")
    runp.add_argument("--build-arg", action="append", help="extra argument for the build tool (repeatable)")
    runp.add_argument("--timeout", type=int, default=1800, help="seconds before the build is stopped (default 1800)")
    runp.add_argument("--verbose", action="store_true", help="show the build output while it runs")
    qual = argparse.ArgumentParser(add_help=False)
    qual.add_argument("--strict", action="store_true", help="warnings also fail the verdict")
    qual.add_argument("--min-coverage", type=float, help="fail classes with line coverage below this percent")
    qual.add_argument("--slow", type=float, default=2.0, help="report tests slower than this many seconds")
    qual.add_argument("--results", action="append", help="folder with JUnit XML (default: search the project)")
    qual.add_argument("--coverage-xml", action="append", help="coverage XML file (default: search the project)")

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--version", action="version", version=f"ktest {VERSION}")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan", parents=[common], help="classes, methods and their tests")
    p.add_argument("--class", dest="cls", action="append", metavar="NAME", help="only these classes")
    p = sub.add_parser("scaffold", parents=[common], help="write test skeletons for untested methods")
    p.add_argument("--class", dest="cls", action="append", metavar="NAME", required=True)
    p.add_argument("--method", action="append", metavar="NAME")
    p.add_argument("--all-methods", action="store_true", help="also methods that already have tests")
    p.add_argument("--to-out", action="store_true", help="write into <out>/scaffold instead of the test folder")
    sub.add_parser("run", parents=[common, sel, runp, qual], help="run tests and write the report").add_argument(
        "--dry-run", action="store_true", help="print the build command only")
    sub.add_parser("verify", parents=[common, qual], help="check tests and existing results, no run")
    sub.add_parser("report", parents=[common, qual], help="rebuild the HTML report from existing results")
    p = sub.add_parser("mutate", parents=[common, sel, runp, qual], help="check that the tests catch injected bugs")
    p.add_argument("--max-mutants", type=int, default=12, help="most mutants to try (default 12)")
    p.add_argument("--min-score", type=float, default=0, help="fail if the mutation score is below this percent")
    opts = ap.parse_args(argv)
    if not opts.cmd:
        ap.print_help()
        return 2
    for k, v in (("results", None), ("coverage_xml", None), ("strict", False), ("min_coverage", None),
                 ("slow", 2.0), ("coverage", False), ("cls", None), ("method", None), ("test", None)):
        if not hasattr(opts, k):
            setattr(opts, k, v)
    if not Path(opts.project).is_dir():
        print(f"ERROR project folder not found: {opts.project}", file=sys.stderr)
        return 2
    try:
        if opts.cmd == "plan":
            return cmd_plan(opts)
        if opts.cmd == "scaffold":
            return cmd_scaffold(opts)
        if opts.cmd == "run":
            return cmd_run(opts)
        if opts.cmd == "verify":
            return cmd_verify(opts)
        if opts.cmd == "report":
            return cmd_verify(opts, write=True)
        if opts.cmd == "mutate":
            return cmd_mutate(opts)
    except KtestError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
