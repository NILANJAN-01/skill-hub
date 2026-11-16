---
name: ai-token-saver
description: "Cut AI token usage and cost in any AI IDE, coding agent or chat model: audit a project for context waste (huge files, lockfiles, logs, bloated instruction files, missing ignore files) with a bundled script, then apply prompting and session habits that save tokens. Use when the user says tokens, usage limit, context window, cost, bill, rate limit, or asks to make AI use cheaper, shorter or faster."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the audit script. The advice applies to any model or IDE. Token counts are estimates (characters / 4).
metadata:
  title: "AI token saver: audit a project and spend fewer tokens"
  category: ai-efficiency-tools
---

# AI token saver

Tokens are spent on everything sent to the model: instructions, history, files read, tool output and the reply. This skill finds where a project and a workflow waste them and fixes the biggest items first.

## When to use

- The user hits usage or rate limits, or complains about cost or slow replies.
- The context window fills up, or answers degrade in long sessions.
- The user wants to set up a repo so an AI tool reads less.

## When NOT to use

- The user needs exact token counts for billing: use the provider's own tokenizer.

## Procedure

1. **Measure** (read-only, nothing is changed):
   ```bash
   python scripts/token_audit.py <project-dir> --top 10
   ```
   Add `--limit-tokens N` to compare against a budget, `--json` for machine output. Counts are estimates (about +-25%).
2. **Fix the largest items first**, in this order:
   1. Instruction files sent on every request: trim to short rules; link to details instead of inlining them.
   2. Add the right ignore file so heavy folders, lockfiles, logs, build output and data dumps are excluded ([references/tools.md](references/tools.md) lists the file per tool). Show the user the lines to add and ask before writing them.
   3. Huge source files: split them, or work on a function or line range.
3. **Apply session habits** (tell the user which ones you applied):
   - Search first (grep, symbol search), then open only the matching slice. Never read a whole large file or directory "to get context".
   - Be specific: name the file, function and goal. Vague prompts cause exploration.
   - Ask for diffs or only changed parts, not full file rewrites. Ask for short answers when long ones add nothing.
   - Start a fresh session per task. When history is long, summarise the state in 10 lines and restart with only that.
   - Do not paste logs or stack traces whole: keep the first error, its stack and a few lines around it.
   - Keep the stable text (instructions, reference files) first and unchanged between requests so provider caching can reuse it.
   - Use a smaller, cheaper model for simple work (renames, formatting, boilerplate, summaries); keep the large model and deep reasoning modes for hard problems.
   - Batch related questions into one request rather than many tiny turns that each resend history.
4. **Report**: before and after estimated tokens for the files changed, the habits applied, and what the user should still do themselves (for example plan or model settings in their IDE).

## Safety rules

- Do not delete or edit user files to save tokens without confirmation. Prefer ignore entries over deletion.
- Never paste secrets anywhere; just list the file names to exclude.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Audit reports nothing large but usage is high | Long chat history or tool output is the cause: restart the session with a short summary |
| Estimate differs from the provider's count | Expected; code and non-English text tokenize denser than chars/4 |
| Ignored folder still read | Check the tool's own ignore file name and that the pattern matches the path |
