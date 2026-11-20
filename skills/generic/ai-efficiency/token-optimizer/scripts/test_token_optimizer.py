"""Tests for token_optimizer.py and token_dashboard.py (standard library only).

Run: python -m unittest discover -s skills/generic/ai-efficiency/token-optimizer/scripts -p "test_*.py" -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE))

import token_dashboard as td  # noqa: E402
import token_optimizer as to  # noqa: E402


def big_log() -> str:
    lines = [f"2026-11-20 10:{i // 60 % 60:02d}:{i % 60:02d} INFO request id={i * 7919:x} took {i % 97}ms"
             for i in range(2000)]
    lines += [f"2026-11-20 10:30:{i:02d} WARN pool almost full ({i}/50)" for i in range(10)]
    lines.append("2026-11-20 11:00:00 ERROR Request failed: java.lang.IllegalStateException: boom")
    lines += [f"\tat com.example.Service.method{k}(Service.java:{100 + k})" for k in range(40)]
    lines.append("Caused by: java.io.IOException: disk full")
    lines += [f"2026-11-20 11:00:{s:02d} INFO shutting down step {s}" for s in range(20)]
    return "\n".join(lines) + "\n"


class TempLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.ledger = self.dir / "usage.jsonl"
        self.env = {k: os.environ.get(k) for k in ("TOKEN_OPTIMIZER_LEDGER", "SKILL_TOKEN_LEDGER")}
        os.environ["TOKEN_OPTIMIZER_LEDGER"] = str(self.ledger)
        os.environ["SKILL_TOKEN_LEDGER"] = str(self.dir / "meter.jsonl")

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *argv) -> str:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = to.main(list(argv))
        self.assertEqual(code, 0)
        return out.getvalue()


class LogTests(unittest.TestCase):
    def test_keeps_problems_and_shrinks(self):
        text = big_log()
        r = to.compress_log(text)
        out = r["text"]
        self.assertIn("ERROR Request failed", out)
        self.assertIn("Caused by: java.io.IOException: disk full", out)
        self.assertIn("shutting down step", out)               # tail kept
        self.assertIn("lines omitted", out)
        self.assertLess(to.est_tokens(out), to.est_tokens(text) / 10)

    def test_repeated_problem_lines_are_folded(self):
        out = to.compress_log(big_log(), max_repeats=3)["text"]
        shown = [ln for ln in out.splitlines() if "WARN pool almost full" in ln and not ln.startswith("x")]
        self.assertLessEqual(len(shown), 3)
        self.assertRegex(out, r"x7\s+.*WARN pool almost full")

    def test_small_log_is_kept_whole(self):
        text = "line one\nERROR two\nline three\n"
        out = to.compress_log(text)["text"]
        for ln in text.splitlines():
            self.assertIn(ln, out)
        self.assertNotIn("omitted", out)


class OutlineSliceTests(unittest.TestCase):
    def test_python_outline_has_ranges_and_nesting(self):
        items = to.outline_items((FIX / "sample.py").read_text(encoding="utf-8"), FIX / "sample.py")
        names = {it["name"]: it for it in items}
        self.assertEqual((names["Cart"]["start"], names["Cart"]["end"]), (5, 17))
        self.assertIn("Cart.add", names)
        self.assertEqual(names["Cart.add"]["depth"], 1)
        self.assertIn("qty: int = 1", names["Cart.add"]["sig"])      # multi-line signature joined
        self.assertEqual(names["helper"]["start"], 20)                 # decorator line included

    def test_brace_language_outline_ignores_braces_in_strings(self):
        items = to.outline_items((FIX / "sample.js").read_text(encoding="utf-8"), FIX / "sample.js")
        rng = {it["short"]: (it["start"], it["end"]) for it in items}
        self.assertEqual(rng["loadConfig"], (12, 18))
        self.assertEqual(rng["Store"], (2, 10))
        self.assertEqual(rng["double"], (20, 22))
        self.assertIn("main", rng)

    def test_markdown_outline_uses_headings(self):
        md = "# Title\ntext\n## Part A\n```\n# not a heading\n```\n## Part B\nend\n"
        items = to._generic_outline(md, Path("x.md"))
        self.assertEqual([it["name"] for it in items], ["Title", "Part A", "Part B"])
        self.assertEqual(items[1]["end"], 6)

    def test_slice_by_symbol_and_lines(self):
        r = to.slice_file(FIX / "sample.py", symbol="Cart.add")
        self.assertIn("def add", r["text"])
        self.assertNotIn("def total", r["text"])
        r = to.slice_file(FIX / "sample.py", symbol="total")
        self.assertEqual(r["ranges"], [(16, 17)])
        r = to.slice_file(FIX / "sample.js", lines_spec="12-13")
        self.assertIn("loadConfig", r["text"])

    def test_slice_unknown_symbol_suggests_names(self):
        with self.assertRaises(SystemExit) as cm:
            to.slice_file(FIX / "sample.py", symbol="totl")
        self.assertIn("total", str(cm.exception))


class JsonTests(unittest.TestCase):
    DATA = json.dumps({"items": [{"id": i, "blob": "y" * 500, "secret": "x"} for i in range(100)]})

    def test_shrink_cuts_lists_strings_and_drops_keys(self):
        out = json.loads(to.compact_json(self.DATA, max_items=2, max_str=10, drop=["secret"])["text"])
        self.assertEqual(len(out["items"]), 3)
        self.assertEqual(out["items"][2], "... 98 more items")
        self.assertTrue(out["items"][0]["blob"].endswith("(+490 chars)"))
        self.assertNotIn("secret", out["items"][0])

    def test_shape(self):
        out = json.loads(to.compact_json(self.DATA, shape=True)["text"])
        self.assertEqual(out["items"][0], "<100 items>")
        self.assertEqual(out["items"][1]["id"], "number")
        self.assertEqual(out["items"][1]["blob"], "string")

    def test_jsonl_input(self):
        text = "\n".join(json.dumps({"n": i, "s": "abc"}) for i in range(5))
        r = to.compact_json(text, max_items=2)
        self.assertTrue(r["jsonl"])
        self.assertEqual(len(r["text"].strip().splitlines()), 3)


class PackTests(unittest.TestCase):
    def test_budget_is_respected_and_focus_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "small.py").write_text("def a():\n    return 1\n", encoding="utf-8")
            body = "    x = x * 2  # a long body line here\n" * 6
            (d / "big.py").write_text("".join(f"def f{i}(x):\n{body}    return x\n\n" for i in range(60)),
                                      encoding="utf-8")
            (d / "focus.py").write_text("# needle\n" + "x = 1\n" * 60, encoding="utf-8")
            (d / "package-lock.json").write_text("{}", encoding="utf-8")
            (d / "node_modules").mkdir()
            (d / "node_modules" / "dep.js").write_text("var x;", encoding="utf-8")
            r = to.build_pack([str(d)], budget=900, focus=["needle"], use_git=False)
            self.assertLessEqual(r["tokens"], 900)
            self.assertEqual(r["files"], 3)                       # lockfile and node_modules skipped
            self.assertIn("## focus.py\n", r["text"])             # whole, because it matches the focus term
            self.assertIn("## big.py (outline)", r["text"])
            self.assertNotIn("dep.js", r["text"])

    def test_tiny_budget_lists_names_only(self):
        r = to.build_pack([str(FIX / "sample.py"), str(FIX / "sample.js")], budget=10, use_git=False)
        self.assertEqual(r["listed"], 2)


class AutoTests(TempLedger):
    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_picks_the_method_by_input(self):
        big_py = "".join(f"def f{i}(x):\n" + "    x = x * 2  # a long body line\n" * 8 + "    return x\n\n"
                         for i in range(80))
        rows = [{"id": i, "blob": "y" * 300} for i in range(300)]
        cases = {
            "build.log": (big_log(), "log"),
            "output.txt": (big_log(), "log"),                       # log-like content, no .log suffix
            "data.json": (json.dumps(rows[:30]), "json"),
            "rows.json": (json.dumps(rows), "json"),                # long list: 3 samples fit the budget
            "events.jsonl": ("\n".join(json.dumps(r) for r in rows), "json"),
            "wide.json": (json.dumps({f"key{i}": "v" * 40 for i in range(3000)}), "json-shape"),  # still too big
            "module.py": (big_py, "outline"),
            "notes.md": ("# Title\n" + "".join(f"## Part {i}\n" + "text " * 300 + "\n" for i in range(10)),
                         "outline"),
        }
        for name, (text, method) in cases.items():
            with self.subTest(file=name):
                r = to.auto_reduce([self.write(name, text)], budget=2000)
                self.assertEqual(r["method"], method)
                self.assertLess(r["after"], r["before"])

    def test_small_file_is_unchanged_and_not_recorded(self):
        p = self.write("tiny.py", "print('hi')\n")
        out = self.run_cli("auto", str(p))
        self.assertEqual(out, "print('hi')\n")
        self.assertEqual(to.read_events(self.ledger), [])

    def test_folder_becomes_a_pack_and_is_recorded(self):
        d = self.dir / "proj"
        d.mkdir()
        (d / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
        out = self.run_cli("auto", str(d), "--no-git", "--skill", "python-unit-test")
        self.assertIn("# context pack", out)
        e = to.read_events(self.ledger)[0]
        self.assertEqual((e["tool"], e["skill"], e["note"]), ("pack", "python-unit-test", "auto"))

    def test_binary_is_refused(self):
        p = self.dir / "x.bin"
        p.write_bytes(b"\0\1\2" * 10)
        with self.assertRaises(SystemExit):
            to.auto_reduce([p])


class ImportTests(TempLedger):
    def test_session_log_import(self):
        events = to.scan_session(FIX / "session.jsonl", "demo")
        self.assertEqual(len(events), 2)                         # one per local day
        total = {k: sum(e[k] for e in events) for k in ("input", "output", "cache_read", "cache_write")}
        # msg_1 repeated: counted once; running totals (total_token_usage) skipped
        self.assertEqual(total, {"input": 460, "output": 95, "cache_read": 3000, "cache_write": 200})
        skills = {}
        for e in events:
            for k, v in e["skills"].items():
                skills[k] = skills.get(k, 0) + v
        # a SKILL.md path in a user message is not a use; tool calls are
        self.assertEqual(skills, {"ai-token-saver": 1, "token-optimizer": 2, "context-handoff": 1})
        self.assertEqual(sum(e["tool_calls"] for e in events), 4)
        first_day = to.parse_time("2026-11-18T09:00:05Z").astimezone().date().isoformat()
        self.assertTrue(events[0]["id"].endswith(first_day))
        self.assertEqual(events[0]["models"], {"model-large": 2})

    def test_reimport_replaces_instead_of_duplicating(self):
        self.run_cli("import", str(FIX / "session.jsonl"))
        self.run_cli("import", str(FIX / "session.jsonl"))
        events = to.read_events(self.ledger)
        self.assertEqual(len(events), 2)

    def test_parse_time_formats(self):
        self.assertIsNotNone(to.parse_time("2026-11-18T09:00:05.123456789Z"))
        self.assertIsNotNone(to.parse_time("2026-11-18 09:00"))
        self.assertIsNotNone(to.parse_time(1795082700))
        self.assertIsNotNone(to.parse_time(1795082700000))
        self.assertIsNone(to.parse_time("yesterday"))
        self.assertIsNone(to.parse_time(42))


class LedgerStatsDashboardTests(TempLedger):
    def test_optimizer_commands_record_and_no_record(self):
        log = self.dir / "build.log"
        log.write_text(big_log(), encoding="utf-8")
        self.run_cli("log", str(log), "-o", str(self.dir / "small.log"), "--skill", "gradle-android")
        self.run_cli("outline", str(FIX / "sample.py"), "--no-record")
        events = to.read_events(self.ledger)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual((e["kind"], e["tool"], e["skill"], e["source"]), ("optimize", "log", "gradle-android",
                                                                            "build.log"))
        self.assertGreater(e["saved"], 0)
        self.assertEqual(e["saved"], e["before"] - e["after"])
        self.assertRegex(e["time"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")

    def test_record_and_stats(self):
        self.run_cli("record", "--skill", "kotlin-unit-test", "--input", "1200", "--output", "300",
                     "--task", "add tests")
        self.run_cli("import", str(FIX / "session.jsonl"))
        s = to.summarize(to.read_events(self.ledger))
        self.assertEqual(s["totals"]["total"], 1500 + 3755)
        names = [r["skill"] for r in s["skills"]]
        self.assertIn("kotlin-unit-test", names)
        self.assertIn("token-optimizer", names)
        row = next(r for r in s["skills"] if r["skill"] == "token-optimizer")
        self.assertTrue(row["first"] and row["last"])
        self.assertTrue(s["advice"])
        out = self.run_cli("stats")
        self.assertIn("Tokens used: 5,255", out)

    def test_meter_ledger_is_merged(self):
        meter = self.dir / "meter.jsonl"
        meter.write_text(json.dumps({"time": "2026-11-18T10:00:00+00:00", "skill": "yt-lecture-overview",
                                     "method": "estimate", "with": 4000, "without": 50000, "saved": 46000}) + "\n",
                         encoding="utf-8")
        s = to.summarize([], to.read_events(meter))
        self.assertEqual(s["totals"]["meter_saved"], 46000)
        self.assertEqual(s["skills"][0]["skill"], "yt-lecture-overview")

    def test_days_filter(self):
        old = {"time": "2020-01-01T00:00:00+00:00", "kind": "usage", "id": "a", "input": 5, "output": 0,
               "cache_read": 0, "cache_write": 0, "total": 5}
        new = dict(old, time=to.now_iso(), id="b", input=7, total=7)
        s = to.summarize([old, new], days=7)
        self.assertEqual(s["totals"]["total"], 7)

    def test_dashboard_html(self):
        self.run_cli("import", str(FIX / "session.jsonl"))
        self.run_cli("json", str(FIX / "session.jsonl"), "--shape", "-o", str(self.dir / "shape.json"))
        evil = {"time": to.now_iso(), "kind": "usage", "id": "x", "session": "x", "input": 1, "output": 1,
                "cache_read": 0, "cache_write": 0, "total": 2, "skills": {"<script>alert(1)</script>": 1},
                "task": "</script><b>"}
        to.append_event(evil, self.ledger)
        out = self.dir / "dash.html"
        self.run_cli("dashboard", "-o", str(out))
        html = out.read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<!doctype html>"))
        for text in ("Tokens used per day", "Fresh tokens per day", "Tokens saved per day", "How skills are used",
                     "Recent activity", "context-handoff", "json-shape", "Advice from your data"):
            self.assertIn(text, html)
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;alert(1)", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))   # no external resources

    def test_dashboard_import_refreshes_first(self):
        logs = self.dir / "agent-logs"
        logs.mkdir()
        (logs / "s.jsonl").write_text((FIX / "session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        saved = dict(to.KNOWN_LOG_DIRS)
        to.KNOWN_LOG_DIRS.clear()
        to.KNOWN_LOG_DIRS["test-agent"] = str(logs)
        try:
            self.run_cli("dashboard", "--import", "-o", str(self.dir / "d.html"))
        finally:
            to.KNOWN_LOG_DIRS.clear()
            to.KNOWN_LOG_DIRS.update(saved)
        events = to.read_events(self.ledger)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["agent"], "test-agent")
        self.assertIn("context-handoff", (self.dir / "d.html").read_text(encoding="utf-8"))

    def test_empty_dashboard(self):
        html = td.render(to.summarize([]), generated=to.now_iso(), sources=["none"])
        self.assertIn("No data yet", html)

    def test_day_range_fills_gaps(self):
        days = td.day_range({"2026-11-01": {}, "2026-11-04": {}})
        self.assertEqual(days, ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"])


if __name__ == "__main__":
    unittest.main()
