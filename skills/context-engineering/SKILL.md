---
name: context-engineering
description: "Design what goes into an AI model's context, centrally: one source-of-truth context file, thin pointers for each tool, layered loading (always, on demand, retrieved), a token budget and session handoff notes. A bundled script checks for duplicated or drifting instruction files and creates the pointers. Use when the user mentions context engineering, context window, instruction files drifting between tools, or wants one shared project context for every AI agent."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the script. The technique applies to any model or agent. Token counts are estimates (characters / 4).
metadata:
  title: "Context engineering: one central context for every agent"
  category: ai-efficiency-tools
---

# Context engineering

The model only knows what is in its context. Context engineering decides what goes in, when and where it is kept. The central idea: keep **one source of truth** and make every tool, session and sub-task load a small, relevant slice of it.

## When to use

- Several AI tools are used on one repo and each has its own copy of the rules, which drift apart.
- The model ignores rules, repeats mistakes or loses the plan in long sessions.
- The user wants a shared project brief, a handoff note or a context budget.

## When NOT to use

- Only a lower token bill is wanted: use `ai-token-saver`.

## The technique: five layers

1. **Central file** (`AGENTS.md`): the only place project rules live. Short: purpose, run/test commands, hard rules, links to details. Aim for under 2000 tokens.
2. **Thin pointers**: each tool's own instruction file only says "read `AGENTS.md`". No rules are copied, so nothing drifts.
3. **Layers by load time**:
   - *Always*: the central file (small and stable, so it can be cached).
   - *On demand*: topic files it links to (`rule/`, `references/`), opened only when the task needs them.
   - *Retrieved*: code and docs found by search at task time, never pre-loaded.
4. **Budget**: decide how much of the window each layer may use; leave most of it for the task itself.
5. **Handoff**: at the end of a task or before a restart, write a 10-line note (goal, done, decisions, next step, open questions) and start the next session from it, not from the old history.

## Procedure

1. **Check** the current state (read-only):
   ```bash
   python scripts/context_hub.py check <project-dir>
   ```
   It reports each pointer as `pointer`, `duplicate`, `divergent` or `missing`, plus the always-loaded size.
2. **Create or tidy the central file.** If a tool file is `divergent`, merge its unique rules into the central file first. Show the user the merge before editing.
3. **Create the missing pointers** (dry run first; it never overwrites a file):
   ```bash
   python scripts/context_hub.py sync <project-dir>
   python scripts/context_hub.py sync <project-dir> --write
   ```
   Ask the user before running with `--write`. Replacing an existing tool file with a pointer is a manual step: confirm it first.
4. **Split what is large.** Move long how-to text out of the central file into linked topic files; keep one line and a link behind.
5. **Add the habits** from [references/layers.md](references/layers.md): write rules as checks, put the stable text first, keep tool output short, write the handoff note.
6. **Re-run `check`** and report before and after sizes and what is still manual.

## Safety rules

- Never write or overwrite files without confirmation. Never put secrets in a context file.
- Do not delete a tool's file to centralize; replace its content with a pointer after the user agrees.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Rules still ignored | They are probably buried: shorten the file, put hard rules first, state each as a testable check |
| `divergent` file | It has rules the central file lacks: merge them, then replace the file with a pointer |
| A tool does not follow the pointer | Put a one-line summary of the top rules in that tool's file next to the pointer |
| Central file keeps growing | Move sections to topic files and link them |
