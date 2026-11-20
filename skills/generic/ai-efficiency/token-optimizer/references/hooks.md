# Always-on hooks

A skill only runs when the agent chooses to use it. A **hook** is run by the agent app itself at fixed points, so it works even when the model forgets. `scripts/token_hook.py` provides two hooks. Both read the event as JSON on stdin and exit 0. On any error they allow the action, so they never break a session.

| Mode | When it runs | What it does |
|---|---|---|
| `read-guard` | Before a file-read tool call | If the agent reads a **whole** text file over `--min-tokens` (default 2000, or `TOKEN_GUARD_MIN_TOKENS`), it blocks the call **once per file per session**. The reason it gives, which the model reads, says to run `token_optimizer.py auto <file>` or read a line range. The same read a second time is allowed, so a full read needed before an edit still works. Reads with a line range, small files, images and PDFs always pass. Each block is recorded in the ledger as a `guard` entry and shown on the dashboard |
| `session-end` | When a session ends | Imports that session's transcript (`transcript_path`) into the usage ledger. It is idempotent: entries are keyed by session and day |

Off switch: set `TOKEN_GUARD=off`, or create `~/.skill-hub/token-guard.off`. Delete the file to turn it back on. The state for "already blocked once" is kept in `~/.skill-hub/token-guard/` and is cleaned after 2 days.

## Agent support

| Agent | Registered by `install.py --token-hooks` | Notes |
|---|---|---|
| Claude Code | Yes: `PreToolUse` (matcher `Read`) runs `read-guard`, and `SessionEnd` runs `session-end --agent claude-code`. User level goes in `~/.claude/settings.json`; project level goes in the personal `.claude/settings.local.json` | The deny reason is returned as `hookSpecificOutput.permissionDecision` = `deny` with `permissionDecisionReason`. Docs: https://code.claude.com/docs/en/hooks |
| Others | No | Many agents read files through a shell command or have no blocking pre-tool hook. Use the instruction line from SKILL.md, and run `dashboard --import` (or `import --auto`) to keep usage current |

Add another agent only from its vendor's hook documentation: an entry `token_hooks` in `AGENTS` in `tools/install.py` (file, events, matcher and args), plus the output format that agent expects.

## Manual setup (Claude Code example)

Merge into `~/.claude/settings.json`, keeping your other hooks, and use your Python and skill paths:

```json
{
  "hooks": {
    "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "timeout": 30,
      "command": "python ~/.claude/skills/token-optimizer/scripts/token_hook.py read-guard"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "timeout": 30,
      "command": "python ~/.claude/skills/token-optimizer/scripts/token_hook.py session-end --agent claude-code"}]}]
  }
}
```

Remove them with `python tools/install.py --agent claude-code --skill token-optimizer --token-hooks --global --remove`. `--uninstall` also removes them.

## Test a hook by hand

```bash
echo '{"session_id":"t","tool_name":"Read","tool_input":{"file_path":"/path/to/big.log"}}' | python scripts/token_hook.py read-guard
```

It prints a deny decision for a big file, and nothing for a small one or on the second run in the same session.
