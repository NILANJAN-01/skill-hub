"""Tests for logcat_analyzer.py. Standard library only; no device or adb needed.

    python -m unittest discover -s scripts -p "test_*.py"
"""
import gzip
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import logcat_analyzer as la  # noqa: E402

APP = os.path.join(HERE, "fixtures", "app_crash.txt")
SYSTEM = os.path.join(HERE, "fixtures", "system_issues.txt")


def read(path, mode="r"):
    with (open(path, "rb") if mode == "rb" else io.open(path, encoding="utf-8")) as f:
        return f.read()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = la.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def analyze(*argv):
    code, out, err = run(*(list(argv) + ["--json"]))
    assert code in (0, 1), err
    return json.loads(out)


def group(result, kind, process=None):
    found = [g for g in result["groups"] if g["type"] == kind and (process is None or g["process"] == process)]
    assert found, "no %s group for %s in %s" % (kind, process, [(g["type"], g["process"]) for g in result["groups"]])
    return found[0]


class ParseTest(unittest.TestCase):
    def test_threadtime(self):
        e, st = la.parse_lines(["11-12 10:00:02.501  4321  4322 E AndroidRuntime: FATAL EXCEPTION: main"])
        self.assertEqual((e[0].date, e[0].time, e[0].pid, e[0].tid, e[0].level, e[0].tag, e[0].msg),
                         ("11-12", "10:00:02.501", 4321, 4322, "E", "AndroidRuntime", "FATAL EXCEPTION: main"))
        self.assertEqual(st["formats"], {"threadtime": 1})

    def test_threadtime_with_year_uid_and_padded_tag(self):
        e, _ = la.parse_lines([
            "2026-11-12 10:00:02.501  4321  4321 I Process : Sending signal. PID: 4321 SIG: 9",
            "11-12 10:00:02.501 u0_a123  4321  4322 W Tag: with: colons",
            "11-12 10:00:02.501  1000  4321  4322 W Tag:",
        ])
        self.assertEqual((e[0].tag, e[0].date, e[0].msg), ("Process", "11-12", "Sending signal. PID: 4321 SIG: 9"))
        self.assertEqual((e[1].pid, e[1].tid, e[1].tag, e[1].msg), (4321, 4322, "Tag", "with: colons"))
        self.assertEqual((e[2].pid, e[2].tid, e[2].msg), (4321, 4322, ""))

    def test_time_and_brief(self):
        e, st = la.parse_lines([
            "11-12 10:00:02.501 E/AndroidRuntime( 4321): FATAL EXCEPTION: main",
            "E/AndroidRuntime( 4321): Process: com.a, PID: 4321",
            "some other text",
        ])
        self.assertEqual((e[0].pid, e[0].tag, e[0].level), (4321, "AndroidRuntime", "E"))
        self.assertEqual((e[1].pid, e[1].date, e[1].msg), (4321, None, "Process: com.a, PID: 4321"))
        self.assertEqual(st["skipped"], 1)

    def test_studio_format_with_continuation_lines(self):
        text = [
            "2026-11-12 10:00:02.501  4321-4321  AndroidRuntime          com.example.shop                     E  FATAL EXCEPTION: main",
            "                                                                                                    Process: com.example.shop, PID: 4321",
            "                                                                                                    java.lang.IllegalStateException: boom",
            "                                                                                                    \tat com.example.shop.Main.onCreate(Main.kt:9)",
        ]
        e, _ = la.parse_lines(text)
        self.assertEqual(len(e), 4)
        a = la.Analyzer(e)
        issues = a.run()
        self.assertEqual([(x.kind, x.process) for x in issues], [("java_crash", "com.example.shop")])
        self.assertEqual(issues[0].fields["Top app frame"], "com.example.shop.Main.onCreate(Main.kt:9)")

    def test_utf16_file(self):
        d = tempfile.mkdtemp()
        try:
            for enc in ("utf-16", "utf-16-le"):
                p = os.path.join(d, enc + ".txt")
                with io.open(APP, encoding="utf-8") as f, io.open(p, "w", encoding=enc) as g:
                    g.write(f.read())
                self.assertEqual(analyze(p)["counts"]["java_crash"], 2, enc)
        finally:
            shutil.rmtree(d)

    def test_gzip_and_bugreport_zip(self):
        d = tempfile.mkdtemp()
        try:
            data = read(APP, "rb")
            gz = os.path.join(d, "log.txt.gz")
            with gzip.open(gz, "wb") as f:
                f.write(data)
            self.assertEqual(analyze(gz)["counts"]["java_crash"], 2)
            zp = os.path.join(d, "bugreport.zip")
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("bugreport-device-2026.txt", b"== dumpstate ==\n------ SYSTEM LOG ------\n" + data)
                z.writestr("version.txt", "2.0")
                z.writestr("FS/data/anr/anr_1", "ignored")
            r = analyze(zp)
            self.assertEqual(r["counts"]["java_crash"], 2)
            self.assertEqual(len(r["sources"]), 1)
        finally:
            shutil.rmtree(d)


class AppCrashTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = analyze(APP)

    def test_fatal_exception_grouped(self):
        g = group(self.r, "java_crash")
        self.assertEqual(g["id"], 1)
        self.assertEqual((g["severity"], g["count"], g["process"], g["pids"]),
                         ("critical", 2, "com.example.shop", [4321, 4400]))
        self.assertTrue(g["title"].startswith("java.lang.NullPointerException"))
        self.assertEqual(g["fields"]["Thread"], "main")
        self.assertTrue(g["fields"]["Exception"].startswith("java.lang.RuntimeException: Unable to start service"))
        self.assertEqual(g["fields"]["Top app frame"], "com.example.shop.sync.SyncService.onStartCommand(SyncService.kt:42)")
        self.assertEqual(g["fields"]["Last activity shown"], "com.example.shop/.MainActivity")
        self.assertIn("null", g["hint"])
        self.assertEqual(g["first_at"], "line 19")
        self.assertTrue(any("process died" in x for x in g["related"]))
        self.assertTrue(any("FATAL EXCEPTION" in x for x in g["stack"]))
        self.assertTrue(any("Shutting down VM" in x for x in g["before"]))
        self.assertFalse(any("FATAL" in x for x in g["before"]))

    def test_service_restart_linked_to_crash(self):
        gs = [g for g in self.r["groups"] if g["type"] == "service_crash"]
        self.assertEqual(len(gs), 2)
        restart = [g for g in gs if "restart in 1000 ms" in g["title"]][0]
        self.assertEqual(restart["severity"], "high")
        self.assertIn("Fatal exception", restart["fields"]["Cause"])
        self.assertIn("line 19", restart["fields"]["Cause"])
        loop = [g for g in gs if "crashed 2 times" in g["title"]][0]
        self.assertEqual(loop["fields"]["Service"], "com.example.shop/.sync.SyncService")

    def test_no_process_death_reported_for_explained_deaths(self):
        self.assertNotIn("process_death", self.r["counts"])

    def test_non_fatal_exceptions(self):
        gs = [g for g in self.r["groups"] if g["type"] == "exception"]
        self.assertEqual(len(gs), 2)
        by = dict((g["title"].split(":")[0], g) for g in gs)
        ise = by["java.lang.IllegalStateException"]
        self.assertEqual(ise["fields"]["Log message"], "Failed to refresh cart")
        self.assertEqual(ise["fields"]["Top app frame"], "com.example.shop.cart.CartRepository.refresh(CartRepository.kt:77)")
        net = by["java.net.SocketTimeoutException"]
        self.assertEqual(net["fields"]["Top app frame"], "com.example.shop.net.ApiClient.fetchCart(ApiClient.kt:58)")
        self.assertEqual(net["process"], "com.example.shop")

    def test_fatal_stack_is_not_reported_twice(self):
        for g in self.r["groups"]:
            if g["type"] in ("exception", "exception_mention"):
                self.assertNotIn("Unable to start service", g["title"])

    def test_jank_threshold_and_mention(self):
        g = group(self.r, "jank")
        self.assertEqual((g["count"], g["title"]), (1, "Main thread skipped 142 frames"))
        self.assertEqual(group(analyze(APP, "--jank-frames", "10"), "jank")["count"], 2)
        self.assertIn("PaymentException", group(self.r, "exception_mention")["title"])

    def test_timeline_is_chronological(self):
        times = [t["time"] for t in self.r["timeline"]]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(times), 8)


class SystemIssuesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = analyze(SYSTEM, "--min-severity", "info")

    def test_anr(self):
        g = group(self.r, "anr")
        self.assertEqual((g["process"], g["pids"], g["count"], g["severity"]), ("com.example.player", [5001], 1, "critical"))
        self.assertTrue(g["fields"]["Reason"].startswith("Input dispatching timed out"))
        self.assertEqual(g["fields"]["Component"], "com.example.player/.ui.PlayerActivity")
        self.assertEqual(g["fields"]["Trace file"], "/data/anr/anr_2026-11-12-11-00-21-000")
        self.assertIn("98% 5001/com.example.player", g["fields"]["Top CPU"])
        self.assertIn("busy computing", g["fields"]["CPU reading"])
        self.assertIn("main thread", g["hint"])
        self.assertTrue(any("user request after error" in x for x in g["related"]))
        self.assertTrue(any("decoding cover art" in x for x in g["before"]))

    def test_anr_event_is_not_counted_twice(self):
        self.assertEqual(self.r["counts"]["anr"], 1)

    def test_service_restart_after_anr(self):
        g = group(self.r, "service_crash", "com.example.player")
        self.assertEqual(g["severity"], "high")
        self.assertIn("ANR", g["fields"]["Cause"])

    def test_native_crash(self):
        g = group(self.r, "native_crash", "com.example.camera")
        self.assertEqual(g["pids"], [6001])
        self.assertEqual(g["title"], "SIGSEGV (SEGV_MAPERR) in libimgproc.so (ImageFilter::apply(unsigned char*, int)+44)")
        self.assertEqual(g["fields"]["Thread"], "RenderThread (tid 6020)")
        self.assertEqual(g["fields"]["Cause"], "null pointer dereference")
        self.assertEqual(g["fields"]["Tombstone"], "/data/tombstones/tombstone_07")
        self.assertIn("ndk-stack", g["hint"])
        self.assertTrue(any("process died" in x for x in g["related"]))

    def test_fatal_signal_without_tombstone(self):
        self.assertEqual(self.r["counts"]["native_crash"], 2)
        g = [x for x in self.r["groups"] if x["type"] == "native_crash" and x["pids"] == [8100]][0]
        self.assertIn("SIGABRT", g["title"])
        self.assertIn("no tombstone", g["title"])

    def test_crash_from_events_buffer(self):
        g = group(self.r, "java_crash", "com.example.widget")
        self.assertEqual(g["title"], "java.lang.IllegalArgumentException: bad id")
        self.assertEqual(g["fields"]["Thrown at"], "WidgetProvider.java:31")

    def test_kills_and_deaths(self):
        lmk = group(self.r, "lmk", "com.example.maps")
        self.assertEqual(lmk["severity"], "high")
        self.assertIn("low watermark", lmk["fields"]["Reason"])
        kill = group(self.r, "kill", "com.example.notes")
        self.assertEqual(kill["severity"], "info")
        deaths = [g for g in self.r["groups"] if g["type"] == "process_death"]
        self.assertEqual([(g["process"], g["severity"]) for g in deaths], [("com.example.clock", "high")])

    def test_init_service_and_watchdog(self):
        g = group(self.r, "service_crash", "vendor.gnss-hal")
        self.assertIn("received signal 6 (SIGABRT)", g["title"])
        self.assertFalse(any("bootanim" in x["title"] for x in self.r["groups"]))
        w = group(self.r, "watchdog")
        self.assertEqual((w["severity"], w["process"]), ("critical", "system_server"))

    def test_other_findings(self):
        self.assertIn("com.example.mail/.FetchService", group(self.r, "service_blocked")["title"])
        self.assertEqual(group(self.r, "selinux")["title"], "SELinux denied { read } untrusted_app -> proc_stat (file)")
        self.assertEqual(group(self.r, "strictmode")["title"],
                         "StrictMode DiskReadViolation at com.example.mail.Prefs.load(Prefs.kt:20)")
        self.assertIn("wtf", group(self.r, "fatal_log")["title"])
        self.assertIn("parcel size", group(self.r, "binder")["title"])

    def test_groups_are_sorted_by_severity(self):
        ranks = [la.SEV_RANK[g["severity"]] for g in self.r["groups"]]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual([g["id"] for g in self.r["groups"]], list(range(1, len(ranks) + 1)))


