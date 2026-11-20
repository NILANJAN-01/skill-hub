"""Tests for design_check.py (stdlib only; git is needed for the diff tests)."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design_check  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def rules_at(ctx, name):
    return {(f.rule, f.line) for f in ctx.findings if os.path.basename(f.path) == name}


def run_main(args, cwd=None):
    out = io.StringIO()
    old = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = design_check.main(args)
    finally:
        os.chdir(old)
    return code, out.getvalue()


class PythonRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = design_check.run([os.path.join(FIXTURES, "bad"), os.path.join(FIXTURES, "good")])
        cls.found = rules_at(cls.ctx, "orders.py")

    def test_pass_through_method(self):
        self.assertIn(("pass-through-method", 8), self.found)   # save -> self._db.save
        self.assertIn(("pass-through-method", 21), self.found)  # place -> self._submit

    def test_shallow_wrapper_is_not_pass_through(self):
        self.assertNotIn(("pass-through-method", 51), self.found)  # add_items -> list(...)
        self.assertIn(("single-use-shallow", 51), self.found)

    def test_pass_through_variable_chain(self):
        self.assertIn(("pass-through-variable", 24), self.found)
        self.assertIn(("pass-through-variable", 28), self.found)
        messages = [f.message for f in self.ctx.findings if f.rule == "pass-through-variable"]
        self.assertFalse(any("'customer'" in m for m in messages), messages)  # printed = used

    def test_errors(self):
        self.assertIn(("swallowed-error", 42), self.found)
        self.assertIn(("repeated-handler", 92), self.found)

    def test_names_and_comments(self):
        for expected in [("vague-name", 35), ("vague-name", 57), ("non-predicate-boolean", 47),
                         ("doc-repeats-name", 55), ("comment-repeats-code", 33),
                         ("tactical-marker", 65), ("trivial-accessor", 11),
                         ("generic-container", 32), ("long-parameter-list", 32),
                         ("missing-interface-doc", 4), ("duplicate-code", 78)]:
            self.assertIn(expected, self.found)

    def test_clean_file_has_no_findings(self):
        self.assertEqual(rules_at(self.ctx, "text_buffer.py"), set())


class CFamilyRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = design_check.run([os.path.join(FIXTURES, "bad")])

    def test_java(self):
        found = rules_at(self.ctx, "TextDocument.java")
        for expected in [("pass-through-method", 9), ("pass-through-method", 13),
                         ("swallowed-error", 36), ("doc-repeats-name", 20),
                         ("generic-container", 28), ("long-parameter-list", 28),
                         ("non-predicate-boolean", 7), ("vague-name", 41),
                         ("comment-repeats-code", 29), ("missing-interface-doc", 5)]:
            self.assertIn(expected, found)
        self.assertNotIn(("missing-interface-doc", 20), found)  # has a doc comment

    def test_typescript(self):
        found = rules_at(self.ctx, "client.ts")
        self.assertIn(("pass-through-method", 4), found)
        self.assertIn(("swallowed-error", 11), found)
        self.assertIn(("missing-interface-doc", 16), found)
        self.assertNotIn(("pass-through-method", 8), found)

    def test_go(self):
        found = rules_at(self.ctx, "store.go")
        self.assertIn(("pass-through-method", 12), found)
        self.assertIn(("swallowed-error", 18), found)
        self.assertIn(("missing-interface-doc", 8), found)      # Cache
        self.assertNotIn(("missing-interface-doc", 4), found)   # Store is documented

    def test_strings_and_comments_are_masked(self):
        masked, comments, _ = design_check.mask_c_like(
            'a = "x { // y"; // real\n/* b { */ c = \'{\';', "java")
        self.assertNotIn("{", masked)
        self.assertEqual([c.text for c in comments], ["real", "b {"])


class Suppression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_inline_ignore(self):
        self.write("a.py", "def load(p):\n    try:\n        return open(p)\n"
                           "    # design-check: ignore[swallowed-error] -- optional file\n"
                           "    except OSError:\n        pass\n")
        rules = {f.rule for f in design_check.run([self.tmp]).findings}
        self.assertNotIn("swallowed-error", rules)

    def test_comment_in_handler_documents_the_choice(self):
        self.write("b.py", "def load(p):\n    try:\n        return open(p)\n"
                           "    except OSError:\n        pass  # missing config is fine\n")
        rules = {f.rule for f in design_check.run([self.tmp]).findings}
        self.assertNotIn("swallowed-error", rules)

    def test_baseline_hides_known_findings(self):
        self.write("c.py", "def f():\n    tmp = 1\n    return tmp\n")
        base = os.path.join(self.tmp, "baseline.json")
        code, _ = run_main([self.tmp, "--write-baseline", base])
        self.assertEqual(code, 0)
        code, out = run_main([self.tmp, "--baseline", base, "--fail-on", "info"])
        self.assertEqual(code, 0, out)
        code, _ = run_main([self.tmp, "--fail-on", "info"])
        self.assertEqual(code, 1)

    def test_json_and_exit_codes(self):
        self.write("d.py", "def f():\n    try:\n        g()\n    except Exception:\n        pass\n")
        code, out = run_main([self.tmp, "--format", "json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertIn("swallowed-error", [f["rule"] for f in data["findings"]])
        self.assertEqual(data["summary"]["warning"], 1)
        self.assertEqual(run_main([self.tmp, "--fail-on", "never"])[0], 0)
        self.assertEqual(run_main([self.tmp, "--select", "nope"])[0], 2)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class DiffMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("old.py", "def old():\n    tmp = 1\n    return tmp\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        subprocess.run(["git"] + list(args), cwd=self.tmp, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write(self, name, text):
        with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_only_changed_lines_are_reported(self):
        self.write("new.py", "def new():\n    data = 2\n    return data\n")
        code, out = run_main(["--diff", "--fail-on", "info"], cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("new.py", out)
        self.assertNotIn("old.py", out)

    def test_staged_mode(self):
        self.write("old.py", "def old():\n    tmp = 1\n    return tmp\n\n\ndef added():\n"
                             "    try:\n        old()\n    except ValueError:\n        pass\n")
        self.git("add", "old.py")
        code, out = run_main(["--staged"], cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("swallowed-error", out)
        self.assertNotIn("'tmp'", out)  # unchanged line 2 is not reported


if __name__ == "__main__":
    unittest.main()
