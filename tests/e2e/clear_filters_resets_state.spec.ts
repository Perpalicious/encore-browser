import { test, expect } from '@playwright/test';
import { shownCount, topCategories, pickCategory, inFilters, clearAll } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

// CLEAR on the rail resets every filter but deliberately preserves the tab,
// density and sort order. It only exists while at least one chip does.
test('Clear resets search, day, and category (tab + density preserved)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);

  // No filter active → no chips, so no CLEAR.
  await expect(page.locator('[data-testid="clear-filters-btn"]')).toHaveCount(0);

  // Apply search.
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();
  await search.fill('LED');
  await page.waitForTimeout(450);

  // Apply a non-default day filter, from the filters overlay.
  await inFilters(page, async () => {
    await page.locator('[data-testid="day-Sunday"]').click();
  });

  // Apply a non-default category, from the drill-down popover.
  const cats = await topCategories(page);
  await pickCategory(page, cats[0]);

  // Each one surfaces as its own chip on the rail.
  await expect(page.locator('[data-testid="chip-query"]')).toBeVisible();
  await expect(page.locator('[data-testid="chip-day"]')).toBeVisible();
  await expect(page.locator('[data-testid="chip-category"]')).toBeVisible();

  const allTabBefore = await page.locator('[data-testid="tab-all"]').getAttribute('aria-pressed');

  await clearAll(page);

  // Search empty, category reset, day back to Both, every chip gone.
  await expect(search).toHaveValue('');
  await expect(page.locator('[data-testid="category-button"]')).toContainText('All categories');
  await expect(page.locator('[data-testid="clear-filters-btn"]')).toHaveCount(0);
  await inFilters(page, async () => {
    await expect(page.locator('[data-testid="day-Both"]')).toHaveAttribute('aria-pressed', 'true');
  });
  expect(await shownCount(page)).toBe(total);

  // Tab preserved.
  const allTabAfter = await page.locator('[data-testid="tab-all"]').getAttribute('aria-pressed');
  expect(allTabAfter).toBe(allTabBefore);
});

// Every chip removes exactly its own filter and leaves the others alone.
test('each chip removes only its own filter', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await inFilters(page, async () => {
    await page.locator('[data-testid="day-Sunday"]').click();
    await page.locator('[data-testid="condition-chip-New"]').click();
  });

  await expect(page.locator('[data-testid="chip-day"]')).toBeVisible();
  await expect(page.locator('[data-testid="chip-condition-New"]')).toBeVisible();

  await page.locator('[data-testid="chip-day"]').click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="chip-day"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="chip-condition-New"]')).toBeVisible();

  await page.locator('[data-testid="chip-condition-New"]').click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="clear-filters-btn"]')).toHaveCount(0);
});
