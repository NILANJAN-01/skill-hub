"""Tests for tools/install.py. Standard library only; every write goes to a temp folder.

    python -m unittest discover -s tools -p "test_*.py" -v
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402


def make_hub(root: Path, version: str = "1.0.0") -> None:
    skill = root / "skills" / "demo"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\nbody\n", encoding="utf-8")
    (skill / "scripts" / "run.py").write_text("print('v1')\n", encoding="utf-8")
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"metadata": {"version": version},
                    "plugins": [{"name": "demo-tools", "skills": ["./skills/demo"]}]}), encoding="utf-8")


class SameSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "hub"
        self.root.mkdir()
        make_hub(self.root)
        self.dest = Path(self.tmp.name) / "agent" / "skills"
        install.copy_skill(self.root, "demo", self.dest)
        self.src = self.root / "skills" / "demo"

    def test_fresh_copy_is_same(self):
        self.assertTrue(install.same_skill(self.src, self.dest / "demo"))

    def test_script_change_is_detected(self):
        (self.src / "scripts" / "run.py").write_text("print('v2')\n", encoding="utf-8")
        self.assertFalse(install.same_skill(self.src, self.dest / "demo"))

    def test_added_or_removed_file_is_detected(self):
        (self.src / "references").mkdir()
        (self.src / "references" / "new.md").write_text("x\n", encoding="utf-8")
        self.assertFalse(install.same_skill(self.src, self.dest / "demo"))
        (self.src / "references" / "new.md").unlink()
        (self.dest / "demo" / "scripts" / "run.py").unlink()
        self.assertFalse(install.same_skill(self.src, self.dest / "demo"))

    def test_line_endings_and_pycache_are_ignored(self):
        lf = (self.src / "SKILL.md").read_bytes().replace(b"\r\n", b"\n")
        (self.src / "SKILL.md").write_bytes(lf)
        (self.dest / "demo" / "SKILL.md").write_bytes(lf.replace(b"\n", b"\r\n"))
        cache = self.dest / "demo" / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "run.cpython-312.pyc").write_bytes(b"\0")
        self.assertTrue(install.same_skill(self.src, self.dest / "demo"))

    def test_plan_reports_script_only_change_as_outdated(self):
        project = Path(self.tmp.name) / "proj"
        install.copy_skill(self.root, "demo", project / ".claude" / "skills")
        (self.src / "scripts" / "run.py").write_text("print('v2')\n", encoding="utf-8")
        plan = install.make_plan(self.root, ["demo"], ["claude-code"], False, project)
        self.assertEqual(list(plan["outdated"].values()), [["demo"]])
        self.assertEqual(plan["uptodate"], 0)


class ManifestTests(unittest.TestCase):
    def test_install_and_remove_update_the_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root, dest = Path(d) / "hub", Path(d) / "skills"
            root.mkdir()
            make_hub(root, "2.3.4")
            install.copy_skill(root, "demo", dest)
            data = json.loads((dest / install.MANIFEST).read_text(encoding="utf-8"))
            self.assertEqual(data["skills"]["demo"]["version"], "2.3.4")
            install.record(dest, "demo", None)
            self.assertFalse((dest / install.MANIFEST).exists())

    def test_broken_manifest_is_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / install.MANIFEST).write_text("not json", encoding="utf-8")
            self.assertEqual(install.read_manifest(Path(d)), {"skills": {}})
            (Path(d) / install.MANIFEST).write_text("[1]", encoding="utf-8")
            self.assertEqual(install.read_manifest(Path(d)), {"skills": {}})


class ChecksumTests(unittest.TestCase):
    def test_checksum(self):
        data = b"archive"
        good = hashlib.sha256(data).hexdigest()
        sums = f"{'0' * 64}  install.py\n{good}  skill-hub-1.0.0.zip\n"
        self.assertIs(install.checksum_ok(data, sums, "skill-hub-1.0.0.zip"), True)
        self.assertIs(install.checksum_ok(b"tampered", sums, "skill-hub-1.0.0.zip"), False)
        self.assertIsNone(install.checksum_ok(data, sums, "skill-hub-9.9.9.zip"))


class RequiresTests(unittest.TestCase):
    """metadata.requires: installing a skill also installs the skills it needs next to it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "hub"
        for name, meta in (("dispatcher", '  requires: "router, missing-one"\n'), ("router", "  requires: core\n"),
                           ("core", "  title: Core\n"), ("loner", "")):
            d = self.root / "skills" / "generic" / "hub" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\nmetadata:\n{meta}---\nrequires: no\n",
                                        encoding="utf-8")

    def test_reads_frontmatter_only(self):
        self.assertEqual(install.skill_requires(self.root, "dispatcher"), ["router", "missing-one"])
        self.assertEqual(install.skill_requires(self.root, "loner"), [])   # body text is not frontmatter

    def test_adds_requirements_transitively_once(self):
        with mock.patch("builtins.print") as said:
            names = install.with_requirements(self.root, ["dispatcher", "loner", "core"])
        self.assertEqual(names, ["dispatcher", "loner", "core", "router"])   # unknown names are skipped
        self.assertIn("needed by dispatcher", said.call_args_list[0].args[0])
        self.assertEqual(install.with_requirements(self.root, ["loner"]), ["loner"])


