import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test('Clear filters resets search, day, category, and bucket', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // No filter active → toolbar hidden.
  await expect(page.locator('[data-testid="clear-filters-btn"]')).toHaveCount(0);

  // Apply search.
  const search = page.locator('[data-testid="search-input"]').filter({ visible: true }).first();
  await search.fill('LED');

  // Apply a non-default day filter via the visible Day segmented control.
  // The desktop layout exposes Sunday/Monday/Both as buttons; click "Sunday".
  const sundayBtn = page.getByRole('button', { name: /^Sunday$/ }).first();
  if (await sundayBtn.count()) {
    await sundayBtn.click();
  }

  // Apply a non-default category via the hierarchical filter's level-0 select.
  const categoryLevel0 = page.locator('[data-testid="category-level-0"]').filter({ visible: true }).first();
  const optionTexts = await categoryLevel0.locator('option').allTextContents();
  const target = optionTexts[1]; // option[0] is the "All categories" sentinel
  await categoryLevel0.selectOption({ label: target });

  // Switch to Bat's List tab so we can pick a bucket chip.
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  // Pick the first non-"All" bucket chip if present (sample bat lots may include several).
  const bucketChips = page.locator('button[aria-pressed]', { hasText: /./ });
  const chipCount = await bucketChips.count();
  for (let i = 0; i < chipCount; i++) {
    const chip = bucketChips.nth(i);
    const label = (await chip.textContent() || '').trim();
    if (label && label !== 'All' && !/^(Sunday|Monday|Both|Standard|Compact|All|Bat|Nice|Watched)/.test(label)) {
      await chip.click();
      break;
    }
  }

  // Clear filters button should now be visible.
  const clearBtn = page.locator('[data-testid="clear-filters-btn"]');
  await expect(clearBtn).toBeVisible();

  // Capture the active tab BEFORE clicking, so we can verify it's preserved.
  const tabBefore = await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).getAttribute('aria-pressed');

  await clearBtn.click();
  await page.waitForTimeout(300);

  // Search empty
  await expect(search).toHaveValue('');

  // Category filter reset: level-0 select back to the "All categories" sentinel
  // (value="") and no deeper drill-down selects present.
  await expect(categoryLevel0).toHaveValue('');
  await expect(page.locator('[data-testid="category-level-1"]').filter({ visible: true })).toHaveCount(0);

  // Day: Both is the active segmented option
  const bothBtn = page.getByRole('button', { name: /^Both$/ }).first();
  if (await bothBtn.count()) {
    await expect(bothBtn).toHaveAttribute('aria-pressed', 'true');
  }

  // Tab preserved (still 'bat')
  const tabAfter = await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).getAttribute('aria-pressed');
  expect(tabAfter).toBe(tabBefore);

  // Toolbar button itself should now be hidden again (no filters active).
  await expect(clearBtn).toHaveCount(0);
});
