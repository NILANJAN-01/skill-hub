#!/usr/bin/env python3
"""Audit JUnit tests (Java and Kotlin) and their build for migration problems and weak or flaky tests.

Usage:
    python junit_audit.py <project-dir-or-file> [--json] [--strict] [--only RULE ...] [--rules]

Scans *.java and *.kt test sources (src/test, src/integrationTest, androidTest, or any file importing
JUnit), junit-platform.properties, build.gradle(.kts), gradle/libs.versions.toml and pom.xml. Reports:
  - JUnit 3/4 code to migrate to JUnit Jupiter (imports, @Test(expected/timeout), rules, runners,
    categories, Parameterized, message-first assertions) and files that mix JUnit 4 and Jupiter
  - APIs and settings removed or deprecated in JUnit 6 (MethodOrderer.Alphanumeric, JUnitPlatform
    runner, JRE.JAVA_8..16, JRE.OTHER, migrationsupport, junit.jupiter.tempdir.scope, ...)
  - tests that never run (private, static or non-void test methods, non-static @BeforeAll, static
    @Nested classes, Kotlin @BeforeAll outside a companion object, JUnit 4 tests with no Vintage engine)
  - weak and flaky tests (no assertion, sleeps, @Disabled without a reason, try/fail/catch, clock and
    randomness, assertTrue(a.equals(b)))
  - build setup (useJUnitPlatform, launcher, engine, params, BOM/version mismatches, Surefire < 3.0.0,
    Java < 17, Kotlin < 2.2 for JUnit 6).
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

LATEST = "6.1.3"                     # JUnit (Platform, Jupiter, Vintage share one version since 6.0)
SUREFIRE_DOC = "3.5.5"               # version used in the JUnit 6.1.3 user guide examples
SKIP_DIRS = {".git", ".gradle", ".idea", "build", "out", "target", "node_modules", ".venv", "venv",
             "__pycache__", "generated", ".kotlin"}
TEST_ANN = {"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"}
LIFECYCLE_ANN = {"BeforeEach", "AfterEach", "BeforeAll", "AfterAll"}
ASSERT_WORDS = re.compile(r"\b(assert\w*|expect\w*|verify\w*|fail|should\w*|check\w*|then|assertThat|"
                          r"confirm\w*|ensure\w*|must\w*|validate\w*)\s*[\(\{<]|\bassertThat\b|\.should|"
                          r"\bshouldBe\b|\.isEqualTo\(|\.matches\(")

JUNIT4_MAP = {
    "Test": "org.junit.jupiter.api.Test",
    "Before": "org.junit.jupiter.api.BeforeEach",
    "After": "org.junit.jupiter.api.AfterEach",
    "BeforeClass": "org.junit.jupiter.api.BeforeAll",
    "AfterClass": "org.junit.jupiter.api.AfterAll",
    "Ignore": "org.junit.jupiter.api.Disabled (with a reason)",
    "Assert": "org.junit.jupiter.api.Assertions (message is the LAST argument)",
    "Assume": "org.junit.jupiter.api.Assumptions",
    "Rule": "@ExtendWith / @RegisterExtension (or a built-in: @TempDir, @Timeout, TestInfo)",
    "ClassRule": "@ExtendWith / static @RegisterExtension",
    "FixMethodOrder": "@TestMethodOrder(MethodOrderer.MethodName.class)",
    "runner.RunWith": "@ExtendWith (Mockito: MockitoExtension; Spring: SpringExtension); "
                      "Enclosed -> @Nested; Parameterized -> @ParameterizedTest/@ParameterizedClass; "
                      "Suite -> @Suite (junit-platform-suite)",
    "experimental.categories.Category": "@Tag(\"name\")",
    "rules.ExpectedException": "assertThrows(Type.class, () -> ...)",
    "rules.TemporaryFolder": "@TempDir Path dir",
    "rules.Timeout": "@Timeout(value = 5, unit = TimeUnit.SECONDS) or assertTimeout",
    "rules.TestName": "TestInfo parameter (testInfo.getDisplayName(), getTestMethod())",
    "rules.ErrorCollector": "assertAll(...)",
    "rules.TestWatcher": "an extension implementing org.junit.jupiter.api.extension.TestWatcher",
    "rules.ExternalResource": "an extension with BeforeEachCallback/AfterEachCallback, or @AutoClose",
    "runners.Parameterized": "@ParameterizedTest with @MethodSource/@CsvSource, or @ParameterizedClass",
    "runners.Suite": "@Suite + @SelectClasses/@SelectPackages (org.junit.platform.suite.api)",
    "runners.JUnit4": "nothing (remove @RunWith)",
    "runners.BlockJUnit4ClassRunner": "a Jupiter extension",
}

# (id, level, langs, regex, message, fix)
RULES = [
    # ---- JUnit 3 / 4 -----------------------------------------------------------------------------
    ("junit3-testcase", "WARN", "both", re.compile(r"\bextends\s+(junit\.framework\.)?TestCase\b|"
                                                   r"\bimport\s+junit\.framework\."),
     "JUnit 3 (junit.framework.TestCase): runs only through the deprecated Vintage engine",
     "plain class with @Test methods from org.junit.jupiter.api; setUp/tearDown -> @BeforeEach/@AfterEach"),
    ("junit4-expected", "WARN", "both", re.compile(r"@(org\.junit\.)?Test\s*\(\s*expected\s*="),
     "@Test(expected = ...) is JUnit 4", "assertThrows(Type.class, () -> call()) (Kotlin: assertThrows<Type> { })"),
    ("junit4-timeout", "WARN", "both", re.compile(r"@(org\.junit\.)?Test\s*\(\s*timeout\s*="),
     "@Test(timeout = ...) is JUnit 4", "@Timeout(value = N, unit = MILLISECONDS) or assertTimeout(Duration, ...)"),
    ("junit4-assert-that", "WARN", "both", re.compile(r"\bAssert\.assertThat\s*\(|import\s+static\s+org\.junit\."
                                                      r"Assert\.assertThat\b"),
     "org.junit.Assert.assertThat is deprecated and absent from Jupiter",
     "Hamcrest MatcherAssert.assertThat, AssertJ assertThat, or a Jupiter assertion"),
    # ---- JUnit 6 removals and deprecations -------------------------------------------------------
    ("removed-alphanumeric", "ERROR", "both", re.compile(r"\bMethodOrderer\.Alphanumeric\b"),
     "MethodOrderer.Alphanumeric was removed in JUnit 6", "MethodOrderer.MethodName"),
    ("removed-platform-runner", "ERROR", "both",
     re.compile(r"\bJUnitPlatform(\.class|::class)|\borg\.junit\.platform\.runner\b"),
     "the JUnit 4 JUnitPlatform runner (junit-platform-runner) was removed in JUnit 6",
     "@Suite with @SelectPackages/@SelectClasses from junit-platform-suite"),
    ("removed-use-technical-names", "ERROR", "both", re.compile(r"@UseTechnicalNames\b"),
     "@UseTechnicalNames was removed in JUnit 6", "remove it; suites use display names"),
    ("removed-intercept-dynamic", "ERROR", "both",
     re.compile(r"\binterceptDynamicTest\s*\(\s*(\w+\s+)?\w+\s*,\s*(\w+\s+)?\w+\s*\)"),
     "InvocationInterceptor.interceptDynamicTest(Invocation, ExtensionContext) was removed in JUnit 6",
     "override interceptDynamicTest(Invocation, DynamicTestInvocationContext, ExtensionContext)"),
    ("removed-platform-api", "ERROR", "both",
     re.compile(r"\bReflectionSupport\.loadClass\s*\(|\bBlacklistedExceptions\b|\bClasspathScanningSupport\b|"
                r"\bLegacyReportingUtils\b|\bSingleTestExecutor\b|"
                r"\borg\.junit\.platform\.commons\.util\.PreconditionViolationException\b"),
     "JUnit Platform API removed in JUnit 6",
     "ReflectionSupport.tryToLoadClass(...); org.junit.platform.commons.PreconditionViolationException; "
     "see the 6.0.0 release notes for the others"),
    ("csv-line-separator", "ERROR", "both", re.compile(r"@CsvFileSource\s*\([^)]*\blineSeparator\s*="),
     "@CsvFileSource(lineSeparator = ...) was removed in JUnit 6 (\\r, \\n and \\r\\n are detected)",
     "remove the attribute"),
    ("deprecated-jre-constant", "WARN", "both", re.compile(r"\bJRE\.JAVA_(8|9|1[0-6])\b"),
     "JRE.JAVA_8 .. JAVA_16 are deprecated in JUnit 6 (Java 17 is the minimum)",
     "use JAVA_17 or newer, or the int attributes (versions / minVersion / maxVersion)"),
    ("deprecated-jre-other", "WARN", "both", re.compile(r"\bJRE\.OTHER\b"),
     "JRE.OTHER is deprecated since 6.1", "@EnabledOnJre(versions = 30) / @EnabledForJreRange(minVersion = 30)"),
    ("deprecated-engine-constants", "WARN", "both", re.compile(r"\borg\.junit\.jupiter\.engine\.Constants\b"),
     "org.junit.jupiter.engine.Constants is deprecated since 6.1", "org.junit.jupiter.api.Constants"),
    ("deprecated-get-or-compute", "INFO", "both", re.compile(r"\.getOrComputeIfAbsent\s*\("),
     "ExtensionContext.Store.getOrComputeIfAbsent is deprecated in JUnit 6", "computeIfAbsent(...)"),
    ("deprecated-migrationsupport", "WARN", "both",
     re.compile(r"@EnableRuleMigrationSupport\b|@EnableJUnit4MigrationSupport\b|\bIgnoreCondition\b|"
                r"\borg\.junit\.jupiter\.migrationsupport\b"),
     "junit-jupiter-migrationsupport is deprecated and will be removed in the next major version",
     "replace the JUnit 4 rules with Jupiter extensions (@TempDir, assertThrows, @RegisterExtension) and @Ignore "
     "with @Disabled"),
    # ---- weak and flaky tests --------------------------------------------------------------------
    ("sleep", "WARN", "both", re.compile(r"\b(Thread\.sleep|TimeUnit\.\w+\.sleep|SystemClock\.sleep)\s*\("),
     "sleeping in a test makes it slow and flaky",
     "wait for a condition (Awaitility, CountDownLatch.await(timeout)), or inject a fake clock/scheduler"),
    ("disabled-no-reason", "WARN", "both", re.compile(r"@Disabled\s*(\(\s*\))?\s*($|[^(\s])"),
     "@Disabled without a reason", "@Disabled(\"why, and the ticket that re-enables it\")"),
    ("wall-clock", "INFO", "both",
     re.compile(r"\b(System\.currentTimeMillis|System\.nanoTime|LocalDate\.now|LocalDateTime\.now|Instant\.now|"
                r"ZonedDateTime\.now|OffsetDateTime\.now)\s*\(\s*\)|\bnew\s+Date\s*\(\s*\)"),
     "test depends on the real clock", "pass a java.time.Clock (Clock.fixed(...)) into the code under test"),
    ("random", "INFO", "both", re.compile(r"\bMath\.random\s*\(|\bnew\s+Random\s*\(\s*\)|\bRandom\s*\(\s*\)\s*$|"
                                          r"\bThreadLocalRandom\.current\s*\("),
     "unseeded randomness makes failures hard to reproduce", "new Random(seed), log the seed, or fixed data"),
    ("assert-true-equals", "INFO", "both", re.compile(r"\bassertTrue\s*\(\s*[\w.()\[\]\"]+\.equals\s*\("),
     "assertTrue(a.equals(b)) hides both values on failure", "assertEquals(expected, actual)"),
    ("assert-true-null", "INFO", "both", re.compile(r"\bassert(True|False)\s*\([^;]*?[=!]=\s*null\s*[,)]"),
     "null check through assertTrue/assertFalse", "assertNull(x) / assertNotNull(x)"),
    ("assert-equals-boolean", "INFO", "both", re.compile(r"\bassertEquals\s*\(\s*(true|false)\s*,"),
     "assertEquals(true/false, x)", "assertTrue(x) / assertFalse(x)"),
    ("print", "INFO", "both", re.compile(r"\bSystem\.(out|err)\.print(ln|f)?\s*\(|^\s*println\s*\("),
     "printing from tests clutters the build log", "assert on the value, or use TestReporter.publishEntry(...)"),
]

DECL_JAVA = re.compile(r"^\s*((?:(?:public|protected|private|static|final|abstract|synchronized|default|native)\s+)*)"
                       r"(?:<[^>]+>\s+)?([\w$][\w$<>\[\],.?\s]*?)\s+([\w$]+)\s*\(")
DECL_KT = re.compile(r"^\s*((?:(?:public|protected|private|internal|override|open|suspend|inline|operator|infix|"
                     r"tailrec|final|abstract)\s+)*)fun\s+(?:<[^>]+>\s*)?(?:[\w.]+\.)?(`[^`]+`|[\w$]+)\s*\(")
CLASS_RE = re.compile(r"^\s*((?:(?:public|protected|private|internal|static|final|abstract|open|inner|data|sealed|"
                      r"enum|annotation)\s+)*)(class|interface|object|record|enum)\s+([\w$]+)")
COMPANION_RE = re.compile(r"\bcompanion\s+object\b")
ANN_RE = re.compile(r"@([\w.]+)(\s*\((?:[^()]|\([^()]*\))*\))?")
NOT_DECL = {"if", "for", "while", "switch", "catch", "return", "new", "throw", "else", "synchronized", "try", "do"}


def strip_comments(line: str, state: dict) -> str:
    """Drop // and /* */ comments, keep strings."""
    out, i, n, in_str = [], 0, len(line), None
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
        elif line.startswith("//", i):
            break
        elif line.startswith("/*", i):
            state["in_block"] = True
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def no_strings(line: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', line)


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


def rel(path: str, root: str) -> str:
    r = os.path.relpath(path, root) if os.path.isdir(root) else os.path.basename(path)
    return r.replace(os.sep, "/")


def is_test_source(path: str, text: str) -> bool:
    p = path.replace("\\", "/")
    if re.search(r"/src/(test|integrationTest|testFixtures|androidTest|it|\w+Test)/", p):
        return True
    return bool(re.search(r"\bimport\s+(static\s+)?(org\.junit\.|junit\.framework\.)", text))


def imports_of(text: str) -> dict:
    j4 = set(m.group(2) for m in re.finditer(r"^\s*import\s+(static\s+)?org\.junit\.(?!jupiter\.|platform\.|"
                                              r"vintage\.)([\w.]+?)(\.\*|\.\w+)?\s*;?\s*$", text, re.M))
    j4_names = set()
    for m in re.finditer(r"^\s*import\s+org\.junit\.(?!jupiter\.|platform\.|vintage\.)([\w.]+)\s*;?\s*$", text, re.M):
        j4_names.add(m.group(1))
    jup = bool(re.search(r"^\s*import\s+(static\s+)?org\.junit\.jupiter\.", text, re.M))
    jup_wild = bool(re.search(r"^\s*import\s+org\.junit\.jupiter\.api\.\*", text, re.M))
    j4_wild = bool(re.search(r"^\s*import\s+org\.junit\.\*", text, re.M))
    jup_ann = set(m.group(1) for m in re.finditer(r"^\s*import\s+org\.junit\.jupiter\.api\.(\w+)\s*;?\s*$", text, re.M))
    return {"j4": j4, "j4_names": j4_names, "jupiter": jup, "jup_wild": jup_wild, "j4_wild": j4_wild,
            "jup_ann": jup_ann}


def framework_of(ann: str, imp: dict) -> str:
    """'junit4', 'jupiter' or '' for an annotation name as written."""
    if ann.startswith("org.junit.jupiter."):
        return "jupiter"
    if ann.startswith("org.junit."):
        return "junit4"
    if ann in imp["jup_ann"] or imp["jup_wild"]:
        return "jupiter"
    if ann in imp["j4_names"] or imp["j4_wild"]:
        return "junit4"
    if ann in ("ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate", "BeforeEach", "AfterEach",
               "BeforeAll", "AfterAll", "Nested", "Disabled"):
        return "jupiter"
    return ""


def call_args(line: str, start: int) -> list:
    """Top-level comma-separated arguments of the call whose '(' is at start."""
    depth, cur, args, i, in_str = 0, [], [], start, None
    while i < len(line):
        c = line[i]
        if in_str:
            cur.append(c)
            if c == "\\":
                cur.append(line[i + 1] if i + 1 < len(line) else "")
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            if depth > 1:
                cur.append(c)
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(cur).strip())
                return [a for a in args if a]
            cur.append(c)
        elif c == "," and depth == 1:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    return []                                     # call continues on another line: unknown


