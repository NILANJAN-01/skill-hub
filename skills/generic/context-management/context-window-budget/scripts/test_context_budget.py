import json
import os
import tempfile
import unittest

import context_budget as cb

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")


def big_session(turns=12, tool_chars=20000):
    """A synthetic agent session: each turn reads a large file."""
    msgs = [{"role": "user", "content": "Task: refactor the billing module."}]
    for n in range(turns):
        msgs.append({"role": "assistant", "content": [
            {"type": "text", "text": "Reading file %d" % n},
            {"type": "tool_use", "id": "t%d" % n, "name": "read_file", "input": {"path": "f%d.py" % n}}]})
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t%d" % n, "content": ("line %d " % n) * (tool_chars // 7)}]})
        msgs.append({"role": "assistant", "content": "Done with file %d." % n})
        msgs.append({"role": "user", "content": "Next file please (%d)." % n})
    return {"messages": msgs, "system": "Be brief.", "tools": None, "extra": {}}


def pairs_intact(messages):
    """Every tool_use id has its tool_result and vice versa."""
    uses, results = set(), set()
    for m in messages:
        for b in m.get("content") if isinstance(m.get("content"), list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                uses.add(b["id"])
            if isinstance(b, dict) and b.get("type") == "tool_result":
                results.add(b["tool_use_id"])
    return uses == results


class LoadTests(unittest.TestCase):
    def test_block_format(self):
        c = cb.load(os.path.join(FIX, "blocks.json"))
        r = cb.analyze(c)
        self.assertEqual(r["messages"], 6)
        self.assertEqual(r["turns"], 2)  # tool-result-only user messages are not turns
        self.assertGreater(r["tool_definition_tokens"], 0)
        self.assertGreaterEqual(r["by_kind"]["image"], cb.IMAGE_TOKENS)
        self.assertIn("tool_call", r["by_kind"])
        self.assertEqual(cb.save(c)["model"], "any-model")

    def test_jsonl_tool_calls_format(self):
        c = cb.load(os.path.join(FIX, "tool_calls.jsonl"))
        r = cb.analyze(c)
        self.assertEqual(r["messages"], 5)
        self.assertIn("tool_result", r["by_kind"])
        self.assertIn("tool_call", r["by_kind"])
        self.assertIsInstance(cb.save(c), list)

    def test_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            with open(p, "w") as fh:
                fh.write('[{"content": "no role"}]')
            with self.assertRaises(ValueError):
                cb.load(p)


class AnalyzeTests(unittest.TestCase):
    def test_recommendations(self):
        c = big_session()
        c["messages"].append(dict(c["messages"][2]))  # the same tool result again
        r = cb.analyze(c, window=50000)
        text = "\n".join(r["recommendations"])
        self.assertIn("Tool results are", text)
        self.assertIn("older than the last", text)
        self.assertIn("repeated tool results", text)
        self.assertIn("Over 80%", text)
        self.assertEqual(r["largest"][0]["kind"], "tool_result")


class TrimTests(unittest.TestCase):
    def test_trim_fits_and_keeps_pairs(self):
        c = big_session()
        before = cb.total_tokens(c)
        new, r = cb.trim(c, budget=before // 4, keep_last=6)
        self.assertTrue(r["fits"], r)
        self.assertLessEqual(cb.total_tokens(new), before // 4)
        self.assertTrue(pairs_intact(new["messages"]))
        self.assertEqual(new["messages"][0]["content"], "Task: refactor the billing module.")
        self.assertEqual(new["messages"][-6:], c["messages"][-6:])  # protected tail untouched
        self.assertEqual(cb.total_tokens(c), before)  # input not modified

    def test_single_strategies(self):
        c = big_session(turns=4, tool_chars=40000)
        new, r = cb.trim(c, budget=cb.total_tokens(c) - 1000, strategies=["truncate-tools"])
        self.assertTrue(r["fits"])
        self.assertTrue(r["actions"][0].startswith("truncate-tools"))
        _, r2 = cb.trim(c, budget=500, strategies=["clear-tools"])
        self.assertFalse(r2["fits"])

    def test_drop_oldest_inserts_note(self):
        c = big_session(turns=6, tool_chars=200)
        new, r = cb.trim(c, budget=200, keep_last=4, strategies=["drop-oldest"], summary="files 0-3 reviewed")
        self.assertTrue(any(a.startswith("drop-oldest") for a in r["actions"]))
        text = json.dumps(new["messages"])
        self.assertIn("were removed to fit the context window", text)
        self.assertIn("files 0-3 reviewed", text)
        self.assertTrue(pairs_intact(new["messages"]))
        self.assertEqual(new["messages"][0]["content"], "Task: refactor the billing module.")

    def test_drop_everything_but_task(self):
        c = big_session(turns=3, tool_chars=200)
        new, r = cb.trim(c, budget=10, keep_last=0, strategies=["drop-oldest"])
        self.assertFalse(r["fits"])
        self.assertEqual(new["messages"][0]["content"], "Task: refactor the billing module.")
        self.assertIn("were removed", new["messages"][-1]["content"])

    def test_tool_role_format(self):
        msgs = [{"role": "user", "content": "go"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "function": {"name": "f", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "x" * 40000},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "next"},
                {"role": "assistant", "content": "done"}]
        c = {"messages": msgs, "system": None, "tools": None, "extra": {}, "list": True}
        new, r = cb.trim(c, budget=3000, keep_last=2)
        self.assertTrue(r["fits"])
        self.assertEqual(len(new["messages"]), 6)
        self.assertIn("trimmed", new["messages"][2]["content"])

    def test_cli_out_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "t.json")
            with open(src, "w") as fh:
                json.dump(cb.save(big_session(turns=3)), fh)
            out = os.path.join(d, "small.json")
            self.assertEqual(cb.main(["trim", src, "--budget", "7000", "--keep-last", "2", "--out", out]), 0)
            self.assertTrue(os.path.exists(out))
            self.assertEqual(cb.main(["trim", src, "--budget", "3000", "--out", out]), 2)
            self.assertEqual(cb.main(["trim", src, "--budget", "3000", "--out", src]), 2)
            self.assertEqual(cb.main(["trim", src, "--budget", "10", "--strategies", "bogus"]), 2)


class PlanTests(unittest.TestCase):
    def test_plan_rows_sum_to_window(self):
        r = cb.plan(200000, system=3000, tools=6000, output=8000, retrieval=20000)
        self.assertEqual(sum(row["tokens"] for row in r["rows"]), 200000)
        self.assertLess(r["trim_to"], r["compact_at"])
        self.assertEqual(r["warnings"], [])

    def test_plan_warnings(self):
        r = cb.plan(8000, system=2000, tools=2000, output=3000, retrieval=2000)
        self.assertTrue(any("exceed the window" in w for w in r["warnings"]))
        self.assertTrue(any("25%" in w for w in r["warnings"]))


if __name__ == "__main__":
    unittest.main()
