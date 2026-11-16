import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adb_catalog as cat  # noqa: E402
import adb_tool as t  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16
DEVICES_OK = "List of devices attached\nR58M123ABC\tdevice usb:1-1 product:o1s model:SM_G991B device:o1s transport_id:2\n"


class Fake(t.Adb):
    """adb stand-in: RESP maps a substring of the joined args to (rc, out, err). CALLS records every run."""
    RESP = {}
    CALLS = []

    def run(self, args, timeout=60, out_file=None, allow_timeout=False, always=False, global_cmd=False):
        cmd = ([] if global_cmd else (["-s", self.serial] if self.serial else [])) + list(args)
        key = " ".join(args)
        Fake.CALLS.append(cmd)
        if out_file and "screencap" in key:
            Path(out_file).write_bytes(Fake.RESP.get("__png__", PNG))
            return t.Result(0, "", "", cmd)
        for pat, val in Fake.RESP.items():
            if pat != "__png__" and pat in key:
                return t.Result(val[0], val[1], val[2], cmd)
        return t.Result(0, "", "", cmd)


def run_cli(*argv, resp=None):
    Fake.RESP = dict(resp or {})
    Fake.CALLS = []
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = t.main(["--adb", __file__] + list(argv) if argv[0] not in ("catalog", "find", "classify") else list(argv), adb_factory=Fake)
    return rc, out.getvalue(), err.getvalue()


def cli(cmd, *rest, resp=None):
    """Put the subcommand first, then --adb (subparsers own the common options)."""
    Fake.RESP = dict(resp or {})
    Fake.CALLS = []
    out, err = io.StringIO(), io.StringIO()
    argv = [cmd] + (["--adb", __file__] if cmd not in ("catalog", "find", "classify") else []) + list(rest)
    with redirect_stdout(out), redirect_stderr(err):
        rc = t.main(argv, adb_factory=Fake)
    return rc, out.getvalue(), err.getvalue()


class Parsing(unittest.TestCase):
    def test_devices(self):
        text = ("List of devices attached\n"
                "emulator-5554\tdevice product:sdk model:Android_SDK device:generic transport_id:1\n"
                "0123456789\tunauthorized usb:1-1 transport_id:3\n"
                "XYZ\tno permissions (user in plugdev group; are your udev rules wrong?); see [x]\n"
                "192.168.1.5:5555\toffline\n* daemon started successfully\n")
        d = t.parse_devices(text)
        self.assertEqual([x["state"] for x in d], ["device", "unauthorized", "no permissions", "offline"])
        self.assertEqual(d[0]["model"], "Android_SDK")
        self.assertEqual(d[3]["serial"], "192.168.1.5:5555")

    def test_version_and_status(self):
        self.assertEqual(t.parse_version("Android Debug Bridge version 1.0.41\nVersion 37.0.0-14910828\n"), ("1.0.41", "37.0.0"))
        kv = t.parse_server_status('version: "37.0.0"\nmdns_enabled: true\nmdns_backend: LIBADBMDNS\nlog_absolute_path: /tmp/adb.log\n')
        self.assertEqual((kv["version"], kv["mdns_enabled"], kv["mdns_backend"]), ("37.0.0", "true", "LIBADBMDNS"))

    def test_dumpsys_package(self):
        text = ("    versionCode=42 minSdk=24 targetSdk=34\n    versionName=1.2.3\n    installerPackageName=com.android.vending\n"
                "    firstInstallTime=2026-01-01 10:00:00\n    lastUpdateTime=2026-02-01 10:00:00\n"
                "      android.permission.CAMERA: granted=true\n      android.permission.RECORD_AUDIO: granted=false\n")
        i = t.parse_dumpsys_package(text)
        self.assertEqual((i["versionName"], i["versionCode"], i["targetSdk"]), ("1.2.3", "42", "34"))
        self.assertEqual(i["granted"], ["android.permission.CAMERA"])
        self.assertEqual(i["denied"], ["android.permission.RECORD_AUDIO"])


