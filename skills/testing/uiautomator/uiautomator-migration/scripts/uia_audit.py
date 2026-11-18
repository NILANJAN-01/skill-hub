#!/usr/bin/env python3
"""Audit Android UI Automator tests (Kotlin and Java) for legacy APIs, flaky patterns and build setup.

Usage:
    python uia_audit.py <project-dir-or-file> [--json] [--strict] [--rules] [--only RULE_ID ...]

Scans *.kt and *.java files (androidTest, test modules, benchmark modules) plus build.gradle,
build.gradle.kts and gradle/libs.versions.toml. Reports, with file and line:
  - legacy UI Automator APIs to migrate (UiSelector, UiObject, UiScrollable, UiCollection,
    UiAutomatorTestCase, deprecated UiDevice/Configurator methods, the old support library)
  - code written against pre-release 2.4 alphas (onView -> onElement, clearAppData("pkg"),
    startIntent -> startActivityIntent, lower-case uiautomator { })
  - flaky patterns (sleeps, fixed coordinates, findObject(...) used without a wait or null check,
    text == in predicates, viewIdResourceName compared to a short id, leaked watchers and display ids)
  - the uiautomator dependency version and the instrumentation runner.
Standard library only. Read-only: it never changes a file.

Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

LATEST_STABLE = "2.4.1"          # androidx.test.uiautomator:uiautomator, released 2026-11-04
SKIP_DIRS = {".git", ".gradle", ".idea", "build", "out", "node_modules", ".venv", "venv", "__pycache__",
             "intermediates", "generated"}
SOURCE_EXT = (".kt", ".java")
BUILD_FILES = ("build.gradle", "build.gradle.kts")

# (id, level, langs, regex, message, fix). langs: "kt", "java" or "both".
RULES = [
    # --- legacy / removed APIs ------------------------------------------------------------------
    ("support-library", "ERROR", "both", re.compile(r"\bandroid\.support\.test\.uiautomator\b"),
     "old Android Support Library UI Automator (android.support.test.uiautomator)",
     "depend on androidx.test.uiautomator:uiautomator:%s and change imports to androidx.test.uiautomator" % LATEST_STABLE),
    ("uiautomator-jar", "ERROR", "both", re.compile(r"\bimport\s+com\.android\.uiautomator\."),
     "UI Automator 1.0 (uiautomator.jar, UiAutomatorTestCase run with `uiautomator runtest`)",
     "rewrite as an instrumented JUnit4 test with androidx.test.uiautomator and AndroidJUnitRunner"),
    ("test-case", "ERROR", "both", re.compile(r"\bUiAutomatorTestCase\b"),
     "UiAutomatorTestCase is deprecated and no longer needed",
     "write a plain JUnit4 class annotated @RunWith(AndroidJUnit4::class) and get UiDevice in @Before (or use uiAutomator { })"),
    ("test-runner", "ERROR", "both", re.compile(r"\bUiAutomatorInstrumentationTestRunner\b"),
     "UiAutomatorInstrumentationTestRunner is deprecated (it only runs UiAutomatorTestCase)",
     "set testInstrumentationRunner = \"androidx.test.runner.AndroidJUnitRunner\""),
    ("device-getinstance-noarg", "ERROR", "both", re.compile(r"\bUiDevice\.getInstance\(\s*\)"),
     "UiDevice.getInstance() without an Instrumentation is deprecated",
     "UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()), or use `device` inside uiAutomator { }"),
    ("compressed-typo", "WARN", "both", re.compile(r"\bsetCompressedLayoutHeirarchy\s*\("),
     "setCompressedLayoutHeirarchy (typo) is deprecated", "setCompressedLayoutHierarchy(...)"),
    ("current-activity", "WARN", "both", re.compile(r"\b(getCurrentActivityName\s*\(|\.currentActivityName\b)"),
     "UiDevice.getCurrentActivityName() is deprecated and unreliable",
     "check the package with getCurrentPackageName() / waitForAppToBeVisible(), or an element of the screen"),
    ("dump-string", "WARN", "both", re.compile(r"\bdumpWindowHierarchy\s*\(\s*\""),
     "dumpWindowHierarchy(String) is deprecated", "dumpWindowHierarchy(File) or dumpWindowHierarchy(OutputStream)"),
    ("key-injection-delay", "WARN", "both", re.compile(r"\b(set|get)KeyInjectionDelay\s*\(|\.keyInjectionDelay\b"),
     "Configurator key injection delay is deprecated and has no effect (text is set directly)",
     "remove the call"),
    ("ui-selector", "WARN", "both", re.compile(r"\bUiSelector\s*\(\s*\)"),
     "UiSelector (legacy API, being deprecated)",
     "Java: By.res/text/desc/clazz (BySelector) with device.findObject / device.wait(Until.findObject(...)); "
     "Kotlin: onElement { ... }"),
    ("ui-object", "WARN", "both", re.compile(r"\bUiObject\b(?!2|NotFound)"),
     "UiObject (legacy API, being deprecated)", "UiObject2 from findObject(BySelector), or onElement { ... } in Kotlin"),
    ("ui-scrollable", "WARN", "both", re.compile(r"\bUiScrollable\b"),
     "UiScrollable (legacy API, being deprecated)",
     "scrollable.scrollUntil(Direction.DOWN, Until.findObject(selector)); Kotlin: onElement { isScrollable }"
     ".scrollToElement(Direction.DOWN) { ... }"),
    ("ui-collection", "WARN", "both", re.compile(r"\bUiCollection\b"),
     "UiCollection (legacy API, being deprecated)", "parent.findObjects(selector) / onElements { ... }"),
    ("not-found-exception", "INFO", "both", re.compile(r"\bUiObjectNotFoundException\b"),
     "UiObjectNotFoundException belongs to the legacy UiObject API",
     "UiObject2 lookups return null (Java) and onElement throws ElementNotFoundException (Kotlin)"),
    ("old-junit4-runner", "WARN", "both", re.compile(r"\bandroidx\.test\.runner\.AndroidJUnit4\b"),
     "androidx.test.runner.AndroidJUnit4 is deprecated", "import androidx.test.ext.junit.runners.AndroidJUnit4"),
    ("register-watcher", "INFO", "kt", re.compile(r"\bregisterWatcher\s*\("),
     "UiDevice.registerWatcher in Kotlin", "inside uiAutomator { } use watchFor(PermissionDialog) { clickAllow() } "
     "or a custom ScopedUiWatcher; it is unregistered when the block ends"),
    ("wait-for-idle", "INFO", "both", re.compile(r"\bwaitForIdle\s*\("),
     "waitForIdle() waits for the whole UI to be idle, which some screens (animations, video) never are",
     "Kotlin: rely on onElement's timeout or activeWindow().waitForStable(); Java: device.wait(Until.hasObject(...), t)"),
    ("shell-command", "INFO", "both", re.compile(r"\bexecuteShellCommand\s*\("),
     "UiDevice.executeShellCommand is public but discouraged",
     "keep it for setup/teardown only; prefer startApp/startActivity, clearAppData() or Intent APIs"),
    # --- pre-release 2.4 alphas ------------------------------------------------------------------
    ("dsl-onview", "ERROR", "kt", re.compile(r"\bonView(s|OrNull)?\s*(\(\s*[\w_]*\s*\)\s*)?\{"),
     "onView { } / onViews { } were renamed to onElement { } / onElements { } in 2.4.0-alpha04",
     "rename to onElement / onElements / onElementOrNull"),
    ("dsl-lowercase", "ERROR", "kt", re.compile(r"\buiautomator\s*\{"),
     "the entry point is uiAutomator { } (capital A); uiautomator { } does not compile",
     "uiAutomator { ... }"),
    ("dsl-clear-app-data-arg", "WARN", "kt", re.compile(r"\bclearAppData\s*\(\s*[^)\s]"),
     "in 2.4.1 UiAutomatorTestScope.clearAppData() takes no argument and clears the instrumentation target app",
     "clearAppData(); for another package run `pm clear <pkg>` from the host (adb) before the test"),
    ("dsl-start-intent", "WARN", "kt", re.compile(r"(?<![\w.])startIntent\s*\("),
     "the 2.4.1 scope method is startActivityIntent(intent) (the guide's startIntent does not exist)",
     "startActivityIntent(intent)"),
    ("permission-import", "ERROR", "kt", re.compile(r"\bimport\s+androidx\.test\.uiautomator\.PermissionDialog\b"),
     "PermissionDialog lives in the watcher package", "import androidx.test.uiautomator.watcher.PermissionDialog"),
    # --- flaky patterns --------------------------------------------------------------------------
    ("sleep", "WARN", "both", re.compile(r"\b(Thread\.sleep|SystemClock\.sleep|TimeUnit\.\w+\.sleep)\s*\("),
     "hard sleep: slow when the UI is fast and flaky when it is slow",
     "wait for a condition: onElement(timeoutMs) { ... }, device.wait(Until.hasObject(sel), t), "
     "obj.wait(Until.textEquals(...), t), clickAndWait(Until.newWindow(), t)"),
    ("coordinates", "WARN", "both", re.compile(r"\b(device|uiDevice|mDevice)\.(click|swipe|drag)\s*\(\s*\d+\s*,\s*\d+"),
     "fixed screen coordinates break on other screen sizes, densities and orientations",
     "find the element and act on it (obj.click(), obj.swipe(Direction.UP, 0.8f), obj.drag(point))"),
    ("findobject-chain", "WARN", "both",
     re.compile(r"\bfindObject\s*\(\s*By\.[^;]*?\)\s*\)\s*[!?]*\s*\.\s*(click|longClick|setText|clear|getText|text|"
                r"swipe|scroll|fling|drag|isChecked|isEnabled)\b"),
     "findObject(By...) returns null when the element is not on screen yet; chaining a call can throw NPE",
     "Java: UiObject2 o = device.wait(Until.findObject(sel), TIMEOUT); assertNotNull(o); "
     "Kotlin: onElement { ... } (waits and throws ElementNotFoundException with a clear message)"),
    ("predicate-text", "WARN", "kt",
     re.compile(r"\b(onElement|onElements|onElementOrNull|scrollToElement|scrollToElementOrNull)\b[^{\n]*\{[^}\n]*"
                r"(?<![\w.])text\s*(==|!=)"),
     "AccessibilityNodeInfo.text is a CharSequence (may be a SpannableString), so == \"...\" can be false",
     "textAsString() == \"...\" (the library's lint check suggests the same)"),
    ("predicate-desc", "INFO", "kt",
     re.compile(r"\b(onElement|onElements|onElementOrNull|scrollToElement|scrollToElementOrNull)\b[^{\n]*\{[^}\n]*"
                r"(?<![\w.])contentDescription\s*(==|!=)\s*\""),
     "contentDescription is a CharSequence", "contentDescription?.toString() == \"...\""),
    ("predicate-short-id", "WARN", "kt", re.compile(r"\bviewIdResourceName\s*==\s*\"(?![^\"]*:id/)[^\"]+\""),
     "viewIdResourceName is the full id (\"com.app:id/name\") for Views; a short value only matches a Compose "
     "testTag exposed with testTagsAsResourceId",
     "for Views: simpleViewResourceName() == \"name\" or viewIdResourceName == \"com.app:id/name\""),
]

TEST_TAG_RES = re.compile(r"\bBy\.res\(\s*\"[^\"]+\"\s*,\s*\"")
DSL_USE = re.compile(r"\b(uiAutomator\s*\{|onElement(s|OrNull)?\s*(\([^)]*\))?\s*\{|watchFor\s*\(|waitForStable\s*\()")
CONFIG_SET = re.compile(r"\bset(WaitForIdleTimeout|WaitForSelectorTimeout|ActionAcknowledgmentTimeout|"
                        r"ScrollAcknowledgmentTimeout|ToolType|UiAutomationFlags)\s*\(")
DEP_RE = re.compile(r"""["'](?:androidx\.test\.uiautomator|com\.android\.support\.test\.uiautomator):"""
                    r"""(uiautomator(?:-v18)?)(?::([^"'$\s]+))?["']""")
