import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pw_ci  # noqa: E402


class CiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "package.json"), "w", encoding="utf-8") as fh:
            json.dump({"devDependencies": {"@playwright/test": "^1.56.1"}}, fh)
        with open(os.path.join(self.dir, "package-lock.json"), "w", encoding="utf-8") as fh:
            json.dump({"packages": {"node_modules/@playwright/test": {"version": "1.56.1"}}}, fh)

    def test_detects_version_and_package_manager(self):
        info = pw_ci.detect(self.dir, "node")
        self.assertEqual((info["pm"], info["version"]), ("npm", "1.56.1"))
        open(os.path.join(self.dir, "pnpm-lock.yaml"), "w").close()
        self.assertEqual(pw_ci.detect(self.dir, "node")["pm"], "pnpm")

    def test_github_sharded(self):
        text, notes, _ = pw_ci.generate("github", self.dir, shards=3, env=["E2E_PASSWORD"], grep="@smoke",
                                        browsers="chromium")
        self.assertIn("shardIndex: [1, 2, 3]", text)
        self.assertIn("--shard=${{ matrix.shardIndex }}/${{ matrix.shardTotal }}", text)
        self.assertIn('--grep "@smoke" --pass-with-no-tests', text)
        self.assertIn("E2E_PASSWORD: ${{ secrets.E2E_PASSWORD }}", text)
        self.assertIn("playwright install --with-deps chromium", text)
        self.assertIn("merge-reports --reporter html,junit ./all-blob-reports", text)
        self.assertIn("if: ${{ !cancelled() }}", text)

    def test_gitlab_pins_image_and_parallel(self):
        text, _, _ = pw_ci.generate("gitlab", self.dir, shards=4, env=["BASE_URL"])
        self.assertIn("mcr.microsoft.com/playwright:v1.56.1-noble", text)
        self.assertIn("parallel: 4", text)
        self.assertIn("--shard=$CI_NODE_INDEX/$CI_NODE_TOTAL", text)
        self.assertIn("junit: results.xml", text)
        self.assertIn("#   BASE_URL", text)
        single, _, _ = pw_ci.generate("gitlab", self.dir, shards=1)
        self.assertNotIn("parallel:", single)
        self.assertNotIn("--shard", single)

    def test_azure_and_jenkins(self):
        az, _, _ = pw_ci.generate("azure", self.dir, shards=2, env=["E2E_USER"])
        self.assertIn("$(System.JobPositionInPhase)/$(System.TotalJobsInPhase)", az)
        self.assertIn("E2E_USER: $(E2E_USER)", az)
        jk, _, _ = pw_ci.generate("jenkins", self.dir, shards=2, env=["E2E_USER"])
        self.assertIn("stage('Shard 2')", jk)
        self.assertIn("--shard=2/2", jk)
        self.assertIn("--output=test-results-2", jk)
        self.assertIn("E2E_USER = credentials('E2E_USER')", jk)
        self.assertIn("args '--ipc=host'", jk)

    def test_python_has_no_sharding(self):
        text, notes, _ = pw_ci.generate("github", self.dir, shards=3, lang="python", grep="@smoke")
        self.assertNotIn("--shard", text)
        self.assertIn("pytest --tracing retain-on-failure", text)
        self.assertTrue(any("xdist" in n for n in notes))
        self.assertTrue(any("-k or -m" in n for n in notes))

    def test_unknown_version_note_and_errors(self):
        with tempfile.TemporaryDirectory() as empty:
            text, notes, _ = pw_ci.generate("gitlab", empty)
            self.assertIn("<PLAYWRIGHT_VERSION>", text)
            self.assertTrue(any("version not found" in n for n in notes))
        with self.assertRaises(ValueError):
            pw_ci.generate("travis", self.dir)
        with self.assertRaises(ValueError):
            pw_ci.generate("github", self.dir, env=["bad name"])

    def test_cli_out_and_no_overwrite(self):
        out = os.path.join(self.dir, ".github", "workflows", "playwright.yml")
        stderr = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            self.assertEqual(pw_ci.main(["--ci", "github", "--project-dir", self.dir, "--out", out]), 0)
            self.assertEqual(pw_ci.main(["--ci", "github", "--project-dir", self.dir, "--out", out]), 1)
            self.assertEqual(pw_ci.main(["--ci", "github", "--project-dir", self.dir, "--out", out, "--force"]), 0)
            self.assertEqual(pw_ci.main(["--ci", "github", "--shards", "0"]), 2)
        finally:
            sys.stderr.close()
            sys.stderr = stderr
        self.assertTrue(os.path.isfile(out))


if __name__ == "__main__":
    unittest.main()
