---
name: context-memory
description: "Give an AI agent memory that lasts across sessions: decide what is worth remembering, store one fact per Markdown file with a short index, update instead of duplicating, and prune stale or wrong memories. A bundled script lints a memory folder (missing index entries, duplicates, secrets, relative dates, files that no longer exist) and builds the index. Use when the user says remember this, asks the agent to stop forgetting preferences, or wants to set up, audit or clean agent memory."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the script. The format works with any agent that can read and write files; agents with a built-in memory feature can follow the same rules.
metadata:
  title: "Context memory: durable, small and correct agent memory"
  category: context-management-tools
---

# Context memory

Memory is context that survives the session. It pays off only if it stays **small** (the index is loaded every time), **true** (a wrong memory is worse than none) and **findable** (one fact per file, described in one line). This skill sets up that store and keeps it healthy.

## When to use

- The user says "remember...", "from now on...", "stop doing X", or corrects the agent in a way that will matter again.
- The agent keeps relearning the same preference, convention or project fact every session.
- An existing memory folder is large, contradictory or out of date.

## When NOT to use

- Rules every contributor and tool must follow: put them in the project's central context file (`context-engineering`). Memory is for what the repository does not record.
- Task state for the next session: write a handoff note (`context-handoff`).
- Memory inside an LLM product you are building (vector stores, per-user profiles): see [references/memory-design.md](references/memory-design.md#memory-in-applications), then `rag-pipeline`.

## What to remember

| Type | Holds | Example |
|---|---|---|
| `user` | Who the user is: role, expertise, preferences | "Prefers terse replies; reads diffs directly" |
| `feedback` | How to work, from corrections and confirmed approaches, with **Why** | "Never force-push shared branches. Why: lost commits on 2026-10-02" |
| `project` | Goals, deadlines, constraints not in the code, with **Why** | "Merge freeze 2026-12-01 to 2026-12-05 for the mobile release" |
| `reference` | Where things live outside the repo | "Release dashboard: <internal URL>" |

Do **not** store: what the code, git history or project docs already say; one-off task details; guesses; secrets or credentials; personal data the user has not asked you to keep.

## Layout

```
<memory-dir>/
  MEMORY.md                    # index: one line per memory, loaded every session
  no-force-push.md             # one fact per file
  prefers-short-answers.md
```

Each file:

```markdown
---
name: no-force-push
description: never force-push shared branches; ask first
metadata:
  type: feedback
---

Never force-push `main` or any branch others use; ask the user first.

**Why:** a force push on 2026-10-02 erased a teammate's commits.

**How to apply:** push a new branch for rewritten history. Related: [[branch-naming]].
```

Index line (one per memory):

```markdown
- [No force push](no-force-push.md) — never force-push shared branches; ask first
```

Where the folder lives depends on the agent; use its documented memory location if it has one, otherwise a folder the user chooses (outside the repository for personal memories).

## Procedure: save a memory

1. **Decide** it is worth keeping (table above). If unsure, ask the user.
2. **Look for an existing memory** on the same subject (read the index, search the folder). Update that file instead of adding a near-duplicate; delete one that turned out to be wrong.
3. **Create** the file (dry run first; it never overwrites):
   ```bash
   python scripts/memory_lint.py new <memory-dir> --name <slug> --type feedback --description "<one line>"
   python scripts/memory_lint.py new <memory-dir> --name <slug> --type feedback --description "<one line>" --write
   ```
   Replace the `<...>` markers. Convert "yesterday" or "next week" to absolute dates.
4. **Index** it:
   ```bash
   python scripts/memory_lint.py index <memory-dir> --write
   ```
5. Tell the user in one line what was saved.

## Procedure: audit and clean

1. **Lint** (read-only):
   ```bash
   python scripts/memory_lint.py lint <memory-dir> --root <project-dir>
   ```
   ERRORs: files missing from the index (never recalled), index lines to deleted files, missing frontmatter, duplicate names, stored secrets. WARNs: near-duplicate facts, feedback/project without *Why*, relative dates, memories naming files that no longer exist, long files, a long or chatty index.
2. **Fix** in this order: remove secrets; merge duplicates; verify memories that name missing files (update or delete); add *Why* lines; shorten the index.
3. Show the user every deletion or merge before doing it.
4. Re-run `lint` until it reports OK.

## Procedure: use memories

- Read the index at the start of a session; open a memory file only when its description is relevant.
- A memory is a claim about the past. Before acting on one that names a file, function or flag, check it still exists.
- If the user says a memory is wrong, fix or delete it at once.

## Safety rules

- Never store secrets, tokens, passwords or other people's personal data.
- Memories are private to the user: never send them to external services.
- Do not delete or rewrite memories the user did not ask about without showing the change first.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The agent ignores a memory | It is not in the index, or its description does not match how the topic comes up: rewrite the description |
| Two memories contradict | Keep the newer one if confirmed, delete the other, note the change in the kept file |
| Index is huge | Merge related memories, drop ones the repo now records, keep each line under ~150 characters |
| `no frontmatter` error | The file must start with `---`, then `name`, `description`, `type`, then `---` |

## References

- [references/memory-design.md](references/memory-design.md): save/skip rules with examples, decay and review policy, linking, and memory in LLM applications
