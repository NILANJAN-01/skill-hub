"""Tests for lint_check.py (stdlib only; no real linters are run)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lint_check  # noqa: E402

SAMPLE = os.path.join(HERE, "fixtures", "sample-project")


def rules(findings):
    return sorted({f["rule"] for f in findings})


def fake_which(installed):
    """A resolve_exe stand-in that 'installs' only the given executables."""
    return lambda exe, node, root: f"/usr/bin/{exe}" if exe in installed else None


def run_cli(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = lint_check.main(argv)
    return code, out.getvalue()


class BuiltinChecks(unittest.TestCase):
    def test_clean_file_has_no_findings(self):
        self.assertEqual(lint_check.check_text("a.py", b"x = 1\n"), [])

    def test_conflict_markers(self):
        text = b"a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> topic\n"
        found = [f for f in lint_check.check_text("a.txt", text) if f["rule"] == "conflict-marker"]
        self.assertEqual([f["line"] for f in found], [2, 4, 6])
        self.assertTrue(all(f["severity"] == "error" for f in found))

    def test_lone_equals_line_is_not_a_conflict(self):
        self.assertEqual(lint_check.check_text("doc.rst", b"Title\n=======\n"), [])

    def test_markers_in_markdown_fences_are_examples(self):
        text = b"# Merging\n\n```\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n```\n"
        self.assertEqual(lint_check.check_text("guide.md", text), [])

    def test_python_syntax_error(self):
        found = lint_check.check_text("bad.py", b"def f(:\n    pass\n")
        self.assertEqual(rules(found), ["syntax"])
        self.assertEqual(found[0]["line"], 1)

    def test_json_syntax_error_and_jsonc_skipped(self):
        bad = b'{"a": 1,}\n'
        self.assertEqual(rules(lint_check.check_text("data.json", bad)), ["syntax"])
        self.assertEqual(lint_check.check_text("tsconfig.json", bad), [])
        self.assertEqual(lint_check.check_text(".vscode/settings.json", bad), [])

    def test_debugger_calls(self):
        self.assertEqual(rules(lint_check.check_text("a.py", b"x = 1\nbreakpoint()\n")), ["debugger"])
        self.assertEqual(rules(lint_check.check_text("a.ts", b"let x = 1;\ndebugger;\n")), ["debugger"])
        self.assertEqual(rules(lint_check.check_text("a.rs", b"fn main() { dbg!(1); }\n")), ["debugger"])

    def test_whitespace_rules(self):
        found = lint_check.check_text("a.js", b"let a = 1;  \r\nlet b = 2;\n\tlet c;\n  let d;")
        self.assertEqual(rules(found), ["final-newline", "line-endings", "mixed-indent", "trailing-whitespace"])

    def test_markdown_trailing_spaces_allowed(self):
        self.assertEqual(lint_check.check_text("a.md", b"line one  \nline two\n"), [])

    def test_long_lines_summarised_once(self):
        text = ("x = '" + "a" * 130 + "'\n").encode() * 3
        found = lint_check.check_text("a.py", text, max_line=120)
        self.assertEqual(rules(found), ["line-length"])
        self.assertEqual(len(found), 1)
        self.assertIn("3 lines", found[0]["message"])
        self.assertEqual(lint_check.check_text("a.py", text, max_line=0), [])

    def test_binary_and_generated_files_skipped(self):
        self.assertEqual(lint_check.check_text("img.png", b"\x89PNG\0\0 \n"), [])
        self.assertEqual(lint_check.check_text("package-lock.json", b"{bad"), [])


class Planning(unittest.TestCase):
    def test_languages_in_sample(self):
        langs = lint_check.count_languages(lint_check.list_files(SAMPLE))
        self.assertEqual(set(langs), {"python", "typescript", "shell"})

    def test_configured_linters_win(self):
        files = lint_check.list_files(SAMPLE)
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"ruff", "flake8", "shellcheck"})):
            plan = lint_check.make_plan(SAMPLE, files)
        self.assertIn("ruff", plan["selected"])          # pyproject.toml has [tool.ruff]
        self.assertNotIn("flake8", plan["selected"])     # installed but ruff is the configured one
        self.assertIn("eslint", plan["selected"])        # package.json has eslintConfig ...
        eslint = next(r for r in plan["linters"] if r["id"] == "eslint")
        self.assertIn("NOT INSTALLED", eslint["reason"])  # ... but it is not installed
        self.assertIn("shellcheck", plan["selected"])    # default for shell

    def test_default_when_nothing_configured(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"flake8", "mypy"})):
            plan = lint_check.make_plan(empty, ["x.py"])
        self.assertEqual(plan["selected"], ["flake8"])   # mypy is a type checker: only when configured

    def test_needs_config_not_picked_by_default_and_note_given(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"sqlfluff"})):
            plan = lint_check.make_plan(SAMPLE, ["q.sql"])
        self.assertEqual(plan["selected"], [])
        self.assertTrue(any(n.startswith("sql:") for n in plan["notes"]))

    def test_markers_required(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"cargo"})):
            plan = lint_check.make_plan(SAMPLE, ["src/main.rs"])  # no Cargo.toml in the sample
        self.assertEqual(plan["selected"], [])

    def test_only(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            plan = lint_check.make_plan(SAMPLE, ["x.py"], only=["pylint"])
        self.assertEqual(plan["selected"], ["pylint"])

    def test_unknown_only_id_is_a_usage_error(self):
        code, _ = run_cli_expect_exit(["detect", SAMPLE, "--only", "nope"])
        self.assertEqual(code, 2)


def run_cli_expect_exit(argv):
    try:
        return run_cli(argv)
    except SystemExit as e:
        return e.code, ""


class Commands(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(lint_check, "resolve_exe", fake_which(set()))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dir_target_appends_dot(self):
        cmds = lint_check.build_commands(lint_check.BY_ID["ruff"], SAMPLE, ["a.py"], False, False)
        self.assertEqual(cmds, [["ruff", "check", "."]])

    def test_changed_files_passed_to_file_aware_tools(self):
        cmds = lint_check.build_commands(lint_check.BY_ID["ruff"], SAMPLE, ["a.py", "b.ts"], True, True)
        self.assertEqual(cmds, [["ruff", "check", "--fix", "a.py"]])

    def test_changed_with_no_matching_files_skips(self):
        self.assertEqual(lint_check.build_commands(lint_check.BY_ID["go-vet"], SAMPLE, ["a.py"], True, False), [])

    def test_root_target_ignores_files(self):
        cmds = lint_check.build_commands(lint_check.BY_ID["go-vet"], SAMPLE, ["a.go"], True, False)
        self.assertEqual(cmds, [["go", "vet", "./..."]])

    def test_files_target_is_chunked(self):
        files = [f"scripts/s{i:03}.sh" for i in range(450)]
        cmds = lint_check.build_commands(lint_check.BY_ID["shellcheck"], SAMPLE, files, False, False)
        self.assertGreater(len(cmds), 2)
        self.assertEqual(sum(len(c) - 1 for c in cmds), 450)


GRADLE = os.path.join(HERE, "fixtures", "gradle-project")
MAVEN = os.path.join(HERE, "fixtures", "maven-project")


class JavaKotlin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_gradle_plugins_found_in_kts_and_version_catalog(self):
        plugins, check, fix = lint_check.build_tasks(lint_check.BY_ID["gradle-lint"], GRADLE)
        self.assertEqual(plugins, ["checkstyle", "ktlint", "detekt"])
        self.assertEqual(check, ["checkstyleMain", "ktlintCheck", "detekt"])
        self.assertEqual(fix, ["ktlintFormat"])

    def test_gradle_groovy_dsl_and_android(self):
        self.write("build.gradle", "plugins {\n    id 'com.android.application'\n}\napply plugin: 'pmd'\n")
        plugins, check, fix = lint_check.build_tasks(lint_check.BY_ID["gradle-lint"], self.tmp)
        self.assertEqual(plugins, ["pmd", "android-lint"])
        self.assertEqual(fix, ["lintFix"])

    def test_gradle_build_without_lint_plugins(self):
        self.write("build.gradle.kts", "plugins {\n    java\n}\ncheckstyleVersion = \"10\"\n")
        self.assertEqual(lint_check.build_tasks(lint_check.BY_ID["gradle-lint"], self.tmp), ([], [], []))

    def test_maven_plugins(self):
        plugins, check, fix = lint_check.build_tasks(lint_check.BY_ID["maven-lint"], MAVEN)
        self.assertEqual(plugins, ["checkstyle", "spotless"])
        self.assertEqual(check, ["checkstyle:check", "spotless:check"])
        self.assertEqual(fix, ["spotless:apply"])

    def test_build_linter_wins_over_standalone_copies(self):
        files = lint_check.list_files(GRADLE)
        with mock.patch.object(lint_check, "resolve_build", return_value=["gradlew"]), \
                mock.patch.object(lint_check, "resolve_exe", fake_which({"checkstyle", "ktlint", "detekt"})):
            plan = lint_check.make_plan(GRADLE, files)
        self.assertEqual(plan["selected"], ["gradle-lint"])  # config/checkstyle/checkstyle.xml is the build's
        self.assertEqual(plan["notes"], [])

    def test_gradle_and_maven_commands(self):
        with mock.patch.object(lint_check, "resolve_build", return_value=["gradlew"]):
            cmds = lint_check.build_commands(lint_check.BY_ID["gradle-lint"], GRADLE, ["a.kt"], False, False)
            fixes = lint_check.build_commands(lint_check.BY_ID["gradle-lint"], GRADLE, ["a.kt"], False, True)
        self.assertEqual(cmds, [["gradlew", "--console=plain", "--continue", "checkstyleMain", "ktlintCheck", "detekt"]])
        self.assertEqual(fixes, [["gradlew", "--console=plain", "--continue", "ktlintFormat"]])
        with mock.patch.object(lint_check, "resolve_build", return_value=None):  # falls back to the bare name
            cmds = lint_check.build_commands(lint_check.BY_ID["maven-lint"], MAVEN, ["A.java"], False, False)
        self.assertEqual(cmds, [["mvnw", "-B", "-fae", "checkstyle:check", "spotless:check"]])

    def test_build_linter_skipped_when_no_jvm_file_changed(self):
        cmds = lint_check.build_commands(lint_check.BY_ID["gradle-lint"], GRADLE, ["README.md"], True, False)
        self.assertEqual(cmds, [])

    def test_maven_fix_dry_run(self):
        with mock.patch.object(lint_check, "resolve_build", return_value=["mvnw"]), \
                mock.patch.object(lint_check, "run_command") as runner:
            code, out = run_cli(["run", MAVEN, "--fix"])
        runner.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("$ mvnw -B -fae spotless:apply", out)

    def test_wrapper_not_found_message(self):
        with mock.patch.object(lint_check, "resolve_build", return_value=None):
            code, out = run_cli(["run", GRADLE])
        self.assertEqual(code, 3)
        self.assertIn("no gradlew wrapper in the project and no gradle on PATH", out)

    def test_no_lint_plugin_hints_the_build(self):
        self.write("pom.xml", "<project></project>\n")
        self.write("src/main/java/App.java", "class App {}\n")
        with mock.patch.object(lint_check, "resolve_build", return_value=["mvnw"]), \
                mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            plan = lint_check.make_plan(self.tmp, lint_check.list_files(self.tmp))
        self.assertEqual(plan["selected"], [])
        self.assertIn("maven-lint", plan["notes"][0])

    def test_standalone_ktlint_when_build_has_no_plugins(self):
        self.write("build.gradle.kts", "plugins {\n    kotlin(\"jvm\")\n}\n")
        with mock.patch.object(lint_check, "resolve_build", return_value=["gradlew"]), \
                mock.patch.object(lint_check, "resolve_exe", fake_which({"ktlint"})):
            plan = lint_check.make_plan(self.tmp, ["src/main/kotlin/A.kt"])
        self.assertEqual(plan["selected"], ["ktlint"])

    def test_standalone_checkstyle_uses_project_config(self):
        self.write("checkstyle.xml", "<module name=\"Checker\"/>\n")
        with mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            cmds = lint_check.build_commands(lint_check.BY_ID["checkstyle"], self.tmp, ["src/App.java"], False, False)
        self.assertEqual(cmds, [["checkstyle", "-c", "checkstyle.xml", "src/App.java"]])
        empty = os.path.join(self.tmp, "other")
        os.makedirs(empty)
        with mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            cmds = lint_check.build_commands(lint_check.BY_ID["checkstyle"], empty, ["App.java"], False, False)
        self.assertEqual(cmds, [["checkstyle", "-c", "/google_checks.xml", "App.java"]])

    def test_print_stack_trace_builtin(self):
        java = b"class A {\n    void f() {\n        try { g(); } catch (Exception e) { e.printStackTrace(); }\n    }\n}\n"
        found = lint_check.check_text("A.java", java)
        self.assertEqual([(f["rule"], f["line"]) for f in found], [("debugger", 3)])
        self.assertEqual(rules(lint_check.check_text("A.kt", b"fun f() {\n    e.printStackTrace()\n}\n")),
                         ["debugger"])


class RunCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(SAMPLE, os.path.join(self.tmp, "p"))
        self.root = os.path.join(self.tmp, "p")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_fix_without_yes_is_a_dry_run(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"ruff"})), \
                mock.patch.object(lint_check, "run_command") as runner:
            code, out = run_cli(["run", self.root, "--only", "ruff", "--fix"])
        runner.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertIn("$ ruff check --fix .", out)

    def test_failing_linter_fails_the_run(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which({"ruff"})), \
                mock.patch.object(lint_check, "run_command", return_value=(1, "app.py:1:1: F401 unused")):
            code, out = run_cli(["run", self.root, "--only", "ruff", "--format", "json"])
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["linters"][0]["output"], "app.py:1:1: F401 unused")

    def test_missing_linter_is_incomplete(self):
        with mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            code, out = run_cli(["run", self.root, "--only", "ruff"])
        self.assertEqual(code, 3)
        self.assertIn("result: INCOMPLETE", out)

    def test_builtin_error_fails_run(self):
        with open(os.path.join(self.root, "app.py"), "a", encoding="utf-8") as fh:
            fh.write("def broken(:\n")
        with mock.patch.object(lint_check, "resolve_exe", fake_which(set())):
            code, out = run_cli(["run", self.root, "--only", "ruff"])
        self.assertEqual(code, 1)
        self.assertIn("[syntax]", out)

    def test_basic_cli_exit_codes(self):
        code, out = run_cli(["basic", self.root])
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.root, "data.json"), "w", encoding="utf-8") as fh:
            fh.write("{oops}\n")
        code, out = run_cli(["basic", self.root])
        self.assertEqual(code, 1)
        self.assertIn("data.json:1:2: error [syntax]", out)


if __name__ == "__main__":
    unittest.main()
