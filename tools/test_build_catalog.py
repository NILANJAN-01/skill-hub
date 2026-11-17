"""Tests that user-guide.html stays complete: every skill, plugin, agent, installer option, MCP preset and
MCP tool in the repository must appear in its data. Standard library only.

    python -m unittest discover -s tools -p "test_*.py" -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog  # noqa: E402
import install  # noqa: E402


def guide_data():
    catalog = build_catalog.build()[4]
    html = build_catalog.user_guide_html(catalog)
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    return catalog, html, json.loads(m.group(1).replace("<\\/", "</"))


class UserGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.html, cls.data = guide_data()

    def test_every_skill_and_plugin(self):
        self.assertEqual({s["name"] for s in self.data["skills"]}, {s["name"] for s in self.catalog["skills"]})
        self.assertEqual({p["name"] for p in self.data["plugins"]}, {p["name"] for p in self.catalog["plugins"]})
        self.assertEqual(self.data["stats"]["skills"], len(self.catalog["skills"]))

    def test_every_installer_option(self):
        in_guide = {f for g in self.data["installer"] for o in g["options"] for f in o["flags"].split(", ")}
        in_parser = {f for a in install.build_parser()._actions for f in a.option_strings} - {"-h", "--help"}
        self.assertEqual(in_guide, in_parser)

    def test_agents_presets_and_mcp_tools(self):
        self.assertEqual([a["id"] for a in self.data["agents"]], list(install.AGENTS))
        self.assertEqual([p["name"] for p in self.data["mcp_presets"]], list(install.MCP_PRESETS))
        tools = {t["name"] for t in self.data["mcp_server"]["tools"]}
        self.assertTrue({"search_skills", "route_request", "get_skill", "plan_change", "apply_change"} <= tools)

    def test_scripts_are_listed_with_usage(self):
        scripts = {sc["file"] for s in self.data["skills"] for sc in s["scripts"]}
        on_disk = {p.name for p in (build_catalog.ROOT / "skills").rglob("scripts/*.py")
                   if not p.name.startswith(("test_", "_"))}
        self.assertEqual(scripts, on_disk)

    def test_page_is_self_contained_and_deterministic(self):
        self.assertNotIn("/*__DATA__*/null", self.html)
        self.assertEqual(self.html, build_catalog.user_guide_html(self.catalog))     # same input, same page
        self.assertTrue(self.data["maintainers"]["checks"])
        self.assertTrue(self.data["changelog"])


if __name__ == "__main__":
    unittest.main()
