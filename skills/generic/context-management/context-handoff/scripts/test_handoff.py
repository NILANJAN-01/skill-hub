import os
import shutil
import subprocess
import tempfile
import unittest

import handoff as h

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class CheckTests(unittest.TestCase):
    def test_good_note_passes(self):
        r = h.check_text(fixture("good_handoff.md"), root=FIXTURES)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["warnings"], [])
        self.assertIn("decisions", r["sections"])

    def test_bad_note_findings(self):
        r = h.check_text(fixture("bad_handoff.md"), root=FIXTURES)
        text = "\n".join(r["errors"] + r["warnings"])
        self.assertIn("missing required section: next", text)
        self.assertIn("as discussed", text)
        self.assertIn("yesterday", text)
        self.assertIn("secret", text)
        self.assertIn("file not found under root: src/missing.py", text)
        self.assertIn("unfilled placeholder", text)

    def test_inline_labels_count_as_sections(self):
        note = "Goal: ship the export\nDone: parser written\nNext step: add tests for empty input\n"
        r = h.check_text(note)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["sections"], ["done", "goal", "next"])

    def test_brief_kind(self):
        r = h.check_text(fixture("good_brief.md"), kind="brief")
        self.assertEqual(r["errors"], [])
        r = h.check_text("## Goal\nFind the slow query\n", kind="brief")
        self.assertIn("missing required section: return", r["errors"])

    def test_empty_section_is_error(self):
        r = h.check_text("## Goal\n\n## Done\nx\n## Next\ny\n")
        self.assertIn("section is empty: goal", r["errors"])

    def test_size_limit(self):
        r = h.check_text("Goal: a\nDone: b\nNext: c\n" + "word " * 2000, max_tokens=100)
        self.assertTrue(any("tokens" in w for w in r["warnings"]))

    def test_cli_exit_codes(self):
        self.assertEqual(h.main(["check", os.path.join(FIXTURES, "good_handoff.md"), "--root", FIXTURES]), 0)
        self.assertEqual(h.main(["check", os.path.join(FIXTURES, "bad_handoff.md")]), 1)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class DraftTests(unittest.TestCase):
    def run_git(self, root, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com"] + list(args),
                       cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_draft_from_git(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_git(d, "init", "-q")
            with open(os.path.join(d, "app.py"), "w") as fh:
                fh.write("print('hi')\n")
            self.run_git(d, "add", "app.py")
            self.run_git(d, "commit", "-q", "-m", "Add app")
            with open(os.path.join(d, "app.py"), "a") as fh:
                fh.write("# TODO: handle errors\n")
            note = h.draft(d, goal="Make app robust", today="2026-01-02")
            self.assertIn("# Handoff (2026-01-02)", note)
            self.assertIn("Make app robust", note)
            self.assertIn("Add app", note)
            self.assertIn("`app.py`", note)
            self.assertIn("app.py: # TODO: handle errors", note)
            r = h.check_text(note)
            self.assertEqual(r["errors"], [])
            self.assertTrue(any("<fill:" in w for w in r["warnings"]))

    def test_draft_without_git(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("No git repository", h.draft(d))

    def test_out_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "note.md")
            with open(out, "w") as fh:
                fh.write("keep")
            self.assertEqual(h.main(["draft", "--root", d, "--out", out]), 2)
            with open(out) as fh:
                self.assertEqual(fh.read(), "keep")


if __name__ == "__main__":
    unittest.main()
