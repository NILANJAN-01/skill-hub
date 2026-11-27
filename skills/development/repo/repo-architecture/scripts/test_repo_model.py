"""Tests for repo_model.py, the shared engine (standard library only)."""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_model as rm  # noqa: E402

FAKE_KEY = "Zx9" + "Qw81Lm2Kp7Vb4T"          # built at run time so secret scanners ignore this file
FAKE_AWS = "AKIA" + "QWERTYUIOPASDFGH"

FILES = {
    "README.md": "# Demo\n\nA small polyglot demo.\n",
    "requirements.txt": "requests\nflask>=2\n",
    "config.yaml": 'api_key: "%s"\nname: "time-random-math"\n' % FAKE_KEY,
    "app/main.py": ("import requests\nfrom core.engine import run\n\n\ndef main():\n    cfg = load()\n    run(cfg)\n\n\n"
                    "def load():\n    return {}\n\n\nif __name__ == '__main__':\n    main()\n"),
    "core/__init__.py": "",
    "core/engine.py": ("from lib.db import save\n\n\ndef run(cfg):\n    data = transform(cfg)\n    save(data)\n\n\n"
                       "def transform(x):\n    try:\n        return x\n    except:\n        pass\n\n\n"
                       "def _unused_helper():\n    return 1\n"),
    "lib/db.py": ("import sqlite3\n\n\ndef save(data):\n    c = sqlite3.connect('x')\n"
                  "    c.execute(\"SELECT * FROM t WHERE id=\" + data)\n"),
    "csrc/main.c": ("#include <stdio.h>\n#include \"util.h\"\n\n/* main entry */\nint main(int argc, char **argv) {\n"
                    "    char buf[10];\n    gets(buf);\n    helper(buf);\n    return 0;\n}\n"),
    "csrc/util.h": "void helper(char *s);\n",
    "csrc/util.c": ("#include \"util.h\"\n#include <string.h>\n\nstatic int\ncount(char *s)\n{\n    return strlen(s);\n}\n\n"
                    "void helper(char *s) {\n    count(s);\n}\n"),
    "cpp/widget.cpp": ("#include \"widget.hpp\"\n\nWidget::Widget(int a) : x_(a), y_{2} {\n    init();\n}\n\n"
                       "void Widget::init() {\n    draw();\n}\n\nvoid Widget::draw() const {\n}\n"),
    "cpp/widget.hpp": "class Widget {\npublic:\n    Widget(int a);\n    void init();\n    void draw() const;\n};\n",
    "jv/src/main/java/com/demo/App.java": ("package com.demo;\nimport com.demo.svc.Service;\n\npublic class App {\n"
                                           "    public static void main(String[] args) {\n"
                                           "        Service s = new Service();\n        s.start();\n    }\n}\n"),
    "jv/src/main/java/com/demo/svc/Service.java": ("package com.demo.svc;\n\npublic class Service {\n"
                                                   "    public Service() {}\n    public void start() {\n"
                                                   "        try { work(); } catch (Exception e) {}\n    }\n"
                                                   "    private void work() {\n        String q = \"x\";\n    }\n}\n"),
    "kt/Main.kt": ("package demo.kt\n\nfun main() {\n    val r = Repo()\n    r.load()\n    greet(\"x\")\n}\n\n"
                   "fun greet(n: String) = println(n)\n\nclass Repo @Inject constructor() {\n"
                   "    fun load(): Int {\n        return parse()\n    }\n    private fun parse() = 1\n}\n"),
    "gosrc/go.mod": "module example.com/demo\n\ngo 1.21\n",
    "gosrc/main.go": ("package main\n\nimport (\n    \"fmt\"\n    \"example.com/demo/store\"\n)\n\nfunc main() {\n"
                      "    s := store.New()\n    s.Put(\"a\")\n    fmt.Println(\"ok\")\n}\n"),
    "gosrc/store/store.go": ("package store\n\ntype Store struct{}\n\nfunc New() *Store { return &Store{} }\n\n"
                             "func (s *Store) Put(k string) {\n    s.flush()\n}\n\n"
                             "func (s *Store) flush() {\n    if err != nil {}\n}\n"),
    "web/index.ts": ("import { api } from './api';\n\nexport async function boot(): Promise<void> {\n"
                     "  const r = await api('/x');\n  render(r);\n}\n\nconst render = (x: any) => {\n"
                     "  console.log(x);\n};\n\nboot();\n"),
    "web/api.ts": "import axios from 'axios';\nexport const api = async (u: string) => {\n  return axios.get(u);\n};\n",
    "rs/Cargo.toml": "[package]\nname = \"demo\"\n\n[dependencies]\nserde = \"*\"\n",
    "rs/src/main.rs": "mod util;\nuse crate::util::Thing;\n\nfn main() {\n    let t = Thing::new();\n    t.go();\n}\n",
    "rs/src/util.rs": ("pub struct Thing;\nimpl Thing {\n    pub fn new() -> Self { Thing }\n"
                       "    pub fn go(&self) { helper_fn(); }\n}\nfn helper_fn() {}\n\n"
                       "#[cfg(test)]\nmod tests {\n    use super::*;\n}\n"),
    "cs/Program.cs": ("using System;\nnamespace Demo {\n  class Program {\n    static void Main(string[] args) {\n"
                      "      var w = new Worker();\n      w.DoWork();\n    }\n  }\n  class Worker {\n"
                      "    public void DoWork() => Console.WriteLine(\"x\");\n  }\n}\n"),
    "tests/test_engine.py": "from core.engine import run\n\n\ndef test_run():\n    run({})\n",
    "tests/fixture_secret.py": "TOKEN = '%s'\n" % FAKE_AWS,
    ".env": "SECRET=abc\n",
}