class SkillFolderListsTests(unittest.TestCase):
    """skill-router and skill-orchestrator scan the folders agents read skills from; they keep their own copy
    of that list (they install on their own), so it must match AGENTS here."""

    def test_lists_match_agents(self):
        import ast
        project, user = set(), set()
        for a in install.AGENTS.values():
            project.update([a["project"]] if a.get("project") else [])
            project.update(a.get("also_reads") or [])
            user.update([a["global"]] if a.get("global") else [])
            user.update(a.get("global_also_reads") or [])
        repo = Path(__file__).resolve().parent.parent / "skills" / "generic" / "hub"
        for script in ("skill-router/scripts/route.py", "skill-orchestrator/scripts/orchestrate.py"):
            tree = ast.parse((repo / script).read_text(encoding="utf-8"))
            found = {t.id: set(ast.literal_eval(n.value)) for n in tree.body if isinstance(n, ast.Assign)
                     for t in n.targets if isinstance(t, ast.Name) and t.id in ("PROJECT_DIRS", "USER_DIRS")}
            with self.subTest(script=script):
                self.assertEqual(found["PROJECT_DIRS"], project, "project folders differ from AGENTS in install.py")
                self.assertEqual(found["USER_DIRS"], user, "user folders differ from AGENTS in install.py")


