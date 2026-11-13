# skill-hub MCP server

An [MCP](https://modelcontextprotocol.io) server that exposes the skill-hub catalog to any MCP-capable agent, so the agent can **find** the right skill for a task by itself and **read** its playbook, instead of relying on the agent trimming 70+ skill descriptions into its context.

- Python 3.8+, **standard library only**, no install step. Speaks MCP over stdio (protocol versions 2024-11-05 to 2025-11-25).
- **Read-only.** It never writes files or runs commands. `get_install_instructions` only *returns* commands for you to run.
- Reads a local clone of this repo, or GitHub (`--remote`) when there is no clone.

## Tools

| Tool | Purpose |
|---|---|
| `search_skills` | Ranked keyword search (name, title, description, example prompts); optional `category`, `limit` |
| `recommend_skills` | Best 1-5 skills for a task, with example prompts and an install command |
| `get_skill` | A skill's full instructions (SKILL.md body) and its file list |
| `read_skill_file` | A text file bundled with a skill (`references/…`, `scripts/…`), max 200 KB, path-traversal safe |
| `list_categories` / `list_plugins` / `list_agents` | Browse categories, installable bundles and supported agents |
| `get_install_instructions` | Installer, `npx skills` and native-plugin commands for a skill or plugin |

Also: resources `skillhub://catalog` and `skillhub://skill/{name}` (every SKILL.md), and prompts `find_skill` and `use_skill`.

## Run it

From a clone of this repository:

```bash
cd mcp-server
python -m skillhub_mcp --check      # prints "N skills from local clone ..." and exits
python -m skillhub_mcp --remote     # read from GitHub, no clone needed (still run from mcp-server/ or set PYTHONPATH)
```

Options: `--root DIR` (a clone; also `SKILLHUB_ROOT`), `--remote`, `--ref BRANCH`, `--check`.

## Add it to an agent

Most agents take the same JSON shape. Use absolute paths:

```json
{
  "mcpServers": {
    "skill-hub": {
      "command": "python",
      "args": ["-m", "skillhub_mcp"],
      "cwd": "/path/to/skill-hub/mcp-server"
    }
  }
}
```

If the agent has no `cwd` option, set `"env": {"PYTHONPATH": "/path/to/skill-hub/mcp-server"}` instead. Without a clone, add `"--remote"` to `args`.
Claude Code: `claude mcp add skill-hub --env PYTHONPATH=/path/to/skill-hub/mcp-server -- python -m skillhub_mcp`.
Check your agent's documentation for where its MCP configuration lives.

## Tests

```bash
python -m unittest discover -s mcp-server/tests -v
```

They cover ranking on plain-language queries, path-traversal rejection, protocol negotiation, tool-error handling, and a real stdio session against a spawned server process. They need no network.

## Notes

- Network is used only with `--remote` (raw.githubusercontent.com and api.github.com, fixed URLs, cached 15 minutes).
- Logs go to stderr; stdout carries protocol messages only.
- The server is hand-written protocol code on purpose, to keep the hub dependency-free. If you prefer the official `mcp` SDK, only `protocol.py` would be replaced.
