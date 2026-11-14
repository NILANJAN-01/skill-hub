# Changelog

Notable changes to skill-hub. Newest first. Skills are listed by name; see `git log` for detail.

## Unreleased

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
