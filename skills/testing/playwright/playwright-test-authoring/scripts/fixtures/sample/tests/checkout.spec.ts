import { test, expect } from '@playwright/test';

test.only('checkout works', async ({ page }) => {
  await page.goto('https://shop.example.com/cart');
  await page.waitForTimeout(3000);
  await page.locator('[data-qa=checkout-button]').click({ force: true });
  await page.locator('//div[@id="pay"]/button').click();
  await page.locator('#main > div > ul > li:nth-child(2)').click();
  await page.getByLabel('Password').fill('Sup3rSecret!');
  expect(page.getByRole('heading', { name: 'Thanks' })).toBeVisible();
  expect(await page.locator('[data-qa=total]').isVisible()).toBe(true);
  await page.waitForLoadState('networkidle');
  // await page.waitForTimeout(1000);  comments are ignored
});

test('good test', async ({ page }) => {
  await page.goto('/cart');
  await page.getByRole('button', { name: 'Checkout' }).click();
  await expect(page.getByRole('heading', { name: 'Thanks' })).toBeVisible();
  await expect(page.getByTestId('total')).toHaveText('$10');
  const total = page.getByText('Total');
  return expect(total).toBeVisible();
});

test.fixme('flaky refund flow', async () => {});

test('old apis', async ({ page }) => {
  await page.locator('_react=CartButton').click();
  const tree = await page.accessibility.snapshot();
  await page.locator('button:visible').click();
});
