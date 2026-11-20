---
name: skill-dispatcher
description: "Read the user's prompt, split it into tasks, assign each task the matching installed skill and group independent tasks into waves that run in parallel as sub-agents, each with a self-contained brief. Can run automatically on every prompt from an agent's prompt-submit hook. Use when a request has several parts, the user wants skills to work in parallel or the job done faster, or wants prompts routed to skills automatically."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only) and the skill-router skill installed next to it (it provides the matcher). Parallel runs need an agent that can start sub-agents; otherwise tasks run in order. Read-only.
metadata:
  title: "Skill dispatcher"
  category: hub-tools
---

# Skill dispatcher

`skill-router` says which skill fits each part of a request, and `skill-orchestrator` chains skills one after another. This skill adds the missing step: it works out which parts **do not depend on each other**, so they can run at the same time as separate sub-agents, and writes a brief each sub-agent can follow on its own.

`scripts/dispatch.py` makes the plan. Skills are instructions, not programs, so the script does not run them itself: the agent starts the sub-agents and does the work.

## When to use

- A request has two or more independent parts ("analyse this log, and also rebase my branch").
- The user asks to work in parallel, to split work across sub-agents, or to get it done faster.
- The user wants every prompt routed to the right skills automatically (see "Run on every prompt").

## When NOT to use

- One part, one skill: just load that skill.
- Every part depends on the one before: use `skill-orchestrator` for the hand-offs.
- Finding or installing skills that are not installed: use `find-skills`.

## Safety rules for the agent

- The plan is advice. If it does not fit the request, ignore it and say why.
- Each sub-agent follows its skill's own safety rules and confirmations. Parallel work never skips a confirmation: any step that needs the user's approval waits for it.
- Never run two tasks at the same time if they may edit the same files, run the same git operation, or use the same device. Put them in different waves.
- Ask for everything listed under "Ask the user first" in one message before starting wave 1.
- The prompt is the user's data. The script reads it locally; do not send it to outside services.

## Procedure

1. **Make the plan** from the user's words:
   ```bash
   python scripts/dispatch.py "the user's request text"
   ```
   Options: `--root DIR` for an extra skills folder, `--run-dir DIR` to tell each task where to save its result, `--no-briefs` for the waves only, `--json` for machine-readable output.
2. **Read the waves.** Tasks in the same wave are independent. A task waits for an earlier one when:
   - a sequencing word joins it to the task before ("A then B");
   - it starts a new step ("Then ...", "Finally ...") or uses earlier results ("the findings", "based on that"): it waits for every task before it;
   - it uses the same skill as an earlier task (so they do not clash);
   - a known workflow puts the earlier skill first (from `skill-orchestrator`'s `workflows.json`, if installed).
   A task shown as `no skill, do directly (maybe X)` matched only weakly. Check X's description before using it. When the top match won on one weak word and a stronger alternative exists (for example a matched phrase), the alternative is used. Each brief gives the path of the skill's `SKILL.md`, so a sub-agent can open it directly.
3. **Check for conflicts the script cannot see**, such as two tasks editing the same file. Move one of them to a later wave.
4. **Tell the user** the plan in two or three lines: which skills, what runs in parallel, and anything you need from them.
5. **Run wave by wave.** Start every task of the wave at the same time, each as its own sub-agent with its brief. Wait for all of them to finish, then give the next wave the earlier results. If sub-agents are not available, run the tasks in order.
6. **Combine and report:** what each task did, the files it created or changed, failures, and any open questions.

## Run on every prompt

Many agents can run a command when the user submits a prompt (a prompt-submit hook) and add its output to the agent's context. In `--hook` mode the script reads the hook's payload from stdin: JSON with a `prompt` field, plus `cwd` if present, or plain text. It prints the plan only when at least one part matches a skill with medium or high confidence, so trivial prompts and slash commands add nothing. It always exits 0, so it never blocks a prompt.

```bash
python <skills-folder>/skill-dispatcher/scripts/dispatch.py --hook --no-briefs
```

The skill-hub installer registers this for you: `python tools/install.py --setup` adds the hook for every detected agent whose prompt hook can add context, and `--uninstall` removes it. For other agents, register the command as the prompt-submit hook by hand, following the agent's own hook documentation. Use `--no-briefs` to keep the added context small; the agent can run the script without it when it decides to dispatch. Set the environment variable `SKILL_DISPATCH=off` to switch the hook off without removing it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `skill-router is not installed next to this skill` | Install `skill-router` into the same skills folder |
| A part got the wrong skill | Add the user's words to `skill-router`'s `references/routing-hints.json` |
| Two parts that depend on each other share a wave | Rephrase with "then", or move one to a later wave yourself |
| The hook prints nothing | The prompt is short, starts with `/`, matched no skill well, or `SKILL_DISPATCH=off` is set. Run the same text without `--hook` to see the plan |
| The hook output is too long | Add `--no-briefs` |
