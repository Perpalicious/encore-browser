import { test, expect } from '@playwright/test';
import { shownCount } from './helpers';

// Search is EXACT by default; fuzzy is an opt-in toggle. This confirms both the
// default (a typo finds nothing) and that flipping the "Fuzzy" toggle makes the
// same typo recover matches. Precise match semantics are unit-tested in
// viewer/src/lib/search.test.ts.
test('exact by default; the Fuzzy toggle recovers a typo (kitchenad)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();
  const fuzzy = page.locator('[data-testid="fuzzy-toggle"]:visible');

  // Default is exact: it starts un-pressed.
  await expect(fuzzy).toHaveAttribute('aria-pressed', 'false');

  // "kitchenad" is not a substring of "KITCHENAID" (missing the final 'i'), so
  // exact search returns 0.
  await search.fill('kitchenad');
  await page.waitForTimeout(450);
  expect(await shownCount(page)).toBe(0);

  // Turn Fuzzy on — the same typo now recovers matches (a subset of all lots).
  await fuzzy.click();
  await expect(fuzzy).toHaveAttribute('aria-pressed', 'true');
  await page.waitForTimeout(450);
  const typoCount = await shownCount(page);
  expect(typoCount).toBeGreaterThan(0);
  expect(typoCount).toBeLessThan(total);

  // The correctly-spelled query (still in fuzzy mode) finds a comparable set —
  // the typo isn't matching unrelated noise.
  await search.fill('kitchenaid');
  await page.waitForTimeout(450);
  const correctCount = await shownCount(page);
  expect(correctCount).toBeGreaterThan(0);
  expect(typoCount).toBeGreaterThanOrEqual(correctCount * 0.5);
});

// A real substring query works the same in either mode and stays a subset.
test('exact substring search narrows in the default mode (dewalt)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();

  await search.fill('dewalt');
  await page.waitForTimeout(450);
  const n = await shownCount(page);
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThan(total);

  await search.fill('');
  await page.waitForTimeout(450);
  expect(await shownCount(page)).toBe(total);
});
