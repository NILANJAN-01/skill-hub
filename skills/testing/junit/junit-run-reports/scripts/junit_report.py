#!/usr/bin/env python3
"""Run JUnit tests (Java and Kotlin) and explain the results.

Usage:
    python junit_report.py cmd --tool gradle|maven|console [selection] [--module M]
    python junit_report.py run [--tool gradle|maven] [selection] [--project DIR] [--dry-run] [--json]
    python junit_report.py parse PATH [PATH ...] [--json] [--markdown] [--slowest N]
    python junit_report.py results [PROJECT_DIR] [--json] [--markdown] [--slowest N]

Selection: --class C (repeatable; Class or Class#method), --method M, --package P, --tag T, --exclude-tag T,
           --rerun N (retry failures, Maven), --fail-fast, --class-path CP (console)

cmd      prints the Gradle, Maven or ConsoleLauncher command for the selection, nothing is run.
run      runs that command in the project (Gradle wrapper or mvn), then summarises the reports it wrote.
parse    reads legacy JUnit XML (Gradle build/test-results, Maven surefire/failsafe-reports, ConsoleLauncher
         --reports-dir) and Open Test Reporting XML (open-test-report.xml) and prints counts, every failure
         with a likely cause and fix, skipped tests with reasons, flaky tests (passed after a rerun) and the
         slowest tests. --markdown prints a table for a CI job summary.
results  finds every report under a project and summarises them together.
Standard library only. cmd, parse and results only read files.

Exit codes: 0 all passed, 1 failures or errors, 2 bad usage or no reports, 3 the build tool is missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

JUNIT = "6.1.3"

# (id, regex over type + message + stack, cause, fix). First match wins.
CAUSES = [
    ("version-mismatch", re.compile(r"(NoSuchMethodError|NoClassDefFoundError|ClassNotFoundException|"
                                    r"AbstractMethodError)[^\n]*(org[./]junit|opentest4j)|OutputDirectoryProvider not "
                                    r"available|TestEngine with ID '[\w-]+' failed to discover"),
     "JUnit artifacts of different versions are on the test classpath (for example Platform 1.x with Jupiter 6, "
     "or an old launcher from the IDE or build plugin)",
     "Import org.junit:junit-bom:%s and drop versions from the other JUnit dependencies; on Gradle add "
     "testRuntimeOnly(\"org.junit.platform:junit-platform-launcher\"); on Maven use Surefire 3.x" % JUNIT),
    ("lifecycle-config", re.compile(r"@(BeforeAll|AfterAll) method .* must be static|must not be private|"
                                    r"must not return a value|must be static unless"),
     "a lifecycle or test method breaks JUnit's rules (static, private, return type)",
     "@BeforeAll/@AfterAll static (Kotlin: companion object + @JvmStatic) or @TestInstance(PER_CLASS); test "
     "methods non-private and void"),
    ("parameter-resolution", re.compile(r"ParameterResolutionException|No ParameterResolver registered"),
     "a test or constructor parameter has no resolver: missing extension, or a parameter on a plain @Test",
     "Register the extension that provides it (@ExtendWith(MockitoExtension.class), Spring, ...), use "
     "@ParameterizedTest with a source, or remove the parameter"),
    ("parameterized-config", re.compile(r"You must configure at least one set of arguments|ArgumentConversionException|"
                                        r"Failed to convert|ArgumentCountValidation|Configuration error.*@\w+Source|"
                                        r"PreconditionViolationException"),
     "a @ParameterizedTest source does not fit the parameters (no rows, a value that cannot be converted, "
     "or too many columns)",
     "Check the @CsvSource / @MethodSource values against the parameter types and count; quote values with "
     "commas; use argumentCountValidation = STRICT to catch extra columns"),
    ("mockito", re.compile(r"org\.mockito\.\S*(UnnecessaryStubbingException|WantedButNotInvoked|"
                           r"PotentialStubbingProblem|TooManyActualInvocations|ArgumentsAreDifferent|"
                           r"MockitoException|InvalidUseOfMatchersException)"),
     "a Mockito verification or strict-stubbing check failed",
     "Read the Mockito message: remove unused stubs, check the arguments of the expected call, and use "
     "@ExtendWith(MockitoExtension.class) (Mockito 5 on Java 21+ needs its agent configured for inline mocks)"),
    ("spring-context", re.compile(r"Failed to load ApplicationContext|BeanCreationException|"
                                  r"NoSuchBeanDefinitionException"),
     "the Spring test context could not start", "Fix the first 'Caused by' in the stack (a missing bean, "
     "property or database); slice tests (@WebMvcTest, @DataJpaTest) load less"),
    ("timeout", re.compile(r"TimeoutException|timed out after|execution exceeded timeout|"
                           r"execution timed out after", re.I),
     "the test or an assertTimeout block took longer than its limit",
     "Find the slow step; wait for a condition instead of sleeping; raise @Timeout only if the work is really "
     "that slow (and consider assertTimeoutPreemptively side effects)"),
    ("multiple-failures", re.compile(r"MultipleFailuresError|Multiple Failures \(\d+ failures\)"),
     "several assertions in assertAll failed", "Fix each listed failure; they are reported together on purpose"),
    ("assertion", re.compile(r"AssertionFailedError|AssertionError|ComparisonFailure|expected: ?<|"
                             r"org\.opentest4j|Expecting|to be equal to|but was"),
     "an assertion failed: the code returned something other than the test expects",
     "Compare expected and actual below; decide whether the code or the expectation is wrong"),
    ("null-pointer", re.compile(r"NullPointerException"),
     "a NullPointerException: often an object the test never initialised",
     "Check setup: a JUnit 4 @Before in a Jupiter class never runs, mocks need @ExtendWith(MockitoExtension.class) "
     "or MockitoAnnotations.openMocks, and @BeforeEach must assign the field"),
    ("resource", re.compile(r"OutOfMemoryError|StackOverflowError|Too many open files"),
     "the test JVM ran out of a resource", "Look for unbounded recursion, leaked resources (@AutoClose / "
     "try-with-resources) or raise the test JVM heap (Gradle maxHeapSize, Surefire argLine)"),
]


def classify(text: str) -> dict:
    for rid, rx, cause, fix in CAUSES:
        if rx.search(text or ""):
            return {"id": rid, "cause": cause, "fix": fix}
    return {"id": "exception", "cause": "an unexpected exception was thrown",
            "fix": "Read the first stack frame in your code ('at' line) and the exception message"}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def expected_actual(msg: str):
    m = re.search(r"expected: ?<(.*?)> but was: ?<(.*?)>", msg or "", re.S)
    return (m.group(1), m.group(2)) if m else None


def first_frame(stack: str, classname: str) -> str:
    top = classname.split("$")[0]
    for line in (stack or "").splitlines():
        m = re.match(r"\s*at ([\w.$]+)\.([\w$<> -]+?)\(([^)]*)\)", line)
        if m and m.group(1).split("$")[0] == top:
            return "%s.%s(%s)" % (m.group(1), m.group(2), m.group(3))
    for line in (stack or "").splitlines():
        m = re.match(r"\s*at ([\w.$]+)\.([\w$<> -]+?)\(([^)]*)\)", line)
        if m and not re.match(r"(java|jdk|sun|org\.junit|org\.opentest4j|kotlin|org\.gradle|org\.apache\.maven|"
                              r"worker\.org\.gradle)\.", m.group(1)):
            return "%s.%s(%s)" % (m.group(1), m.group(2), m.group(3))
    return ""


# ================================================================================ parsers
def parse_legacy(path: str, root) -> list:
    suites = [root] if local(root.tag) == "testsuite" else [s for s in root.iter() if local(s.tag) == "testsuite"]
    out = []
    for s in suites:
        for tc in s:
            if local(tc.tag) != "testcase":
                continue
            t = {"class": tc.get("classname") or s.get("name", ""), "name": tc.get("name", ""),
                 "time": float(tc.get("time") or 0), "status": "passed", "message": "", "type": "", "stack": "",
                 "flaky": 0, "reason": "", "file": path}
            for ch in tc:
                tag = local(ch.tag)
                if tag in ("failure", "error"):
                    t["status"] = "failed" if tag == "failure" else "error"
                    t["message"] = ch.get("message") or ""
                    t["type"] = ch.get("type") or ""
                    t["stack"] = (ch.text or "").strip()
                elif tag == "skipped":
                    t["status"] = "skipped"
                    t["reason"] = ch.get("message") or (ch.text or "").strip()
                elif tag in ("flakyFailure", "flakyError"):
                    t["flaky"] += 1
                elif tag in ("rerunFailure", "rerunError"):
                    t["reruns"] = t.get("reruns", 0) + 1
            out.append(t)
    return out


def parse_open(path: str, root) -> list:
    """Open Test Reporting: event-based (e:events) or hierarchical (h:execution) XML."""
    out = []
    if local(root.tag) == "execution":
        def walk(node, names):
            for ch in node:
                if local(ch.tag) in ("root", "child"):
                    name = ch.get("name", "")
                    kids = [k for k in ch if local(k.tag) == "child"]
                    if not kids:
                        out.append(_open_record(ch, names + [name], path, ch.get("duration")))
                    walk(ch, names + [name])
        walk(root, [])
        return out
    started, children, finished = {}, set(), {}
    for ev in root:
        tag = local(ev.tag)
        if tag == "started":
            started[ev.get("id")] = ev
            if ev.get("parentId"):
                children.add(ev.get("parentId"))
        elif tag == "finished":
            finished[ev.get("id")] = ev
    for eid, st in started.items():
        meta = {local(x.tag): (x.text or "") for x in st.iter() if len(x) == 0}
        is_test = meta.get("type") == "TEST" or (eid not in children and meta.get("type") != "CONTAINER")
        if not is_test:
            continue
        names, pid = [], st.get("parentId")
        while pid and pid in started:
            p = started[pid]
            names.insert(0, p.get("name", ""))
            pid = p.get("parentId")
        names.append(st.get("name", ""))
        fin = finished.get(eid)
        rec = _open_record(fin if fin is not None else st, names, path, None)
        src = next((x for x in st.iter() if local(x.tag) == "methodSource"), None)
        if src is not None:
            rec["class"] = src.get("className", rec["class"])
        rec["time"] = _duration(st.get("time"), fin.get("time") if fin is not None else None)
        if fin is None:
            rec["status"] = "error"
            rec["message"] = "test started but never finished (crash or killed JVM)"
        out.append(rec)
    return out


def _open_record(node, names, path, duration):
    res = next((x for x in node if local(x.tag) == "result"), None)
    status = (res.get("status") if res is not None else "SUCCESSFUL") or "SUCCESSFUL"
    thr = next((x for x in node.iter() if local(x.tag) == "throwable"), None)
    reason = next((x.text or "" for x in node.iter() if local(x.tag) == "reason"), "")
    t = {"class": ".".join(n for n in names[1:-1] if n) or (names[0] if names else ""), "name": names[-1] if names else "",
         "time": _iso_duration(duration) if duration else 0.0, "status": {"SUCCESSFUL": "passed", "SKIPPED": "skipped",
                                                                        "ABORTED": "skipped", "FAILED": "failed",
                                                                        "ERRORED": "error"}.get(status, "failed"),
         "message": "", "type": "", "stack": "", "flaky": 0, "reason": reason.strip(), "file": path}
    if status == "ABORTED" and not t["reason"]:
        t["reason"] = "aborted (assumption not met)"
    if thr is not None:
        t["type"] = thr.get("type", "")
        t["stack"] = (thr.text or "").strip()
        first = t["stack"].splitlines()[0] if t["stack"] else ""
        t["message"] = first.split(": ", 1)[1] if ": " in first else first
        if t["status"] == "failed" and thr.get("assertionError") == "false":
            t["status"] = "error"
    return t


def _iso_duration(d: str) -> float:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", d or "")
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3) or 0)) if m else 0.0


def _duration(a, b) -> float:
    from datetime import datetime

    def p(x):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            return None
    s, e = p(a), p(b)
    return (e - s).total_seconds() if s and e else 0.0


def parse_file(path: str) -> list:
    root = ET.parse(path).getroot()
    tag = local(root.tag)
    if tag in ("events", "execution"):
        return parse_open(path, root)
    if tag in ("testsuite", "testsuites"):
        return parse_legacy(path, root)
    raise ValueError("%s is not a JUnit XML or Open Test Reporting file (root <%s>)" % (path, tag))


def expand(paths: list) -> list:
    """Files as given; folders are searched for TEST-*.xml and open-test-report.xml."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for pat in ("TEST-*.xml", "open-test-report.xml"):
                files += glob.glob(os.path.join(p, "**", pat), recursive=True)
        else:
            files.append(p)
    return sorted(set(files), key=files.index)


