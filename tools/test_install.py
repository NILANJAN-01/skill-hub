"""Tests for tools/install.py. Standard library only; every write goes to a temp folder.

    python -m unittest discover -s tools -p "test_*.py" -v
"""
import hashlib
import json
import os
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


if __name__ == "__main__":
    unittest.main()
