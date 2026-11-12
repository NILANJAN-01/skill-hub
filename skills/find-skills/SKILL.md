---
name: find-skills
description: "Search the skill-hub catalog for a skill that fits the task and install it into the agent in use. Use when the user asks \"is there a skill for X\", wants to find, browse, list or install skills, or asks what skill-hub offers."
license: Complete terms in the repository README
compatibility: Works in any agent. Installing writes into the agent's skills folder (needs file-system access and Python 3.8+, or Node for npx); reading the online catalog needs web access.
metadata:
  title: "Find & install hub skills"
  category: hub-tools
---

# Find & install skills from skill-hub

skill-hub is a centralized collection of Agent Skills in the open `SKILL.md` format. The same skill folder works in every supported agent. Only the install folder differs.

The machine-readable index is `catalog.json` at the repository root:

- Local clone: `<repo>/catalog.json`
- Online: `https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/catalog.json`
- Human-readable list: `https://github.com/NILANJAN-01/skill-hub/blob/main/skills/README.md` (example prompts: `examples/PROMPTS.md`)

## Catalog format

```json
{
  "plugins":    [{ "name": "git-branching", "description": "...", "skills": ["git-rebasing", "..."] }],
  "categories": [{ "name": "git-branching", "title": "Git: branching & merging", "count": 7 }],
  "agents":     [{ "id": "cursor", "name": "Cursor", "project": ".cursor/skills", "global": "~/.cursor/skills",
                   "also_reads": [".claude/skills", ".codex/skills"] }],
  "skills": [{
    "name": "git-rebasing", "title": "Rebasing", "category": "git-branching",
    "description": "...", "plugins": ["git-branching", "git-skills"], "examples": ["..."],
    "path": "skills/git-rebasing", "license": "..."
  }]
}
```

## Procedure

1. **Load the catalog.** Read the local `catalog.json` if you are inside a skill-hub clone. Otherwise fetch the online URL. If you cannot read files or the web, send the user to the human-readable list instead.
2. **Match the task.** Compare the user's words, commands and error messages with each skill's `name`, `title`, `description` and `examples`. Prefer the most specific skill. For example, use `git-rebasing` rather than the broad `git-pro` reference.
3. **Present 1–5 candidates** with name, title, a one-line purpose, and the smallest plugin that contains each one (the first entry in `skills[].plugins`). If nothing fits, say so. Do not force a match.
4. **Work out the target agent.** Use the agent you are running in. If you are unsure, or the user works with several agents, ask. Look up its `id` and folders in `catalog.agents`.
5. **Install** after the user confirms. Show the plan first.
   - **Hub installer** (Python only, works for every agent). Preview with `--dry-run`, show the user the plan it prints, and run it for real with `--yes` only after they agree:
     ```bash
     curl -fsSL https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/tools/install.py \
       | python3 - --agent <agent-id> --skill <skill-name> --dry-run
     # then the same command with --yes instead of --dry-run
     # whole category:        --plugin <plugin-name>      everything: --all
     # every installed agent:  --agent detected            (--detect shows which they are)
     # for the user, not the project:  --global
     ```
     Inside a skill-hub clone, run `python tools/install.py ...` instead. If the user is at a terminal themselves, they can run the installer with **no options** for a guided install that asks question by question.
   - **`skills` CLI** (needs Node): `npx skills add NILANJAN-01/skill-hub --skill <skill-name> -a <agent>`
   - **Manual:** copy `skills/<skill-name>/` into the agent's `project` folder (shared with the team via git) or its `global` folder (for this user only).
   - **Upload UIs** (web apps without a skills folder): build a zip with `install.py --zip dist --skill <skill-name>` and upload it.
6. **Use it.** Most agents pick up new skills on the next session or reload. If the task is still in progress, read the installed skill's `SKILL.md` now and follow it.

## Rules

- Never write into the user's home or project folders without showing the command and target path first.
- Mention the skill's `license` when it is not permissive. For example, the `git-*` skills are CC BY-NC-SA 3.0 (non-commercial, share-alike).
- Don't install every skill "just in case". Each installed skill adds its description to the agent's context.
- Do not install a skill into several folders that the same agent reads. That creates duplicates. The hub installer avoids this automatically.