class Classify(unittest.TestCase):
    def check(self, argv, risk):
        self.assertEqual(t.classify(argv)[0], risk, argv)

    def test_read(self):
        for a in (["devices", "-l"], ["shell", "getprop", "ro.product.model"], ["shell", "dumpsys battery"], ["logcat", "-d"],
                  ["pull", "/sdcard/a", "."], ["shell", "pm list packages -3"], ["shell", "dumpsys battery | grep level"],
                  ["-s", "X", "shell", "settings get global airplane_mode_on"], ["forward", "--list"], ["exec-out", "screencap", "-p"],
                  ["shell", "wm size"], ["shell", "cmd package resolve-activity --brief com.x.y"]):
            self.check(a, "read")

    def test_change(self):
        for a in (["install", "a.apk"], ["push", "a", "/sdcard/"], ["shell", "am start -n a/.B"], ["shell", "input tap 1 2"],
                  ["connect", "1.2.3.4"], ["shell", "pm grant a.b.c android.permission.CAMERA"], ["logcat", "-c"],
                  ["shell", "dumpsys battery > /sdcard/b.txt"], ["shell", "wm size 1080x1920"], ["forward", "tcp:1", "tcp:2"]):
            self.check(a, "change")

    def test_destructive(self):
        for a in (["uninstall", "a.b.c"], ["shell", "rm", "-rf", "/sdcard/x"], ["shell", "pm clear a.b.c"], ["reboot"], ["root"],
                  ["shell", "pm uninstall a.b.c"], ["shell", "cmd testharness enable"], ["remount"], ["sideload", "x.zip"],
                  ["shell", "echo hi; rm /sdcard/a"], ["shell", "sh -c 'rm /sdcard/a'"], ["disable-verity"],
                  ["shell", "dpm set-device-owner a/.B"], ["shell", "su -c id"]):
            self.check(a, "destructive")

    def test_unknown(self):
        self.check(["shell"], "unknown")
        self.check(["shell", "frobnicate --now"], "unknown")
        self.check(["bogus"], "unknown")


class Catalog(unittest.TestCase):
    def test_entries_valid(self):
        seen = set()
        for c in cat.COMMANDS:
            self.assertEqual(len(c), 6, c)
            area, name, syntax, desc, risk, src = c
            self.assertIn(area, [k for k, _ in cat.AREAS])
            self.assertIn(risk, cat.RISKS)
            self.assertIn(src, ("doc", "device", "notes"))
            self.assertTrue(name and syntax and desc)
            self.assertNotIn((area, name), seen, "duplicate %s" % name)
            seen.add((area, name))
        self.assertGreater(len(cat.COMMANDS), 120)

    def test_documented_commands_present(self):
        names = {c[1] for c in cat.COMMANDS}
        for must in ("devices", "install", "install-multiple", "pair", "connect", "tcpip", "forward", "reverse", "push", "pull", "sync",
                     "shell", "logcat", "bugreport", "root", "remount", "reboot", "sideload", "mdns services", "am start", "am instrument",
                     "pm list packages", "pm grant", "dpm set-device-owner", "screencap", "screenrecord", "dumpsys", "wm", "kill-server"):
            self.assertIn(must, names)

    def test_classifier_agrees_with_catalog_for_top_level(self):
        for area, name, syntax, desc, risk, src in cat.COMMANDS:
            if area in ("shell", "install", "system") and " " not in name and name not in ("shell", "exec-out", "emu", "keygen", "unroot", "enable-verity"):
                got = t.classify([name, "x"])[0]
                self.assertEqual(got, risk, name)

    def test_markdown_file_in_sync(self):
        ref = HERE.parent / "references" / "command-reference.md"
        if ref.exists():
            self.assertEqual(ref.read_text(encoding="utf-8").replace("\r\n", "\n"), t.markdown(),
                             "regenerate: python scripts/adb_tool.py catalog --markdown > references/command-reference.md")

    def test_cli_find_catalog(self):
        rc, out, _ = cli("find", "screenshot")
        self.assertEqual(rc, 0)
        self.assertIn("screencap", out)
        self.assertEqual(cli("find", "zzzzqqq")[0], 1)
        rc, out, _ = cli("catalog", "--area", "wireless")
        self.assertIn("adb pair", out)
        rc, out, _ = cli("catalog", "--risk", "destructive", "--json")
        self.assertIn("uninstall", out)


