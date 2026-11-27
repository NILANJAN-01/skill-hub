import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompt_bench as pb  # noqa: E402

FIX = HERE / "fixtures"
MODEL = f'"{sys.executable}" "{FIX / "fake_model.py"}"'


def cli(*args):
    r = subprocess.run([sys.executable, str(HERE / "prompt_bench.py"), *map(str, args)], capture_output=True,
                       text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


class Extraction(unittest.TestCase):
    forms = pb.verbalizer(["yes", "no"], None)

    def test_extractors(self):
        out = "No doubt about it. Final answer: Yes"
        self.assertEqual(pb.extract(out, self.forms, "first"), "no")
        self.assertEqual(pb.extract(out, self.forms, "last"), "yes")
        self.assertIsNone(pb.extract(out, self.forms, "exact"))
        self.assertEqual(pb.extract("Yes.", self.forms, "exact"), "yes")
        self.assertEqual(pb.extract("yes, because", self.forms, "start"), "yes")
        self.assertEqual(pb.extract("Label: NO (sure)", self.forms, r"regex:label:\s*(\w+)"), "no")
        self.assertIsNone(pb.extract("I cannot help with that.", self.forms, "last"))

    def test_verbalizer_prefers_longer_phrases(self):
        forms = pb.verbalizer(["yes", "no"], {"yes": ["entrapment"], "no": ["not entrapment"]})
        self.assertEqual(pb.extract("This is not entrapment.", forms, "last"), "no")
        self.assertEqual(pb.extract("Clearly entrapment.", forms, "last"), "yes")

    def test_vote_and_metrics(self):
        self.assertEqual(pb.vote(["no", None, "yes", "yes"]), "yes")
        self.assertEqual(pb.vote(["no", "yes"]), "no")                 # tie: earliest
        self.assertIsNone(pb.vote([None, None]))
        m = pb.metrics([("yes", "yes"), ("yes", None), ("no", "yes"), ("no", "no")], ["yes", "no"])
        self.assertEqual((m["accuracy"], m["unparsed"]), (0.5, 1))
        self.assertAlmostEqual(m["per_label"]["yes"]["precision"], 0.5)
        self.assertAlmostEqual(m["per_label"]["yes"]["recall"], 0.5)
        d = pb.metrics([("yes", None), ("no", None)], ["yes", "no"], default="no")
        self.assertEqual((d["accuracy"], d["unparsed"]), (0.5, 2))      # unparsed counted before the default


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def build(self, *extra):
        out = self.tmp / "p.jsonl"
        code, msg = cli("build", "--template", FIX / "template.txt", "--data", FIX / "dev.jsonl",
                        "--exemplars", FIX / "dev.jsonl", "--out", out, *extra)
        self.assertEqual(code, 0, msg)
        return pb.read_jsonl(out)

    def test_balanced_exemplars_are_not_tested_on(self):
        rows = self.build("--k", "4", "--select", "balanced")
        self.assertEqual(len(rows), 8)                                  # 12 items - 4 exemplars
        shot = rows[0]["prompt"].split("\n\nQ: ")[1:-1]
        self.assertEqual(sorted(s.rsplit("A: ", 1)[1] for s in shot), ["no", "no", "yes", "yes"])
        for r in rows:
            self.assertNotIn(f"Q: {r['input']}\nA: {r['label']}", r["prompt"])

    def test_orders_make_variants_with_the_same_exemplars(self):
        rows = self.build("--k", "4", "--orders", "3")
        self.assertEqual(len(rows), 24)
        v = [r["prompt"] for r in rows if r["id"] == rows[0]["id"]]
        self.assertEqual(len(v), 3)
        self.assertEqual({tuple(sorted(p.split("\n\n"))) for p in v}.__len__(), 1)   # same parts, other order

    def test_similar_selection_and_zero_shot(self):
        rows = self.build("--k", "1", "--select", "similar")
        first = next(r for r in rows if r["input"].startswith("I feel trapped in this job"))
        shot = first["prompt"].split("\n\nQ: ")[1]                       # the one exemplar picked for it
        self.assertIn("trapped", shot)                                   # nearest by shared words
        self.assertNotEqual(shot.split("\nA:")[0], first["input"])       # never the input itself
        zero = self.build()
        self.assertEqual(len(zero), 12)
        self.assertNotIn("A: yes", zero[0]["prompt"])


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_build_run_score_autodicot(self):
        p, o = self.tmp / "p.jsonl", self.tmp / "o.jsonl"
        self.assertEqual(cli("build", "--template", FIX / "template.txt", "--data", FIX / "dev.jsonl", "--out", p)[0], 0)
        code, msg = cli("run", p, "--cmd", MODEL, "--jobs", "4", "--out", o)
        self.assertEqual(code, 0, msg)
        self.assertEqual(len(pb.read_jsonl(o)), 12)
        code, msg = cli("run", p, "--cmd", MODEL, "--out", o)           # resumable: nothing left to do
        self.assertIn("0 prompt(s) to run (12 already done)", msg)
        code, msg = cli("score", o, "--labels", "yes,no", "--positive", "yes", "--json", "--compare")
        res = json.loads(msg)["extractors"]
        self.assertGreater(res["last"]["accuracy"], res["first"]["accuracy"])
        self.assertEqual(res["last"]["unparsed"], 1)                     # the refusal
        self.assertEqual(res["last"]["accuracy"], 9 / 12)               # 2 tricky + 1 refusal wrong
        # AutoDiCoT: follow-ups, run them, merge into reasoning exemplars
        f, fo, ex = self.tmp / "f.jsonl", self.tmp / "fo.jsonl", self.tmp / "ex.jsonl"
        self.assertEqual(cli("autodicot", o, "--labels", "yes,no", "--out", f)[0], 0)
        follow = pb.read_jsonl(f)
        wrong = [r for r in follow if not r["correct"]]
        self.assertTrue(all(r["prompt"].endswith(f"It is actually {r['label']}, please explain why.") for r in wrong))
        self.assertEqual(cli("run", f, "--cmd", MODEL, "--out", fo)[0], 0)
        self.assertEqual(cli("autodicot", "--merge", fo, "--out", ex)[0], 0)
        exs = pb.read_jsonl(ex)
        self.assertTrue(all(e["reasoning"].startswith("Because") for e in exs))
        p2 = self.tmp / "p2.jsonl"
        self.assertEqual(cli("build", "--template", FIX / "template.txt", "--data", FIX / "dev.jsonl",
                             "--exemplars", ex, "--k", "2", "--out", p2)[0], 0)
        self.assertIn("\nR: Because", pb.read_jsonl(p2)[0]["prompt"])   # Q/R/A format chosen automatically

    def test_against_lists_fixed_and_broken(self):
        old, new = self.tmp / "old.jsonl", self.tmp / "new.jsonl"
        pb.write_jsonl(old, [{"id": 1, "label": "yes", "outputs": ["no"]}, {"id": 2, "label": "no", "outputs": ["no"]}])
        pb.write_jsonl(new, [{"id": 1, "label": "yes", "outputs": ["yes"]}, {"id": 2, "label": "no", "outputs": ["yes"]}])
        res = json.loads(cli("score", new, "--labels", "yes,no", "--against", old, "--json")[1])
        self.assertEqual(res["against"], {"fixed": [1], "broken": [2]})

    def test_bad_input(self):
        bad = self.tmp / "bad.jsonl"
        bad.write_text('{"label": "maybe", "outputs": ["x"]}\n', encoding="utf-8")
        code, msg = cli("score", bad, "--labels", "yes,no")
        self.assertEqual(code, 2)
        self.assertIn("gold labels not in --labels: maybe", msg)


if __name__ == "__main__":
    unittest.main()
