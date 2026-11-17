# Method: how the meter counts

## Token estimates from files

`tokens ≈ characters / 4` for prose (Markdown, text) and `characters / 3.3` for code and markup (Python, JSON, HTML, YAML, subtitles…). Real tokenizers differ by model and language. Expect about ±20% for English and code, and more for other scripts and languages (often higher counts). The same rule applies to both sides of a comparison, so the **difference** is more reliable than either total.

## What `scan` counts

| Column | Content | When the agent pays it |
|---|---|---|
| every session | `name: description` from the frontmatter | Every session where the skill is installed. Agents list all skills so they can pick one |
| when used | The SKILL.md body (after the frontmatter) | When the skill is activated |
| references | Every file in `references/` | Only for the files actually read |
| scripts | Code files in `scripts/`, without `test_*` files or `fixtures/` | Never read normally. This is code the agent does not have to write |

## The `estimate` model

```
WITH    = description + body + references_read + script_output_read        (input)
        + command_tokens                                                     (output, default 150)
WITHOUT = raw_inputs + research                                              (input)
        + code_of_scripts_used × iterations                                  (output)
research = body × research_factor (default 2.0), or --research-tokens
SAVED   = WITHOUT − WITH            (reported for input, output and total)
```

Why these defaults:
- **research_factor 2.0.** A skill condenses know-how that the agent would otherwise get from documentation, web pages or trial and error. Those sources are usually several times longer than the playbook, so ×2 is deliberately low. Set `--research-tokens 0` if the agent already knows the topic well.
- **iterations 1.5.** Code written from scratch is rarely right the first time; 1.5 counts the first version plus fixing half of it. Use 1.0 for a very simple script and 2–3 for tricky parsing or protocol code.
- **command_tokens 150.** A few command lines and their arguments.
- **Not counted on either side:** the final answer the agent writes for the user. It is roughly the same with or without the skill.

## Choosing `--raw` (the most important input)

Pass what the agent would *really* have had to read without the skill:

| Skill type | `--raw` | `--output` |
|---|---|---|
| Log or report analysers (logcat, test results) | The raw log or report | The script's summary |
| Web page or document to a skill | The fetched page or PDF text | The generated SKILL.md and references |
| Media inspectors (image, video, audio) | Usually nothing: the agent cannot read pixels or audio as text. The saving is the code | The script's text report |
| Playbook-only skills (no scripts) | Nothing | Nothing. Savings come only from research, so set `--research-tokens` honestly |

## Measuring for real (A/B protocol)

1. Pick one concrete task and write the prompt down.
2. **Run A:** a fresh session with the skill installed, using that prompt. Note the total tokens from the agent's usage display, or keep the session log.
3. **Run B:** a fresh session with the skill removed or disabled, using the same prompt and the same files. Note the tokens.
4. `measure --with-tokens A --without-tokens B --record` (or `--with-log` / `--without-log`).
5. For a fairer number, repeat 2–3 times and average. Model output varies between runs.

## Session log formats `usage` understands

`usage` reads any JSON or JSONL file. It adds up every object that has token fields, under any of these names:

| Meaning | Field names |
|---|---|
| Input | `input_tokens`, `prompt_tokens`, `promptTokenCount`, `inputTokens` |
| Output | `output_tokens`, `completion_tokens`, `candidatesTokenCount`, `outputTokens` |
| Cache read | `cache_read_input_tokens`, `cachedContentTokenCount` |
| Cache write | `cache_creation_input_tokens` |

When a log repeats the same message (same message id) on several lines, as streaming logs do, it is counted once. Provider definitions differ: some count cached tokens inside "input" and some separately. Compare logs from the same agent and model only.

## The ledger

One JSON object per line in `~/.skill-hub/token-ledger.jsonl` (or `--ledger` / `SKILL_TOKEN_LEDGER`):

```json
{"time": "2026-11-18T10:05:00+05:30", "skill": "yt-lecture-overview", "method": "estimate",
 "task": "overview of a 5-minute talk", "with": 4661, "without": 50827, "saved": 46166,
 "assumptions": {"iterations": 1.5, "research_tokens": 5750, "scripts_counted": ["yt_lecture.py", "..."]}}
```

It is plain text, so you can open it in a spreadsheet, filter it by project or delete lines. `report` reads it and totals the numbers per skill.
