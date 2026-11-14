"""Tests for repo_architecture.py (standard library only)."""
import io
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_architecture as ra  # noqa: E402

FILES = {
    "README.md": "# Demo\n",
    "package.json": json.dumps({"scripts": {"build": "tsc"}, "dependencies": {"react": "1"}}),
    "requirements.txt": "requests>=2\nflask\n",
    "Makefile": "test:\n\tpython -m unittest\n",
    ".env": "import secret_thing\nTOKEN=abc\n",
    "app/main.py": "import requests\nfrom core import engine\nfrom lib.db import connect\n",
    "core/__init__.py": "",
    "core/engine.py": "from . import util\nfrom lib import db\nimport os\n",
    "core/util.py": "X = 1\n",
    "lib/db.py": "def connect():\n    pass\n",
    "tests/test_engine.py": "from core.engine import run\n",
    "web/src/index.ts": "import React from 'react';\nimport { x } from '../../shared/x';\nimport './util';\n",
    "web/src/util.ts": "export const u = 1;\n",
    "shared/x.ts": "export const x = 1;\n",
    "src/api/Server.java": "package com.demo.api;\nimport com.demo.model.User;\nimport java.util.List;\nimport org.apache.Foo;\n",
    "src/model/User.java": "package com.demo.model;\npublic class User {}\n",
}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def make_repo():
    d = tempfile.mkdtemp(prefix="ra-test-")
    for rel, text in FILES.items():
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = make_repo()
        cls.model = ra.analyze_repo(cls.root)
        cls.edges = {(e["from"], e["to"]) for e in cls.model["edges"]}
        cls.names = {c["name"] for c in cls.model["components"]}

    def test_components(self):
        for n in ("app", "core", "lib", "tests", "web", "shared", "src/api", "src/model"):
            self.assertIn(n, self.names)

    def test_python_edges(self):
        self.assertIn(("app", "core"), self.edges)
        self.assertIn(("app", "lib"), self.edges)
        self.assertIn(("core", "lib"), self.edges)
        self.assertIn(("tests", "core"), self.edges)
        self.assertNotIn(("core", "core"), self.edges)       # relative import stays inside the component

    def test_js_and_java_edges(self):
        self.assertIn(("web", "shared"), self.edges)
        self.assertNotIn(("web", "web"), self.edges)
        self.assertIn(("src/api", "src/model"), self.edges)

    def test_externals(self):
        ext = {x["name"] for x in self.model["externals"]}
        self.assertIn("requests", ext)
        self.assertIn("react", ext)
        self.assertNotIn("os", ext)
        self.assertNotIn("java.util", ext)

    def test_sensitive_file_skipped(self):
        self.assertNotIn(".env", {f for c in self.model["components"] for f in c["key_files"]})
        self.assertNotIn("secret_thing", {x["name"] for x in self.model["externals"]})
        self.assertEqual(self.model["files"], len(FILES) - 1)

    def test_facts(self):
        cmds = {c["command"] for c in self.model["commands"]}
        self.assertIn("npm run build", cmds)
        self.assertIn("make test", cmds)
        pk = {p for d in self.model["dependencies"] for p in d["packages"]}
        self.assertTrue({"react", "requests", "flask"} <= pk)
        self.assertIn("app/main.py", self.model["entry_points"])
        self.assertEqual(self.model["docs"], ["README.md"])

    def test_kinds_and_layers(self):
        kinds = {c["name"]: c["kind"] for c in self.model["components"]}
        self.assertEqual(kinds["tests"], "tests")
        self.assertEqual(kinds["core"], "source")
        layers = self.model["layers"]
        self.assertLess(layers["app"], layers["core"])
        self.assertLess(layers["core"], layers["lib"])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        self.out = tempfile.mkdtemp(prefix="ra-out-")
        with redirect_stdout(io.StringIO()):
            ra.main(["analyze", self.root, "--out", self.out])

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as fh:
            return fh.read()

    def test_outputs_exist(self):
        for n in ("model.json", "annotations.json", "ARCHITECTURE.md", "architecture.html"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, n)), n)

    def test_markdown_has_mermaid_and_sections(self):
        md = self.read("ARCHITECTURE.md")
        self.assertIn("```mermaid\nflowchart TD", md)
        for h in ("## Overview", "## Components", "## Walkthrough", "## Main flows", "## Build, run and test"):
            self.assertIn(h, md)
        self.assertRegex(md, r"n\d+ -->\|\d+\| n\d+")

    def test_html_is_self_contained_and_svg_parses(self):
        page = self.read("architecture.html")
        self.assertNotRegex(page, r"<script|https?://(?!www\.w3\.org)")
        svg = re.search(r"<svg.*?</svg>", page, re.S).group(0)
        ET.fromstring(svg)                                  # well-formed XML
        self.assertIn("app", svg)

    def test_check_then_render_after_annotating(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ra.main(["check", self.out]), 1)
        path = os.path.join(self.out, "annotations.json")
        ann = load(path)
        ann["summary"] = "Demo <b>app</b> & friends"
        for v in ann["components"].values():
            v["description"] = "Does a thing <script>alert(1)</script>"
        ann["flows"] = [{"title": "Request", "steps": ["app calls core", "core reads lib"]}]
        save(path, ann)
        with redirect_stdout(io.StringIO()):
            ra.main(["render", self.out])
            self.assertEqual(ra.main(["check", self.out]), 0)
        page = self.read("architecture.html")
        self.assertNotIn("<script>alert", page)             # escaped
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Request", self.read("ARCHITECTURE.md"))

    def test_render_keeps_existing_descriptions(self):
        path = os.path.join(self.out, "annotations.json")
        ann = load(path)
        ann["components"]["core"]["description"] = "The engine."
        save(path, ann)
        with redirect_stdout(io.StringIO()):
            ra.main(["render", self.out])
        self.assertIn("The engine.", self.read("ARCHITECTURE.md"))


