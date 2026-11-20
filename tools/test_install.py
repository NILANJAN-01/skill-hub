"""Tests for tools/install.py. Standard library only; every write goes to a temp folder.

    python -m unittest discover -s tools -p "test_*.py" -v
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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
        info = install.mcp_info("cursor")
        self.assertEqual(install.mcp_status(cfg, info, self.entry), "missing")
        install.write_mcp_entry(cfg, info, self.entry)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(set(data["mcpServers"]), {"other", "skill-hub"})
        self.assertTrue((cfg.parent / ("mcp.json" + install.BACKUP_SUFFIX)).is_file())
        self.assertEqual(install.mcp_status(cfg, info, self.entry), "same")
        self.assertEqual(install.mcp_status(cfg, info, install.server_entry(allow_install=True)), "differs")
        install.write_mcp_entry(cfg, info, None)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"], {"other": {"command": "x"}})

    def test_type_stdio_added_by_agent_still_counts_as_same(self):
        cfg = self.project / ".mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"skill-hub": dict(self.entry, type="stdio")}}), encoding="utf-8")
        self.assertEqual(install.mcp_status(cfg, install.mcp_info("claude-code"), self.entry), "same")

    def test_unreadable_file_is_left_alone(self):
        cfg = self.project / ".mcp.json"
        cfg.write_text('{ // a comment\n "mcpServers": {} }', encoding="utf-8")
        rows = install.make_mcp_plan(["claude-code"], False, self.project, self.entry)
        self.assertTrue(rows[0]["status"].startswith("unreadable"))
        self.assertEqual(install.apply_mcp_plan(self.root, rows, self.entry, "current", dry=False), 0)
        self.assertIn("// a comment", cfg.read_text(encoding="utf-8"))

    def test_agents_sharing_a_file_share_one_row(self):
        rows = install.make_mcp_plan(["claude-code", "copilot", "cursor"], False, self.project, self.entry)
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
        info = install.mcp_info("codex")
        self.assertEqual(install.mcp_status(cfg, info, self.entry), "differs")
        install.write_mcp_entry(cfg, info, self.entry)
        text = cfg.read_text(encoding="utf-8")
        self.assertNotIn('"old"', text)
        self.assertNotIn("[mcp_servers.skill-hub.env]", text)
        self.assertIn("[mcp_servers.other]", text)
        self.assertIn("[profiles.fast]", text)
        self.assertEqual(text.count("[mcp_servers.skill-hub]"), 1)
        self.assertEqual(install.mcp_status(cfg, info, self.entry), "same")
        install.write_mcp_entry(cfg, info, None)
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
        rows = install.make_mcp_plan(agents, True, self.project, self.entry)
        self.assertEqual({r["status"] for r in rows}, {"same"})

        (self.root / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: d2\n---\n", encoding="utf-8")
        self.assertEqual(install.snapshot_state(self.root), "outdated")

        install.execute(self.root, agents, ["demo"], True, self.project, mcp=True, yes=True,
                        remove=True, uninstall=True)
        self.assertFalse((self.home / ".cursor" / "skills" / "demo").exists())
        self.assertEqual(json.loads((self.home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"], {})
        self.assertNotIn("skill-hub", (self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertFalse(snap.exists())
        self.assertEqual(list(self.home.rglob("*" + install.BACKUP_SUFFIX)), [])   # files we created: no backups

    def test_dry_run_writes_nothing(self):
        install.execute(self.root, ["cursor"], ["demo"], True, self.project, mcp=True, dry=True)
        self.assertFalse((self.home / ".cursor").exists())
        self.assertFalse(install.snapshot_dir().exists())


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
        self.assertEqual(install.make_hook_plan(["cursor", "devin"], True, self.project, self.names), [])
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{ // comment\n}', encoding="utf-8")
        rows = install.make_hook_plan(["claude-code"], True, self.project, self.names)
        self.assertTrue(rows[0]["status"].startswith("unreadable"))
        self.assertEqual(install.apply_hook_plan(rows, False, dry=False), 0)
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

        rows = install.make_hook_plan(self.AGENTS, True, self.project, self.names)
        self.assertEqual({r["status"] for r in rows}, {"same"})          # a second run changes nothing

        install.execute(self.root, self.AGENTS, self.names, True, self.project, yes=True, hook=True,
                        remove=True, uninstall=True)
        self.assertEqual(self.read(self.codex), {})
        self.assertEqual(self.read(self.antigravity), {"reminder": reminder})
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
        self.assertEqual(install.make_hook_plan(["codex", "antigravity", "copilot"], False, self.project,
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
        return install._our_token_hooks(json.loads(path.read_text(encoding="utf-8")))

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
        rows = install.make_token_hook_plan(["claude-code"], True, self.project, self.names)
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
        self.assertEqual(install.make_token_hook_plan(["cursor", "codex"], True, self.project, self.names), [])

    def test_project_scope_uses_the_personal_settings_file(self):
        install.execute(self.root, ["claude-code"], self.names, False, self.project, yes=True, token_hook=True)
        self.assertEqual(len(self.ours(self.project / ".claude" / "settings.local.json")), 2)
        self.assertFalse((self.project / ".claude" / "settings.json").exists())

    def test_dry_run_and_unreadable_file_write_nothing(self):
        install.execute(self.root, ["claude-code"], self.names, True, self.project, dry=True, token_hook=True)
        self.assertFalse(self.settings.exists())
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{ // comment\n}', encoding="utf-8")
        rows = install.make_token_hook_plan(["claude-code"], True, self.project, self.names)
        self.assertTrue(rows[0]["status"].startswith("unreadable"))
        self.assertEqual(install.apply_token_hook_plan(rows, False, dry=False), 0)
        self.assertIn("// comment", self.settings.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
