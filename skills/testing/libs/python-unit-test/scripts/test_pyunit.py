"""Tests for pyunit.py (no third-party packages needed)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyunit  # noqa: E402

SRC = '''
def div(a, b):
    return a / b

def first(items=[]):
    try:
        return items[0]
    except:
        pass

def check(x):
    if x < 0:
        raise ValueError("neg")
    return x
'''
TESTS = '''
import unittest
from calc import div, check
class T(unittest.TestCase):
    def test_div(self):
        self.assertEqual(div(4, 2), 2)
    def test_div_zero(self):
        div(1, 0)
    def test_check_neg(self):
        with self.assertRaises(ValueError):
            check(-1)
    def test_todo(self):
        self.fail("TODO")
'''


class PyunitTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.d)
        self.src = os.path.join(self.d, "calc.py")
        with open(self.src, "w") as fh:
            fh.write(SRC)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.d, ignore_errors=True)

    def write_tests(self):
        with open(os.path.join(self.d, "test_calc.py"), "w") as fh:
            fh.write(TESTS)

    def units(self):
        return pyunit.units_of(pyunit.read_tree(self.src)[1])

    def test_units_found(self):
        u = {x["qualname"]: x for x in self.units()}
        self.assertEqual(set(u), {"div", "first", "check"})
        self.assertEqual(u["check"]["raises"], ["ValueError"])

    def test_static_findings(self):
        codes = {c for _, _, c, _, _ in pyunit.static_findings(self.units())}
        self.assertTrue({"PY001", "PY002", "PY004", "PY005"} <= codes)

    def test_linking_and_quality(self):
        self.write_tests()
        tests = pyunit.collect_tests(pyunit.find_test_files(self.src))
        units = self.units()
        pyunit.link(units, tests)
        linked = {u["name"]: len(u["tests"]) for u in units}
        self.assertEqual(linked["first"], 0)
        self.assertEqual(linked["div"], 2)
        probs = {t["name"]: [c for c, _ in t["problems"]] for t in tests}
        self.assertIn("PT01", probs["test_div_zero"])
        self.assertIn("PT03", probs["test_todo"])
        self.assertEqual(probs["test_div"], [])

    def test_scaffold_never_overwrites(self):
        self.assertEqual(pyunit.main(["scaffold", self.src]), 0)
        dest = os.path.join(self.d, "test_calc.py")
        self.assertTrue(os.path.exists(dest))
        with open(dest, "w") as fh:
            fh.write("# keep me")
        pyunit.main(["scaffold", self.src])
        with open(dest) as fh:
            self.assertEqual(fh.read(), "# keep me")

    def test_run_diagnoses_failures(self):
        self.write_tests()
        self.assertEqual(pyunit.main(["run", self.src]), 1)
        import json
        with open(os.path.join(self.d, pyunit.REPORT_DIR, "report.json")) as fh:
            rep = json.load(fh)
        by = {d["test"].split("::")[-1].split(".")[-1]: d for d in rep["diagnoses"]}
        self.assertEqual(by["test_div_zero"]["likely_cause"], "code")
        self.assertIn("calc.py", by["test_div_zero"]["location"])
        self.assertEqual(by["test_todo"]["likely_cause"], "test")
        self.assertEqual(rep["untested"], ["first"])

    def test_run_without_tests(self):
        self.assertEqual(pyunit.main(["run", self.src]), 2)

    def test_unittest_fallback(self):
        self.write_tests()
        orig = pyunit.have_module
        pyunit.have_module = lambda n: False
        try:
            self.assertEqual(pyunit.main(["run", self.src]), 1)
        finally:
            pyunit.have_module = orig


if __name__ == "__main__":
    unittest.main()
