import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_probe  # noqa: E402

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "fake_server.py")


def levels(report, level):
    return [m for lv, m in report["findings"] if lv == level]


class ProbeTests(unittest.TestCase):
    def test_lists_and_lints_tools(self):
        report = mcp_probe.run_probe([sys.executable, FAKE], timeout=10)
        self.assertEqual(report["server"]["name"], "fake")
        self.assertEqual([t["name"] for t in report["tools"]], ["echo", "bad tool"])
        errors = levels(report, "ERROR")
        self.assertTrue(any("bad tool: missing description" in e for e in errors))
        self.assertTrue(any('type must be "object"' in e for e in errors))
        self.assertFalse(any(e.startswith("echo") for e in errors))

    def test_call_tool(self):
        report = mcp_probe.run_probe([sys.executable, FAKE], timeout=10, call="echo", call_args={"text": "hi"})
        self.assertEqual(report["call"]["content"][0]["text"], "hi")

    def test_detects_stdout_noise(self):
        report = mcp_probe.run_probe([sys.executable, FAKE, "--noisy"], timeout=10)
        self.assertTrue(any("non-JSON line on stdout" in e for e in levels(report, "ERROR")))

    def test_follows_pagination(self):
        report = mcp_probe.run_probe([sys.executable, FAKE, "--paged"], timeout=10)
        self.assertEqual(len(report["tools"]), 2)

    def test_crash_reports_stderr(self):
        with self.assertRaises(mcp_probe.ProbeError) as ctx:
            mcp_probe.run_probe([sys.executable, FAKE, "--crash"], timeout=10)
        self.assertIn("server exited", str(ctx.exception))

    def test_missing_command(self):
        with self.assertRaises(mcp_probe.ProbeError):
            mcp_probe.run_probe(["definitely-not-a-real-command-xyz"], timeout=2)

    def test_lint_required_not_in_properties(self):
        findings = mcp_probe.lint_tools([{"name": "t", "description": "x" * 50,
                                          "inputSchema": {"type": "object", "properties": {}, "required": ["q"]}}])
        self.assertTrue(any("required parameter 'q'" in m for _, m in findings))

    def test_main_exit_codes(self):
        self.assertEqual(mcp_probe.main(["--json", "--", sys.executable, FAKE]), 1)
        self.assertEqual(mcp_probe.main(["--", sys.executable, FAKE, "--crash"]), 2)


if __name__ == "__main__":
    unittest.main()
