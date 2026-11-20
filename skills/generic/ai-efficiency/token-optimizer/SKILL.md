---
name: token-optimizer
description: "Cut the tokens an agent reads and track usage: compress logs, outline or slice files, shrink JSON, pack folders under a budget, import session logs (timestamps, skills used), build an HTML dashboard. Use when the user wants to reduce tokens, read a huge log, file or JSON, or see tokens or skills used per day."
license: MIT
compatibility: "Python 3.8+ (standard library only). Works with any agent. File token counts are estimates (chars/4 prose, chars/3.3 code, about +-20%); usage imported from session logs is what the agent recorded. Importing needs an agent that writes JSON or JSONL session logs with usage records; otherwise record usage by hand."
metadata:
  title: "Token optimizer: read less, track usage, see it on a dashboard"
  category: ai-efficiency-tools
---

# Token optimizer

Most tokens are spent reading big inputs, which are then resent with every later turn. One rule fixes most of it.

## The rule

**Before reading any log, JSON, large file or folder, run `auto` on it and read its output instead:**

```bash
python scripts/token_optimizer.py auto <file, folder or several files>
```

(Use this skill's folder, or the script's full path.) `auto` picks the method by itself:

- **Logs:** errors with their context, the head and the tail.
- **JSON:** shrunk, or only its shape.
- **Code and Markdown:** an outline with line ranges.
- **Folders:** a pack under a token budget.
- **Small files:** printed unchanged.

It prints the before and after token counts to stderr and records them with a timestamp.

Then read only what you still need:

```bash
python scripts/token_optimizer.py slice <file> --symbol <Name>     # or --lines 120-180
```

- If the reduced log does not show the root cause, run `log <file> --context 10` and don't guess.
- When the run serves another skill's task, add `--skill <that-skill>` so the dashboard credits it.

## Usage and the dashboard

When the user asks how many tokens they used, when, or which skills they use:

```bash
python scripts/token_optimizer.py dashboard --import --open    # refresh from session logs, write and open the HTML
python scripts/token_optimizer.py stats --days 7               # the same numbers in the terminal
```

The dashboard is saved as `~/.skill-hub/token-dashboard.html`. It shows tokens per day (all, and without cache reads), tokens saved, every skill's uses with first and last timestamps, recent activity, and advice from the data. Tell the user the path, and ask before sharing it, because it shows which projects and skills they use.

- Say which numbers are **estimates** (savings) and which are **as recorded** by the agent (imported usage).
- When talking about cost, quote fresh tokens (without cache reads).

## When NOT to use

- To audit a project for waste (lockfiles, ignore files, bloated instructions), use `ai-token-saver`.
- To measure what one skill saves, with vs without it, use `skill-token-meter`. Its ledger shows up on this dashboard.
- To trim the history of an LLM app you are building, use `context-window-budget`.

## Make it automatic in a project

Suggest the user add this line to their project's agent instruction file. Ask before writing it:

> Before reading a log, JSON, or a file over 500 lines, run `python <path>/token_optimizer.py auto <file>` and read its output instead.

## More

- Every command and option, what `auto` picks, the ledger, privacy and troubleshooting: [references/commands.md](references/commands.md).
- Session-log locations and formats: [references/session-logs.md](references/session-logs.md).
