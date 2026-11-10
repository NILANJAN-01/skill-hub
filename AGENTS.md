# AGENTS.md: working on skill-hub

These instructions are for AI coding agents (Claude Code, Antigravity, Devin, Copilot, Cursor, Windsurf, Codex, Gemini CLI, …) that edit this repository. Humans should read [CONTRIBUTING.md](CONTRIBUTING.md), which has the same rules.

## What this repo is

A hub of **agent-neutral** Agent Skills (`skills/<name>/SKILL.md`, open format from agentskills.io), distributed to many AI coding agents. One source folder per skill is installed into each agent's own skills folder by `tools/install.py`, `npx skills`, or the Claude Code plugin marketplace.

## Golden rules

1. **Never hand-edit generated files**: `catalog.json`, `skills/README.md`, `prompts.html`, and the `<!-- agents:start/end -->` block in `README.md`. Change the sources, then run `python tools/build_catalog.py`.
2. **Sources of truth:**
   - The skill itself: `skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`).
   - Which plugin/category a skill is in: `.claude-plugin/marketplace.json`.
   - Example prompts: `examples/prompts.json` (at least 2 per skill).
   - Which folders each agent reads: the `AGENTS` dict in `tools/install.py`. Only change it from the vendor's official docs, and update its `docs` link.
   - Category display titles: `CATEGORY_TITLES` in `tools/build_catalog.py`.
3. **Skills must be agent-neutral.** Don't name one agent's tools, slash commands or config files in a skill body. If a skill truly depends on an environment, declare it in the `compatibility` frontmatter field.
4. **Before finishing any change**, run these and fix every error:
   ```bash
   python tools/build_catalog.py
   python tools/validate_skills.py
   python tools/build_catalog.py --check
   ```
5. **Tooling is Python standard library only** (3.8+ for `install.py`). Don't add dependencies to `tools/`.
6. **One skill per pull request.** Title it `Add <name> skill` or `Update <name> skill: <what changed>`. Tooling changes go in their own PR.
7. Don't commit source documents (PDFs, books) or secrets. Respect licenses: derived content needs a `license` field and an entry in `THIRD_PARTY_NOTICES.md`.

## Common tasks

| Task | Steps |
|---|---|
| Add a skill | `cp -r template skills/<name>` → write `SKILL.md` → add to a plugin in `marketplace.json` → add prompts → rebuild + validate |
| Add a category | New plugin entry in `marketplace.json` + title in `CATEGORY_TITLES` |
| Support a new agent | Add an entry to `AGENTS` in `tools/install.py` from official docs → rebuild (updates README matrix, catalog, website) |
| Generate skills from a PDF | Follow `skills/skillforge/SKILL.md` |
| Preview the site | `python -m http.server`, then open http://localhost:8000 |
