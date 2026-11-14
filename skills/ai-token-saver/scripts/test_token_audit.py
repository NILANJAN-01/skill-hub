"""Tests for token_audit.py (standard library only)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import token_audit as ta  # noqa: E402


def write(root, rel, text="", binary=False):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb" if binary else "w") as f:
        f.write(b"\0\1\2" * 10 if binary else text)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_estimate(self):
        self.assertEqual(ta.est_tokens(0), 0)
        self.assertEqual(ta.est_tokens(400), 100)

    def test_finds_largest_and_skips_binary(self):
        write(self.root, "a.py", "x" * 400)
        write(self.root, "b.py", "x" * 40)
        write(self.root, "img.bin", binary=True)
        r = ta.audit(self.root, 5, 0)
        self.assertEqual(r["largest"][0]["file"], "a.py")
        self.assertEqual(r["binary_files_skipped"], 1)

    def test_heavy_dir_not_counted(self):
        write(self.root, "node_modules/x/i.js", "x" * 4000)
        write(self.root, "a.py", "x" * 40)
        r = ta.audit(self.root, 5, 0)
        self.assertEqual(r["heavy_dirs"], ["node_modules"])
        self.assertEqual(r["text_files"], 1)

    def test_noise_and_instruction_tips(self):
        write(self.root, "package-lock.json", "x" * 8000)
        write(self.root, "AGENTS.md", "x" * 12000)
        r = ta.audit(self.root, 5, 0)
        self.assertEqual(r["noise"][0]["kind"], "lockfile")
        self.assertTrue(any("AGENTS.md" in t for t in r["tips"]))
        self.assertTrue(any("ignore file" in t for t in r["tips"]))

    def test_budget_warning(self):
        write(self.root, "a.py", "x" * 4000)
        r = ta.audit(self.root, 5, 100)
        self.assertTrue(any("budget" in t for t in r["tips"]))

    def test_main_bad_dir(self):
        self.assertEqual(ta.main([os.path.join(self.root, "nope")]), 2)


if __name__ == "__main__":
    unittest.main()
