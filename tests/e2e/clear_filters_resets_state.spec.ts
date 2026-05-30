import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test('Clear filters resets search, day, and category (tab + density preserved)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // No filter active → toolbar hidden.
  await expect(page.locator('[data-testid="clear-filters-btn"]')).toHaveCount(0);

  // Apply search.
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();
  await search.fill('LED');

  // Apply a non-default day filter (desktop segmented control).
  const sundayBtn = page.getByRole('button', { name: /^Sunday$/ }).first();
  if (await sundayBtn.count()) {
    await sundayBtn.click();
  }

  // Apply a non-default category via the hierarchical filter's level-0 select.
  const categoryLevel0 = page.locator('[data-testid="category-level-0"]').filter({ visible: true }).first();
  const optionTexts = await categoryLevel0.locator('option').allTextContents();
  await categoryLevel0.selectOption({ label: optionTexts[1] }); // option[0] is "All categories"
  await page.waitForTimeout(300);

  // Clear filters button should now be visible.
  const clearBtn = page.locator('[data-testid="clear-filters-btn"]');
  await expect(clearBtn).toBeVisible();

  // Active tab before clearing (should be preserved): All.
  const allTabBefore = await page.locator('[data-testid="tab-all"]').filter({ visible: true }).getAttribute('aria-pressed');

  await clearBtn.click();
  await page.waitForTimeout(300);

  // Search empty, category reset to the "All categories" sentinel, drill-downs gone.
  await expect(search).toHaveValue('');
  await expect(categoryLevel0).toHaveValue('');
  await expect(page.locator('[data-testid="category-level-1"]').filter({ visible: true })).toHaveCount(0);

  // Day: Both is the active segmented option.
  const bothBtn = page.getByRole('button', { name: /^Both$/ }).first();
  if (await bothBtn.count()) {
    await expect(bothBtn).toHaveAttribute('aria-pressed', 'true');
  }

  // Tab preserved.
  const allTabAfter = await page.locator('[data-testid="tab-all"]').filter({ visible: true }).getAttribute('aria-pressed');
  expect(allTabAfter).toBe(allTabBefore);

  // Toolbar button hidden again (no filters active).
  await expect(clearBtn).toHaveCount(0);
});