def find_reports(project: str) -> list:
    pats = ["**/build/test-results/**/TEST-*.xml", "**/target/surefire-reports/TEST-*.xml",
            "**/target/failsafe-reports/TEST-*.xml", "**/open-test-report.xml", "**/reports/**/TEST-junit-*.xml"]
    found = set()
    for pat in pats:
        for f in glob.glob(os.path.join(project, pat), recursive=True):
            if "node_modules" not in f:
                found.add(os.path.normpath(f))
    return sorted(found)


# ================================================================================ summary
def summarise(tests: list, slowest: int = 5) -> dict:
    # the same test reported more than once (Gradle test-retry, several report formats): merge
    merged, order = {}, []
    for t in tests:
        k = (t["class"], t["name"])
        if k not in merged:
            # Surefire records reruns inside one testcase (flakyFailure / rerunFailure)
            earlier = ["failed"] * (t.get("flaky", 0) + t.get("reruns", 0))
            merged[k] = dict(t, attempts=earlier + [t["status"]])
            order.append(k)
        else:
            m = merged[k]
            m["attempts"].append(t["status"])
            if t["status"] == "passed" and m["status"] in ("failed", "error"):
                m.update(status="passed", flaky=m.get("flaky", 0) + 1)
            elif t["status"] in ("failed", "error") and m["status"] == "passed" and t["file"] == m["file"]:
                m["flaky"] = m.get("flaky", 0) + 1
            m["time"] = max(m["time"], t["time"])
    tests = [merged[k] for k in order]
    counts = {}
    for t in tests:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    failures = []
    for t in tests:
        if t["status"] in ("failed", "error"):
            text = "\n".join([t["type"], t["message"], t["stack"]])
            c = classify(text)
            msg = (t["message"] or (t["stack"].splitlines()[0] if t["stack"] else "")).strip()
            if t["type"] and msg.startswith(t["type"] + ": "):
                msg = msg[len(t["type"]) + 2:]
            failures.append({"test": "%s#%s" % (t["class"], t["name"]), "status": t["status"], "type": t["type"],
                             "message": msg.splitlines()[0][:300] if msg else "", "cause_id": c["id"],
                             "cause": c["cause"], "fix": c["fix"], "at": first_frame(t["stack"], t["class"]),
                             "expected_actual": expected_actual(t["message"] or t["stack"]), "file": t["file"]})
    skipped = [{"test": "%s#%s" % (t["class"], t["name"]), "reason": t["reason"] or "(no reason given)"}
               for t in tests if t["status"] == "skipped"]
    flaky = [{"test": "%s#%s" % (t["class"], t["name"]), "attempts": t.get("attempts"), "status": t["status"]}
             for t in tests if t.get("flaky")]
    slow = sorted((t for t in tests if t["time"]), key=lambda t: -t["time"])[:slowest]
    no_reason = [s for s in skipped if s["reason"] == "(no reason given)"]
    return {"total": len(tests), "counts": counts, "failures": failures, "skipped": skipped, "flaky": flaky,
            "slowest": [{"test": "%s#%s" % (t["class"], t["name"]), "seconds": round(t["time"], 3)} for t in slow],
            "time": round(sum(t["time"] for t in tests), 3), "skipped_without_reason": len(no_reason),
            "ok": not failures}


