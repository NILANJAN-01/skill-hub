import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompt_lint  # noqa: E402

FIX = HERE / "fixtures"


def rules(text):
    return sorted(f["rule"] for f in prompt_lint.lint(text)[0])


class FewShot(unittest.TestCase):
    def test_imbalanced_and_grouped_labels(self):
        got = rules((FIX / "bad_fewshot.txt").read_text(encoding="utf-8"))
        self.assertIn("exemplar-label-imbalance", got)
        self.assertIn("exemplar-labels-grouped", got)
        self.assertNotIn("leading-opinion", got)            # "I love life: Happy" is data, not the author's view

    def test_balanced_mixed_exemplars_pass(self):
        self.assertEqual(rules((FIX / "good.txt").read_text(encoding="utf-8")), [])

    def test_mixed_formats_and_duplicates(self):
        text = ("Label each line.\nTrees are nice: Happy\nAds are bad -> Angry\nTrees are nice: Happy\n"
                "I am mad -> Angry\n")
        got = rules(text)
        self.assertIn("exemplar-format-mixed", got)
        self.assertIn("exemplar-duplicate", got)

    def test_label_run_at_end(self):
        text = "Label each line.\n" + "".join(f"x{i}: {lab}\n" for i, lab in
                                              enumerate(["a", "b", "a", "b", "a", "b", "b", "b", "b"]))
        self.assertIn("exemplar-label-run-at-end", rules(text))


class AnswerAndWording(unittest.TestCase):
    def test_labeling_without_answer_space(self):
        self.assertIn("answer-space-unspecified", rules("Classify this tweet.\n\n<tweet>{TWEET}</tweet>\n"))
        self.assertNotIn("answer-space-unspecified",
                         rules("Classify this tweet as positive or negative.\n<tweet>{TWEET}</tweet>\n"))

    def test_reasoning_needs_a_final_answer_marker(self):
        self.assertIn("reasoning-without-answer-marker", rules("Solve it. Think step by step.\n"))
        self.assertNotIn("reasoning-without-answer-marker",
                         rules("Solve it. Think step by step, then write 'Final answer: <n>'.\n"))

    def test_opinion_presupposition_and_personal_data(self):
        got = rules((FIX / "bad_wording.txt").read_text(encoding="utf-8"))
        for r in ("leading-opinion", "false-presupposition", "personal-data", "input-not-delimited",
                  "reasoning-without-answer-marker"):
            self.assertIn(r, got)

    def test_no_directive(self):
        self.assertIn("no-directive", rules("llamas and alpacas\n"))
        self.assertNotIn("no-directive", rules("What is the capital of France?\n"))


class Inputs(unittest.TestCase):
    def test_delimited_input_passes(self):
        for text in ('Summarize this text:\n"""\n{TEXT}\n"""\n', "Summarize <text>{TEXT}</text>.\n",
                     "Summarize the review.\nReview: {REVIEW}\n"):
            self.assertNotIn("input-not-delimited", rules(text), text)

    def test_chat_json_roles_count_as_delimiters(self):
        text = prompt_lint.load(str(FIX / "chat.json"))
        self.assertIn("You are a support bot", text)
        self.assertEqual(rules(text), [])

    def test_cli_json_and_exit_codes(self):
        r = subprocess.run([sys.executable, str(HERE / "prompt_lint.py"), str(FIX / "bad_fewshot.txt"), "--json"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual((data["exemplars"], data["variables"]), (7, ["{TWEET}"]))
        r = subprocess.run([sys.executable, str(HERE / "prompt_lint.py"), str(FIX / "good.txt")], capture_output=True)
        self.assertEqual(r.returncode, 0)
        r = subprocess.run([sys.executable, str(HERE / "prompt_lint.py"), "missing.txt"], capture_output=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
