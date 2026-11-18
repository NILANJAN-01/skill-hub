#!/usr/bin/env python3
"""Tests for uia_audit.py. Run: python -m unittest discover -s . -p "test_*.py" (standard library only)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uia_audit  # noqa: E402

LEGACY = str(HERE / "fixtures" / "legacy-project")
MODERN = str(HERE / "fixtures" / "modern-project")


def rules(rep):
    return {(f["rule"], f["file"].rsplit("/", 1)[-1], f["line"]) for f in rep["findings"]}


class LegacyProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = uia_audit.audit(LEGACY)
        cls.ids = {f["rule"] for f in cls.rep["findings"]}

    def test_counts_languages_and_dependency(self):
        self.assertEqual(self.rep["languages"], {"java": 1, "kt": 1})
        self.assertEqual(self.rep["dependencies"][0]["version"], "2.2.0")

    def test_legacy_java_apis(self):
        for rid in ("ui-selector", "ui-object", "ui-scrollable", "old-junit4-runner", "device-getinstance-noarg",
                    "compressed-typo", "dump-string", "watcher-leak", "not-found-exception", "wait-for-idle"):
            self.assertIn(rid, self.ids, rid)

    def test_flaky_patterns_with_lines(self):
        r = rules(self.rep)
        self.assertIn(("sleep", "SettingsTest.java", 33), r)
        self.assertIn(("coordinates", "SettingsTest.java", 34), r)
        self.assertIn(("findobject-chain", "SettingsTest.java", 35), r)

    def test_comment_is_ignored(self):
        self.assertNotIn(("sleep", "SettingsTest.java", 29), rules(self.rep))

    def test_alpha_dsl_names(self):
        r = rules(self.rep)
        self.assertIn(("permission-import", "AlphaDslTest.kt", 5), r)
        self.assertIn(("dsl-onview", "AlphaDslTest.kt", 15), r)
        self.assertIn(("predicate-short-id", "AlphaDslTest.kt", 15), r)
        self.assertIn(("predicate-text", "AlphaDslTest.kt", 16), r)
        self.assertIn(("dsl-clear-app-data-arg", "AlphaDslTest.kt", 17), r)
        self.assertIn(("dsl-start-intent", "AlphaDslTest.kt", 18), r)
        self.assertIn(("dsl-lowercase", "AlphaDslTest.kt", 22), r)
        self.assertIn(("predicate-desc", "AlphaDslTest.kt", 23), r)

    def test_old_version_is_error_when_dsl_is_used(self):
        f = [f for f in self.rep["findings"] if f["rule"] == "old-version"]
        self.assertEqual(f[0]["level"], "ERROR")
        self.assertEqual(f[0]["file"], "app/build.gradle")

    def test_errors_sorted_first(self):
        levels = [f["level"] for f in self.rep["findings"]]
        self.assertEqual(levels, sorted(levels, key={"ERROR": 0, "WARN": 1, "INFO": 2}.get))


class ModernProjectTests(unittest.TestCase):
    def test_clean_project_has_no_errors_or_warnings(self):
        rep = uia_audit.audit(MODERN)
        bad = [f for f in rep["findings"] if f["level"] != "INFO"]
        self.assertEqual(bad, [])
        self.assertEqual(rep["dependencies"][0]["version"], "2.4.1")

    def test_short_id_is_info_when_project_uses_test_tags(self):
        rep = uia_audit.audit(MODERN)
        f = [f for f in rep["findings"] if f["rule"] == "predicate-short-id"]
        self.assertEqual([x["level"] for x in f], ["INFO"])


class SnippetTests(unittest.TestCase):
    def write(self, files):
        d = tempfile.mkdtemp()
        for rel, text in files.items():
            p = Path(d) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return d

    def test_prerelease_version_in_kts(self):
        d = self.write({"app/build.gradle.kts":
                        'dependencies { androidTestImplementation("androidx.test.uiautomator:uiautomator:2.4.0-alpha05") }'})
        rep = uia_audit.audit(d)
        self.assertEqual([f["rule"] for f in rep["findings"]], ["prerelease-version"])

    def test_support_library_dependency(self):
        d = self.write({"app/build.gradle":
                        "androidTestImplementation 'com.android.support.test.uiautomator:uiautomator-v18:2.1.3'"})
        rep = uia_audit.audit(d)
        self.assertEqual(rep["findings"][0]["rule"], "support-library")

    def test_string_with_slashes_is_not_a_comment(self):
        d = self.write({"app/src/androidTest/java/A.java":
                        'import androidx.test.uiautomator.By;\nclass A { String u = "http://x"; void t() { Thread.sleep(1); } }'})
        rep = uia_audit.audit(d)
        self.assertIn("sleep", [f["rule"] for f in rep["findings"]])

    def test_config_and_display_leaks(self):
        d = self.write({"app/src/androidTest/java/B.kt":
                        "import androidx.test.uiautomator.Configurator\n"
                        "fun f() { Configurator.getInstance().setWaitForIdleTimeout(0)\n"
                        "Configurator.getInstance().setDefaultDisplayId(2) }"})
        ids = [f["rule"] for f in uia_audit.audit(d)["findings"]]
        self.assertIn("configurator-restore", ids)
        self.assertIn("display-id-leak", ids)

    def test_compose_two_arg_res(self):
        d = self.write({"app/src/main/java/M.kt": "Modifier.semantics { testTagsAsResourceId = true }",
                        "app/src/androidTest/java/T.java":
                        'import androidx.test.uiautomator.By;\nclass T { Object s = By.res("com.app", "list"); }'})
        self.assertIn("res-two-args-compose", [f["rule"] for f in uia_audit.audit(d)["findings"]])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(HERE / "uia_audit.py"), *args], capture_output=True, text=True,
                              encoding="utf-8")

    def test_exit_codes_and_json(self):
        self.assertEqual(self.run_cli(LEGACY).returncode, 1)
        p = self.run_cli(MODERN, "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("findings", json.loads(p.stdout))
        self.assertEqual(self.run_cli(os.path.join(MODERN, "missing")).returncode, 2)

    def test_only_filter(self):
        p = self.run_cli(LEGACY, "--only", "sleep", "--json")
        self.assertEqual({f["rule"] for f in json.loads(p.stdout)["findings"]}, {"sleep"})

    def test_rules_listing(self):
        p = self.run_cli("--rules")
        self.assertEqual(p.returncode, 0)
        self.assertIn("dsl-onview", p.stdout)


if __name__ == "__main__":
    unittest.main()
