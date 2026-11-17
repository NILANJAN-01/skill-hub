# Flakiness checklist

Work down the list; the first match is usually the cause.

## 1. Timing

- [ ] Any `waitForTimeout` / `time.sleep`? Replace with a condition: `await expect(locator).toBeVisible()`, `await page.waitForResponse(...)`, `await expect(page).toHaveURL(...)`.
- [ ] Any `expect(await x.isVisible())`, `textContent()` compared directly, or `count()` checked once? Use web-first assertions, which retry until the timeout.
- [ ] Missing `await` on an action or assertion? (Lint rule `@typescript-eslint/no-floating-promises` catches these.)
- [ ] Clicking before the app is ready (hydration)? Assert on something that only appears when it is interactive before clicking.

## 2. Test data and isolation

- [ ] Do tests share one account or record? Parallel workers then fight over it. Create data per test (API fixture) or one account per worker (`testInfo.workerIndex`).
- [ ] Does a test depend on another test having run first? Make each test set up what it needs. Prove it with `--shuffle` (1.64+) and rerun a bad order with `--shuffle <seed>`.
- [ ] Must some tests share one resource? Give them the same `lock` name (1.63+), or `lock: '-exclusive-'` (1.65+) for tests that need the whole system, instead of `workers: 1` for everyone.
- [ ] Is data cleaned up? Leftovers change lists, counts and search results for the next run.
- [ ] Do assertions depend on "now" (dates, "2 minutes ago")? Freeze time with `page.clock.setFixedTime(...)` or assert on a pattern.

## 3. Locators

- [ ] Does the locator match more than one element in some layouts (mobile menu + desktop menu)? Scope it.
- [ ] Is the text localised or A/B tested? Prefer role + test id, or set the locale in config.
- [ ] Generated class names or positional CSS? Replace with role/label/test id.

## 4. Environment (CI-only failures)

- [ ] Viewport, device scale, locale and time zone set in config (`use: { viewport, locale, timezoneId }`), not left to the machine.
- [ ] Fewer CPUs on CI: reduce `workers`, or the app server is overloaded (start it with production settings).
- [ ] Third-party scripts (analytics, chat widgets, ads) slow or change the page: block them with `page.route` in a fixture.
- [ ] Fonts and rendering differ: generate screenshot baselines in the same Docker image as CI.
- [ ] Network to the test environment: retries on `net::ERR_*` hide outages; check the environment's health first.

## 5. Popups, overlays, animations

- [ ] Cookie banners, onboarding tours or toasts covering buttons: dismiss them in a fixture or set the "already seen" state in `storageState`.
- [ ] New tab or popup: `const popup = page.waitForEvent('popup')` before the click.
- [ ] Animations: `await expect(locator).toBeVisible()` waits for stability; for screenshots use `animations: 'disabled'`.

## Measuring flakiness

- Run a suspect test many times: `npx playwright test path:line --repeat-each=50 --workers=8`.
- Track flaky tests across CI runs: keep each run's JSON report and run `pw_report.py` on them; the same test showing up as `flaky` repeatedly needs an owner.
- Retries (`retries: 2` on CI) mark a test as `flaky` instead of failed; the report and `pw_report.py` list them separately so they are not ignored.
- `retryStrategy: 'isolated'` (1.62+) retries failed tests at the end of the run, one at a time: a test that passes there but fails in the main run is affected by other tests.
- `failOnFlakyTests: true` / `--fail-on-flaky-tests` turns flaky results into a failed run (for a strict main branch).
- In the test, `page.consoleMessages()`, `page.pageErrors()` and `page.requests()` (1.56+) return what happened so far; attach them on failure for evidence.
