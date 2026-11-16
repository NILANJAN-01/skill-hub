"""Tests for the skill-hub MCP server. Standard library only, no network; writes go to temp folders.

    python -m unittest discover -s skill-hub-mcp/tests -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
REPO = PKG_ROOT.parent
sys.path.insert(0, str(PKG_ROOT))

from skill_hub_mcp import hub  # noqa: E402
from skill_hub_mcp.server import build_server  # noqa: E402


def make_server(allow_write=False):
    return build_server(hub.LocalSource(REPO), allow_write=allow_write)


def call(server, tool, **args):
    reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": tool, "arguments": args}})
    result = reply["result"]
    return result.get("structuredContent", result["content"][0]["text"]), result["isError"]


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hub = hub.Hub(hub.LocalSource(REPO))

    def top(self, query, n=3):
        return [h["name"] for h in self.hub.search(query, limit=n)]

    def test_plain_language_queries_find_the_right_skill(self):
        self.assertEqual(self.top("rebase my branch")[0], "git-rebasing")
        self.assertEqual(self.top("undo my last commit")[0], "git-undoing-things")
        self.assertEqual(self.top("shelve uncommitted changes")[0], "git-stashing-and-cleaning")
        self.assertEqual(self.top("unit test kotlin class")[0], "kotlin-unit-test")
        self.assertEqual(self.top("my pipeline is stuck")[0], "gitlab-ci-debugging")

    def test_partial_word_still_matches(self):
        self.assertEqual(self.top("rebas")[0], "git-rebasing")

    def test_category_filter(self):
        hits = self.hub.search("test", category="testing-tools", limit=25)
        self.assertTrue(hits)
        self.assertTrue(all(h["category"] == "testing-tools" for h in hits))

    def test_query_without_words_is_an_error(self):
        with self.assertRaises(hub.HubError):
            self.hub.search("the a of")

    def test_unknown_skill_suggests_names(self):
        with self.assertRaises(hub.HubError) as ctx:
            self.hub.get("rebasing")
        self.assertIn("git-rebasing", str(ctx.exception))

    def test_route_splits_a_multi_part_request(self):
        out = self.hub.route("draw the architecture of this repo, then write unit tests for utils.py "
                             "and also fix my stuck gitlab pipeline")
        self.assertEqual(len(out["parts"]), 3)
        self.assertEqual(out["load_in_order"], ["repo-architecture", "python-unit-test", "gitlab-ci-debugging"])

    def test_targets_separates_plugins_and_skills(self):
        self.assertEqual(self.hub.targets("hub-tools, git-rebasing"), (["hub-tools"], ["git-rebasing"]))
        with self.assertRaises(hub.HubError):
            self.hub.targets("no-such-thing")


class FileSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hub = hub.Hub(hub.LocalSource(REPO))

    def test_reads_a_bundled_file(self):
        self.assertIn("#", self.hub.read_file("kotlin-unit-test", "references/checks.md"))

    def test_path_traversal_is_rejected(self):
        for bad in ("../../README.md", "..\\..\\README.md", "/etc/passwd", "C:\\Windows\\win.ini", "",
                    "references/../../../LICENSE"):
            with self.assertRaises(hub.HubError, msg=bad):
                self.hub.read_file("kotlin-unit-test", bad)

    def test_binary_files_are_refused(self):
        with self.assertRaises(hub.HubError):
            self.hub.read_file("kotlin-unit-test", "references/picture.png")

    def test_remote_source_refuses_paths_outside_skills(self):
        remote = hub.RemoteSource()
        for bad in ("README.md", "skills/../LICENSE"):
            with self.assertRaises(hub.HubError, msg=bad):
                remote.read(bad)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server()

    def rpc(self, method, params=None, mid=1):
        return self.server.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_initialize_negotiates_the_version(self):
        self.assertEqual(self.rpc("initialize", {"protocolVersion": "2024-11-05"})["result"]["protocolVersion"],
                         "2024-11-05")
        result = self.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(result["protocolVersion"], "2025-11-25")
        self.assertEqual(result["serverInfo"]["name"], "skill-hub-mcp")
        self.assertIn("read-only", result["instructions"])

    def test_notifications_get_no_reply(self):
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_bad_messages_are_protocol_errors(self):
        self.assertEqual(self.server.handle({"id": 1, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(self.rpc("no/such")["error"]["code"], -32601)
        self.assertEqual(self.rpc("tools/call", {"name": "nope"})["error"]["code"], -32602)
        self.assertEqual(self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1]})
                         ["error"]["code"], -32602)

    def test_read_only_server_has_no_writing_tool(self):
        tools = self.rpc("tools/list")["result"]["tools"]
        self.assertNotIn("apply_change", [t["name"] for t in tools])
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_write_server_marks_apply_change_as_destructive(self):
        tools = {t["name"]: t for t in make_server(True).handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}
        self.assertFalse(tools["apply_change"]["annotations"]["readOnlyHint"])
        self.assertTrue(tools["apply_change"]["annotations"]["destructiveHint"])
        self.assertTrue(tools["plan_change"]["annotations"]["readOnlyHint"])

    def test_tool_argument_problems_are_tool_errors(self):
        for args in ({}, {"query": 5}, {"query": "x", "bogus": 1}):
            _, is_error = call(self.server, "search_skills", **args)
            self.assertTrue(is_error, args)
        _, is_error = call(self.server, "list_catalog", kind="nonsense")
        self.assertTrue(is_error)
        text, is_error = call(self.server, "get_skill", name="no-such-skill")
        self.assertTrue(is_error)
        self.assertIn("unknown skill", text)

    def test_tools_return_structured_content(self):
        out, is_error = call(self.server, "get_skill", name="git-rebasing")
        self.assertFalse(is_error)
        self.assertIn("SKILL.md", out["files"])
        self.assertNotIn("---\nname:", out["instructions"][:20])
        out, _ = call(self.server, "list_catalog", kind="plugins")
        self.assertIn("hub-tools", [p["name"] for p in out["items"]])
        out, _ = call(self.server, "search_skills", query="rebase", limit=999)
        self.assertLessEqual(out["count"], 25)

    def test_resources_and_prompts(self):
        uris = [r["uri"] for r in self.rpc("resources/list")["result"]["resources"]]
        self.assertIn("skillhub://skill/git-rebasing", uris)
        text = self.rpc("resources/read", {"uri": "skillhub://skill/git-rebasing"})["result"]["contents"][0]["text"]
        self.assertTrue(text.startswith("---"))
        self.assertEqual(self.rpc("resources/read", {"uri": "skillhub://skill/nope"})["error"]["code"], -32002)
        message = self.rpc("prompts/get", {"name": "use_skill", "arguments": {"name": "git-rebasing"}})
        self.assertIn("git-rebasing", message["result"]["messages"][0]["content"]["text"])


class ChangeTests(unittest.TestCase):
    """plan_change and apply_change against a temp project folder (nothing outside it is touched)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = str(Path(self.tmp.name).resolve())
        self.where = {"agents": "claude-code", "scope": "project", "project": self.project}
        self.skill = Path(self.project) / ".claude" / "skills" / "git-rebasing"

    def test_read_only_server_plans_but_gives_no_token(self):
        out, is_error = call(make_server(), "plan_change", action="install", target="git-rebasing", **self.where)
        self.assertFalse(is_error)
        self.assertEqual(out["changes"], 1)
        self.assertNotIn("token", out)
        self.assertIn("--skill git-rebasing", out["equivalent_command"])
        self.assertFalse(self.skill.exists())

    def test_install_update_and_remove(self):
        server = make_server(True)
        plan, _ = call(server, "plan_change", action="install", target="git-rebasing", **self.where)
        self.assertEqual([s["do"] for s in plan["steps"]], ["install"])
        self.assertFalse(self.skill.exists(), "planning must not write")
        done, is_error = call(server, "apply_change", token=plan["token"])
        self.assertFalse(is_error, done)
        self.assertTrue((self.skill / "SKILL.md").is_file())

        _, is_error = call(server, "apply_change", token=plan["token"])
        self.assertTrue(is_error, "a token works once")

        again, _ = call(server, "plan_change", action="install", target="git-rebasing", **self.where)
        self.assertEqual(again["changes"], 0)
        self.assertNotIn("token", again)

        listed, _ = call(server, "list_installed", **self.where)
        self.assertEqual(listed["installed"], 1)
        self.assertTrue(listed["folders"][0]["skills"][0]["matches_hub"])

        (self.skill / "SKILL.md").write_text("edited locally", encoding="utf-8")
        skipped, _ = call(server, "plan_change", action="install", target="git-rebasing", **self.where)
        self.assertEqual(skipped["changes"], 0, "install never overwrites a differing copy")
        update, _ = call(server, "plan_change", action="update", target="git-rebasing", **self.where)
        self.assertEqual([s["do"] for s in update["steps"]], ["update"])
        call(server, "apply_change", token=update["token"])
        self.assertNotEqual((self.skill / "SKILL.md").read_text(encoding="utf-8"), "edited locally")

        remove, _ = call(server, "plan_change", action="remove", target="git-rebasing", **self.where)
        self.assertEqual([s["do"] for s in remove["steps"]], ["remove"])
        self.assertTrue(self.skill.exists(), "planning must not delete")
        call(server, "apply_change", token=remove["token"])
        self.assertFalse(self.skill.exists())

    def test_bad_arguments_are_explained(self):
        server = make_server(True)
        for args in ({"action": "install", "target": "no-such-skill", **self.where},
                     {"action": "install", "target": "git-rebasing", **dict(self.where, agents="not-an-agent")},
                     {"action": "install", "target": "git-rebasing", "agents": "claude-code", "scope": "project"},
                     {"action": "install", "target": "git-rebasing", **dict(self.where, project="relative/path")},
                     {"action": "explode", "target": "git-rebasing", **self.where}):
            _, is_error = call(server, "plan_change", **args)
            self.assertTrue(is_error, args)
        _, is_error = call(server, "apply_change", token="made-up")
        self.assertTrue(is_error)


class StdioTests(unittest.TestCase):
    def test_a_real_session_over_stdio(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "route_request", "arguments": {"request": "rebase my branch"}}},
        ]
        payload = "\n".join(json.dumps(m) for m in messages) + "\nnot json\n"
        proc = subprocess.run([sys.executable, "-m", "skill_hub_mcp", "--root", str(REPO)], input=payload,
                              capture_output=True, text=True, encoding="utf-8", cwd=str(PKG_ROOT), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r.get("id") for r in replies], [1, 2, None])
        self.assertEqual(replies[1]["result"]["structuredContent"]["load_in_order"], ["git-rebasing"])
        self.assertEqual(replies[2]["error"]["code"], -32700)
        self.assertIn("skills from local clone", proc.stderr)


if __name__ == "__main__":
    unittest.main()
