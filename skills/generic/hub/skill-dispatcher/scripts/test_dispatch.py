import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dispatch as d  # noqa: E402

ROUTER = d.load_router()
SCRIPT = HERE / "dispatch.py"


def make_skill(root: Path, name: str, desc: str) -> None:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


def fixture_skills(tmp: str) -> Path:
    root = Path(tmp) / "skills"
    make_skill(root, "log-analyzer", "Analyse a crash log file and list crashes and exceptions. Use when an app crashed.")
    make_skill(root, "report-writer", "Write a report, blog post or document from notes. Use when writing a report.")
    make_skill(root, "branch-rebaser", "Rebase a git branch onto main. Use when rebasing a feature branch.")
    make_skill(root, "skill-router", "Route a request to skills, rebase analyse report. Use when routing.")
    return root


def run(text: str, root: Path) -> dict:
    return d.dispatch(text, ROUTER, [str(root)], defaults=False)


def by_skill(result: dict) -> dict:
    return {t["skill"]: t for t in result["tasks"] if t["skill"]}


@unittest.skipIf(ROUTER is None, "skill-router is not installed next to skill-dispatcher")
class Waves(unittest.TestCase):
    def test_independent_parts_share_the_first_wave(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("analyse the crash log app.log; also rebase my feature branch onto main", fixture_skills(tmp))
            tasks = by_skill(r)
            self.assertEqual(tasks["log-analyzer"]["wave"], 1)
            self.assertEqual(tasks["branch-rebaser"]["wave"], 1)
            self.assertTrue(r["parallel"])

    def test_then_makes_the_second_part_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("analyse the crash log app.log then write a report", fixture_skills(tmp))
            tasks = by_skill(r)
            self.assertEqual(tasks["report-writer"]["depends_on"], [tasks["log-analyzer"]["id"]])
            self.assertEqual(tasks["report-writer"]["wave"], 2)
            self.assertFalse(r["parallel"])

    def test_using_an_earlier_result_makes_it_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("analyse the crash log app.log; write a report from the findings", fixture_skills(tmp))
            self.assertEqual(by_skill(r)["report-writer"]["wave"], 2)

    def test_mixed_request_has_parallel_first_wave_and_a_follow_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("analyse the crash log app.log and then write a report from the findings. "
                    "Also rebase my feature branch onto main.", fixture_skills(tmp))
            tasks = by_skill(r)
            self.assertEqual(sorted(r["waves"][0]), sorted([tasks["log-analyzer"]["id"], tasks["branch-rebaser"]["id"]]))
            self.assertEqual(tasks["report-writer"]["wave"], 2)

    def test_meta_skills_are_never_dispatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("route and rebase my feature branch onto main", fixture_skills(tmp))
            self.assertNotIn("skill-router", [t["skill"] for t in r["tasks"]])


class Planning(unittest.TestCase):
    def routed(self, *parts):
        return {"parts": [{"part": p, "skill": s, "confidence": c, "level": "basic", "alternatives": [],
                           "missing_inputs": [], "missing_tools": []} for p, s, c in parts]}

    def test_workflow_order_links_known_pairs(self):
        text = "find the locators; write the kotlin tests"
        r = d.plan(text, self.routed(("find the locators", "locators", "high"),
                                     ("write the kotlin tests", "kotlin", "high")), {("locators", "kotlin")})
        self.assertEqual(r["tasks"][1]["depends_on"], [1])

    def test_same_skill_twice_runs_in_order(self):
        text = "rebase a; rebase b"
        r = d.plan(text, self.routed(("rebase a", "rebaser", "high"), ("rebase b", "rebaser", "high")))
        self.assertEqual([t["wave"] for t in r["tasks"]], [1, 2])

    def test_low_confidence_is_a_hint_not_an_assignment(self):
        text = "do a; do b"
        r = d.plan(text, self.routed(("do a", "x", "high"), ("do b", "x", "low")))
        self.assertIsNone(r["tasks"][1]["skill"])
        self.assertEqual(r["tasks"][1]["possible_skill"], "x")
        self.assertEqual(r["tasks"][1]["wave"], 1)

    def test_briefs_are_self_contained(self):
        text = "do a then do b"
        r = d.attach_briefs(d.plan(text, self.routed(("do a", "x", "high"), ("do b", "y", "high"))), "runs/demo")
        b = r["tasks"][1]["brief"]
        for needle in ("Goal: do b", "`y` skill", "results of task 1", "runs/demo/02-y.md", "Whole request"):
            self.assertIn(needle, b)


class Hook(unittest.TestCase):
    def test_reads_json_and_raw_payloads(self):
        self.assertEqual(d.prompt_from_hook('{"prompt": " fix it ", "cwd": "/x"}'), ("fix it", "/x"))
        self.assertEqual(d.prompt_from_hook('{"user_prompt": "hello"}'), ("hello", None))
        self.assertEqual(d.prompt_from_hook("plain text prompt"), ("plain text prompt", None))
        self.assertEqual(d.prompt_from_hook("[1, 2]"), ("", None))

    def hook(self, payload: str, *extra) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--hook", *extra], input=payload, text=True,
                              capture_output=True, timeout=60)

    def test_hook_is_quiet_for_trivial_prompts_and_never_fails(self):
        for payload in ('{"prompt": "hi"}', '{"prompt": "/clear now please"}', "not json at all {", ""):
            out = self.hook(payload, "--no-default-roots")
            self.assertEqual(out.returncode, 0)
            self.assertEqual(out.stdout.strip(), "")

    @unittest.skipIf(ROUTER is None, "skill-router is not installed next to skill-dispatcher")
    def test_hook_prints_a_plan_for_a_matching_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture_skills(tmp)
            payload = json.dumps({"prompt": "analyse the crash log app.log; also rebase my feature branch onto main"})
            out = self.hook(payload, "--no-default-roots", "--root", str(root), "--json")
            self.assertEqual(out.returncode, 0)
            self.assertTrue(json.loads(out.stdout)["parallel"])

    def test_off_switch(self):
        env = dict(os.environ, SKILL_DISPATCH="off")
        out = subprocess.run([sys.executable, str(SCRIPT), "--hook"], input='{"prompt": "rebase my branch onto main"}',
                             text=True, capture_output=True, env=env, timeout=60)
        self.assertEqual((out.returncode, out.stdout), (0, ""))


class Render(unittest.TestCase):
    def test_render_lists_waves_and_how_to_run(self):
        routed = {"parts": [{"part": "a", "skill": "x", "confidence": "high", "level": "basic", "alternatives": [],
                             "missing_inputs": ["a file"], "missing_tools": []},
                            {"part": "b", "skill": "y", "confidence": "high", "level": "basic", "alternatives": [],
                             "missing_inputs": [], "missing_tools": []}]}
        text = d.render(d.attach_briefs(d.plan("a; b", routed)))
        for needle in ("Wave 1 (in parallel)", "Ask the user first", "How to run", "Briefs:"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
