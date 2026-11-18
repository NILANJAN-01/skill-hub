#!/usr/bin/env python3
"""Tests for junit_audit.py. Standard library only.
Run: python -m unittest discover -s . -p "test_*.py"
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import junit_audit  # noqa: E402

FIX = HERE / "fixtures"


def keys(rep):
    return {(f["rule"], f["file"].rsplit("/", 1)[-1], f["line"]) for f in rep["findings"]}


def rules(rep):
    return {f["rule"] for f in rep["findings"]}


def project(files):
    d = tempfile.mkdtemp()
    for rel, text in files.items():
        p = Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


class Junit4MavenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = junit_audit.audit(str(FIX / "junit4-maven"))

    def test_junit4_tests_are_not_run_without_vintage(self):
        self.assertIn("junit4-not-run", rules(self.rep))

    def test_surefire_and_java(self):
        self.assertIn(("surefire-too-old", "pom.xml", 30), keys(self.rep))
        self.assertIn("java-target-old", rules(self.rep))

    def test_junit4_constructs(self):
        k = keys(self.rep)
        self.assertIn(("junit4-expected", "InvoiceTest.java", 51), k)
        self.assertIn(("junit4-timeout", "InvoiceTest.java", 56), k)
        self.assertIn(("sleep", "InvoiceTest.java", 58), k)
        imports = [f for f in self.rep["findings"] if f["rule"] == "junit4-import"]
        self.assertEqual(len(imports), 10)
        fixes = {f["message"].split()[-1]: f["fix"] for f in imports}
        self.assertIn("@TempDir", fixes["org.junit.rules.TemporaryFolder"])
        self.assertIn("BeforeEach", fixes["org.junit.Before"])
        self.assertIn("LAST", fixes["org.junit.Assert.assertEquals"])

    def test_maven_property_version_resolved(self):
        d = {x["coordinate"]: x["version"] for x in self.rep["dependencies"]}
        self.assertEqual(d["org.junit.jupiter:junit-jupiter"], "6.1.3")

    def test_message_order_not_flagged_for_junit4_assert(self):
        self.assertNotIn("message-first", rules(self.rep))


class Junit5GradleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = junit_audit.audit(str(FIX / "junit5-gradle"))

    def test_structural_errors(self):
        k = keys(self.rep)
        for expected in [("beforeall-not-static", "OrderServiceTest.java", 24),
                         ("private-method", "OrderServiceTest.java", 29),
                         ("non-void-test", "OrderServiceTest.java", 34),
                         ("nested-static", "OrderServiceTest.java", 80),
                         ("beforeall-kotlin", "CartTest.kt", 12),
                         ("nested-not-inner", "CartTest.kt", 34)]:
            self.assertIn(expected, k)

    def test_junit6_breaking_changes(self):
        k = keys(self.rep)
        self.assertIn(("removed-alphanumeric", "OrderServiceTest.java", 18), k)
        self.assertIn(("deprecated-jre-constant", "OrderServiceTest.java", 73), k)
        self.assertIn(("removed-config", "build.gradle.kts", 21), k)
        self.assertIn(("platform-version-mix", "build.gradle.kts", 14), k)
        self.assertTrue({"no-params", "kotlin-too-old", "deprecated-migrationsupport"} <= rules(self.rep))

    def test_weak_tests(self):
        k = keys(self.rep)
        self.assertIn(("no-assertion", "OrderServiceTest.java", 39), k)
        self.assertIn(("no-assertion", "CartTest.kt", 29), k)
        self.assertIn(("message-first", "OrderServiceTest.java", 45), k)
        self.assertIn(("disabled-no-reason", "OrderServiceTest.java", 58), k)
        self.assertIn(("try-fail-catch", "OrderServiceTest.java", 49), k)
        self.assertNotIn(("no-assertion", "CartTest.kt", 36), k)       # expression body with assertEquals
        self.assertNotIn(("no-assertion", "OrderServiceTest.java", 66), k)   # multi-line @CsvSource test

    def test_multiline_annotation_keeps_parameterized_test(self):
        self.assertEqual(self.rep["test_methods"], 12)


class CleanProjectTests(unittest.TestCase):
    def test_no_findings(self):
        rep = junit_audit.audit(str(FIX / "junit6-clean"))
        self.assertEqual(rep["findings"], [])
        self.assertEqual(rep["languages"], {"java": 1, "kt": 1})


class SnippetTests(unittest.TestCase):
    def test_mixed_junit4_and_jupiter(self):
        d = project({"src/test/java/A.java": "import org.junit.Test;\nimport org.junit.jupiter.api.BeforeEach;\n"
                                             "class A { @BeforeEach void s() {} @Test public void t() { } }"})
        self.assertIn("mixed-junit4-jupiter", rules(junit_audit.audit(d)))

    def test_gradle_without_use_junit_platform_and_launcher(self):
        d = project({"build.gradle": "dependencies { testImplementation 'org.junit.jupiter:junit-jupiter:6.1.3' }"})
        r = rules(junit_audit.audit(d))
        self.assertIn("no-use-junit-platform", r)
        self.assertIn("no-launcher", r)

    def test_android_hint(self):
        d = project({"app/build.gradle.kts": 'plugins { id("com.android.application") }\nandroid { }\n'
                                             'dependencies { testImplementation("org.junit.jupiter:junit-jupiter:6.1.3") }'})
        f = [x for x in junit_audit.audit(d)["findings"] if x["rule"] == "no-use-junit-platform"][0]
        self.assertIn("unitTests.all", f["fix"])

    def test_api_without_engine(self):
        d = project({"build.gradle.kts": 'dependencies { testImplementation("org.junit.jupiter:junit-jupiter-api:6.1.3") }\n'
                                         'tasks.test { useJUnitPlatform() }'})
        self.assertIn("no-engine", rules(junit_audit.audit(d)))

    def test_old_toolchain_and_version_catalog(self):
        d = project({"gradle/libs.versions.toml": '[versions]\njunit = "6.0.1"\n[libraries]\n'
                                                  'junit-bom = { module = "org.junit:junit-bom", version.ref = "junit" }\n',
                     "build.gradle.kts": "dependencies { testImplementation(platform(libs.junit.bom)) }\n"
                                         "kotlin { jvmToolchain(11) }\ntasks.test { useJUnitPlatform() }"})
        rep = junit_audit.audit(d)
        self.assertIn("junit6-patch", rules(rep))
        self.assertEqual(rep["dependencies"][0]["version"], "6.0.1")

    def test_per_class_default_in_properties(self):
        d = project({"src/test/resources/junit-platform.properties":
                     "junit.jupiter.testinstance.lifecycle.default = per_class\n",
                     "src/test/java/A.java": "import org.junit.jupiter.api.*;\nclass A {\n @BeforeAll void s() {}\n"
                                             " @Test void t() { Assertions.assertTrue(true); }\n}"})
        self.assertNotIn("beforeall-not-static", rules(junit_audit.audit(d)))

    def test_comments_and_strings_ignored(self):
        d = project({"src/test/java/A.java": 'import org.junit.jupiter.api.Test;\nclass A {\n'
                                             ' // Thread.sleep(10);\n @Test void t() { String s = "Thread.sleep(1)";'
                                             ' org.junit.jupiter.api.Assertions.assertNotNull(s); }\n}'})
        rep = junit_audit.audit(d)
        self.assertNotIn("sleep", [f["rule"] for f in rep["findings"] if f["line"] == 3])

    def test_brace_on_next_line(self):
        d = project({"src/test/java/A.java": "import org.junit.jupiter.api.Test;\nclass A\n{\n  @Test\n  void t()\n"
                                             "  {\n    int x = 1;\n  }\n  @Test\n  void u()\n  {\n"
                                             "    org.junit.jupiter.api.Assertions.assertEquals(1, 1);\n  }\n}"})
        nos = [f["line"] for f in junit_audit.audit(d)["findings"] if f["rule"] == "no-assertion"]
        self.assertEqual(nos, [5])


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(HERE / "junit_audit.py"), *args], capture_output=True, text=True,
                              encoding="utf-8")

    def test_exit_codes(self):
        self.assertEqual(self.cli(str(FIX / "junit5-gradle")).returncode, 1)
        self.assertEqual(self.cli(str(FIX / "junit6-clean")).returncode, 0)
        self.assertEqual(self.cli(str(FIX / "nope")).returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.cli(d).returncode, 2)

    def test_json_only_and_rules(self):
        p = self.cli(str(FIX / "junit4-maven"), "--json", "--only", "sleep")
        self.assertEqual({f["rule"] for f in json.loads(p.stdout)["findings"]}, {"sleep"})
        self.assertIn("removed-alphanumeric", self.cli("--rules").stdout)


if __name__ == "__main__":
    unittest.main()
