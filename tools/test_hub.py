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
        self.assertFalse((md.parent / hub.TEMPLATE_SKILL).exists())
        self.assertNotIn("Claude", md.read_text(encoding="utf-8"))  # the template is agent-neutral
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


class DistributionChecks(unittest.TestCase):
    """validate_skills.py checks that keep every channel (installer, npx skills, plugins) shipping the right skills."""

    def test_stray_skill_files(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        for rel in ("skills/generic/hub/ok-skill", "template", "skills/generic/hub/ok-skill/fixtures/nested",
                    ".git/x", "node_modules/pkg", "generated-skills/draft"):
            (root / rel).mkdir(parents=True)
            (root / rel / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        (root / "template" / "SKILL.md.tmpl").write_text("", encoding="utf-8")
        self.assertEqual(validate_skills.stray_skill_files(root),
                         ["skills/generic/hub/ok-skill/fixtures/nested/SKILL.md", "template/SKILL.md"])

    def test_repository_has_no_stray_skill_files(self):
        self.assertEqual(validate_skills.stray_skill_files(REPO), [])
        self.assertTrue((REPO / "template" / hub.TEMPLATE_SKILL).is_file())

    def test_requirement_errors(self):
        requires = {"dispatcher": ["router"], "router": [], "selfish": ["selfish"], "typo": ["ruoter"]}
        plugins = [{"name": "full", "skills": ["./skills/a/b/dispatcher", "./skills/a/b/router"]},
                   {"name": "partial", "skills": ["./skills/a/b/dispatcher"]}]
        msgs = [m for _, m in validate_skills.requirement_errors(requires, plugins)]
        self.assertEqual(len(msgs), 3, msgs)
        self.assertIn("lists the skill itself", msgs[0])
        self.assertIn("unknown skill 'ruoter'", msgs[1])
        self.assertIn("plugin 'partial' lists dispatcher but not router", msgs[2])

    def test_requires_of(self):
        self.assertEqual(hublib.requires_of({"metadata": {"requires": "a, b ,"}}), ["a", "b"])
        self.assertEqual(hublib.requires_of({"metadata": "bad"}), [])
        self.assertEqual(hublib.requires_of({}), [])


class CheckPlanning(unittest.TestCase):
    def labels(self, changed):
        first, steps = hub.plan_checks(REPO, changed)
        return [s.label for s in steps], first

    def test_everything(self):
        labels, first = self.labels(None)
        self.assertEqual(first.args, ["tools/build_catalog.py"])
        self.assertIn("tools tests: test_hub.py", labels)
        self.assertEqual(len([l for l in labels if l.startswith("tools tests: ")]),
                         len(list((REPO / "tools").glob("test_*.py"))))
        self.assertIn("mcp-server tests", labels)
        self.assertIn("tests: lint-checker", labels)
        self.assertEqual(len([l for l in labels if l.startswith("tests: ")]), len(hub.skill_test_dirs(REPO)))

    def test_one_skill_changed(self):
        labels, _ = self.labels(["skills/development/code-quality/lint-checker/SKILL.md"])
        self.assertEqual([l for l in labels if l.startswith("tests: ")], ["tests: lint-checker"])
        self.assertIn("tools tests: test_install.py", labels)
        self.assertNotIn("mcp-server tests", labels)

    def test_docs_only_change_runs_only_validation(self):
        labels, _ = self.labels(["CONTRIBUTING.md"])
        self.assertEqual(labels, ["validate skills", "generated files up to date", "byte-compile"])

    def test_mcp_change(self):
        labels, _ = self.labels(["skill-hub-mcp/skill_hub_mcp/hub.py"])
        self.assertIn("skill-hub-mcp tests", labels)
        self.assertNotIn("mcp-server tests", labels)
        self.assertNotIn("python 3.8 compatibility", labels)

    def test_python38_check_runs_for_skills_and_installer(self):
        for path in ("skills/generic/hub/skill-router/scripts/route.py", "tools/install.py"):
            with self.subTest(path=path):
                labels, _ = self.labels([path])
                self.assertIn("python 3.8 compatibility", labels)
        with mock.patch.object(hub.importlib.util, "find_spec", return_value=None):
            _, steps = hub.plan_checks(REPO, None)
        py38 = [s for s in steps if s.label == "python 3.8 compatibility"][0]
        self.assertIn("pip install vermin", py38.skipped)

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


def git(root, *args):
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *args],
                   cwd=root, check=True, capture_output=True)


