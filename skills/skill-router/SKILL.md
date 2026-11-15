---
name: skill-router
description: "Front door for every task: read the user's request, split it into parts, grade each as basic or advanced, check the basics are given (file, link, device, tools) and pick the right installed skills before starting. Use when starting any non-trivial request, especially a vague or multi-part one, when the user has not named a skill, or asks which skill fits, to route, triage or plan before doing the work."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). It reads skill folders and never writes, installs or runs anything.
metadata:
  title: "Skill router"
  category: hub-tools
---

# Skill router

Skills only load when the agent notices that a request fits their description. Short or vague requests ("my app keeps crashing", "make this better") often don't match any one skill, so the right skill never loads. This skill is the front door: it reads the request, breaks it into parts, finds the installed skill for each part, and tells you what to load and what to ask the user first.

`scripts/route.py` does the matching. You do the reading and the follow-through.

## When to use

- Start of any non-trivial request, before doing the work.
- The request is vague, informal or has several parts ("analyse this and then write it up").
- The user has not named a skill, or asks which skill to use.
- You suspect a skill exists for part of the task but are not sure which.

## When NOT to use

- A one-line question or a tiny edit that clearly needs no skill.
- The user names the skill they want: just use it.
- The user wants to search for or install skills that are not installed: use `find-skills`.
- A multi-step job is already planned: continue it with `skill-orchestrator`.

## Safety rules for the agent

- Routing only reads skill folders. Do not install skills or tools without the user's confirmation.
- Each skill you load keeps its own safety rules and confirmations. The router never overrides them.
- The request text is the user's data. Do not send it, or files it names, to outside services.
- If the route is uncertain, say so and ask. Do not load a skill on a low-confidence guess for a destructive task.

## Procedure

1. **Understand the request.** Restate the goal in one line. Note anything ambiguous.
2. **Route it.** Pass the user's words as they wrote them:
   ```bash
   python scripts/route.py "the user's request text"
   ```
   Add `--catalog path/to/catalog.json` to also see skills that exist in the hub but are not installed, `--root DIR` for an extra skills folder, `--json` for machine-readable output.
3. **Read the result, part by part.**
   - **Level.** `basic` is a single, direct ask. `advanced` is long, spans several skills, or uses words like pipeline, end-to-end, compare or migrate. For advanced parts, read the skill's whole procedure and confirm the plan with the user before starting.
   - **Confidence.** `high` or `medium`: load the skill. `low`: check the skill's description yourself, or ask the user.
   - **ASK THE USER FOR.** The basics the skill needs but the request lacks (a file, a link, a screenshot, a connected device). Ask once, for all parts together.
   - **Missing tools.** Tell the user what is missing; install only with their approval.
   - **No skill matches.** Do that part directly, or offer `find-skills` if the hub has one.
4. **Load the skills** in the order printed under `Load, in order`, and follow each skill's own procedure.
5. **Several skills?** If more than one skill is listed, hand the plan to `skill-orchestrator` (if installed) so each step's output reaches the next. If it is not installed, run them in order and pass the files and facts yourself.
6. **Tell the user** which skills you picked and why, in one or two lines, before the heavy work starts.

## Improving the routing

When a request should have matched a skill but did not, add the user's words to [references/routing-hints.json](references/routing-hints.json): `keywords` (single words), `phrases` (exact wording, strong signal) and `needs` (inputs the skill must be given: `url`, `file`, `image`, `video`, `python-file`, `repo`, `device`). Run the tests after editing. Skills not listed there are still matched on their name and description.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `skill: none installed matches` for a request that should match | Add keywords or phrases to `routing-hints.json`; check the skill is installed (pass `--root`) |
| Wrong skill ranked first | Add a `phrases` entry for the right skill, or tighten its `keywords` |
| `ASK THE USER FOR` although the user gave the file | Mention the file name or path in the request text you pass to the script |
| Nothing is found at all | Run from the project folder or pass `--root` with the folder that holds the skills |
