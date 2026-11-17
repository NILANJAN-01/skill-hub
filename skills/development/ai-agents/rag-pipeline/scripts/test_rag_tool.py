import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rag_tool  # noqa: E402

DOCS = os.path.join(HERE, "fixtures", "docs")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ChunkTests(unittest.TestCase):
    def test_sections_keep_heading_path_and_code(self):
        with open(os.path.join(DOCS, "security.md"), encoding="utf-8") as fh:
            chunks = rag_tool.chunk_text(fh.read(), size=1200, overlap=100)
        headings = [h for h, _ in chunks]
        self.assertIn(["Security", "API keys"], headings)
        api = [t for h, t in chunks if h == ["Security", "API keys"]][0]
        self.assertTrue(api.startswith("Security > API keys"))
        self.assertIn("service keys rotate --project demo\nservice keys list", api)

    def test_size_limit_and_overlap(self):
        text = "# Title\n\n" + "\n\n".join("Sentence number %d is here." % i for i in range(200))
        chunks = rag_tool.chunk_text(text, size=300, overlap=60)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(t) <= 300 for _, t in chunks))
        first_body = chunks[0][1].split("\n\n", 1)[1]
        second_body = chunks[1][1].split("\n\n", 1)[1]
        self.assertIn(first_body[-20:], second_body)

    def test_long_paragraph_is_split(self):
        chunks = rag_tool.chunk_text("x" * 2500, size=1000, overlap=0)
        self.assertEqual([len(t) for _, t in chunks], [1000, 1000, 500])

    def test_overlap_must_be_smaller(self):
        with self.assertRaises(ValueError):
            rag_tool.chunk_text("text", size=100, overlap=100)

    def test_cli_chunk_directory(self):
        tmp = tempfile.mkdtemp()
        try:
            out = os.path.join(tmp, "chunks.jsonl")
            stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                self.assertEqual(rag_tool.main(["chunk", DOCS, "--out", out]), 0)
            finally:
                sys.stderr = stderr
            rows = rag_tool.read_jsonl(out)
            self.assertEqual({r["source"] for r in rows}, {"security.md", "faq.txt"})
            self.assertTrue(all(r["id"].startswith(r["source"] + "#") for r in rows))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ScoreTests(unittest.TestCase):
    def test_metrics(self):
        queries = [{"id": "q1", "query": "rotate key", "relevant": ["security.md"]},
                   {"id": "q2", "query": "refund time", "relevant": ["faq.txt"]},
                   {"id": "q3", "query": "unknown", "relevant": ["other.md"]}]
        results = [{"id": "q1", "retrieved": ["security.md#2", "security.md#3", "faq.txt#1"]},
                   {"id": "q2", "retrieved": ["security.md#1", "faq.txt#1"]},
                   {"id": "q3", "retrieved": ["faq.txt#1"]}]
        s = rag_tool.score_retrieval(queries, results, ks=(1, 3), match="source")
        self.assertEqual(s["hit_rate@1"], round(1 / 3.0, 4))
        self.assertEqual(s["hit_rate@3"], round(2 / 3.0, 4))
        self.assertEqual(s["mrr"], round((1 + 0.5 + 0) / 3.0, 4))
        self.assertEqual(s["not_found_in_top_3"], ["q3"])

    def test_exact_match_and_missing(self):
        queries = [{"id": "a", "relevant": ["d#1", "d#2"]}, {"id": "b", "relevant": ["x#1"]}]
        results = [{"id": "a", "retrieved": ["d#2", "z#1"]}]
        s = rag_tool.score_retrieval(queries, results, ks=(2,), match="exact")
        self.assertEqual(s["recall@2"], 0.25)
        self.assertEqual(s["missing_results"], ["b"])

    def test_cli_score(self):
        tmp = tempfile.mkdtemp()
        try:
            q, r = os.path.join(tmp, "q.jsonl"), os.path.join(tmp, "r.jsonl")
            write_jsonl(q, [{"id": "q1", "query": "x", "relevant": ["a.md"]}])
            write_jsonl(r, [{"id": "q1", "retrieved": ["a.md#4"]}])
            stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                self.assertEqual(rag_tool.main(["score", q, r, "--match", "source", "--json"]), 0)
                data = json.loads(sys.stdout.getvalue())
            finally:
                sys.stdout = stdout
            self.assertEqual(data["mrr"], 1.0)
            self.assertEqual(rag_tool.main(["score", q, os.path.join(tmp, "nope.jsonl")]), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