class FilterAndCliTest(unittest.TestCase):
    def test_default_hides_info(self):
        self.assertNotIn("kill", analyze(SYSTEM)["counts"])

    def test_package_filter(self):
        r = analyze(SYSTEM, "--package", "com.example.player")
        self.assertEqual(sorted(r["counts"]), ["anr", "service_crash"])
        r = analyze(SYSTEM, "--package", "com.example.mail")
        self.assertEqual(sorted(r["counts"]), ["selinux", "service_blocked", "strictmode"])

    def test_only_filter(self):
        self.assertEqual(sorted(analyze(SYSTEM, "--only", "crash,anr")["counts"]), ["anr", "java_crash", "native_crash"])
        self.assertEqual(sorted(analyze(APP, "--only", "service")["counts"]), ["service_crash"])
        code, _, err = run(SYSTEM, "--only", "nonsense")
        self.assertEqual(code, 2)
        self.assertIn("unknown type", err)

    def test_time_filter(self):
        r = analyze(SYSTEM, "--since", "11:06:00", "--until", "11-12 11:06:59")
        self.assertNotIn("anr", r["counts"])
        self.assertNotIn("watchdog", r["counts"])
        self.assertEqual(r["counts"]["lmk"], 1)
        self.assertEqual(run(SYSTEM, "--since", "yesterday")[0], 2)

    def test_two_files(self):
        r = analyze(APP, SYSTEM)
        self.assertEqual(r["counts"]["java_crash"], 3)
        self.assertEqual(group(r, "anr")["first_at"], "system_issues.txt:5")

    def test_text_report_and_show(self):
        code, out, _ = run(APP)
        self.assertEqual(code, 0)
        self.assertIn("Result: 2 fatal exceptions, 2 service crashes, 2 non-fatal exceptions", out)
        self.assertIn("| 1 | critical | java_crash | com.example.shop | 2 |", out)
        self.assertIn("### [1] CRITICAL: Fatal exception", out)
        self.assertIn("## Timeline", out)
        code, out, _ = run(APP, "--show", "1")
        self.assertIn("### [1] CRITICAL", out)
        self.assertNotIn("### [2]", out)
        self.assertNotIn("## Summary", out)
        self.assertIn("No issue with id 99", run(APP, "--show", "99")[1])

    def test_max_stack_trims_long_blocks(self):
        lines = ["11-12 10:00:02.501  4321  4321 E AndroidRuntime: FATAL EXCEPTION: main",
                 "11-12 10:00:02.501  4321  4321 E AndroidRuntime: Process: com.a, PID: 4321",
                 "11-12 10:00:02.501  4321  4321 E AndroidRuntime: java.lang.StackOverflowError: stack size 8MB"]
        lines += ["11-12 10:00:02.501  4321  4321 E AndroidRuntime: \tat com.a.Tree.walk(Tree.kt:%d)" % (i % 3)
                  for i in range(120)]
        lines += ["11-12 10:00:02.501  4321  4321 E AndroidRuntime: Caused by: java.lang.IllegalStateException: deep",
                  "11-12 10:00:02.501  4321  4321 E AndroidRuntime: \tat com.a.Tree.leaf(Tree.kt:99)"]
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "deep.txt")
            with io.open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            g = analyze(p, "--max-stack", "10")["groups"][0]
            self.assertLess(len(g["stack"]), 20)
            self.assertTrue(any("lines left out" in x for x in g["stack"]))
            self.assertTrue(any("Caused by" in x for x in g["stack"]))
            self.assertEqual(g["fields"]["Top app frame"], "com.a.Tree.leaf(Tree.kt:99)")
            self.assertEqual(len(analyze(p, "--max-stack", "0")["groups"][0]["stack"]), 125)
        finally:
            shutil.rmtree(d)

    def test_fail_on_and_out_file(self):
        self.assertEqual(run(APP, "--fail-on", "critical")[0], 1)
        self.assertEqual(run(APP, "--fail-on", "critical", "--only", "jank")[0], 0)
        self.assertEqual(run(APP, "--fail-on", "low", "--only", "jank")[0], 1)
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "report.md")
            code, out, err = run(APP, "--out", p)
            self.assertEqual((code, out), (0, ""))
            self.assertIn("report written", err)
            self.assertIn("# Logcat analysis", read(p))
        finally:
            shutil.rmtree(d)

    def test_clean_log_and_bad_input(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "clean.txt")
            with open(p, "w") as f:
                f.write("11-12 10:00:00.000  100  100 I Tag: all good\n")
            code, out, _ = run(p, "--fail-on", "low")
            self.assertEqual(code, 0)
            self.assertIn("No problems found", out)
            q = os.path.join(d, "notlog.txt")
            with open(q, "w") as f:
                f.write("hello\nworld\n")
            code, _, err = run(q)
            self.assertEqual(code, 2)
            self.assertIn("no logcat lines found", err)
            code, _, err = run(os.path.join(d, "missing.txt"))
            self.assertEqual(code, 2)
            self.assertIn("file not found", err)
        finally:
            shutil.rmtree(d)

    def test_adb_missing_is_reported(self):
        code, _, err = run("--adb", "--adb-path", "adb-that-does-not-exist-12345")
        self.assertEqual(code, 2)
        self.assertIn("adb not found", err)

    def test_fake_adb_capture(self):
        d = tempfile.mkdtemp()
        try:
            fake = os.path.join(d, "fakeadb.py")
            with open(fake, "w") as f:
                f.write("import sys\n"
                        "assert sys.argv[1:6] == ['-s', 'emu-1', 'logcat', '-d', '-v'], sys.argv\n"
                        "assert '-c' not in sys.argv\n"
                        "sys.stdout.write(open(%r).read())\n" % APP)
            launcher = os.path.join(d, "adb.cmd" if os.name == "nt" else "adb")
            with open(launcher, "w") as f:
                if os.name == "nt":
                    f.write('@"%s" "%s" %%*\n' % (sys.executable, fake))
                else:
                    f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, fake))
            os.chmod(launcher, 0o755)
            saved = os.path.join(d, "saved.txt")
            code, out, err = run("--adb", "--adb-path", launcher, "--serial", "emu-1", "--save", saved, "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["counts"]["java_crash"], 2)
            self.assertIn("FATAL EXCEPTION", read(saved))
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
