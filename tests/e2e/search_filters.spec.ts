import { test, expect, Page } from '@playwright/test';

// Read the "Showing N of M lots" count from the sticky header.
async function shownCount(page: Page): Promise<number> {
  const text =
    (await page.locator('header').getByText(/Showing .* of .* lots/).first().textContent()) ?? '';
  const m = text.match(/Showing\s+([\d,]+)\s+of/);
  return m ? parseInt(m[1].replace(/,/g, ''), 10) : -1;
}

test('typing in search input filters lots in real-time', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  expect(total).toBeGreaterThan(100);

  // "LED" is a common term in the sample auction — narrows but keeps many lots.
  const searchInput = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();
  await searchInput.fill('LED');
  // debounce (150ms) + re-render
  await page.waitForTimeout(450);

  const afterCount = await shownCount(page);
  expect(afterCount).toBeGreaterThan(0);
  expect(afterCount).toBeLessThan(total);

  // Clearing restores the full set.
  await searchInput.fill('');
  await page.waitForTimeout(450);
  expect(await shownCount(page)).toBe(total);
});
