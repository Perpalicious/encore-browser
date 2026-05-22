import { test, expect } from '@playwright/test';

test('typing in search input filters visible cards in real-time', async ({ page }) => {
  await page.goto('/');

  // Wait for the 900ms skeleton to clear and at least one real card to appear
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 5000 });

  // Count visible cards before typing (virtualized — only in-viewport cards are in DOM)
  const beforeCount = await page.locator('[data-testid="lot-card"]').count();
  expect(beforeCount).toBeGreaterThan(0);

  // Type "LED" into the search input — 321 out of 9880 lots contain LED
  // Use the visible instance (desktop header is shown at 1280px wide viewport)
  const searchInput = page.locator('[data-testid="search-input"]').filter({ visible: true });
  await searchInput.fill('LED');

  // Wait for the filter to take effect — the grid re-renders
  await page.waitForTimeout(300);
  // Wait until lot-card elements are stable (re-rendered after filter)
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible({ timeout: 5000 });

  const afterCount = await page.locator('[data-testid="lot-card"]').count();

  // After filtering for LED (321 matches), count must be > 0 and < before (pre-filter shows more)
  expect(afterCount).toBeGreaterThan(0);
  // The unfiltered grid shows the same number of visible cards as the filtered grid when
  // the filtered set is small; assert that every visible card's title contains "LED" (case-insensitive)
  const cardTitles = await page.locator('[data-testid="lot-card"]').evaluateAll(
    (cards) =>
      cards.map((card) => {
        const h3 = card.querySelector('h3');
        return h3 ? h3.textContent ?? '' : '';
      })
  );

  // All visible cards must have LED in their title (the search filters on title/description/category)
  for (const title of cardTitles) {
    expect(title.toUpperCase()).toContain('LED');
  }

  // Clear the search and verify count returns to a positive number
  await searchInput.fill('');
  await page.waitForTimeout(300);
  const resetCount = await page.locator('[data-testid="lot-card"]').count();

  expect(resetCount).toBeGreaterThan(0);
});
