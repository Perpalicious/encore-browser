import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { counts, inFilters, openFilters, closeFilters, clearAll } from './helpers';

// The "Personal picks" toggle narrows the current view to lots the
// personal-match pass flagged (personal_match === true). Like the resale
// specs, these assertions hold whether or not the loaded bundle contains
// personal-match data: the invariant under the filter is that every lot still
// rendered carries the personal badge, and clearing restores the full count.
// A bundle with no personal-match fields (older builds) yields zero lots under
// the filter and the full, unchanged view without it.
test.use({ viewport: { width: 1280, height: 900 } });

const VISIBLE_TOGGLE = '[data-testid="personal-picks-toggle"]:visible';

async function ready(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);
}

test('personal-picks toggle narrows to badged lots, then clears', async ({ page }) => {
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
  await expect(page.locator('[data-testid="chip-picks"]')).toBeVisible();

  // Filtered total is a subset of the full view.
  const [filtered] = await counts(page);
  expect(filtered).toBeLessThanOrEqual(total);

  // Invariant: every card still rendered is a personal pick (has the badge).
  // Holds for 0 (empty state / older bundle) or N rendered cards.
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const badges = await page.locator('[data-testid="personal-badge"]').count();
  expect(badges).toBe(cards);

  // Clear restores the full count and un-presses the toggle.
  await clearAll(page);
  expect((await counts(page))[0]).toBe(total);
  await inFilters(page, async () => {
    await expect(page.locator(VISIBLE_TOGGLE)).toHaveAttribute('aria-pressed', 'false');
  });
});

test('personal-picks composes with the resale confidence filter', async ({ page }) => {
  await ready(page);
  const [, total] = await counts(page);

  await inFilters(page, async () => {
    await page.locator(VISIBLE_TOGGLE).click();
  });
  const [personalOnly] = await counts(page);

  // Adding the High confidence filter can only narrow further.
  await inFilters(page, async () => {
    await page.locator('[data-testid="confidence-high"]:visible').click();
  });
  const [both] = await counts(page);
  expect(both).toBeLessThanOrEqual(personalOnly);
  expect(both).toBeLessThanOrEqual(total);

  // Any card that survives both filters carries the personal badge.
  const cards = await page.locator('[data-testid="lot-card"]').count();
  const badges = await page.locator('[data-testid="personal-badge"]').count();
  expect(badges).toBe(cards);
});

test('personal-picks composes with search (narrows within results)', async ({ page }) => {
  await ready(page);

  await page.locator('[data-testid="search-input"]:visible').fill('a');
  await page.waitForTimeout(500);
  const [searchOnly] = await counts(page);

  await inFilters(page, async () => {
    await page.locator(VISIBLE_TOGGLE).click();
  });
  const [both] = await counts(page);
  expect(both).toBeLessThanOrEqual(searchOnly);

  const cards = await page.locator('[data-testid="lot-card"]').count();
  const badges = await page.locator('[data-testid="personal-badge"]').count();
  expect(badges).toBe(cards);
});

test('without the toggle, lots render with no personal badges unless flagged', async ({ page }) => {
  await ready(page);

  // Badges never exceed rendered cards, and appear only on flagged lots —
  // with an older bundle (no personal-match fields) there are exactly zero.
  const cards = await page.locator('[data-testid="lot-card"]').count();
  expect(cards).toBeGreaterThan(0);
  const badges = await page.locator('[data-testid="personal-badge"]').count();
  expect(badges).toBeLessThanOrEqual(cards);
});
