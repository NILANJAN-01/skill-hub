"""Tests for audit.py. Fake secrets are assembled at run time, so this file holds nothing that looks like a real key."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit  # noqa: E402

AWS = "AKIA" + "Q7" * 8
GH = "ghp_" + "a1B2c3D4e5" * 4
KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
PW = "Xq" + "7#vL9!pR2$" + "mT4"
HAS_GIT = shutil.which("git") is not None


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(HERE / "audit.py"), *args], cwd=self.dir, capture_output=True,
                           text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True)


class Secrets(TempRepo):
    def test_provider_formats_and_masking(self):
        self.write("config.py", f'AWS_KEY = "{AWS}"\nGITHUB = "{GH}"\n')
        self.write("id_rsa", KEY + "\nabc\n")
        code, out = self.run_cli("scan")
        self.assertEqual(code, 1)
        for rule in ("aws-access-key-id", "github-token", "private-key"):
            self.assertIn(rule, out)
        self.assertNotIn(AWS, out)                                   # never printed in full
        self.assertNotIn(GH, out)
        self.assertIn(AWS[:4] + "…" + AWS[-2:], out)

    def test_generic_assignments_need_a_secret_name_and_a_random_value(self):
        self.write("app.env", f'DB_PASSWORD="{PW}"\nGIT_AUTHOR_NAME="Scott Chacon Long"\ntokenizer="bert-base-uncased"\n'
                              'API_KEY="${API_KEY}"\npassword="changeme123"\nclientSecret: "aaaaaaaaaaaa"\n')
        findings = audit.scan(self.dir, [str(self.dir)])
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("secret-assignment", 1)])

    def test_url_credentials_and_suppression(self):
        self.write("db.txt", f"postgres://admin:{PW}@db.internal:5432/app\n"
                             f"https://user:{PW}@example.com/x  # audit:ignore\n")
        findings = audit.scan(self.dir, [str(self.dir)])
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("url-credentials", 1)])

    def test_baseline_accepts_known_findings(self):
        self.write("a.py", f'k = "{AWS}"\n')
        self.assertEqual(self.run_cli("baseline")[0], 0)
        self.assertTrue((self.dir / audit.BASELINE).is_file())
        code, out = self.run_cli("scan")
        self.assertEqual(code, 0, out)
        self.assertIn("1 accepted finding", out)
        self.write("b.py", f'k = "{GH}"\n')                          # a new secret is still reported
        self.assertEqual(self.run_cli("scan")[0], 1)

    def test_fail_on_and_json(self):
        self.write("a.json", '{"token": "' + "eyJ" + "a" * 12 + ".eyJ" + "b" * 12 + "." + "c" * 12 + '"}')
        self.assertEqual(self.run_cli("scan", "--fail-on", "high")[0], 0)   # a JWT is medium
        code, out = self.run_cli("scan", "--json")
        data = json.loads(out)
        self.assertEqual((code, data["count"], data["findings"][0]["rule"]), (1, 1, "jwt"))

    def test_skips_binaries_and_dependency_folders(self):
        (self.dir / "img.bin").write_bytes(b"\0\1" + AWS.encode())
        self.write("node_modules/pkg/index.js", f'k = "{AWS}"\n')
        self.assertEqual(audit.scan(self.dir, [str(self.dir)]), [])


@unittest.skipUnless(HAS_GIT, "git is not installed")
class GitModes(TempRepo):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "Test")

    def test_staged_reports_only_added_lines(self):
        self.write("old.py", f'k = "{AWS}"\n')
        self.git("add", ".")
        self.git("commit", "-q", "-m", "old")
        self.write("new.py", f'x = 1\ng = "{GH}"\n')
        self.git("add", "new.py")
        findings = audit.scan(self.dir, [], staged=True)
        self.assertEqual([(f["path"], f["line"], f["rule"]) for f in findings], [("new.py", 2, "github-token")])

    def test_history_finds_removed_secrets(self):
        self.write("cfg.py", f'k = "{AWS}"\n')
        self.git("add", ".")
        self.git("commit", "-q", "-m", "add")
        self.write("cfg.py", "k = None\n")
        self.git("commit", "-qam", "remove")
        self.assertEqual(audit.scan(self.dir, [str(self.dir)]), [])                   # gone from the files
        hist = audit.scan(self.dir, [], history=True)
        self.assertEqual([f["rule"] for f in hist], ["aws-access-key-id"])            # but still in history
        self.assertTrue(hist[0]["where"].startswith("commit "))

    def test_gitignored_files_are_skipped(self):
        self.write(".gitignore", "secrets.local\n")
        self.write("secrets.local", f'k = "{AWS}"\n')
        self.assertEqual(audit.scan(self.dir, [str(self.dir)]), [])

    def test_install_hook_asks_first(self):
        code, out = self.run_cli("install-hook")
        self.assertEqual(code, 0)
        self.assertIn("Nothing written", out)
        self.assertFalse((self.dir / ".git" / "hooks" / "pre-commit").exists())
        self.assertEqual(self.run_cli("install-hook", "--yes")[0], 0)
        self.assertIn("scan --staged", (self.dir / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8"))


class Dependencies(TempRepo):
    def rules(self):
        return sorted((f["path"], f["rule"], f["severity"]) for f in audit.deps(self.dir))

    def test_python_requirements(self):
        self.write("requirements.txt", "requests==2.32.3\nflask\ndjango>=4\n--extra-index-url https://pkgs.example\n"
                                       "-i http://mirror.example/simple\ngit+https://github.com/o/r.git\n")
        self.assertEqual(self.rules(), sorted([
            ("requirements.txt", "unpinned-python-dependency", "medium"),
            ("requirements.txt", "unpinned-python-dependency", "low"),
            ("requirements.txt", "extra-index-url", "medium"),
            ("requirements.txt", "insecure-index", "high"),
            ("requirements.txt", "vcs-or-url-dependency", "medium")]))

    def test_npm(self):
        self.write("web/package.json", json.dumps({"dependencies": {"left-pad": "*", "lib": "github:o/lib",
                                                                    "ok": "^1.2.3"}}))
        self.assertEqual(self.rules(), sorted([("web/package.json", "wildcard-npm-version", "high"),
                                               ("web/package.json", "git-or-url-dependency", "medium"),
                                               ("web/package.json", "missing-lockfile", "medium")]))
        self.write("web/package-lock.json", "{}")
        self.assertNotIn("missing-lockfile", [r for _, r, _ in self.rules()])

    def test_gradle_maven_docker_and_actions(self):
        self.write("app/build.gradle.kts", 'implementation("com.squareup:okhttp:4.+")\n'
                                           'maven { url = uri("http://repo.example") }\n')
        self.write("pom.xml", "<version>LATEST</version>\n<url>http://repo.example</url>\n")
        self.write("Dockerfile", "FROM python\nRUN curl -sSL https://x.example/i.sh | sh\n")
        self.write(".github/workflows/ci.yml", "    - uses: actions/checkout@v4\n    - uses: other/tool@main\n"
                                               "    - uses: other/pinned@" + "a" * 40 + "\npermissions: write-all\n")
        got = self.rules()
        for want in [("app/build.gradle.kts", "dynamic-gradle-version", "medium"),
                     ("app/build.gradle.kts", "insecure-repository", "high"),
                     ("pom.xml", "floating-maven-version", "medium"), ("pom.xml", "insecure-repository", "high"),
                     ("Dockerfile", "unpinned-image", "medium"), ("Dockerfile", "pipe-to-shell", "medium"),
                     (".github/workflows/ci.yml", "unpinned-action", "low"),
                     (".github/workflows/ci.yml", "unpinned-action", "medium"),
                     (".github/workflows/ci.yml", "broad-permissions", "medium")]:
            self.assertIn(want, got)
        self.assertEqual(sum(r == "unpinned-action" for _, r, _ in got), 2)      # the SHA-pinned one is fine


if __name__ == "__main__":
    unittest.main()
