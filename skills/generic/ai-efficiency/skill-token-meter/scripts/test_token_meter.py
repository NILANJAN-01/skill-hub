"""Tests for token_meter.py (standard library only, no network)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import token_meter as tm  # noqa: E402

FIX = HERE / "fixtures"


DIGEST_SKILL = """---
name: log-digest
description: "Summarise a large log file into errors and counts with a bundled script. Use when a log is too big to read."
---

# Log digest

Run `python scripts/digest.py <log>` and read the summary instead of the raw log.
Group errors by message, count them, and report the first and last time each one appears.
"""
NOTES_SKILL = """---
name: notes-only
description: "Advice for writing commit messages. Use when writing a commit message."
---

# Commit messages

Write a short summary line, a blank line, then the why.
"""
DIGEST_CODE = """import collections, re, sys

def main(path):
    counts = collections.Counter()
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"ERROR (.*)", line)
        if m:
            counts[m.group(1)] += 1
    for msg, n in counts.most_common():
        print(n, msg)

if __name__ == "__main__":
    main(sys.argv[1])
"""


def make_skills(root: Path) -> Path:
    """Two small skills built at test time (no SKILL.md files are shipped inside this skill)."""
    d = root / "skills" / "demo" / "log-digest"
    (d / "references").mkdir(parents=True)
    (d / "scripts" / "fixtures").mkdir(parents=True)
    (d / "SKILL.md").write_text(DIGEST_SKILL, encoding="utf-8")
    (d / "references" / "patterns.md").write_text("# Patterns\n\nERROR lines start with a timestamp.\n" * 20,
                                                  encoding="utf-8")
    (d / "scripts" / "digest.py").write_text(DIGEST_CODE, encoding="utf-8")
    (d / "scripts" / "test_digest.py").write_text("import unittest\n" * 50, encoding="utf-8")
    (d / "scripts" / "fixtures" / "sample.py").write_text("x = 1\n" * 50, encoding="utf-8")
    n = root / "skills" / "demo" / "notes-only"
    n.mkdir(parents=True)
    (n / "SKILL.md").write_text(NOTES_SKILL, encoding="utf-8")
    return root / "skills"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.skills = make_skills(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class CountingTests(Base):
    def test_estimates(self):
        self.assertEqual(tm.est_tokens(""), 0)
        self.assertEqual(tm.est_tokens("a" * 400), 100)          # prose: chars / 4
        self.assertEqual(tm.est_tokens("a" * 330, "code"), 100)  # code: chars / 3.3

    def test_frontmatter(self):
        meta, body = tm.split_frontmatter('---\nname: x\ndescription: "Does y. Use when z."\n---\n# Body\n')
        self.assertEqual(meta["description"], "Does y. Use when z.")
        self.assertEqual(body.strip(), "# Body")

    def test_skill_costs_split_by_when_paid(self):
        c = tm.skill_costs(self.skills / "demo" / "log-digest")
        self.assertEqual(c["skill"], "log-digest")
        self.assertGreater(c["description"], 0)
        self.assertGreater(c["body"], c["description"])
        self.assertEqual(c["reference_files"], 1)
        self.assertEqual(c["script_files"], 1)          # test_*.py and fixtures are not counted
        self.assertGreater(c["scripts"], 0)

    def test_find_and_resolve(self):
        names = sorted(d.name for d in tm.find_skills(self.skills))
        self.assertEqual(names, ["log-digest", "notes-only"])
        self.assertEqual(tm.resolve_skill("notes-only", [self.skills]).name, "notes-only")
        with self.assertRaises(SystemExit):
            tm.resolve_skill("missing", [self.skills])


class EstimateTests(Base):
    def test_script_skill_saves_tokens(self):
        skill = self.skills / "demo" / "log-digest"
        r = tm.estimate(skill, raw=[str(FIX / "raw.log")], outputs=[str(FIX / "digest.txt")])
        self.assertEqual(r["method"], "estimate")
        self.assertEqual(r["with"]["parts"]["script output read"], tm.file_tokens(FIX / "digest.txt"))
        self.assertEqual(r["without"]["parts"]["raw inputs read directly"], tm.file_tokens(FIX / "raw.log"))
        code = tm.files_tokens(tm.scripts_of(skill))
        self.assertEqual(r["without"]["parts"]["writing equivalent code"], int(code * 1.5))
        self.assertEqual(r["saved"]["total"], r["without"]["total"] - r["with"]["total"])
        self.assertGreater(r["saved"]["total"], 0)

    def test_assumptions_are_adjustable(self):
        skill = self.skills / "demo" / "log-digest"
        a = tm.estimate(skill, iterations=1.0, research_tokens=0, command_tokens=0)
        b = tm.estimate(skill, iterations=3.0, research_tokens=0, command_tokens=0)
        self.assertEqual(b["without"]["output"], 3 * a["without"]["output"])
        self.assertEqual(a["without"]["parts"]["learning the know-how"], 0)

    def test_skill_without_scripts_can_cost_more(self):
        r = tm.estimate(self.skills / "demo" / "notes-only", research_factor=0)
        self.assertEqual(r["without"]["parts"]["writing equivalent code"], 0)
        self.assertEqual(r["with"]["parts"]["commands typed"], 0)
        self.assertLess(r["saved"]["total"], 0)   # honest: a playbook alone costs tokens if no research is saved

    def test_ran_filters_and_rejects_unknown(self):
        skill = self.skills / "demo" / "log-digest"
        self.assertEqual(tm.estimate(skill, ran=[])["without"]["parts"]["writing equivalent code"], 0)
        with self.assertRaises(SystemExit):
            tm.estimate(skill, ran=["nope.py"])

    def test_read_all_references(self):
        r = tm.estimate(self.skills / "demo" / "log-digest", read=["all"])
        self.assertGreater(r["with"]["parts"]["references read"], 0)


class UsageAndLedgerTests(Base):
    def test_usage_dedupes_repeated_message_ids_and_mixed_formats(self):
        u = tm.usage_from_logs([FIX / "session.jsonl"])
        # msg_1 appears twice (counted once); one OpenAI-style and one Gemini-style record
        self.assertEqual(u["records"], 3)
        self.assertEqual(u["input"], 100 + 400 + 50)
        self.assertEqual(u["output"], 20 + 80 + 10)
        self.assertEqual(u["cache_read"], 1000)
        self.assertEqual(u["cache_write"], 200)
        self.assertEqual(u["total"], 550 + 110 + 1000 + 200)

    def test_usage_reads_plain_json(self):
        p = self.tmp / "one.json"
        p.write_text(json.dumps({"usage": {"input_tokens": 7, "output_tokens": 3}}), encoding="utf-8")
        self.assertEqual(tm.usage_from_logs([p])["total"], 10)

    def test_measure_from_numbers_and_logs(self):
        r = tm.measure("log-digest", with_tokens=4000, without_tokens=10000)
        self.assertEqual(r["saved"]["total"], 6000)
        self.assertEqual(r["saved_percent"], 60.0)
        r = tm.measure("x", with_log=FIX / "session.jsonl", without_log=FIX / "session.jsonl")
        self.assertEqual(r["saved"]["total"], 0)
        with self.assertRaises(SystemExit):
            tm.measure("x", with_tokens=1)

    def test_record_and_report(self):
        ledger = self.tmp / "ledger.jsonl"
        skill = self.skills / "demo" / "log-digest"
        tm.record(tm.estimate(skill, raw=[str(FIX / "raw.log")]), "digest a log", ledger)
        tm.record(tm.measure("log-digest", with_tokens=1000, without_tokens=3000), "", ledger)
        tm.record(tm.measure("notes-only", with_tokens=500, without_tokens=400), "", ledger)
        rep = tm.report(ledger)
        rows = {r["skill"]: r for r in rep["skills"]}
        self.assertEqual(rows["log-digest"]["uses"], 2)
        self.assertEqual((rows["log-digest"]["measured"], rows["log-digest"]["estimated"]), (1, 1))
        self.assertEqual(rows["notes-only"]["saved"], -100)
        self.assertEqual(rep["total"]["uses"], 3)
        self.assertEqual(rep["skills"][0]["skill"], "log-digest")   # biggest saver first
        first = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(first["task"], "digest a log")
        self.assertIn("iterations", first["assumptions"])

    def test_ledger_env_and_empty_report(self):
        import os
        old = os.environ.get("SKILL_TOKEN_LEDGER")
        os.environ["SKILL_TOKEN_LEDGER"] = str(self.tmp / "env.jsonl")
        try:
            self.assertEqual(tm.ledger_path(), self.tmp / "env.jsonl")
            self.assertEqual(tm.report()["skills"], [])
        finally:
            if old is None:
                os.environ.pop("SKILL_TOKEN_LEDGER", None)
            else:
                os.environ["SKILL_TOKEN_LEDGER"] = old


class CliTests(Base):
    def run_cli(self, *args):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = tm.main(list(args))
        return code, buf.getvalue()

    def test_scan_and_estimate_output(self):
        code, out = self.run_cli("scan", "--skills-dir", str(self.skills))
        self.assertEqual(code, 0)
        self.assertIn("2 skills", out)
        code, out = self.run_cli("estimate", "--skill", "log-digest", "--skills-dir", str(self.skills),
                                 "--raw", str(FIX / "raw.log"), "--price-in", "3", "--price-out", "15")
        self.assertIn("SAVED", out)
        self.assertIn("Money saved", out)
        self.assertIn("Assumptions", out)

    def test_measure_record_json(self):
        ledger = self.tmp / "l.jsonl"
        code, out = self.run_cli("measure", "--skill", "s", "--with-tokens", "10", "--without-tokens", "30",
                                 "--record", "--ledger", str(ledger), "--json")
        self.assertEqual(json.loads(out)["saved"]["total"], 20)
        code, out = self.run_cli("report", "--ledger", str(ledger))
        self.assertIn("20 tokens saved over 1 uses", out)


if __name__ == "__main__":
    unittest.main()