def make_repo(files=FILES):
    d = tempfile.mkdtemp(prefix="rm-test-")
    for rel, text in files.items():
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return d


class LexerTests(unittest.TestCase):
    def test_comments_and_strings_are_blanked_keeping_offsets(self):
        src = 'int a = 1; // call(x)\nchar *s = "foo(bar)"; /* x(\n y */ z();\n'
        code, bare, comments, _ = rm.lex(src, "C")
        self.assertEqual(len(code), len(src))
        self.assertEqual(len(bare), len(src))
        self.assertNotIn("call", code)
        self.assertIn('"foo(bar)"', code)
        self.assertNotIn("foo", bare)
        self.assertIn("z();", bare)
        self.assertEqual(len(comments), 2)

    def test_rust_lifetimes_and_raw_strings(self):
        src = 'fn f<\'a>(x: &\'a str) -> &\'a str { let r = r#"say "hi"(x)"#; g(x) }\n'
        _, bare, _, _ = rm.lex(src, "Rust")
        self.assertIn("g(x)", bare)
        self.assertNotIn("say", bare)

    def test_python_docstrings_count_as_documentation(self):
        _, _, comments, doc = rm.lex('"""Module doc\nline two"""\nx = 1  # note\n', "Python")
        self.assertEqual(doc, 2)
        self.assertEqual(len(comments), 1)


