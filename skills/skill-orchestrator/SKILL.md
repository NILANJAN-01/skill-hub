---
name: skill-orchestrator
description: "Combine several installed skills to finish a multi-step task: find which skills are installed, pick the right ones, check they can run (adb, Python packages), run them in order and pass each result to the next. Use when a task needs more than one skill, or the user asks which skills to use, to chain skills, or to plan and track a multi-skill job."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). It reads skill folders and writes only inside a run folder you choose.
metadata:
  title: "Skill orchestrator"
  category: hub-tools
---

# Skill orchestrator

Skills do not call each other. This skill makes them work together: it gives you a picture of what is installed, a plan that chains skills in a sensible order, and a run folder where each step records its output files for the next step to read.

`scripts/orchestrate.py` does the bookkeeping. You do the thinking and run each skill's own procedure.

## When to use

- The task needs two or more skills (for example: analyse a log, then write a report about it).
- The user asks "which skill should I use?", "chain these skills", or "do this end to end".
- You need to check that a skill's tools are present before starting (adb, a JDK, ffmpeg, OpenCV, Docker).
- A long multi-step job needs progress tracking across steps or sessions.

## When NOT to use

- One skill clearly covers the task: just use it.
- The user wants to find a skill that is not installed or install one: use `find-skills`.

## Safety rules for the agent

- Each step is run by following that skill's own instructions, including its safety rules and confirmations. The plan never overrides them.
- The script only reads skill folders. It writes only `run.json` inside the run folder the user agreed to. Never write elsewhere with it.
- Do not install skills or tools without the user's confirmation. Missing requirements are reported, not fixed silently.
- Hand-off files can contain logs, CVs or code. Keep them in the run folder, and don't send them to outside services.

## Procedure

1. **See what is installed.**
   ```bash
   python scripts/orchestrate.py scan
   ```
   It looks in every known agent's project and user skill folders, plus any `--root DIR` you pass.
2. **Plan the task.** Give the user's request in their words:
   ```bash
   python scripts/orchestrate.py plan "analyse this logcat and write a bug report"
   ```
   It picks a named workflow if one fits (list them with `workflows`), otherwise the best matching skill, and marks each step `ok`, `check requirements` or `NOT INSTALLED`. To see raw rankings: `python scripts/orchestrate.py match "task text"`.
3. **Check requirements** for the chosen skills and tell the user what is missing:
   ```bash
   python scripts/orchestrate.py check android-logcat-analyzer professional-writing
   ```
4. **Agree the plan with the user** (steps, which files go in and out, anything missing). If a skill is not installed, stop and offer to install it.
5. **Start a run folder** and work through the steps in order:
   ```bash
   python scripts/orchestrate.py run init runs/crash-report --workflow android-crash-report --task "why does the app crash?"
   ```
   For each step: open that skill, follow it, passing it the previous steps' output files; save its result in the run folder, then record it:
   ```bash
   python scripts/orchestrate.py run done runs/crash-report 1 --output 01-logcat-findings.md --note "3 crashes, 1 ANR"
   ```
   `run status runs/crash-report` shows what is done and what to do next, and works across sessions.
6. **Report back:** which skills ran, the files produced (with paths), what failed or was skipped, and suggested next steps.

## Hand-off conventions

- Name outputs `NN-what-it-is.ext` in the run folder, so the order is obvious.
- Put the facts the next skill needs (findings, decisions, open questions) in a text or Markdown file, not only in the chat.
- Never edit an earlier step's output to make a later step pass. If an earlier result is wrong, redo that step.
- Keep user data (logs, CVs) out of file names and notes beyond what is needed.

## Workflows included

See [references/workflows.json](references/workflows.json). Run `python scripts/orchestrate.py workflows` for the list. Examples: `android-crash-report` (logcat analysis then a report), `android-ui-test-suite` (locators then Kotlin tests), `repo-to-blog` (repo reading then a post), `docs-to-skill` (web page to skill, then register it). To add one, append an entry with `steps` (each with `skill`, `purpose`, `input`, `output`, optional `input_from`) and run the tests.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `0 skill(s) found` | Run from the project folder, or pass `--root` with the folder that holds the skills |
| Plan shows `NOT INSTALLED` | Install that skill (see `find-skills`) or choose another workflow |
| `check` reports a missing tool | Tell the user; install it only with their approval, or skip the feature that needs it |
| `Step N is not done yet` | Steps are recorded in order; finish or redo the earlier step |
| No workflow matches | The plan falls back to the best single skill; name steps yourself with `run init --skills a,b,c` |
| Output file not found | Save the file in the run folder first, then record it |
