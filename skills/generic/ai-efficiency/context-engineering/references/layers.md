# Context layers and habits

## What belongs in each layer

| Layer | Content | Size guide | Changes |
|---|---|---|---|
| Always | Purpose, commands to build/test, hard rules, index of topic files | < 2000 tokens | Rarely |
| On demand | Per-topic rules, architecture notes, checklists | Any, one topic per file | When the topic changes |
| Retrieved | Source code, logs, docs found by search | Only the slice needed | Every task |
| Session | Current goal, decisions, handoff note | ~10 lines | Every task |

## Habits

- Write rules as checks ("run X and fix every error"), not as wishes.
- Put hard rules first and stable text before changing text, so caching can reuse the prefix.
- Say each fact once, in the central file or one topic file, and link to it.
- Prefer a link plus one line over inlining a long document.
- Keep tool output short: first error plus stack, not the whole log.
- Give each sub-task its own small context (goal, files, constraints) rather than the whole history.
- Remove a rule when the code or a check already enforces it.

## Handoff note template

```
Goal:
Done:
Decisions (and why):
Next step:
Open questions:
```

## Where tools read instructions

Names change between versions; confirm in the vendor's docs. Common files: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.windsurfrules`. The script's pointer list is `POINTERS` in `scripts/context_hub.py`.
