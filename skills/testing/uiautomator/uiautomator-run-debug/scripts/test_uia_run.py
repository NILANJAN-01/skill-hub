#!/usr/bin/env python3
"""Tests for uia_run.py with a fake adb (no device needed). Standard library only.
Run: python -m unittest discover -s . -p "test_*.py"
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uia_run  # noqa: E402

FIX = HERE / "fixtures"
FAKE_ADB = str(HERE / "testing" / "fake_adb.py")
SCRIPT = str(HERE / "uia_run.py")


class ParseTests(unittest.TestCase):
    def test_raw_mixed(self):
        rep = uia_run.summarise(uia_run.parse_any(str(FIX / "raw_mixed.txt")))
        self.assertEqual(rep["format"], "raw")
        self.assertEqual(rep["counts"], {"passed": 1, "failed": 2, "ignored": 1})
        causes = {f["test"].split("#")[1]: f["cause_id"] for f in rep["failures"]}
        self.assertEqual(causes, {"wrongPasswordShowsError": "element-not-found", "opensWifi": "null-uiobject2"})
        frames = [f["test_frame"] for f in rep["failures"]]
        self.assertIn("com.example.app.test.LoginTest$wrongPasswordShowsError$1.invoke(LoginTest.kt:41)", frames)
        self.assertEqual(rep["reported"], {"run": 3, "failures": 2})
        self.assertFalse(rep["ok"])

    def test_crash_marks_running_test_incomplete(self):
        rep = uia_run.summarise(uia_run.parse_any(str(FIX / "raw_crash.txt")))
        self.assertEqual(rep["counts"], {"incomplete": 1})
        self.assertEqual(rep["run_problems"][0]["cause_id"], "process-crashed")

    def test_missing_instrumentation(self):
        rep = uia_run.summarise(uia_run.parse_any(str(FIX / "raw_missing.txt")))
        self.assertEqual(rep["run_problems"][0]["cause_id"], "instrumentation-missing")

    def test_plain_output(self):
        rep = uia_run.summarise(uia_run.parse_any(str(FIX / "plain_failure.txt")))
        self.assertEqual(rep["format"], "plain")
        self.assertEqual(rep["failures"][0]["cause_id"], "stale-object")
        self.assertEqual(rep["reported"], {"run": 2, "failures": 1})

    def test_junit_xml(self):
        xml = next((FIX / "project").rglob("TEST-*.xml"))
        rep = uia_run.summarise(uia_run.parse_any(str(xml)))
        self.assertEqual(rep["format"], "junit")
        self.assertEqual(rep["counts"], {"passed": 1, "failed": 1, "ignored": 1})
        self.assertEqual(rep["failures"][0]["cause_id"], "uiautomation-busy")
        self.assertEqual(rep["device"], "Pixel_8(AVD) - 16")

    def test_all_passed(self):
        text = ("INSTRUMENTATION_STATUS: class=a.B\nINSTRUMENTATION_STATUS: test=t\nINSTRUMENTATION_STATUS_CODE: 1\n"
                "INSTRUMENTATION_STATUS: class=a.B\nINSTRUMENTATION_STATUS: test=t\nINSTRUMENTATION_STATUS_CODE: 0\n"
                "INSTRUMENTATION_RESULT: stream=\n\nOK (1 test)\n\nINSTRUMENTATION_CODE: -1\n")
        rep = uia_run.summarise(uia_run.parse_raw(text))
        self.assertTrue(rep["ok"])

    def test_classify_order(self):
        self.assertEqual(uia_run.classify("java.lang.AssertionError: expected:<5> but was:<4>")["id"], "assertion")
        self.assertEqual(uia_run.classify("ERROR: could not get idle state.")["id"], "idle-timeout")
        self.assertEqual(uia_run.classify("IllegalArgumentException: The intent launched `x` does not resolve to "
                                          "an activity")["id"], "intent-unresolved")
        self.assertEqual(uia_run.classify("something odd")["id"], "other")


class CommandTests(unittest.TestCase):
    def capture(self, *argv):
        return subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, encoding="utf-8")

    def test_adb_command_with_filters(self):
        p = self.capture("cmd", "--adb", "adb", "--serial", "emulator-5554", "--test-package", "com.example.test",
                         "--class", "com.example.LoginTest#signIn", "--annotation", "com.example.Smoke",
                         "--shards", "2", "--shard-index", "0")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(),
                         "adb -s emulator-5554 shell am instrument -w -r -e class 'com.example.LoginTest#signIn' "
                         "-e annotation com.example.Smoke -e numShards 2 -e shardIndex 0 "
                         "com.example.test/androidx.test.runner.AndroidJUnitRunner")

    def test_gradle_command(self):
        p = self.capture("cmd", "--gradle", "app", "--variant", "freeDebug", "--class", "com.example.LoginTest")
        self.assertIn(":app:connectedFreeDebugAndroidTest", p.stdout)
        self.assertIn("-Pandroid.testInstrumentationRunnerArguments.class=com.example.LoginTest", p.stdout)

    def test_bad_usage(self):
        self.assertEqual(self.capture("cmd", "--test-package", "x", "--shards", "2").returncode, 2)
        self.assertEqual(self.capture("cmd", "--runner", "no-slash").returncode, 2)
        self.assertEqual(self.capture("cmd", "--class", "a.B").returncode, 2)


class FakeDeviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "calls.log")
        self.env = dict(os.environ, FAKE_ADB_LOG=self.log, FAKE_ADB_OUTPUT=str(FIX / "raw_mixed.txt"))
        self.env.pop("ANDROID_SERIAL", None)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *argv, **env):
        return subprocess.run([sys.executable, SCRIPT, *argv, "--adb", FAKE_ADB], capture_output=True, text=True,
                              encoding="utf-8", env=dict(self.env, **env))

    def test_run_saves_output_and_summarises(self):
        out = os.path.join(self.tmp.name, "raw.txt")
        logcat = os.path.join(self.tmp.name, "logcat.txt")
        p = self.cli("run", "--test-package", "com.example.app.test", "--out", out, "--logcat", logcat, "--json")
        self.assertEqual(p.returncode, 1, p.stderr)
        rep = json.loads(p.stdout)
        self.assertEqual(len(rep["failures"]), 2)
        self.assertTrue(os.path.getsize(out) > 0)
        self.assertIn("FATAL EXCEPTION", Path(logcat).read_text(encoding="utf-8"))
        calls = Path(self.log).read_text(encoding="utf-8").splitlines()
        self.assertIn("-s emulator-5554 shell am instrument -w -r "
                      "com.example.app.test/androidx.test.runner.AndroidJUnitRunner", calls)

    def test_several_devices_need_serial(self):
        p = self.cli("run", "--test-package", "x", FAKE_ADB_DEVICES="a:device,b:device")
        self.assertEqual(p.returncode, 3)
        self.assertIn("--serial", p.stderr)

    def test_unauthorized_device(self):
        p = self.cli("run", "--test-package", "x", FAKE_ADB_DEVICES="R58M:unauthorized")
        self.assertEqual(p.returncode, 3)
        self.assertIn("unauthorized", p.stderr)

    def test_doctor_lists_instrumentations(self):
        p = self.cli("doctor")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("com.example.app.test/androidx.test.runner.AndroidJUnitRunner", p.stdout)
        self.assertIn("animations are on", p.stdout)

    def test_dry_run_does_not_call_am(self):
        p = self.cli("run", "--test-package", "x", "--dry-run")
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(self.log) and "am instrument" in Path(self.log).read_text(encoding="utf-8"))


class ResultsTests(unittest.TestCase):
    def test_results_finds_gradle_xml(self):
        p = subprocess.run([sys.executable, SCRIPT, "results", str(FIX / "project"), "--json"], capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["source"].endswith(".xml"))

    def test_results_without_xml(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, SCRIPT, "results", d], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
