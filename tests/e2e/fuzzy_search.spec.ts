import { test, expect, Page } from '@playwright/test';

async function shownCount(page: Page): Promise<number> {
  const text =
    (await page.locator('header').getByText(/Showing .* of .* lots/).first().textContent()) ?? '';
  const m = text.match(/Showing\s+([\d,]+)\s+of/);
  return m ? parseInt(m[1].replace(/,/g, ''), 10) : -1;
}

// End-to-end proof that fuzzy search is wired into the real app. The precise
// "kitchenad → KitchenAid" match semantics are unit-tested in
// viewer/src/lib/search.test.ts against a controlled dataset; here we confirm
// the live app tolerates a typo that an exact-substring search could not.
test('fuzzy search tolerates a typo the substring search could not (kitchenad)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();

  // "kitchenad" is not a substring of "KITCHENAID" (missing the final 'i'),
  // so an exact-substring search returns 0. Fuzzy must still find lots.
  await search.fill('kitchenad');
  await page.waitForTimeout(450);
  const typoCount = await shownCount(page);
  expect(typoCount).toBeGreaterThan(0);
  expect(typoCount).toBeLessThan(total);

  // The correctly-spelled query should find a comparable set — the typo isn't
  // matching unrelated noise.
  await search.fill('kitchenaid');
  await page.waitForTimeout(450);
  const correctCount = await shownCount(page);
  expect(correctCount).toBeGreaterThan(0);
  // Typo recall is at least half of the correctly-spelled result set.
  expect(typoCount).toBeGreaterThanOrEqual(correctCount * 0.5);
});
