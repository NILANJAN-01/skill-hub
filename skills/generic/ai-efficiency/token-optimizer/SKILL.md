---
name: token-optimizer
description: "Cut the tokens an agent reads and track usage: scripts compress logs, outline or slice files, shrink JSON, pack folders under a budget, import session logs (timestamps, skills used) and build an HTML usage dashboard. Use when the user wants to save tokens or see token usage per day or per skill."
license: MIT
compatibility: "Python 3.8+ (standard library only). Works with any agent. File token counts are estimates (chars/4 prose, chars/3.3 code, about +-20%); usage imported from session logs is what the agent recorded. Importing needs an agent that writes JSON or JSONL session logs with usage records; otherwise record usage by hand."
metadata:
  title: "Token optimizer: read less, track usage, see it on a dashboard"
  category: ai-efficiency-tools
---

# Token optimizer

Most tokens are spent reading things: whole logs, whole files and large JSON dumps. This skill keeps those inputs out of the context. Its scripts produce the short version first, so the agent reads that instead. Every reduction is recorded with a timestamp. Session usage can be imported from the agent's own logs, and one command turns it all into a dashboard.

Everything is one script: `scripts/token_optimizer.py` (run it from this skill's folder or give its full path). Optimizer commands print the reduced text to stdout, or to a file with `-o`. They print one line to stderr with the estimated tokens before and after, and record that in the ledger.

## When to use

- Before reading a large log, source file, JSON response or folder. Also when the user says "save tokens", "too much context" or "usage limit".
- The user asks how many tokens they used, when, with which model, or which skills they use most.
- The user wants a token usage dashboard, a daily trend or a report to share.

## When NOT to use

- Auditing a whole project for waste (lockfiles, missing ignore files, bloated instruction files): use `ai-token-saver`.
- Estimating how many tokens one specific skill saves, with vs without it: use `skill-token-meter`. Its ledger appears on this dashboard automatically.
- Trimming the message history of an LLM app you are building: use `context-window-budget`.

## Procedure A: read less (do this before reading a large input)

Pick the command by input type. Read its output, and open the original only for the part you still need.

| Input | Command | What you get |
|---|---|---|
| Log, CI output, test output | `log build.log` | Head, tail, each error or warning with 2 lines of context, and long stack traces cut to their top and bottom. Repeats are folded into counts |
| Source or Markdown file | `outline app.py` | Classes, functions and headings with line ranges and first doc lines, but no bodies |
| One function or range | `slice app.py --symbol Cart.add` or `--lines 120-180` | Only that code |
| JSON / JSONL | `json resp.json` (`--max-items 3 --max-str 200 --drop key1,key2`) | The same structure with long arrays and strings cut |
| JSON you only need to code against | `json resp.json --shape` | The keys and value types only |
| A folder or several files | `pack src/ --budget 8000 --focus "login"` | Small files whole and big files as outlines, all under the budget. Files that mention the focus term are kept whole first. Lockfiles, binaries, build output and git-ignored files are skipped |

Rules:

1. **Search first.** If you know a symbol or string, search for it, then `slice` around it. Use `outline` when you don't know where to look.
2. **Attribute the run.** When the reduction serves another skill's task, add `--skill <that-skill>` so the dashboard credits that skill.
3. **Never hide the cause.** If the compressed log does not show the root error, run `log` again with `--context 10`, or `slice --lines` around the line numbers it shows. Don't guess.
4. Add `--no-record` for runs that should not appear on the dashboard.

## Procedure B: track usage

1. **Import session logs.** This is read-only on the logs and can be run as often as needed, because a re-import replaces earlier entries instead of adding them twice:
   ```bash
   python scripts/token_optimizer.py import --auto --since 30      # known session-log folders, last 30 days
   python scripts/token_optimizer.py import <log file or folder> --agent <label>
   python scripts/token_optimizer.py import --list-dirs           # which folders --auto checks
   ```
   Each session is stored per local day. An entry holds its start and end timestamps, input, output, cache-read and cache-write tokens, model replies, tool calls, models, and the **skills used**. A skill counts as used when a tool call names it, reads its `SKILL.md`, or runs a script from its `scripts/` folder. Duplicated usage records (same message id) and running totals are counted once. Where agents keep their logs, and how to add another location: [references/session-logs.md](references/session-logs.md).
2. **No logs?** Record usage by hand from the agent's usage display:
   ```bash
   python scripts/token_optimizer.py record --skill kotlin-unit-test --input 18000 --output 2500 --task "unit tests for Cart"
   ```
3. **Summary in the terminal:** `python scripts/token_optimizer.py stats --days 7`. This shows totals, the last 14 days, a per-skill table with last-used times, optimizer savings and advice.

## Procedure C: the dashboard

```bash
python scripts/token_optimizer.py dashboard --open                 # writes ~/.skill-hub/token-dashboard.html
python scripts/token_optimizer.py dashboard --days 30 -o report.html
```

The dashboard is one self-contained HTML file. It needs no internet access, it supports light and dark mode, and hovering a mark shows its numbers. It shows:

- **Tiles:** tokens used, output tokens, cache-read share, tool calls, tokens saved, and skills used.
- **Tokens used per day:** input, output, cache read and cache write, stacked. Missing days are shown as gaps.
- **Fresh tokens per day:** the same chart without cache reads, which is where most of the cost is.
- **Tokens saved per day:** by the optimizer and by the skill savings recorded with `skill-token-meter`.
- **How skills are used:** calls, sessions, tokens, savings, and first and last used timestamps for every skill.
- **Optimizer tools** (before, after and % saved), **models and agents**, **advice from your data**, and **recent activity** (the newest 50 entries with timestamps).

Every chart has a "Show as table" view. Tell the user the file path. The file lists only numbers, names and short notes, but it can still reveal which projects and skills they use, so ask before sharing or publishing it anywhere.

## Reading the numbers

- Report which kind of number it is: optimizer and skill savings are **estimates**, and imported usage is **as recorded** by the agent.
- Cache reads are usually most of a long session's tokens and are billed far below fresh input. Quote fresh tokens (input + output + cache write) when talking about cost.
- Skill detection reads tool calls. If you edit skill files, for example in a skill repository, reading a `SKILL.md` to edit it also counts as a use.
- No built-in prices: show money only when the user gives their prices.

## Ledger and privacy

- Ledger: `~/.skill-hub/token-usage.jsonl`. Set another one with `--ledger <file>` or `TOKEN_OPTIMIZER_LEDGER`, for example one per project. The skill-token-meter ledger is read from `~/.skill-hub/token-ledger.jsonl` (or `SKILL_TOKEN_LEDGER`, or `--meter-ledger`). Use `--no-meter` to leave it out.
- The ledger stores numbers, timestamps, skill, tool and model names, file base names, a session id hash and the notes you type. It never stores file or conversation content. Don't put secrets in `--task`.
- `import` reads logs and never changes them. The only files written are the ledger, the dashboard and `-o` outputs.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `import --auto` finds 0 files | Run `import --list-dirs`. If your agent keeps logs elsewhere, pass the folder; if it writes none, use `record` |
| Imported tokens are 0 but tool calls are found | The agent logs no usage fields: record totals by hand |
| A skill is missing from "How skills are used" | It was used without a tool call that names it, reads its `SKILL.md` or runs its scripts (for example, its text was already in context) |
| `log` dropped a line you need | Rerun with `--context 10 --max-repeats 10`, or `slice --lines` |
| `outline` shows no functions | The language is not recognised: use `slice --lines` or search instead |
| Dashboard shows "No data yet" | Run `import` or an optimizer command first; check `--ledger` and `--days` |
