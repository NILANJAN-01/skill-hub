#!/usr/bin/env python3
"""Tests for capture_and_convert.py using a fake adb (no device needed).
Run: python test_capture_and_convert.py   (standard library only)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = str(HERE / "capture_and_convert.py")
FAKE_ADB = str(HERE / "testing" / "fake_adb.py")
DUMP = str(HERE / "fixtures" / "automotive_media.xml")


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "adbstate"
        self.env = dict(os.environ, FAKE_ADB_STATE=str(self.state), FAKE_ADB_DUMP=DUMP,
                        FAKE_ADB_DEVICES="emulator-5554:device",
                        FAKE_ADB_FOCUS="com.example.oem.media/.MainActivity")
        self.env.pop("ANDROID_SERIAL", None)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, stdin=None, **env):
        e = dict(self.env, **env)
        return subprocess.run([sys.executable, SCRIPT, "--adb", FAKE_ADB, "--retry-delay", "0", *args],
                              cwd=self.dir, env=e, input=stdin, capture_output=True, text=True, encoding="utf-8")

    def calls(self):
        return (self.state / "calls.log").read_text(encoding="utf-8").splitlines()

    def test_capture_names_screen_from_foreground_app(self):
        p = self.cli()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        xml = self.dir / "dumps" / "media_mainactivity.xml"
        js = self.dir / "locators" / "media_mainactivity.locators.json"
        self.assertTrue(xml.is_file())
        data = json.loads(js.read_text(encoding="utf-8"))
        self.assertEqual(data["keywords"]["back"], "com.example.oem.media:id/back")
        calls = self.calls()
        self.assertIn("-s emulator-5554 shell uiautomator dump /sdcard/skillhub_window_dump.xml", calls)
        self.assertTrue(any(c.startswith("-s emulator-5554 pull /sdcard/skillhub_window_dump.xml") for c in calls))
        self.assertIn("-s emulator-5554 shell rm -f /sdcard/skillhub_window_dump.xml", calls)

    def test_custom_name_and_no_overwrite(self):
        self.assertEqual(self.cli("--name", "Media Home").returncode, 0)
        self.assertTrue((self.dir / "locators" / "media_home.locators.json").is_file())
        p = self.cli("--name", "Media Home")                      # same name again -> timestamped copy
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(list((self.dir / "dumps").glob("media_home*.xml"))), 2)
        p = self.cli("--name", "Media Home", "--overwrite")
        self.assertEqual(len(list((self.dir / "dumps").glob("media_home*.xml"))), 2)

    def test_retries_when_ui_is_not_idle(self):
        p = self.cli("--name", "busy", FAKE_ADB_IDLE_FAILS="2")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout.count("retrying"), 2)
        self.assertTrue((self.dir / "locators" / "busy.locators.json").is_file())

    def test_gives_up_with_advice(self):
        p = self.cli("--name", "busy", "--retries", "2", FAKE_ADB_IDLE_FAILS="5")
        self.assertEqual(p.returncode, 1)
        self.assertIn("could not get idle state", p.stderr)
        self.assertIn("animating", p.stderr)

    def test_no_device_and_unauthorized(self):
        p = self.cli(FAKE_ADB_DEVICES="")
        self.assertEqual(p.returncode, 1)
        self.assertIn("No device ready", p.stderr)
        p = self.cli(FAKE_ADB_DEVICES="R58M:unauthorized")
        self.assertIn("Allow USB debugging", p.stderr)

    def test_several_devices_need_serial(self):
        two = "emulator-5554:device,R58M:device"
        p = self.cli(FAKE_ADB_DEVICES=two)
        self.assertEqual(p.returncode, 1)
        self.assertIn("--serial", p.stderr)
        p = self.cli("--serial", "R58M", "--name", "x", FAKE_ADB_DEVICES=two)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("-s R58M shell uiautomator dump /sdcard/skillhub_window_dump.xml", self.calls())

    def test_adb_missing(self):
        p = subprocess.run([sys.executable, SCRIPT, "--adb", str(self.dir / "no-such-adb")], cwd=self.dir,
                           env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 1)
        self.assertIn("adb not found", p.stderr)

    def test_converter_options_and_dump_args_pass_through(self):
        p = self.cli("--name", "bar", "--exclude-package", "com.android.systemui", "--format", "keywords",
                     "--dump-arg=--compressed")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads((self.dir / "locators" / "bar.locators.json").read_text(encoding="utf-8"))
        self.assertIn("back", data)
        self.assertNotIn("systemui_back", data)
        self.assertIn("-s emulator-5554 shell uiautomator dump --compressed /sdcard/skillhub_window_dump.xml",
                      self.calls())

    def test_interactive_captures_several_screens(self):
        p = self.cli("--interactive", stdin="home\n\nq\n")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Captured 2 screen(s)", p.stdout)
        names = sorted(f.name for f in (self.dir / "locators").iterdir())
        self.assertEqual(names, ["home.locators.json", "media_mainactivity.locators.json"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
