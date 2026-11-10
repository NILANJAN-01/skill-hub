---
name: find-skills
description: Search the skill-hub catalog for an Agent Skill that fits the current task and install it into Claude Code (as a plugin or by copying the folder). Use when the user asks "is there a skill for X", wants to find, browse, list, recommend or install skills, asks what skills or plugins skill-hub offers, or when a task would clearly benefit from a specialized playbook (e.g. a tricky git rebase, writing a git hook, generating skills from a PDF).
license: Complete terms in the repository README
metadata:
  title: "Find & install hub skills"
  category: hub-tools
---

# Find & install skills from skill-hub

skill-hub is a centralized collection of Agent Skills. Its machine-readable index is `catalog.json` at the repository root:

- Local clone: `<repo>/catalog.json`
- Online: `https://raw.githubusercontent.com/NILANJAN-01/skill-hub/main/catalog.json`
- Website: `https://nilanjan-01.github.io/skill-hub/`

## Catalog format

```json
{
  "name": "skill-hub",
  "repository": "https://github.com/NILANJAN-01/skill-hub",
  "plugins":  [{ "name": "git-branching", "description": "...", "skills": ["git-rebasing", "..."] }],
  "categories": [{ "name": "git-branching", "title": "Git: branching & merging", "count": 7 }],
  "skills": [{
    "name": "git-rebasing", "title": "Rebasing", "category": "git-branching",
    "description": "...", "plugins": ["git-branching", "git-skills"],
    "path": "skills/git-rebasing", "license": "...", "source": "...", "pages": "101-110"
  }]
}
```

## Procedure

1. **Load the catalog.** Read the local `catalog.json` if you are inside a skill-hub clone. Otherwise fetch the online URL.
2. **Match the task.** Score skills by how well the user's words, commands and error messages match each skill's `name`, `title` and `description`. Descriptions list trigger topics ("Use when the user asks about …") and commands ("or mentions …"). Prefer the most specific skill. For example, use `git-rebasing` rather than the broad `git-pro` reference.
3. **Present 1–5 candidates** with name, title, one-line purpose and the plugin that contains each. If nothing fits, say so. Do not force a match.
4. **Install** in the way the user prefers:
   - **Plugin marketplace (Claude Code)**, which installs a curated bundle:
     ```
     /plugin marketplace add NILANJAN-01/skill-hub
     /plugin install <plugin-name>@skill-hub
     ```
     Pick the smallest plugin that contains the skill (see `skills[].plugins`). Only suggest big bundles such as `git-skills` when the user wants everything.
   - **Copy a single skill**, which needs no plugin system:
     ```bash
     git clone --depth 1 https://github.com/NILANJAN-01/skill-hub.git
     cp -r skill-hub/skills/<name> ~/.claude/skills/          # personal, all projects
     cp -r skill-hub/skills/<name> <project>/.claude/skills/  # this project only
     ```
   - **Claude.ai / API**: zip the skill folder and upload it as a custom skill.
5. **Use it.** After install, the skill loads automatically when a task matches its description. If the task is still in progress, read that skill's `SKILL.md` now and follow it.

## Rules

- Always show the user the install command and the target path before copying files into their home or project directory.
- Mention the skill's `license` when it is not permissive. For example, the `git-*` skills are CC BY-NC-SA 3.0 (non-commercial, share-alike).
- Don't install every skill "just in case". Each installed skill adds its description to the agent's context.
