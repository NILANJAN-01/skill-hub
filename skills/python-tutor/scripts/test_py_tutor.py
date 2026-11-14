"""Tests for py_tutor.py (standard library only)."""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import py_tutor as pt  # noqa: E402
from py_tutor_concepts import CONCEPTS, ORDER  # noqa: E402

SAMPLE = '''"""Demo module."""
import os
import json
from dataclasses import dataclass
from functools import lru_cache

API_KEY = "sk-live-123456"
DEBUG = True


def greet(name, greeting="Hello", *args, **kwargs):
    """Say hello."""
    msg = f"{greeting}, {name}"
    return msg if name else None


def bad(items=[]):
    try:
        x = 1 / 0
    except:
        pass
    for i in items:
        items.remove(i)
    if x == None:
        return [n * n for n in range(3) if n % 2]
    f = open("a.txt")
    return f


@lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def gen(n):
    for i in range(n):
        for j in range(n):
            yield i, j


def outer(n):
    def inner(x):
        return x + n
    return inner


class Animal:
    count = 0

    def __init__(self, name):
        self.name = name

    @property
    def upper(self):
        return self.name.upper()

    def __repr__(self):
        return f"Animal({self.name!r})"


@dataclass
class Point:
    x: int
    y: int = 0


class Dog(Animal):
    def speak(self):
        return super().speak() + "woof"


async def fetch(u):
    await asyncio.sleep(1)


if __name__ == "__main__":
    print(greet("ada"))
'''


