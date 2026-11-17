import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rf_audit  # noqa: E402

PROJECT = os.path.join(HERE, "fixtures", "project")


def found(s, file_part=""):
    return {(f["rule"], f["line"]) for f in s["findings"] if file_part in (f["file"] or "")}


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = rf_audit.audit(PROJECT)

    def test_detects_version_and_features(self):
        self.assertEqual(self.s["robot_framework"], "7.1")
        self.assertEqual(self.s["files"], 2)
        f = self.s["features"]
        for name in ("VAR", "GROUP", "typed variables ${x: type}", "Secret variables", "[Metadata] in tests",
                     "keyword [Setup]", "Markdown tests (*.robot.md)", "RETURN"):
            self.assertGreater(f.get(name, 0), 0, name)

    def test_legacy_rules(self):
        got = found(self.s, "legacy.robot")
        for expected in [("telnet", 3), ("force-tags", 4), ("literal-secret", 7), ("secret-literal", 8),
                         ("old-for", 13), ("run-keyword-if", 15), ("set-variable", 16), ("sleep", 17),
                         ("os-run", 18), ("var-no-value", 19), ("loop-keywords", 20), ("return-setting", 31)]:
            self.assertIn(expected, got)
        self.assertNotIn(("literal-secret", 9), got)          # from environment: fine

    def test_markdown_blocks_only(self):
        got = found(self.s, "login.robot.md")
        self.assertIn(("sleep", 8), got)
        self.assertNotIn(("sleep", 13), got)                   # python block ignored

    def test_version_mismatch_and_cli_patterns(self):
        msgs = [f["message"] for f in self.s["findings"] if f["rule"] == "version"]
        self.assertTrue(any("GROUP" in m and "7.2+" in m for m in msgs))
        self.assertTrue(any("Secret" in m for m in msgs))
        self.assertFalse(any(m.startswith("suites use VAR") for m in msgs))   # VAR is 7.0: fine on 7.1
        got = found(self.s, "run.sh")
        self.assertIn(("tag-pattern", 2), got)
        self.assertIn(("testdoc", 3), got)
        self.assertNotIn(("tag-pattern", 4), got)

    def test_undocumented_and_exit_codes(self):
        und = [f for f in self.s["findings"] if f["rule"] == "undocumented"]
        self.assertIn("Old Keyword", und[0]["message"])
        self.assertNotIn("Documented Keyword", und[0]["message"])
        self.assertEqual(rf_audit.main([PROJECT, "--json"]), 1)
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ok.robot"), "w", encoding="utf-8") as fh:
                fh.write("*** Test Cases ***\nT\n    VAR    ${x: int}    1\n    Should Be Equal    ${x}    ${1}\n")
            self.assertEqual(rf_audit.main([d, "--strict", "--json"]), 0)
        self.assertEqual(rf_audit.main([os.path.join(PROJECT, "missing")]), 2)


if __name__ == "__main__":
    unittest.main()
