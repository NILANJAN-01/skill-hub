#!/usr/bin/env python3
"""Tests for uia_scaffold.py. Standard library only.
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
import uia_scaffold  # noqa: E402

FIX = HERE / "fixtures"
SCRIPT = str(HERE / "uia_scaffold.py")


def cli(*argv):
    return subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, encoding="utf-8")


def write_project(files):
    d = tempfile.mkdtemp()
    for rel, text in files.items():
        p = Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


class CheckTests(unittest.TestCase):
    def test_missing_setup_reports_snippet(self):
        d = write_project({"settings.gradle.kts": 'include(":app")',
                           "app/build.gradle.kts": 'plugins { id("com.android.application") }\n'
                                                   'android { buildFeatures { compose = true } }'})
        rep = uia_scaffold.check(d)
        app = rep["modules"][0]
        self.assertFalse(rep["ok"])
        self.assertEqual(app["type"], "application")
        self.assertTrue(any("uiautomator" in m for m in app["missing"]))
        self.assertTrue(any("testInstrumentationRunner" in m for m in app["missing"]))
        self.assertTrue(any("testTagsAsResourceId" in n for n in app["notes"]))
        p = cli("check", d)
        self.assertEqual(p.returncode, 1)
        self.assertIn('androidTestImplementation("androidx.test.uiautomator:uiautomator:2.4.1")', p.stdout)

    def test_complete_setup_with_version_catalog(self):
        d = write_project({
            "settings.gradle": "include ':app'",
            "gradle/libs.versions.toml": '[versions]\nui = "2.4.1"\njunit = "1.3.0"\n[libraries]\n'
                                         'androidx-test-uiautomator = { module = "androidx.test.uiautomator:uiautomator",'
                                         ' version.ref = "ui" }\n'
                                         'androidx-junit = { group = "androidx.test.ext", name = "junit", '
                                         'version.ref = "junit" }\n',
            "app/build.gradle": "plugins { id 'com.android.application' }\n"
                                "android { defaultConfig { testInstrumentationRunner "
                                "\"androidx.test.runner.AndroidJUnitRunner\" } }\n"
                                "dependencies { androidTestImplementation libs.androidx.test.uiautomator\n"
                                "  androidTestImplementation libs.androidx.junit }",
            "app/src/androidTest/java/.keep": ""})
        rep = uia_scaffold.check(d)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["modules"][0]["uiautomator"], "2.4.1")

    def test_test_module_needs_target(self):
        d = write_project({"settings.gradle.kts": 'include(":benchmark")',
                           "benchmark/build.gradle.kts": 'plugins { id("com.android.test") }\n'
                                                         'dependencies { androidTestImplementation('
                                                         '"androidx.test.uiautomator:uiautomator:2.4.1") }'})
        mod = uia_scaffold.check(d)["modules"][0]
        self.assertEqual(mod["type"], "test")
        self.assertTrue(any("targetProjectPath" in m for m in mod["missing"]))

    def test_deps_snippets(self):
        for dsl in ("kts", "groovy", "toml"):
            out = cli("deps", "--dsl", dsl).stdout
            self.assertIn("2.4.1", out)
            self.assertIn("AndroidJUnitRunner", out)


class ElementTests(unittest.TestCase):
    def test_dump_without_ids_uses_text_desc_and_class(self):
        elems = uia_scaffold.elements_from_dump(str(FIX / "compose_login.xml"))
        elems = uia_scaffold.name_elements(uia_scaffold.disambiguate(uia_scaffold.filter_elements(elems, False)),
                                           "kotlin")
        preds = [uia_scaffold.kotlin_predicate(e) for e in elems]
        self.assertIn('contentDescription?.toString() == "Email"', preds)
        self.assertIn('textAsString() == "Sign in" && className?.toString() == "android.widget.Button"', preds)
        self.assertTrue(all(e.get("instance") is None for e in elems))

    def test_locators_json_groups_and_rows(self):
        elems = uia_scaffold.elements_from_locators(str(FIX / "phone_settings.locators.json"))
        elems = uia_scaffold.name_elements(uia_scaffold.filter_elements(elems, False), "java")
        sels = {e["member"]: uia_scaffold.java_selector(e) for e in elems}
        self.assertEqual(sels["homepageTitle"], 'By.res("com.android.settings:id/homepage_title")')
        self.assertEqual(sels["titleNetworkInternet"], 'By.res("android:id/title").text("Network & internet")')
        self.assertTrue(any(e.get("occurrences") for e in elems))

    def test_names_avoid_keywords_and_digits(self):
        elems = [{"keyword": "", "resource_id": "", "text": "class", "desc": "", "class": "", "clickable": True,
                  "scrollable": False, "strategy": "text", "instance": None, "occurrences": None},
                 {"keyword": "", "resource_id": "", "text": "1st", "desc": "", "class": "", "clickable": True,
                  "scrollable": False, "strategy": "text", "instance": None, "occurrences": None}]
        names = [e["member"] for e in uia_scaffold.name_elements(elems, "kotlin")]
        self.assertEqual(names, ["classElement", "el1st"])

    def test_kotlin_string_escaping(self):
        e = {"resource_id": "", "text": 'Pay $5 "now"', "desc": "", "strategy": "text"}
        self.assertEqual(uia_scaffold.kotlin_predicate(e), 'textAsString() == "Pay \\$5 \\"now\\""')

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            uia_scaffold.elements_from_dump(str(HERE / "uia_scaffold.py"))
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "other.json"
            bad.write_text(json.dumps({"keywords": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                uia_scaffold.elements_from_locators(str(bad))


class GenerateTests(unittest.TestCase):
    def test_kotlin_test_and_page(self):
        p = cli("new", "--name", "LoginTest", "--package", "com.example.login", "--app", "com.example.composeapp",
                "--dump", str(FIX / "compose_login.xml"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("fun appStartsAndShowsItsUi() = uiAutomator {", p.stdout)
        self.assertIn("import androidx.test.uiautomator.watcher.PermissionDialog", p.stdout)
        self.assertIn("class LoginScreen(private val ui: UiAutomatorTestScope)", p.stdout)
        self.assertIn("val screen = LoginScreen(this)", p.stdout)
        self.assertIn("no resource-ids", p.stderr)

    def test_java_files_written_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            args = ["new", "--name", "SettingsTest", "--lang", "java", "--package", "com.example.settings.test",
                    "--app", "com.android.settings", "--locators", str(FIX / "phone_settings.locators.json"),
                    "--out", d]
            self.assertEqual(cli(*args).returncode, 0)
            base = Path(d) / "com" / "example" / "settings" / "test"
            test = (base / "SettingsTest.java").read_text(encoding="utf-8")
            page = (base / "SettingsScreen.java").read_text(encoding="utf-8")
            self.assertIn("UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())", test)
            self.assertIn("SettingsScreen screen = new SettingsScreen(device);", test)
            self.assertIn("device.wait(Until.findObject(selector), TIMEOUT_MS)", page)
            self.assertNotIn("UiSelector", test + page)
            self.assertEqual(cli(*args).returncode, 2)            # exists -> refused
            self.assertEqual(cli(*args, "--force").returncode, 0)

    def test_benchmark_and_baseline_kotlin_only(self):
        p = cli("new", "--name", "StartupBenchmark", "--kind", "benchmark", "--package", "com.example.bench",
                "--app", "com.example.app")
        self.assertIn("MacrobenchmarkRule()", p.stdout)
        self.assertIn("StartupTimingMetric()", p.stdout)
        self.assertIn("startApp(TARGET_PACKAGE)", p.stdout)
        self.assertIn("FrameTimingMetric()", p.stdout)
        p = cli("new", "--name", "BaselineProfileGenerator", "--kind", "baseline-profile", "--package", "com.example",
                "--app", "com.example.app")
        self.assertIn("baselineProfileRule.collect(", p.stdout)
        self.assertIn("includeInStartupProfile = true", p.stdout)
        p = cli("new", "--name", "StartupBenchmark", "--kind", "benchmark", "--lang", "java", "--package", "a.b",
                "--app", "a.b")
        self.assertEqual(p.returncode, 2)

    def test_validation(self):
        self.assertEqual(cli("new", "--name", "lower", "--package", "a.b", "--app", "a.b").returncode, 2)
        self.assertEqual(cli("new", "--name", "Ok", "--package", "a..b", "--app", "a.b").returncode, 2)
        self.assertEqual(cli("new", "--name", "Ok", "--kind", "page", "--package", "a.b", "--app", "a.b").returncode, 2)


if __name__ == "__main__":
    unittest.main()
