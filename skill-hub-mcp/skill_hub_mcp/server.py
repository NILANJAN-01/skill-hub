"""The skill-hub MCP server: tools, resources and prompts over the hub catalog."""
from __future__ import annotations

import json

from .actions import ACTIONS, Actions
from .hub import Hub, HubError, strip_frontmatter
from .rpc import Server, Tool

VERSION = "0.1.0"
NAME = "skill-hub-mcp"


def instructions(allow_write):
    text = ("skill-hub is a catalog of agent-neutral Agent Skills: step-by-step playbooks, some with scripts. "
            "For a task that might match a skill, call route_request (multi-part or vague requests) or "
            "search_skills, then get_skill and follow the playbook. Read bundled files with read_skill_file only "
            "when the playbook points to them. To add skills to the user's agents, call plan_change and show the "
            "plan to the user. ")
    return text + ("Call apply_change only after the user agrees to that exact plan." if allow_write else
                   "This server is read-only: give the user the command from the plan to run themselves.")


def build_server(source, allow_write=False):
    hub = Hub(source)
    actions = Actions(hub, allow_write)
    S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}

    def search_skills(query, category=None, limit=8):
        hits = hub.search(query, category, limit)
        return {"query": query, "source": source.describe(), "count": len(hits), "results": hits}

    def route_request(request):
        return hub.route(request)

    def get_skill(name, include_body=True):
        s = hub.get(name)
        out = {k: s.get(k, "") for k in ("name", "title", "category", "description", "license", "compatibility")}
        out["examples"] = s.get("examples", [])[:3]
        out["files"] = hub.files(name)
        if include_body:
            out["instructions"] = strip_frontmatter(hub.skill_text(name))
        return out

    def read_skill_file(name, path):
        return hub.read_file(name, path)

    def list_catalog(kind="categories"):
        rows = {"categories": hub.categories, "plugins": hub.plugins, "agents": hub.agents}[kind]()
        return {"kind": kind, "hub_version": hub.version, "skills": len(hub.skills), "items": rows}

    scope = dict(S, enum=["user", "project"], description="'user' = every project of this user (default); "
                                                          "'project' = one project folder")
    agents = dict(S, description="Agent ids separated by commas (see list_catalog kind=agents), or 'detected' "
                                 "(default) for every agent found on this machine")
    project = dict(S, description="Absolute path of the project folder; needed when scope is 'project'")

    tools = [
        Tool("search_skills", "Search skills",
             "Ranked search over skill names, titles, descriptions and example prompts.", search_skills,
             {"query": dict(S, description="What the user wants, in plain words, e.g. 'undo last commit'"),
              "category": dict(S, description="Optional category or plugin name"),
              "limit": dict(I, minimum=1, maximum=25, description="Maximum results (default 8)")}, ["query"]),
        Tool("route_request", "Route a request to skills",
             "Split a vague or multi-part request into parts and pick the skills to load for each, in order.",
             route_request, {"request": dict(S, description="The user's whole request, in their words")}, ["request"]),
        Tool("get_skill", "Get a skill's playbook",
             "The full instructions (SKILL.md body) of one skill and the list of its bundled files. Follow them.",
             get_skill, {"name": dict(S, description="Skill name, e.g. git-rebasing"),
                         "include_body": dict(B, description="false for metadata and the file list only")}, ["name"]),
        Tool("read_skill_file", "Read a file bundled with a skill",
             "Read a text file inside a skill folder (references/, scripts/, assets/). At most 200 KB.",
             read_skill_file, {"name": dict(S, description="Skill name"),
                               "path": dict(S, description="Path inside the skill, e.g. references/checks.md")},
             ["name", "path"]),
        Tool("list_catalog", "List categories, plugins or agents",
             "Browse the hub: categories with skill counts, installable plugins, or supported agents and their folders.",
             list_catalog, {"kind": dict(S, enum=["categories", "plugins", "agents"])}),
        Tool("detect_agents", "Detect installed agents",
             "Which supported AI coding agents are installed on this machine. Changes nothing.",
             lambda: actions.detect()),
        Tool("list_installed", "List installed hub skills",
             "Hub skills already installed for the chosen agents, their hub version and whether they match the hub.",
             lambda agents=None, scope="user", project=None: actions.installed(agents, scope, project),
             {"agents": agents, "scope": scope, "project": project}),
        Tool("plan_change", "Plan an install, update or removal",
             "Work out exactly which folders would change to install, update or remove a skill or plugin. Changes "
             "nothing. Returns the steps, an equivalent command, and a token for apply_change when writes are enabled.",
             lambda action, target, agents=None, scope="user", project=None:
             actions.plan(action, target, agents, scope, project),
             {"action": dict(S, enum=list(ACTIONS)),
              "target": dict(S, description="Skill or plugin names, separated by commas"),
              "agents": agents, "scope": scope, "project": project}, ["action", "target"]),
    ]
    if allow_write:
        tools.append(Tool(
            "apply_change", "Apply a planned change",
            "Carry out a plan made by plan_change. Writes or deletes skill folders. Call it only after the user has "
            "seen that plan and agreed.", lambda token: actions.apply(token),
            {"token": dict(S, description="The token returned by plan_change")}, ["token"], writes=True))

    class Resources:
        def list(self):
            items = [{"uri": "skillhub://catalog", "name": "catalog", "title": "skill-hub catalog summary",
                      "mimeType": "application/json"}]
            return items + [{"uri": f"skillhub://skill/{s['name']}", "name": s["name"],
                             "title": s.get("title", s["name"]), "description": s.get("description", ""),
                             "mimeType": "text/markdown"} for s in hub.skills]

        def templates(self):
            return [{"uriTemplate": "skillhub://skill/{name}", "name": "skill", "title": "A skill's SKILL.md",
                     "mimeType": "text/markdown"}]

        def read(self, uri):
            if uri == "skillhub://catalog":
                return {"uri": uri, "mimeType": "application/json", "text": json.dumps(
                    {"source": source.describe(), "version": hub.version, "skills": len(hub.skills),
                     "categories": hub.categories()}, indent=2)}
            if uri.startswith("skillhub://skill/"):
                try:
                    return {"uri": uri, "mimeType": "text/markdown", "text": hub.skill_text(uri.rsplit("/", 1)[-1])}
                except HubError:
                    pass
            raise KeyError(uri)

    def message(text):
        return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}

    prompts = {
        "find_skill": ({"name": "find_skill", "title": "Find a skill for a task",
                        "description": "Route the task to skills and follow the best match.",
                        "arguments": [{"name": "task", "description": "What you want to do", "required": True}]},
                       lambda a: message("Use the skill-hub tools: call route_request for this task, read the chosen "
                                         f"skills with get_skill and follow them: {a.get('task', '')}")),
        "use_skill": ({"name": "use_skill", "title": "Use a named skill", "description": "Load one skill and apply it.",
                       "arguments": [{"name": "name", "description": "Skill name", "required": True},
                                     {"name": "task", "description": "What to apply it to", "required": False}]},
                      lambda a: message(f"Read the skill '{a.get('name', '')}' with get_skill and follow its procedure"
                                        + (f" for: {a['task']}" if a.get("task") else "."))),
    }
    return Server(NAME, VERSION, instructions(allow_write), tools, Resources(), prompts, soft_errors=(HubError,))
