import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import route as r  # noqa: E402


def make_skill(root: Path, name: str, desc: str, compat: str = "") -> None:
    d = root / name
    d.mkdir(parents=True)
    c = f"compatibility: {compat}\n" if compat else ""
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n{c}---\n\n# {name}\n", encoding="utf-8")


def registry(tmp: str) -> dict:
    root = Path(tmp) / "skills"
    make_skill(root, "android-logcat-analyzer", "Analyse Android logcat output, crashes, ANRs and bugreports")
    make_skill(root, "professional-writing", "Write blog posts, CVs, cover letters and technical documents")
    make_skill(root, "image-inspector", "Inspect an image or screenshot: colours, OCR text, size", "Needs ffmpeg-not-really")
    return r.scan([str(root)], defaults=False)


class Split(unittest.TestCase):
    def test_splits_sentences_bullets_and_actions(self):
        parts = r.split_request("Analyse this logcat and write a report.\n- tailor my cv\n2) check the screenshot")
        self.assertEqual(parts, ["Analyse this logcat", "write a report.", "tailor my cv", "check the screenshot"])

    def test_and_also_leaves_no_dangling_and(self):
        self.assertEqual(r.split_request("the pipeline is stuck and also slow"), ["the pipeline is stuck", "slow"])

    def test_urls_stay_whole(self):
        parts = r.split_request("Turn https://docs.example.com/a.b into a skill. Then explain it")
        self.assertEqual(parts[0], "Turn https://docs.example.com/a.b into a skill.")
        self.assertEqual(len(parts), 2)

    def test_levels(self):
        self.assertEqual(r.level_of("fix this typo"), "basic")
        self.assertEqual(r.level_of("migrate the whole pipeline end-to-end"), "advanced")


class Routing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reg = registry(self.tmp.name)
        self.hints = r.load_hints()

    def test_vague_prompt_still_routes_with_hints(self):
        res = r.route("my app keeps crashing", self.reg, self.hints)
        self.assertEqual(res["parts"][0]["skill"], "android-logcat-analyzer")
        self.assertIn("ASK THE USER FOR", r.render(res))          # no log given

    def test_input_present_clears_missing(self):
        res = r.route("why did app crash, see crash.log", self.reg, self.hints)
        self.assertEqual(res["parts"][0]["missing_inputs"], [])

    def test_multi_part_request_is_a_chain(self):
        res = r.route("Analyse crash.log for the crash. Then write a blog post about it.", self.reg, self.hints)
        self.assertEqual(res["load"], ["android-logcat-analyzer", "professional-writing"])
        self.assertTrue(res["chain"])
        self.assertIn("skill-orchestrator", r.render(res))

    def test_context_resolves_it(self):
        root = Path(self.tmp.name) / "skills"
        make_skill(root, "kotlin-unit-test", "Write and run unit tests for Kotlin code")
        make_skill(root, "python-unit-test", "Write and run unit tests for a Python file")
        reg = r.scan([str(root)], defaults=False)
        res = r.route("Look at my python file. Write unit tests for it.", reg, {})
        self.assertEqual(res["parts"][1]["skill"], "python-unit-test")

    def test_no_match_is_handled_directly(self):
        res = r.route("what is the capital of France", self.reg, self.hints)
        self.assertEqual(res["load"], [])
        self.assertEqual(len(res["unmatched"]), 1)

    def test_catalog_suggests_not_installed(self):
        cat = Path(self.tmp.name) / "catalog.json"
        cat.write_text(json.dumps({"skills": [{"name": "video-inspector", "description": "Analyse a video recording, frames and black screens"}]}), encoding="utf-8")
        reg = dict(self.reg)
        reg.update(r.load_catalog(cat, reg))
        res = r.route("check the screen recording for a black screen", reg, self.hints)
        self.assertIsNone(res["parts"][0]["skill"])
        self.assertEqual(res["parts"][0]["not_installed_suggestion"], "video-inspector")

    def test_hints_file_is_valid(self):
        data = json.loads(r.HINTS_FILE.read_text(encoding="utf-8"))
        for name, h in data["skills"].items():
            for need in h.get("needs", []):
                self.assertIn(need, r.INPUT_PATTERNS, f"{name}: unknown need {need}")


class Cli(unittest.TestCase):
    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = registry(tmp)
            self.assertIn("professional-writing", reg)
            out = subprocess.run([sys.executable, str(HERE / "route.py"), "write my cover letter", "--json",
                                  "--no-default-roots", "--root", str(Path(tmp) / "skills")],
                                 capture_output=True, text=True, check=True, cwd=tmp).stdout
            self.assertEqual(json.loads(out)["load"], ["professional-writing"])


if __name__ == "__main__":
    unittest.main()
