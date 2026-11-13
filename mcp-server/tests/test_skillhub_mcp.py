import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
REPO = PKG_ROOT.parent
sys.path.insert(0, str(PKG_ROOT))

from skillhub_mcp import catalog  # noqa: E402
from skillhub_mcp.server import build_server  # noqa: E402


def local_catalog():
    return catalog.Catalog(catalog.LocalSource(REPO))


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = local_catalog()

    def top(self, q, n=3):
        return [h["name"] for h in self.cat.search(q, limit=n)]

    def test_plain_language_queries_find_the_right_skill(self):
        self.assertEqual(self.top("rebase my branch")[0], "git-rebasing")
        self.assertIn("git-undoing-things", self.top("undo my last commit"))
        self.assertIn("git-stashing-and-cleaning", self.top("shelve uncommitted changes"))
        self.assertIn("kotlin-unit-test", self.top("unit test kotlin class"))

    def test_category_filter(self):
        hits = self.cat.search("test", category="testing-tools", limit=25)
        self.assertTrue(hits)
        self.assertTrue(all(h["category"] == "testing-tools" for h in hits))

    def test_empty_query_is_an_error(self):
        with self.assertRaises(catalog.CatalogError):
            self.cat.search("the a of")

    def test_unknown_skill_suggests_names(self):
        with self.assertRaises(catalog.CatalogError) as ctx:
            self.cat.get("rebas")
        self.assertIn("git-rebasing", str(ctx.exception))


class FileSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = local_catalog()

    def test_reads_a_reference_file(self):
        self.assertIn("#", self.cat.read_file("kotlin-unit-test", "references/checks.md"))

    def test_path_traversal_is_rejected(self):
        for bad in ("../../README.md", "..\\..\\README.md", "/etc/passwd", "C:\\Windows\\win.ini", "", "references/../../../LICENSE"):
            with self.assertRaises(catalog.CatalogError, msg=bad):
                self.cat.read_file("kotlin-unit-test", bad)

    def test_binary_suffix_is_rejected(self):
        with self.assertRaises(catalog.CatalogError):
            self.cat.read_file("kotlin-unit-test", "scripts/x.exe")

    def test_install_commands_never_write(self):
        out = self.cat.install_commands("git-rebasing", "claude-code")
        self.assertEqual(out["kind"], "skill")
        self.assertTrue(any("npx skills add" in c["command"] for c in out["commands"]))
        self.assertEqual(self.cat.install_commands("testing-tools")["kind"], "plugin")
        with self.assertRaises(catalog.CatalogError):
            self.cat.install_commands("git-rebasing", "no-such-agent")


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = build_server(catalog.LocalSource(REPO))

    def rpc(self, method, params=None, mid=1):
        return self.server.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_initialize_negotiates_version(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(r["protocolVersion"], "2025-03-26")
        r = self.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(r["protocolVersion"], "2025-11-25")
        self.assertIn("tools", r["capabilities"])

    def test_notification_gets_no_reply(self):
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_and_call(self):
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"search_skills", "get_skill", "read_skill_file", "get_install_instructions"} <= names)
        res = self.rpc("tools/call", {"name": "get_skill", "arguments": {"name": "git-rebasing"}})["result"]
        self.assertFalse(res["isError"])
        self.assertIn("instructions", res["structuredContent"])
        self.assertNotIn("description:", res["structuredContent"]["instructions"][:40])

    def test_tool_errors_are_results_not_protocol_errors(self):
        res = self.rpc("tools/call", {"name": "get_skill", "arguments": {"name": "nope-nope"}})["result"]
        self.assertTrue(res["isError"])
        res = self.rpc("tools/call", {"name": "search_skills", "arguments": {}})["result"]
        self.assertTrue(res["isError"])
        res = self.rpc("tools/call", {"name": "search_skills", "arguments": {"query": "git", "bogus": 1}})["result"]
        self.assertTrue(res["isError"])
        self.assertEqual(self.rpc("tools/call", {"name": "missing"})["error"]["code"], -32602)

    def test_limit_is_clamped(self):
        res = self.rpc("tools/call", {"name": "search_skills", "arguments": {"query": "git", "limit": 9999}})["result"]
        self.assertLessEqual(res["structuredContent"]["count"], 25)

    def test_resources_and_prompts(self):
        listed = self.rpc("resources/list")["result"]["resources"]
        self.assertGreater(len(listed), 50)
        read = self.rpc("resources/read", {"uri": "skillhub://skill/git-rebasing"})["result"]["contents"][0]
        self.assertIn("rebase", read["text"].lower())
        self.assertEqual(self.rpc("resources/read", {"uri": "skillhub://skill/zzz"})["error"]["code"], -32002)
        prompt = self.rpc("prompts/get", {"name": "find_skill", "arguments": {"task": "squash commits"}})["result"]
        self.assertIn("squash commits", prompt["messages"][0]["content"]["text"])

    def test_unknown_method(self):
        self.assertEqual(self.rpc("nope/nope")["error"]["code"], -32601)


class StdioEndToEnd(unittest.TestCase):
    def test_real_process_over_stdio(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                           "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "recommend_skills", "arguments": {"task": "I committed to the wrong branch, undo it"}}},
        ]
        data = "\n".join(json.dumps(m) for m in msgs) + "\nnot json\n"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "skillhub_mcp", "--root", str(REPO)], input=data, capture_output=True,
                           text=True, cwd=str(PKG_ROOT), env=env, timeout=60, encoding="utf-8")
        lines = [json.loads(line) for line in p.stdout.splitlines()]  # stdout must be pure JSON
        by_id = {m.get("id"): m for m in lines}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "skillhub-mcp")
        recs = by_id[2]["result"]["structuredContent"]["recommendations"]
        self.assertTrue(recs and recs[0]["install"])
        self.assertEqual(by_id[None]["error"]["code"], -32700)  # the garbage line
        self.assertIn("skills from", p.stderr)  # logging only on stderr
        self.assertEqual(p.returncode, 0)

    def test_bad_root_exits_2(self):
        p = subprocess.run([sys.executable, "-m", "skillhub_mcp", "--root", str(HERE), "--check"], capture_output=True,
                           text=True, cwd=str(PKG_ROOT), timeout=30)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