class Balanced(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in ("meta", "br", "link", "input", "hr", "img"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.bad.append(tag)


def make_file(text, name="sample.py", newline="\n"):
    d = tempfile.mkdtemp(prefix="pt-test-")
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    return p


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = pt.analyze_source("sample.py", SAMPLE)
        cls.c = cls.model["concepts"]
        cls.g = {g["id"] for g in cls.model["gotchas"]}

    def test_concept_catalogue_is_complete(self):
        self.assertGreaterEqual(len(CONCEPTS), 70)
        for cid in ORDER:
            row = CONCEPTS[cid]
            for k in ("title", "what", "why", "pitfall", "example", "q", "a"):
                self.assertTrue(row[k].strip(), (cid, k))
            self.assertIn(row["level"], (1, 2, 3))

    def test_beginner_to_advanced_concepts_found(self):
        for cid in ("variables", "f-strings", "conditionals", "for-loops", "functions", "imports", "exceptions",
                    "comprehensions", "default-args", "args-kwargs", "classes", "inheritance", "property", "dunder-methods",
                    "memoization", "generators", "closures", "dataclasses", "async-await", "main-guard", "recursion",
                    "ternary", "range", "type-hints", "docstrings", "file-io"):
            self.assertIn(cid, self.c, cid)

    def test_no_false_positives(self):
        for cid in ("metaclasses", "descriptors", "walrus", "pattern-matching", "bitwise", "regex", "slots"):
            self.assertNotIn(cid, self.c, cid)

    def test_gotchas(self):
        for gid in ("mutable-default", "bare-except", "swallowed", "eq-none", "open-no-with", "hard-coded-secret",
                    "mutate-while-iterating"):
            self.assertIn(gid, self.g, gid)

    def test_secret_value_is_hidden(self):
        shown = "\n".join(self.model["source_lines"])
        self.assertNotIn("sk-live-123456", shown)
        self.assertIn("API_KEY", shown)
        html = pt.render_html(self.model, pt.new_notes(self.model))
        self.assertNotIn("sk-live-123456", html)

    def test_blocks(self):
        ids = [b["id"] for b in self.model["blocks"]]
        for want in ("function:greet", "function:fib", "class:Animal", "method:Animal.upper", "method:Dog.speak",
                     "class:Point", "main-guard@" + str(next(b["start"] for b in self.model["blocks"] if b["kind"] == "main-guard"))):
            self.assertIn(want, ids)
        self.assertEqual(len(ids), len(set(ids)))
        kinds = {b["id"]: b for b in self.model["blocks"]}
        self.assertEqual(kinds["function:gen"]["loop_depth"], 2)
        self.assertGreaterEqual(kinds["function:bad"]["complexity"], 5)
        self.assertIn("recursion", kinds["function:fib"]["concepts"])
        self.assertIn("big-o", kinds["function:gen"]["concepts"])
        # class block covers the header only; the methods are their own blocks
        self.assertLess(kinds["class:Animal"]["end"], kinds["method:Animal.upper"]["start"])

    def test_level(self):
        self.assertEqual(self.model["level"], "Advanced")      # generators, dataclasses, async, memoization
        self.assertEqual(pt.analyze_source("a.py", "x = 1\nprint(x)\n")["level"], "Beginner")

    @unittest.skipIf(sys.version_info < (3, 10), "match needs 3.10+")
    def test_match_statement(self):
        m = pt.analyze_source("m.py", "def f(c):\n    match c:\n        case 1:\n            return 2\n")
        self.assertIn("pattern-matching", m["concepts"])

    def test_bit_or_on_sets_is_not_bitwise(self):
        m = pt.analyze_source("s.py", "a = {1}\nb = {2}\nc = a | b\nd = 5 & 3\n")
        self.assertEqual(m["concepts"]["bitwise"], [4])

    def test_syntax_error_is_reported_not_raised(self):
        m = pt.analyze_source("old.py", "print 'hello'\n")
        self.assertEqual(m["error"]["line"], 1)
        self.assertIn("Python 2", m["error"]["hint"])
        page = pt.render_html(m, pt.new_notes(m))
        self.assertIn("Could not parse", page)

    def test_crlf_and_encoding_declaration(self):
        p = make_file("# -*- coding: latin-1 -*-\nname = 'caf\u00e9'\nprint(name)\n", newline="\r\n")
        with open(p, "rb") as fh:
            raw = fh.read().replace("café".encode("utf-8"), "café".encode("latin-1"))
        with open(p, "wb") as fh:
            fh.write(raw)
        m = pt.analyze_source("l.py", pt.read_py(p))
        self.assertIsNone(m["error"])
        self.assertIn("café", "\n".join(m["source_lines"]))


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.src = make_file(SAMPLE)
        self.out = tempfile.mkdtemp(prefix="pt-out-")
        with redirect_stdout(io.StringIO()):
            pt.main(["analyze", self.src, "--out", self.out])

    def path(self, name):
        return os.path.join(self.out, name)

    def load(self, name):
        with open(self.path(name), encoding="utf-8") as fh:
            return json.load(fh)

    def page(self):
        with open(self.path("sample.html"), encoding="utf-8") as fh:
            return fh.read()

    def test_files_written(self):
        for n in ("sample.model.json", "sample.notes.json", "sample.html"):
            self.assertTrue(os.path.isfile(self.path(n)), n)
        self.assertFalse(os.path.isfile(self.path("index.html")))      # single file: no index

    def test_html_structure(self):
        page = self.page()
        b = Balanced()
        b.feed(page)
        self.assertEqual((b.stack, b.bad), ([], []))
        for needle in ("Walkthrough", "Concepts used in this file", "Gotchas", "Interview questions", "Also revise",
                       "Fundamentals checklist", 'data-n="1"'):
            self.assertIn(needle, page)
        self.assertNotRegex(page, r"https?://|<link |src=")            # self-contained
        self.assertEqual(page.count("<script>"), 1)

    def test_check_render_cycle(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pt.main(["check", self.out]), 1)
        notes = self.load("sample.notes.json")
        self.assertIn("Imports other modules", notes["blocks"]["imports@2"]["explanation"])      # auto-filled
        notes["summary"] = "Demo file <b>with</b> markup & `code`."
        for bid, v in notes["blocks"].items():
            if pt.TODO in v["explanation"]:
                v["explanation"] = "Explains **this** block <script>alert(1)</script>."
        notes["blocks"]["function:greet"]["lines"] = {"12": "Builds the message with an f-string."}
        notes["blocks"]["function:greet"]["deeper"] = "f-strings call `format` on each value."
        notes["interview_questions"] = [{"level": 3, "q": "Why is my custom question here?", "a": "Because."}]
        notes["exercises"] = ["Add type hints."]
        with open(self.path("sample.notes.json"), "w", encoding="utf-8") as fh:
            json.dump(notes, fh)
        with redirect_stdout(io.StringIO()):
            pt.main(["render", self.out])
            self.assertEqual(pt.main(["check", self.out]), 0)
        page = self.page()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Builds the message with an f-string.", page)
        self.assertIn("Going deeper", page)
        self.assertIn("Why is my custom question here?", page)
        self.assertIn("<code>code</code>", page)
        self.assertIn("Add type hints.", page)

    def test_reanalyze_keeps_notes(self):
        notes = self.load("sample.notes.json")
        notes["summary"] = "Keep me."
        with open(self.path("sample.notes.json"), "w", encoding="utf-8") as fh:
            json.dump(notes, fh)
        with redirect_stdout(io.StringIO()):
            pt.main(["analyze", self.src, "--out", self.out])
        self.assertEqual(self.load("sample.notes.json")["summary"], "Keep me.")

    def test_folder_makes_index(self):
        d = tempfile.mkdtemp(prefix="pt-dir-")
        os.makedirs(os.path.join(d, "pkg", "__pycache__"))
        for rel, text in (("a.py", "x = 1\n"), ("pkg/b.py", "def f():\n    return 1\n"), ("pkg/__pycache__/c.py", "x=1\n"),
                          ("notes.txt", "hi")):
            with open(os.path.join(d, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
        out = tempfile.mkdtemp(prefix="pt-out2-")
        with redirect_stdout(io.StringIO()):
            pt.main(["analyze", d, "--out", out])
        names = set(os.listdir(out))
        self.assertIn("index.html", names)
        self.assertIn("a.html", names)
        self.assertIn("pkg__b.html", names)
        self.assertFalse(any("c.html" in n for n in names))

    def test_bad_inputs_exit(self):
        with self.assertRaises(SystemExit):
            pt.main(["analyze", os.path.join(tempfile.gettempdir(), "no-such-file-xyz.py")])
        with self.assertRaises(SystemExit):
            pt.main(["render", tempfile.mkdtemp()])


if __name__ == "__main__":
    unittest.main()
