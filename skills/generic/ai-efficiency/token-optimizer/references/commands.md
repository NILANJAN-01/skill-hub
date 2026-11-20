# token-optimizer: every command in detail

All commands: `python scripts/token_optimizer.py <command> ...`. Add `--json` for machine output, `-o FILE` to write the result to a file, `--no-record` to keep a run off the ledger, and `--skill NAME` to credit the run to the skill whose task it served.

## What `auto` picks

| Input | Method | Result |
|---|---|---|
| A folder or several files | `pack` | Small files whole, big ones as outlines, all under `--budget` (default 8000). Files containing a `--focus` term are kept whole first. Lockfiles, binaries, build output and git-ignored files are skipped |
| File up to `--min-tokens` (default 1500) | none | Printed unchanged and not recorded: shrinking it would save nothing |
| JSON / JSONL | `json` | Same structure; arrays cut to 3 items and strings to 200 characters |
| JSON still over `--budget` after that | `json-shape` | The keys and value types only |
| Log-like text (`.log`, `log` in the name, or 30% of lines start with a timestamp or level) | `log` | Head, tail, each error or warning with 2 lines of context, and long stack traces cut to their top and bottom. Repeats are folded into counts |
| Source code or Markdown with declarations or headings | `outline` | Functions, classes and headings with line ranges and first doc lines, but no bodies |
| Any other text | `log` | Head, tail and problem lines |

Binary files are refused.

## The single methods (when you need their options)

| Command | Options |
|---|---|
| `log FILE` | `--context N` (lines around each problem, default 2), `--max-repeats N` (default 3), `--head N`, `--tail N` |
| `outline FILE` | none |
| `slice FILE` | `--symbol NAME` (`Class.method` works; close names are suggested on a miss) or `--lines A-B` |
| `json FILE` | `--max-items N`, `--max-str N`, `--drop key1,key2`, `--shape`, `--indent N` |
| `pack PATH...` | `--budget N`, `--focus TERM` (repeatable), `--no-git` |

Rules:

1. **Search first.** When you know a symbol or string, search for it and `slice` around it. Use `outline` when you don't know where to look.
2. **Never hide the cause.** If the reduced log does not show the root error, rerun `log --context 10 --max-repeats 10`, or `slice --lines` around the line numbers it shows. Don't guess.

## Tracking usage

```bash
python scripts/token_optimizer.py import --auto --since 30          # known session-log folders
python scripts/token_optimizer.py import <log file or folder> --agent <label>
python scripts/token_optimizer.py import --list-dirs               # folders --auto checks
python scripts/token_optimizer.py record --skill kotlin-unit-test --input 18000 --output 2500 --task "unit tests"
python scripts/token_optimizer.py stats --days 7
```

- `import` only reads the logs. Re-importing replaces earlier entries rather than adding them twice. Each session is stored per local day: start and end time, input, output, cache-read and cache-write tokens, model replies, tool calls, models, and the skills used.
- A skill counts as **used** when a tool call names it, reads its `SKILL.md` or runs a script from its `scripts/` folder. Editing skill files, for example in a skill repository, counts too.
- Log formats and locations: [session-logs.md](session-logs.md).

## The dashboard

`dashboard --import --open` refreshes from the session-log folders (changed in the last `--days`, default 30) and opens `~/.skill-hub/token-dashboard.html`. Use `-o FILE` to write it elsewhere, `--days N` to limit the period, and `--title`.

It is one self-contained HTML file. It needs no internet access, supports light and dark mode, and hovering a mark shows its numbers. Every chart has a table view. It contains:

- **Tiles:** tokens used, output tokens, cache-read share, tool calls, tokens saved, and skills used.
- **Tokens used per day:** input, output, cache read and cache write.
- **Fresh tokens per day:** without cache reads, which is where most of the cost is.
- **Tokens saved per day:** by the optimizer and by skill-token-meter.
- **How skills are used:** calls, sessions, tokens, savings, and first and last used times.
- **Optimizer tools**, **models and agents**, **advice from the data**, and **recent activity** (the newest 50 entries with timestamps).

## Reading the numbers

- Optimizer and skill savings are **estimates** (chars/4 for prose, chars/3.3 for code, about ±20%). Imported usage is **as recorded** by the agent. Say which kind you are quoting.
- Cache reads are usually most of a long session's tokens and are billed far below fresh input. Quote fresh tokens (input + output + cache write) when talking about cost.
- There are no built-in prices. Show money only when the user gives their prices.

## Ledger and privacy

- Ledger: `~/.skill-hub/token-usage.jsonl`. Set another one with `--ledger` or `TOKEN_OPTIMIZER_LEDGER`, for example one per project. The skill-token-meter ledger comes from `~/.skill-hub/token-ledger.jsonl` (or `SKILL_TOKEN_LEDGER` or `--meter-ledger`). Use `--no-meter` to leave it out.
- The ledger stores numbers, timestamps, skill, tool and model names, file base names, a session id hash and the notes you type. It never stores file or conversation content. Don't put secrets in `--task`.
- The dashboard shows which projects and skills someone uses. Ask before sharing or publishing it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `import --auto` finds 0 files | Run `import --list-dirs`. Pass the agent's log folder, or use `record` if it writes none |
| Imported tokens are 0 but tool calls are found | The agent logs no usage fields: record totals by hand |
| A skill is missing from "How skills are used" | It was used without a tool call that names it, reads its `SKILL.md` or runs its scripts |
| `auto` printed a file unchanged | It is under `--min-tokens`; lower that only if the file is really costing tokens |
| `auto` chose the wrong method | Run the single method (`log`, `outline`, `json`) directly |
| `outline` shows no functions | The language is not recognised: use `slice --lines` or search instead |
| Dashboard shows "No data yet" | Run `dashboard --import`, or check `--ledger` and `--days` |
