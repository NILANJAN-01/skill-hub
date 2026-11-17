import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pw_audit  # noqa: E402

SAMPLE = os.path.join(HERE, "fixtures", "sample")


def rules(summary, level=None, file_part=""):
    return [(f["rule"], f["line"]) for f in summary["findings"]
            if (level is None or f["level"] == level) and file_part in f["file"]]


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = pw_audit.audit(SAMPLE)

    def test_counts_files_and_config(self):
        self.assertEqual(self.s["test_files"], 2)
        cfg = self.s["config"]
        self.assertEqual(cfg["config"], "playwright.config.ts")
        self.assertEqual(cfg["projects"], ["chromium", "webkit"])
        self.assertIsNone(cfg["baseURL"])

    def test_js_findings_with_lines(self):
        found = rules(self.s, file_part="checkout.spec.ts")
        for expected in [("only", 3), ("hardcoded-url", 4), ("hard-wait", 5), ("force", 6), ("xpath", 7),
                         ("brittle-css", 8), ("credential", 9), ("missing-await", 10), ("non-retrying", 11),
                         ("networkidle", 12)]:
            self.assertIn(expected, found)
        self.assertNotIn(("hard-wait", 13), found)          # commented out
        self.assertIn(("removed-api", 28), found)           # _react=
        self.assertIn(("removed-api", 29), found)           # page.accessibility
        self.assertIn(("visible-pseudo", 30), found)
        good_lines = range(16, 23)
        self.assertFalse([f for f in found if f[1] in good_lines], found)   # the good test is clean

    def test_python_findings(self):
        found = rules(self.s, file_part="test_login.py")
        self.assertIn(("hard-wait", 7), found)
        self.assertIn(("force", 9), found)
        self.assertIn(("non-retrying", 10), found)

    def test_config_and_testid_findings(self):
        msgs = " ".join(f["message"] for f in self.s["findings"] if f["rule"] in ("config", "test-id"))
        self.assertIn("no baseURL", msgs)
        self.assertIn("no forbidOnly", msgs)
        self.assertIn("no trace", msgs)
        self.assertIn("testIdAttribute: 'data-qa'", msgs)
        self.assertEqual(self.s["skipped_or_fixme"], 1)

    def test_exit_codes(self):
        self.assertEqual(pw_audit.main([SAMPLE, "--json"]), 1)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tests"))
            with open(os.path.join(d, "playwright.config.ts"), "w", encoding="utf-8") as fh:
                fh.write("export default { forbidOnly: !!process.env.CI, retries: 2, use: { baseURL: process.env.BASE_URL, trace: 'on-first-retry' } }\n")
            with open(os.path.join(d, "tests", "a.spec.ts"), "w", encoding="utf-8") as fh:
                fh.write("import { test, expect } from '@playwright/test';\n"
                         "test('a', async ({ page }) => { await page.goto('/'); "
                         "await expect(page.getByRole('heading')).toBeVisible(); });\n")
            self.assertEqual(pw_audit.main([d, "--strict", "--json"]), 0)
        self.assertEqual(pw_audit.main([os.path.join(SAMPLE, "missing")]), 2)


if __name__ == "__main__":
    unittest.main()
