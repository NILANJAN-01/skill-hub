import { test, expect } from '@playwright/test';

test('cart', async ({ page }) => {
  await page.goto('/cart');
  await page.locator('_react=CartButton').click();
  const tree = await page.accessibility.snapshot();
  await page.waitForURL('**/order?id=*');
  await expect(page).toHaveScreenshot('cart.png');
});
