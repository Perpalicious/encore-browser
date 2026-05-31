import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

// The resale filters (confidence + "Potential resales") narrow the current
// view. These assertions are written to hold whether or not the loaded bundle
// actually contains resale valuations: the invariant under each filter is that
// every lot still shown is a valued lot, and that clearing restores the count.
//
// Rendered card counts are unreliable here (the grid is virtualized), so the
// stable signal is the header "Showing X of Y" count.
test.use({ viewport: { width: 1280, height: 900 } });

const VISIBLE_TOGGLE = '[data-testid="potential-resales-toggle"]:visible';

// Returns [filteredCount, totalCount] parsed from the visible result-count.
async function counts(page: Page): Promise<[number, number]> {
  const text = (await page.locator('[data-testid="result-count"]:visible').textContent()) ?? '';
  const nums = (text.match(/\d+/g) ?? []).map(Number);
  return [nums[0] ?? 0, nums[1] ?? 0];
}

async function ready(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);
}

test('potential-resales filter shows only valued lots, then clears', async ({ page }) => {
  await ready(page);
  const [, total] = await counts(page);
  expect(total).toBeGreaterThan(0);

  const toggle = page.locator(VISIBLE_TOGGLE);
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');

  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await page.waitForTimeout(500);

  // Filtered total is a subset of the full view.
  const [filtered] = await counts(page);
  expect(filtered).toBeLessThanOrEqual(total);

  // Invariant: every lot card currently rendered is a valued lot (has a resale
  // summary). True for 0 (empty state) or N rendered cards.
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const summaries = await page.locator('[data-testid="resale-summary"]').count();
  expect(summaries).toBe(cards);

  // Clear filters restores the full count and un-presses the toggle.
  const clear = page.locator('[data-testid="clear-filters-btn"]');
  await expect(clear).toBeVisible();
  await clear.click();
  await page.waitForTimeout(400);
  await expect(page.locator(VISIBLE_TOGGLE)).toHaveAttribute('aria-pressed', 'false');
  expect((await counts(page))[0]).toBe(total);
});

test('confidence filter (High) narrows to valued lots and is reversible', async ({ page }) => {
  await ready(page);
  const [, total] = await counts(page);

  await page.locator('[data-testid="confidence-high"]:visible').click();
  await page.waitForTimeout(500);

  const [filtered] = await counts(page);
  expect(filtered).toBeLessThanOrEqual(total);

  // Every shown lot is valued (un-valued lots have null confidence → dropped).
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const summaries = await page.locator('[data-testid="resale-summary"]').count();
  expect(summaries).toBe(cards);

  // Back to "All" restores the full count.
  await page.locator('[data-testid="confidence-all"]:visible').click();
  await page.waitForTimeout(400);
  expect((await counts(page))[0]).toBe(total);
});
