---
name: agent-tool-design
description: "Design and review agent tools (function calling): names, descriptions, JSON Schema parameters, outputs and errors, with a script that lints tool definitions in common formats. Use when the user writes tool or function definitions, or an agent picks the wrong tool or passes bad arguments."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the lint script. The guidance applies to any model provider or agent framework.
metadata:
  title: "Agent tool design: names, schemas and errors models use well"
  category: ai-agent-tools
---

# Agent tool design

A model chooses and calls tools using only their **name, description and parameter schema**. Most "the agent is dumb" problems are tool-design problems: overlapping tools, vague descriptions, loose schemas, or outputs and errors the model cannot act on.

## When to use

- Writing tool/function definitions for an agent, an MCP server or a function-calling API.
- The agent picks the wrong tool, skips a tool, loops, or sends invalid arguments.
- Reviewing a tool set before release.

## When NOT to use

- Building or debugging the MCP server process itself: use `mcp-server-builder`.
- Measuring the effect of a change across many tasks: use `llm-evals` (do it after this skill).

## Design rules

1. **One tool per user-level job**, not per API endpoint. `schedule_meeting` beats `list_calendars` + `get_free_busy` + `create_event` when the agent always needs all three. Fewer, sharper tools beat many thin ones; above ~20 tools, selection accuracy drops.
2. **Names**: `verb_noun`, snake_case, unique and distinct (`search_issues`, `create_issue`). Keep within `[A-Za-z0-9_-]`, max 64 characters, which every major provider accepts. Prefix by domain when tools come from several servers (`github_search_issues`).
3. **Descriptions** (3 to 6 sentences) answer: what it does, **when to use it**, when *not* to (and which tool instead), what it returns, and limits (page size, rate limits, side effects). Write for a new teammate who has never seen the system.
4. **Parameters**:
   - Root schema is `{"type": "object", "properties": ..., "required": [...]}`; every property has a `description`.
   - Prefer `enum` over free text, explicit formats (`"format": "date"`, "ISO 8601, e.g. 2026-11-17") and units in names (`timeout_seconds`).
   - Require only what is truly required; give defaults in the description.
   - Accept human identifiers (names, emails, paths) rather than internal IDs the model would have to look up first.
   - Set `"additionalProperties": false` when the provider supports strict schemas.
5. **Outputs**: return only what the model needs, in compact text or JSON; human-meaningful fields over UUIDs; paginate or truncate large results and say so ("showing 20 of 312; pass page=2").
6. **Errors**: say what went wrong **and what to do next** ("No user 'jdoe'. Call search_users with part of the name."). Never return raw stack traces.
7. **Side effects**: say clearly in the description if a tool writes, deletes, sends or spends money; make it idempotent where possible; require confirmation for destructive actions at the agent level.

## Procedure

1. **Inventory** the tasks the agent must complete and sketch the minimal tool set (table: job → tool → inputs → output).
2. **Write the definitions** in the format the project uses. Typical shapes:
   ```json
   {"name": "search_issues",
    "description": "Search open and closed issues in the current repository by keywords, label or author. Use when the user asks about existing bugs or feature requests. Do not use to create issues (use create_issue). Returns up to 20 issues with number, title, state and URL, newest first.",
    "inputSchema": {"type": "object",
      "properties": {
        "query": {"type": "string", "description": "Keywords to match in title and body"},
        "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue state filter; default open"},
        "page": {"type": "integer", "minimum": 1, "description": "Result page, 20 per page; default 1"}},
      "required": ["query"]}}
   ```
   MCP uses `inputSchema`; some APIs use `input_schema`; OpenAI-style APIs wrap it as `{"type": "function", "function": {"name", "description", "parameters"}}`. The schema content is the same JSON Schema.
3. **Lint** the definitions (a JSON file holding one tool, a list, or `{"tools": [...]}`):
   ```bash
   python scripts/tool_lint.py tools.json
   python scripts/tool_lint.py tools.json --json      # machine-readable
   python scripts/tool_lint.py tools.json --strict    # warnings fail too (for CI)
   ```
   It checks names, description length and "when to use" guidance, schema root type, parameter descriptions, `required` vs `properties`, enum and type sanity, parameter count, and name/description overlap between tools. Exit `0` clean, `1` errors (or warnings with `--strict`), `2` unreadable input.
4. **Test with the model**: write 10 to 20 realistic requests, including ones that should *not* use a tool and ones that sit between two tools. Check which tool is called and with which arguments. Turn them into a repeatable suite with `llm-evals`.
5. **Iterate on wording**, not code, first: most fixes are a clearer description, an `enum`, or merging two overlapping tools.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Wrong tool chosen | Overlapping descriptions: add "Use when ... / Do not use for ... (use X)" to both |
| Tool never used | Description does not mention the words users say; add them, and say when to use it |
| Invalid or made-up arguments | Loose schema: add `enum`, formats, examples in descriptions, mark required fields |
| Agent loops calling the same tool | Output lacks a clear end state or the error gives no next step |
| Context fills up | Tool returns too much: filter fields, paginate, summarize |
| Model asks for IDs it cannot know | Accept names/emails, or add a lookup tool and say so in the description |

## References

- [references/checklist.md](references/checklist.md): review checklist and before/after examples.