def build(files):
    d = tempfile.mkdtemp(prefix="ra-t-")
    for rel, text in files.items():
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return d


class OtherLayouts(unittest.TestCase):
    def edges(self, model):
        return {(e["from"], e["to"]) for e in model["edges"]}

    def test_flat_package_is_split_into_files(self):
        files = {f"pkg/m{i}.py": ("from pkg import m0\n" if i else "X = 1\n") for i in range(6)}
        files["pkg/__init__.py"] = ""
        model = ra.analyze_repo(build(files))
        names = {c["name"] for c in model["components"]}
        self.assertIn("pkg/m3.py", names)
        self.assertIn(("pkg/m3.py", "pkg/m0.py"), self.edges(model))

    def test_granularity_folder_never_splits(self):
        files = {f"pkg/m{i}.py": "X = 1\n" for i in range(8)}
        model = ra.analyze_repo(build(files), granularity="folder")
        self.assertEqual(model["split_files"], 0)

    def test_big_folder_is_opened(self):
        files = {}
        for sub in ("api", "db", "ui"):
            for i in range(6):
                files[f"app/src/main/java/com/acme/{sub}/F{i}.kt"] = "package com.acme.%s\nclass F%d\n" % (sub, i)
        files["app/src/main/java/com/acme/api/Server.kt"] = "package com.acme.api\nimport com.acme.db.F1\n"
        files["other/a.py"] = "x=1\n"
        files["lib/b.py"] = "x=1\n"
        model = ra.analyze_repo(build(files))
        names = {c["name"] for c in model["components"]}
        self.assertTrue(any(n.endswith("/com/acme/db") for n in names), names)
        self.assertTrue(any(a.endswith("/api") and b.endswith("/db") for a, b in self.edges(model)))

    def test_rust_modules(self):
        rust = {"Cargo.toml": "[dependencies]\nserde = '1'\n",
                "src/main.rs": "mod exec;\nuse crate::fmt::out;\nuse serde::Serialize;\n",
                "src/exec/mod.rs": "use crate::fmt::out;\n", "src/fmt/mod.rs": "pub fn out() {}\n"}
        for i in range(4):
            rust[f"src/exec/e{i}.rs"] = "fn f() {}\n"
            rust[f"src/fmt/f{i}.rs"] = "fn f() {}\n"
        m = ra.analyze_repo(build(rust))
        self.assertIn(("src/exec", "src/fmt"), self.edges(m))
        self.assertIn(("src", "src/exec"), self.edges(m))
        self.assertIn("serde", {x["name"] for x in m["externals"]})

    def test_go_packages(self):
        go = {"go.mod": "module example.com/app\n\ngo 1.21\n",
              "cmd/app/main.go": 'package main\nimport (\n\t"fmt"\n\t"example.com/app/internal/store"\n\t"github.com/spf13/cobra"\n)\n',
              "internal/store/s.go": "package store\n", "internal/web/w.go": "package web\n"}
        m = ra.analyze_repo(build(go))
        self.assertIn(("cmd/app", "internal/store"), self.edges(m))
        self.assertIn("github.com/spf13/cobra", {x["name"] for x in m["externals"]})

    def test_docs_only_repo_still_renders(self):
        m = ra.analyze_repo(build({"README.md": "# x\n", "docs/a.md": "a\n"}))
        self.assertEqual(m["edges"], [])
        self.assertTrue(ra.render_html(m, ra.new_annotations(m)).startswith("<!doctype html>"))

    def test_entry_points_skip_tests_and_examples(self):
        m = ra.analyze_repo(build({"main.py": "x=1\n", "tests/main.py": "x=1\n", "examples/app.py": "x=1\n"}))
        self.assertEqual(m["entry_points"], ["main.py"])


class SmallPieces(unittest.TestCase):
    def test_shown_caps_nodes(self):
        comps = [{"name": f"c{i}", "kind": "source", "files": 1, "lines": i, "language": "", "key_files": []} for i in range(50)]
        model = {"components": comps, "edges": []}
        self.assertEqual(len(ra.shown(model)), ra.MAX_NODES)

    def test_bad_source_exits(self):
        with self.assertRaises(SystemExit):
            ra.main(["analyze", os.path.join(tempfile.gettempdir(), "definitely-not-here-xyz")])


if __name__ == "__main__":
    unittest.main()
