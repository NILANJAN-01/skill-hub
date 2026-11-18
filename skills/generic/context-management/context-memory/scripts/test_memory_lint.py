import os
import shutil
import tempfile
import unittest

import memory_lint as ml

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = os.path.join(HERE, "fixtures", "good")
BAD = os.path.join(HERE, "fixtures", "bad")
PROJECT = os.path.join(HERE, "fixtures", "project")


class ParseTests(unittest.TestCase):
    def test_flat_and_nested(self):
        fm, body, err = ml.parse("---\nname: a\ndescription: 'b c'\nmetadata:\n  type: user\n---\nfact\n")
        self.assertIsNone(err)
        self.assertEqual(fm["name"], "a")
        self.assertEqual(fm["description"], "b c")
        self.assertEqual(fm["metadata"]["type"], "user")
        self.assertEqual(body, "fact")

    def test_missing_frontmatter(self):
        self.assertIsNotNone(ml.parse("just text")[2])
        self.assertIsNotNone(ml.parse("---\nname: a\n")[2])


class LintTests(unittest.TestCase):
    def test_good_folder_is_clean(self):
        r = ml.lint(GOOD, root=PROJECT)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["memories"], 3)
        self.assertEqual(r["by_type"]["feedback"], 1)
        self.assertTrue(any("[[branch-naming]]" in n for n in r["notes"]))

    def test_bad_folder_findings(self):
        r = ml.lint(BAD, root=PROJECT)
        errors, warnings = "\n".join(r["errors"]), "\n".join(r["warnings"])
        self.assertIn("no-frontmatter.md: no frontmatter", errors)
        self.assertIn("points to missing file deleted-memory.md", errors)
        self.assertIn("terse-replies.md: not listed in MEMORY.md", errors)
        self.assertIn("deploy-rule.md: looks like it stores a secret", errors)
        self.assertIn("lowercase-kebab", warnings)
        self.assertIn("no 'Why:' line", warnings)
        self.assertIn("relative time 'last week'", warnings)
        self.assertIn("`deploy/prod.yaml`, which no longer exists", warnings)
        self.assertIn("short-answers.md and terse-replies.md look like the same fact", warnings)
        self.assertIn("non-pointer lines", warnings)

    def test_missing_index_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(GOOD, "no-force-push.md"), d)
            r = ml.lint(d)
            self.assertTrue(any("MEMORY.md is missing" in e for e in r["errors"]))

    def test_duplicate_names(self):
        with tempfile.TemporaryDirectory() as d:
            text = "---\nname: same\ndescription: x y z\ntype: user\n---\nfact\n"
            for fn in ("same.md", "copy.md"):
                with open(os.path.join(d, fn), "w") as fh:
                    fh.write(text)
            r = ml.lint(d)
            self.assertTrue(any("duplicate name 'same'" in e for e in r["errors"]))

    def test_cli_exit_codes(self):
        self.assertEqual(ml.main(["lint", GOOD]), 0)
        self.assertEqual(ml.main(["lint", BAD]), 1)
        self.assertEqual(ml.main(["lint", os.path.join(HERE, "nope")]), 2)


class WriteTests(unittest.TestCase):
    def test_index_dry_run_then_write(self):
        with tempfile.TemporaryDirectory() as d:
            for fn in os.listdir(GOOD):
                shutil.copy(os.path.join(GOOD, fn), d)
            index = os.path.join(d, "MEMORY.md")
            with open(index, "w", encoding="utf-8") as fh:
                fh.write("# Memory index\n")
            self.assertEqual(len(ml.index_lines(d)), 3)
            ml.main(["index", d])
            with open(index, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "# Memory index\n")
            ml.main(["index", d, "--write"])
            self.assertEqual(ml.index_lines(d), [])
            self.assertEqual(ml.lint(d)["errors"], [])

    def test_new_memory(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ml.main(["new", d, "--name", "use-uv", "--type", "feedback",
                                      "--description", "use uv, not pip"]), 0)
            self.assertFalse(os.path.exists(os.path.join(d, "use-uv.md")))
            self.assertEqual(ml.main(["new", d, "--name", "use-uv", "--type", "feedback",
                                      "--description", "use uv, not pip", "--write"]), 0)
            with open(os.path.join(d, "use-uv.md"), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("**Why:**", text)
            ml.main(["index", d, "--write"])
            self.assertTrue(any("unfilled" in w for w in ml.lint(d)["warnings"]))
            self.assertEqual(ml.main(["new", d, "--name", "use-uv", "--type", "user",
                                      "--description", "dup", "--write"]), 2)
            with self.assertRaises(ValueError):
                ml.new_memory("Bad Name", "user", "x")


if __name__ == "__main__":
    unittest.main()