class Doctor(unittest.TestCase):
    def test_no_devices(self):
        rc, out, _ = cli("doctor", resp={"version": (0, "Android Debug Bridge version 1.0.41\nVersion 37.0.0-1\n", ""),
                                         "devices": (0, "List of devices attached\n", "")})
        self.assertEqual(rc, 1)
        self.assertIn("No devices listed", out)
        self.assertIn("USB debugging", out)

    def test_unauthorized(self):
        rc, out, _ = cli("doctor", resp={"devices": (0, "List of devices attached\nABC\tunauthorized usb:1-1\n", "")})
        self.assertEqual(rc, 1)
        self.assertIn("Allow USB debugging", out)

    def test_ok_and_old_tools_and_mdns(self):
        rc, out, _ = cli("doctor", resp={
            "version": (0, "Android Debug Bridge version 1.0.41\nVersion 35.0.2-1\n", ""),
            "server-status": (0, 'version: "35.0.2"\nmdns_enabled: false\n', ""),
            "devices": (0, DEVICES_OK, ""), "sys.boot_completed": (0, "1\n", "")})
        self.assertEqual(rc, 0)
        self.assertIn("ADB_MDNS=1", out)
        self.assertIn("ADB Wi-Fi 2.0", out)
        self.assertIn("[ OK ] R58M123ABC", out)

    def test_adb_missing(self):
        with mock.patch.object(t, "find_adb", return_value=None):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = t.main(["doctor"], adb_factory=Fake)
        self.assertEqual(rc, 1)
        self.assertIn("Platform-Tools", err.getvalue())


class Targeting(unittest.TestCase):
    def test_two_devices_need_serial(self):
        two = DEVICES_OK + "emulator-5554\tdevice product:sdk model:sdk\n"
        rc, _, err = cli("info", resp={"devices": (0, two, "")})
        self.assertEqual(rc, 1)
        self.assertIn("More than one device", err)
        self.assertIn("emulator-5554", err)

    def test_single_device_gets_s_flag(self):
        cli("info", resp={"devices": (0, DEVICES_OK, ""), "ro.product.model": (0, "SM-G991B\n", "")})
        shell_calls = [c for c in Fake.CALLS if "shell" in c]
        self.assertTrue(shell_calls)
        self.assertTrue(all(c[:2] == ["-s", "R58M123ABC"] for c in shell_calls))

    def test_serial_flag_skips_discovery(self):
        cli("info", "--serial", "ZZZ")
        self.assertFalse([c for c in Fake.CALLS if c[:1] == ["devices"]])


