# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md
@rule/01-generated-files.md
@rule/02-sources-of-truth.md
@rule/03-skill-content.md
@rule/04-checks.md
@rule/05-tooling.md
@rule/06-pull-requests.md
@rule/07-common-tasks.md
@rule/08-releases.md

The golden rules, sources of truth and per-task steps live in the `rule/` folder (imported above, indexed from AGENTS.md). The sections below add commands and architecture that the rules don't cover.

## Using skills

At the start of every non-trivial task, use the `skill-router` skill first (`python skills/generic/hub/skill-router/scripts/route.py "<the user's request>"`), so vague or multi-part requests still reach the right skills. Skip it only when the user names a skill or the task is a trivial one-liner.

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

# Rerun a single failing suite or case (hub.py check prints the exact command)
python -m unittest discover -s skills/<area>/<group>/<name>/scripts -p "test_*.py"
python -m unittest discover -s mcp-server/tests -k <substring>

# Installer (never run without a sandboxed HOME/USERPROFILE when testing writes)
python tools/install.py --list
python tools/install.py --detect
python tools/install.py --agent <agent> --skill <name> --project <dir> --yes
```

`image-inspector` and `video-inspector` tests need `Pillow` and `opencv-python-headless`; all other tests are stdlib only. `tools/install.py` must stay compatible with Python 3.8 (CI checks it with `vermin`).

Releases: the version is `metadata.version` in `.claude-plugin/marketplace.json`; pushing a matching `v*` tag runs `.github/workflows/release.yml` (steps in CONTRIBUTING.md). `install.py` has `DEFAULT_REF`, which the release workflow rewrites to the tag, so don't rename that line. Forks use `--repo` / `SKILLHUB_REPO`.

## Architecture

- **Skills** (`skills/<area>/<group>/<name>/`): the five areas are `testing`, `development`, `design`, `generic` and `external-tools` (`AREAS` in `tools/hublib.py`); groups are plain subfolders. The layout is exactly three levels deep, and the area and group come from the path. A skill is installed by its `<name>` alone, so names are unique across the hub and skills in the same group stay siblings after install. Each skill has `SKILL.md` with YAML frontmatter plus optional `references/`, `scripts/` (cross-platform Python, often with their own `test_*.py` and `fixtures/`), `assets/`. `template/` is the starting point; `spec/agent-skills-spec.md` is the format spec. Families: ~61 `git-*` skills (derived from Pro Git, see `THIRD_PARTY_NOTICES.md`), `gitlab-ci-*`, Android/image/video inspectors, unit-test skills, and meta skills (`skillforge`, `url-to-skill`, `contribute-skill`, `find-skills`, `skill-orchestrator`).
- **Registry**: `.claude-plugin/marketplace.json` groups skills into plugins; plugin == category. It is the only place that defines category membership, and family bundle plugins (e.g. all `git-*`) must also list their member skills.
- **Generator pipeline**: `tools/build_catalog.py` reads skills + `marketplace.json` + `examples/prompts.json` (via `tools/hublib.py`, which holds shared paths and frontmatter parsing) and writes `catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html` (from `tools/prompts_template.html`), `user-guide.html` (the master user guide, from `tools/user_guide_template.html` plus data read from the skills, `install.build_parser()`, `install.MCP_PRESETS`, the skill-hub MCP server's tools, `rule/` and `CHANGELOG.md`), and marked blocks in `README.md` / `GUIDE.md`. `tools/validate_skills.py` enforces frontmatter, description length, agent-neutrality, example-prompt minimums and marketplace consistency.
- **Distribution**: `tools/install.py` copies a skill folder into each agent's skills directory, driven by its `AGENTS` dict (the per-agent folder and detection table, which also feeds the generated README/GUIDE tables). Other channels are `npx skills` and the Claude Code plugin marketplace.
- **MCP server** (`mcp-server/skillhub_mcp/`): read-only stdio MCP server exposing the catalog (`catalog.py`), JSON-RPC/MCP plumbing (`protocol.py`) and tools/resources/prompts (`server.py`). It reads a local clone or GitHub with `--remote`. Run `python -m skillhub_mcp --check` from `mcp-server/`.
- **Newer MCP server** (`skill-hub-mcp/skill_hub_mcp/`): kept beside the first one. `hub.py` (catalog sources, BM25 search, request routing, file access), `rpc.py` (MCP over stdio), `actions.py` (plans and applies installs by driving `tools/install.py`; writes only with `--allow-install` and a one-time plan token) and `server.py`. Tests: `python -m unittest discover -s skill-hub-mcp/tests -v`.
- **Front-ends**: `index.html` (catalog browser), `prompts.html` and `user-guide.html` (both generated). Don't publish to GitHub Pages; link repo files instead.
