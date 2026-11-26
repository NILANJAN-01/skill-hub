"""Tests for nlp_lite.py. Expected values were produced by scikit-learn 1.x, numpy and the yake package."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nlp_lite  # noqa: E402

DOCS = ["git rebase rebase onto master", "git merge master branch", "git commit amend message",
        "rebase interactive squash commits"]
HOOKS = ("Git hooks are scripts that Git runs before or after events such as commit, push and receive. "
         "Client-side hooks run on your machine. The pre-commit hook runs first, before you type a commit message. "
         "Server-side hooks run on the server when a push arrives. A pre-receive hook can reject a push. "
         "Git hooks live in the hooks directory of the repository.")


class TfidfMatchesScikitLearn(unittest.TestCase):
    def setUp(self):
        self.vec = nlp_lite.Tfidf(str.split, sublinear_tf=True, max_df=0.6)
        self.X = self.vec.fit_transform(DOCS)
        self.names = {i: t for t, i in self.vec.vocab.items()}

    def row(self, r):
        return sorted((self.names[k], round(w, 6)) for k, w in r.items())

    def test_weights(self):
        # TfidfVectorizer(analyzer=str.split, sublinear_tf=True, max_df=0.6): 'git' is in 3 of 4 docs, so dropped
        self.assertEqual(self.row(self.X[0]), [("master", 0.427354), ("onto", 0.542044), ("rebase", 0.723573)])
        self.assertEqual(self.row(self.X[1]), [("branch", 0.617614), ("master", 0.486934), ("merge", 0.617614)])
        self.assertEqual(self.row(self.X[3]), [("commits", 0.525473), ("interactive", 0.525473),
                                               ("rebase", 0.414289), ("squash", 0.525473)])
        self.assertNotIn("git", self.vec.vocab)

    def test_transform_ignores_unknown_terms(self):
        self.assertEqual(self.row(self.vec.transform(["rebase master unknown"])[0]),
                         [("master", 0.707107), ("rebase", 0.707107)])

    def test_empty_vocabulary_raises_value_error(self):
        with self.assertRaises(ValueError):
            nlp_lite.Tfidf(lambda s: []).fit_transform(["a", "b"])

    def test_pagerank_matches_numpy_power_iteration(self):
        ranks = nlp_lite.pagerank(nlp_lite.similarity_matrix(self.X), len(DOCS))
        self.assertEqual([round(x, 6) for x in ranks], [0.46332, 0.208985, 0.047619, 0.280075])
        self.assertAlmostEqual(sum(ranks), 1.0, places=6)


class Yake(unittest.TestCase):
    def test_top_keywords_match_the_yake_package(self):
        got = [k for k, _ in nlp_lite.yake(HOOKS, n=3, top=8, dedup_lim=0.7)]
        # yake.KeywordExtractor(lan="en", n=3, top=8, dedupLim=0.7) gives the same first seven
        self.assertEqual(got[:7], ["hooks", "hooks run", "Git", "Git hooks", "Client-side hooks run", "push", "runs"])

    def test_scores_ascend_and_empty_text(self):
        scores = [s for _, s in nlp_lite.yake(HOOKS, top=10)]
        self.assertEqual(scores, sorted(scores))
        self.assertEqual(nlp_lite.yake(""), [])
        self.assertEqual(nlp_lite.yake("the and of"), [])


if __name__ == "__main__":
    unittest.main()