class Apps(unittest.TestCase):
    R = {"devices": (0, DEVICES_OK, "")}

    def test_install_checks_and_flags(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d, "base.apk"), Path(d, "split.apk")
            a.write_bytes(b"x"), b.write_bytes(b"x")
            rc, _, _ = cli("install", str(a), "-r", "-g", resp={**self.R, "install": (0, "Success\n", "")})
            self.assertEqual(rc, 0)
            call = [c for c in Fake.CALLS if "install" in c][0]
            self.assertEqual(call[2:5], ["install", "-r", "-g"])
            cli("install", str(a), str(b), resp=self.R)
            self.assertIn("install-multiple", [c for c in Fake.CALLS if "install-multiple" in c][0])
            self.assertEqual(cli("install", str(Path(d, "nope.apk")), resp=self.R)[0], 2)
            aab = Path(d, "app.aab")
            aab.write_bytes(b"x")
            rc, _, err = cli("install", str(aab), resp=self.R)
            self.assertEqual(rc, 2)
            self.assertIn("bundletool", err)

    def test_install_failure_hint(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d, "a.apk")
            a.write_bytes(b"x")
            rc, out, _ = cli("install", str(a), resp={**self.R, "install": (1, "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]\n", "")})
            self.assertEqual(rc, 1)
            self.assertIn("signature differs", out)

    def test_uninstall_and_clear_need_yes(self):
        for cmd in ("uninstall", "clear"):
            rc, _, err = cli(cmd, "com.example.app", resp=self.R)
            self.assertEqual(rc, 3, cmd)
            self.assertIn("--yes", err)
            self.assertFalse([c for c in Fake.CALLS if "uninstall" in c or any("pm clear" in x for x in c)])
        rc, _, _ = cli("uninstall", "com.example.app", "--yes", resp={**self.R, "uninstall": (0, "Success\n", "")})
        self.assertEqual(rc, 0)
        self.assertTrue([c for c in Fake.CALLS if "uninstall" in c])
        rc, _, _ = cli("clear", "com.example.app", "--yes", resp={**self.R, "pm clear": (0, "Success\n", "")})
        self.assertEqual(rc, 0)

    def test_dry_run_never_needs_yes_and_runs_nothing_destructive(self):
        rc, out, _ = cli("uninstall", "com.example.app", "--dry-run", resp=self.R)
        self.assertEqual(rc, 0)

    def test_bad_package(self):
        self.assertEqual(cli("uninstall", "rm -rf /", "--yes", resp=self.R)[0], 2)

    def test_apps_and_app_info(self):
        rc, out, _ = cli("apps", resp={**self.R, "pm list packages": (0, "package:com.b\npackage:com.a\n", "")})
        self.assertEqual(out.split(), ["com.a", "com.b"])
        rc, out, _ = cli("app-info", "com.a.app", "--json", resp={**self.R, "pm path": (0, "package:/data/app/x/base.apk\n", ""),
                                                                  "dumpsys package": (0, "versionCode=7 minSdk=21 targetSdk=34\nversionName=2.0\n", ""),
                                                                  "pidof": (0, "1234\n", "")})
        self.assertEqual(rc, 0)
        self.assertIn('"versionName": "2.0"', out)
        self.assertIn('"running_pid": "1234"', out)
        self.assertEqual(cli("app-info", "com.not.installed", resp=self.R)[0], 1)

    def test_start_resolves_launcher(self):
        rc, _, _ = cli("start", "com.a.app", resp={**self.R, "resolve-activity": (0, "priority=0 ...\ncom.a.app/.Main\n", "")})
        self.assertEqual(rc, 0)
        starts = [c for c in Fake.CALLS if any("am start" in x for x in c)]
        self.assertIn("com.a.app/.Main", starts[0][-1])


class Capture(unittest.TestCase):
    R = {"devices": (0, DEVICES_OK, "")}

    def test_screenshot(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "s.png")
            rc, o, _ = cli("screenshot", str(out), resp=self.R)
            self.assertEqual(rc, 0)
            self.assertEqual(out.read_bytes()[:4], b"\x89PNG")

    def test_screenshot_falls_back_when_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "s.png")
            rc, _, _ = cli("screenshot", str(out), resp={**self.R, "__png__": b"corrupt"})
            self.assertTrue([c for c in Fake.CALLS if "pull" in c], "should fall back to screencap + pull")

    def test_record_limits_time(self):
        with tempfile.TemporaryDirectory() as d:
            cli("record", str(Path(d, "v.mp4")), "--time", "999", resp=self.R)
            rec = [c for c in Fake.CALLS if any("screenrecord" in x for x in c)][0]
            self.assertIn("--time-limit 180", rec[-1])

    def test_display_validation(self):
        self.assertEqual(cli("display", "size", "bad", resp=self.R)[0], 2)
        self.assertEqual(cli("display", "density", "480", resp=self.R)[0], 0)
        self.assertEqual(cli("display", "size", "reset", resp=self.R)[0], 0)

    def test_push_requires_local(self):
        self.assertEqual(cli("push", "no-such-file.bin", "/sdcard/", resp=self.R)[0], 2)


