# Architecture and commands

Read this when you need to know how the hub fits together or which command does a chore. The rules themselves are in [`rule/`](rule/README.md); this file does not repeat them.

## Commands

Everything is Python standard library only; there is no build step or package install. Use `tools/hub.py` for repository chores instead of doing them by hand: it applies the rules for you and prints only what needs attention.

```bash
# Before finishing any change: rebuild generated files, then run everything CI runs, in parallel.
# Prints one line per step group, the output of failed steps only, and the command to rerun each.
python tools/hub.py check --changed      # while iterating: only tests affected by changes since HEAD
python tools/hub.py check                # everything (what CI runs)

# Add a skill: copies template/, writes frontmatter, registers it in marketplace.json
# (+ CATEGORY_TITLES for a new plugin) and examples/prompts.json, rebuilds. Then fill the TODOs.
python tools/hub.py new-skill <area>/<group>/<name> --plugin <plugin> --description "..." --prompt "..." --prompt "..."
python tools/hub.py new-skill <area>/<group>/<name> --plugin <new-plugin> --plugin-title "Title" --plugin-description "..."

# Hooks (once per checkout; dry run without --yes): rebuild generated files after every edit, run
# `check --changed` before the agent finishes (blocks once per failing state) and before each commit.
python tools/hub.py setup-hooks --yes    # HUB_HOOKS=off disables them

# Rerun a single failing suite or case (hub.py check prints the exact command)
python -m unittest discover -s skills/<area>/<group>/<name>/scripts -p "test_*.py"
python -m unittest discover -s mcp-server/tests -k <substring>

# Installer (never run without a sandboxed HOME/USERPROFILE when testing writes)
python tools/install.py --list
python tools/install.py --detect
python tools/install.py --agent <agent> --skill <name> --project <dir> --yes
```

## Architecture

- **Skills** (`skills/<area>/<group>/<name>/`): the five areas are `testing`, `development`, `design`, `generic` and `external-tools` (`AREAS` in `tools/hublib.py`); groups are plain subfolders. The layout is exactly three levels deep, and the area and group come from the path. A skill is installed by its `<name>` alone, so names are unique across the hub and skills in the same group stay siblings after install. Each skill has `SKILL.md` with YAML frontmatter plus optional `references/`, `scripts/` (cross-platform Python, often with their own `test_*.py` and `fixtures/`), `assets/`. `template/` is the starting point; `spec/agent-skills-spec.md` is the format spec. Families: ~61 `git-*` skills (derived from Pro Git, see `THIRD_PARTY_NOTICES.md`), `gitlab-ci-*`, Android/image/video inspectors, unit-test skills, and meta skills (`skillforge`, `url-to-skill`, `contribute-skill`, `find-skills`, `skill-orchestrator`).
- **Registry**: `.claude-plugin/marketplace.json` groups skills into plugins; plugin == category. It is the only place that defines category membership, and family bundle plugins (e.g. all `git-*`) must also list their member skills.
- **Generator pipeline**: `tools/build_catalog.py` reads skills + `marketplace.json` + `examples/prompts.json` (via `tools/hublib.py`, which holds shared paths and frontmatter parsing) and writes `catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html` (from `tools/prompts_template.html`), `user-guide.html` (the master user guide, from `tools/user_guide_template.html` plus data read from the skills, `install.build_parser()`, `install.MCP_PRESETS`, the skill-hub MCP server's tools, `rule/` and `CHANGELOG.md`), and marked blocks in `README.md` / `GUIDE.md`. `tools/validate_skills.py` enforces frontmatter, description length, agent-neutrality, example-prompt minimums and marketplace consistency.
- **Distribution**: `tools/install.py` copies a skill folder into each agent's skills directory, driven by its `AGENTS` dict (the per-agent folder and detection table, which also feeds the generated README/GUIDE tables). Everything it writes into an agent's config files (MCP server entries, the skill-dispatcher and token-optimizer hooks) goes through `ConfigEntry` (`plan` / `show` / `apply`), one adapter per entry; `merge_hooks` is the one merge for shared hooks files, also used by `hub.py`. Other channels are `npx skills` and the Claude Code plugin marketplace.
- **MCP server** (`mcp-server/skillhub_mcp/`): read-only stdio MCP server exposing the catalog (`catalog.py`), JSON-RPC/MCP plumbing (`protocol.py`) and tools/resources/prompts (`server.py`). It reads a local clone or GitHub with `--remote`. Run `python -m skillhub_mcp --check` from `mcp-server/`.
- **Newer MCP server** (`skill-hub-mcp/skill_hub_mcp/`): kept beside the first one. `hub.py` (catalog sources, BM25 search, request routing, file access), `rpc.py` (MCP over stdio), `actions.py` (plans and applies installs by driving `tools/install.py`; writes only with `--allow-install` and a one-time plan token) and `server.py`. Tests: `python -m unittest discover -s skill-hub-mcp/tests -v`.
- **Front-ends**: `index.html` (catalog browser), `prompts.html` and `user-guide.html` (both generated). Don't publish to GitHub Pages; link repo files instead.