def print_summary(rep: dict, files: list) -> None:
    c = rep["counts"]
    print("JUnit results: %d report file(s)" % len(files))
    print("tests: %d  passed: %d  failed: %d  errors: %d  skipped: %d  flaky: %d  time: %.1fs" %
          (rep["total"], c.get("passed", 0), c.get("failed", 0), c.get("error", 0), c.get("skipped", 0),
           len(rep["flaky"]), rep["time"]))
    for f in rep["failures"]:
        print("\n%s %s [%s]" % (f["status"].upper(), f["test"], f["cause_id"]))
        if f["type"]:
            print("  type:    %s" % f["type"])
        print("  message: %s" % f["message"])
        if f["expected_actual"]:
            print("  expected: %s\n  actual:   %s" % f["expected_actual"])
        if f["at"]:
            print("  at:      %s" % f["at"])
        print("  cause:   %s" % f["cause"])
        print("  fix:     %s" % f["fix"])
    if rep["flaky"]:
        print("\nFLAKY (failed, then passed on a rerun):")
        for f in rep["flaky"]:
            print("  %s  attempts: %s" % (f["test"], ", ".join(f["attempts"] or [])))
    if rep["skipped"]:
        print("\nSkipped (%d, %d without a reason):" % (len(rep["skipped"]), rep["skipped_without_reason"]))
        for s in rep["skipped"][:20]:
            print("  %s: %s" % (s["test"], s["reason"]))
    if rep["slowest"]:
        print("\nSlowest:")
        for s in rep["slowest"]:
            print("  %8.3fs  %s" % (s["seconds"], s["test"]))
    print("\n" + ("All tests passed." if rep["ok"] else "%d failing test(s)." % len(rep["failures"])))


