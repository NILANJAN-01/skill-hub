# Contributing to skill-hub

Thanks for adding to the hub! Skills here are installed into many AI coding agents (Claude Code, Google Antigravity, Devin, GitHub Copilot, Cursor, Windsurf, Codex, Gemini CLI), so they must follow the open Agent Skills format and stay **agent-neutral**. Every skill must pass `tools/validate_skills.py` and appear in the generated catalog.

If you use an AI agent to contribute, it follows [AGENTS.md](AGENTS.md).

## Checklist for a new skill

- [ ] The folder is `skills/<name>/`, and `<name>` is kebab-case, at most 64 chars, and unique.
- [ ] `SKILL.md` frontmatter has `name` (equal to the folder name) and `description` (≤1024 chars, says **what** the skill does and **when** to use it, and names the words users type).
- [ ] `metadata.title` and `metadata.category` are set. The category is the focused plugin the skill belongs to.
- [ ] `license` is set. It is required if the content derives from a book, docs or another project. Credit the source in `THIRD_PARTY_NOTICES.md`.
- [ ] The body is actionable: when to use, when not to use, numbered steps with exact commands, safety rules for destructive actions, and troubleshooting.
- [ ] The body is agent-neutral: no single agent's tool names, slash commands or config paths. Scripts are cross-platform. Any real requirement is declared in the `compatibility` field.
- [ ] `SKILL.md` is under about 500 lines. Long material goes in `references/`, code in `scripts/`, and templates or data in `assets/`. All links are relative.
- [ ] The skill is listed in at least one plugin in `.claude-plugin/marketplace.json`.
- [ ] `examples/prompts.json` has at least 2 realistic prompts for the skill, written the way a user would ask. Each one should make Claude load the skill.
- [ ] You ran `python tools/build_catalog.py` and committed all the generated files it changed.
- [ ] `python tools/validate_skills.py` reports 0 errors.
- [ ] You tested it in at least one agent: install it with `python tools/install.py --agent <agent> --skill <name>`, then check that the agent picks it up for a matching request and does **not** pick it up for an unrelated one.

## Pull requests (same convention as anthropics/skills)

- One skill per PR. Tooling changes go in their own PR.
- Title: `Add <name> skill` for new skills, `Update <name> skill: <what changed>` for changes, `Rename <old> skill to <new>` for renames.
- Fill in the PR template checklist. CI validates skills, checks that generated files are fresh, and tests the installer on Linux, Windows and macOS.

## Supporting a new agent

Add an entry to the `AGENTS` dict in `tools/install.py`, using only the vendor's official documentation (link it in `docs`). Fill in its skill folders and its `detect` hints (commands on PATH, app install folders, config folders) so the guided installer can find it. Then run `python tools/build_catalog.py`, which updates the agent tables in `README.md` and `GUIDE.md` and `catalog.json`.

## Adding a new category

Create a new plugin entry in `.claude-plugin/marketplace.json` (see the existing entries for the shape) and add a display title to `CATEGORY_TITLES` in `tools/build_catalog.py`. If the category is part of a family (e.g. all `git-*`), also add its skills to the family bundle plugin.

## Writing good descriptions

The description is the only thing Claude sees before deciding to load a skill.

- Good: `Rebase a branch onto another, resolve rebase conflicts and clean up history with interactive rebase. Use when the user mentions git rebase, --onto, squash commits, or "rebase onto main".`
- Every agent decides from the description alone, so avoid agent-specific phrasing there too.
- Start with the task in the words a user would type, not with where the skill came from. `Undo mistakes: amend the last commit, unstage a file ...` triggers; `Undoing Things playbook extracted from "Pro Git" ...` does not.
- Keep it short: aim for under 300 characters, and put the trigger words in the first 150. Agents give the whole skill list a fixed amount of space, so when many skills are installed, long descriptions get shortened or dropped and those skills stop triggering. `validate_skills.py` warns above 500 characters.
- Too vague: `Helps with git.`

## Ground rules

- Do not commit copyrighted source documents such as the PDFs used with `skillforge`.
- Do not put secrets, credentials or private data in skills.
- Skills must not instruct the agent to take destructive actions without user confirmation.
