import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { counts, inFilters, openFilters, closeFilters, clearAll } from './helpers';

// The resale filters (confidence + "Potential resales") narrow the current
// view. These assertions are written to hold whether or not the loaded bundle
// actually contains resale valuations: the invariant under each filter is that
// every lot still shown is a valued lot, and that clearing restores the count.
//
// Rendered card counts are unreliable here (the grid is virtualized), so the
// stable signal is the header "Showing X of Y" count.
test.use({ viewport: { width: 1280, height: 900 } });

const VISIBLE_TOGGLE = '[data-testid="potential-resales-toggle"]:visible';

async function ready(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);
}

test('potential-resales filter shows only valued lots, then clears', async ({ page }) => {
  await ready(page);
  const [, total] = await counts(page);
  expect(total).toBeGreaterThan(0);

  // The toggle lives in the filters overlay now; its state surfaces on the rail
  // as a chip once it is on.
  await openFilters(page);
  const toggle = page.locator(VISIBLE_TOGGLE);
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await closeFilters(page);
  await expect(page.locator('[data-testid="chip-resales"]')).toBeVisible();

  // Filtered total is a subset of the full view.
  const [filtered] = await counts(page);
  expect(filtered).toBeLessThanOrEqual(total);

  // Invariant: every lot card currently rendered is a valued lot (has a resale
  // summary). True for 0 (empty state) or N rendered cards.
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const summaries = await page.locator('[data-testid="resale-summary"]').count();
  expect(summaries).toBe(cards);

  // Clear restores the full count and un-presses the toggle.
  await clearAll(page);
  expect((await counts(page))[0]).toBe(total);
  await inFilters(page, async () => {
    await expect(page.locator(VISIBLE_TOGGLE)).toHaveAttribute('aria-pressed', 'false');
  });
});

test('confidence filter (High) narrows to valued lots and is reversible', async ({ page }) => {
  await ready(page);
  const [, total] = await counts(page);

  await inFilters(page, async () => {
    await page.locator('[data-testid="confidence-high"]:visible').click();
  });

  const [filtered] = await counts(page);
  expect(filtered).toBeLessThanOrEqual(total);

  // Every shown lot is valued (un-valued lots have null confidence → dropped).
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const summaries = await page.locator('[data-testid="resale-summary"]').count();
  expect(summaries).toBe(cards);

  // Back to "All" restores the full count.
  await inFilters(page, async () => {
    await page.locator('[data-testid="confidence-all"]:visible').click();
  });
  expect((await counts(page))[0]).toBe(total);
});
