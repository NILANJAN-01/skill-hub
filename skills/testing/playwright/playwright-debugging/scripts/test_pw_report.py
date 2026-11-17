import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pw_report  # noqa: E402

JSON_REPORT = os.path.join(HERE, "fixtures", "results.json")
JUNIT_REPORT = os.path.join(HERE, "fixtures", "results.xml")


class ReportTests(unittest.TestCase):
    def test_json_report(self):
        tests, _ = pw_report.load(JSON_REPORT)
        s = pw_report.summarize(tests, [])
        self.assertEqual((s["total"], s["passed"], s["failed"], s["flaky"], s["skipped"]), (5, 1, 2, 1, 1))
        by_title = {f["title"]: f for f in s["failures"]}
        pay = by_title["customer can pay"]
        self.assertEqual((pay["category"], pay["project"], pay["retries"]), ("timeout", "chromium", 1))
        self.assertNotIn("\x1b", pay["message"])
        self.assertEqual(pay["traces"], ["test-results/checkout-pay-chromium-retry1/trace.zip"])
        self.assertEqual(by_title["cart > applies coupon"]["category"], "assertion")
        self.assertEqual(s["flaky_tests"][0]["category"], "strict-mode")
        self.assertEqual(s["slowest"][0]["title"], "customer can pay")
        self.assertEqual(s["by_project"], {"chromium": 1, "webkit": 1})

    def test_junit_report(self):
        tests, _ = pw_report.load(JUNIT_REPORT)
        s = pw_report.summarize(tests, [])
        self.assertEqual((s["total"], s["passed"], s["failed"], s["skipped"]), (3, 1, 1, 1))
        self.assertEqual(s["failures"][0]["category"], "navigation")
        self.assertEqual(s["failures"][0]["traces"], ["test-results/test-logout-chromium/trace.zip"])

    def test_categories(self):
        self.assertEqual(pw_report.categorize("Target page, context or browser has been closed"), "closed")
        self.assertEqual(pw_report.categorize("Screenshot comparison failed: 120 pixels (ratio 0.01)"), "screenshot")
        self.assertEqual(pw_report.categorize("element is not visible"), "locator")
        self.assertEqual(pw_report.categorize("something odd"), "other")

    def test_baseline_and_cli(self):
        tests, _ = pw_report.load(JSON_REPORT)
        base = json.loads(json.dumps(tests))
        for t in base:
            if t["title"] == "customer can pay":
                t["status"] = "passed"
            if t["title"] == "cart > applies coupon":
                t["status"] = "failed"
        s = pw_report.summarize(tests, [], baseline=base)
        self.assertEqual(len(s["new_failures"]), 1)
        self.assertIn("customer can pay", s["new_failures"][0])
        self.assertEqual(len(s["still_failing"]), 1)
        self.assertEqual(pw_report.main([JSON_REPORT, "--json", "--baseline", JSON_REPORT]), 0)
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.txt")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("not a report")
            self.assertEqual(pw_report.main([bad]), 2)


if __name__ == "__main__":
    unittest.main()
