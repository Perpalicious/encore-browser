import { test, expect } from '@playwright/test';
import { pickBatBucket, shownCount } from './helpers';

/**
 * Switching Bat's List buckets from the rail.
 *
 * Choosing a bucket replaces the picker with the grid, so before this existed
 * the only way to another bucket was to clear the bucket entirely and drill
 * group → bucket again from a full-screen detour.
 */

test.use({ viewport: { width: 1400, height: 900 } });

test('the rail button switches buckets without returning to the picker', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await pickBatBucket(page, 0, 0);

  const firstCount = await shownCount(page);
  const button = page.locator('[data-testid="bucket-button"]');
  const firstLabel = (await button.textContent())!;
  expect(firstLabel).toContain('✦');

  // Open the drill-down, cross to a DIFFERENT group, take a bucket there.
  await button.click();
  const popover = page.locator('[data-testid="bucket-popover"]');
  await expect(popover).toBeVisible({ timeout: 5000 });
  await popover.locator('[data-testid^="bucket-level-0-"]').nth(1).click();
  const buckets = popover.locator('[data-testid^="bucket-level-1-"]');
  await expect(buckets.first()).toBeVisible();
  const targetName = (await buckets.first().locator('span').first().textContent())!.trim();
  await buckets.first().click();

  // Picking closes it, and the grid was never replaced by the picker.
  await expect(popover).toHaveCount(0, { timeout: 5000 });
  await expect(page.locator('[data-testid="bat-prompt"]')).toHaveCount(0);
  await page.waitForTimeout(400);

  await expect(button).toContainText(targetName);
  await expect(page.locator('[data-testid="chip-bucket"]')).toContainText(targetName);
  expect(await shownCount(page)).not.toBe(firstCount);
  expect(await shownCount(page)).toBeGreaterThan(0);
});

test('"All buckets" clears back to the picker', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await pickBatBucket(page, 0, 0);

  await page.locator('[data-testid="bucket-button"]').click();
  await page.locator('[data-testid="bucket-all"]').click();
  await page.waitForTimeout(400);

  await expect(page.locator('[data-testid="bat-prompt"]')).toBeVisible();
  await expect(page.locator('[data-testid="bucket-button"]')).toContainText('Pick a bucket');
});

test('the category button is not offered on this tab', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await expect(page.locator('[data-testid="category-button"]')).toBeVisible();

  // Category never applies inside a Bat's List bucket, so the slot carries the
  // control that does: the bucket switcher.
  await page.locator('[data-testid="tab-bat"]').click();
  await expect(page.locator('[data-testid="category-button"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="bucket-button"]')).toBeVisible();
});
