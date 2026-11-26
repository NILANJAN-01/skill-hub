"""End-to-end test: a small generated PDF manual becomes a skill, using only the standard library."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_pdf_lite import Builder  # noqa: E402

LOREM = ("The tool keeps a local cache of packages, so later installs are fast and work offline. "
         "You can use the cache to pin versions for a whole team. ")


def manual_pdf():
    """A 3-page 'manual' with headings, prose and shell commands, like the books skillforge reads."""
    pages = []
    b = Builder()
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold>>", 3)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>", 4)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Courier>>", 5)
    fonts = b"<</Font <</H 3 0 R /B 4 0 R /C 5 0 R>>>>"
    chapters = [
        (b"Installing Packages", [b"$ tool install left-pad", b"$ tool install --global serve",
                                  b"$ tool list", b"Installed: left-pad 1.3.0"]),
        (b"Removing Packages", [b"$ tool remove left-pad", b"$ tool remove --force serve", b"$ tool list",
                                b"error: package serve is still in use"]),
    ]
    num = 10
    for title, cmds in chapters:
        for part in range(2):
            ops = [b"BT /H 20 Tf 72 740 Td (%s) Tj ET" % title] if part == 0 else []   # page 2 continues
            y = 700
            for k in range(6):
                for line in (LOREM[:90], LOREM[90:]):
                    ops.append(b"BT /B 10 Tf 72 %d Td (%s) Tj ET" % (y, line.encode()))
                    y -= 12
                y -= 8
                if k == 2:
                    ops.append(b"BT /B 10 Tf 72 %d Td (To do this, run:) Tj ET" % y)
                    y -= 20
                    for c in cmds:
                        ops.append(b"BT /C 9 Tf 90 %d Td (%s) Tj ET" % (y, c))
                        y -= 11
                    y -= 10
            content = b"\n".join(ops)
            b.add((b"<</Length %d>>" % len(content), content), num + 1)
            b.add(b"<</Type /Page /Parent 2 0 R /Resources %s /Contents %d 0 R>>" % (fonts, num + 1), num)
            pages.append(num)
            num += 2
    kids = b" ".join(b"%d 0 R" % p for p in pages)
    b.add(b"<</Type /Pages /Kids [%s] /Count %d /MediaBox [0 0 612 792]>>" % (kids, len(pages)), 2)
    b.add(b"<</Type /Catalog /Pages 2 0 R /Outlines 6 0 R>>", 1)
    b.add(b"<</Type /Outlines /First 7 0 R /Last 8 0 R>>", 6)
    b.add(b"<</Title (Tool Installing) /Parent 6 0 R /Next 8 0 R /Dest [%d 0 R /Fit]>>" % pages[0], 7)
    b.add(b"<</Title (Tool Removing) /Parent 6 0 R /Prev 7 0 R /Dest [%d 0 R /Fit]>>" % pages[2], 8)
    b.add(b"<</Title (The Tool Manual)>>", 9)
    return b.build(1, 9)


class EndToEnd(unittest.TestCase):
    def test_pdf_becomes_skills_without_third_party_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp, "manual.pdf")
            pdf.write_bytes(manual_pdf())
            out = Path(tmp, "out")
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            # -S: no site-packages, so any third-party import would fail
            res = subprocess.run([sys.executable, "-S", str(HERE / "skillforge.py"), str(pdf), "--out", str(out),
                                  "--min-commands", "2", "--prefix", "tool"],
                                 capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
            names = [c["name"] for c in catalog]
            self.assertEqual(names, ["tool-installing-packages", "tool-removing-packages"])
            md = (out / "tool-removing-packages" / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(md.startswith("---\nname: tool-removing-packages\ndescription: "))
            self.assertIn("## Procedures", md)
            self.assertIn("tool remove --force serve", md)
            self.assertIn("error: package serve is still in use", md)       # troubleshooting from output
            self.assertIn("`tool remove --force serve`", md)              # destructive command flagged
            src = (out / "tool-installing-packages" / "references" / "source-text.md").read_text(encoding="utf-8")
            self.assertIn("```console\n$ tool install left-pad", src)

    def test_module_imports_only_the_standard_library(self):
        code = ("import sys; sys.path.insert(0, %r); import skillforge; "
                "bad = [m for m in ('numpy', 'pymupdf', 'fitz', 'sklearn', 'yake', 'scipy') if m in sys.modules]; "
                "print(bad)" % str(HERE))
        res = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(res.stdout.strip(), "[]", res.stderr)


if __name__ == "__main__":
    unittest.main()
