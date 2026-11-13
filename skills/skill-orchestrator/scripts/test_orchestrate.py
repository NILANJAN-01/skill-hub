import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import orchestrate as o  # noqa: E402

HUB_SKILLS = HERE.parents[1]          # skills/ folder of this repo


def make_skill(root: Path, name: str, desc: str, compat: str = "") -> None:
    d = root / name
    d.mkdir(parents=True)
    fm = f'---\nname: {name}\ndescription: "{desc}"\n'
    if compat:
        fm += f"compatibility: {compat}\n"
    fm += "metadata:\n  title: \"T " + name + "\"\n---\n\nBody\n"
    (d / "SKILL.md").write_text(fm, encoding="utf-8")


class Registry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "skills"
        make_skill(self.root, "android-logcat-analyzer", "Analyse Android logcat crashes, ANRs and exceptions",
                   "Needs Python 3.8+ and adb")
        make_skill(self.root, "professional-writing", "Write blog posts, CVs and technical documents")
        make_skill(self.root, "git-rebasing", "Rebase a branch onto another and squash commits")
        self.reg = o.scan([str(self.root)], defaults=False)

    def test_frontmatter_parser(self):
        fm = o.parse_frontmatter('---\nname: x\ndescription: "a: b"\nmetadata:\n  title: "Hi"\n---\nbody')
        self.assertEqual(fm["description"], "a: b")
        self.assertEqual(fm["metadata"]["title"], "Hi")
        self.assertEqual(o.parse_frontmatter("no frontmatter"), {})

    def test_scan_finds_skills_and_first_root_wins(self):
        for n in ("android-logcat-analyzer", "professional-writing", "git-rebasing"):
            self.assertIn(n, self.reg)
        other = Path(self.tmp.name) / "other"
        make_skill(other, "git-rebasing", "different text")
        reg = o.scan([str(self.root), str(other)], defaults=False)
        self.assertIn("Rebase", reg["git-rebasing"]["description"])

    def test_match_ranks_relevant_skill_first(self):
        r = o.match("my android app crashed, read the logcat", self.reg)
        self.assertEqual(r[0]["skill"], "android-logcat-analyzer")
        r = o.match("write a blog post about testing", self.reg)
        self.assertEqual(r[0]["skill"], "professional-writing")
        self.assertEqual(o.match("zzzz qqqq", self.reg), [])

    def test_requirements_detection(self):
        reqs = o.requirements_of("Needs Python 3.8+ and adb (Android platform-tools); Pillow or OpenCV optional")
        for r in ("python", "adb", "pillow"):
            self.assertIn(r, reqs)

    def test_check_not_installed_and_installed(self):
        res = {r["skill"]: r for r in o.check(["nope", "professional-writing"], self.reg)}
        self.assertFalse(res["nope"]["installed"])
        self.assertTrue(res["professional-writing"]["installed"])
        self.assertTrue(res["professional-writing"]["ready"])


class Workflows(unittest.TestCase):
    def test_every_workflow_skill_exists_in_the_hub(self):
        existing = {p.name for p in HUB_SKILLS.iterdir() if (p / "SKILL.md").is_file()}
        for name, w in o.load_workflows().items():
            for s in w["steps"]:
                self.assertIn(s["skill"], existing, f"workflow {name} uses unknown skill {s['skill']}")

    def test_every_workflow_has_valid_handoffs(self):
        for name, w in o.load_workflows().items():
            steps = [dict(s, n=i + 1) for i, s in enumerate(w["steps"])]
            self.assertEqual(o.validate_handoffs(steps), [], name)
            self.assertTrue(w["description"] and w.get("triggers"), name)

    def test_broken_handoff_is_reported(self):
        steps = [{"n": 1, "skill": "a", "output": "x.md"}, {"n": 2, "skill": "b", "input_from": ["y.md"]}]
        self.assertEqual(len(o.validate_handoffs(steps)), 1)

    def test_pick_workflow_and_plan(self):
        wf = o.load_workflows()
        self.assertEqual(o.pick_workflow("analyse this logcat crash and write a bug report", wf)[0],
                         "android-crash-report")
        self.assertEqual(o.pick_workflow("tailor my resume for this job ad", wf)[0], "cv-for-job")
        reg = {"android-logcat-analyzer": {"name": "android-logcat-analyzer", "description": "x", "title": "x",
                                           "compatibility": "", "path": "", "root": ""}}
        plan = o.build_plan("logcat crash report", reg, None, wf)
        self.assertEqual(plan["workflow"], "android-crash-report")
        self.assertFalse(plan["can_run"])                       # professional-writing is not installed
        self.assertIn("NOT INSTALLED", o.fmt_plan(plan))

    def test_unknown_workflow(self):
        with self.assertRaises(SystemExit):
            o.build_plan("x", {}, "nope", o.load_workflows())


class RunState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name) / "run"
        self.steps = o.load_workflows()["android-crash-report"]["steps"]
        o.run_init(self.run, self.steps, "why crash", "android-crash-report")

    def test_init_refuses_existing(self):
        with self.assertRaises(SystemExit):
            o.run_init(self.run, self.steps, "again", None)

    def test_steps_must_be_done_in_order_and_outputs_must_exist(self):
        with self.assertRaises(SystemExit):
            o.run_done(self.run, 2, [], "")
        with self.assertRaises(SystemExit):
            o.run_done(self.run, 1, ["missing.md"], "")
        (self.run / "01-logcat-findings.md").write_text("findings", encoding="utf-8")
        state = o.run_done(self.run, 1, ["01-logcat-findings.md"], "3 crashes")
        self.assertEqual(state["steps"][0]["status"], "done")
        text = o.render_status(state)
        self.assertIn("[x] 1.", text)
        self.assertIn("<- next", text)
        self.assertIn("01-logcat-findings.md", text)
        (self.run / "02-report.md").write_text("report", encoding="utf-8")
        state = o.run_done(self.run, 2, ["02-report.md"], "")
        self.assertIn("All steps are done", o.render_status(state))

    def test_status_without_run(self):
        with self.assertRaises(SystemExit):
            o.load_run(Path(self.tmp.name) / "none")


class Cli(unittest.TestCase):
    def test_cli_scan_plan_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            make_skill(root, "professional-writing", "Write blog posts, CVs and technical documents")
            py = [sys.executable, str(HERE / "orchestrate.py")]
            out = subprocess.run(py + ["scan", "--no-default-roots", "--root", str(root)], capture_output=True, text=True, check=True).stdout
            self.assertIn("professional-writing", out)
            out = subprocess.run(py + ["plan", "tailor my cv for a job post", "--no-default-roots", "--root", str(root)],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("cv-for-job", out)
            self.assertIn("Ready to run.", out)
            run = Path(tmp) / "runs" / "r1"
            subprocess.run(py + ["run", "init", str(run), "--workflow", "cv-for-job", "--task", "t"],
                           capture_output=True, text=True, check=True)
            self.assertTrue((run / "run.json").is_file())
            out = subprocess.run(py + ["run", "status", str(run)], capture_output=True, text=True, check=True).stdout
            self.assertIn("professional-writing", out)
            out = subprocess.run(py + ["workflows"], capture_output=True, text=True, check=True).stdout
            self.assertIn("android-crash-report", out)


if __name__ == "__main__":
    unittest.main()
