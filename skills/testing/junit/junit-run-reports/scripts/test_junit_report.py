#!/usr/bin/env python3
"""Tests for junit_report.py. Standard library only; the run test uses a fake Gradle wrapper.
Run: python -m unittest discover -s . -p "test_*.py"
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import junit_report as jr  # noqa: E402

FIX = HERE / "fixtures"
GRADLE_XML = next((FIX / "gradle-project").rglob("TEST-*.xml"))
SUREFIRE_XML = next((FIX / "maven-project").rglob("TEST-*.xml"))
OPEN_XML = FIX / "open" / "open-test-report.xml"
SCRIPT = str(HERE / "junit_report.py")


def cli(*argv, cwd=None, env=None):
    return subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=env)


class ParseTests(unittest.TestCase):
    def test_gradle_legacy_xml(self):
        rep = jr.summarise(jr.parse_file(str(GRADLE_XML)))
        self.assertEqual(rep["total"], 7)                      # reducesPrice reported twice (retry) -> merged
        self.assertEqual(rep["counts"], {"passed": 3, "failed": 2, "error": 1, "skipped": 1})
        causes = {f["test"].split("#")[1]: f["cause_id"] for f in rep["failures"]}
        self.assertEqual(causes, {"[2] quantity=3, expected=30": "assertion", "exportsPriceList(Path)": "timeout",
                                  "loadsFixture(Path)": "parameter-resolution"})
        first = rep["failures"][0]
        self.assertEqual(first["expected_actual"], ("30", "27"))
        self.assertEqual(first["message"], "price for 3 ==> expected: <30> but was: <27>")
        self.assertEqual(first["at"], "com.example.shop.PriceCalculatorTest.pricePerQuantity(PriceCalculatorTest.java:48)")
        self.assertEqual([f["test"] for f in rep["flaky"]], ["com.example.shop.PriceCalculatorTest$WithDiscount#reducesPrice()"])
        self.assertEqual(rep["skipped_without_reason"], 1)
        self.assertEqual(rep["slowest"][0]["test"], "com.example.shop.PriceCalculatorTest#exportsPriceList(Path)")

    def test_surefire_reruns(self):
        rep = jr.summarise(jr.parse_file(str(SUREFIRE_XML)))
        self.assertEqual(rep["counts"], {"passed": 2, "failed": 1, "skipped": 1})
        self.assertEqual(rep["flaky"][0]["attempts"], ["failed", "passed"])
        self.assertEqual(rep["skipped"][0]["reason"], "old format removed in 3.0, see BILL-120")
        self.assertEqual(rep["failures"][0]["expected_actual"],
                         ("java.lang.IllegalArgumentException", "java.lang.IllegalStateException"))

    def test_open_test_reporting(self):
        tests = jr.parse_file(str(OPEN_XML))
        self.assertEqual(len(tests), 4)                        # containers are not tests
        rep = jr.summarise(tests)
        self.assertEqual(rep["counts"], {"passed": 1, "failed": 1, "skipped": 1, "error": 1})
        by = {f["test"]: f for f in rep["failures"]}
        self.assertEqual(by["com.example.shop.BasketTest#loads the catalog"]["cause_id"], "version-mismatch")
        self.assertEqual(by["com.example.shop.BasketTest#rejects more items"]["at"],
                         "com.example.shop.BasketTest.rejects more items(BasketTest.kt:44)")
        self.assertEqual(rep["skipped"][0]["reason"], "Assumption failed: CI is not set")
        self.assertAlmostEqual(rep["slowest"][0]["seconds"], 0.5)

    def test_hierarchical_format(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "report.xml"
            f.write_text('<h:execution xmlns:h="https://schemas.opentest4j.org/reporting/hierarchy/0.2.0" '
                         'xmlns="https://schemas.opentest4j.org/reporting/core/0.2.0">'
                         '<h:root name="JUnit Jupiter" duration="PT0.2S"><result status="SUCCESSFUL"/>'
                         '<h:child name="CalcTest" duration="PT0.1S"><result status="SUCCESSFUL"/>'
                         '<h:child name="adds()" duration="PT0.05S"><result status="SUCCESSFUL"/></h:child>'
                         '</h:child></h:root></h:execution>', encoding="utf-8")
            rep = jr.summarise(jr.parse_file(str(f)))
            self.assertEqual(rep["counts"], {"passed": 1})

    def test_not_a_report(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "pom.xml"
            f.write_text("<project/>", encoding="utf-8")
            with self.assertRaises(ValueError):
                jr.parse_file(str(f))

    def test_classify(self):
        self.assertEqual(jr.classify("org.mockito.exceptions.misusing.UnnecessaryStubbingException")["id"], "mockito")
        self.assertEqual(jr.classify("java.lang.NullPointerException")["id"], "null-pointer")
        self.assertEqual(jr.classify("org.junit.platform.commons.PreconditionViolationException: Configuration error: "
                                     "You must configure at least one set of arguments")["id"], "parameterized-config")
        self.assertEqual(jr.classify("MultipleFailuresError: person (2 failures)")["id"], "multiple-failures")
        self.assertEqual(jr.classify("Failed to load ApplicationContext")["id"], "spring-context")
        self.assertEqual(jr.classify("java.io.IOException: disk")["id"], "exception")


class CliTests(unittest.TestCase):
    def test_results_and_markdown(self):
        p = cli("results", str(FIX / "gradle-project"), "--markdown")
        self.assertEqual(p.returncode, 1)
        self.assertIn("| 7 | 3 | 2 | 1 | 1 | 1 |", p.stdout)
        p = cli("parse", str(FIX), "--json")
        data = json.loads(p.stdout)
        self.assertEqual(len(data["files"]), 3)

    def test_missing_reports(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cli("results", d).returncode, 2)
            self.assertEqual(cli("parse", d).returncode, 2)

    def test_truncated_xml(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "TEST-x.xml"
            f.write_text("<testsuite><testcase name='a'", encoding="utf-8")
            p = cli("parse", str(f))
            self.assertEqual(p.returncode, 2)
            self.assertIn("half-written", p.stderr)

    def test_commands(self):
        p = cli("cmd", "--tool", "maven", "--class", "a.B", "--method", "m", "--tag", "fast", "--rerun", "2")
        self.assertIn("-Dtest=a.B#m", p.stdout)
        self.assertIn("-Dsurefire.rerunFailingTestsCount=2", p.stdout)
        p = cli("cmd", "--tool", "gradle", "--class", "a.B#m", "--fail-fast")
        self.assertIn("--tests a.B.m --fail-fast", p.stdout)
        p = cli("cmd", "--tool", "console", "--package", "a.b", "--exclude-tag", "slow")
        self.assertIn("--select-package a.b --exclude-tag slow", p.stdout)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cli("cmd", "--project", d).returncode, 2)


class RunTests(unittest.TestCase):
    def make_project(self):
        d = Path(tempfile.mkdtemp())
        (d / "settings.gradle.kts").write_text('rootProject.name = "demo"\n', encoding="utf-8")
        fake = HERE / "testing" / "fake_build.py"
        if os.name == "nt":
            (d / "gradlew.bat").write_text('@"%s" "%s" %%*\r\n@exit /b %%ERRORLEVEL%%\r\n' % (sys.executable, fake),
                                           encoding="utf-8")
        else:
            w = d / "gradlew"
            w.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, fake), encoding="utf-8")
            w.chmod(w.stat().st_mode | stat.S_IEXEC)
        return d

    def test_run_summarises_new_reports(self):
        d = self.make_project()
        env = dict(os.environ, FAKE_BUILD_REPORT=str(GRADLE_XML), FAKE_BUILD_EXIT="1")
        p = cli("run", "--project", str(d), "--class", "com.example.shop.PriceCalculatorTest", "--json", env=env)
        self.assertEqual(p.returncode, 1, p.stderr)
        rep = json.loads(p.stdout)
        self.assertEqual(rep["total"], 7)
        log = (d / "fake-build.log").read_text(encoding="utf-8")
        self.assertIn("test --tests com.example.shop.PriceCalculatorTest", log)

    def test_run_without_reports(self):
        d = self.make_project()
        env = dict(os.environ, FAKE_BUILD_EXIT="1")
        env.pop("FAKE_BUILD_REPORT", None)
        p = cli("run", "--project", str(d), env=env)
        self.assertEqual(p.returncode, 1)
        self.assertIn("no new test reports", p.stderr)

    def test_dry_run(self):
        d = self.make_project()
        p = cli("run", "--project", str(d), "--dry-run", "--tag", "fast")
        self.assertEqual(p.returncode, 0)
        self.assertFalse((d / "fake-build.log").exists())


if __name__ == "__main__":
    unittest.main()
