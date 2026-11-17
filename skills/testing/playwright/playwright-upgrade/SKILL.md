---
name: playwright-upgrade
description: "Upgrade Playwright safely to a newer version (up to 1.65): list the breaking changes and removed APIs between the current and target versions, find every affected place in tests, config, CI files and Docker image tags, then update packages, browsers, Node.js and baselines. A script builds the plan. Use when the user wants to upgrade Playwright or a newer version broke the tests."
license: MIT
compatibility: The planning script needs Python 3.8+ (standard library only). Its release data covers Playwright 1.50 to 1.65; check the release notes for later versions.
metadata:
  title: "Playwright upgrade: breaking changes, affected code, steps"
  category: playwright-tools
---

# Playwright upgrade

Playwright ships a release about every month, and most remove or change something. Companies often fall several versions behind and then hit removed APIs, unsupported Node.js or OS versions, and CI images that no longer match. Upgrade with a plan, not by trial and error.

## When to use

- Moving a project from an older Playwright (for example 1.4x) to a current one.
- Tests, CI or the Docker image broke right after a Playwright version bump.
- Checking whether a project can upgrade before scheduling the work.

## When NOT to use

- Ordinary test failures with no version change: use `playwright-debugging`.
- Writing new tests: use `playwright-test-authoring`.

## Procedure

1. **Make the plan** (read-only):
   ```bash
   python scripts/pw_upgrade.py <project-dir>                      # current version detected, target 1.65
   python scripts/pw_upgrade.py <project-dir> --from 1.48 --to 1.60
   python scripts/pw_upgrade.py <project-dir> --json
   ```
   It reads the installed version from `package-lock.json` / `package.json` (or `requirements*.txt` / `pyproject.toml` for Python), lists every breaking change and removal after it up to the target, and scans tests, config, CI files and `package.json` scripts for each one, with file and line. Output marks each change `AFFECTED` (places listed), `ok` (pattern not found) or `check` (cannot be found by text search, e.g. "elements in hidden iframes count as hidden"; review by hand). It also lists `mcr.microsoft.com/playwright:v...` image tags to update, and prints the upgrade steps. Exit `1` when something is affected.
2. **Read the release notes** for the versions in between (https://playwright.dev/docs/release-notes): the script covers breaking changes, the notes also show new features worth adopting (see `playwright-test-authoring` for the most useful ones).
3. **Upgrade on a branch**, in this order:
   1. Runtimes: Node.js 22+ for Playwright 1.65 (locally, CI `node-version`, custom images); CI hosts on Ubuntu 22.04+ / Debian 12+.
   2. Package: `npm install -D @playwright/test@<version>` (or yarn/pnpm; Python: `pip install -U playwright==<version>` and `pytest-playwright`). Keep every Playwright package on the same version.
   3. Browsers: `npx playwright install --with-deps` (Python: `python -m playwright install --with-deps`).
   4. CI images: the tag must equal the installed version exactly: `mcr.microsoft.com/playwright:v<version>-noble` (Python: `mcr.microsoft.com/playwright/python:v<version>-noble`).
   5. Fix every `AFFECTED` place, then the `check` items that apply.
   6. If the project uses Playwright test agents or the bundled MCP server, regenerate the agent files (`npx playwright init-agents --loop=<your agent>`).
4. **Verify:** run all projects (`npx playwright test`), compare with the last green run using `pw_report.py --baseline` from `playwright-debugging`, then review screenshot diffs before updating baselines (`--update-snapshots`); Chrome for Testing builds (1.57) and other rendering changes can move pixels.
5. **Big jumps:** for many versions at once, upgrade in steps (for example 1.48 → 1.54 → 1.60 → 1.65), running the suite at each step, so each failure points to one release.

## Most impactful changes 1.50 – 1.65

| Version | Change | Action |
|---|---|---|
| 1.52 | Glob patterns no longer support `?` and `[]` | Use a RegExp or predicate in `route`, `waitForURL`, `testMatch` |
| 1.54 | Node 16 removed, `-gv` removed | Upgrade Node; use `--grep-invert` |
| 1.57 | `page.accessibility` removed; Chrome for Testing builds | Aria snapshots or axe; re-check screenshots |
| 1.58 | `_react` / `_vue` selectors, `:light`, `devtools` option removed | Role/test-id locators; launch args |
| 1.60 | `videosPath` / `videoSize`, `ariaRef()` removed | `recordVideo` |
| 1.62 / 1.63 | Debian 11 and Ubuntu 20.04 unsupported; component-testing packages frozen | Newer CI images; plan CT migration |
| 1.64 | `screen` from device descriptors; hidden-iframe elements are hidden | Re-check affected assertions |
| 1.65 | Node 20 unsupported; sharded runs with no matching tests fail; actions wait for non-inert elements; RFC 6265 cookie matching | Node 22+; `--pass-with-no-tests` on filtered shards; close modals first |

## Safety rules

- Upgrade on a branch; never update screenshot baselines in bulk without reviewing the diffs.
- Do not change CI for other teams' pipelines without telling them (shared runner images, shared templates).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Executable doesn't exist` after upgrading | Browsers or the Docker image still on the old version: reinstall browsers, update the image tag |
| `Unsupported engine` / Node errors | Node.js too old for the new Playwright: 22+ for 1.65 |
| Many screenshot diffs | Rendering changed with the browser version: review a sample, then update baselines in the CI image |
| `No tests found` on sharded CI after upgrading | 1.65 behaviour: add `--pass-with-no-tests` to filtered sharded runs |
| Script cannot find the version | Pass `--from <version>` |
