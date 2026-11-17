# Playwright patterns

Docs: https://playwright.dev/docs/intro (TypeScript/JS) and https://playwright.dev/python/docs/intro (Python).

## Config baseline (TypeScript)

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['blob'], ['github']] : [['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    testIdAttribute: 'data-testid',          // change to the attribute your app uses (data-qa, data-cy, ...)
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: '.auth/user.json' }, dependencies: ['setup'] },
    { name: 'firefox', use: { ...devices['Desktop Firefox'], storageState: '.auth/user.json' }, dependencies: ['setup'] },
    { name: 'mobile', use: { ...devices['Pixel 7'], storageState: '.auth/user.json' }, dependencies: ['setup'] },
  ],
  webServer: process.env.CI ? undefined : { command: 'npm run dev', url: 'http://localhost:3000', reuseExistingServer: true },
});
```

Environments: one `BASE_URL` per environment (`BASE_URL=https://staging.example.com npx playwright test`), never hard-coded URLs in tests.

## Sign in once, reuse the session

```ts
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

setup('sign in', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.E2E_USER!);
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await page.context().storageState({ path: '.auth/user.json' });
});
```
Add `.auth/` to `.gitignore`. SSO / MFA: sign in through an API or a test-only bypass agreed with the identity team, or use a test tenant without MFA; do not automate real MFA.

## Fixtures

```ts
// tests/fixtures.ts
import { test as base, expect } from '@playwright/test';
import { OrdersPage } from './pages/orders-page';

type Fixtures = { ordersPage: OrdersPage; order: { id: string } };

export const test = base.extend<Fixtures>({
  order: async ({ request }, use) => {
    const res = await request.post('/api/test/orders', { data: { items: [{ sku: 'A-1', qty: 1 }] } });
    expect(res.ok()).toBeTruthy();
    const order = await res.json();
    await use(order);
    await request.delete(`/api/test/orders/${order.id}`);   // clean up
  },
  ordersPage: async ({ page }, use) => { await use(new OrdersPage(page)); },
});
export { expect };
```

## Page object (keep them thin)

```ts
import { type Page, type Locator, expect } from '@playwright/test';

export class OrdersPage {
  readonly search: Locator;
  constructor(private page: Page) {
    this.search = page.getByRole('searchbox', { name: 'Search orders' });
  }
  async goto() { await this.page.goto('/orders'); }
  row(orderId: string) { return this.page.getByRole('row').filter({ hasText: orderId }); }
  async reorder(orderId: string) {
    await this.row(orderId).getByRole('button', { name: 'Reorder' }).click();
    await expect(this.page.getByRole('status')).toHaveText(/added to cart/i);
  }
}
```
Page objects hold locators and actions; assertions about the business outcome stay in the test.

## A test

```ts
import { test, expect } from './fixtures';

test('customer can reorder a past order @smoke', async ({ ordersPage, order, page }) => {
  await ordersPage.goto();
  await ordersPage.reorder(order.id);
  await page.getByRole('link', { name: 'Cart' }).click();
  await expect(page.getByRole('row')).toHaveCount(2);        // header + 1 item
});
```

## Python (pytest-playwright)

```python
import re
from playwright.sync_api import Page, expect

def test_customer_can_reorder(page: Page, order):            # `order` is a pytest fixture using the API
    page.goto("/orders")
    row = page.get_by_role("row").filter(has_text=order["id"])
    row.get_by_role("button", name="Reorder").click()
    expect(page.get_by_role("status")).to_have_text(re.compile("added to cart", re.I))
```
Run with `pytest --base-url https://staging.example.com --browser chromium --tracing retain-on-failure`. Set the test id attribute with `playwright.selectors.set_test_id_attribute("data-qa")` in `conftest.py`.

## Network control

```ts
await page.route('**/api/recommendations', route => route.fulfill({ json: [] }));   // stub a flaky dependency
const resp = page.waitForResponse(r => r.url().includes('/api/orders') && r.ok());
await page.getByRole('button', { name: 'Save' }).click();
await resp;
```

## Visual and accessibility

```ts
await expect(page).toHaveScreenshot('orders.png', { mask: [page.getByTestId('clock')], maxDiffPixelRatio: 0.01 });

import AxeBuilder from '@axe-core/playwright';
const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
expect(results.violations).toEqual([]);

await expect(page.getByRole('navigation')).toMatchAriaSnapshot(`
  - navigation:
    - link "Orders"
    - link "Cart"
`);
```
Update baselines deliberately: `npx playwright test --update-snapshots`, then review the image diff in the pull request.

## Newer APIs worth using (1.51 – 1.65)

```ts
// Scoping and visibility
await page.getByRole('button', { name: 'Save' }).within(page.getByTestId('settings-dialog')).click();   // 1.64
await page.locator('button').visible().click();                                                       // 1.63, replaces ':visible'
await page.getByRole('listitem').filter({ visible: true }).first().click();                           // 1.51
await page.getByRole('button', { name: 'Delete', description: 'Removes the draft' }).click();         // 1.60

// Assertions
await expect(page.getByRole('tab', { name: 'Billing' })).toContainClass('active');                     // 1.52
await expect(page.getByLabel('Email')).toHaveAccessibleErrorMessage('Enter a valid email');            // 1.50
await expect(page).toMatchAriaSnapshot(`- heading "Orders" [level=1]`);                                 // page-level, 1.60

// No console errors during a flow (1.56)
expect(page.pageErrors()).toEqual([]);
expect(page.consoleMessages().filter(m => m.type() === 'error')).toEqual([]);

// Tests that share one resource never run together (1.63); '-exclusive-' runs alone (1.65)
test('change company settings', { lock: 'company-settings' }, async ({ page }) => { /* ... */ });
test('restart the mail server', { lock: '-exclusive-' }, async () => { /* ... */ });

// Steps with a timeout (1.50)
await test.step('pay', async () => { /* ... */ }, { timeout: 20_000 });
```

**Passkey sign-in (1.61):** `browserContext.credentials` is a virtual authenticator, so WebAuthn/passkey login works in tests without a device. Create the credential for your site's domain with `context.credentials.create(...)`, call `context.credentials.install()`, and read stored passkeys with `credentials.get()`; see the `BrowserContext.credentials` API page for the exact options.

**Dev server on a dynamic port (1.57):** `webServer.wait: { stdout: /Listening on port (?<my_server_port>\d+)/ }` waits for the log line and exposes the captured group as `process.env.MY_SERVER_PORT`.

**Tag a whole run (1.57):** `tag: '@staging'` in the config adds the tag to every test, which helps when reports from several environments are merged.

**Component tests:** the `experimental-ct-*` packages are no longer updated (1.63). Prefer end-to-end tests against a running app, or check the current component-testing docs before starting a new component suite.

## Team conventions checklist

Agree on these once and write them in the repo's contributing notes:

- [ ] Test-id attribute (`data-testid`, `data-qa`, ...) and when to add one to app code.
- [ ] Folder layout (`tests/<feature>/`, `pages/`, `fixtures.ts`) and file naming (`*.spec.ts`).
- [ ] Tags for suites (`@smoke` on every PR, `@regression` nightly) and how CI selects them (`--grep`).
- [ ] Environments and their `BASE_URL`s; which tests may run against which environment.
- [ ] Test accounts and data seeding (API, fixtures, database reset), and cleanup.
- [ ] Browsers and devices that matter for your users (projects).
- [ ] Flake policy: retries on CI only, every flaky test gets a ticket, quarantine with `test.fixme` plus a link.
- [ ] Review rules: run the audit script in CI with `--strict`.
