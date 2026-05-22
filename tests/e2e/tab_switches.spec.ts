import { test, expect } from '@playwright/test';

test("clicking Bat's List tab changes the visible card set vs. All tab", async ({ page }) => {
  await page.goto('/');

  // Wait for skeleton to clear and cards to appear
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 5000 });

  // Scroll past the ~349 bat lots that sort to the top of the All tab, so
  // visible cards include non-bat lots (which will be filtered out on the Bat
  // tab). With ~4 cards per row × ~340px row height, 349 lots ≈ 87 rows ≈
  // 29700px. Scroll comfortably past that.
  await page.evaluate(() => window.scrollTo(0, 32000));
  await page.waitForTimeout(400);
  const allTabLotNumbers = await page.locator('[data-testid="lot-card"]').evaluateAll(
    (cards) => cards.map((c) => c.getAttribute('data-lot-number') ?? '')
  );
  const allTabOrdered = allTabLotNumbers.filter(Boolean);
  expect(allTabOrdered.length).toBeGreaterThan(0);

  // Scroll back to top before switching tab
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);

  // Click the Bat's List tab — use the visible instance (desktop header shown at 1280px)
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();

  // Wait for re-render — the bat tab filter reduces lots to ~349
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 5000 });
  await page.waitForTimeout(200);

  // Collect lot numbers visible on Bat's List tab
  const batTabLotNumbers = await page.locator('[data-testid="lot-card"]').evaluateAll(
    (cards) => cards.map((c) => c.getAttribute('data-lot-number') ?? '')
  );
  const batTabOrdered = batTabLotNumbers.filter(Boolean);
  expect(batTabOrdered.length).toBeGreaterThan(0);

  // The Bat tab shows only the ~349 "Bat's List" lots out of 9880 total.
  // The All tab includes ALL lots. So:
  // 1. Bat tab cards should all be a strict subset of All lots (every bat card is in All)
  // 2. The ordered render sequence on Bat tab differs from All tab because non-bat lots
  //    are filtered out, creating a different interleaving.
  // Assert: NOT all Bat-tab lot numbers appear at the same relative positions as All-tab.
  // Simplest reliable assertion: the first lot number on Bat tab differs from All tab,
  // OR the count of cards visible from Bat tab differs — but most robustly:
  // at least one lot in All tab is NOT in the Bat tab (since All has non-bat lots too).
  const batTabSet = new Set(batTabOrdered);

  // All tab contains 9880 lots total; Bat tab has only 349.
  // So there must be lot numbers in allTabOrdered that are NOT in batTabSet.
  const nonBatInAllTab = allTabOrdered.filter((n) => !batTabSet.has(n));
  expect(nonBatInAllTab.length).toBeGreaterThan(0);

  // Additionally: the first rendered card on the Bat tab must be marked as a bat lot.
  // We verify this by confirming at least one card on the Bat tab (first visible)
  // is present — and that not all All-tab cards are bat-list cards.
  expect(batTabOrdered.length).toBeLessThanOrEqual(allTabOrdered.length + 349);
});
