"""Tests for yaml_lite.py, the bundled YAML reader. Expected values were checked against PyYAML."""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yaml_lite import YamlError, load  # noqa: E402


class Scalars(unittest.TestCase):
    def test_core_schema(self):
        doc = load("n: ~\nn2: null\nt: true\nf: False\ni: -12\nh: 0x1F\no: 0o17\nfl: 1.5e3\n"
                   "inf: -.inf\nver: 3.0.3\nyes: yes\nempty:\n")
        self.assertEqual(doc, {"n": None, "n2": None, "t": True, "f": False, "i": -12, "h": 31, "o": 15,
                               "fl": 1500.0, "inf": float("-inf"), "ver": "3.0.3", "yes": "yes", "empty": None})
        self.assertTrue(math.isnan(load("x: .nan")["x"]))

    def test_keys_are_strings_as_written(self):
        self.assertEqual(load("200:\n  description: OK\n'404': {description: nf}\n1.0: a\n"),
                         {"200": {"description": "OK"}, "404": {"description": "nf"}, "1.0": "a"})

    def test_quoted(self):
        doc = load("s: 'it''s'\nd: \"tab\\tnew\\nline \\u00e9 \\x41\"\nw: \"\\\"esc\\\" \\\\ back\"\n"
                   "e1: \"\"\ne2: ''\n")
        self.assertEqual(doc, {"s": "it's", "d": "tab\tnew\nline \u00e9 A", "w": '"esc" \\ back', "e1": "", "e2": ""})

    def test_multiline_flow_scalars(self):
        self.assertEqual(load("q: \"a long\n  quoted\n\n  string\"\n")["q"], "a long quoted\nstring")
        self.assertEqual(load("q: 'single\n  folded'\n")["q"], "single folded")
        self.assertEqual(load("esc: \"line\\\n  joined\"\n")["esc"], "linejoined")
        self.assertEqual(load("multi: this is\n  a long\n  plain scalar\nnext: 1\n"),
                         {"multi": "this is a long plain scalar", "next": 1})

    def test_comments_and_colons(self):
        doc = load("# c\n---\na: 1 # trailing\nb: 'x # not comment'\nurl: http://h:8080/x\n"
                   "text: don't panic\nhash: a#b\nc: 'a:'\n")
        self.assertEqual(doc, {"a": 1, "b": "x # not comment", "url": "http://h:8080/x",
                               "text": "don't panic", "hash": "a#b", "c": "a:"})

    def test_tags(self):
        self.assertEqual(load("a: !!str 123\nb: !!int '7'\nc: !!str true\n"), {"a": "123", "b": 7, "c": "true"})


class BlockScalars(unittest.TestCase):
    def test_literal_and_chomping(self):
        self.assertEqual(load("lit: |\n  line1\n  line2\n\nnext: x\n"), {"lit": "line1\nline2\n", "next": "x"})
        self.assertEqual(load("lit: |-\n  a\n  b\n\n\n")["lit"], "a\nb")
        self.assertEqual(load("lit: |+\n  a\n  b\n\n\nz: 1\n"), {"lit": "a\nb\n\n\n", "z": 1})

    def test_folded(self):
        self.assertEqual(load("fold: >\n  one\n  two\n\n  three\n    indented\n  four\n")["fold"],
                         "one two\nthree\n  indented\nfour\n")
        self.assertEqual(load("x: >\n\n  leading blank\n")["x"], "\nleading blank\n")
        self.assertEqual(load("d: |\n  Code:\n\n      indented code\n\n  done\n")["d"],
                         "Code:\n\n    indented code\n\ndone\n")

    def test_in_a_list(self):
        self.assertEqual(load("- |\n  block in list\n- >\n  folded\n  in list\n"),
                         ["block in list\n", "folded in list\n"])


class Collections(unittest.TestCase):
    def test_block(self):
        self.assertEqual(load("- a\n- b: 1\n  c: 2\n- - x\n  - y\n"), ["a", {"b": 1, "c": 2}, ["x", "y"]])
        self.assertEqual(load("key:\n- a\n- b\nother: 3\n"), {"key": ["a", "b"], "other": 3})
        self.assertEqual(load("a:\n  - b\n  -\n    c: 1\n  - \n"), {"a": ["b", {"c": 1}, None]})
        self.assertEqual(load("obj:\n  a: 1\n\n\n  b: 2\n"), {"obj": {"a": 1, "b": 2}})

    def test_flow(self):
        self.assertEqual(load("flow: [a, b,\n  c, d]\nmap: {a: 1,\n  b: [2, 3]}\nl: []\nm: {}\n"),
                         {"flow": ["a", "b", "c", "d"], "map": {"a": 1, "b": [2, 3]}, "l": [], "m": {}})
        self.assertEqual(load('json: {"a": 1, "b": [true, null, "x"]}'), {"json": {"a": 1, "b": [True, None, "x"]}})

    def test_anchors_aliases_merge(self):
        self.assertEqual(load("base: &b {x: 1, y: 2}\nderived:\n  <<: *b\n  y: 3\n"),
                         {"base": {"x": 1, "y": 2}, "derived": {"x": 1, "y": 3}})
        self.assertEqual(load("a: &anc\n  k: v\nb: *anc\nl:\n  - &x 1\n  - *x\n"),
                         {"a": {"k": "v"}, "b": {"k": "v"}, "l": [1, 1]})

    def test_documents(self):
        self.assertEqual(load("--- \n- 1\n- 2\n...\n"), [1, 2])
        self.assertEqual(load("a: 1\n---\nb: 2\n"), {"a": 1})     # first document only
        self.assertIsNone(load("# only a comment\n"))


class Errors(unittest.TestCase):
    def test_errors_name_the_line(self):
        for text, line in (("a: 1\n  b: 2\n", 2), ("a: [1, 2\n", 1), ("a: *nope\n", 1), ("a:\n\t- x\n", 2),
                           ("? complex\n", 1), ("s: \"open\n", 1)):
            with self.subTest(text=text):
                with self.assertRaises(YamlError) as cm:
                    load(text)
                self.assertEqual(cm.exception.line, line, str(cm.exception))


class OpenApiFixture(unittest.TestCase):
    def test_yaml_spec_equals_json_spec(self):
        as_yaml = load((HERE / "fixtures" / "openapi.yaml").read_text(encoding="utf-8"))
        as_json = json.loads((HERE / "fixtures" / "openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(as_yaml, as_json)


if __name__ == "__main__":
    unittest.main()
