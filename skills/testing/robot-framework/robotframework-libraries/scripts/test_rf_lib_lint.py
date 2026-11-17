import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rf_lib_lint  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def rules(r, file_part):
    return {(f["rule"], f["line"]) for f in r["findings"] if file_part in f["file"]}


class LibLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = rf_lib_lint.lint(FIX)

    def test_keywords_found(self):
        names = {k["keyword"] for k in self.r["keywords"]}
        self.assertEqual(names, {"Connect", "Order ${order_id: int} should be ${status}", "Wait For Order", "Log In"})
        self.assertTrue(any(k["async"] for k in self.r["keywords"] if k["keyword"] == "Wait For Order"))

    def test_class_library_findings(self):
        got = rules(self.r, "OrdersLibrary.py")
        for expected in [("deprecated-utils", 3), ("scope", 7), ("no-intro", 7), ("no-doc", 9), ("no-types", 9),
                         ("secret-arg", 9), ("print", 10), ("positional-only", 11), ("base-exception", 18)]:
            self.assertIn(expected, got)

    def test_good_module_is_clean(self):
        self.assertEqual(rules(self.r, "good_module.py"), set())

    def test_library_decorator_exposes_only_keyword_methods(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Lib.py"), "w", encoding="utf-8") as fh:
                fh.write("from robot.api.deco import keyword, library\n\n"
                         "@library(scope='GLOBAL')\nclass Lib:\n    '''Intro.'''\n"
                         "    @keyword\n    def visible(self, x: int):\n        '''Doc.'''\n"
                         "    def forgotten(self):\n        pass\n")
            r = rf_lib_lint.lint(d)
            self.assertEqual([k["keyword"] for k in r["keywords"]], ["Visible"])
            self.assertEqual([(f["rule"], f["line"]) for f in r["findings"]], [("not-exposed", 9)])

    def test_exit_codes(self):
        self.assertEqual(rf_lib_lint.main([os.path.join(FIX, "good_module.py"), "--strict", "--json"]), 0)
        self.assertEqual(rf_lib_lint.main([os.path.join(FIX, "OrdersLibrary.py"), "--strict", "--json"]), 1)
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "Broken.py"), "w", encoding="utf-8") as fh:
                fh.write("def x(:\n")
            self.assertEqual(rf_lib_lint.main([d, "--json"]), 1)
        self.assertEqual(rf_lib_lint.main([os.path.join(FIX, "missing.py")]), 2)


if __name__ == "__main__":
    unittest.main()
