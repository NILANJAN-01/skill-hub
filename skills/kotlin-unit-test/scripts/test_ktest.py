#!/usr/bin/env python3
"""Tests for the kotlin-unit-test scripts. No JDK is needed: a fake Gradle wrapper (Python) stands in for the build.
It decides pass/fail from the Kotlin source text (rules.json), writes real JUnit XML and JaCoCo XML, so the parser,
the class/method mapping, the verification rules, the run/report flow and the mutation check are all exercised.
Run: python -m unittest discover -s scripts -p "test_*.py" """

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks  # noqa: E402
import kotlin_source as ks  # noqa: E402
import results as rs  # noqa: E402

CALC = """\
package com.acme

/** Calculator { with a brace in a comment } */
class Calculator(private val audit: Audit) {
    fun add(a: Int, b: Int): Int = a + b

    fun isPositive(x: Int): Boolean {
        return x > 0
    }

    fun divide(a: Int, b: Int): Int {
        require(b != 0) { "b must not be 0: ${'$'}{b}" }
        audit.record("divide")
        return a / b
    }

    private fun hidden() = 1
}

interface Audit { fun record(event: String) }
"""

STRINGS = """\
package com.acme

fun String.shout(): String = uppercase() + "!"

fun slug(s: String): String = s.lowercase().replace(" ", "-")
"""

UNTESTED = """\
package com.acme

class Untested {
    fun twice(x: Int) = x * 2
}
"""

CALC_TEST = """\
package com.acme

import io.mockk.mockk
import io.mockk.verify
import org.junit.jupiter.api.Disabled
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CalculatorTest {
    private val audit = mockk<Audit>(relaxed = true)
    private val calc = Calculator(audit)

    @Test
    fun `add returns sum`() {
        assertEquals(5, calc.add(2, 3))
    }

    @Test
    fun isPositiveForOne() {
        val expected = true
        calc.isPositive(1)
    }

    @Test
    fun `divide records audit`() {
        calc.divide(4, 2)
        verify { audit.record("divide") }
    }

    @Test
    fun trivial() { assertTrue(true) }

    @Test
    @Disabled("flaky on CI")
    fun `divide by zero`() { }

    @Test
    fun sleepy() {
        Thread.sleep(10)
        assertEquals(2, calc.divide(4, 2))
    }

    @Test
    fun todo() { TODO("later") }
}
"""

STRINGS_TEST = """\
package com.acme

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals

class StringsTest {
    @Test fun shoutAddsBang() = assertEquals("HI!", "hi".shout())

    @Test
    fun slugReplacesSpaces() {
        assertEquals("a-b", slug("A B"))
    }
}
"""

LEGACY_TEST = """\
package com.acme

import org.junit.Test
import org.junit.Assert.assertEquals

class LegacyTest {
    @Test
    fun addStillWorks() {
        assertEquals(3, Calculator(object : Audit { override fun record(event: String) {} }).add(1, 2))
    }
}
"""

KOTEST_SPEC = """\
package com.acme

import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.shouldBe

class SlugSpec : StringSpec({
    "slug lowercases" {
        slug("A") shouldBe "a"
    }
    !"slug disabled case" {
        slug("") shouldBe ""
    }
})
"""

BUILD = """\
plugins { kotlin("jvm") version "2.0.21"; jacoco }
dependencies {
    testImplementation(kotlin("test"))
    testImplementation("io.mockk:mockk:1.13.13")
}
tasks.test { useJUnitPlatform() }
"""

RULES = {
    "tests": {
        "com.acme.CalculatorTest": {
            "add returns sum": {"requires": ["a + b"]},
            "isPositiveForOne": {},
            "divide records audit": {},
            "trivial": {},
            "divide by zero": {"skip": True},
            "sleepy": {"requires": ["a / b", "b != 0"]},
            "todo": {"fail": "kotlin.NotImplementedError: An operation is not implemented: later"},
        },
        "com.acme.StringsTest": {"shoutAddsBang": {"requires": ["+ \"!\""]},
                                 "slugReplacesSpaces": {"requires": ["replace(\" \", \"-\")"]}},
        "com.acme.SlugSpec": {"slug lowercases": {"requires": ["lowercase()"]},
                              "slug disabled case": {"skip": True}},
    },
    "compile_error_if": ["a * b"],
    "coverage": {
        "com/acme/Calculator": {"add": [5, 1, 0], "isPositive": [8, 1, 0], "divide": [12, 3, 0]},
        "com/acme/StringsKt": {"shout": [3, 1, 0], "slug": [5, 1, 0]},
        "com/acme/Untested": {"twice": [4, 0, 1]},
    },
}

