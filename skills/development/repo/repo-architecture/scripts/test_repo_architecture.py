"""Tests for repo_architecture.py, the command line (standard library only)."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import repo_architecture as ra  # noqa: E402
import repo_model as rm  # noqa: E402
from test_repo_model import FILES, make_repo  # noqa: E402


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ra.main(list(argv))
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
            err.write(str(e))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = make_repo()
        cls.tmp = tempfile.mkdtemp(prefix="ra-out-")
        cls.out = os.path.join(cls.tmp, "demo")
        cls.code, cls.stdout, _ = run("analyze", cls.repo, "--out", cls.out, "--name", "demo", "--flows", "4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def doc(self):
        with io.open(os.path.join(self.out, "ARCHITECTURE.md"), encoding="utf-8") as f:
            return f.read()

    def test_analyze_writes_all_outputs(self):
        self.assertEqual(self.code, 0)
        for name in ("ARCHITECTURE.md", "model.json", "annotations.json"):
            self.assertTrue(os.path.exists(os.path.join(self.out, name)), name)
        self.assertIn("Health:", self.stdout)
        self.assertIn("flows drawn: 4", self.stdout)

    def test_document_sections_and_diagrams(self):
        doc = self.doc()
        for heading in ("# Architecture: demo", "## High-level design", "## Components", "## Code flows",
                        "## Health audit", "## Build, run and test", "## Dependencies", "## Reading order",
                        "## Notes and limits"):
            self.assertIn(heading, doc)
        blocks = re.findall(r"```mermaid\n(.*?)\n```", doc, re.S)
        self.assertEqual(len(blocks), 5)
        self.assertTrue(blocks[0].startswith("flowchart TB"))
        self.assertTrue(all(b.startswith("sequenceDiagram") for b in blocks[1:]))
        self.assertNotIn("Zx9Q" + "w81", doc)

    def test_check_render_cycle_keeps_text(self):
        code, out, _ = run("check", self.out)
        self.assertEqual(code, 1)
        self.assertIn("Not described yet: summary", out)
        path = os.path.join(self.out, "annotations.json")
        ann = rm.load_json(path)
        ann["summary"] = "A polyglot demo."
        for v in ann["components"].values():
            v["description"] = "Does a thing."
        ann["components"]["lib"]["title"] = "Storage layer"
        for k in ann["flows"]:
            ann["flows"][k] = "Runs the demo."
        ann["dismissed"] = {"SEC009": "constant query"}
        rm.save_json(path, ann)
        code, out, _ = run("check", self.out)
        self.assertEqual(code, 1)
        self.assertIn("older than annotations.json", out)
        self.assertEqual(run("render", self.out)[0], 0)
        code, out, _ = run("check", self.out)
        self.assertEqual(code, 0, out)
        doc = self.doc()
        self.assertIn("A polyglot demo.", doc)
        self.assertIn("Storage layer", doc)
        self.assertIn("Dismissed after review", doc)
        # analyze again: written text survives
        run("analyze", self.repo, "--out", self.out, "--name", "demo", "--flows", "4")
        self.assertEqual(rm.load_json(path)["summary"], "A polyglot demo.")

    def test_audit_command(self):
        code, out, _ = run("audit", self.repo, "--json", "--out", os.path.join(self.tmp, "a"))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("security", data["areas"])
        self.assertEqual(run("audit", self.out, "--fail-under", "101")[0], 1)
        code, out, _ = run("audit", self.out)
        self.assertIn("# Health audit", out)

    def test_errors(self):
        code, _, err = run("analyze", os.path.join(self.tmp, "missing"), "--out", os.path.join(self.tmp, "x"))
        self.assertNotEqual(code, 0)
        self.assertIn("not a folder or a git URL", err)
        self.assertNotEqual(run("render", os.path.join(self.tmp, "nothing"))[0], 0)

    def test_skill_documents_every_audit_rule(self):
        with io.open(os.path.join(HERE, "..", "references", "audit.md"), encoding="utf-8") as f:
            text = f.read()
        for rule in rm.RULES:
            self.assertIn("| %s |" % rule, text)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class GitTests(unittest.TestCase):
    def test_git_listing_follows_gitignore_and_skips_output(self):
        repo = make_repo(dict(FILES, **{".gitignore": "build/\n", "build/gen.py": "x = 1\n"}))
        try:
            subprocess.run(["git", "init", "-q", repo], check=True)
            out = os.path.join(repo, "repo-architecture", "demo")
            code, stdout, _ = run("analyze", repo, "--out", out)
            self.assertEqual(code, 0)
            paths = {f["path"] for f in rm.load_json(os.path.join(out, "model.json"))["files"]}
            self.assertNotIn("build/gen.py", paths)
            self.assertFalse(any(p.startswith("repo-architecture/") for p in paths))
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