class Sandbox(unittest.TestCase):
    """A temp hub plus HOME / USERPROFILE / APPDATA / SKILLHUB_HOME pointing into a temp folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home, self.project, self.root = base / "home", base / "proj", base / "hub"
        for p in (self.home, self.project, self.root):
            p.mkdir()
        make_hub(self.root)
        server = self.root / "skill-hub-mcp" / "skill_hub_mcp"
        server.mkdir(parents=True)
        (server / "__main__.py").write_text("print('server')\n", encoding="utf-8")
        saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "APPDATA", "SKILLHUB_HOME")}

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        os.environ.update(HOME=str(self.home), USERPROFILE=str(self.home),
                          APPDATA=str(self.home / "AppData"), SKILLHUB_HOME=str(self.home / ".skill-hub"))
        self.entry = install.server_entry()


class McpJsonTests(Sandbox):
    def test_merge_keeps_other_servers_and_settings(self):
        cfg = self.home / ".cursor" / "mcp.json"
        cfg.parent.mkdir()
        cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}), encoding="utf-8")
        server = install.McpServer(entry=self.entry)
        self.assertEqual(server.check("cursor", True, self.project), "missing")
        self.assertEqual(server.apply(server.plan(["cursor"], True, self.project)), 1)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(set(data["mcpServers"]), {"other", "skill-hub"})
        self.assertTrue((cfg.parent / ("mcp.json" + install.BACKUP_SUFFIX)).is_file())
        self.assertEqual(server.check("cursor", True, self.project), "same")
        newer = install.McpServer(entry=install.server_entry(allow_install=True))
        self.assertEqual(newer.check("cursor", True, self.project), "differs")
        self.assertEqual(server.apply(server.plan(["cursor"], True, self.project, removing=True)), 1)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"], {"other": {"command": "x"}})

    def test_type_stdio_added_by_agent_still_counts_as_same(self):
        cfg = self.project / ".mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"skill-hub": dict(self.entry, type="stdio")}}), encoding="utf-8")
        self.assertEqual(install.McpServer(entry=self.entry).check("claude-code", False, self.project), "same")

    def test_unreadable_file_is_left_alone(self):
        cfg = self.project / ".mcp.json"
        cfg.write_text('{ // a comment\n "mcpServers": {} }', encoding="utf-8")
        server = install.McpServer(entry=self.entry)
        rows = server.plan(["claude-code"], False, self.project)
        self.assertEqual(rows[0]["status"], "unreadable")
        self.assertIn("unreadable: ", server.check("claude-code", False, self.project))
        install.ATTENTION.clear()
        self.assertEqual(server.apply(rows), 0)
        self.assertEqual(len(install.ATTENTION), 1)
        self.assertIn("// a comment", cfg.read_text(encoding="utf-8"))

    def test_agents_sharing_a_file_share_one_row(self):
        rows = install.McpServer(entry=self.entry).plan(["claude-code", "copilot", "cursor"], False, self.project)
        by_path = {r["path"]: r["agents"] for r in rows}
        self.assertEqual(by_path[self.project / ".mcp.json"], ["claude-code", "copilot"])
        self.assertEqual(len(rows), 2)

    def test_os_specific_user_path(self):
        path = install.mcp_config_path("devin", True, self.project)
        expected = "devin/mcp_config.json" if os.name == "nt" else ".config/devin/mcp_config.json"
        self.assertTrue(path.as_posix().endswith(expected))
        self.assertIsNone(install.mcp_config_path("universal", True, self.project))


class McpTomlTests(Sandbox):
    def test_add_update_remove_keeps_other_tables(self):
        cfg = self.home / ".codex" / "config.toml"
        cfg.parent.mkdir()
        cfg.write_text('model = "x"\n\n[mcp_servers.other]\ncommand = "o"\n\n'
                       '[mcp_servers.skill-hub]\ncommand = "old"\n\n[mcp_servers.skill-hub.env]\nA = "1"\n\n'
                       '[profiles.fast]\nmodel = "y"\n', encoding="utf-8")
        server = install.McpServer(entry=self.entry)
        self.assertEqual(server.check("codex", True, self.project), "differs")
        self.assertEqual(server.apply(server.plan(["codex"], True, self.project)), 1)
        text = cfg.read_text(encoding="utf-8")
        self.assertNotIn('"old"', text)
        self.assertNotIn("[mcp_servers.skill-hub.env]", text)
        self.assertIn("[mcp_servers.other]", text)
        self.assertIn("[profiles.fast]", text)
        self.assertEqual(text.count("[mcp_servers.skill-hub]"), 1)
        self.assertEqual(server.check("codex", True, self.project), "same")
        self.assertEqual(server.apply(server.plan(["codex"], True, self.project, removing=True)), 1)
        text = cfg.read_text(encoding="utf-8")
        self.assertNotIn("skill-hub", text)
        self.assertIn('model = "y"', text)

    def test_rendered_paths_are_escaped(self):
        block = install.toml_render("mcp_servers", {"command": "C:\\Py\\python.exe", "args": ["-m", "x"],
                                                    "env": {"PYTHONPATH": "C:\\a b"}})
        self.assertIn('command = "C:\\\\Py\\\\python.exe"', block)
        self.assertIn('env = { PYTHONPATH = "C:\\\\a b" }', block)


class SetupFlowTests(Sandbox):
    def test_setup_then_doctor_then_uninstall(self):
        agents = ["cursor", "codex"]
        install.execute(self.root, agents, ["demo"], True, self.project, mcp=True, yes=True)
        snap = install.snapshot_dir()
        self.assertTrue((snap / "skill-hub-mcp" / "skill_hub_mcp" / "__main__.py").is_file())
        self.assertEqual(install.snapshot_state(self.root), "current")
        self.assertTrue((self.home / ".cursor" / "skills" / "demo" / "SKILL.md").is_file())
        self.assertIn("skill-hub", json.loads((self.home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"])
        self.assertIn("[mcp_servers.skill-hub]", (self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        rows = install.McpServer(entry=self.entry).plan(agents, True, self.project)
        self.assertEqual({r["status"] for r in rows}, {"same"})

        (self.root / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: d2\n---\n", encoding="utf-8")
        self.assertEqual(install.snapshot_state(self.root), "outdated")

        install.execute(self.root, agents, ["demo"], True, self.project, mcp=True, yes=True,
                        remove=True, uninstall=True)
        self.assertFalse((self.home / ".cursor" / "skills" / "demo").exists())
        self.assertFalse((self.home / ".cursor" / "mcp.json").exists())    # created by setup, so removed again
        self.assertNotIn("skill-hub", (self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertFalse(snap.exists())
        self.assertEqual(list(self.home.rglob("*" + install.BACKUP_SUFFIX)), [])   # files we created: no backups

    def test_dry_run_writes_nothing(self):
        install.execute(self.root, ["cursor"], ["demo"], True, self.project, mcp=True, dry=True)
        self.assertFalse((self.home / ".cursor").exists())
        self.assertFalse(install.snapshot_dir().exists())


class ProfessionalFinishTests(Sandbox):
    """Exit codes, the closing summary, quiet output, license note and leaving nothing behind."""

    def run_quiet(self, *args, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = install.execute(self.root, *args, **kwargs)
        return code, out.getvalue()

    def test_exit_codes_ok_nothing_to_do_and_dry_run(self):
        code, out = self.run_quiet(["cursor"], ["demo"], True, self.project, yes=True)
        self.assertEqual(code, install.EXIT_OK)
        self.assertIn("Done: 1 skill folder(s)", out)
        self.assertEqual(self.run_quiet(["cursor"], ["demo"], True, self.project, yes=True)[0], install.EXIT_OK)
        self.assertEqual(self.run_quiet(["codex"], ["demo"], True, self.project, dry=True)[0], install.EXIT_OK)

    def test_skipped_config_means_partly_done(self):
        cfg = self.home / ".cursor" / "mcp.json"
        cfg.parent.mkdir()
        cfg.write_text('{ // comment\n', encoding="utf-8")
        code, out = self.run_quiet(["cursor"], ["demo"], True, self.project, mcp=True, yes=True)
        self.assertEqual(code, install.EXIT_PARTIAL)
        self.assertIn("Partly done", out)
        self.assertIn("1 item(s) need your attention", out)
        self.assertIn("mcp.json: can't be read safely", out)
        self.assertEqual(cfg.read_text(encoding="utf-8"), '{ // comment\n')     # left alone
        code, _ = self.run_quiet(["codex"], ["demo"], True, self.project, yes=True)
        self.assertEqual(code, install.EXIT_OK)                                  # items do not leak into the next run

    def test_one_line_per_folder_unless_verbose(self):
        _, out = self.run_quiet(["cursor"], ["demo"], True, self.project, dry=True)
        self.assertIn("would install  1 skill(s)  ->", out)
        self.assertNotIn("demo  ->", out)
        with mock.patch.object(install, "VERBOSE", True):
            _, out = self.run_quiet(["cursor"], ["demo"], True, self.project, dry=True)
        self.assertIn("would install  demo  ->", out)

    def test_license_note_for_non_commercial_skills(self):
        nc = self.root / "skills" / "git-x"
        nc.mkdir()
        (nc / "SKILL.md").write_text('---\nname: git-x\ndescription: d\nlicense: CC BY-NC-SA 3.0. Derived from a '
                                     'book\n---\n', encoding="utf-8")
        install._INDEX.clear()
        self.assertEqual(install.license_note(self.root, ["demo"]), "")
        note = install.license_note(self.root, ["demo", "git-x"])
        self.assertIn("1 git-* skills are licensed CC BY-NC-SA 3.0", note)
        self.assertIn("--plugin", note)

    def test_uninstall_restores_files_and_drops_backups(self):
        cfg = self.home / ".cursor" / "mcp.json"
        cfg.parent.mkdir()
        cfg.write_text('{\n    "mcpServers": {\n        "mine": {"command": "x"}\n    },\n    "theme": "dark"\n}\n',
                       encoding="utf-8")
        self.run_quiet(["cursor"], ["demo"], True, self.project, mcp=True, yes=True)
        self.assertIn('\n    "mcpServers"', cfg.read_text(encoding="utf-8"))           # 4-space indent kept
        backup = cfg.with_name(cfg.name + install.BACKUP_SUFFIX)
        self.assertTrue(backup.is_file())
        code, out = self.run_quiet(["cursor"], ["demo"], True, self.project, mcp=True, yes=True, remove=True,
                                   uninstall=True)
        self.assertEqual(code, install.EXIT_OK)
        self.assertIn("1 MCP server entry", out)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8")),
                         {"mcpServers": {"mine": {"command": "x"}}, "theme": "dark"})
        self.assertFalse(backup.exists())

    def test_backup_is_kept_when_the_file_changed_since(self):
        cfg = self.home / "a.json"
        cfg.write_text('{"a": 1}', encoding="utf-8")
        backup = cfg.with_name(cfg.name + install.BACKUP_SUFFIX)
        backup.write_text('{"a": 0}', encoding="utf-8")
        self.assertEqual(install.drop_backups([cfg]), [backup])
        backup.write_text('{ "a" : 1 }', encoding="utf-8")
        self.assertEqual(install.drop_backups([cfg]), [])
        self.assertFalse(backup.exists())

    def test_json_text_keeps_tabs_and_defaults_to_two_spaces(self):
        cfg = self.home / "t.json"
        cfg.write_text('{\n\t"a": 1\n}\n', encoding="utf-8")
        self.assertEqual(install.json_text({"a": 1}, cfg), '{\n\t"a": 1\n}\n')
        self.assertEqual(install.json_text({"a": 1}, self.home / "new.json"), '{\n  "a": 1\n}\n')


class FriendlyErrorTests(unittest.TestCase):
    def test_download_errors_are_one_short_message(self):
        not_found = urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO())
        self.addCleanup(not_found.close)
        self.assertIn("was not found on GitHub", install.download_error(not_found, "nope"))
        offline = urllib.error.URLError(OSError("getaddrinfo failed"))
        self.assertIn("internet connection", install.download_error(offline, "main"))
        cert = urllib.error.URLError("CERTIFICATE_VERIFY_FAILED")
        self.assertIn("proxy", install.download_error(cert, "main"))
        with mock.patch.object(install, "_fetch", side_effect=offline):
            with self.assertRaises(SystemExit) as ctx:
                install.download_hub("main")
        self.assertIn("Could not download", str(ctx.exception.code))      # a message, not a traceback

    def test_unknown_names_suggest_and_exit_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            install.unknown("agent", "claud", list(install.AGENTS))
        self.assertEqual(ctx.exception.code, install.EXIT_USAGE)
        self.assertIn("Did you mean claude-code?", ctx.exception.message)
        self.assertIn("Did you mean claude-code?", err.getvalue())

    def test_version_and_exit_codes_in_help(self):
        script = str(Path(install.__file__))
        out = subprocess.run([sys.executable, script, "--version"], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        self.assertIn("skill-hub installer", out.stdout)
        out = subprocess.run([sys.executable, script, "--agent", "claud", "--all"], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(out.returncode, 2)
        self.assertIn("Did you mean claude-code?", out.stderr)
        self.assertNotIn("usage:", out.stderr)                              # no wall of usage text
        out = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True, timeout=60)
        self.assertIn("Exit codes: 0 done", out.stdout)


class OtherServerTests(Sandbox):
    def test_preset_needs_its_secret_and_copies_it_from_the_environment(self):
        with self.assertRaises(install.McpError) as ctx:
            install.build_server("github", environ={})
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", str(ctx.exception))
        entry, notes = install.build_server("github", environ={"GITHUB_PERSONAL_ACCESS_TOKEN": "tok"})
        self.assertEqual(entry["env"], {"GITHUB_PERSONAL_ACCESS_TOKEN": "tok"})
        self.assertTrue(any("secrets" in n for n in notes))

    def test_preset_args_and_custom_command(self):
        with self.assertRaises(install.McpError):
            install.build_server("filesystem")                       # needs a folder
        entry, _ = install.build_server("filesystem", extra_args=["/data"])
        self.assertEqual(entry["args"][-1], "/data")
        entry, _ = install.build_server("mydb", command="mydb-server --readonly", env_pairs=["MODE=ro"])
        self.assertEqual((entry["command"], entry["args"], entry["env"]), ("mydb-server", ["--readonly"], {"MODE": "ro"}))
        for bad in ("bad name", "skill-hub", "unknown-preset"):
            with self.assertRaises(install.McpError):
                install.build_server(bad)

    def test_add_list_remove_keeps_skill_hub_entry(self):
        agents = ["cursor", "codex"]
        install.execute(self.root, agents, [], True, self.project, mcp=True, yes=True)
        entry, _ = install.build_server("tool-x", command="tool-x --stdio")
        self.assertEqual(install.manage_server(self.root, "tool-x", agents, True, self.project, entry, yes=True), 2)
        cursor = self.home / ".cursor" / "mcp.json"
        codex = self.home / ".codex" / "config.toml"
        self.assertEqual(install.configured_servers(cursor, install.mcp_info("cursor")), ["skill-hub", "tool-x"])
        self.assertEqual(install.configured_servers(codex, install.mcp_info("codex")), ["skill-hub", "tool-x"])
        self.assertEqual(install.manage_server(self.root, "tool-x", agents, True, self.project, entry, yes=True), 0)
        self.assertEqual(install.manage_server(self.root, "tool-x", agents, True, self.project, None, yes=True), 2)
        self.assertEqual(install.configured_servers(cursor, install.mcp_info("cursor")), ["skill-hub"])
        self.assertEqual(install.configured_servers(codex, install.mcp_info("codex")), ["skill-hub"])


class GuidedMenuTests(Sandbox):
    """The guided menu's choose / update / remove / MCP steps, with the answers fed to ask()."""

    def setUp(self):
        super().setUp()
        extra = self.root / "skills" / "extra"
        extra.mkdir()
        (extra / "SKILL.md").write_text("---\nname: extra\ndescription: e\n---\nbody\n", encoding="utf-8")
        install._INDEX.pop(str(self.root), None)
        self.folder = self.project / install.AGENTS["claude-code"]["project"]

    def answer(self, func, answers, *args):
        out = io.StringIO()
        with mock.patch.object(install, "ask", side_effect=list(answers)), contextlib.redirect_stdout(out):
            return func(*args)

    def states(self):
        return install.skill_states(self.root, ["claude-code"], False, self.project)

    def make_stale(self):
        (self.root / "skills" / "demo" / "scripts" / "run.py").write_text("print('v2')\n", encoding="utf-8")

    def test_states_mark_installed_and_update(self):
        self.assertEqual(self.states(), {})
        install.copy_skill(self.root, "demo", self.folder)
        self.assertEqual(self.states(), {"demo": "installed"})
        self.make_stale()
        self.assertEqual(self.states(), {"demo": "update"})

    def test_update_refreshes_only_installed_copies_that_differ(self):
        install.copy_skill(self.root, "demo", self.folder)
        self.make_stale()
        with contextlib.redirect_stdout(io.StringIO()):
            code = install.update_skills(self.root, ["claude-code"], ["demo", "extra"], False, self.project, yes=True)
        self.assertEqual(code, install.EXIT_OK)
        self.assertEqual(self.states(), {"demo": "installed"})            # extra was not installed
        self.assertFalse((self.folder / "extra").exists())

    def test_choose_updates_plus_a_single_skill_found_by_name(self):
        install.copy_skill(self.root, "demo", self.folder)
        self.make_stale()
        # options: 1 everything, 2 single skills, 3 the ones with an update, 4 demo-tools
        names, update = self.answer(install.choose_skills, ["2,3", "ext", "1"],
                                    self.root, ["claude-code"], False, self.project)
        self.assertEqual((names, update), (["demo", "extra"], True))

    def test_manage_installed_removes_only_the_picked_skill(self):
        install.copy_skill(self.root, "demo", self.folder)
        install.copy_skill(self.root, "extra", self.folder)
        code = self.answer(install.manage_installed, ["extra", "2", "y"],
                           self.root, ["claude-code"], False, self.project)
        self.assertEqual(code, install.EXIT_OK)
        self.assertEqual(self.states(), {"demo": "installed"})

    def test_manage_mcp_adds_then_removes_a_preset(self):
        cfg = self.home / ".cursor" / "mcp.json"
        info = install.mcp_info("cursor")
        self.answer(install.manage_mcp, ["memory", "1", "y"], self.root, ["cursor"], True, self.project)
        self.assertEqual(install.configured_servers(cfg, info), ["memory"])
        self.answer(install.manage_mcp, ["memory", "2", "y"], self.root, ["cursor"], True, self.project)
        self.assertEqual(install.configured_servers(cfg, info), [])

    def test_menu_asks_again_after_an_unknown_choice(self):
        args = mock.Mock(project=self.project)
        with mock.patch.object(install, "detect_agents", return_value={}):
            code = self.answer(install.guided, ["9", "6"], self.root, args)
        self.assertEqual(code, install.EXIT_OK)                          # 6 with no agents: nothing to do


