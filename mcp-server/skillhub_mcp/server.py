"""Wire the skill-hub catalog into MCP tools, resources and prompts."""
from __future__ import annotations

from .catalog import Catalog, CatalogError, split_frontmatter
from .protocol import Server, Tool

VERSION = "0.1.0"
INSTRUCTIONS = (
    "skill-hub is a catalog of agent-neutral Agent Skills (step-by-step playbooks). "
    "When the user's task might match a skill, call search_skills or recommend_skills, then get_skill to read the "
    "playbook and follow it. Read references with read_skill_file only when the skill points to them. "
    "All tools are read-only; get_install_instructions only returns commands for the user to run."
)


def build_server(source):
    cat = Catalog(source)

    def search_skills(query, category=None, limit=8):
        hits = cat.search(query, category, limit)
        return {"query": query, "source": source.describe(), "count": len(hits), "results": hits}

    def recommend_skills(task, limit=3):
        hits = cat.search(task, None, limit)
        out = []
        for h in hits:
            s = cat.get(h["name"])
            out.append({**h, "example_prompts": s.get("examples", [])[:2],
                        "install": cat.install_commands(h["name"])["commands"][0]["command"]})
        return {"task": task, "recommendations": out,
                "next": "Call get_skill with the best match and follow its procedure." if out else "No match; try other words."}

    def get_skill(name, include_body=True):
        s = cat.get(name)
        out = {"name": s["name"], "title": s.get("title", ""), "category": s["category"], "description": s["description"],
               "license": s.get("license", ""), "compatibility": s.get("compatibility", ""),
               "files": cat.files(name)}
        if include_body:
            out["instructions"] = split_frontmatter(cat.skill_text(name))
        return out

    def read_skill_file(name, path):
        return cat.read_file(name, path)

    def list_categories():
        return {"categories": cat.categories()}

    def list_plugins(category=None):
        return {"plugins": cat.plugins(category)}

    def list_agents():
        return {"agents": cat.agents()}

    def get_install_instructions(target, agent=None, use_global=False):
        return cat.install_commands(target, agent, use_global)

    S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
    tools = [
        Tool("search_skills", "Search skills",
             "Keyword search over skill names, titles, descriptions and example prompts. Returns ranked matches.",
             {"query": dict(S, description="What the user wants, in plain words, e.g. 'undo last commit'"),
              "category": dict(S, description="Optional category or plugin name from list_categories"),
              "limit": dict(I, minimum=1, maximum=25, description="Max results (default 8)")}, ["query"], search_skills),
        Tool("recommend_skills", "Recommend skills for a task",
             "Best 1-5 skills for a task, with example prompts and an install command for each.",
             {"task": dict(S, description="The task in the user's words"), "limit": dict(I, minimum=1, maximum=5)},
             ["task"], recommend_skills),
        Tool("get_skill", "Get a skill's playbook",
             "Full instructions (SKILL.md body) of one skill plus the list of its bundled files. Follow the instructions.",
             {"name": dict(S, description="Skill name, e.g. git-rebasing"),
              "include_body": dict(B, description="false to get metadata and file list only")}, ["name"], get_skill),
        Tool("read_skill_file", "Read a file bundled with a skill",
             "Read a text file inside a skill folder (references/*.md, scripts/*.py, assets). Max 200 KB.",
             {"name": S, "path": dict(S, description="Path inside the skill, e.g. references/checks.md")},
             ["name", "path"], read_skill_file),
        Tool("list_categories", "List categories", "All categories with skill counts.", {}, [], list_categories),
        Tool("list_plugins", "List plugins",
             "Plugin bundles (installable groups of skills), optionally for one category.",
             {"category": S}, [], list_plugins),
        Tool("list_agents", "List supported agents",
             "AI coding agents skill-hub installs into, with their skill folders.", {}, [], list_agents),
        Tool("get_install_instructions", "How to install a skill or plugin",
             "Commands to install a skill or plugin (installer, npx skills, native plugin). Does NOT run anything; "
             "show the commands to the user.",
             {"target": dict(S, description="Skill or plugin name"), "agent": dict(S, description="Agent id, e.g. claude-code"),
              "use_global": dict(B, description="Install for the user instead of the project")}, ["target"],
             get_install_instructions),
    ]

    class Resources:
        def list(self):
            items = [{"uri": "skillhub://catalog", "name": "catalog", "title": "skill-hub catalog summary",
                      "mimeType": "application/json"}]
            items += [{"uri": f"skillhub://skill/{s['name']}", "name": s["name"], "title": s.get("title", s["name"]),
                       "description": s["description"], "mimeType": "text/markdown"} for s in cat.skills]
            return items

        def templates(self):
            return [{"uriTemplate": "skillhub://skill/{name}", "name": "skill", "title": "A skill's SKILL.md",
                     "mimeType": "text/markdown"}]

        def read(self, uri):
            import json
            if uri == "skillhub://catalog":
                return {"uri": uri, "mimeType": "application/json", "text": json.dumps(
                    {"source": source.describe(), "skills": len(cat.skills), "categories": cat.categories()}, indent=2)}
            if uri.startswith("skillhub://skill/"):
                try:
                    return {"uri": uri, "mimeType": "text/markdown", "text": cat.skill_text(uri.rsplit("/", 1)[-1])}
                except CatalogError:
                    pass
            raise KeyError(uri)

    def msg(text):
        return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}

    prompts = {
        "find_skill": ({"name": "find_skill", "title": "Find a skill for a task",
                        "description": "Search skill-hub and follow the best matching skill.",
                        "arguments": [{"name": "task", "description": "What you want to do", "required": True}]},
                       lambda a: msg(f"Use the skill-hub tools to find the best skill for this task, read it with get_skill "
                                     f"and follow it: {a.get('task', '')}")),
        "use_skill": ({"name": "use_skill", "title": "Use a named skill",
                       "description": "Load one skill and apply it.",
                       "arguments": [{"name": "name", "description": "Skill name", "required": True},
                                     {"name": "task", "description": "What to apply it to", "required": False}]},
                      lambda a: msg(f"Read the skill '{a.get('name', '')}' with get_skill and follow its procedure"
                                    + (f" for: {a['task']}" if a.get("task") else "."))),
    }
    return Server("skillhub-mcp", VERSION, INSTRUCTIONS, tools, Resources(), prompts)
