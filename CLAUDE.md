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

## Commands

Everything is Python standard library only; there is no build step or package install.

```bash
# The three checks CI runs for every change (run all before finishing)
python tools/build_catalog.py            # regenerate catalog.json, READMEs, prompts.html, etc.
python tools/validate_skills.py
python tools/build_catalog.py --check    # fails if generated files are stale

# Byte-compile (CI does this too)
python -m compileall -q tools skills mcp-server

# MCP server tests
python -m unittest discover -s mcp-server/tests -v

# Tests for one skill's bundled scripts (each skill with tests has skills/<name>/scripts/test_*.py)
python -m unittest discover -s skills/<name>/scripts -p "test_*.py" -v
# single test file / case
python -m unittest skills/<name>/scripts/test_foo.py
python -m unittest discover -s mcp-server/tests -k <substring>

# Installer (never run without a sandboxed HOME/USERPROFILE when testing writes)
python tools/install.py --list
python tools/install.py --detect
python tools/install.py --agent <agent> --skill <name> --project <dir> --yes
```

`image-inspector` and `video-inspector` tests need `Pillow` and `opencv-python-headless`; all other tests are stdlib only. `tools/install.py` must stay compatible with Python 3.8 (CI checks it with `vermin`).

Releases: the version is `metadata.version` in `.claude-plugin/marketplace.json`; pushing a matching `v*` tag runs `.github/workflows/release.yml` (steps in CONTRIBUTING.md). `install.py` has `DEFAULT_REF`, which the release workflow rewrites to the tag, so don't rename that line. Forks use `--repo` / `SKILLHUB_REPO`.

## Architecture

- **Skills** (`skills/<name>/`): `SKILL.md` with YAML frontmatter plus optional `references/`, `scripts/` (cross-platform Python, often with their own `test_*.py` and `fixtures/`), `assets/`. `template/` is the starting point; `spec/agent-skills-spec.md` is the format spec. Families: ~61 `git-*` skills (derived from Pro Git, see `THIRD_PARTY_NOTICES.md`), `gitlab-ci-*`, Android/image/video inspectors, unit-test skills, and meta skills (`skillforge`, `url-to-skill`, `contribute-skill`, `find-skills`, `skill-orchestrator`).
- **Registry**: `.claude-plugin/marketplace.json` groups skills into plugins; plugin == category. It is the only place that defines category membership, and family bundle plugins (e.g. all `git-*`) must also list their member skills.
- **Generator pipeline**: `tools/build_catalog.py` reads skills + `marketplace.json` + `examples/prompts.json` (via `tools/hublib.py`, which holds shared paths and frontmatter parsing) and writes `catalog.json`, `skills/README.md`, `examples/PROMPTS.md`, `prompts.html` (from `tools/prompts_template.html`), and marked blocks in `README.md` / `GUIDE.md`. `tools/validate_skills.py` enforces frontmatter, description length, agent-neutrality, example-prompt minimums and marketplace consistency.
- **Distribution**: `tools/install.py` copies a skill folder into each agent's skills directory, driven by its `AGENTS` dict (the per-agent folder and detection table, which also feeds the generated README/GUIDE tables). Other channels are `npx skills` and the Claude Code plugin marketplace.
- **MCP server** (`mcp-server/skillhub_mcp/`): read-only stdio MCP server exposing the catalog (`catalog.py`), JSON-RPC/MCP plumbing (`protocol.py`) and tools/resources/prompts (`server.py`). It reads a local clone or GitHub with `--remote`. Run `python -m skillhub_mcp --check` from `mcp-server/`.
- **Front-ends**: `index.html` (catalog browser) and `prompts.html` (generated). Don't publish to GitHub Pages; link repo files instead.
