import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_score  # noqa: E402

CASES = os.path.join(HERE, "fixtures", "cases.jsonl")
OUTPUTS = os.path.join(HERE, "fixtures", "outputs.jsonl")


class EvalScoreTests(unittest.TestCase):
    def setUp(self):
        self.results, self.extra = eval_score.score(eval_score.read_jsonl(CASES), eval_score.read_jsonl(OUTPUTS))
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_statuses(self):
        status = {cid: r["status"] for cid, r in self.results.items()}
        self.assertEqual(status, {"refund-01": "pass", "tool-02": "pass", "json-03": "fail",
                                  "tone-04": "pending", "class-05": "pass", "missing-06": "fail"})
        self.assertIn("items.0.sku", self.results["json-03"]["failures"][0])
        self.assertEqual(self.results["missing-06"]["failures"], ["missing output"])
        self.assertEqual(self.extra, ["extra-99"])

    def test_summary(self):
        s = eval_score.summarize(self.results, self.extra)
        self.assertEqual((s["passed"], s["failed"], s["pending"]), (3, 2, 1))
        self.assertEqual(s["pass_rate"], 0.6)
        self.assertEqual(s["by_tag"]["policy"]["total"], 2)

    def test_judge_results(self):
        case = {"type": "judge", "rubric": "R"}
        self.assertEqual(eval_score.run_check(case, {"output": "", "judge": {"R": False}})[0], "fail")
        self.assertEqual(eval_score.run_check(case, {"output": "", "judge_pass": True})[0], "pass")

    def test_unknown_check_fails(self):
        status, reason = eval_score.run_check({"type": "nope"}, {"output": "x"})
        self.assertEqual(status, "fail")
        self.assertIn("unknown check type", reason)

    def test_baseline_regressions_and_exit_codes(self):
        report = os.path.join(self.tmp, "base.json")
        base = json.loads(json.dumps(eval_score.summarize(self.results, self.extra)))
        base["results"]["json-03"]["status"] = "pass"
        base["results"]["refund-01"]["status"] = "fail"
        with open(report, "w", encoding="utf-8") as fh:
            json.dump(base, fh)
        s = eval_score.summarize(self.results, self.extra, base)
        self.assertEqual(s["regressions"], ["json-03"])
        self.assertEqual(s["fixed"], ["refund-01"])
        self.assertEqual(eval_score.main([CASES, OUTPUTS, "--json", "--baseline", report, "--no-regressions"]), 1)
        self.assertEqual(eval_score.main([CASES, OUTPUTS, "--json", "--min-pass", "0.5"]), 0)
        self.assertEqual(eval_score.main([CASES, OUTPUTS, "--json", "--min-pass", "0.9"]), 1)
        self.assertEqual(eval_score.main([CASES, os.path.join(self.tmp, "missing.jsonl")]), 2)


if __name__ == "__main__":
    unittest.main()
