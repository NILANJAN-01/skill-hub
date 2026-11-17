---
name: playwright-test-authoring
description: "Write and review Playwright end-to-end tests (TypeScript/JavaScript or Python) that fit the team's conventions: resilient locators, web-first assertions, fixtures, page objects, login reuse, API, visual and accessibility checks. A script audits a suite and its config for flaky patterns. Use when the user wants Playwright tests written, reviewed or set up."
license: MIT
compatibility: The audit script needs Python 3.8+ (standard library only). Running tests needs Node.js with @playwright/test, or Python with pytest-playwright.
metadata:
  title: "Playwright test authoring: resilient E2E tests that fit your team"
  category: playwright-tools
---

# Playwright test authoring

Write end-to-end tests that are readable, fast and not flaky, and that follow **the conventions this project already uses**. Every company differs (test-id attribute, environments, sign-in, folder layout), so read the existing setup before writing anything.

## When to use

- Add Playwright to a project, or write new tests for a page or user flow.
- Review or refactor existing Playwright tests; replace brittle selectors and sleeps.
- Add login reuse, API, visual-regression or accessibility checks.

## When NOT to use

- A test already fails or flakes and the cause is unknown: use `playwright-debugging`.
- Running tests in a pipeline: use `playwright-ci`.
- Driving a browser interactively for the user (not writing tests): use `playwright-mcp-browser`.

## Procedure

1. **Learn the project's setup first.** Find `playwright.config.*` (or `pytest.ini` / `pyproject.toml` with pytest-playwright), the test folder, existing fixtures and page objects, and how tests sign in. Then audit it:
   ```bash
   python scripts/pw_audit.py <project-dir>
   python scripts/pw_audit.py <project-dir> --json        # machine-readable
   python scripts/pw_audit.py <project-dir> --strict      # warnings fail too (for CI)
   ```
   It reports the config (baseURL, retries, trace, forbidOnly, testIdAttribute, projects, webServer), locator mix (role/label/test-id vs CSS/XPath), and anti-patterns with file and line: `test.only`, hard waits, missing `await` on web-first assertions, non-retrying assertions, `force: true`, `networkidle`, legacy `page.$`, XPath and brittle CSS, hard-coded URLs and credentials. It also notices a custom test-id attribute (e.g. `data-qa`) used in selectors and suggests `testIdAttribute`.
2. **New project:** `npm init playwright@latest` (TypeScript/JS) or `pip install pytest-playwright && playwright install` (Python). Set in the config: `baseURL` from an env variable, `forbidOnly: !!process.env.CI`, `retries: process.env.CI ? 2 : 0`, `trace: 'on-first-retry'`, and `testIdAttribute` if the app uses `data-qa`, `data-cy`, etc.
3. **Explore the flow before writing it.** Use `npx playwright codegen <url>` (or `playwright codegen` for Python) to record a first draft and pick locators, then clean it up. Never ship raw recordings.
4. **Write the test** with these rules ([references/patterns.md](references/patterns.md) has full examples):
   - **Locators, in order:** `getByRole(role, { name })` → `getByLabel` → `getByPlaceholder` → `getByText` → `getByTestId`. CSS only for things with no accessible name; never XPath or generated class names. Python: `page.get_by_role(...)`. Narrow with `.filter({ hasText })`, `.visible()` (1.63+, replaces the `:visible` CSS suffix), `locator.within(container)` (1.64+) or `getByRole(..., { description })` (1.60+).
   - **Web-first assertions** that retry: `await expect(locator).toBeVisible()`, `toHaveText`, `toHaveURL`, `toHaveCount`. Never `expect(await locator.isVisible()).toBe(true)`.
   - **No sleeps** (`waitForTimeout`, `time.sleep`): wait for a condition (an assertion, `waitForResponse`, `toHaveURL`).
   - **Independent tests**: each test sets up its own data (API calls or fixtures) and does not depend on another test's order.
   - **One user goal per test**, named for the behaviour: `test('customer can reorder a past order', ...)`. Use `test.step` for long flows and tags (`@smoke`, `@regression`) for selection with `--grep`.
5. **Structure for reuse:** page objects or small helper functions for repeated screens; custom fixtures (`test.extend`) for logged-in pages, seeded data and API clients; a `setup` project that signs in once and saves `storageState`, which other projects reuse. Passkey (WebAuthn) sign-in: use the virtual authenticator `context.credentials` (1.61+) instead of real devices. Tests that must not run at the same time (one shared admin, a settings page): give them the same `lock` (1.63+) rather than serialising the whole suite.
6. **Add other checks where they pay off:** `request` fixture for API setup and API tests; `toHaveScreenshot()` for visual regression (stable data, masked dynamic areas, same OS as CI); `@axe-core/playwright` for accessibility; `toMatchAriaSnapshot()` for page structure.
7. **Run and verify:** `npx playwright test <file> --project=chromium` then all browsers; `--repeat-each=5` on new tests to catch flakiness before merging; `npx playwright test --ui` while developing. Re-run the audit and fix every ERROR.

Version notes: this skill follows Playwright 1.65. The audit flags APIs removed in recent releases (`_react=`/`_vue=` selectors, `page.accessibility`, `videosPath`/`videoSize`, the `devtools` launch option). To move an older project forward, use `playwright-upgrade`.

## Safety rules

- Never put real credentials or customer data in tests: read secrets from environment variables or the CI secret store, and use test accounts.
- Do not point destructive tests (deleting, paying, emailing) at production; check `baseURL` first.
- Keep `storageState` files (they contain session cookies) out of version control.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `strict mode violation: ... resolved to N elements` | Make the locator unique: add `{ name }`, `exact: true`, scope it (`row.getByRole(...)`) or `.filter({ hasText })` |
| Test passes locally, fails in CI | Different viewport, time zone, data or speed: set them in config, seed data, remove sleeps; see `playwright-debugging` |
| Login repeated in every test is slow | `setup` project + `storageState`, or a worker-scoped auth fixture |
| Screenshots differ between machines | Generate baselines in the same OS/browser image as CI (Docker), mask dynamic content |
| Test id selectors don't match | Set `testIdAttribute` to the attribute the app uses |

## References

- [references/patterns.md](references/patterns.md): config, fixtures, page objects, auth setup, API, visual and accessibility examples in TypeScript and Python, and a team conventions checklist.
