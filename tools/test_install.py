"""Tests for tools/install.py. Standard library only; every write goes to a temp folder.

    python -m unittest discover -s tools -p "test_*.py" -v
"""
import hashlib
import json
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


if __name__ == "__main__":
    unittest.main()
