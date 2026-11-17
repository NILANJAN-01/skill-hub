import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tool_lint  # noqa: E402


def load(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8-sig") as fh:
        return tool_lint.load_tools(json.load(fh))


def messages(findings, level=None, tool=None):
    return [m for lv, t, m in findings if (level is None or lv == level) and (tool is None or t == tool)]


class ToolLintTests(unittest.TestCase):
    def test_good_file_has_no_errors(self):
        findings = tool_lint.lint(load("tools_good.json"))
        self.assertEqual(messages(findings, "ERROR"), [])

    def test_openai_and_mcp_shapes_normalized(self):
        tools = load("tools_good.json")
        self.assertEqual(tool_lint.normalize(tools[1])[0], "create_issue")
        self.assertEqual(tool_lint.normalize(tools[1])[3], "openai")
        self.assertEqual(tool_lint.normalize(tools[0])[3], "mcp")

    def test_bad_file_findings(self):
        findings = tool_lint.lint(load("tools_bad.json"))
        errs = messages(findings, "ERROR")
        self.assertTrue(any("name must be" in m for m in messages(findings, "ERROR", "get data")))
        self.assertTrue(any("unknown JSON Schema type 'str'" in m for m in errs))
        self.assertTrue(any("required 't'" in m for m in errs))
        self.assertTrue(any("duplicate name" in m for m in messages(findings, "ERROR", "GET DATA")))
        self.assertTrue(any("missing description" in m for m in messages(findings, "ERROR", "GET DATA")))
        self.assertTrue(any('root type must be "object"' in m for m in errs))
        self.assertTrue(any("missing parameter schema" in m for m in messages(findings, "ERROR", "no_schema")))

    def test_warnings(self):
        findings = tool_lint.lint(load("tools_bad.json"))
        warns = messages(findings, "WARN")
        self.assertTrue(any("overlaps" in m for m in warns))
        self.assertTrue(any("array without items" in m for m in warns))
        self.assertTrue(any("when to use" in m for m in messages(findings, "WARN", "lookup")))

    def test_main_exit_codes(self):
        good = os.path.join(HERE, "fixtures", "tools_good.json")
        bad = os.path.join(HERE, "fixtures", "tools_bad.json")
        self.assertEqual(tool_lint.main([good, "--json"]), 0)
        self.assertEqual(tool_lint.main([bad, "--json"]), 1)
        self.assertEqual(tool_lint.main([os.path.join(HERE, "fixtures", "missing.json")]), 2)


if __name__ == "__main__":
    unittest.main()
