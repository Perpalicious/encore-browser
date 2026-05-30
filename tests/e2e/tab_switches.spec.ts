import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test("clicking Bat's List swaps the card grid for the group selector", async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);

  // All tab: item cards are shown, no Bat group selector.
  expect(await page.locator('[data-testid="lot-card"]').count()).toBeGreaterThan(0);
  await expect(page.locator('[data-testid="bat-group-nav"]')).toHaveCount(0);

  // Switch to Bat's List → the grid is replaced by the two-level group selector
  // (no flood of item cards at the default level).
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="bat-group-nav"]')).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);
  expect(await page.locator('[data-testid="bat-group"]').count()).toBeGreaterThanOrEqual(1);

  // Switch back to All → grid returns, selector gone.
  await page.locator('[data-testid="tab-all"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="bat-group-nav"]')).toHaveCount(0);
  expect(await page.locator('[data-testid="lot-card"]').count()).toBeGreaterThan(0);
});
