# skill-hub-mcp

An [MCP](https://modelcontextprotocol.io) server for the skill-hub catalog. Any MCP-capable agent can use it to **find** the right skill for a task, **read** its playbook, and **install, update or remove** skills in the agents on your machine, after you agree.

- Python 3.8+, **standard library only**. Speaks MCP over stdio (protocol versions 2024-11-05 to 2025-11-25).
- **Read-only unless you start it with `--allow-install`.** Without that option there is no tool that writes.
- Reads a local clone of the hub, or GitHub (`--remote`) when there is no clone.
- This is the newer server. The first one, [`mcp-server/`](../mcp-server/README.md), still works and is kept until this one has proven itself.

## Tools

| Tool | What it does | Writes? |
|---|---|---|
| `search_skills` | Ranked search (BM25 over name, title, category, description and example prompts); optional `category`, `limit` | no |
| `route_request` | Splits a vague or multi-part request into parts and picks the skills to load for each, in order | no |
| `get_skill` | A skill's full instructions (the `SKILL.md` body), example prompts and file list | no |
| `read_skill_file` | A text file bundled with a skill (`references/…`, `scripts/…`); at most 200 KB, no path traversal | no |
| `list_catalog` | `categories`, `plugins` or `agents` | no |
| `detect_agents` | Which supported agents are installed on this machine | no |
| `list_installed` | Hub skills an agent already has, their hub version, and whether they still match the hub | no |
| `plan_change` | The exact steps to `install`, `update` or `remove` a skill or plugin, plus the equivalent installer command | no |
| `apply_change` | Carries out one plan. **Only present with `--allow-install`** | **yes** |

Also: resources `skillhub://catalog` and `skillhub://skill/{name}`, and prompts `find_skill` and `use_skill`.

## How installing is kept safe

1. `plan_change` never writes. It returns the steps and, when writes are enabled, a one-time token.
2. `apply_change` takes only that token, so it can do nothing except the plan that was shown. A token works once and expires after 10 minutes.
3. `apply_change` is marked as a destructive tool, so MCP clients ask you before running it.
4. `install` never replaces a copy that differs from the hub (use `update` for that), and installing never deletes anything.
5. All planning and copying is done by the hub's own installer, `tools/install.py`, so the folders match what the installer would choose.

## Run it

From a clone of this repository:

```bash
cd skill-hub-mcp
python -m skill_hub_mcp --check                   # prints "N skills from local clone ... (read-only, 8 tools)"
python -m skill_hub_mcp --allow-install --check   # 9 tools
python -m skill_hub_mcp --remote --ref v1.3.0     # read a release from GitHub instead of the clone
```

Options: `--root DIR` (a clone; also the `SKILLHUB_ROOT` variable), `--remote`, `--ref REF`, `--allow-install`, `--check`. Set `SKILLHUB_REPO=owner/name` for a fork.

Without a clone, install the package from the repository and use `--remote`:

```bash
pip install "git+https://github.com/NILANJAN-01/skill-hub#subdirectory=skill-hub-mcp"
skill-hub-mcp --remote --check
```

With `--remote`, installing downloads the hub archive for that ref first. A release tag is checked against the release's `SHA256SUMS` by the installer.

## Add it to an agent

Most agents take this JSON shape. Use absolute paths:

```json
{
  "mcpServers": {
    "skill-hub": {
      "command": "python",
      "args": ["-m", "skill_hub_mcp"],
      "cwd": "/path/to/skill-hub/skill-hub-mcp"
    }
  }
}
```

Add `"--allow-install"` to `args` to let the agent install skills. If the agent has no `cwd` option, set `"env": {"PYTHONPATH": "/path/to/skill-hub/skill-hub-mcp"}` instead. Check your agent's documentation for where its MCP configuration lives.

## Tests

```bash
python -m unittest discover -s skill-hub-mcp/tests -v
```

They cover search ranking on plain-language queries, request routing, path-traversal rejection, protocol negotiation and errors, tool annotations, a full install / update / remove cycle in a temporary project folder, and a real stdio session against a spawned server. They need no network.

## Notes

- Network is used only with `--remote` (raw.githubusercontent.com, api.github.com, and the hub archive when installing), with fixed URLs and a 15-minute cache.
- Logs go to stderr; stdout carries protocol messages only. The installer's own output is captured and returned in the tool result.
- Not published to PyPI yet. The name `skill-hub-mcp` was free when this was written; `skillhub-mcp` (no hyphen) is an unrelated project.
