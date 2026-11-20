"""Tests for token_hook.py, run the way an agent runs it: a subprocess with the event as JSON on stdin.

Run: python -m unittest discover -s skills/generic/ai-efficiency/token-optimizer/scripts -p "test_*.py" -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "token_hook.py"
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE))

import token_optimizer as to  # noqa: E402


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.ledger = self.dir / "usage.jsonl"
        self.env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home),
                        TOKEN_OPTIMIZER_LEDGER=str(self.ledger))
        self.env.pop("TOKEN_GUARD", None)
        self.env.pop("TOKEN_GUARD_MIN_TOKENS", None)
        self.big = self.dir / "big.py"
        self.big.write_text("".join(f"def f{i}(x):\n    return x + {i}\n\n" for i in range(600)), encoding="utf-8")
        self.small = self.dir / "small.py"
        self.small.write_text("x = 1\n", encoding="utf-8")

    def run_hook(self, mode, event, *extra, env=None):
        out = subprocess.run([sys.executable, str(HOOK), mode, *extra], input=event if isinstance(event, str)
                             else json.dumps(event), capture_output=True, text=True, timeout=60,
                             env=env or self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        return out.stdout.strip()

    def read_event(self, path, session="s1", **tool_input):
        return {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": "Read",
                "tool_input": dict(file_path=str(path), **tool_input), "cwd": str(self.dir)}

    def test_big_whole_read_is_blocked_once_per_session(self):
        out = self.run_hook("read-guard", self.read_event(self.big))
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("token_optimizer.py auto", decision["permissionDecisionReason"])
        self.assertIn("big.py", decision["permissionDecisionReason"])
        self.assertEqual(self.run_hook("read-guard", self.read_event(self.big)), "")          # second try allowed
        self.assertTrue(self.run_hook("read-guard", self.read_event(self.big, session="s2")))  # new session
        events = [e for e in to.read_events(self.ledger) if e["kind"] == "guard"]
        self.assertEqual(len(events), 2)
        self.assertEqual(to.summarize(to.read_events(self.ledger))["totals"]["guarded_reads"], 2)

    def test_reads_that_pass(self):
        cases = {
            "small file": self.read_event(self.small),
            "line range": self.read_event(self.big, offset=10, limit=50),
            "other tool": dict(self.read_event(self.big), tool_name="Bash"),
            "missing file": self.read_event(self.dir / "nope.py"),
            "image": self.read_event(self.dir / "pic.png"),
        }
        for name, event in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.run_hook("read-guard", event), "")

    def test_relative_path_uses_cwd(self):
        event = self.read_event("big.py")
        self.assertIn("deny", self.run_hook("read-guard", event))

    def test_threshold_and_off_switch(self):
        self.assertEqual(self.run_hook("read-guard", self.read_event(self.big), "--min-tokens", "100000"), "")
        self.assertEqual(self.run_hook("read-guard", self.read_event(self.big, session="x"),
                                       env=dict(self.env, TOKEN_GUARD="off")), "")
        off = self.home / ".skill-hub" / "token-guard.off"
        off.parent.mkdir(parents=True)
        off.write_text("", encoding="utf-8")
        self.assertEqual(self.run_hook("read-guard", self.read_event(self.big, session="y")), "")

    def test_bad_input_never_blocks(self):
        for raw in ("", "not json", "[1, 2]", json.dumps({"tool_name": "Read", "tool_input": "{bad"})):
            with self.subTest(raw=raw):
                self.assertEqual(self.run_hook("read-guard", raw), "")
        self.assertEqual(self.run_hook("session-end", "garbage"), "")

    def test_session_end_imports_the_transcript(self):
        event = {"session_id": "s1", "hook_event_name": "SessionEnd", "transcript_path": str(FIX / "session.jsonl")}
        self.run_hook("session-end", event, "--agent", "claude-code")
        self.run_hook("session-end", event, "--agent", "claude-code")                     # idempotent
        usage = [e for e in to.read_events(self.ledger) if e["kind"] == "usage"]
        self.assertEqual(len(usage), 2)
        self.assertEqual({e["agent"] for e in usage}, {"claude-code"})
        self.assertEqual(sum(e["total"] for e in usage), 3755)


if __name__ == "__main__":
    unittest.main()
