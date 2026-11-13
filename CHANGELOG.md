# Changelog

Notable changes to skill-hub. Newest first. Skills are listed by name; see `git log` for detail.

## Unreleased

- Added: `skill-orchestrator` (in `hub-tools`): finds installed skills, plans multi-skill workflows, checks requirements and tracks hand-offs between steps.
- Added: `professional-writing` (new `writing-tools` category): blog posts, CVs, cover letters and technical docs, with templates and a checker script.
- Added: `repo-learnings` (new `repo-tools` category).
- Added: `gitlab-ci-pipeline-authoring`, `gitlab-ci-debugging`, `gitlab-ci-optimization` (new `gitlab-ci-tools` category).
- Added: `android-logcat-analyzer`, `kotlin-unit-test` (new `testing-tools` category).
- Installer: `--update` (refresh installed skills) and `--remove` (uninstall selected skills).
- README: category table, plugin list and skill counts are now generated; "Start here" section; MIT `LICENSE`.
- CI: unit tests of every skill that has tests now run automatically.