def markdown(rep: dict) -> str:
    c = rep["counts"]
    lines = ["### JUnit results", "",
             "| Total | Passed | Failed | Errors | Skipped | Flaky | Time |", "|---|---|---|---|---|---|---|",
             "| %d | %d | %d | %d | %d | %d | %.1fs |" % (rep["total"], c.get("passed", 0), c.get("failed", 0),
                                                       c.get("error", 0), c.get("skipped", 0), len(rep["flaky"]),
                                                       rep["time"])]
    if rep["failures"]:
        lines += ["", "| Test | Cause | Message |", "|---|---|---|"]
        for f in rep["failures"]:
            lines.append("| `%s` | %s | %s |" % (f["test"], f["cause_id"], f["message"].replace("|", "\\|")[:150]))
    if rep["flaky"]:
        lines += ["", "Flaky: " + ", ".join("`%s`" % f["test"] for f in rep["flaky"])]
    return "\n".join(lines) + "\n"


# ================================================================================ commands
def gradle_cmd(a, project: str) -> list:
    wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
    if not os.path.isfile(os.path.join(project, "gradlew.bat" if os.name == "nt" else "gradlew")):
        wrapper = "gradle"
    mod = (a.module if a.module.startswith(":") else ":" + a.module) if a.module else ""
    task = (mod + ":" if mod else "") + (a.task or "test")
    cmd = [wrapper, task]
    for c in a.cls or []:
        if "#" in c:
            c = c.replace("#", ".")
        elif a.method:
            c = "%s.%s" % (c, a.method)
        cmd += ["--tests", c]
    if a.package:
        cmd += ["--tests", a.package + ".*"]
    if a.fail_fast:
        cmd.append("--fail-fast")
    if a.tag or a.exclude_tag:
        if a.tag:
            cmd.append("-PincludeTags=" + ",".join(a.tag))
        if a.exclude_tag:
            cmd.append("-PexcludeTags=" + ",".join(a.exclude_tag))
    return cmd


