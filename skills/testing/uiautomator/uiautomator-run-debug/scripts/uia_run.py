#!/usr/bin/env python3
"""Run Android UI Automator tests (Kotlin or Java) and explain the results.

Usage:
    python uia_run.py doctor [--serial S] [--adb PATH]
    python uia_run.py cmd  (--runner PKG/RUNNER | --test-package PKG | --gradle MODULE) [filters]
    python uia_run.py run  (--runner PKG/RUNNER | --test-package PKG) [filters] [--serial S]
                           [--out raw.txt] [--logcat logcat.txt] [--json] [--dry-run]
    python uia_run.py parse FILE [FILE ...] [--json]
    python uia_run.py results PROJECT_DIR [--json]

Filters (AndroidJUnitRunner arguments): --class C[,C2#method] --package-filter P --size small|medium|large
  --annotation A --not-annotation A --shards N --shard-index I --debug --log-only --arg KEY=VALUE
  Gradle only: --variant debug (default)

doctor   finds adb, lists devices and the installed instrumentations (pm list instrumentation).
cmd      prints the adb or Gradle command for the chosen tests, nothing is run.
run      runs `adb shell am instrument -w -r ...`, saves the raw output and prints a summary in which
         every failure gets a likely cause and a fix (ElementNotFoundException, StaleObjectException,
         null UiObject2, process crash, missing instrumentation, UiAutomation already connected, ...).
parse    summarises saved output: raw `am instrument -r` output, plain `am instrument` output, or JUnit
         XML written by Gradle (build/outputs/androidTest-results/...).
results  finds and summarises every JUnit XML under a project's build/outputs/androidTest-results.
Standard library only. doctor, cmd, parse and results never change the device.

Exit codes: 0 all tests passed (or nothing to run), 1 failures or errors, 2 bad usage, 3 setup problem.
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

DEFAULT_RUNNER = "androidx.test.runner.AndroidJUnitRunner"
STATUS_NAMES = {1: "started", 0: "passed", -1: "error", -2: "failed", -3: "ignored", -4: "assumption-failed"}

# (id, regex, cause, fix). The first matching rule wins, so specific rules come first.
CAUSES = [
    ("element-not-found", re.compile(r"ElementNotFoundException"),
     "onElement { } found no node matching the predicate before its timeout (10 s by default)",
     "Check the predicate: for Views viewIdResourceName is the full 'pkg:id/name' (or use "
     "simpleViewResourceName()), compare text with textAsString(), and Compose test tags need "
     "testTagsAsResourceId. Make sure the screen is really shown (dump it), or pass a longer timeoutMs."),
    ("stale-object", re.compile(r"StaleObjectException"),
     "a UiObject2 was used after its view was destroyed or redrawn (navigation, list recycling, recomposition)",
     "Look the element up again right before using it (page-object getters that call onElement / findObject "
     "each time) instead of keeping UiObject2 references across screen changes."),
    ("legacy-not-found", re.compile(r"UiObjectNotFoundException"),
     "a legacy UiSelector / UiObject did not match anything on screen",
     "Migrate to BySelector + device.wait(Until.findObject(...)) (Java) or onElement { } (Kotlin); "
     "see the uiautomator-migration skill."),
    ("null-uiobject2", re.compile(r"NullPointerException[\s\S]{0,400}(UiObject2|androidx\.test\.uiautomator)|"
                                  r"on a null object reference[\s\S]{0,200}UiObject2|"
                                  r"UiObject2[^\n]{0,120}on a null object reference|"
                                  r"Cannot invoke \"androidx\.test\.uiautomator\.UiObject2"),
     "device.findObject(By...) returned null because the element was not on screen at that moment",
     "Wait for it: UiObject2 o = device.wait(Until.findObject(sel), TIMEOUT); assertNotNull(o) (Java), or "
     "onElement { } which waits (Kotlin)."),
    ("intent-unresolved", re.compile(r"does not resolve to an activity|ActivityNotFoundException|"
                                     r"Unable to find explicit activity class"),
     "startActivity / startActivityIntent got an Intent no installed activity can handle",
     "Check the package and activity name, that the activity is exported (for another app), and that the app "
     "under test is installed. On Android 11+ add a <queries> entry for other packages."),
    ("no-launch-intent", re.compile(r"getLaunchIntentForPackage|no launch intent for|"
                                    r"Unable to launch .* no launch intent"),
     "the test could not get a launch Intent for the package",
     "Install the app under test; on Android 11+ add <queries><package android:name=\"...\"/></queries> to the "
     "androidTest manifest so the test APK can see it."),
    ("uiautomation-busy", re.compile(r"UiAutomationService .*already registered|UiAutomation not connected|"
                                     r"Cannot call disconnect\(\) while connecting|"
                                     r"Error while connecting UiAutomation"),
     "another client already holds UiAutomation (an Appium uiautomator2 server, a second test run, a stuck "
     "instrumentation)",
     "Stop the other client (for Appium: adb shell am force-stop io.appium.uiautomator2.server and "
     "io.appium.uiautomator2.server.test), wait for other runs to finish, then run again."),
    ("no-root-window", re.compile(r"Failed to get root in active window|Failed to find root|"
                                  r"waitForRootInActiveWindow|IllegalStateException: .*root"),
     "UI Automator could not read the active window (screen off, keyguard, a secure window, or the app was "
     "still starting)",
     "Wake and unlock the device before the run (adb shell input keyevent KEYCODE_WAKEUP; adb shell wm "
     "dismiss-keyguard), keep the screen on during tests, and wait for the app with waitForAppToBeVisible."),
    ("idle-timeout", re.compile(r"could not get idle state|Could not detect idle state|waitForIdle.*timed out",
                                re.I),
     "the UI never became idle (animations, video, live data) while UI Automator waited for it",
     "Avoid waitForIdle on such screens: wait for a specific element instead. Turning off animations in "
     "Developer options (or with `settings put global window_animation_scale 0` etc., after asking) also helps."),
    ("inject-events", re.compile(r"INJECT_EVENTS"),
     "input was injected into another app's window through Instrumentation (Espresso or "
     "Instrumentation.sendKeySync / type())",
     "Use UI Automator actions for other apps' windows: UiObject2.setText / click, UiDevice.pressKeyCode."),
    ("process-crashed", re.compile(r"Process crashed|shortMsg=Process crashed|Instrumentation run failed due to "
                                   r"'Process crashed"),
     "the test or app process crashed during the run, so later tests did not run",
     "Read logcat around the crash (run again with --logcat, or use the android-logcat-analyzer skill) and "
     "fix the exception first."),
    ("instrumentation-missing", re.compile(r"Unable to find instrumentation info|INSTRUMENTATION_FAILED|"
                                           r"Unable to find instrumentation target package"),
     "the test APK (or the app it targets) is not installed, or the runner name is wrong",
     "Install both APKs (./gradlew :app:installDebug :app:installDebugAndroidTest), then check the name with "
     "`uia_run.py doctor` (pm list instrumentation)."),
    ("no-tests", re.compile(r"No tests found|numtests=0|Tests run: 0\b|initializationError"),
     "no test matched the filters, or the class could not be initialised",
     "Check --class / --package-filter spelling (fully qualified, Class#method), @Test annotations, and that "
     "the class is in the test APK. initializationError usually means a bad @Rule, constructor or runner."),
    ("incomplete-run", re.compile(r"Test run failed to complete|Expected \d+ tests?, received \d+"),
     "the run stopped before every test finished (crash, timeout or the device disconnected)",
     "Look at the last test that started and at logcat; consider the Android Test Orchestrator to isolate "
     "crashes per test."),
    ("assertion", re.compile(r"AssertionError|AssertionFailedError|ComparisonFailure|expected:<"),
     "an assertion failed: the app showed something different from what the test expects",
     "Compare the expected and actual values; take a screenshot or a hierarchy dump at the failing step "
     "(device.takeScreenshot(file), device.dumpWindowHierarchy(file)) to see the real screen."),
    ("dependency-clash", re.compile(r"NoSuchMethodError[^\n]*androidx/test|NoClassDefFoundError[^\n]*androidx/test|"
                                    r"NoSuchMethodError[^\n]*androidx\.test"),
     "two versions of androidx.test / uiautomator are on the test classpath (for example one pulled in by "
     "Macrobenchmark or a library)",
     "Align the versions (./gradlew :app:dependencies --configuration debugAndroidTestRuntimeClasspath) and pin "
     "androidx.test.uiautomator:uiautomator to one version."),
    ("timeout", re.compile(r"TimeoutException|timed out", re.I),
     "something did not happen within its timeout", "Find the step that waited (stack trace) and wait for a "
     "specific condition instead of a fixed time."),
]


def classify(text: str) -> dict:
    for rid, rx, cause, fix in CAUSES:
        if rx.search(text or ""):
            return {"id": rid, "cause": cause, "fix": fix}
    return {"id": "other", "cause": "see the stack trace", "fix": "Read the first 'at' line in your test code."}


# ================================================================================ parsing
def parse_raw(text: str) -> dict:
    """Parse `am instrument -r` output."""
    tests, status, result, order = {}, {}, {}, []
    last = None
    instr_code = None
    failed_msgs = []
    for line in text.splitlines():
        if line.startswith("INSTRUMENTATION_STATUS: "):
            k, _, v = line[len("INSTRUMENTATION_STATUS: "):].partition("=")
            status[k] = v
            last = ("s", k)
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            try:
                code = int(line.split(":", 1)[1].strip())
            except ValueError:
                code = None
            cls, name = status.get("class", ""), status.get("test", "")
            key = "%s#%s" % (cls, name)
            if not (cls or name) and status.get("Error"):
                failed_msgs.append(status["Error"].strip())
            if cls or name:
                if code == 1:
                    if key not in tests:
                        order.append(key)
                    tests[key] = {"class": cls, "name": name, "status": "started", "stack": ""}
                elif code in STATUS_NAMES:
                    t = tests.setdefault(key, {"class": cls, "name": name, "status": "", "stack": ""})
                    if key not in order:
                        order.append(key)
                    t["status"] = STATUS_NAMES[code]
                    if status.get("stack"):
                        t["stack"] = status["stack"].strip()
            status, last = {}, None
        elif line.startswith("INSTRUMENTATION_RESULT: "):
            k, _, v = line[len("INSTRUMENTATION_RESULT: "):].partition("=")
            result[k] = v
            last = ("r", k)
        elif line.startswith("INSTRUMENTATION_CODE: "):
            try:
                instr_code = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
            last = None
        elif "INSTRUMENTATION_FAILED: " in line or line.startswith("INSTRUMENTATION_ABORTED: "):
            failed_msgs.append(line.strip())
            last = None
        elif last:
            target = status if last[0] == "s" else result
            target[last[1]] = target.get(last[1], "") + "\n" + line
    for t in tests.values():
        if t["status"] == "started":
            t["status"] = "incomplete"
    stream = result.get("stream", "")
    problems = []
    if result.get("shortMsg"):
        problems.append("shortMsg=%s" % result["shortMsg"].strip())
    if result.get("longMsg"):
        problems.append(result["longMsg"].strip())
    problems.extend(failed_msgs)
    m = re.search(r"Tests run: (\d+),\s+Failures: (\d+)", stream)
    return {"format": "raw", "tests": [tests[k] for k in order], "stream": stream.strip(), "problems": problems,
            "instrumentation_code": instr_code,
            "reported": {"run": int(m.group(1)), "failures": int(m.group(2))} if m else None}


def parse_plain(text: str) -> dict:
    """Best effort for `am instrument -w` output without -r."""
    tests = []
    for m in re.finditer(r"^\d+\) (\w+)\(([\w.$]+)\)\n([\s\S]*?)(?=^\d+\) |\nFAILURES!!!|\nTests run:|\Z)",
                         text, re.M):
        tests.append({"class": m.group(2), "name": m.group(1), "status": "failed", "stack": m.group(3).strip()})
    problems = [l.strip() for l in text.splitlines() if l.startswith("INSTRUMENTATION_") or "Process crashed" in l]
    ok = re.search(r"^OK \((\d+) tests?\)", text, re.M)
    fail = re.search(r"Tests run: (\d+),\s+Failures: (\d+)", text)
    reported = None
    if ok:
        reported = {"run": int(ok.group(1)), "failures": 0}
    elif fail:
        reported = {"run": int(fail.group(1)), "failures": int(fail.group(2))}
    return {"format": "plain", "tests": tests, "stream": "", "problems": problems, "instrumentation_code": None,
            "reported": reported}


def parse_junit(path: str) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = []
    for s in suites:
        for tc in s.iter("testcase"):
            st, stack = "passed", ""
            for child in tc:
                if child.tag in ("failure", "error"):
                    st = "failed" if child.tag == "failure" else "error"
                    stack = ((child.get("message") or "") + "\n" + (child.text or "")).strip()
                elif child.tag == "skipped":
                    st = "ignored"
            tests.append({"class": tc.get("classname", ""), "name": tc.get("name", ""), "status": st, "stack": stack,
                          "time": tc.get("time")})
    device = ""
    for s in suites:
        for p in s.iter("property"):
            if p.get("name") in ("device", "deviceName"):
                device = p.get("value", "")
    return {"format": "junit", "tests": tests, "stream": "", "problems": [], "instrumentation_code": None,
            "reported": None, "device": device, "file": path}


def parse_any(path: str) -> dict:
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    head = text.lstrip()[:200]
    if head.startswith("<?xml") or head.startswith("<testsuite"):
        return parse_junit(path)
    if "INSTRUMENTATION_STATUS" in text or "INSTRUMENTATION_RESULT" in text:
        return parse_raw(text)
    return parse_plain(text)


def summarise(rep: dict) -> dict:
    counts = {}
    for t in rep["tests"]:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    failures = []
    for t in rep["tests"]:
        if t["status"] in ("failed", "error", "incomplete"):
            text = t["stack"] or ("incomplete: the run stopped during this test " + " ".join(rep["problems"]))
            c = classify(text)
            first = next((l.strip() for l in text.splitlines() if l.strip()), "")
            failures.append({"test": "%s#%s" % (t["class"], t["name"]), "status": t["status"],
                             "message": first[:300], "cause_id": c["id"], "cause": c["cause"], "fix": c["fix"],
                             "test_frame": test_frame(text)})
    run_problems = []
    joined = "\n".join(rep["problems"])
    if joined:
        c = classify(joined)
        run_problems.append({"message": joined[:500], "cause_id": c["id"], "cause": c["cause"], "fix": c["fix"]})
    if not rep["tests"] and not run_problems:
        c = classify("No tests found")
        run_problems.append({"message": "no test results in the output", "cause_id": c["id"], "cause": c["cause"],
                             "fix": c["fix"]})
    rep["counts"], rep["failures"], rep["run_problems"] = counts, failures, run_problems
    rep["ok"] = not failures and not run_problems
    return rep


def test_frame(stack: str) -> str:
    """First stack frame outside android / androidx / java / kotlin / junit: usually the test line."""
    for line in stack.splitlines():
        m = re.match(r"\s*at ([\w.$]+)\.([\w$<>]+)\(([^)]*)\)", line)
        if not m:
            continue
        owner = m.group(1)
        if re.match(r"(android|androidx|java|javax|kotlin|kotlinx|junit|org\.junit|dalvik|com\.android\.internal|"
                    r"sun|jdk)\.", owner):
            continue
        return "%s.%s(%s)" % (owner, m.group(2), m.group(3))
    return ""


def print_summary(rep: dict, label: str = "") -> None:
    c = rep["counts"]
    total = sum(c.values())
    if label:
        print("== %s (%s)" % (label, rep["format"]))
    print("tests: %d  passed: %d  failed: %d  errors: %d  ignored: %d  incomplete: %d" %
          (total, c.get("passed", 0), c.get("failed", 0), c.get("error", 0),
           c.get("ignored", 0) + c.get("assumption-failed", 0), c.get("incomplete", 0)))
    if rep.get("reported") and rep["reported"]["run"] != total and rep["format"] == "raw":
        print("note: the runner reported %d tests run" % rep["reported"]["run"])
    for p in rep["run_problems"]:
        print("\nRUN PROBLEM [%s] %s" % (p["cause_id"], p["message"].splitlines()[0]))
        print("  cause: %s" % p["cause"])
        print("  fix:   %s" % p["fix"])
    for f in rep["failures"]:
        print("\n%s %s [%s]" % (f["status"].upper(), f["test"], f["cause_id"]))
        print("  message: %s" % f["message"])
        if f["test_frame"]:
            print("  at:      %s" % f["test_frame"])
        print("  cause:   %s" % f["cause"])
        print("  fix:     %s" % f["fix"])
    if rep["ok"]:
        print("All tests passed.")


# ================================================================================ commands
def runner_args(a) -> list:
    args = []

    def e(k, v):
        args.extend(["-e", k, str(v)])
    if a.cls:
        e("class", a.cls)
    if a.package_filter:
        e("package", a.package_filter)
    if a.size:
        e("size", a.size)
    if a.annotation:
        e("annotation", a.annotation)
    if a.not_annotation:
        e("notAnnotation", a.not_annotation)
    if a.shards:
        if a.shard_index is None or not 0 <= a.shard_index < a.shards:
            raise SystemExit("error: --shards needs --shard-index between 0 and %d" % (a.shards - 1))
        e("numShards", a.shards)
        e("shardIndex", a.shard_index)
    if a.debug:
        e("debug", "true")
    if a.log_only:
        e("log", "true")
    for kv in a.arg or []:
        if "=" not in kv:
            raise SystemExit("error: --arg needs KEY=VALUE, got %r" % kv)
        k, v = kv.split("=", 1)
        e(k, v)
    return args


def runner_name(a) -> str:
    if a.runner:
        if "/" not in a.runner:
            raise SystemExit("error: --runner needs <test.package>/<RunnerClass>, e.g. "
                             "com.example.app.test/%s" % DEFAULT_RUNNER)
        return a.runner
    if a.test_package:
        return "%s/%s" % (a.test_package, DEFAULT_RUNNER)
    raise SystemExit("error: pass --runner PKG/RUNNER or --test-package PKG (see `uia_run.py doctor`)")


def gradle_command(a) -> list:
    mod = a.gradle if a.gradle.startswith(":") else ":" + a.gradle
    variant = (a.variant or "debug")
    task = "%s:connected%s%sAndroidTest" % (mod, variant[:1].upper(), variant[1:])
    gw = "gradlew.bat" if os.name == "nt" else "./gradlew"
    cmd = [gw, task]
    pairs = runner_args(a)
    for i in range(0, len(pairs), 3):
        cmd.append("-Pandroid.testInstrumentationRunnerArguments.%s=%s" % (pairs[i + 1], pairs[i + 2]))
    return cmd


def adb_command(adb: str, serial: str, a) -> list:
    """adb argv; the device command is one string, quoted for the device shell."""
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    shell = ["am", "instrument", "-w", "-r"] + runner_args(a) + [runner_name(a)]
    return cmd + ["shell", " ".join(shlex.quote(x) for x in shell)]


def show(cmd: list) -> str:
    """Readable command line: the device command after `shell` is shown unwrapped."""
    if "shell" in cmd:
        i = cmd.index("shell")
        return " ".join(shlex.quote(x) for x in cmd[:i + 1]) + " " + " ".join(cmd[i + 1:])
    return " ".join(shlex.quote(x) for x in cmd)


def find_adb(explicit: str = "") -> str:
    for c in (explicit, os.environ.get("ADB", "")):
        if c:
            return c
    p = shutil.which("adb")
    if p:
        return p
    roots = [os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", ""),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
             os.path.expanduser("~/Library/Android/sdk"), os.path.expanduser("~/Android/Sdk"), r"C:\Android\Sdk"]
    for r in roots:
        if not r:
            continue
        for name in ("adb.exe", "adb"):
            cand = os.path.join(r, "platform-tools", name)
            if os.path.isfile(cand):
                return cand
    return ""


def adb_argv(adb: str) -> list:
    return [sys.executable, adb] if adb.endswith(".py") else [adb]


def run_adb(adb: str, args: list, timeout: int = 60) -> tuple:
    try:
        p = subprocess.run(adb_argv(adb) + args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "adb not found: %s" % adb
    except subprocess.TimeoutExpired:
        return 124, "", "adb timed out after %d s" % timeout


def devices(adb: str) -> list:
    rc, out, err = run_adb(adb, ["devices"])
    if rc != 0:
        return []
    res = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            res.append((parts[0], parts[1]))
    return res


def pick_serial(adb: str, serial: str) -> str:
    serial = serial or os.environ.get("ANDROID_SERIAL", "")
    devs = devices(adb)
    ready = [s for s, st in devs if st == "device"]
    if serial:
        if serial not in ready:
            states = dict(devs)
            raise SetupError("device %s is %s" % (serial, states.get(serial, "not connected")))
        return serial
    if not ready:
        bad = ", ".join("%s (%s)" % d for d in devs) or "none"
        raise SetupError("no device ready (seen: %s). Connect a device or start an emulator; accept the USB "
                         "debugging prompt if it shows 'unauthorized'" % bad)
    if len(ready) > 1:
        raise SetupError("several devices are connected (%s): pass --serial" % ", ".join(ready))
    return ready[0]


class SetupError(Exception):
    pass


def cmd_doctor(a) -> int:
    adb = find_adb(a.adb)
    if not adb:
        print("adb: not found. Install Android SDK Platform-Tools, put it on PATH, or pass --adb (or set ADB).")
        return 3
    rc, out, _ = run_adb(adb, ["version"])
    print("adb: %s (%s)" % (adb, out.splitlines()[0] if rc == 0 and out else "version unknown"))
    devs = devices(adb)
    if not devs:
        print("devices: none")
        return 3
    for s, st in devs:
        print("device: %s %s" % (s, st))
    try:
        serial = pick_serial(adb, a.serial)
    except SetupError as e:
        print("problem: %s" % e)
        return 3
    rc, out, err = run_adb(adb, ["-s", serial, "shell", "pm", "list", "instrumentation"])
    rows = [l[len("instrumentation:"):].strip() for l in out.splitlines() if l.startswith("instrumentation:")]
    print("\ninstrumentations on %s (%d):" % (serial, len(rows)))
    for r in rows:
        print("  " + r)
    if not rows:
        print("  none: install the test APK (./gradlew :app:installDebugAndroidTest)")
    rc, out, _ = run_adb(adb, ["-s", serial, "shell", "settings", "get", "global", "animator_duration_scale"])
    if rc == 0 and out.strip() not in ("", "null", "0", "0.0"):
        print("\nnote: animations are on (animator_duration_scale=%s). They slow tests and can stop the UI from "
              "becoming idle; turn them off in Developer options if tests are flaky." % out.strip())
    return 0


def cmd_cmd(a) -> int:
    if a.gradle:
        print(" ".join(shlex.quote(x) for x in gradle_command(a)))
        return 0
    adb = find_adb(a.adb) or "adb"
    print(show(adb_command(adb, a.serial, a)))
    return 0


def cmd_run(a) -> int:
    adb = find_adb(a.adb)
    if not adb:
        print("error: adb not found (install Platform-Tools, or pass --adb)", file=sys.stderr)
        return 3
    if a.dry_run:
        print(show(adb_command(adb, a.serial or "<serial>", a)))
        return 0
    try:
        serial = pick_serial(adb, a.serial)
    except SetupError as e:
        print("error: %s" % e, file=sys.stderr)
        return 3
    full = adb_command(adb, serial, a)
    print("running: " + show(full), file=sys.stderr)
    rc, out, err = run_adb(adb, full[1:], timeout=a.timeout)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("raw output saved to %s" % a.out, file=sys.stderr)
    if a.logcat:
        _rc, lout, _ = run_adb(adb, ["-s", serial, "logcat", "-d", "-v", "threadtime"], timeout=120)
        with open(a.logcat, "w", encoding="utf-8") as fh:
            fh.write(lout)
        print("logcat saved to %s" % a.logcat, file=sys.stderr)
    if rc == 124:
        print("error: %s" % err, file=sys.stderr)
    rep = parse_raw(out) if "INSTRUMENTATION_" in out else parse_plain(out + "\n" + err)
    if err.strip() and "INSTRUMENTATION_" not in out:
        rep["problems"].append(err.strip())
    rep = summarise(rep)
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        print_summary(rep)
    return 0 if rep["ok"] else 1


def cmd_parse(a) -> int:
    reps = []
    for f in a.files:
        if not os.path.isfile(f):
            print("error: %s not found" % f, file=sys.stderr)
            return 2
        try:
            reps.append((f, summarise(parse_any(f))))
        except ET.ParseError as e:
            print("error: %s is not valid XML: %s" % (f, e), file=sys.stderr)
            return 2
    return emit(reps, a.json)


def cmd_results(a) -> int:
    pattern = os.path.join(a.project, "**", "build", "outputs", "androidTest-results", "**", "*.xml")
    files = sorted(f for f in glob.glob(pattern, recursive=True) if os.path.basename(f).startswith("TEST-"))
    if not files:
        print("no JUnit XML under %s/**/build/outputs/androidTest-results (run connectedAndroidTest first)"
              % a.project)
        return 2
    reps = []
    for f in files:
        try:
            reps.append((os.path.relpath(f, a.project).replace(os.sep, "/"), summarise(parse_junit(f))))
        except ET.ParseError:
            continue
    return emit(reps, a.json)


def emit(reps: list, as_json: bool) -> int:
    if as_json:
        print(json.dumps([dict(r, source=f) for f, r in reps], indent=2))
    else:
        for i, (f, r) in enumerate(reps):
            if i:
                print()
            print_summary(r, f)
        if len(reps) > 1:
            tot = sum(sum(r["counts"].values()) for _, r in reps)
            bad = sum(len(r["failures"]) for _, r in reps)
            print("\nTotal: %d tests in %d files, %d failing" % (tot, len(reps), bad))
    return 0 if all(r["ok"] for _, r in reps) else 1


def add_filters(p, gradle: bool) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--runner", help="test.package/RunnerClass (see doctor)")
    g.add_argument("--test-package", help="test APK package; the runner defaults to " + DEFAULT_RUNNER)
    if gradle:
        g.add_argument("--gradle", metavar="MODULE", help="print a Gradle command for this module (e.g. app)")
        p.add_argument("--variant", default="debug", help="build variant for --gradle (default debug)")
    p.add_argument("--class", dest="cls", help="fully qualified class, Class#method, comma separated")
    p.add_argument("--package-filter", help="Java package of the tests to run")
    p.add_argument("--size", choices=["small", "medium", "large"])
    p.add_argument("--annotation", help="run only tests with this annotation (fully qualified)")
    p.add_argument("--not-annotation", help="skip tests with this annotation (fully qualified)")
    p.add_argument("--shards", type=int, help="split the tests into N shards")
    p.add_argument("--shard-index", type=int, help="which shard to run (0-based)")
    p.add_argument("--debug", action="store_true", help="wait for a debugger (-e debug true)")
    p.add_argument("--log-only", action="store_true", help="list the tests without running them (-e log true)")
    p.add_argument("--arg", action="append", metavar="KEY=VALUE", help="any other runner argument")
    p.add_argument("--serial", default="", help="device serial (default: the only device, or $ANDROID_SERIAL)")
    p.add_argument("--adb", default="", help="path to adb")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run UI Automator tests and explain the results.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="adb, devices and installed instrumentations")
    d.add_argument("--serial", default="")
    d.add_argument("--adb", default="")
    c = sub.add_parser("cmd", help="print the adb or Gradle command, run nothing")
    add_filters(c, gradle=True)
    r = sub.add_parser("run", help="run tests with am instrument and summarise")
    add_filters(r, gradle=False)
    r.add_argument("--out", help="save the raw output to this file")
    r.add_argument("--logcat", help="save `adb logcat -d` to this file after the run")
    r.add_argument("--json", action="store_true")
    r.add_argument("--dry-run", action="store_true", help="print the command only")
    r.add_argument("--timeout", type=int, default=3600, help="seconds before giving up (default 3600)")
    p = sub.add_parser("parse", help="summarise saved output or JUnit XML")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")
    s = sub.add_parser("results", help="summarise Gradle's androidTest JUnit XML in a project")
    s.add_argument("project")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"doctor": cmd_doctor, "cmd": cmd_cmd, "run": cmd_run, "parse": cmd_parse,
                "results": cmd_results}[a.cmd](a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
