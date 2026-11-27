import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE))
import llm_sec  # noqa: E402


def cli(*args):
    r = subprocess.run([sys.executable, str(HERE / "llm_sec.py"), *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def found(*args):
    code, out = cli(*args, "--json")
    return code, [(f["rule"], Path(f["path"]).name, f["line"]) for f in json.loads(out)["findings"]]


class Scan(unittest.TestCase):
    def test_model_output_reaching_sinks(self):
        code, got = found("scan", FIX / "vulnerable_app.py")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(got), [("llm-output-to-sink", "vulnerable_app.py", 13),
                                       ("llm-output-to-sink", "vulnerable_app.py", 14),
                                       ("llm-output-to-sink", "vulnerable_app.py", 15),
                                       ("user-input-in-system-prompt", "vulnerable_app.py", 10)])

    def test_safe_patterns_pass(self):
        # fixed system prompt, delimited user text, JSON + allowlist, parameterised SQL, eval of a constant
        self.assertEqual(found("scan", FIX / "safe_app.py"), (0, []))

    def test_javascript(self):
        _, got = found("scan", FIX / "chat.js")
        self.assertEqual(sorted(r for r, _, _ in got),
                         ["llm-output-to-sink", "user-input-in-system-prompt", "user-input-in-system-prompt"])

    def test_prompt_text(self):
        _, got = found("scan", FIX / "system_prompt.txt")
        self.assertEqual(sorted(r for r, _, _ in got), ["confidential-prompt", "secret-in-prompt"])

    def test_missing_path(self):
        self.assertEqual(cli("scan", "no/such/dir")[0], 2)


class Imports(unittest.TestCase):
    def test_unknown_imports_offline(self):
        code, got = found("imports", FIX / "gen")
        self.assertEqual(code, 1)
        names = sorted(n for _, n, _ in got)
        self.assertEqual(names, ["gen.js", "gen.js", "generated.py", "generated.py"])
        _, out = cli("imports", FIX / "gen")
        for bad in ("fastjsonparse_ultra", "totally_made_up_pkg_4471", "left-pad-turbo-x9", "@acme/not-real-sdk"):
            self.assertIn(bad, out)
        for ok in ("'requests'", "'helpers'", "'express'", "'fs'", "'json'", "'path'"):
            self.assertNotIn(ok, out)                  # declared, local, builtin or stdlib

    def test_parsers(self):
        self.assertEqual(llm_sec.py_imports("import a.b, c as d\nfrom e.f import g\n  import h\n"),
                         [(1, "a"), (1, "c"), (2, "e"), (3, "h")])
        self.assertEqual([m for _, m in llm_sec.js_imports(
            'import x from "@s/p/deep";\nconst y = require("q/r");\nimport("./rel");\nimport "side";\n')],
            ["@s/p", "q", "side"])

    def test_alias_maps_import_to_distribution(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "requirements.txt").write_text("PyYAML>=6\nbeautifulsoup4\n", encoding="utf-8")
            Path(d, "app.py").write_text("import yaml\nimport bs4\n", encoding="utf-8")
            self.assertEqual(found("imports", d, "--root", d), (0, []))


class Probe(unittest.TestCase):
    def probe(self, model):
        cmd = f'"{sys.executable}" "{FIX / model}"'
        code, out = cli("probe", "--template", FIX / "app_prompt.txt", "--cmd", cmd, "--json")
        return code, json.loads(out)

    def test_naive_model_is_hijacked_and_leaks(self):
        code, res = self.probe("naive_model.py")
        self.assertEqual(code, 1)
        won = {r["attack"] for r in res["attacks"] if r["succeeded"]}
        self.assertIn("override", won)
        self.assertIn("encoded", won)
        self.assertIn("leak-direct", won)              # the canary came back

    def test_robust_model_blocks_everything(self):
        code, res = self.probe("robust_model.py")
        self.assertEqual((code, res["succeeded"]), (0, 0))
        self.assertEqual(len(res["attacks"]), 12)

    def test_export_and_bad_template(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "cases.jsonl")
            self.assertEqual(cli("probe", "--export", out)[0], 0)
            rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 12)
            self.assertTrue(any("PWNED123" in r["input"] for r in rows))
            bad = Path(d, "t.txt")
            bad.write_text("no placeholder", encoding="utf-8")
            code, msg = cli("probe", "--template", bad, "--cmd", "echo hi")
            self.assertEqual(code, 2)
            self.assertIn("{INPUT}", msg)


if __name__ == "__main__":
    unittest.main()