GRADLE_TAG_SNIPPET = '''tasks.test {
    useJUnitPlatform {
        (findProperty("includeTags") as String?)?.let { includeTags(*it.split(",").toTypedArray()) }
        (findProperty("excludeTags") as String?)?.let { excludeTags(*it.split(",").toTypedArray()) }
    }
}'''


def maven_cmd(a, project: str) -> list:
    mvnw = "mvnw.cmd" if os.name == "nt" else "./mvnw"
    exe = mvnw if os.path.isfile(os.path.join(project, "mvnw.cmd" if os.name == "nt" else "mvnw")) else "mvn"
    cmd = [exe, a.task or "test"]
    if a.module:
        cmd += ["-pl", a.module.strip(":"), "-am", "-Dsurefire.failIfNoSpecifiedTests=false"]
    sel = []
    for c in a.cls or []:
        sel.append(c if "#" in c or not a.method else "%s#%s" % (c, a.method))
    if a.package:
        sel.append(a.package.replace(".", "/") + "/**")
    if sel:
        cmd.append("-Dtest=" + ",".join(sel))
    if a.tag:
        cmd.append("-Dgroups=" + ",".join(a.tag))
    if a.exclude_tag:
        cmd.append("-DexcludedGroups=" + ",".join(a.exclude_tag))
    if a.rerun:
        cmd.append("-Dsurefire.rerunFailingTestsCount=%d" % a.rerun)
    if a.fail_fast:
        cmd.append("-Dsurefire.skipAfterFailureCount=1")
    return cmd


