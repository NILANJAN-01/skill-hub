"""Tests for install_guardrails.py; every test works in a temporary folder."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import install_guardrails as ig  # noqa: E402


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ig.main(list(args))
    return code, out.getvalue()


class InstallGuardrails(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)

    def read(self, name):
        with open(self.path(name), encoding="utf-8") as fh:
            return fh.read()

    def write(self, name, text):
        os.makedirs(os.path.dirname(self.path(name)) or self.dir, exist_ok=True)
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_dry_run_writes_nothing(self):
        code, out = run("install", "--project", self.dir)
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertEqual(os.listdir(self.dir), [])

    def test_install_creates_block_and_checker(self):
        run("install", "--project", self.dir, "--yes")
        text = self.read("AGENTS.md")
        self.assertIn(ig.START, text)
        self.assertIn("python tools/design_check.py --diff", text)
        self.assertTrue(os.path.isfile(self.path("tools/design_check.py")))
        code, out = run("install", "--project", self.dir, "--yes")
        self.assertIn("nothing to do", out)

    def test_keeps_existing_text_and_updates_in_place(self):
        self.write("AGENTS.md", "# Rules\n\nUse tabs.\n")
        run("install", "--project", self.dir, "--yes")
        first = self.read("AGENTS.md")
        self.assertTrue(first.startswith("# Rules\n\nUse tabs.\n"))
        run("install", "--project", self.dir, "--yes", "--vendor", "scripts")
        second = self.read("AGENTS.md")
        self.assertEqual(second.count(ig.START), 1)
        self.assertIn("python scripts/design_check.py", second)

    def test_other_instruction_files(self):
        self.write("CLAUDE.md", "@AGENTS.md\n")                     # pointer: left alone
        self.write("GEMINI.md", "Own rules for this agent.\n")      # standalone: gets block
        run("install", "--project", self.dir, "--yes")
        self.assertNotIn(ig.START, self.read("CLAUDE.md"))
        self.assertIn(ig.START, self.read("GEMINI.md"))

    def test_remove(self):
        self.write("AGENTS.md", "# Rules\n")
        run("install", "--project", self.dir, "--yes")
        run("remove", "--project", self.dir, "--yes")
        self.assertEqual(self.read("AGENTS.md"), "# Rules\n")

    def test_refuses_to_overwrite_foreign_checker(self):
        self.write("tools/design_check.py", "print('mine')\n")
        with self.assertRaises(SystemExit):
            run("install", "--project", self.dir, "--yes")

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_hook_install_and_foreign_hook(self):
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        run("install", "--project", self.dir, "--hook", "--yes")
        hook = self.read(".git/hooks/pre-commit")
        self.assertIn(ig.HOOK_MARK, hook)
        self.assertIn("--staged", hook)
        run("remove", "--project", self.dir, "--hook", "--yes")
        self.assertFalse(os.path.exists(self.path(".git/hooks/pre-commit")))
        self.write(".git/hooks/pre-commit", "#!/bin/sh\necho mine\n")
        code, out = run("install", "--project", self.dir, "--hook", "--yes")
        self.assertIn("was not written by this script", out)
        self.assertEqual(self.read(".git/hooks/pre-commit"), "#!/bin/sh\necho mine\n")


if __name__ == "__main__":
    unittest.main()
