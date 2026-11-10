# Contributing to skill-hub

Thanks for adding to the hub! Every skill must pass `tools/validate_skills.py` and appear in the generated catalog.

## Checklist for a new skill

- [ ] The folder is `skills/<name>/`, and `<name>` is kebab-case, at most 64 chars, and unique.
- [ ] `SKILL.md` frontmatter has `name` (equal to the folder name) and `description` (≤1024 chars, says **what** the skill does and **when** to use it, and names the words users type).
- [ ] `metadata.title` and `metadata.category` are set. The category is the focused plugin the skill belongs to.
- [ ] `license` is set. It is required if the content derives from a book, docs or another project. Credit the source in `THIRD_PARTY_NOTICES.md`.
- [ ] The body is actionable: when to use, when not to use, numbered steps with exact commands, safety rules for destructive actions, and troubleshooting.
- [ ] `SKILL.md` is under about 500 lines. Long material goes in `references/`, code in `scripts/`, and templates or data in `assets/`. All links are relative.
- [ ] The skill is listed in at least one plugin in `.claude-plugin/marketplace.json`.
- [ ] `examples/prompts.json` has at least 2 realistic prompts for the skill, written the way a user would ask. Each one should make Claude load the skill.
- [ ] You ran `python tools/build_catalog.py` and committed `catalog.json`, `skills/README.md` and `prompts.html`.
- [ ] `python tools/validate_skills.py` reports 0 errors.
- [ ] You tested it: install the skill locally (`cp -r skills/<name> ~/.claude/skills/`) and check that Claude picks it up for a matching request and does **not** pick it up for an unrelated one.

## Adding a new category

Create a new plugin entry in `.claude-plugin/marketplace.json` (see the existing entries for the shape) and add a display title to `CATEGORY_TITLES` in `tools/build_catalog.py`. If the category is part of a family (e.g. all `git-*`), also add its skills to the family bundle plugin.

## Writing good descriptions

The description is the only thing Claude sees before deciding to load a skill.

- Good: `Rebase a branch onto another, resolve rebase conflicts and clean up history with interactive rebase. Use when the user mentions git rebase, --onto, squash commits, or "rebase onto main".`
- Too vague: `Helps with git.`

## Ground rules

- Do not commit copyrighted source documents such as the PDFs used with `skillforge`.
- Do not put secrets, credentials or private data in skills.
- Skills must not instruct the agent to take destructive actions without user confirmation.
