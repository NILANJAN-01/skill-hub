---
name: context-handoff
description: "Keep long AI agent sessions on track: decide when to compact or restart, write a handoff note pre-filled from git state, resume a task from that note, and give sub-agents short self-contained briefs. A bundled script drafts notes and checks them for missing sections, references to lost history and secrets. Use when a session is long or degrading, before a restart or context compaction, when resuming yesterday's work, or when delegating a sub-task."
license: MIT
compatibility: Needs Python 3.8+ (standard library only) for the script; git is optional (used by draft). Works with any agent or model. Token counts are estimates (characters / 4).
metadata:
  title: "Context handoff: checkpoint, compact, resume and delegate"
  category: context-management-tools
---

# Context handoff

A session's history is the most expensive and least reliable context: it grows with every step, holds dead ends next to decisions, and is lost on restart. This skill replaces history with a short, checked **handoff note** and gives sub-tasks a **brief** instead of the whole conversation.

## When to use

- The session is long, answers are degrading, the model repeats failed attempts or forgets rules.
- The context window is about 70% full, or a compaction or restart is coming.
- Work stops for the day, moves to another person or agent, or starts again after a break.
- A sub-task (search, review, test run) is handed to a sub-agent or a fresh session.

## When NOT to use

- Facts that must survive across many sessions (user preferences, project conventions): use `context-memory`.
- Project rules every session needs: put them in the central context file with `context-engineering`.
- Context limits inside an LLM application you are building: use `context-window-budget`.

## Signals that it is time to checkpoint

| Signal | Action |
|---|---|
| A sub-goal is finished and verified | Write a note, start the next sub-goal fresh |
| ~70% of the window used, or the agent warns about context | Write a note now, before an automatic compaction decides what to keep |
| The same fix is tried twice, or rules are ignored | The history is misleading: note what failed and why, restart from the note |
| Switching task, branch or person | Note, then close the session |

## Procedure: checkpoint

1. **Draft** the note from the repository state (read-only; prints to the terminal):
   ```bash
   python scripts/handoff.py draft --root <project-dir> --goal "<the user's goal>"
   ```
   It fills branch, HEAD, changed files, recent commits and new TODO lines, and leaves `<fill: ...>` markers for Done, Decisions, Next step, Open questions and Verify. Add `--out <file>` to save it; it never overwrites a file.
2. **Fill every marker from what you know**, following [references/templates.md](references/templates.md):
   - *Done*: only what is verified, naming files and functions.
   - *Decisions*: each choice with its reason, and rejected options so nobody retries them.
   - *Next step*: one concrete action that can start without questions.
   - *Verify*: the exact command and its last result.
3. **Check** it as a stranger would read it:
   ```bash
   python scripts/handoff.py check <note.md> --root <project-dir>
   ```
   Fix every ERROR (missing Goal/Done/Next, secrets) and every WARN that matters: phrases such as "as discussed" or "the earlier fix", relative dates, missing files, unfilled markers, notes over ~800 tokens.
4. **Store the note** where the next session will find it, for example `.handoff/<date>-<topic>.md` or the task's ticket. Ask the user before committing it; notes often hold work-in-progress details.

## Procedure: resume

1. Read the newest note first, not the old conversation.
2. Re-run its *Verify* command to confirm the state still holds; check `git status` against its file list.
3. If something differs, say so before continuing. Then start at *Next step*.

## Procedure: compact in place

When the agent has its own compaction or summary command, write the handoff note first and give it as the summary instructions (keep: goal, decisions, next step, verify command, file list; drop: tool output, dead ends after their lesson is recorded). After compaction, check that the summary still contains those five items.

## Procedure: brief a sub-task

A sub-agent sees only its brief. Write it with sections **Goal, Context, Constraints, Done when, Return** (template in [references/templates.md](references/templates.md)) and check it:

```bash
python scripts/handoff.py check <brief.md> --kind brief
```

Ask for a short return format (for example "at most 10 lines: cause, evidence, fix") so the result does not flood the main context.

## Safety rules

- Never put secrets, tokens or personal data in a note or brief; `check` flags common patterns, but read the note too.
- Do not write notes into the repository or commit them without the user's agreement.
- A note records facts. Mark guesses as guesses ("unverified: ...").

## Troubleshooting

| Symptom | Fix |
|---|---|
| The resumed session redoes finished work | *Done* was vague: name files, functions and the verify result |
| It retries a rejected approach | Add the approach and the reason to *Decisions* |
| The sub-agent returns a huge answer | Put a size limit and format in *Return* |
| `draft` shows no git facts | Not a git repository, or git is not on PATH: list changed files by hand |
| Note keeps growing past 800 tokens | Link to logs and files instead of pasting them; keep only the latest state |

## References

- [references/templates.md](references/templates.md): handoff note, sub-task brief, compaction instructions and a resume checklist
