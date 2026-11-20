"""Tests for tools/hub.py (standard library only; new-skill runs against a throwaway mini repository).

    python -m unittest discover -s tools -p "test_hub.py" -v
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import hub  # noqa: E402
import hublib  # noqa: E402
import validate_skills  # noqa: E402

TITLES = '''CATEGORY_TITLES = {
    "hub-tools": "Hub tools",
    "git-getting-started": "Git: getting started",
}
'''


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hub.main(argv)
    return code, out.getvalue() + err.getvalue()


class MiniRepo(unittest.TestCase):
    """A repository with just what new-skill touches."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / "tools").mkdir()
        shutil.copy(TOOLS / "hublib.py", self.root / "tools" / "hublib.py")
        (self.root / "tools" / "build_catalog.py").write_text("# generator\n" + TITLES, encoding="utf-8")
        shutil.copytree(REPO / "template", self.root / "template")
        (self.root / ".claude-plugin").mkdir()
        self.market = {"name": "skill-hub", "owner": {"name": "x"}, "plugins": [
            {"name": "hub-tools", "description": "d", "source": "./", "strict": False, "category": "hub-tools",
             "skills": ["./skills/generic/hub/old-skill"]},
            {"name": "git-skills", "description": "d", "source": "./", "strict": False, "category": "git-skills",
             "skills": []}]}
        (self.root / ".claude-plugin" / "marketplace.json").write_text(json.dumps(self.market), encoding="utf-8")
        (self.root / "examples").mkdir()
        (self.root / "examples" / "prompts.json").write_text('{"old-skill": ["a", "b"]}\n', encoding="utf-8")
        old = self.root / "skills" / "generic" / "hub" / "old-skill"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("---\nname: old-skill\ndescription: x\n---\n", encoding="utf-8")

    def new(self, *args):
        return run(["--root", str(self.root), "new-skill", *args, "--no-build"])

    def market_now(self):
        return json.loads((self.root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    def prompts_now(self):
        return json.loads((self.root / "examples" / "prompts.json").read_text(encoding="utf-8"))


class NewSkill(MiniRepo):
    def test_scaffold_into_existing_plugin(self):
        code, out = self.new("development/code-quality/type-checker", "--plugin", "hub-tools",
                             "--also-plugin", "git-skills", "--description", "Check types. Use when asked.",
                             "--prompt", "check my types", "--prompt", "run mypy")
        self.assertEqual(code, 0, out)
        md = self.root / "skills/development/code-quality/type-checker/SKILL.md"
        fm, body = hublib.parse_frontmatter(md.read_text(encoding="utf-8"))
        self.assertEqual(fm["name"], "type-checker")
        self.assertEqual(fm["description"], "Check types. Use when asked.")
        self.assertEqual(fm["metadata"], {"title": "Type checker", "category": "hub-tools"})
        self.assertIn("# Type checker", body)
        self.assertTrue((md.parent / "references" / "details.md").is_file())
        plugins = {p["name"]: p["skills"] for p in self.market_now()["plugins"]}
        self.assertIn("./skills/development/code-quality/type-checker", plugins["hub-tools"])
        self.assertIn("./skills/development/code-quality/type-checker", plugins["git-skills"])
        self.assertEqual(self.prompts_now()["type-checker"], ["check my types", "run mypy"])
        self.assertNotIn("Replace the TODO", out)

    def test_new_plugin_gets_title_before_git_entries(self):
        code, out = self.new("testing/perf/load-tester", "--plugin", "perf-tools", "--plugin-title",
                             "Performance: load tests", "--plugin-description", "Load testing")
        self.assertEqual(code, 0, out)
        plugin = self.market_now()["plugins"][-1]
        self.assertEqual((plugin["name"], plugin["category"], plugin["skills"]),
                         ("perf-tools", "perf-tools", ["./skills/testing/perf/load-tester"]))
        titles = (self.root / "tools" / "build_catalog.py").read_text(encoding="utf-8")
        self.assertLess(titles.index('"perf-tools"'), titles.index('"git-getting-started"'))
        self.assertGreater(titles.index('"perf-tools"'), titles.index('"hub-tools"'))
        self.assertIn("Replace the TODO placeholders in the description and the example prompts", out)

    def test_placeholders_fail_validation(self):
        self.new("generic/hub/half-done", "--plugin", "hub-tools")
        d = self.root / "skills/generic/hub/half-done"
        errors, _ = validate_skills.check_skill(d, {"hub-tools"}, {"half-done"})
        joined = "\n".join(errors)
        self.assertIn("TODO placeholder", joined)
        self.assertIn("template text", joined)
        self.assertTrue(all(p.startswith(validate_skills.PLACEHOLDER) for p in self.prompts_now()["half-done"]))

    def test_dry_run_writes_nothing(self):
        before = self.market_now()
        code, out = self.new("generic/hub/new-one", "--plugin", "hub-tools", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertFalse((self.root / "skills/generic/hub/new-one").exists())
        self.assertEqual(self.market_now(), before)

    def test_refusals_write_nothing(self):
        cases = [
            (["generic/new-one", "--plugin", "hub-tools"], "<area>/<group>/<name>"),
            (["nowhere/hub/new-one", "--plugin", "hub-tools"], "unknown area"),
            (["generic/hub/Bad_Name", "--plugin", "hub-tools"], "lowercase"),
            (["development/other/old-skill", "--plugin", "hub-tools"], "already exists"),
            (["generic/hub/new-one", "--plugin", "hub-tool"], "Did you mean hub-tools"),
            (["generic/hub/new-one", "--plugin", "x-tools", "--plugin-title", "X"], "--plugin-description"),
            (["generic/hub/new-one", "--plugin", "hub-tools", "--also-plugin", "nope"], "--also-plugin"),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                code, out = self.new(*args)
                self.assertEqual(code, 2)
                self.assertIn(expected, out)
        self.assertEqual(self.market_now(), self.market)
        self.assertFalse((self.root / "skills/generic/hub/new-one").exists())

    def test_category_title_is_idempotent(self):
        once = hub.add_category_title(TITLES, "hub-tools", "Other")
        self.assertEqual(once, TITLES)


class CheckPlanning(unittest.TestCase):
    def labels(self, changed):
        first, steps = hub.plan_checks(REPO, changed)
        return [s.label for s in steps], first

    def test_everything(self):
        labels, first = self.labels(None)
        self.assertEqual(first.args, ["tools/build_catalog.py"])
        self.assertIn("tools tests", labels)
        self.assertIn("mcp-server tests", labels)
        self.assertIn("tests: lint-checker", labels)
        self.assertEqual(len([l for l in labels if l.startswith("tests: ")]), len(hub.skill_test_dirs(REPO)))

    def test_one_skill_changed(self):
        labels, _ = self.labels(["skills/development/code-quality/lint-checker/SKILL.md"])
        self.assertEqual([l for l in labels if l.startswith("tests: ")], ["tests: lint-checker"])
        self.assertIn("tools tests", labels)
        self.assertNotIn("mcp-server tests", labels)

    def test_docs_only_change_runs_only_validation(self):
        labels, _ = self.labels(["CONTRIBUTING.md"])
        self.assertEqual(labels, ["validate skills", "generated files up to date", "byte-compile"])

    def test_mcp_change(self):
        labels, _ = self.labels(["skill-hub-mcp/skill_hub_mcp/hub.py"])
        self.assertIn("skill-hub-mcp tests", labels)
        self.assertNotIn("mcp-server tests", labels)

    def test_no_build(self):
        self.assertIsNone(hub.plan_checks(REPO, None, build=False)[0])


class CheckOutput(unittest.TestCase):
    def test_failure_excerpt_keeps_unittest_blocks(self):
        out = "test_a ... ok\ntest_b ... FAIL\n" + "=" * 70 + "\nFAIL: test_b\nAssertionError: 1 != 2\n\nFAILED (failures=1)"
        excerpt = hub.failure_excerpt(out, 40)
        self.assertTrue(excerpt.startswith("====="))
        self.assertNotIn("test_a ... ok", excerpt)
        long = hub.failure_excerpt("\n".join(f"line {i}" for i in range(100)), 10)
        self.assertEqual(len(long.splitlines()), 10)
        self.assertIn("more lines", long)
        self.assertTrue(long.endswith("line 99"))

    def test_validator_errors_only(self):
        out = "WARN  a: w\nERROR skills/x: bad\n\n1 skills: 1 error(s)"
        self.assertEqual(hub.failure_excerpt(out, 40), "ERROR skills/x: bad")

    def fake_plan(self, codes):
        steps = [hub.Step(f"step {i}", ["-c", f"import sys; print('out {i}'); sys.exit({c})"]) for i, c in enumerate(codes)]
        skipped = hub.Step("tests: image-inspector", ["-c", "pass"], group="skill tests")
        skipped.skipped = "needs PIL"
        return lambda root, changed, build=True: (None, steps + [skipped])

    def test_check_reports_only_failures(self):
        with mock.patch.object(hub, "plan_checks", self.fake_plan([0, 3])):
            code, out = run(["check", "--no-build"])
        self.assertEqual(code, 1)
        self.assertIn("ok    step 0", out)
        self.assertIn("FAIL  step 1  (exit 3)  ->  python -c", out)
        self.assertIn("out 1", out)
        self.assertNotIn("out 0", out)
        self.assertIn("skip  tests: image-inspector: needs PIL", out)
        self.assertIn("check FAILED: 1 of", out)

    def test_check_ok(self):
        with mock.patch.object(hub, "plan_checks", self.fake_plan([0, 0])):
            code, out = run(["check", "--no-build"])
        self.assertEqual(code, 0)
        self.assertTrue(out.rstrip().endswith("check OK."))

    def test_command_quotes_globs(self):
        step = hub.Step("t", ["-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"])
        self.assertTrue(step.command.endswith('-p "test_*.py"'))


if __name__ == "__main__":
    unittest.main()