class GitRepo(unittest.TestCase):
    """Each test gets a copy of one committed repository, built once per class (git calls are slow on Windows)."""

    @classmethod
    def setUpClass(cls):
        cls.template = Path(tempfile.mkdtemp())
        git(cls.template, "init", "-q", "--template=")  # no sample hooks: smaller and faster to copy
        (cls.template / "a.txt").write_text("one\n", encoding="utf-8")
        git(cls.template, "add", "a.txt")
        git(cls.template, "commit", "-qm", "base")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.template, True)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "repo"
        self.addCleanup(shutil.rmtree, self.root.parent, True)
        shutil.copytree(self.template, self.root)

    def change(self, text):
        (self.root / "a.txt").write_text(text, encoding="utf-8")


class ChangedPaths(GitRepo):
    def test_status_covers_edits_untracked_and_renames(self):
        self.assertEqual(hub.changed_paths(self.root, "HEAD"), [])
        (self.root / "dir").mkdir()
        (self.root / "dir" / "new file.txt").write_text("x\n", encoding="utf-8")
        git(self.root, "mv", "a.txt", "b.txt")
        self.assertEqual(hub.changed_paths(self.root, "HEAD"), ["a.txt", "b.txt", "dir/new file.txt"])

    def test_repo_info(self):
        state, head = hub._repo_info(self.root)
        self.assertEqual(state.name, "hub-hook-state.json")
        self.assertEqual(len(head), 40)


class PostEditHook(unittest.TestCase):
    def hook(self, rel, build=(0, "")):
        data = {"tool_input": {"file_path": str(REPO / rel)}}
        with mock.patch.object(hub, "_run_build", return_value=build) as builder:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = hub.hook_post_edit(REPO, data)
        return code, err.getvalue(), builder.called

    def test_edited_path(self):
        self.assertEqual(hub.edited_path(REPO, {"tool_input": {"file_path": str(REPO / "rule" / "x.md")}}), "rule/x.md")
        self.assertEqual(hub.edited_path(REPO, {"tool_input": {"file_path": "tools/hub.py"}, "cwd": str(REPO)}),
                         "tools/hub.py")
        self.assertEqual(hub.edited_path(REPO, {"tool_response": {"filePath": str(REPO / "a.md")}}), "a.md")
        self.assertIsNone(hub.edited_path(REPO, {"tool_input": {"file_path": str(REPO.parent / "elsewhere.md")}}))
        self.assertIsNone(hub.edited_path(REPO, {}))
        if sys.platform == "win32":
            posix = "/" + REPO.drive[0].lower() + REPO.as_posix()[2:] + "/catalog.json"
            self.assertEqual(hub.edited_path(REPO, {"tool_input": {"file_path": posix}}), "catalog.json")

    def test_source_edit_rebuilds_silently(self):
        self.assertEqual(self.hook("skills/development/code-quality/lint-checker/SKILL.md"), (0, "", True))
        self.assertEqual(self.hook(".claude-plugin/marketplace.json"), (0, "", True))

    def test_unrelated_edit_does_nothing(self):
        self.assertEqual(self.hook("index.html"), (0, "", False))
        self.assertEqual(self.hook("skills/x/y/z/scripts/__pycache__/a.pyc"), (0, "", False))

    def test_generated_file_edit_is_reported(self):
        code, err, built = self.hook("catalog.json")
        self.assertEqual((code, built), (2, True))
        self.assertIn("generated file", err)

    def test_build_failure_is_reported(self):
        code, err, _ = self.hook("examples/prompts.json", build=(1, "Traceback\nValueError: bad json"))
        self.assertEqual(code, 2)
        self.assertIn("build_catalog.py failed", err)