TOML_COORD = re.compile(r"""androidx\.test\.uiautomator:uiautomator|group\s*=\s*["']androidx\.test\.uiautomator["']\s*,"""
                        r"""\s*name\s*=\s*["']uiautomator["']""")
RUNNER_RE = re.compile(r"""testInstrumentationRunner\s*(?:=|\s)\s*["']([^"']+)["']""")


def parse_version(v: str):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(\d+))?$", v.strip())
    if not m:
        return None
    rank = {"alpha": 0, "beta": 1, "rc": 2, None: 3}[m.group(4)]
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), rank, int(m.group(5) or 0))


def strip_line(line: str, state: dict) -> str:
    """Remove comments (// and /* */) and string contents are kept. state carries 'in_block'."""
    out, i, n = [], 0, len(line)
    in_str = None
    while i < n:
        if state["in_block"]:
            end = line.find("*/", i)
            if end < 0:
                return "".join(out)
            state["in_block"], i = False, end + 2
            continue
        c = line[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(line[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in "\"'":
            in_str = c
            out.append(c)
            i += 1
            continue
        if line.startswith("//", i):
            break
        if line.startswith("/*", i):
            state["in_block"] = True
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def rel(path: str, root: str) -> str:
    r = os.path.relpath(path, root) if os.path.isdir(root) else os.path.basename(path)
    return r.replace(os.sep, "/")


def iter_files(root: str):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            yield os.path.join(dirpath, f)


def read(path: str) -> str:
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def is_test_source(path: str, text: str) -> bool:
    p = path.replace("\\", "/")
    if "/androidTest/" in p or "/test/" in p or "benchmark" in p.lower() or "baselineprofile" in p.lower():
        return True
    return "androidx.test.uiautomator" in text or "android.support.test.uiautomator" in text \
        or "com.android.uiautomator" in text


def audit(root: str, only: set | None = None) -> dict:
    findings, files_scanned = [], 0
    langs, usage = Counter(), Counter()
    sources = []
    builds = []
    tomls = []
    for path in iter_files(root):
        name = os.path.basename(path)
        if name.endswith(SOURCE_EXT):
            text = read(path)
            if is_test_source(path, text):
                sources.append((path, text))
        elif name in BUILD_FILES:
            builds.append((path, read(path)))
        elif name == "libs.versions.toml":
            tomls.append((path, read(path)))
    if not sources and not builds and not tomls:
        return {"root": root, "files": 0, "findings": [], "error": "no Kotlin/Java test sources or Gradle files found"}

    # testTagsAsResourceId is set in app code (not test code), so look at every source file.
    project_uses_test_tags = any("testTagsAsResourceId" in t for _, t in sources) or \
        any("testTagsAsResourceId" in t for _, t in _all_sources(root))
    uses_dsl = False

    def add(rule_id, level, path, line_no, msg, fix, code=""):
        if only and rule_id not in only:
            return
        findings.append({"rule": rule_id, "level": level, "file": rel(path, root), "line": line_no, "message": msg, "fix": fix,
                         "code": code.strip()[:160]})

    for path, text in sources:
        files_scanned += 1
        lang = "kt" if path.endswith(".kt") else "java"
        langs[lang] += 1
        state = {"in_block": False}
        file_has = {"registerWatcher": False, "removeWatcher": False, "setDefaultDisplayId": False,
                    "resetDefaultDisplayId": False, "config_set": [], "config_get": False}
        for no, raw in enumerate(text.splitlines(), 1):
            line = strip_line(raw, state)
            if not line.strip():
                continue
            if DSL_USE.search(line):
                usage["modern-dsl"] += 1
                uses_dsl = True
            if re.search(r"\bBy\.\w+\s*\(", line):
                usage["by-selector"] += 1
            if re.search(r"\bUiSelector\s*\(", line):
                usage["ui-selector"] += 1
            for rid, level, rl, rx, msg, fix in RULES:
                if rl != "both" and rl != lang:
                    continue
                if rx.search(line):
                    if rid == "predicate-short-id" and project_uses_test_tags:
                        level = "INFO"           # short ids are expected for Compose test tags
                    add(rid, level, path, no, msg, fix, raw)
            if project_uses_test_tags and TEST_TAG_RES.search(line):
                add("res-two-args-compose", "WARN", path, no,
                    "this project uses testTagsAsResourceId: By.res(pkg, id) builds \"pkg:id/id\", which never matches a "
                    "Compose testTag", "By.res(\"tag\") with the testTag as the whole resource name", raw)
            if "registerWatcher" in line:
                file_has["registerWatcher"] = file_has["registerWatcher"] or no
            if "removeWatcher" in line or "resetWatcherTriggers" in line:
                file_has["removeWatcher"] = True
            if "setDefaultDisplayId" in line:
                file_has["setDefaultDisplayId"] = file_has["setDefaultDisplayId"] or no
            if "resetDefaultDisplayId" in line:
                file_has["resetDefaultDisplayId"] = True
            m = CONFIG_SET.search(line)
            if m and "Configurator" in text:
                file_has["config_set"].append((no, m.group(1)))
            if re.search(r"\bget(WaitForIdleTimeout|WaitForSelectorTimeout|ActionAcknowledgmentTimeout|"
                         r"ScrollAcknowledgmentTimeout|ToolType|UiAutomationFlags)\s*\(|\.(waitForIdleTimeout|"
                         r"waitForSelectorTimeout|actionAcknowledgmentTimeout|scrollAcknowledgmentTimeout|toolType|"
                         r"uiAutomationFlags)\b(?!\s*=)", line):
                file_has["config_get"] = True
        if lang == "java" and file_has["registerWatcher"] and not file_has["removeWatcher"]:
            add("watcher-leak", "WARN", path, file_has["registerWatcher"],
                "registerWatcher without removeWatcher: the watcher keeps running in later tests",
                "device.removeWatcher(NAME) in @After")
        if file_has["setDefaultDisplayId"] and not file_has["resetDefaultDisplayId"]:
            add("display-id-leak", "WARN", path, file_has["setDefaultDisplayId"],
                "Configurator.setDefaultDisplayId without resetDefaultDisplayId affects later tests",
                "Configurator.getInstance().resetDefaultDisplayId() in @After / finally")
        if file_has["config_set"] and not file_has["config_get"]:
            no, param = file_has["config_set"][0]
            add("configurator-restore", "INFO", path, no,
                "Configurator.set%s without saving the old value: the change leaks into other tests" % param,
                "save the original value and restore it in @After (Configurator is a process-wide singleton)")

    # --- build files -----------------------------------------------------------------------------
    versions = []
    for path, text in builds:
        st = {"in_block": False}
        for no, raw in enumerate(text.splitlines(), 1):
            line = strip_line(raw, st)
            m = DEP_RE.search(line)
            if m:
                versions.append((path, no, m.group(2) or "", "support" if "support" in line else "androidx", raw))
            r = RUNNER_RE.search(line)
            if r and r.group(1) not in ("androidx.test.runner.AndroidJUnitRunner",) and \
                    "UiAutomatorInstrumentationTestRunner" not in r.group(1):
                add("custom-runner", "INFO", path, no, "custom instrumentation runner %s" % r.group(1),
                    "fine if it extends androidx.test.runner.AndroidJUnitRunner", raw)
            elif r and "UiAutomatorInstrumentationTestRunner" in r.group(1):
                add("test-runner", "ERROR", path, no, "deprecated UiAutomatorInstrumentationTestRunner",
                    "testInstrumentationRunner = \"androidx.test.runner.AndroidJUnitRunner\"", raw)
    for tpath, ttext in tomls:
        toml_versions, sect = {}, None
        lines = ttext.splitlines()
        for raw in lines:
            st_ = raw.strip()
            if st_.startswith("["):
                sect = st_.strip("[]").strip()
            elif sect == "versions":
                mv = re.match(r"""([\w.-]+)\s*=\s*["']([^"']+)["']""", st_)
                if mv:
                    toml_versions[mv.group(1)] = mv.group(2)
        for no, raw in enumerate(lines, 1):
            if not TOML_COORD.search(raw) or raw.strip().startswith("#"):
                continue
            ver = ""
            m = re.search(r"""version\.ref\s*=\s*["']([^"']+)["']""", raw)
            if m:
                ver = toml_versions.get(m.group(1), "")
            else:
                m = (re.search(r"""version\s*=\s*["']([^"']+)["']""", raw)
                     or re.search(r"""uiautomator:uiautomator:([^"'\s]+)["']""", raw))
                ver = m.group(1) if m else ""
            versions.append((tpath, no, ver, "androidx", raw))

    dep_report = []
    for path, no, ver, kind, raw in versions:
        dep_report.append({"file": rel(path, root), "line": no, "version": ver or "?", "kind": kind})
        absp = path
        if kind == "support":
            add("support-library", "ERROR", absp, no, "com.android.support.test.uiautomator dependency",
                "androidTestImplementation(\"androidx.test.uiautomator:uiautomator:%s\")" % LATEST_STABLE, raw)
            continue
        pv = parse_version(ver) if ver else None
        if pv is None:
            continue
        latest = parse_version(LATEST_STABLE)
        if pv[:3] == (2, 4, 0) and pv[3] < 3:
            add("prerelease-version", "WARN", absp, no,
                "pre-release uiautomator %s: APIs were renamed before 2.4.0 (onView -> onElement in alpha04, "
                "implicit-package APIs removed in alpha07, scrollToElementOrNull fixed in beta02)" % ver,
                "use %s (stable)" % LATEST_STABLE, raw)
        elif pv < (2, 4, 0, 0, 0):
            level = "ERROR" if uses_dsl else "INFO"
            add("old-version", level, absp, no,
                "uiautomator %s has no uiAutomator { } / onElement DSL (added in 2.4.0)%s" %
                (ver, "; this project uses it, so it does not compile" if uses_dsl else ""),
                "upgrade to %s" % LATEST_STABLE, raw)
        elif pv < latest:
            add("newer-patch", "INFO", absp, no, "uiautomator %s; %s is the latest stable" % (ver, LATEST_STABLE),
                "upgrade to %s (fixes ShellServer port collisions)" % LATEST_STABLE, raw)

    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (order[f["level"]], f["file"], f["line"]))
    levels = Counter(f["level"] for f in findings)
    return {"root": root, "files": files_scanned, "languages": dict(langs), "usage": dict(usage),
            "dependencies": dep_report, "findings": findings, "counts": dict(levels),
            "by_rule": dict(Counter(f["rule"] for f in findings))}


def _all_sources(root: str):
    if not os.path.isdir(root):
        return []
    out = []
    for path in iter_files(root):
        if path.endswith(SOURCE_EXT):
            try:
                out.append((path, read(path)))
            except OSError:
                pass
    return out


def print_report(rep: dict) -> None:
    print("UI Automator audit: %s" % rep["root"])
    langs = rep.get("languages", {})
    print("  test sources: %d (Kotlin %d, Java %d)" % (rep["files"], langs.get("kt", 0), langs.get("java", 0)))
    u = rep.get("usage", {})
    print("  API mix: modern DSL %d, By selectors %d, UiSelector %d" %
          (u.get("modern-dsl", 0), u.get("by-selector", 0), u.get("ui-selector", 0)))
    for d in rep.get("dependencies", []):
        print("  dependency: uiautomator %s (%s%s)" % (d["version"], d["file"], (":%d" % d["line"]) if d["line"] else ""))
    if not rep.get("dependencies"):
        print("  dependency: androidx.test.uiautomator:uiautomator not found in Gradle files")
    print()
    if not rep["findings"]:
        print("No findings.")
    for f in rep["findings"]:
        loc = "%s:%d" % (f["file"], f["line"]) if f["line"] else f["file"]
        print("%-5s %s [%s] %s" % (f["level"], loc, f["rule"], f["message"]))
        if f.get("code"):
            print("      code: %s" % f["code"])
        print("      fix:  %s" % f["fix"])
    c = rep.get("counts", {})
    print()
    print("Summary: %d error(s), %d warning(s), %d info" % (c.get("ERROR", 0), c.get("WARN", 0), c.get("INFO", 0)))
    if rep.get("by_rule"):
        print("By rule: " + ", ".join("%s=%d" % kv for kv in sorted(rep["by_rule"].items())))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audit UI Automator tests (Kotlin/Java) for legacy APIs and flaky patterns.")
    ap.add_argument("path", nargs="?", help="project folder or a single .kt/.java/build file")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--only", nargs="+", metavar="RULE", help="report only these rule ids")
    ap.add_argument("--rules", action="store_true", help="list the rules and exit")
    a = ap.parse_args(argv)
    if a.rules:
        for rid, level, langs, _rx, msg, fix in RULES:
            print("%-26s %-5s %-4s %s\n%33s fix: %s" % (rid, level, langs, msg, "", fix))
        return 0
    if not a.path:
        ap.error("path is required")
    if not os.path.exists(a.path):
        print("error: %s does not exist" % a.path, file=sys.stderr)
        return 2
    rep = audit(a.path, set(a.only) if a.only else None)
    if rep.get("error"):
        print("error: %s in %s" % (rep["error"], a.path), file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        print_report(rep)
    c = rep.get("counts", {})
    if c.get("ERROR") or (a.strict and c.get("WARN")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
