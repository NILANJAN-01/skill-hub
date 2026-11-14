# AGENTS.md: working on skill-hub

These instructions are for AI coding agents (Claude Code, Antigravity, Devin, Copilot, Cursor, Windsurf, Codex, Gemini CLI, …) that edit this repository. Humans should read [CONTRIBUTING.md](CONTRIBUTING.md), which has the same rules.

## What this repo is

A hub of **agent-neutral** Agent Skills (`skills/<name>/SKILL.md`, open format from agentskills.io), distributed to many AI coding agents. One source folder per skill is installed into each agent's own skills folder by `tools/install.py`, `npx skills`, or the Claude Code plugin marketplace.

## Rules

The rules live in the [`rule/`](rule/README.md) folder. **Read them before editing anything.** Do not copy them back into this file.

- [01-generated-files](rule/01-generated-files.md): never hand-edit generated files
- [02-sources-of-truth](rule/02-sources-of-truth.md): where each kind of change belongs
- [03-skill-content](rule/03-skill-content.md): skills must be agent-neutral
- [04-checks](rule/04-checks.md): run `build_catalog.py`, `validate_skills.py`, `build_catalog.py --check` before finishing
- [05-tooling](rule/05-tooling.md): Python standard library only; `install.py` never writes without confirmation
- [06-pull-requests](rule/06-pull-requests.md): one skill per PR, no secrets or source documents
- [07-common-tasks](rule/07-common-tasks.md): steps for adding a skill, category or agent
- [08-releases](rule/08-releases.md): versioning and release flow
