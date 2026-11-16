# Changelog

Notable changes to skill-hub. Newest first. Skills are listed by name; see `git log` for detail.

## Unreleased

## 1.3.0 - 2026-11-16

- Added: `context-engineering` (in `ai-efficiency-tools`): one central context file, thin pointers for each tool, layered loading, a token budget and handoff notes, with a script that finds duplicated or drifting instruction files and creates the pointers.
- Added: `ai-token-saver` (new `ai-efficiency-tools` category): audits a project for context waste and lists habits that cut token use and cost.
- Added: `adb-tool`, `adb-connect`, `adb-device-control`, `adb-debug` (new `adb-tools` category).
- Added: `gradle-android` (new `gradle-tools` category).
- Added: `install.bat`, a one-shot Windows installer with precondition checks. It now honours `SKILLHUB_REF` instead of always reading `main`.
- Installer: update detection compares every file of a skill, not only `SKILL.md`, so a change to a bundled script or reference is now reported and `--update` refreshes it. Line endings are ignored.
- Installer: records what it installs in `.skill-hub.json` in each skills folder (skill, hub version, repository); new `--installed` lists the hub skills an agent has, their version and whether they still match the hub.
- Installer: a release download (`--ref v1.3.0`, or the new `SKILLHUB_REF`) uses the release archive and checks it against the release's `SHA256SUMS`; a mismatch stops the install.
- Installer: unit tests in `tools/test_install.py`, run by CI and the release workflow.
- Docs: the `--plugin` table in `GUIDE.md` is generated from the marketplace (it listed 14 of 22 plugins); update, remove and pinning steps corrected; marketplace description is agent-neutral.
- MCP server: removed the `uvx skillhub-mcp` instruction. That PyPI name belongs to an unrelated project; this server has not been published.
- Repo: rules moved into `rule/`; `code-reviewer` agent for skill review.
- Added: `skill-router` (in `hub-tools`): front door for any request. Splits it into parts, grades each basic or advanced, checks the basics are given (file, link, device, tools), and picks the installed skills to load, with editable routing hints and a hand-off to `skill-orchestrator` for multi-skill jobs.

- `skill-orchestrator`: hand-off briefings for inter-skill communication. `run done` records `--fact key=value` and `--question` beside the note and outputs, and the new `run handoff DIR [N]` prints one briefing of everything earlier steps passed on.

## 1.2.0 - 2026-11-14

- Added: `python-tutor` (new `learning-tools` category): explains any `.py` file from beginner to advanced and generates self-contained study-notes HTML (walkthrough, ~75 concepts by level, gotchas, interview Q&A, fundamentals checklist). The file is parsed, never run.
- `python-tutor`: Functionality section (call tree, inputs, outputs, side effects, public API, docstring examples), `--only` to explain selected functions or classes, loose mode for Python 2 files and syntax errors, warnings about suspicious explanations, and notes that follow moved code.

## 1.1.0 - 2026-11-14

- Added: `repo-architecture` (in `repo-tools`): scans a repository and drafts `ARCHITECTURE.md` (Mermaid) and a self-contained `architecture.html` (layered SVG), then guides the reader to describe components and flows.
- Added: `powershell-commands` (new `shell-tools` category): PowerShell playbook for agents with a bash-to-PowerShell map and references for files, text and data, processes, network, dev tools, scripting and troubleshooting.

## 1.0.0 - 2026-11-14

- Release: tagged releases (`v*`) now publish a GitHub Release with a version-pinned `install.py`, `catalog.json`, one zip per skill, a full-repo zip and `SHA256SUMS`. The version lives in `.claude-plugin/marketplace.json` and is stamped into `catalog.json`.
- Installer: `--ref` accepts release tags, new `--repo owner/name` (or `SKILLHUB_REPO`) so forks can distribute their own copy. The MCP server honours `SKILLHUB_REPO` too.
- MCP server: `publish-mcp.yml` publishes `skillhub-mcp` to PyPI on `mcp-v*` tags; without a clone it falls back to reading GitHub.
- Repo health: `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates; README licence section explains the CC BY-NC-SA `git-*` skills.
- Added: `skill-orchestrator` (in `hub-tools`): finds installed skills, plans multi-skill workflows, checks requirements and tracks hand-offs between steps.
- Added: `professional-writing` (new `writing-tools` category): blog posts, CVs, cover letters and technical docs, with templates and a checker script.
- Added: `repo-learnings` (new `repo-tools` category).
- Added: `gitlab-ci-pipeline-authoring`, `gitlab-ci-debugging`, `gitlab-ci-optimization` (new `gitlab-ci-tools` category).
- Added: `android-logcat-analyzer`, `kotlin-unit-test` (new `testing-tools` category).
- Installer: `--update` (refresh installed skills) and `--remove` (uninstall selected skills).
- README: category table, plugin list and skill counts are now generated; "Start here" section; MIT `LICENSE`.
- CI: unit tests of every skill that has tests now run automatically.