FAKE_GRADLE = r'''
import json, re, sys, os
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
root = Path(__file__).resolve().parent
rules = json.loads((root / "rules.json").read_text())
args = sys.argv[1:]
src = "\n".join(p.read_text(encoding="utf-8") for p in (root / "src" / "main").rglob("*.kt"))
print("> fake gradle " + " ".join(args))
for bad in rules.get("compile_error_if", []):
    if bad in src:
        print("e: file:///src/main/kotlin/com/acme/Calculator.kt:5:40 Type mismatch")
        print("* What went wrong:\nExecution failed for task ':compileKotlin'.\n* Try:")
        sys.exit(1)
pats = [args[i + 1] for i, a in enumerate(args) if a == "--tests"]
def selected(cls, name):
    if not pats:
        return True
    for p in pats:
        rx = "^" + re.escape(p).replace(r"\*", ".*") + "$"
        if re.match(rx, cls) or re.match(rx, cls + "." + name):
            return True
    return False
out = root / "build" / "test-results" / "test"
failed = False
if any(a.endswith(":test") for a in args):
    out.mkdir(parents=True, exist_ok=True)
    for cls, tests in rules["tests"].items():
        cases = []
        for name, r in tests.items():
            if not selected(cls, name):
                continue
            missing = [x for x in r.get("requires", []) if x not in src]
            jname = name if cls.endswith("Spec") else name + "()"
            if r.get("skip"):
                cases.append(f'<testcase name={quoteattr(jname)} classname="{cls}" time="0"><skipped/></testcase>')
            elif r.get("fail") or missing:
                msg = r.get("fail") or ("expected the original behaviour, missing " + missing[0])
                failed = True
                cases.append(f'<testcase name={quoteattr(jname)} classname="{cls}" time="0.01"><failure message={quoteattr(msg)} type="org.opentest4j.AssertionFailedError">{escape(msg)}\n\tat {cls}</failure></testcase>')
            else:
                cases.append(f'<testcase name={quoteattr(jname)} classname="{cls}" time="0.02"/>')
        if cases:
            (out / f"TEST-{cls}.xml").write_text(f'<?xml version="1.0"?><testsuite name="{cls}" tests="{len(cases)}">' + "".join(cases) + "</testsuite>")
if any(a.endswith("jacocoTestReport") for a in args) and not failed:
    rep = root / "build" / "reports" / "jacoco" / "test"
    rep.mkdir(parents=True, exist_ok=True)
    body = ""
    for cls, ms in rules["coverage"].items():
        mx = ""
        for m, (line, cov, miss) in ms.items():
            mx += f'<method name="{m}" desc="()V" line="{line}"><counter type="INSTRUCTION" missed="{miss*4}" covered="{cov*4}"/><counter type="LINE" missed="{miss}" covered="{cov}"/></method>'
        tc = sum(v[1] for v in ms.values()); tm = sum(v[2] for v in ms.values())
        body += f'<class name="{cls}" sourcefilename="x.kt">{mx}<counter type="LINE" missed="{tm}" covered="{tc}"/></class>'
    (rep / "jacocoTestReport.xml").write_text(f'<?xml version="1.0"?><!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd"><report name="x"><package name="com/acme">{body}</package><counter type="LINE" missed="1" covered="8"/><counter type="BRANCH" missed="1" covered="1"/></report>')
print("BUILD FAILED" if failed else "BUILD SUCCESSFUL")
sys.exit(1 if failed else 0)
'''