def console_cmd(a) -> list:
    cmd = ["java", "-jar", "junit-platform-console-standalone-%s.jar" % JUNIT, "execute"]
    cmd += ["--class-path", a.class_path or os.pathsep.join(["build/classes/java/test", "build/classes/java/main"])]
    if not (a.cls or a.package):
        cmd.append("--scan-classpath")
    for c in a.cls or []:
        if "#" in c or a.method:
            cmd += ["--select-method", c if "#" in c else "%s#%s" % (c, a.method)]
        else:
            cmd += ["--select-class", c]
    if a.package:
        cmd += ["--select-package", a.package]
    for t in a.tag or []:
        cmd += ["--include-tag", t]
    for t in a.exclude_tag or []:
        cmd += ["--exclude-tag", t]
    if a.fail_fast:
        cmd.append("--fail-fast")
    cmd += ["--reports-dir", "build/junit-reports", "--details", "tree"]
    return cmd


def detect_tool(project: str) -> str:
    if any(os.path.isfile(os.path.join(project, f)) for f in ("build.gradle", "build.gradle.kts", "settings.gradle",
                                                              "settings.gradle.kts")):
        return "gradle"
    if os.path.isfile(os.path.join(project, "pom.xml")):
        return "maven"
    return ""


def build_cmd(a, project: str) -> list:
    tool = a.tool or detect_tool(project)
    if tool == "gradle":
        return gradle_cmd(a, project)
    if tool == "maven":
        return maven_cmd(a, project)
    if tool == "console":
        return console_cmd(a)
    raise SystemExit("error: no build.gradle(.kts) or pom.xml in %s; pass --tool" % project)


def show(cmd: list) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


def emit(tests, files, a) -> int:
    rep = summarise(tests, a.slowest)
    rep["files"] = files
    if a.json:
        print(json.dumps(rep, indent=2))
    elif a.markdown:
        print(markdown(rep), end="")
    else:
        print_summary(rep, files)
    return 0 if rep["ok"] else 1


def cmd_cmd(a) -> int:
    project = a.project or "."
    cmd = build_cmd(a, project)
    print(show(cmd))
    tool = a.tool or detect_tool(project)
    if tool == "gradle" and (a.tag or a.exclude_tag):
        print("\n# Gradle has no command-line tag filter: -PincludeTags / -PexcludeTags work once the test task reads "
              "them, e.g. in build.gradle.kts:\n" + GRADLE_TAG_SNIPPET)
    if tool == "gradle" and a.rerun:
        print("\n# Gradle reruns need the test-retry plugin: plugins { id(\"org.gradle.test-retry\") version \"...\" } "
              "and tasks.test { retry { maxRetries.set(%d); failOnPassedAfterRetry.set(false) } }" % a.rerun)
    return 0


