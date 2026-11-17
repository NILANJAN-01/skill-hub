"""Tests run against real outputs produced by Robot Framework 7.5.1 from fixtures/suite/checkout.robot."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rf_results  # noqa: E402

FX = os.path.join(HERE, "fixtures")
XML, JSON, RERUN = (os.path.join(FX, n) for n in ("output.xml", "output.json", "rerun.xml"))


def summary(path, **kw):
    tests, errors, kws, gen = rf_results.load(path)
    return rf_results.summarize(tests, errors, kws, gen, **kw)


class ResultsTests(unittest.TestCase):
    def check_common(self, s):
        self.assertIn("Robot 7.5.1", s["generator"])
        self.assertEqual((s["total"], s["passed"], s["failed"], s["skipped"]), (6, 1, 4, 1))
        by_name = {f["test"].split(".")[-1]: f for f in s["failures"]}
        self.assertEqual(by_name["Price Should Match"]["category"], "assertion")
        self.assertEqual(by_name["Price Should Match"]["failing_keywords"], ["Check Total", "BuiltIn.Should Be Equal"])
        self.assertEqual(by_name["Missing Keyword"]["category"], "keyword-not-found")
        self.assertEqual(by_name["Slow Step"]["category"], "timeout")
        self.assertNotIn("Modern Syntax Works", by_name)          # handled TRY failure does not count
        self.assertEqual(s["skipped_tests"][0]["reason"], "Feature flag is off")
        self.assertEqual(s["slowest_tests"][0]["test"], "Suite.Checkout.Slow Step")
        self.assertIn("checkout", s["by_tag"])

    def test_xml(self):
        self.check_common(summary(XML))

    def test_json(self):
        self.check_common(summary(JSON))

    def test_rerun_finds_flaky(self):
        rerun = rf_results.load(RERUN)[0]
        s = summary(XML, rerun=rerun)
        self.assertEqual(s["flaky"], ["Suite.Checkout.Flaky Payment"])
        self.assertEqual(len(s["failed_again"]), 3)

    def test_baseline_and_cli(self):
        base = rf_results.load(XML)[0]
        for t in base:
            if t["name"] == "Missing Keyword":
                t["status"] = "PASS"
        s = summary(XML, baseline=base)
        self.assertEqual(s["new_failures"], ["Suite.Checkout.Missing Keyword"])
        self.assertEqual(rf_results.main([XML, "--rerun", RERUN, "--json"]), 0)
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "x.xml")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("<testsuite/>")
            self.assertEqual(rf_results.main([bad]), 2)

    def test_rf6_timestamps(self):
        xml = ('<robot generator="Robot 6.1.1"><suite name="S"><test name="T">'
               '<kw name="Log" library="BuiltIn"><status status="FAIL" starttime="20240101 10:00:00.000" endtime="20240101 10:00:01.500"/></kw>'
               '<status status="FAIL" starttime="20240101 10:00:00.000" endtime="20240101 10:00:02.000">boom</status>'
               '</test></suite><errors/></robot>')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "o.xml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(xml)
            s = summary(path)
        self.assertEqual(s["slowest_tests"][0]["seconds"], 2.0)
        self.assertEqual(s["failures"][0]["failing_keywords"], ["BuiltIn.Log"])


if __name__ == "__main__":
    unittest.main()
