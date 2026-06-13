import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test("clicking Bat's List swaps the card grid for the bucket dropdown", async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);

  // All tab: item cards are shown, no Bat bucket dropdown.
  expect(await page.locator('[data-testid="lot-card"]').count()).toBeGreaterThan(0);
  await expect(page.locator('[data-testid="bat-bucket-dropdown"]')).toHaveCount(0);

  // Switch to Bat's List → the grid is replaced by the bucket dropdown + a
  // "pick a bucket" prompt (no flood of item cards at the default level).
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="bat-bucket-dropdown"]')).toBeVisible();
  await expect(page.locator('[data-testid="bat-prompt"]')).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);

  // Switch back to All → grid returns, dropdown gone.
  await page.locator('[data-testid="tab-all"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="bat-bucket-dropdown"]')).toHaveCount(0);
  expect(await page.locator('[data-testid="lot-card"]').count()).toBeGreaterThan(0);
});
