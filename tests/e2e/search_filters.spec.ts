import { test, expect } from '@playwright/test';
import { shownCount } from './helpers';

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
