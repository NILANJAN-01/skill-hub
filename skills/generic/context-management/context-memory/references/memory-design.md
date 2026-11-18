# Memory design

## Save or skip

| Situation | Save? | As |
|---|---|---|
| "Stop adding summaries at the end" | Yes | `feedback`, with the reason if given |
| The user confirms an unusual approach worked ("yes, one PR for all of it is right here") | Yes | `feedback`: confirmed approaches matter as much as corrections |
| "I'm a data scientist new to React" | Yes | `user`: changes how explanations are pitched |
| "We ship on 2026-12-01" | Yes | `project`, absolute date, with why it matters |
| "Bugs are tracked in project PAY in the tracker" | Yes | `reference` |
| How the build works, folder layout | No | The repo and its docs already say it |
| "Fixed the null check in `parse()`" | No | Git history has it; task state goes in a handoff note |
| An API key the user pasted | Never | Tell the user it should be rotated if it was exposed |
| A guess about the user's preference | No | Ask, or wait for evidence |

If the user asks to remember something the repo already records, ask what was surprising about it and save that instead.

## Writing a good memory

- **One fact per file.** Two facts in one file cannot be updated or deleted separately.
- **Description = the recall key.** Write it as the words the topic will come up with: "deploy needs approval from the on-call lead", not "deploy info".
- **Lead with the rule, then Why, then How to apply.** The reason lets a later session judge edge cases instead of following the rule blindly.
- **Absolute dates.** "Thursday" is meaningless next month.
- **Link related memories** with `[[other-name]]`. A link to a memory that does not exist yet is fine: it marks something worth writing later.
- **Keep it short.** Most memories are 2 to 6 lines.

## Decay and review

Memories go stale as the code and the team change. Review when:

- `lint --root` reports a memory names a file that no longer exists.
- The memory is a `project` fact whose date has passed (a freeze, a deadline).
- The user contradicts a memory: update or delete it at once, do not keep both.
- The index passes ~100 lines: merge, generalise or drop.

Delete rather than mark obsolete; git (or a backup) is the archive.

## Trust

A memory says what was true when written. Before recommending an action based on one (a file path, a flag, a command), verify it in the current code. If it is wrong, fix the memory as part of the task.

## Scopes

| Scope | Where | Holds |
|---|---|---|
| Per user, all projects | The agent's user-level memory folder | `user` preferences and general `feedback` |
| Per user, one project | A project-specific folder outside the repo | `project` and project `feedback` |
| Shared with the team | The repo's central context file (reviewed in PRs) | Conventions everyone follows: not memory |

## Memory in applications

When building an LLM product that remembers its users:

- **Profile memory** (small, structured): key-value facts per user (name, preferences), stored in your database and injected into the system prompt. Update by key; never let it grow without limit.
- **Episodic memory** (large): past conversations or events, chunked and retrieved by search at question time (see `rag-pipeline`). Store a short summary per session, not raw transcripts.
- **Write policy**: let the model propose memories through a tool call ("save_memory(key, value, reason)"), validate and deduplicate in code, and show users what is stored with a way to delete it.
- **Privacy**: tell users what is remembered, honour deletion requests, never store secrets or sensitive categories without consent, and scope memory per user so one user's facts never reach another.
- **Evaluation**: test recall (is the right memory used?) and restraint (is an irrelevant or outdated memory ignored?) with `llm-evals`.
