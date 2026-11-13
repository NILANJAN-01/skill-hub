import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import doc_check  # noqa: E402
import new_doc  # noqa: E402

GOOD_CV = """# Jane Roe

Pune | jane@example.com | +91 98765 43210 | [GitHub](https://github.com/jane)

## Summary

QA automation engineer with 8 years of Android testing experience. Strong in Kotlin, Appium and Espresso, looking for a senior SDET role that owns test strategy and CI quality gates.

## Skills

- **Automation:** Kotlin, Appium, Espresso, UI Automator
- **CI and reporting:** CI/CD pipelines, Gradle, Allure

## Experience

### SDET, Acme | 2021 - Present

- Built an Appium regression suite of 240 tests that cut release checks from 2 days to 3 hours.
- Reduced flaky tests from 18% to 2% by adding idling resources across 12 screens.
- Automated nightly runs on 6 devices, saving 10 hours per week.
- Mentored 4 engineers on test design and led 12 code reviews per month.

### QA Engineer, Beta Systems | 2018 - 2021

- Wrote 180 Espresso tests for a banking app used by 2 million customers.
- Introduced Allure reports for 3 product teams, shortening triage by 40%.
- Migrated 500 manual test cases to Kotlin automation in 9 months.
- Documented release checklists that reduced escaped defects by 25%.

### Test Analyst, Gamma Labs | 2016 - 2018

- Executed 300 regression cases per release across 15 Android devices.
- Created a device inventory sheet that cut setup time from 30 to 5 minutes.
- Reported 120 defects with logs, videos and reproduction steps.

## Projects

- Open-source logcat analyser used by 300 developers, written in Python with 40 unit tests.

## Education

- B.Tech, Computer Science, 2016

"""

WEAK_CV = """Jane Roe
jane@example.com

Experience
- Responsible for testing things.
- Worked on many projects and helped with various tasks.
- I am a team player and hard-working, and my team liked me.
- Did some more stuff for the company.

Skills
- testing
"""

JOB = """Senior SDET. Requirements: Kotlin, Appium, Espresso, CI/CD pipelines, Docker and Kubernetes experience."""


def write(tmp, name, text):
    p = Path(tmp) / name
    p.write_text(text, encoding="utf-8")
    return p


class Checker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_check(self, text, kind=None, job=None):
        p = write(self.tmp.name, "doc.md", text)
        j = write(self.tmp.name, "job.txt", job) if job else None
        return doc_check.run(p, kind, j)

    def messages(self, result):
        return " | ".join(f["message"] for f in result["findings"])

    def test_good_cv_has_no_warnings(self):
        r = self.run_check(GOOD_CV, "cv")
        warns = [f for f in r["findings"] if f["severity"] == "warn"]
        self.assertEqual(warns, [], self.messages(r))
        self.assertEqual(r["stats"]["bullets"], 15)
        self.assertGreaterEqual(r["stats"]["bullets_with_numbers_pct"], 80)

    def test_weak_cv_is_flagged(self):
        r = self.run_check(WEAK_CV, "cv")
        m = self.messages(r)
        self.assertIn("strong action verb", m)
        self.assertIn("contain a number", m)
        self.assertIn("No dates", m)
        self.assertIn("First-person", m)
        self.assertIn("education", m)

    def test_job_keyword_match(self):
        r = self.run_check(GOOD_CV, "cv", job=JOB)
        s = r["stats"]
        self.assertIn("kotlin", s["job_keywords_covered"])
        self.assertIn("docker", s["job_keywords_missing"])
        self.assertIn("kubernetes", s["job_keywords_missing"])
        self.assertTrue(0 < s["job_keyword_coverage_pct"] < 100)

    def test_type_guessing(self):
        self.assertEqual(doc_check.guess_type(GOOD_CV), "cv")
        blog = "# A title\n\n" + ("Some sentence about tools. " * 150)
        self.assertEqual(doc_check.guess_type(blog), "blog")
        self.assertEqual(doc_check.guess_type("short note"), "doc")

    def test_blog_checks(self):
        text = "# One\n\n# Two\n\n" + ("This is a sentence about testing tools. " * 130) + "\nAndroid 14.0 is the best.\n"
        r = self.run_check(text, "blog")
        m = self.messages(r)
        self.assertIn("More than one H1", m)
        self.assertIn("section headings", m)
        self.assertIn("No external links", m)
        self.assertIn("Superlatives", m)
        self.assertIn("tested with", m.lower())

    def test_prose_metrics_and_filler(self):
        long_sentence = " ".join(["word"] * 45) + "."
        r = self.run_check("It is really very basic. " + long_sentence, "doc")
        m = self.messages(r)
        self.assertIn("over 35 words", m)
        self.assertIn("Filler", m)
        self.assertGreater(r["stats"]["words"], 40)

    def test_docx_is_read(self):
        p = Path(self.tmp.name) / "cv.docx"
        xml = ('<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>Hello &amp; welcome</w:t></w:r></w:p>'
               "<w:p><w:r><w:t>Second line</w:t></w:r></w:p></w:body></w:document>")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", xml)
        self.assertEqual(doc_check.read_text(p), "Hello & welcome\nSecond line")

    def test_pdf_is_rejected_clearly(self):
        p = Path(self.tmp.name) / "cv.pdf"
        p.write_bytes(b"%PDF-1.4")
        with self.assertRaises(SystemExit) as ctx:
            doc_check.read_text(p)
        self.assertIn("PDF", str(ctx.exception))

    def test_cli_json_and_text(self):
        p = write(self.tmp.name, "cv.md", GOOD_CV)
        out = subprocess.run([sys.executable, str(HERE / "doc_check.py"), str(p), "--json"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out)["type"], "cv")
        out = subprocess.run([sys.executable, str(HERE / "doc_check.py"), str(p), "--type", "cv"],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("Type: cv", out)

    def test_missing_file_exits_nonzero(self):
        r = subprocess.run([sys.executable, str(HERE / "doc_check.py"), str(Path(self.tmp.name) / "none.md")],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


class Scaffold(unittest.TestCase):
    def test_all_templates_exist_and_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            for kind in new_doc.TEMPLATES:
                out = Path(tmp) / f"{kind}.md"
                new_doc.create(kind, out, title="My Title")
                text = out.read_text(encoding="utf-8")
                self.assertNotIn("{{TITLE}}", text)
                self.assertIn("My Title", text)

    def test_no_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "x.md"
            out.write_text("mine", encoding="utf-8")
            with self.assertRaises(SystemExit):
                new_doc.create("blog", out)
            self.assertEqual(out.read_text(encoding="utf-8"), "mine")
            new_doc.create("blog", out, force=True)
            self.assertNotEqual(out.read_text(encoding="utf-8"), "mine")

    def test_unknown_template(self):
        with self.assertRaises(SystemExit):
            new_doc.create("nope", Path("x.md"))

    def test_blog_template_passes_structure_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.md"
            new_doc.create("blog", out, title="Android test tools compared")
            r = doc_check.run(out, "blog", None)
            self.assertEqual(r["type"], "blog")
            self.assertNotIn("No title", " ".join(f["message"] for f in r["findings"]))


if __name__ == "__main__":
    unittest.main()
