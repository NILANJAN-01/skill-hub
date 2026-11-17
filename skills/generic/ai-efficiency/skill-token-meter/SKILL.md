---
name: skill-token-meter
description: "Measure how many tokens a skill costs and saves, for any skill and any agent: scan every skill's token cost, estimate tokens with vs without a skill for a real task, measure exact savings from two runs or session logs, and keep one central ledger with a per-skill report. Use when the user asks how many tokens a skill saves, wants to track savings across skills, or asks which skills are worth installing."
license: MIT
compatibility: "Python 3.8+ (standard library only). Works with any agent. Token counts from files are estimates (chars/4 prose, chars/3.3 code, about +-20%); exact numbers come from usage the agent or its session logs report."
metadata:
  title: "Skill token meter: how many tokens each skill saves"
  category: ai-efficiency-tools
---

# Skill token meter

One central tool that answers: **"How many tokens did using this skill save?"** It works with every skill in the hub and every installed skill, and it runs next to whatever skill you just used. Results go into one shared ledger, so savings add up across all skills and sessions.

A skill costs tokens and saves tokens at different moments:

| When | What it costs | What it saves |
|---|---|---|
| Every session it is installed | Its description (name + one paragraph) | — |
| When it is used | Its `SKILL.md` body, any references read, and the script output read | Reading raw inputs (a 5 MB log, a web page) that a script digests; working out the know-how; writing and fixing the code its scripts already contain |

The meter puts numbers on each part. It shows the result as **with the skill** versus **without the skill**, split into input and output tokens. Output tokens usually cost several times more than input tokens.

## When to use

- "How many tokens did that skill save?" or "Is this skill worth it?"
- "Track token savings for every skill I use" (tracking mode, below).
- "Which installed skills cost the most?" or "How many tokens do all my skills' descriptions take?"
- Comparing two real runs of the same task, one with the skill and one without.

## When NOT to use

- To cut a project's general token waste (huge files, lockfiles, bloated instruction files), use `ai-token-saver`.
- To set up shared context files for many tools, use `context-engineering`.

## Rules for honest numbers

1. **Say which kind of number it is.** `estimate` gives a model built from real file sizes with stated assumptions. `measure` gives exact numbers from real runs. Never present an estimate as exact.
2. **Do not inflate.** For `--raw`, pass only the inputs the agent would really have had to read without the skill. Pass `--ran` for the scripts that were actually used. Keep the default assumptions unless you have a reason to change them, and say why if you do.
3. **Negative is a valid answer.** A skill with no scripts and nothing to digest can cost more than it saves on a given task. Report that plainly.
4. **Privacy.** `usage` reads session logs only to add up token counts; never quote their content. The ledger stores numbers, the skill name and an optional short task note, never conversation text.
5. **No built-in prices.** Prices change. Show money only when the user gives their prices (`--price-in`, `--price-out`, per 1M tokens).

## Procedure

Run the commands from this skill's folder, or give the full path of `scripts/token_meter.py`. Add `--json` to any command for machine-readable output.

### 1. Central view: what every skill costs

```bash
python scripts/token_meter.py scan                          # this hub, or the folder the skills are installed in
python scripts/token_meter.py scan --skills-dir <agent skills folder> --sort body
```

For each skill this shows the tokens used **every session** (the description), **when used** (the body), **references** (only if read) and **scripts** (code the agent need not write). It ends with the total description cost of all the skills. That total is the fixed price of having them all installed.

### 2. After using a skill: estimate with vs without

Use the real files from the task you just finished:

```bash
python scripts/token_meter.py estimate --skill <name> \
    --raw <inputs the agent would otherwise read itself> \
    --output <script output files the agent read> \
    --read <reference files the agent read, or: all> \
    --ran <script names actually used> \
    --record --task "short note"
```

- **With the skill:** description, SKILL.md body, references read and script output read (input), plus the commands typed (output, default 150).
- **Without the skill:**
  - the raw inputs read directly (input);
  - learning the know-how: the body × 2 by default (`--research-factor`), or a number you set with `--research-tokens` (input);
  - writing equivalent code for the scripts used, × 1.5 by default for writing plus fixing (`--iterations`) (output).

The output lists every part, the saving (tokens and %, input and output), how many sessions of the description's cost one use pays for, and the assumptions. With `--price-in` and `--price-out` it also shows money saved.

Example: for a YouTube lecture overview, `--raw transcript.json --output transcript.txt` with that skill's four scripts gave about 4,700 tokens with the skill and about 50,800 without it. Most of the difference is code the agent did not have to write.

### 3. Exact numbers: measure two real runs

Run the same task twice, in fresh sessions: once with the skill and once without it (uninstall or disable it for that run). Then use either:

```bash
python scripts/token_meter.py measure --skill <name> --with-tokens 18500 --without-tokens 61200 --record
python scripts/token_meter.py measure --skill <name> --with-log run_with.jsonl --without-log run_without.jsonl --record
```

- The token numbers come from the agent's own usage display.
- Session logs work when the agent writes JSON or JSONL logs that contain usage records. Several common field-name formats are recognised, and records repeated with the same message id are counted once. `python scripts/token_meter.py usage <log>` shows the totals of one log.

Cache reads are usually most of a long session's tokens, and providers bill them well below normal input. So report the breakdown, not only the total.

### 4. Report: totals per skill

```bash
python scripts/token_meter.py report
```

This shows, per skill: uses, tokens saved, average per use, % saved, and how many results were measured or estimated. The biggest savers come first. The ledger is `~/.skill-hub/token-ledger.jsonl`; `--ledger <file>` or `SKILL_TOKEN_LEDGER` sets another one (for example, one per project).

## Tracking mode (runs alongside every skill)

When the user asks to track savings, for example "track tokens saved for every skill this session", keep going with the normal work. After **each** task where another skill was used:

1. Run `estimate` for that skill with that task's real files, and add `--record --task "<what was done>"`.
2. Add one line to your reply: "<skill> saved about N tokens (estimate)".

At the end, or when asked, run `report` and show the table. Do not run the meter for tasks that used no skill, and do not hold up the user's actual work to measure it.

More detail on the formulas, how to choose `--raw`, accuracy, and the A/B measurement protocol is in [references/method.md](references/method.md).