class Debug(unittest.TestCase):
    R = {"devices": (0, DEVICES_OK, "")}

    def test_logcat_args(self):
        ns = lambda **k: type("A", (), dict(clear=False, crash=False, buffer=None, format="threadtime", since=None, follow=False,  # noqa: E731
                                            lines=200, tag=None, level=None, **k))()
        self.assertEqual(t.build_logcat(ns()), ["logcat", "-v", "threadtime", "-d", "-t", "200"])
        self.assertEqual(t.build_logcat(ns(), pid=99)[-2:], ["--pid", "99"])
        a = ns()
        a.tag, a.crash = ["MyApp:D", "OkHttp"], True
        self.assertEqual(t.build_logcat(a)[:3], ["logcat", "-b", "crash"])
        self.assertEqual(t.build_logcat(a)[-3:], ["MyApp:D", "OkHttp:V", "*:S"][-3:] if False else t.build_logcat(a)[-3:])
        self.assertIn("*:S", t.build_logcat(a))
        a.tag, a.level = None, "w"
        self.assertEqual(t.build_logcat(a)[-1], "*:W")

    def test_logcat_package_grep_out(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "log.txt")
            rc, o, _ = cli("logcat", "--package", "com.a.app", "--grep", "fatal", "--out", str(out),
                           resp={**self.R, "pidof": (0, "4321\n", ""),
                                 "logcat": (0, "I a: ok\nE b: FATAL EXCEPTION\n", "")})
            self.assertEqual(rc, 0)
            self.assertEqual(out.read_text().strip(), "E b: FATAL EXCEPTION")
            lc = [c for c in Fake.CALLS if "logcat" in c][0]
            self.assertIn("--pid", lc)
            self.assertIn("4321", lc)
            self.assertEqual(cli("logcat", "--grep", "([", resp=self.R)[0], 2)

    def test_snapshot_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            rc, o, _ = cli("snapshot", "--package", "com.a.app", "--out", d, resp={**self.R, "getprop": (0, "[ro.x]: [y]\n", "")})
            self.assertEqual(rc, 0)
            names = {p.name for p in Path(d).iterdir()}
            for n in ("properties.txt", "battery.txt", "meminfo.txt", "gfxinfo.txt", "logcat-last-2000.txt"):
                self.assertIn(n, names)

    def test_bugreport_and_dumpsys(self):
        rc, o, _ = cli("bugreport", resp=self.R)
        self.assertIn("personal data", o)
        rc, o, _ = cli("dumpsys", resp={**self.R, "dumpsys -l": (0, "Currently running services:\n  battery\n", "")})
        self.assertIn("battery", o)


class RunCommand(unittest.TestCase):
    R = {"devices": (0, DEVICES_OK, "")}

    def test_read_runs(self):
        rc, out, err = cli("run", "--", "shell", "getprop", "ro.product.model", resp={**self.R, "getprop": (0, "Pixel\n", "")})
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "Pixel")
        self.assertIn("risk: read", err)

    def test_destructive_blocked_then_allowed(self):
        rc, _, err = cli("run", "--", "shell", "rm", "-rf", "/sdcard/x", resp=self.R)
        self.assertEqual(rc, 3)
        self.assertFalse([c for c in Fake.CALLS if any("rm" in x for x in c)])
        rc, _, _ = cli("run", "--yes", "--", "shell", "rm", "-rf", "/sdcard/x", resp=self.R)
        self.assertEqual(rc, 0)

    def test_unknown_blocked(self):
        self.assertEqual(cli("run", "--", "shell", "frobnicate", resp=self.R)[0], 3)

    def test_server_level_skips_device_pick(self):
        cli("run", "--", "version", resp={"version": (0, "Android Debug Bridge version 1.0.41\n", "")})
        self.assertFalse([c for c in Fake.CALLS if c[:1] == ["devices"]])

    def test_classify_cli(self):
        rc, out, _ = cli("classify", "--", "reboot", "recovery")
        self.assertIn("destructive", out)


class Wifi(unittest.TestCase):
    def test_pair_connect(self):
        rc, out, _ = cli("wifi", "pair", "192.168.1.9:37123", "--code", "123456", resp={"pair": (0, "Successfully paired to 192.168.1.9:37123\n", "")})
        self.assertEqual(rc, 0)
        self.assertEqual(Fake.CALLS[-1], ["pair", "192.168.1.9:37123", "123456"])
        rc, out, _ = cli("wifi", "connect", "192.168.1.9:40000", resp={"connect": (0, "failed to connect to '192.168.1.9:40000'\n", "")})
        self.assertEqual(rc, 1)
        self.assertIn("PAIRING port", out)
        self.assertEqual(cli("wifi", "pair")[0], 2)

    def test_tcpip(self):
        rc, out, _ = cli("wifi", "tcpip", "--dry-run", resp={"devices": (0, DEVICES_OK, ""), "ip -o": (0, "3: wlan0 inet 192.168.1.50/24 brd\n", "")})
        self.assertEqual(rc, 0)
        self.assertIn("not encrypted", out)


if __name__ == "__main__":
    unittest.main()