def cmd_run(a) -> int:
    project = a.project or "."
    cmd = build_cmd(a, project)
    if a.dry_run:
        print(show(cmd))
        return 0
    exe = cmd[0]
    if exe.startswith("./") or exe.endswith((".bat", ".cmd")):        # the project's wrapper
        resolved = os.path.abspath(os.path.join(project, exe[2:] if exe.startswith("./") else exe))
    else:
        resolved = shutil.which(exe)
    if not resolved or not os.path.isfile(resolved):
        print("error: %s not found (install it, or use the project's wrapper)" % exe, file=sys.stderr)
        return 3
    before = {f: os.path.getmtime(f) for f in find_reports(project)}
    print("running: %s" % show(cmd), file=sys.stderr)
    try:
        proc = subprocess.run([resolved] + cmd[1:], cwd=project, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        print("error: the build did not finish within %d s" % a.timeout, file=sys.stderr)
        return 1
    files = [f for f in find_reports(project) if f not in before or os.path.getmtime(f) > before[f]]
    if not files:
        print("no new test reports were written (build exit code %d): the build may have failed before the tests "
              "ran, or no test matched the selection" % proc.returncode, file=sys.stderr)
        return 1 if proc.returncode else 2
    tests = []
    for f in files:
        try:
            tests += parse_file(f)
        except (ET.ParseError, ValueError):
            continue
    code = emit(tests, [os.path.relpath(f, project) for f in files], a)
    return code if code else (1 if proc.returncode else 0)


def cmd_parse(a) -> int:
    files = expand(a.paths)
    if not files:
        print("error: no report files in %s" % ", ".join(a.paths), file=sys.stderr)
        return 2
    tests = []
    for f in files:
        if not os.path.isfile(f):
            print("error: %s not found" % f, file=sys.stderr)
            return 2
        try:
            tests += parse_file(f)
        except ET.ParseError as e:
            print("error: %s is not valid XML (%s); a killed build can leave a half-written report" % (f, e),
                  file=sys.stderr)
            return 2
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            return 2
    return emit(tests, files, a)


def cmd_results(a) -> int:
    project = a.project or "."
    files = find_reports(project)
    if not files:
        print("no JUnit reports under %s (looked in build/test-results, target/surefire-reports, "
              "target/failsafe-reports and open-test-report.xml); run the tests first" % project, file=sys.stderr)
        return 2
    tests = []
    for f in files:
        try:
            tests += parse_file(f)
        except (ET.ParseError, ValueError):
            print("warning: skipped unreadable %s" % f, file=sys.stderr)
    return emit(tests, [os.path.relpath(f, project).replace(os.sep, "/") for f in files], a)


def add_selection(p):
    p.add_argument("--tool", choices=["gradle", "maven", "console"])
    p.add_argument("--project", default=".", help="project folder (default: current)")
    p.add_argument("--module", help="Gradle project path (:app) or Maven module (app)")
    p.add_argument("--task", help="Gradle task or Maven phase (default test; e.g. integrationTest, verify)")
    p.add_argument("--class", dest="cls", action="append", help="test class, or Class#method; repeatable")
    p.add_argument("--method", help="method name within --class")
    p.add_argument("--package", help="run every test in this package")
    p.add_argument("--tag", action="append", help="include tag (or tag expression); repeatable")
    p.add_argument("--exclude-tag", action="append", help="exclude tag; repeatable")
    p.add_argument("--rerun", type=int, help="rerun failing tests up to N times (Maven; Gradle prints how)")
    p.add_argument("--fail-fast", action="store_true", help="stop after the first failure")
    p.add_argument("--class-path", help="console launcher class path")


def add_output(p):
    p.add_argument("--json", action="store_true")
    p.add_argument("--markdown", action="store_true", help="Markdown table (CI job summary)")
    p.add_argument("--slowest", type=int, default=5, help="how many slow tests to list (default 5)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run JUnit tests and explain the results.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cmd", help="print the command for a selection")
    add_selection(c)
    r = sub.add_parser("run", help="run the tests with Gradle or Maven, then summarise")
    add_selection(r)
    add_output(r)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--timeout", type=int, default=3600)
    p = sub.add_parser("parse", help="summarise report files or folders")
    p.add_argument("paths", nargs="+")
    add_output(p)
    s = sub.add_parser("results", help="find and summarise all reports in a project")
    s.add_argument("project", nargs="?", default=".")
    add_output(s)
    a = ap.parse_args(argv)
    try:
        return {"cmd": cmd_cmd, "run": cmd_run, "parse": cmd_parse, "results": cmd_results}[a.cmd](a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