class MergeHooksTests(unittest.TestCase):
    def test_merge_replaces_ours_and_keeps_the_rest(self):
        mine = {"type": "command", "command": "mine.sh"}
        old = {"type": "command", "command": "ours.sh --old"}
        data = {"model": "x", "hooks": {"Stop": [{"hooks": [mine, old]}], "PreToolUse": [{"matcher": "Read",
                                                                                     "hooks": [old]}],
                                        "Broken": "not a list"}}
        def is_ours(h):
            return isinstance(h, dict) and str(h.get("command", "")).startswith("ours.sh")
        new = {"type": "command", "command": "ours.sh"}
        merged = install.merge_hooks(data, is_ours, [("Stop", None, new), ("PreToolUse", "Read", new)])
        self.assertEqual(merged["hooks"]["Stop"], [{"hooks": [mine]}, {"hooks": [new]}])
        self.assertEqual(merged["hooks"]["PreToolUse"], [{"matcher": "Read", "hooks": [new]}])
        self.assertEqual(merged["hooks"]["Broken"], "not a list")                 # not ours to fix
        self.assertEqual(install.merge_hooks(merged, is_ours, [("Stop", None, new), ("PreToolUse", "Read", new)]),
                         merged)                                                   # idempotent
        self.assertEqual(sorted(e for e, _, _ in install.hooks_matching(merged, is_ours)), ["PreToolUse", "Stop"])
        removed = install.merge_hooks(merged, is_ours, [])
        self.assertEqual(removed["hooks"], {"Stop": [{"hooks": [mine]}], "Broken": "not a list"})
        self.assertIn("ours.sh --old", str(data))                                  # input left untouched


