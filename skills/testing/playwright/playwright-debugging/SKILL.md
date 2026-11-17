---
name: playwright-debugging
description: "Find why Playwright tests fail or flake: read the report and traces, sort failures by cause (timeout, strict mode, assertion, navigation, closed page, screenshot diff), list flaky and slow tests, and fix the root cause. A script summarises Playwright JSON or JUnit reports. Use when Playwright tests fail, time out, or pass locally but fail in CI."
license: MIT
compatibility: The report script needs Python 3.8+ (standard library only). Traces open with the Playwright CLI (Node.js) or trace.playwright.dev.
metadata:
  title: "Playwright debugging: failing and flaky tests"
  category: playwright-tools
---

# Playwright debugging

Most Playwright failures fall into a few causes. Find the cause from evidence (report, trace, error text) before changing code, and fix the cause, not the symptom: adding sleeps or retries hides bugs.

## When to use

- A Playwright run failed (locally or in CI) and the reason is not obvious.
- Tests are flaky: pass on retry, fail only in CI, or fail only in one browser.
- The suite got slow and you need the slowest tests.

## When NOT to use

- Writing new tests or reviewing style: use `playwright-test-authoring`.
- Pipeline setup (sharding, artifacts, images): use `playwright-ci`.

## Procedure

1. **Get a machine-readable report.** Add a JSON (or JUnit) reporter for the failing run:
   ```bash
   npx playwright test --reporter=json,html > results.json        # or PLAYWRIGHT_JSON_OUTPUT_NAME=results.json
   npx playwright test --reporter=failures                        # 1.65+: only failures and retries, then a summary
   pytest --junitxml=results.xml                                  # pytest-playwright
   ```
   CI usually already keeps a JUnit file or a merged report; download it with the `trace.zip` / `test-results/` artifacts.
2. **Summarise it:**
   ```bash
   python scripts/pw_report.py results.json
   python scripts/pw_report.py results.xml --slowest 15
   python scripts/pw_report.py results.json --baseline last-green.json   # what newly fails
   python scripts/pw_report.py results.json --json                       # machine-readable
   ```
   It prints totals; every failed test with its project (browser), retry count, cause category and first error line; flaky tests (failed then passed on retry); failures grouped by cause and by project; the slowest tests; trace attachments to open; and, with `--baseline`, new failures and fixes.
3. **Read the trace** of a failed or flaky test: each action, DOM snapshots, console, network and the exact moment it failed.
   - **As text, from the terminal** (Playwright 1.59+; best for an agent, no GUI needed):
     ```bash
     npx playwright trace open test-results/<test-folder>/trace.zip
     npx playwright trace actions --grep="expect"       # list actions, filtered
     npx playwright trace action 9                      # details and error of action 9
     npx playwright trace snapshot 9 --name after       # page state before/after the action
     npx playwright trace close
     ```
   - **In a viewer** (people): `npx playwright show-trace <trace.zip>` or drop it on https://trace.playwright.dev; `npx playwright show-report` has traces inline.
   - No trace? Set `trace: 'on-first-retry'` (or run once with `--trace on`). Since 1.63 the `snapshots` trace option can also record `aria` snapshots, which are compact for reading.
4. **Reproduce locally** under CI-like conditions: `npx playwright test <file>:<line> --project=<browser> --repeat-each=20 --workers=4`, plus `--headed`, `--debug` (Inspector) or `--ui` to step through. Python: `PWDEBUG=1 pytest -k <name>`.
   - **Order dependence:** `npx playwright test --shuffle` (1.64+) randomises order and prints a seed; rerun with `--shuffle <seed>` to reproduce a failure.
   - **Interference between tests:** `retryStrategy: 'isolated'` (1.62+) runs retries at the end, alone; a test that then passes is being disturbed by others.
   - **Agent stepping:** `npx playwright test <file> --debug=cli` (1.59+) prints a `playwright-cli attach <session>` command; the session can then be stepped and inspected from the terminal (`playwright-cli --session <id> step-over`, `snapshot`).
5. **Fix by cause** (see the table below and [references/flakiness.md](references/flakiness.md)), then confirm with `--repeat-each=20` and on CI. Keep retries as a safety net, not as the fix.
6. **Quarantine only with a ticket:** `test.fixme('...', ...)` or a `@quarantine` tag skipped by `--grep-invert`, with an owner and a link, so it is not forgotten.

## Causes and fixes

| Category (script) | Typical error text | Usual root cause → fix |
|---|---|---|
| `timeout` | `Timeout 30000ms exceeded`, `Test timeout of ... exceeded` | Waiting for something that never happens (wrong locator, missing data, slow backend). Check the trace's last action; fix the locator or data; raise a specific `timeout` only for known slow steps |
| `strict-mode` | `strict mode violation: ... resolved to 2 elements` | Locator matches several elements (often responsive duplicates or lists) → scope it, `{ name, exact: true }`, `.filter()` |
| `locator` | `waiting for getByRole(...)`, `element is not visible / not enabled / outside of the viewport` | Element hidden, covered by an overlay/toast/cookie banner, or rendered later → wait for the overlay to go, dismiss banners in a fixture; never `force: true` |
| `assertion` | `expect(received).toBe...`, `Expected: ... Received: ...` | Wrong data or a real bug; non-retrying assertion racing the UI → use web-first assertions |
| `navigation` | `net::ERR_...`, `NS_ERROR_...`, `page.goto: ...` | App or environment down, wrong `baseURL`, certificate or proxy problem → check the environment first |
| `closed` | `Target page, context or browser has been closed` | Missing `await`, test ended while an action ran, or a crash → add the `await`; check for popups/new tabs |
| `screenshot` | `Screenshot comparison failed`, `pixels ... different` | Different OS/fonts/data, animations → baselines from the CI image, mask dynamic areas, disable animations |
| `other` | anything else | Read the trace and the stack; check console errors in the trace |

Signs of flakiness rather than a bug: passes on retry, fails only under parallel load (shared accounts or data between tests), fails only in CI (slower machines, different viewport/time zone/locale), or depends on test order.

Tests that must share one resource (a single admin account, a settings page, a server restart) can use **test locks** (1.63+) instead of turning off parallelism: `test('update settings', { lock: 'user-settings' }, ...)` never runs at the same time as other tests with that lock, and `{ lock: '-exclusive-' }` (1.65+) runs a test only when nothing else is running.

## Safety rules

- Traces and reports can contain session cookies, tokens and personal data from the app under test: share them only inside the team, and do not attach them to public issues.
- Do not "fix" failures by deleting assertions or adding sleeps; record why a test is quarantined.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pw_report.py` says it cannot read the file | Make sure the JSON is the reporter output only (no extra log lines); use `PLAYWRIGHT_JSON_OUTPUT_NAME` |
| No traces in CI artifacts | Upload `test-results/` (and `playwright-report/`) with `if: always()`; set `trace: 'on-first-retry'` |
| Only one browser fails | Browser-specific behaviour or a missing polyfill: run that `--project` locally with `--headed` |
| Many tests fail at once | Environment, login or `globalSetup` problem: look at the first failure and the setup project |

## References

- [references/flakiness.md](references/flakiness.md): flakiness checklist, isolation of test data, and CI-only failures.