class StopHook(GitRepo):
    def stop(self, check=(1, "check FAILED: 1 of 5 steps."), session="s1"):
        out = io.StringIO()
        with mock.patch.object(hub, "run_check", return_value=check) as checker, contextlib.redirect_stdout(out):
            code = hub.hook_stop(self.root, {"session_id": session})
        self.assertEqual(code, 0)
        text = out.getvalue().strip()
        return (json.loads(text) if text else None), checker.called

    def test_clean_tree_is_not_checked(self):
        self.assertEqual(self.stop(), (None, False))

    def test_failure_blocks_once_per_state(self):
        self.change("two\n")
        message, checked = self.stop()
        self.assertTrue(checked)
        self.assertEqual(message["decision"], "block")
        self.assertIn("check FAILED", message["reason"])
        self.assertEqual(self.stop(), (None, False))     # same state: the agent may stop now
        self.change("three, longer\n")                     # new state: checked and blocked again
        self.assertEqual(self.stop()[0]["decision"], "block")

    def test_gives_up_after_max_blocks(self):
        for i in range(hub.MAX_STOP_BLOCKS):
            self.change("x" * (i + 2) + "\n")
            self.assertEqual(self.stop()[0]["decision"], "block")
        self.change("final state\n")
        message, _ = self.stop()
        self.assertIn("stopping anyway", message["systemMessage"])

    def test_pass_is_remembered(self):
        self.change("two\n")
        self.assertEqual(self.stop(check=(0, "check OK.")), (None, True))
        self.assertEqual(self.stop(), (None, False))       # unchanged since the pass: not rerun
        self.assertEqual(self.stop(session="other"), (None, False))

    def test_hooks_off(self):
        self.change("two\n")
        with mock.patch.dict("os.environ", {hub.HOOKS_OFF_ENV: "off"}), \
                mock.patch.object(hub, "run_check") as checker:
            self.assertEqual(run(["--root", str(self.root), "hook", "stop"])[0], 0)
        checker.assert_not_called()

    def test_internal_errors_never_block(self):
        with mock.patch.object(hub, "hook_stop", side_effect=RuntimeError("boom")), \
                mock.patch.object(hub, "_hook_input", return_value={}):
            code, out = run(["--root", str(self.root), "hook", "stop"])
        self.assertEqual(code, 0)
        self.assertIn("internal error ignored", out)


class PreCommit(GitRepo):
    def hook_file(self):
        return self.root / ".git" / "hooks" / "pre-commit"

    def settings(self):
        return self.root / ".claude" / "settings.json"

    def test_setup_is_a_dry_run_without_yes(self):
        code, out = run(["--root", str(self.root), "setup-hooks"])
        self.assertEqual(code, 0)
        self.assertIn("Nothing was written", out)
        self.assertFalse(self.hook_file().exists())
        self.assertFalse(self.settings().exists())

    def test_install_and_remove_both(self):
        self.assertEqual(run(["--root", str(self.root), "setup-hooks", "--yes"])[0], 0)
        text = self.hook_file().read_text(encoding="utf-8")
        self.assertIn(hub.PRE_COMMIT_MARK, text)
        self.assertIn("tools/hub.py hook pre-commit", text)
        hooks = json.loads(self.settings().read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Edit|Write|MultiEdit|NotebookEdit")
        self.assertTrue(hooks["PostToolUse"][0]["hooks"][0]["command"].endswith("hook post-edit"))
        self.assertTrue(hooks["Stop"][0]["hooks"][0]["command"].endswith("hook stop"))
        self.assertIn("up to date", run(["--root", str(self.root), "setup-hooks", "--yes"])[1])
        self.assertEqual(run(["--root", str(self.root), "setup-hooks", "--remove", "--yes"])[0], 0)
        self.assertFalse(self.hook_file().exists())
        self.assertFalse(self.settings().exists())

    def test_agent_settings_merge_keeps_other_settings(self):
        mine = {"permissions": {"allow": ["Bash(git *)"]}, "hooks": {
            "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "log.sh"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "notify.sh"}]}]}}
        merged = hub.merged_agent_settings(mine)
        self.assertEqual(merged["permissions"], mine["permissions"])
        self.assertEqual(merged["hooks"]["PostToolUse"][0], mine["hooks"]["PostToolUse"][0])
        self.assertEqual(len(merged["hooks"]["PostToolUse"]), 2)
        self.assertEqual(merged["hooks"]["Stop"][0], mine["hooks"]["Stop"][0])
        self.assertEqual(hub.merged_agent_settings(merged), merged)          # idempotent
        self.assertEqual(hub.merged_agent_settings(merged, remove=True), mine)

    def test_agent_settings_invalid_json_refused(self):
        self.settings().parent.mkdir(parents=True)
        self.settings().write_text("{not json", encoding="utf-8")
        code, out = run(["--root", str(self.root), "setup-hooks", "--agent", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", out)
        self.assertEqual(self.settings().read_text(encoding="utf-8"), "{not json")

    def test_foreign_hook_is_left_alone(self):
        self.hook_file().parent.mkdir(parents=True, exist_ok=True)
        self.hook_file().write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
        code, out = run(["--root", str(self.root), "setup-hooks", "--git", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("leaving it alone", out)
        self.assertEqual(self.hook_file().read_text(encoding="utf-8"), "#!/bin/sh\necho mine\n")

    def test_pre_commit_blocks_on_failure(self):
        with mock.patch.object(hub, "run_check", return_value=(1, "check FAILED")) as checker:
            code, out = run(["--root", str(self.root), "hook", "pre-commit"])
        self.assertEqual(code, 1)
        self.assertIn("Commit blocked", out)
        self.assertEqual(checker.call_args.kwargs.get("build"), False)


if __name__ == "__main__":
    unittest.main()