class FileAudit:
    def __init__(self, path, root, text, add, per_class_default=False):
        self.path, self.root, self.text, self.add = path, root, text, add
        self.per_class_default = per_class_default
        self.lang = "kt" if path.endswith(".kt") else "java"
        self.imp = imports_of(text)

    def run(self):
        lang = self.lang
        state = {"in_block": False}
        pending = []                              # annotations waiting for a declaration: (name, args, line)
        depth = 0                                 # brace depth
        paren = 0                                 # open parentheses of a multi-line annotation
        scopes = []                               # (kind, depth_at_open, info)
        method = None                             # test method whose body is being collected
        counts = Counter()
        for no, raw in enumerate(self.text.splitlines(), 1):
            line = strip_comments(raw, state)
            if not line.strip():
                continue
            for rid, level, rl, rx, msg, fix in RULES:
                if (rl == "both" or rl == lang) and rx.search(line):
                    self.add(rid, level, self.path, no, msg, fix, raw)
            m = re.match(r"^\s*import\s+(static\s+)?org\.junit\.(?!jupiter\.|platform\.|vintage\.)([\w.]+)", line)
            if m:
                name = m.group(2)
                key = re.sub(r"\.\*$", "", name.rsplit(".", 1)[0] if m.group(1) else name)
                fix = JUNIT4_MAP.get(key) or JUNIT4_MAP.get(key.split(".")[-1]) or "the Jupiter equivalent"
                self.add("junit4-import", "WARN", self.path, no, "JUnit 4 import org.junit.%s" % name,
                         "use %s" % fix, raw)
            self._message_order(line, raw, no)
            code = no_strings(line)
            opens, closes = code.count("{"), code.count("}")
            if paren > 0:                         # still inside a multi-line annotation argument list
                paren += code.count("(") - code.count(")")
                depth += opens - closes
                continue
            if method is None or depth == method["start_depth"]:
                for am in ANN_RE.finditer(code):
                    pending.append((am.group(1), am.group(2) or "", no))
                rest = ANN_RE.sub(" ", code)
                starts = list(re.finditer(r"@[\w.]+\s*\(", code))
                if starts and not rest.strip():
                    tail = code[starts[-1].start():]
                    bal = tail.count("(") - tail.count(")")
                    if bal > 0:                   # annotation arguments continue on the next lines
                        paren = bal
                        depth += opens - closes
                        pending.append((starts[-1].group(0).strip("@( \t"), tail, no))
                        continue
                cls = CLASS_RE.match(rest)
                comp = COMPANION_RE.search(rest)
                decl = self._decl(rest) if not cls and not comp else None
                if cls:
                    anns, pending = pending, []
                    self._class(cls, anns, no, raw, scopes, depth)
                elif comp:
                    pending = []
                    scopes.append(("companion", depth, {}))
                elif decl:
                    anns, pending = pending, []
                    self._check_method(decl, anns, no, raw, scopes)
                    tests = [x for x in anns if x[0].split(".")[-1] in TEST_ANN]
                    if tests:
                        counts["tests"] += 1
                        if method is None:
                            expr = lang == "kt" and bool(re.search(r"\)\s*(:\s*[\w.<>?, ]+)?\s*=(?!=)", rest)) \
                                and not re.search(r"\)\s*(:\s*[\w.<>?, ]+)?\s*\{", rest)
                            method = {"name": decl["name"], "line": no, "start_depth": depth, "body": [],
                                      "ann": [x[0].split(".")[-1] for x in anns],
                                      "expected": any("expected" in x[1] for x in anns), "expr": expr}
                elif rest.strip() and pending and not re.match(r"^\s*(import|package)\b", rest):
                    pending = []                  # a field or other declaration took the annotations
            if method is not None:
                method["body"].append(code)
            depth += opens - closes
            if method is not None:
                ended = closes > 0 and depth <= method["start_depth"]
                if method["expr"] and not opens and depth == method["start_depth"] and \
                        not re.search(r"[({,=]\s*$", code):
                    ended = True
                if ended:
                    self._check_body(method)
                    method = None
            while scopes and closes and depth <= scopes[-1][1]:
                scopes.pop()
        return counts

    def _decl(self, rest: str):
        if self.lang == "kt":
            d = DECL_KT.match(rest)
            return {"mods": d.group(1).split(), "name": d.group(2), "ret": self._kt_return(rest)} if d else None
        d = DECL_JAVA.match(rest)
        if not d or d.group(3) in NOT_DECL or d.group(2).split()[-1] in NOT_DECL:
            return None
        if "=" in rest.split("(")[0] or rest.strip().startswith(("return", "throw", "new ")):
            return None
        tw = d.group(2).split()
        mods = d.group(1).split() + [w for w in tw[:-1] if w in ("public", "protected", "private", "static", "final")]
        return {"mods": mods, "name": d.group(3), "ret": tw[-1] if tw else ""}

    def _class(self, cls, anns, no, raw, scopes, depth):
        mods = cls.group(1).split()
        info = {"name": cls.group(3), "kind": cls.group(2),
                "per_class": self.per_class_default or any(
                    x[0].endswith("TestInstance") and "PER_CLASS" in x[1] for x in anns),
                "nested": any(x[0].split(".")[-1] == "Nested" for x in anns)}
        if info["nested"] and self.lang == "java" and "static" in mods:
            self.add("nested-static", "ERROR", self.path, no,
                     "@Nested class %s is static: JUnit only runs non-static inner classes" % info["name"],
                     "remove static", raw)
        if info["nested"] and self.lang == "kt" and "inner" not in mods:
            self.add("nested-not-inner", "ERROR", self.path, no,
                     "@Nested class %s is not inner: a Kotlin nested class is static" % info["name"],
                     "inner class %s" % info["name"], raw)
        scopes.append(("class", depth, info))

    def _kt_return(self, rest: str) -> str:
        m = re.search(r"\)\s*:\s*([\w.<>?, ]+?)\s*(\{|=|$)", rest)
        return m.group(1).strip() if m else "Unit"

    def _message_order(self, line: str, raw: str, no: int):
        if not self.imp["jupiter"] or "org.junit.Assert" in self.text:
            return
        for m in re.finditer(r"\bassert(Equals|NotEquals|ArrayEquals|Same|NotSame|IterableEquals)\s*\(", line):
            args = call_args(line, m.end() - 1)
            if len(args) == 3 and re.match(r'^"', args[0]) and not re.match(r'^"', args[2]):
                self.add("message-first", "WARN", self.path, no,
                         "message looks like the first argument (JUnit 4 order); Jupiter compares it as the "
                         "expected value", "assert%s(expected, actual, \"message\")" % m.group(1), raw)

    def _check_method(self, decl, anns, no, raw, scopes):
        names = [a[0].split(".")[-1] for a in anns]
        tests = [a for a in anns if a[0].split(".")[-1] in TEST_ANN]
        lifecycle = [a for a in anns if a[0].split(".")[-1] in LIFECYCLE_ANN]
        relevant = tests + lifecycle
        if not relevant:
            return
        fw = framework_of(relevant[0][0], self.imp)
        if fw != "jupiter":
            return
        mods, lang = decl["mods"], self.lang
        what = "@" + relevant[0][0].split(".")[-1]
        if "private" in mods:
            self.add("private-method", "ERROR", self.path, no,
                     "%s method %s is private: JUnit does not run it" % (what, decl["name"]),
                     "make it package-private (Java) / public (Kotlin)", raw)
        if lang == "java" and tests and "static" in mods:
            self.add("static-test", "ERROR", self.path, no,
                     "%s method %s is static: JUnit does not run it" % (what, decl["name"]), "remove static", raw)
        if tests and "TestFactory" not in names:
            ret = decl["ret"]
            if (lang == "java" and ret and ret != "void") or (lang == "kt" and ret not in ("Unit", "")):
                self.add("non-void-test", "ERROR", self.path, no,
                         "%s method %s returns %s: test methods must not return a value, so it is not run"
                         % (what, decl["name"], ret), "return void (Kotlin: Unit)", raw)
        klass = next((s for s in reversed(scopes) if s[0] == "class"), None)
        per_class = bool(klass and klass[2].get("per_class"))
        for a in lifecycle:
            n = a[0].split(".")[-1]
            if n not in ("BeforeAll", "AfterAll") or per_class:
                continue
            if lang == "java" and "static" not in mods:
                self.add("beforeall-not-static", "ERROR", self.path, no,
                         "@%s method %s is not static (and the class is not @TestInstance(PER_CLASS))"
                         % (n, decl["name"]), "make it static, or annotate the class "
                         "@TestInstance(TestInstance.Lifecycle.PER_CLASS)", raw)
            if lang == "kt":
                in_comp = bool(scopes and scopes[-1][0] == "companion")
                if not in_comp or "JvmStatic" not in [x[0].split(".")[-1] for x in anns]:
                    self.add("beforeall-kotlin", "ERROR", self.path, no,
                             "@%s fun %s must be in a companion object with @JvmStatic (or the class "
                             "@TestInstance(PER_CLASS))" % (n, decl["name"]),
                             "companion object { @JvmStatic @%s fun %s() { } }" % (n, decl["name"]), raw)

    def _check_body(self, m):
        if m["expected"] or "TestFactory" in m["ann"] or "TestTemplate" in m["ann"]:
            return
        first = m["body"][0] if m["body"] else ""
        # the body starts after the declaration: after '{' (block body) or '=' (Kotlin expression body)
        sep = "=" if m["expr"] else "{"
        head = first.split(sep, 1)[1] if sep in first else ""
        body = head + "\n" + "\n".join(m["body"][1:])
        if not ASSERT_WORDS.search(body):
            self.add("no-assertion", "WARN", self.path, m["line"],
                     "test %s has no assertion: it passes as long as nothing throws" % m["name"],
                     "assert the result (assertEquals, assertThrows, assertAll, AssertJ assertThat, verify(...))")
        if re.search(r"\bfail\s*\(", body) and re.search(r"\bcatch\s*\(|\bcatch\s*\{|} catch", body):
            self.add("try-fail-catch", "INFO", self.path, m["line"],
                     "test %s uses try / fail / catch to expect an exception" % m["name"],
                     "var e = assertThrows(Type.class, () -> ...); assert on e.getMessage()")


VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-.]?(M|RC|alpha|beta|rc)\d*)?")


def vparse(v: str):
    m = VERSION_RE.match(v or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def build_findings(builds, tomls, poms, props, sources_info, add, root):
    deps = []                                  # (file, line, group, artifact, version)
    text_all = ""
    for path, text in builds + poms:
        text_all += text + "\n"
    toml_versions, toml_libs = {}, {}
    for path, text in tomls:
        sect = None
        for no, raw in enumerate(text.splitlines(), 1):
            s = raw.split("#", 1)[0].strip()
            if s.startswith("["):
                sect = s.strip("[]").strip()
                continue
            kv = re.match(r"""([\w.-]+)\s*=\s*(.+)$""", s)
            if not kv:
                continue
            if sect == "versions":
                toml_versions[kv.group(1)] = kv.group(2).strip().strip("\"'")
            elif sect == "libraries":
                val = kv.group(2)
                mod = re.search(r"""module\s*=\s*["']([^"':]+):([^"']+)["']""", val)
                g = re.search(r"""group\s*=\s*["']([^"']+)["']""", val)
                n = re.search(r"""name\s*=\s*["']([^"']+)["']""", val)
                inline = re.match(r"""["']([^"':]+):([^"':]+):([^"']+)["']""", val.strip())
                ver = ""
                vr = re.search(r"""version\.ref\s*=\s*["']([^"']+)["']""", val)
                vv = re.search(r"""version\s*=\s*["']([^"']+)["']""", val)
                if inline:
                    grp, art, ver = inline.groups()
                elif mod:
                    grp, art = mod.groups()
                elif g and n:
                    grp, art = g.group(1), n.group(1)
                else:
                    continue
                if vr:
                    ver = toml_versions.get(vr.group(1), "")
                elif vv and not inline:
                    ver = vv.group(1)
                toml_libs["libs." + re.sub(r"[-_]", ".", kv.group(1))] = (grp, art, ver)
                deps.append((path, no, grp, art, ver, "toml"))
    # gradle coordinates
    for path, text in builds:
        for no, raw in enumerate(text.splitlines(), 1):
            line = raw.split("//", 1)[0]
            for m in re.finditer(r"""["']([\w.-]+):([\w.-]+)(?::([^"'@\s)]+))?["']""", line):
                deps.append((path, no, m.group(1), m.group(2), m.group(3) or "", "gradle"))
    # maven
    for path, text in poms:
        propmap = dict(re.findall(r"<([\w.-]+)>([^<]+)</\1>", re.search(r"<properties>(.*?)</properties>", text, re.S)
                                  .group(1) if re.search(r"<properties>(.*?)</properties>", text, re.S) else ""))
        for m in re.finditer(r"<(dependency|plugin)>(.*?)</\1>", text, re.S):
            blk = m.group(2)
            g = re.search(r"<groupId>\s*([^<\s]+)\s*</groupId>", blk)
            a = re.search(r"<artifactId>\s*([^<\s]+)\s*</artifactId>", blk)
            v = re.search(r"<version>\s*([^<\s]+)\s*</version>", blk)
            if not a:
                continue
            ver = v.group(1) if v else ""
            pv = re.match(r"\$\{([^}]+)\}", ver)
            if pv:
                ver = propmap.get(pv.group(1), ver)
            no = text[:m.start()].count("\n") + 1
            deps.append((path, no, g.group(1) if g else "org.apache.maven.plugins", a.group(1), ver,
                         "maven-" + m.group(1)))

    junit = [d for d in deps if d[2] in ("org.junit", "org.junit.jupiter", "org.junit.platform", "org.junit.vintage")
             or (d[2] == "junit" and d[3] == "junit")]
    report = [{"file": rel(d[0], root), "line": d[1], "coordinate": "%s:%s" % (d[2], d[3]), "version": d[4] or "-"}
              for d in junit]

    jup_versions = {vparse(d[4]) for d in junit if d[2] in ("org.junit", "org.junit.jupiter") and vparse(d[4])}
    plat_versions = {(d, vparse(d[4])) for d in junit if d[2] == "org.junit.platform" and vparse(d[4])}
    majors = {v[0] for v in jup_versions}
    if len(majors) > 1:
        add("junit-version-mix", "ERROR", None, 0, "JUnit Jupiter/BOM versions of different majors: %s" %
            ", ".join(".".join(map(str, v)) for v in sorted(jup_versions)),
            "use one version everywhere, ideally through the BOM org.junit:junit-bom:%s" % LATEST)
    if 6 in majors:
        for d, pv in plat_versions:
            if pv[0] == 1:
                add("platform-version-mix", "ERROR", d[0], d[1],
                    "%s:%s:%s is a JUnit 5 Platform version, but Jupiter is 6.x (since 6.0 Platform uses the same "
                    "version)" % (d[2], d[3], d[4]), "drop the version and import org.junit:junit-bom:%s" % LATEST)
    for v in jup_versions:
        if v[0] == 5:
            add("junit5-version", "INFO", None, 0, "JUnit %s; JUnit %s is current (needs Java 17+)" %
                (".".join(map(str, v)), LATEST), "upgrade with the BOM org.junit:junit-bom:%s" % LATEST)
        if v[0] == 6 and v < vparse(LATEST):
            add("junit6-patch", "INFO", None, 0, "JUnit %s; %s is the latest" % (".".join(map(str, v)), LATEST),
                "org.junit:junit-bom:%s" % LATEST)
    is6 = 6 in majors or (not majors and any(d[4].startswith("6") for d in junit))

    arts = {d[3] for d in junit}
    has_engine = bool(arts & {"junit-jupiter", "junit-jupiter-engine"})
    if "junit-jupiter-api" in arts and not has_engine:
        add("no-engine", "ERROR", None, 0, "junit-jupiter-api without junit-jupiter-engine: no tests are found",
            "depend on the aggregate org.junit.jupiter:junit-jupiter (api + params + engine)")
    if sources_info["params"] and "junit-jupiter-api" in arts and "junit-jupiter" not in arts and \
            "junit-jupiter-params" not in arts:
        add("no-params", "ERROR", None, 0, "@ParameterizedTest is used but junit-jupiter-params is missing",
            "add org.junit.jupiter:junit-jupiter-params, or use the aggregate org.junit.jupiter:junit-jupiter")
    for d in junit:
        if d[3] == "junit-platform-runner":
            add("removed-platform-runner", "ERROR", d[0], d[1], "junit-platform-runner was removed in JUnit 6",
                "use junit-platform-suite and @Suite")
        if d[3] == "junit-platform-suite-commons":
            add("removed-suite-commons", "ERROR", d[0], d[1], "junit-platform-suite-commons was removed in JUnit 6",
                "org.junit.platform:junit-platform-suite")
        if d[3] == "junit-jupiter-migrationsupport":
            add("deprecated-migrationsupport", "WARN", d[0], d[1],
                "junit-jupiter-migrationsupport is deprecated (removal planned)", "migrate the JUnit 4 rules")
        if d[3] == "junit-vintage-engine":
            add("vintage-engine", "WARN", d[0], d[1], "junit-vintage-engine is deprecated in JUnit 6: a temporary "
                "bridge while migrating JUnit 4 tests", "migrate the JUnit 4 tests, then remove it")
    j4_files = sources_info["junit4_files"]
    if j4_files and has_engine and "junit-vintage-engine" not in arts:
        add("junit4-not-run", "ERROR", None, 0,
            "%d JUnit 4 test file(s) but no junit-vintage-engine: on the JUnit Platform they are silently skipped "
            "(e.g. %s)" % (len(j4_files), ", ".join(j4_files[:3])),
            "migrate them to Jupiter (preferred), or add testRuntimeOnly(\"org.junit.vintage:junit-vintage-engine\") "
            "temporarily")

    # Gradle specifics
    for path, text in builds:
        body = re.sub(r"//.*", "", text)
        uses_junit = re.search(r"junit[-.]jupiter|junit-bom|libs\.[\w.]*junit", body)
        if not uses_junit:
            continue
        if not re.search(r"useJUnitPlatform|useJUnitJupiter", body):
            android = "com.android" in body or "android {" in body
            add("no-use-junit-platform", "ERROR", path, 0,
                "JUnit Jupiter dependency but no useJUnitPlatform(): Gradle runs no Jupiter tests",
                "testOptions { unitTests.all { it.useJUnitPlatform() } }" if android else
                "tasks.test { useJUnitPlatform() }  (or testing.suites.test { useJUnitJupiter() })")
        if not re.search(r"junit-platform-launcher|platform\.launcher|libs\.[\w.]*launcher", body) and \
                not re.search(r"useJUnitJupiter", body):
            add("no-launcher", "WARN", path, 0,
                "no testRuntimeOnly(\"org.junit.platform:junit-platform-launcher\"): required on Gradle 9, "
                "recommended by the JUnit docs to keep versions aligned",
                "testRuntimeOnly(\"org.junit.platform:junit-platform-launcher\")")
        if is6:
            tc = re.search(r"(jvmToolchain\s*\(\s*|JavaLanguageVersion\.of\s*\(\s*)(\d+)", body)
            if tc and int(tc.group(2)) < 17:
                add("java-too-old", "ERROR", path, 0, "Java toolchain %s: JUnit 6 needs Java 17+ at runtime" %
                    tc.group(2), "jvmToolchain(17) or newer for the test task")
            kv = re.search(r"""(org\.jetbrains\.kotlin\.(?:jvm|android|multiplatform)|kotlin\(["'](?:jvm|android)["']\))"""
                           r"""["']?\)?\s*version\s*["'](\d+\.\d+)""", body)
            if kv and tuple(map(int, kv.group(2).split("."))) < (2, 2):
                add("kotlin-too-old", "WARN", path, 0, "Kotlin %s: JUnit 6 requires Kotlin 2.2+" % kv.group(2),
                    "upgrade the Kotlin plugin to 2.2 or newer")
    # Maven specifics
    for path, text in poms:
        if not re.search(r"<groupId>\s*org\.junit", text):
            continue
        sf = [d for d in deps if d[0] == path and d[3] in ("maven-surefire-plugin", "maven-failsafe-plugin")]
        for d in sf:
            v = vparse(d[4])
            if v and v < (3, 0, 0) and is6:
                add("surefire-too-old", "ERROR", path, d[1], "%s %s: JUnit 6 needs 3.0.0 or newer" % (d[3], d[4]),
                    "<version>%s</version> (or newer)" % SUREFIRE_DOC)
        if is6 and not any(d[3] == "maven-surefire-plugin" and d[4] for d in sf):
            add("surefire-unpinned", "INFO", path, 0, "maven-surefire-plugin version is not pinned; the default "
                "depends on the Maven version", "declare maven-surefire-plugin %s or newer" % SUREFIRE_DOC)
        rel_ = re.search(r"<(maven\.compiler\.release|maven\.compiler\.source|java\.version|release)>\s*(\d+)\s*<", text)
        if is6 and rel_ and int(rel_.group(2)) < 17:
            add("java-target-old", "INFO", path, 0, "compiling for Java %s: fine, but the tests must run on a "
                "Java 17+ JVM with JUnit 6" % rel_.group(2), "run Maven on JDK 17+ (or use a toolchain)")
    for path, text in props + builds + poms:
        for no, raw in enumerate(text.splitlines(), 1):
            for key, msg in (("junit.jupiter.tempdir.scope", "no longer supported in JUnit 6"),
                             ("junit.jupiter.params.arguments.conversion.locale.format",
                              "removed in JUnit 6 (Locale conversion always uses BCP 47)"),
                             ("junit.platform.reflection.search.useLegacySemantics", "removed in JUnit 6")):
                if key in raw and not raw.strip().startswith("#"):
                    add("removed-config", "ERROR", path, no, "%s is %s" % (key, msg), "remove it", raw)
    return report


def audit(root: str, only=None) -> dict:
    findings = []
    sources, builds, tomls, poms, props = [], [], [], [], []
    for path in iter_files(root):
        name = os.path.basename(path)
        if name.endswith((".java", ".kt")):
            text = read(path)
            if is_test_source(path, text):
                sources.append((path, text))
        elif name in ("build.gradle", "build.gradle.kts"):
            builds.append((path, read(path)))
        elif name == "libs.versions.toml":
            tomls.append((path, read(path)))
        elif name == "pom.xml":
            poms.append((path, read(path)))
        elif name == "junit-platform.properties":
            props.append((path, read(path)))
    if not (sources or builds or poms or tomls):
        return {"root": root, "error": "no Java/Kotlin test sources, Gradle or Maven files found"}

    def add(rule, level, path, line, msg, fix, code=""):
        if only and rule not in only:
            return
        findings.append({"rule": rule, "level": level, "file": rel(path, root) if path else "(build)",
                         "line": line, "message": msg, "fix": fix, "code": (code or "").strip()[:160]})

    per_class_default = any(re.search(r"junit\.jupiter\.testinstance\.lifecycle\.default\W+per_class", t)
                            for _p, t in props + builds + poms)
    langs, frameworks = Counter(), Counter()
    junit4_files, params = [], False
    tests = 0
    for path, text in sources:
        fa = FileAudit(path, root, text, add, per_class_default)
        langs[fa.lang] += 1
        imp = fa.imp
        j4_test = bool({"Test"} & imp["j4_names"]) or "@org.junit.Test" in text or \
            bool(re.search(r"extends\s+(junit\.framework\.)?TestCase\b", text))
        jup = imp["jupiter"]
        if j4_test:
            junit4_files.append(rel(path, root))
            frameworks["junit4"] += 1
        if jup:
            frameworks["jupiter"] += 1
        j4_life = imp["j4_names"] & {"Test", "Before", "After", "BeforeClass", "AfterClass", "Rule", "ClassRule"}
        jup_life = imp["jup_ann"] & {"Test", "BeforeEach", "AfterEach", "BeforeAll", "AfterAll", "Nested",
                                     "Disabled", "ParameterizedTest"}
        if j4_life and (jup_life or imp["jup_wild"] or "org.junit.jupiter.params" in text):
            add("mixed-junit4-jupiter", "ERROR", path, 1,
                "file mixes JUnit 4 (%s) and Jupiter (%s) annotations: each engine ignores the other's, so "
                "lifecycle methods or tests silently do not run" % (", ".join(sorted(j4_life)),
                                                                    ", ".join(sorted(jup_life)) or "params"),
                "migrate the whole class to org.junit.jupiter.api")
        if "org.junit.jupiter.params" in text:
            params = True
        tests += fa.run()["tests"]
    report = build_findings(builds, tomls, poms, props, {"junit4_files": junit4_files, "params": params}, add, root)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (order[f["level"]], f["file"], f["line"]))
    # de-duplicate identical rule+file+line
    seen, uniq = set(), []
    for f in findings:
        k = (f["rule"], f["file"], f["line"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return {"root": root, "files": len(sources), "languages": dict(langs), "frameworks": dict(frameworks),
            "test_methods": tests, "dependencies": report, "findings": uniq,
            "counts": dict(Counter(f["level"] for f in uniq)), "by_rule": dict(Counter(f["rule"] for f in uniq))}


def print_report(rep: dict) -> None:
    print("JUnit audit: %s" % rep["root"])
    l, fw = rep["languages"], rep["frameworks"]
    print("  test sources: %d (Java %d, Kotlin %d); test methods: %d" %
          (rep["files"], l.get("java", 0), l.get("kt", 0), rep["test_methods"]))
    print("  files using: Jupiter %d, JUnit 3/4 %d" % (fw.get("jupiter", 0), fw.get("junit4", 0)))
    for d in rep["dependencies"]:
        print("  dependency: %s %s (%s%s)" % (d["coordinate"], d["version"], d["file"], ":%d" % d["line"] if d["line"] else ""))
    print()
    for f in rep["findings"]:
        loc = "%s:%d" % (f["file"], f["line"]) if f["line"] else f["file"]
        print("%-5s %s [%s] %s" % (f["level"], loc, f["rule"], f["message"]))
        if f["code"]:
            print("      code: %s" % f["code"])
        print("      fix:  %s" % f["fix"])
    if not rep["findings"]:
        print("No findings.")
    c = rep["counts"]
    print("\nSummary: %d error(s), %d warning(s), %d info" % (c.get("ERROR", 0), c.get("WARN", 0), c.get("INFO", 0)))
    if rep["by_rule"]:
        print("By rule: " + ", ".join("%s=%d" % kv for kv in sorted(rep["by_rule"].items())))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audit JUnit tests (Java/Kotlin) for migration problems and weak tests.")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--only", nargs="+", metavar="RULE")
    ap.add_argument("--rules", action="store_true", help="list the line rules and exit")
    a = ap.parse_args(argv)
    if a.rules:
        for rid, level, langs, _rx, msg, fix in RULES:
            print("%-28s %-5s %-4s %s\n%35s fix: %s" % (rid, level, langs, msg, "", fix))
        print("\nAlso: junit4-import, mixed-junit4-jupiter, message-first, private-method, static-test, "
              "non-void-test, beforeall-not-static, beforeall-kotlin, nested-static, nested-not-inner, "
              "no-assertion, try-fail-catch, junit4-not-run, no-engine, no-params, no-use-junit-platform, "
              "no-launcher, junit-version-mix, platform-version-mix, vintage-engine, surefire-too-old, "
              "java-too-old, kotlin-too-old, removed-config, junit5-version")
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
    c = rep["counts"]
    return 1 if c.get("ERROR") or (a.strict and c.get("WARN")) else 0


if __name__ == "__main__":
    sys.exit(main())
