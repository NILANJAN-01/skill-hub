"""Tests for design_note.py (stdlib only)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design_note  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class DesignNote(unittest.TestCase):
    def test_good_note_passes(self):
        errors, warns = design_note.check(read("good_note.md"))
        self.assertEqual(errors, [])
        self.assertEqual(warns, [])

    def test_bad_note(self):
        errors, warns = design_note.check(read("bad_note.md"))
        joined = "\n".join(errors + warns)
        self.assertIn("Alternative A: 'cons' is empty", joined)
        self.assertIn("nearly the same interface", joined)
        self.assertIn("'Interface comments' is empty", joined)
        self.assertIn("unfilled marker", joined)
        self.assertIn("'Hides' is empty", joined)

    def test_template_is_incomplete_until_filled(self):
        errors, _ = design_note.check(design_note.template("x", 3))
        self.assertTrue(any("unfilled marker" in e for e in errors))
        self.assertEqual(design_note.template("x", 3).count("## Alternative"), 3)

    def test_cli_new_never_overwrites(self):
        tmp = tempfile.mkdtemp()
        try:
            out = os.path.join(tmp, "docs", "note.md")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(design_note.main(["new", "Cache", "--out", out]), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(design_note.main(["new", "Cache", "--out", out]), 2)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(design_note.main(["check", out]), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