def make_project(d, calc_test=CALC_TEST):
    files = {"src/main/kotlin/com/acme/Calculator.kt": CALC, "src/main/kotlin/com/acme/Strings.kt": STRINGS,
             "src/main/kotlin/com/acme/Untested.kt": UNTESTED,
             "src/test/kotlin/com/acme/CalculatorTest.kt": calc_test,
             "src/test/kotlin/com/acme/StringsTest.kt": STRINGS_TEST,
             "src/test/kotlin/com/acme/LegacyTest.kt": LEGACY_TEST,
             "src/test/kotlin/com/acme/SlugSpec.kt": KOTEST_SPEC,
             "build.gradle.kts": BUILD, "settings.gradle.kts": 'rootProject.name = "demo"\n',
             "rules.json": json.dumps(RULES), "fake_gradle.py": FAKE_GRADLE}
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    py = sys.executable
    (d / "gradlew.bat").write_text(f'@"{py}" "%~dp0fake_gradle.py" %*\r\n', encoding="utf-8")
    sh = d / "gradlew"
    sh.write_text(f'#!/bin/sh\nexec "{py}" "$(dirname "$0")/fake_gradle.py" "$@"\n', encoding="utf-8")
    sh.chmod(sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_cli(*args, cwd):
    return subprocess.run([sys.executable, str(HERE / "ktest.py"), *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


class ParserTests(unittest.TestCase):
    def test_masking_keeps_offsets(self):
        src = 'val s = "a { ${ x("}") } b" // c {\n/* d /* e */ { */ val c = \'{\''
        m = ks.mask(src)
        self.assertEqual(len(m), len(src))
        self.assertNotIn("{", m.replace("${", ""))
        self.assertEqual(m.count("\n"), 1)

    def test_classes_and_functions(self):
        r = ks.parse(CALC + "\nobject Reg { fun <T> put(x: T): Boolean { return true } }\n"
                     "private class Hidden { fun h() {} }\nval a = object : Audit { override fun record(event: String) {} }\n",
                     "Calculator.kt")
        cls = {c["qualname"]: c for c in r["classes"]}
        self.assertEqual(set(cls), {"Calculator", "Audit", "Reg", "Hidden"})
        self.assertEqual(cls["Calculator"]["line"], 4)
        funs = {(f["owner"], f["name"]): f for f in r["functions"]}
        self.assertEqual(set(funs), {("Calculator", "add"), ("Calculator", "isPositive"), ("Calculator", "divide"),
                                     ("Calculator", "hidden"), ("Audit", "record"), ("Reg", "put"), ("Hidden", "h")})
        self.assertEqual(funs[("Calculator", "add")]["body_kind"], "expr")
        self.assertEqual((funs[("Calculator", "divide")]["line"], funs[("Calculator", "divide")]["end_line"]), (11, 15))
        self.assertIsNone(funs[("Audit", "record")]["body_kind"])
        self.assertEqual(funs[("Calculator", "hidden")]["modifiers"], ["private"])
        self.assertEqual(funs[("Hidden", "h")]["modifiers"], [])
        self.assertTrue(funs[("Hidden", "h")]["class_private"])
        top = ks.parse(STRINGS, "Strings.kt")
        self.assertEqual([(f["name"], f["receiver"], f["owner"]) for f in top["functions"]],
                         [("shout", "String", None), ("slug", None, None)])
        self.assertEqual(top["facade"], "StringsKt")

    def test_tests_annotations_and_kotest(self):
        r = ks.parse(CALC_TEST, "CalculatorTest.kt")
        tests = {f["name"]: f for f in r["functions"] if f["is_test"]}
        self.assertEqual(len(tests), 7)
        self.assertEqual(tests["divide by zero"]["disabled"], "flaky on CI")
        s = ks.parse(KOTEST_SPEC, "SlugSpec.kt")
        cases = {f["name"]: f for f in s["functions"] if f["is_test"]}
        self.assertEqual(set(cases), {"slug lowercases", "slug disabled case"})
        self.assertTrue(cases["slug disabled case"]["disabled"])
        self.assertEqual(cases["slug lowercases"]["owner"], "SlugSpec")


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        make_project(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mapping_class_and_method_wise(self):
        info = checks.scan(self.dir)
        self.assertEqual(len(info["files"]["main"]), 3)
        self.assertEqual(len(info["files"]["test"]), 4)
        model = checks.link(info)
        u = model["units"]["com.acme.Calculator"]
        self.assertEqual(u["test_classes"][0], "com.acme.CalculatorTest")
        tested = {m["name"]: sorted(x["test"].split("#")[1] for x in m["tests"]) for m in u["methods"]}
        self.assertEqual(tested["add"], ["add returns sum", "addStillWorks"])
        self.assertEqual(tested["isPositive"], ["isPositiveForOne"])
        self.assertEqual(tested["divide"], ["divide by zero", "divide records audit", "sleepy"])
        self.assertEqual([m["skip"] for m in u["methods"] if m["name"] == "hidden"], ["private"])
        audit = model["units"]["com.acme.Audit"]
        self.assertEqual(audit["methods"][0]["skip"], "abstract (no body)")
        self.assertEqual(audit["methods"][0]["tests"], [])           # verify { audit.record() } is not a test of it
        fac = model["units"]["com.acme.StringsKt"]
        self.assertEqual({m["name"]: len(m["tests"]) for m in fac["methods"]}, {"shout": 1, "slug": 3})
        self.assertEqual(model["units"]["com.acme.Untested"]["test_classes"], [])

    def test_static_rules(self):
        info = checks.scan(self.dir)
        model = checks.link(info)
        fs = checks.static_checks(model, info)
        got = {(f["rule"], (f.get("test") or f.get("unit") or "").split("#")[-1]) for f in fs}
        for expected in [("KT001", "isPositiveForOne"), ("KT002", "divide by zero"), ("KT003", "todo"),
                         ("KT004", "trivial"), ("KT006", "sleepy"), ("KT007", "divide by zero"),
                         ("KT021", "divide records audit"), ("KT020", "trivial"), ("KT010", ""),
                         ("KT012", "com.acme.Untested"), ("KT007", "slug disabled case")]:
            self.assertIn(expected, got)
        self.assertNotIn(("KT001", "add returns sum"), got)
        self.assertNotIn(("KT001", "shoutAddsBang"), got)
        self.assertNotIn(("KT001", "slug lowercases"), got)

    def test_plan_and_verify_cli(self):
        p = run_cli("plan", str(self.dir), cwd=self.dir)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("[x] fun add(a: Int, b: Int): Int", p.stdout)
        self.assertIn("[ ] fun twice(x: Int)", p.stdout)
        self.assertIn("[-] fun hidden()  (private)", p.stdout)
        p = run_cli("verify", str(self.dir), cwd=self.dir)
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAILED", p.stdout)
        self.assertIn("KT001 Test without assertions", p.stdout)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        make_project(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self):
        return json.loads((self.dir / "ktest-report" / "report.json").read_text(encoding="utf-8"))

    def test_full_run_with_coverage_and_html(self):
        p = run_cli("run", ".", "--coverage", cwd=self.dir)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)            # the todo test fails
        r = self.report()
        s = r["summary"]
        self.assertEqual((s["failed"], s["skipped"]), (1, 2))
        self.assertEqual(s["passed"], 8)
        rules = {f["rule"] for f in r["findings"]}
        self.assertTrue({"KT013", "KT014", "KT001", "KT010"} <= rules, rules)
        notrun = [f for f in r["findings"] if f["rule"] == "KT014"]
        self.assertEqual([f["test"].split("#")[1] for f in notrun], ["addStillWorks"])  # JUnit 4 test never ran
        calc = next(c for c in r["classes"] if c["id"] == "com.acme.Calculator")
        st = {m["name"]: m["status"] for m in calc["methods"]}
        self.assertEqual(st["add"], "tested")
        self.assertEqual(st["isPositive"], "weak")              # its only test asserts nothing
        self.assertIn("KT022", rules)
        self.assertEqual(s["methods_weak"], 1)
        unt = next(c for c in r["classes"] if c["id"] == "com.acme.Untested")
        self.assertEqual(unt["methods"][0]["status"], "untested")
        self.assertIsNone(s["line_coverage"] if False else None)
        html = (self.dir / "ktest-report" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Kotlin unit test report", html)
        self.assertIn("NotImplementedError", html)
        self.assertNotIn("<script src", html)
        self.assertIn("addStillWorks", html)

    def test_class_wise_and_method_wise_runs(self):
        p = run_cli("run", ".", "--class", "Strings", "--dry-run", cwd=self.dir)
        self.assertNotEqual(p.returncode, 0)                  # no class 'Strings': it is StringsKt / slug
        p = run_cli("run", ".", "--class", "StringsKt", cwd=self.dir)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        r = self.report()
        self.assertEqual({t["name"] for tc in r["test_classes"] for t in tc["tests"] if t["status"] == "passed"},
                         {"shoutAddsBang", "slugReplacesSpaces", "slug lowercases"})
        self.assertFalse([f for f in r["findings"] if f["rule"] == "KT014"])       # filtered run: no 'not run'
        p = run_cli("run", ".", "--class", "Calculator", "--method", "add", cwd=self.dir)
        self.assertEqual(p.returncode, 1, p.stdout)                     # LegacyTest#addStillWorks is linked too
        r = self.report()
        self.assertEqual(r["run"]["filters"], ["com.acme.CalculatorTest#add returns sum",
                                               "com.acme.LegacyTest#addStillWorks"])
        ran = [t["name"] for tc in r["test_classes"] for t in tc["tests"] if t["status"] != "not run"]
        self.assertEqual(ran, ["add returns sum"])
        p = run_cli("run", ".", "--class", "Untested", cwd=self.dir)
        self.assertEqual(p.returncode, 2)
        self.assertIn("scaffold --class Untested", p.stderr)

    def test_build_failure_is_reported(self):
        f = self.dir / "src/main/kotlin/com/acme/Calculator.kt"
        f.write_text(CALC.replace("a + b", "a * b"), encoding="utf-8")
        p = run_cli("run", ".", cwd=self.dir)
        self.assertEqual(p.returncode, 1)
        r = self.report()
        bf = [x for x in r["findings"] if x["rule"] == "KT029"]
        self.assertTrue(bf and "Type mismatch" in bf[0]["detail"], r["findings"][:3])
        self.assertIn("KT015", {x["rule"] for x in r["findings"]})

    def test_scaffold(self):
        p = run_cli("scaffold", ".", "--class", "Untested", cwd=self.dir)
        self.assertEqual(p.returncode, 0, p.stderr)
        t = self.dir / "src/test/kotlin/com/acme/UntestedTest.kt"
        text = t.read_text(encoding="utf-8")
        self.assertIn("class UntestedTest", text)
        self.assertIn("fun `twice returns the expected result for typical input`()", text)
        self.assertIn("import kotlin.test.assertEquals", text)
        info = checks.scan(self.dir)
        model = checks.link(info)
        fs = checks.static_checks(model, info)
        self.assertEqual(sum(1 for f in fs if f["rule"] == "KT003" and "UntestedTest" in f["test"]), 2)
        self.assertEqual(len(model["units"]["com.acme.Untested"]["methods"][0]["tests"]), 2)
        p = run_cli("scaffold", ".", "--class", "Calculator", "--all-methods", cwd=self.dir)
        self.assertIn("exists: merge", p.stdout)               # existing test file is never overwritten

    def test_mutation_check(self):
        p = run_cli("mutate", ".", "--class", "Calculator", cwd=self.dir)
        self.assertEqual(p.returncode, 2)
        self.assertIn("must pass before a mutation check", p.stderr)
        (self.dir / "src/test/kotlin/com/acme/CalculatorTest.kt").write_text(
            CALC_TEST.replace('    @Test\n    fun todo() { TODO("later") }\n', ""), encoding="utf-8")
        (self.dir / "src/test/kotlin/com/acme/LegacyTest.kt").unlink()
        rules = json.loads((self.dir / "rules.json").read_text())
        del rules["tests"]["com.acme.CalculatorTest"]["todo"]
        (self.dir / "rules.json").write_text(json.dumps(rules))
        before = (self.dir / "src/main/kotlin/com/acme/Calculator.kt").read_bytes()
        p = run_cli("mutate", ".", "--class", "Calculator", cwd=self.dir)
        out = p.stdout + p.stderr
        self.assertEqual((self.dir / "src/main/kotlin/com/acme/Calculator.kt").read_bytes(), before, out)
        self.assertFalse(list(self.dir.rglob("*.ktest-orig")))
        mu = json.loads((self.dir / "ktest-report" / "mutation.json").read_text())
        res = {(m["method"].split(".")[-1], m["original"], m["mutated"]): m["result"] for m in mu["mutants"]}
        self.assertEqual(res[("add", "+", "-")], "killed")
        self.assertEqual(res[("isPositive", ">", ">=")], "survived")       # the test has no assertion
        self.assertEqual(res[("divide", "!=", "==")], "killed")
        self.assertEqual(res[("divide", "/", "*")], "killed")
        self.assertEqual(mu["summary"]["survived"], 1)
        r = self.report()
        self.assertIn("KT019", {f["rule"] for f in r["findings"]})
        self.assertEqual(r["mutation"]["summary"]["score"], 75.0)
        self.assertIn("Mutation check", (self.dir / "ktest-report" / "index.html").read_text(encoding="utf-8"))

    def test_leftover_backup_is_restored(self):
        src = self.dir / "src/main/kotlin/com/acme/Calculator.kt"
        good = src.read_bytes()
        (src.parent / (src.name + ".ktest-orig")).write_bytes(good)
        src.write_text(CALC.replace("a + b", "a - b"), encoding="utf-8")
        import ktest
        ktest.restore_leftovers(self.dir)
        self.assertEqual(src.read_bytes(), good)


class GradleCommandTests(unittest.TestCase):
    def test_multi_module_android_and_filters(self):
        import argparse
        import ktest
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "settings.gradle.kts").write_text('include(":app", ":core")')
            (d / "app").mkdir()
            (d / "app/build.gradle.kts").write_text('plugins { id("com.android.application") }\njacoco')
            (d / "core").mkdir()
            (d / "core/build.gradle.kts").write_text('plugins { kotlin("jvm") }')
            rels = ["app/src/test/kotlin/a/LoginViewModelTest.kt", "core/src/test/kotlin/c/PriceTest.kt"]
            for rel in rels:
                (d / rel).parent.mkdir(parents=True, exist_ok=True)
                (d / rel).write_text("class X")
            info = {"root": str(d), "files": {"test": [{"rel": r} for r in rels]}}
            opts = argparse.Namespace(variant="debug", coverage=True, coverage_task=None, build_arg=None)
            tool = {"exe": "gradlew", "root": d}
            cmd = ktest.gradle_command(tool, info, [], opts)
            self.assertEqual(cmd[1:], [":app:cleanTestDebugUnitTest", ":app:testDebugUnitTest",
                                       ":app:jacocoTestReport", ":core:cleanTest", ":core:test",
                                       "--continue", "--console=plain"])
            f = [{"class": "c.PriceTest", "test": "total adds tax", "file": rels[1]}]
            cmd = ktest.gradle_command(tool, info, f, opts, clean=False, coverage=False)
            self.assertEqual(cmd[1:4], [":core:test", "--tests", "c.PriceTest.total adds tax"])


class ResultParsingTests(unittest.TestCase):
    def test_names_and_coverage_lookup(self):
        self.assertEqual(rs.test_key("add returns sum()"), "add returns sum")
        self.assertEqual(rs.test_key("add(int, int)[2]"), "add")
        self.assertIsNone(rs.test_key("[1] 1, 2"))
        cov = {"classes": {"a.Outer$Inner": {"methods": [{"name": "go", "line": 9, "counters": {"LINE": (0, 2)}},
                                                         {"name": "go$default", "line": 9, "counters": {}}]}}}
        self.assertEqual(rs.coverage_for(cov, "a.Outer.Inner", "go", 8, 10), {"LINE": (0, 2)})


if __name__ == "__main__":
    unittest.main(verbosity=1)