REPO_HUB = Path(__file__).resolve().parent.parent / "skills" / "generic" / "hub"


class PromptHookTests(Sandbox):
    def setUp(self):
        super().setUp()
        for name in install.HOOK_NEEDS:                      # the real skills, so the hook can really run
            shutil.copytree(str(REPO_HUB / name), str(self.root / "skills" / name),
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.names = ["demo", *install.HOOK_NEEDS]
        self.settings = self.home / ".claude" / "settings.json"

    def our_hooks(self, path: Path) -> list:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [h for g in data.get("hooks", {}).get("UserPromptSubmit", []) for h in g["hooks"]
                if install._is_our_hook(h)]

    def test_setup_merges_the_hook_and_uninstall_removes_only_it(self):
        self.settings.parent.mkdir(parents=True)
        other = {"type": "command", "command": "echo mine"}
        self.settings.write_text(json.dumps({"model": "opus", "hooks": {
            "UserPromptSubmit": [{"hooks": [other]}], "PreToolUse": [{"matcher": "Bash", "hooks": [other]}]}}),
            encoding="utf-8")
        install.execute(self.root, ["claude-code", "cursor"], self.names, True, self.project, yes=True, hook=True)
        ours = self.our_hooks(self.settings)
        self.assertEqual(len(ours), 1)
        self.assertIn((self.home / ".claude" / "skills" / "skill-dispatcher").as_posix(), ours[0]["command"])
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertIn(other, data["hooks"]["UserPromptSubmit"][0]["hooks"])
        self.assertIn("PreToolUse", data["hooks"])
        self.assertTrue((self.settings.parent / ("settings.json" + install.BACKUP_SUFFIX)).is_file())

        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, hook=True)
        self.assertEqual(len(self.our_hooks(self.settings)), 1)          # running setup again adds no copy

        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, hook=True,
                        remove=True, uninstall=True)
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(self.our_hooks(self.settings), [])
        self.assertEqual(data["hooks"]["UserPromptSubmit"], [{"hooks": [other]}])
        self.assertEqual(data["model"], "opus")

    def test_installed_hook_command_runs_and_never_blocks(self):
        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, hook=True)
        cmd = self.our_hooks(self.settings)[0]["command"]
        for prompt in ("rebase my feature branch onto main", "/clear", ""):
            out = subprocess.run(cmd, shell=True, input=json.dumps({"prompt": prompt, "cwd": str(self.project)}),
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertNotIn("Traceback", out.stderr)

    def test_no_hook_unless_both_skills_are_installed(self):
        install.execute(self.root, ["claude-code"], ["demo"], True, self.project, yes=True, hook=True)
        self.assertFalse(self.settings.exists())

    def test_project_install_uses_the_personal_settings_file(self):
        install.execute(self.root, ["claude-code"], self.names, False, self.project, yes=True, hook=True)
        local = self.project / ".claude" / "settings.local.json"
        self.assertEqual(len(self.our_hooks(local)), 1)
        self.assertFalse((self.project / ".claude" / "settings.json").exists())
        self.assertIn((self.project / ".claude" / "skills" / "skill-dispatcher").as_posix(),
                      self.our_hooks(local)[0]["command"])

    def test_agents_without_a_prompt_hook_and_unreadable_files_are_left_alone(self):
        self.assertEqual(install.PROMPT_HOOK.plan(["cursor", "devin"], True, self.project, self.names), [])
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{ // comment\n}', encoding="utf-8")
        rows = install.PROMPT_HOOK.plan(["claude-code"], True, self.project, self.names)
        self.assertTrue(rows[0]["status"].startswith("unreadable"))
        self.assertEqual(install.PROMPT_HOOK.apply(rows), 0)
        self.assertIn("// comment", self.settings.read_text(encoding="utf-8"))

    def test_dry_run_and_opt_out_write_nothing(self):
        install.execute(self.root, ["claude-code"], self.names, True, self.project, dry=True, hook=True)
        self.assertFalse(self.settings.exists())
        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, hook=False)
        self.assertFalse(self.settings.exists())


class OtherAgentHookTests(PromptHookTests):
    AGENTS = ["claude-code", "codex", "antigravity", "copilot"]

    def setUp(self):
        super().setUp()
        self.codex = self.home / ".codex" / "hooks.json"
        self.antigravity = self.home / ".gemini" / "config" / "hooks.json"
        self.copilot = self.home / ".copilot" / "hooks" / "skill-hub.json"
        for var in ("CODEX_HOME", "COPILOT_HOME", "SKILL_DISPATCH_STATE"):
            saved = os.environ.pop(var, None)
            if saved is not None:
                self.addCleanup(os.environ.__setitem__, var, saved)
        os.environ["SKILL_DISPATCH_STATE"] = str(self.home / "seen.json")
        self.addCleanup(os.environ.pop, "SKILL_DISPATCH_STATE", None)

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_setup_writes_each_agents_format_and_uninstall_removes_only_ours(self):
        self.antigravity.parent.mkdir(parents=True)
        reminder = {"PreInvocation": [{"type": "command", "command": "./scripts/reminder.sh"}]}
        self.antigravity.write_text(json.dumps({"reminder": reminder}), encoding="utf-8")
        install.execute(self.root, self.AGENTS, self.names, True, self.project, yes=True, hook=True)

        codex = self.our_hooks(self.codex)
        self.assertEqual(len(codex), 1)
        self.assertIn("--hook-format json", codex[0]["command"])
        self.assertIn((self.home / ".agents" / "skills" / "skill-dispatcher").as_posix(), codex[0]["command"])

        ag = self.read(self.antigravity)
        self.assertEqual(ag["reminder"], reminder)
        handler = ag[install.HOOK_NAME]["PreInvocation"][0]
        self.assertIn("--hook-format injectsteps", handler["command"])
        self.assertIn((self.home / ".gemini" / "config" / "skills").as_posix(), handler["command"])

        cp = self.read(self.copilot)
        self.assertEqual(cp["version"], 1)
        handler = cp["hooks"]["sessionStart"][0]
        self.assertIn("--hook-format session", handler["bash"])
        self.assertIn("--hook-format session", handler["powershell"])

        rows = install.PROMPT_HOOK.plan(self.AGENTS, True, self.project, self.names)
        self.assertEqual({r["status"] for r in rows}, {"same"})          # a second run changes nothing

        install.execute(self.root, self.AGENTS, self.names, True, self.project, yes=True, hook=True,
                        remove=True, uninstall=True)
        self.assertFalse(self.codex.exists())                             # setup created it: removed again
        self.assertEqual(self.read(self.antigravity), {"reminder": reminder})   # the user's file: kept
        self.assertFalse(self.copilot.exists())

    def test_installed_commands_print_what_each_agent_expects(self):
        install.execute(self.root, self.AGENTS, self.names, True, self.project, yes=True, hook=True)
        payloads = {
            "codex": (self.our_hooks(self.codex)[0]["command"], {"prompt": "rebase my branch onto main please"}),
            "antigravity": (self.read(self.antigravity)[install.HOOK_NAME]["PreInvocation"][0]["command"],
                            {"conversationId": "c1", "invocationNum": 0, "lastUserInput": "rebase my branch onto main"}),
            "copilot": (self.read(self.copilot)["hooks"]["sessionStart"][0]["bash"], {"sessionId": "s1"}),
        }
        for agent, (cmd, payload) in payloads.items():
            out = subprocess.run(cmd, shell=True, input=json.dumps(payload), capture_output=True, text=True,
                                 timeout=60)
            self.assertEqual(out.returncode, 0, (agent, out.stderr))
            if agent == "codex":
                self.assertTrue(out.stdout.strip() == "" or "hookSpecificOutput" in json.loads(out.stdout))
            elif agent == "antigravity":
                self.assertIsInstance(json.loads(out.stdout), dict)
            else:
                self.assertIn("skill-dispatcher", json.loads(out.stdout)["additionalContext"])

    def test_shared_project_files_are_never_used(self):
        self.assertEqual(install.PROMPT_HOOK.plan(["codex", "antigravity", "copilot"], False, self.project,
                                                self.names), [])

    def test_home_env_moves_the_user_file(self):
        os.environ["CODEX_HOME"] = str(self.home / "elsewhere")
        self.addCleanup(os.environ.pop, "CODEX_HOME", None)
        self.assertEqual(install.hook_config_path("codex", True, self.project), self.home / "elsewhere" / "hooks.json")

    def test_paths_with_spaces_are_quoted_for_each_shell(self):
        info = install.hook_info("copilot")
        cmd, ps = install.hook_commands(info, Path("C:/My Skills/skill-dispatcher"))
        self.assertIn('"C:/My Skills/skill-dispatcher/scripts/dispatch.py"', cmd)
        self.assertTrue(ps.startswith('& ') or not cmd.startswith('"'))
        plain, _ = install.hook_commands(info, Path("C:/skills/skill-dispatcher"))
        self.assertIn(" C:/skills/skill-dispatcher/scripts/dispatch.py ", plain)


REPO_TOKEN = Path(__file__).resolve().parent.parent / "skills" / "generic" / "ai-efficiency" / install.TOKEN_SKILL


class TokenHookTests(Sandbox):
    def setUp(self):
        super().setUp()
        shutil.copytree(str(REPO_TOKEN), str(self.root / "skills" / install.TOKEN_SKILL),
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.names = ["demo", install.TOKEN_SKILL]
        self.settings = self.home / ".claude" / "settings.json"

    def ours(self, path: Path) -> list:
        return install.hooks_matching(json.loads(path.read_text(encoding="utf-8")), install._is_token_hook)

    def test_install_merges_and_uninstall_removes_only_ours(self):
        self.settings.parent.mkdir(parents=True)
        other = {"type": "command", "command": "echo mine"}
        self.settings.write_text(json.dumps({"model": "opus", "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [other]}], "UserPromptSubmit": [{"hooks": [other]}]}}),
            encoding="utf-8")
        install.execute(self.root, ["claude-code", "cursor"], self.names, True, self.project, yes=True,
                        token_hook=True)
        ours = self.ours(self.settings)
        self.assertEqual(sorted((e, m) for e, m, _ in ours), [("PreToolUse", "Read"), ("SessionEnd", None)])
        skill = (self.home / ".claude" / "skills" / install.TOKEN_SKILL).as_posix()
        self.assertTrue(all(skill + "/scripts/token_hook.py" in h["command"] for _, _, h in ours))
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertIn({"matcher": "Bash", "hooks": [other]}, data["hooks"]["PreToolUse"])
        self.assertEqual(data["hooks"]["UserPromptSubmit"], [{"hooks": [other]}])

        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, token_hook=True)
        self.assertEqual(len(self.ours(self.settings)), 2)              # running again adds no copy
        rows = install.TOKEN_HOOKS.plan(["claude-code"], True, self.project, self.names)
        self.assertEqual(rows[0]["status"], "same")

        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, token_hook=True,
                        remove=True)
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(self.ours(self.settings), [])
        self.assertEqual(data["hooks"], {"PreToolUse": [{"matcher": "Bash", "hooks": [other]}],
                                         "UserPromptSubmit": [{"hooks": [other]}]})

    def test_installed_read_guard_runs(self):
        install.execute(self.root, ["claude-code"], self.names, True, self.project, yes=True, token_hook=True)
        guard = next(h["command"] for e, _, h in self.ours(self.settings) if e == "PreToolUse")
        big = self.project / "big.py"
        big.write_text("x = 1  # filler line for size\n" * 2000, encoding="utf-8")
        event = {"session_id": "t", "tool_name": "Read", "tool_input": {"file_path": str(big)}}
        out = subprocess.run(guard, shell=True, input=json.dumps(event), capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_needs_the_skill_and_a_supporting_agent(self):
        install.execute(self.root, ["claude-code"], ["demo"], True, self.project, yes=True, token_hook=True)
        self.assertFalse(self.settings.exists())
        self.assertEqual(install.TOKEN_HOOKS.plan(["cursor", "codex"], True, self.project, self.names), [])

    def test_project_scope_uses_the_personal_settings_file(self):
        install.execute(self.root, ["claude-code"], self.names, False, self.project, yes=True, token_hook=True)
        self.assertEqual(len(self.ours(self.project / ".claude" / "settings.local.json")), 2)
        self.assertFalse((self.project / ".claude" / "settings.json").exists())

    def test_dry_run_and_unreadable_file_write_nothing(self):
        install.execute(self.root, ["claude-code"], self.names, True, self.project, dry=True, token_hook=True)
        self.assertFalse(self.settings.exists())
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{ // comment\n}', encoding="utf-8")
        rows = install.TOKEN_HOOKS.plan(["claude-code"], True, self.project, self.names)
        self.assertTrue(rows[0]["status"].startswith("unreadable"))
        self.assertEqual(install.TOKEN_HOOKS.apply(rows), 0)
        self.assertIn("// comment", self.settings.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
