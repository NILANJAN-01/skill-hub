import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pw_upgrade  # noqa: E402

OLD = os.path.join(HERE, "fixtures", "old-project")


def affected(p):
    return {(r["version"], r["change"].split()[0]): r["places"] for r in p["changes"] if r["places"]}


class UpgradeTests(unittest.TestCase):
    def test_detects_version_and_scans(self):
        p = pw_upgrade.plan(OLD)
        self.assertEqual((p["current"], p["target"]), ("1.48", "1.65"))
        found = affected(p)
        files = {(v, h["file"]) for (v, _), hits in found.items() for h in hits}
        for expected in [("1.58", "tests/cart.spec.ts"),        # _react=
                         ("1.57", "tests/cart.spec.ts"),        # page.accessibility, screenshots
                         ("1.52", "tests/cart.spec.ts"),        # glob with ?
                         ("1.58", "playwright.config.ts"),      # devtools
                         ("1.54", "package.json"),              # -gv
                         ("1.63", ".github/workflows/e2e.yml"), # ubuntu-20.04
                         ("1.65", ".github/workflows/e2e.yml")]:  # node 20, shard + grep
            self.assertIn(expected, files)
        self.assertEqual(p["docker_images"][0]["tag"], "mcr.microsoft.com/playwright:v1.48.2-noble")

    def test_range_is_respected(self):
        p = pw_upgrade.plan(OLD, from_v=(1, 60), to_v=(1, 62))
        self.assertEqual({r["version"] for r in p["changes"]}, {"1.62"})
        p = pw_upgrade.plan(OLD, from_v=(1, 65), to_v=(1, 65))
        self.assertEqual(p["changes"], [])
        self.assertTrue(any("already on" in n for n in p["notes"]))
        p = pw_upgrade.plan(OLD, to_v=(1, 70))
        self.assertTrue(any("covers up to 1.65" in n for n in p["notes"]))

    def test_python_project_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "requirements.txt"), "w", encoding="utf-8") as fh:
                fh.write("pytest-playwright==0.7.0\nplaywright==1.55.0\n")
            p = pw_upgrade.plan(d)
            self.assertEqual((p["language"], p["current"]), ("python", "1.55"))
            self.assertIn("pip install", pw_upgrade.steps(p)[0])
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(pw_upgrade.main([empty]), 2)
            self.assertEqual(pw_upgrade.main([empty, "--from", "1.64", "--json"]), 0)
        self.assertEqual(pw_upgrade.main([OLD, "--json"]), 1)
        self.assertEqual(pw_upgrade.main([OLD, "--to", "abc"]), 2)


if __name__ == "__main__":
    unittest.main()