class ParserTests(unittest.TestCase):
    def names(self, lang, text):
        return {(d["cls"], d["name"]) for d in rm.parse_file(lang, text)["defs"] if not d.get("pseudo")}

    def test_cpp_definitions(self):
        defs = self.names("C++", FILES["cpp/widget.cpp"])
        self.assertEqual(defs, {("Widget", "Widget"), ("Widget", "init"), ("Widget", "draw")})

    def test_c_gnu_style_and_static(self):
        P = rm.parse_file("C", FILES["csrc/util.c"])
        by = {d["name"]: d for d in P["defs"]}
        self.assertEqual(set(by), {"count", "helper"})
        self.assertFalse(by["count"]["public"])
        self.assertEqual([c[0] for c in by["helper"]["calls"]], ["count"])

    def test_java_kotlin_go_rust_csharp_ts(self):
        self.assertIn(("Service", "work"), self.names("Java", FILES["jv/src/main/java/com/demo/svc/Service.java"]))
        kt = self.names("Kotlin", FILES["kt/Main.kt"])
        self.assertIn(("Repo", "parse"), kt)
        self.assertIn((None, "greet"), kt)
        self.assertIn(("Store", "Put"), self.names("Go", FILES["gosrc/store/store.go"]))
        self.assertIn(("Thing", "go"), self.names("Rust", FILES["rs/src/util.rs"]))
        self.assertIn(("Worker", "DoWork"), self.names("C#", FILES["cs/Program.cs"]))
        self.assertEqual(self.names("TypeScript", FILES["web/index.ts"]), {(None, "boot"), (None, "render")})

    def test_python_ast_and_python2_fallback(self):
        P = rm.parse_file("Python", FILES["app/main.py"])
        self.assertTrue(any(d.get("pseudo") == "main" for d in P["defs"]))
        P2 = rm.parse_file("Python", "def old():\n    print 'hi'\n    helper()\n")
        self.assertTrue(P2.get("syntax_error"))
        self.assertEqual(P2["defs"][0]["name"], "old")

    def test_imports_per_language(self):
        specs = lambda lang, rel: [i["spec"] for i in rm.parse_file(lang, FILES[rel])["imports"]]  # noqa: E731
        self.assertEqual(specs("Go", "gosrc/main.go"), ["fmt", "example.com/demo/store"])
        self.assertIn("util.h", specs("C", "csrc/main.c"))
        self.assertEqual(specs("TypeScript", "web/index.ts"), ["./api"])
        self.assertIn("crate::util::Thing", specs("Rust", "rs/src/main.rs"))


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = make_repo()
        cls.model = rm.analyze(cls.root, name="demo", flows=10)
        cls.comps = {c["id"]: c for c in cls.model["components"]}
        cls.flows = {f["entry"]["file"]: f for f in cls.model["flows"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_components_and_edges(self):
        edges = {(e["from"], e["to"]) for e in self.model["edges"]}
        self.assertIn(("app", "core"), edges)
        self.assertIn(("core", "lib"), edges)
        self.assertEqual(self.comps["tests"]["kind"], "tests")
        self.assertEqual(self.comps["jv/src/main/java/com/demo"]["kind"], "source")
        self.assertFalse(self.comps["tests"]["hld"])
        self.assertEqual(self.comps["lib"]["tier"], 2)

    def test_flows_in_every_language(self):
        calls = lambda f: [s["call"] for s in self.flows[f]["steps"]]  # noqa: E731
        self.assertEqual(calls("app/main.py"), ["main()", "load()", "run()", "transform()", "save()"])
        self.assertEqual(calls("gosrc/main.go"), ["New()", "Store.Put()", "Store.flush()"])
        self.assertEqual(calls("jv/src/main/java/com/demo/App.java"),
                         ["Service.Service()", "Service.start()", "Service.work()"])
        self.assertEqual(calls("kt/Main.kt"), ["Repo.load()", "Repo.parse()", "greet()"])
        self.assertEqual(calls("csrc/main.c"), ["helper()", "count()"])
        self.assertEqual(calls("rs/src/main.rs"), ["Thing.new()", "Thing.go()", "helper_fn()"])
        self.assertEqual(calls("cs/Program.cs"), ["Worker.DoWork()"])
        self.assertEqual(calls("web/index.ts"), ["boot()", "api()", "render()"])

    def test_flow_participants_are_components(self):
        f = self.flows["app/main.py"]
        self.assertEqual([p["label"] for p in f["participants"]], ["app", "core", "lib"])
        self.assertEqual(f["actor"], "Command-line user")

    def test_external_systems(self):
        systems = {s["label"]: s["used_by"] for s in self.model["systems"]}
        self.assertEqual(systems["SQL database"], ["lib"])
        self.assertIn("HTTP APIs", systems)

    def test_findings(self):
        got = {(f["rule"], f["file"]) for f in self.model["findings"]}
        for want in [("SEC001", "config.yaml"), ("SEC002", ".env"), ("SEC006", "csrc/main.c"),
                     ("SEC009", "lib/db.py"), ("COD004", "core/engine.py"), ("COD004", "gosrc/store/store.go"),
                     ("COD004", "jv/src/main/java/com/demo/svc/Service.java"), ("DEP003", "rs/Cargo.toml"),
                     ("DEP001", "requirements.txt"), ("DES003", "core/engine.py"), ("DOC003", "")]:
            self.assertIn(want, got)
        secrets = [f for f in self.model["findings"] if f["rule"] == "SEC001"]
        self.assertTrue(all(FAKE_KEY not in f["msg"] and FAKE_AWS not in f["msg"] for f in secrets))
        self.assertFalse(any("time-random" in f["msg"] for f in secrets))
        test_secret = [f for f in secrets if f["file"] == "tests/fixture_secret.py"]
        self.assertEqual(test_secret[0]["sev"], "MEDIUM")

    def test_sensitive_file_never_read(self):
        env = next(f for f in self.model["files"] if f["path"] == ".env")
        self.assertEqual((env["status"], env["reason"]), ("skip", "sensitive"))

    def test_health_and_dismissals(self):
        h = rm.health(self.model)
        self.assertLess(h["areas"]["security"], 100)
        self.assertEqual(h["grade"], "A" if h["score"] >= 90 else h["grade"])
        rules = {f["rule"] for f in h["active"]}
        dismissed = {r: "accepted" for r in rules}
        h2 = rm.health(self.model, dismissed)
        self.assertEqual(h2["score"], 100)
        self.assertEqual(len(h2["active"]), 0)
        one = next(f for f in self.model["findings"] if f["rule"] == "SEC009")
        h3 = rm.health(self.model, {"SEC009@%s:%d" % (one["file"], one["line"]): "constant"})
        self.assertGreater(h3["areas"]["security"], h["areas"]["security"])

    def test_mermaid_hld_structure(self):
        text = rm.hld_mermaid(self.model)
        lines = text.splitlines()
        self.assertEqual(lines[0], "flowchart TB")
        self.assertEqual(sum(l.strip().startswith("subgraph") for l in lines), sum(l.strip() == "end" for l in lines))
        ids = set(re.findall(r"^\s+(C\d+|X\d+|A\d+)[\[\(\{]", text, re.M))
        for a, b in re.findall(r"^\s+(\w+) [-=.]+> (\w+)$", text, re.M):
            self.assertIn(a, ids)
            self.assertIn(b, ids)
        self.assertNotIn('"C#', text)   # '#' is escaped as an entity

    def test_mermaid_sequence_escapes(self):
        flow = {"actor": "HTTP client", "participants": [{"key": "a", "label": "a;b#c"}],
                "entry": {"label": "x: y", "p": 0}, "steps": [], "truncated": True}
        text = rm.flow_mermaid(flow)
        self.assertIn("participant P0 as a#59;b#35;c", text)
        self.assertIn("U->>P0: x#58; y", text)
        self.assertIn("Note over P0", text)


class HeuristicTests(unittest.TestCase):
    def test_unique_names(self):
        n = rm.unique_names(["gson/src/main/java/com/google/gson", "extras/src/main/java/com/google/gson",
                             "app/src/main/java/x/todo", "app/src/debug/java/x/todo", "", "lib"])
        self.assertEqual(n["gson/src/main/java/com/google/gson"], "gson")
        self.assertEqual(n["extras/src/main/java/com/google/gson"], "extras/gson")
        self.assertEqual(n["app/src/debug/java/x/todo"], "app/debug/todo")
        self.assertEqual(n[""], "(root)")
        self.assertEqual(len(set(n.values())), len(n))

    def test_secret_filter(self):
        self.assertFalse(rm._secret_ok("time-random-math"))
        self.assertFalse(rm._secret_ok("your-api-key-here"))
        self.assertTrue(rm._secret_ok(FAKE_KEY))

    def test_flat_project_splits_into_files(self):
        root = make_repo({"a.py": "import b\n", "b.py": "import c\n", "c.py": "x = 1\n", "README.md": "# x\n"})
        try:
            infos, _, _ = rm.collect(root)
            comp_of, comps = rm.build_components(infos)
            self.assertEqual(comp_of["a.py"], "a.py")
            comp_of, _ = rm.build_components(infos, granularity="folder")
            self.assertEqual(comp_of["a.py"], "")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_flow_prefers_breadth(self):
        defs = [{"name": n, "cls": None, "file": "f.py", "line": i + 1} for i, n in enumerate("abcdefg")]
        graph = [[(1, 1), (2, 2), (3, 3)], [(4, 1), (5, 2), (6, 3)], [], [], [], [], []]
        flow = rm._make_flow({"i": 0, "kind": "main", "label": None, "reach": 6}, defs, graph,
                             {"f.py": ""}, {"": {"name": "(root)"}}, 4)
        self.assertEqual([s["call"] for s in flow["steps"]], ["b()", "e()", "c()", "d()"])
        self.assertTrue(flow["truncated"])


if __name__ == "__main__":
    unittest.main()
