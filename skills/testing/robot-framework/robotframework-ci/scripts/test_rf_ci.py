import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rf_ci  # noqa: E402


class CiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "requirements.txt"), "w", encoding="utf-8") as fh:
            fh.write("robotframework==7.5.1\nrobotframework-browser==20.1.0\nrobotframework-pabot==5.1.0\n")

    def test_detect(self):
        info = rf_ci.detect(self.dir)
        self.assertEqual((info["rf"], info["browser"], info["pabot"]), ("7.5.1", "20.1.0", True))

    def test_github_rerun_block(self):
        text, _, _ = rf_ci.generate("github", self.dir, env=["E2E_PASSWORD"], include="smoke")
        self.assertIn("PYTHONIOENCODING: utf-8", text)
        self.assertIn("E2E_PASSWORD: ${{ secrets.E2E_PASSWORD }}", text)
        self.assertIn("rfbrowser init", text)
        self.assertIn("actions/setup-node@v4", text)
        self.assertIn('robot --outputdir results --xunit xunit.xml --include "smoke" tests', text)
        self.assertIn('if [ "$rc" -ge 1 ] && [ "$rc" -le 250 ]; then', text)
        self.assertIn("set +e", text)
        self.assertIn("--rerunfailed results/output.xml --output rerun.xml", text)
        self.assertIn("rebot --outputdir results --output merged.xml --xunit xunit.xml --merge", text)

    def test_pabot_and_no_rerun(self):
        text, _, _ = rf_ci.generate("github", self.dir, pabot=4, rerun=False)
        self.assertIn("pabot --processes 4 --outputdir results --xunit xunit.xml tests", text)
        self.assertNotIn("--rerunfailed", text)

    def test_gitlab_uses_browser_image(self):
        text, _, _ = rf_ci.generate("gitlab", self.dir, env=["API_TOKEN"])
        self.assertIn("image: marketsquare/robotframework-browser:20.1.0", text)
        self.assertNotIn("- rfbrowser init", text)
        self.assertIn("junit: results/xunit.xml", text)
        self.assertIn("#   API_TOKEN", text)

    def test_azure_and_jenkins(self):
        az, _, _ = rf_ci.generate("azure", self.dir, env=["E2E_USER"])
        self.assertIn("E2E_USER: $(E2E_USER)", az)
        self.assertIn("testResultsFiles: results/xunit.xml", az)
        self.assertIn("NodeTool@0", az)
        jk, _, _ = rf_ci.generate("jenkins", self.dir, env=["E2E_USER"])
        self.assertIn("E2E_USER = credentials('E2E_USER')", jk)
        self.assertIn("junit allowEmptyResults: true, testResults: 'results/xunit.xml'", jk)
        self.assertIn(". .venv/bin/activate", jk)

    def test_plain_project_notes_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "requirements.txt"), "w", encoding="utf-8") as fh:
                fh.write("robotframework==6.1.1\n")
            text, notes, _ = rf_ci.generate("gitlab", d, pabot=2)
            self.assertIn("image: python:3.13", text)
            self.assertNotIn("rfbrowser", text)
            self.assertIn("pip install -r requirements.txt robotframework-pabot", text)
            self.assertTrue(any("6.1.1" in n for n in notes))
        with self.assertRaises(ValueError):
            rf_ci.generate("travis", self.dir)
        with self.assertRaises(ValueError):
            rf_ci.generate("github", self.dir, env=["bad name"])

    def test_cli_out(self):
        out = os.path.join(self.dir, ".github", "workflows", "robot.yml")
        stderr, sys.stderr = sys.stderr, open(os.devnull, "w")
        try:
            self.assertEqual(rf_ci.main(["--ci", "github", "--project-dir", self.dir, "--out", out]), 0)
            self.assertEqual(rf_ci.main(["--ci", "github", "--project-dir", self.dir, "--out", out]), 1)
            self.assertEqual(rf_ci.main(["--ci", "github", "--pabot", "-1"]), 2)
        finally:
            sys.stderr.close()
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
