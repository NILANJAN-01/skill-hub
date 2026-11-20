# Session logs: where agents keep them and what the importer reads

Locations change between versions. Check the agent's current docs if a folder is missing.

| Agent | Session logs (checked by `import --auto`) | Usage fields |
|---|---|---|
| Claude Code | `~/.claude/projects/<project>/*.jsonl` (sub-agent runs in `subagents/`) | `message.usage`: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` |
| Codex CLI | `~/.codex/sessions/YYYY/MM/DD/*.jsonl` | `token_count` events: `last_token_usage` per turn (`total_token_usage` is a running total and is skipped) |
| Gemini CLI | `~/.gemini/tmp/<project>/` (chat checkpoints, when enabled) | `usageMetadata`: `promptTokenCount`, `candidatesTokenCount`, `cachedContentTokenCount` |
| opencode | `~/.local/share/opencode/storage/` | `tokens` records when present |
| Others | Pass the folder: `import <dir> --agent <name>` | Any JSON/JSONL with `input_tokens`/`prompt_tokens` style keys |

Agents that write no usage (many IDE chats) can still be tracked with `record`, using the numbers from their usage or billing page.

## What the importer recognises

- **Records:** one JSON document, a JSON array, an object with a `messages` array, or JSON Lines. Lines that are not JSON are skipped.
- **Tokens:** input `input_tokens | prompt_tokens | promptTokenCount | inputTokens | prompt_token_count`; output `output_tokens | completion_tokens | candidatesTokenCount | outputTokens | completion_token_count`; cache read `cache_read_input_tokens | cachedContentTokenCount | cache_read_tokens`; cache write `cache_creation_input_tokens | cache_write_tokens`. Objects whose key starts with `total_` or `cumulative` are skipped, because they repeat per-turn numbers.
- **Duplicates:** records with the same `message.id`, `requestId` or `response_id` are counted once. Some agents write one record per content block with the same usage.
- **Time:** `timestamp | time | created_at | createdAt | ts | date`, as ISO 8601 or epoch seconds or milliseconds, on the record or its `message`/`payload`. A record without a time takes the previous record's time, or the file's modification time if there is none.
- **Tool calls:** objects whose `type` is `tool_use`, `function_call`, `tool_call`, `server_tool_use`, `custom_tool_call` or `local_shell_call`, and `functionCall` objects.
- **Skills used:** in a tool call's arguments, a `skill` or `skill_name` value, any path `.../<name>/SKILL.md`, or a path `skills/.../<name>/scripts/...`. Text in user or assistant messages is ignored, so mentioning a skill is not counted as using it.
- **Session id:** the first 12 hex characters of the SHA-1 of the log's path. Entries are keyed by `<session>:<local day>`, so a re-import replaces them.

## Ledger entry kinds

```json
{"time": "2026-11-18T14:30:00+05:30", "end": "...", "kind": "usage", "id": "f5be86260c0f:2026-11-18",
 "session": "f5be86260c0f", "agent": "claude-code", "input": 150, "output": 50, "cache_read": 3000,
 "cache_write": 200, "total": 3400, "messages": 2, "tool_calls": 3,
 "skills": {"token-optimizer": 2}, "models": {"model-name": 2}}
{"time": "2026-11-20T22:41:07+05:30", "kind": "optimize", "tool": "log", "skill": "token-optimizer",
 "source": "build.log", "before": 58737, "after": 510, "saved": 58227}
```

`record` writes a `usage` entry whose id starts with `manual:` and can include a `task` note. Entries from the skill-token-meter ledger are read as they are and shown as "skill saving" rows.
