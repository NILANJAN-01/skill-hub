import os
import tempfile
import unittest

import context_hub as ch


def write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class ContextHubTests(unittest.TestCase):
    def test_missing_central_warns(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(ch.classify(d)["warnings"])

    def test_states(self):
        with tempfile.TemporaryDirectory() as d:
            rules = "Always run the full test suite before you finish a change.\n"
            write(d, "AGENTS.md", rules)
            write(d, "CLAUDE.md", "@AGENTS.md\n")
            write(d, "GEMINI.md", rules + "more\n")
            write(d, ".windsurfrules", "Use tabs. Never use semicolons anywhere at all.\n")
            states = {p["path"]: p["state"] for p in ch.classify(d)["pointers"]}
            self.assertEqual(states["CLAUDE.md"], "pointer")
            self.assertEqual(states["GEMINI.md"], "duplicate")
            self.assertEqual(states[".windsurfrules"], "divergent")
            self.assertEqual(states[".cursorrules"], "missing")

    def test_sync_dry_run_then_write_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "AGENTS.md", "rules\n")
            write(d, "CLAUDE.md", "keep me\n")
            self.assertEqual(ch.main(["sync", d]), 0)
            self.assertFalse(os.path.exists(os.path.join(d, "GEMINI.md")))
            self.assertEqual(ch.main(["sync", d, "--write"]), 0)
            self.assertTrue(os.path.exists(os.path.join(d, ".github", "copilot-instructions.md")))
            with open(os.path.join(d, "CLAUDE.md")) as fh:
                self.assertEqual(fh.read(), "keep me\n")

    def test_sync_requires_central(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ch.main(["sync", d, "--write"]), 2)


if __name__ == "__main__":
    unittest.main()
