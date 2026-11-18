# Handoff templates

All templates are plain Markdown. `scripts/handoff.py check` recognises the section names below as `## Heading` lines or as `Name:` lines.

## Handoff note (`--kind handoff`)

Required: Goal, Done, Next step. Recommended: Decisions, Open questions, Verify, and file names somewhere in the note.

```markdown
# Handoff (2026-11-18)

## Goal
<The outcome the user asked for, in one or two sentences. Include the acceptance criteria if any.>

## Done
- <Verified result, with `path/to/file.py` and function names>
- <Uncommitted or partial work, clearly marked as partial>

## Decisions
- <Choice> because <reason>. Rejected: <option> because <reason>.

## Next step
<One concrete action, e.g. "Add a test for empty input in `tests/test_export.py`, then make it pass.">

## Open questions
- <Question for the user, or "None">

## Verify
`<command>` -> <result on 2026-11-18, e.g. "42 passed, 1 failing: test_unicode">
```

Good habits:

- Facts over narrative: no "first I tried..., then...". Record the lesson, not the story.
- Absolute dates (2026-11-18), never "yesterday".
- Name things: "the bug" means nothing to a new session; "`parse_date` returns None for ISO weeks" does.
- Link logs and long outputs by path; do not paste them.
- Keep it under ~800 tokens. If it is longer, the task should be split.

## Sub-task brief (`--kind brief`)

Required: Goal, Context, Done when, Return. Recommended: Constraints, file names.

```markdown
## Goal
<One sentence: what to find, decide or produce.>

## Context
<Only what this sub-task needs: relevant files, facts already known, what was ruled out.>

## Constraints
<Read-only? Which folders are off limits? Time or size limits? Tools not to use?>

## Done when
<A checkable condition, e.g. "you can name the failing call and show its timing".>

## Return
<Format and size, e.g. "at most 10 lines: cause, evidence (file:line), one suggested fix".>
```

Briefs are for any delegated work: a sub-agent, a parallel session, a teammate, or a fresh session of the same agent.

## Compaction instructions

When the agent offers a compaction or summary step that accepts instructions, give it:

```text
Summarise this session for a fresh start. Keep exactly:
1. Goal and acceptance criteria.
2. Decisions with reasons, and approaches that failed with the reason.
3. Files changed or relevant, with one line each.
4. The verify command and its latest result.
5. The single next step and open questions.
Drop tool output, file contents, and exploration that led nowhere (keep only its lesson).
Use absolute dates. Maximum 400 words.
```

## Resume checklist

1. Read the newest handoff note (and the project's central context file).
2. Run the *Verify* command; compare with the recorded result.
3. Compare `git status` and the branch with the note.
4. Report any difference to the user before continuing.
5. Start at *Next step*. Update the note when the next checkpoint comes; do not append a diary.

## Where to keep notes

| Place | Good for |
|---|---|
| `.handoff/<date>-<topic>.md` (git-ignored) | Personal, short-lived notes |
| The ticket or pull request description | Notes others will read |
| A memory store (`context-memory`) | Only the lasting lessons, not the task state |
