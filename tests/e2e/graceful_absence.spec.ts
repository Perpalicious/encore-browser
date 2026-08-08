import { test, expect } from '@playwright/test';
import { ready, openFilters, closeFilters, pickBatBucket } from './helpers';

/**
 * The state the live site is actually in.
 *
 * Closing times and Bat's List subtypes both arrive with a weekly pipeline
 * run, so the bundle in the repo has neither and will not until the next one.
 * Shipping a dead "Closing soonest" option and an inert Hide-ended toggle in
 * the meantime would be worse than not shipping the feature, so every
 * time- and subtype-related affordance is feature-detected — and that is what
 * this asserts. When a bundle WITH times lands, these tests are expected to be
 * inverted, not deleted.
 */

test.use({ viewport: { width: 1400, height: 900 } });

test('no closing-time affordances appear on a bundle without close_at', async ({ page }) => {
  await ready(page);

  await expect(page.locator('[data-testid="close-time"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="lot-card"]').first()).not.toContainText('ENDED');

  await openFilters(page);
  await expect(page.locator('[data-testid="hide-ended-toggle"]')).toHaveCount(0);
  const options = await page.locator('[data-testid="sort-select"] option').allTextContents();
  expect(options).not.toContain('Closing soonest');
  await closeFilters(page);
});

test('the rail sort cycle skips the close order it has no data for', async ({ page }) => {
  await ready(page);
  const button = page.locator('[data-testid="sort-button"]');
  const seen: string[] = [];
  for (let i = 0; i < 4; i++) {
    seen.push(((await button.textContent()) ?? '').trim());
    await button.click();
    await page.waitForTimeout(200);
  }
  expect(seen.join(' | ')).not.toContain('Closing soonest');
});

test('the bucket drill-down stays two panes without subtypes', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await pickBatBucket(page, 0, 0);

  await page.locator('[data-testid="bucket-button"]').click();
  await expect(page.locator('[data-testid="bucket-popover"]')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('[data-testid="bucket-level-0"]')).toBeVisible();
  await expect(page.locator('[data-testid="bucket-level-1"]')).toBeVisible();
  await expect(page.locator('[data-testid="subtype-level"]')).toHaveCount(0);
});
