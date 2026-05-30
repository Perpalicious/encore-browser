import { test, expect, Page } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// Read the "Showing N of M lots" count from the sticky header (always present).
async function shownCount(page: Page): Promise<number> {
  const text = (await page.locator('header').getByText(/Showing .* of .* lots/).first().textContent()) ?? '';
  const m = text.match(/Showing\s+([\d,]+)\s+of/);
  return m ? parseInt(m[1].replace(/,/g, ''), 10) : -1;
}

test('hierarchical category filter drills down and narrows results', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  expect(total).toBeGreaterThan(100); // sample auction is ~9880 lots

  // Level 0 select exists; pick the first real top-level category.
  // (mobile + desktop headers both render one; target the visible/desktop one)
  const level0 = page.locator('[data-testid="category-level-0"]').filter({ visible: true }).first();
  await expect(level0).toBeVisible();
  const topOptions = await level0.locator('option').allTextContents();
  // option[0] is the "All categories" sentinel; option[1] is the first category.
  const firstCategory = topOptions[1];
  expect(firstCategory).toBeTruthy();
  await level0.selectOption({ label: firstCategory });
  await page.waitForTimeout(300);

  const afterTop = await shownCount(page);
  expect(afterTop).toBeGreaterThan(0);
  expect(afterTop).toBeLessThan(total); // narrowed to one top-level branch

  // A level-1 drill-down select should now appear (top categories have children).
  const level1 = page.locator('[data-testid="category-level-1"]').filter({ visible: true }).first();
  await expect(level1).toBeVisible();

  // Drill into the first subcategory.
  const subOptions = await level1.locator('option').allTextContents();
  if (subOptions.length > 1) {
    await level1.selectOption({ label: subOptions[1] });
    await page.waitForTimeout(300);
    const afterSub = await shownCount(page);
    expect(afterSub).toBeGreaterThan(0);
    expect(afterSub).toBeLessThanOrEqual(afterTop); // narrower or equal
  }

  // Selecting the "All categories" sentinel at level 0 resets to the full set.
  await level0.selectOption({ value: '' });
  await page.waitForTimeout(300);
  expect(await shownCount(page)).toBe(total);
  // Drill-down selects collapse away once the prefix is cleared.
  await expect(page.locator('[data-testid="category-level-1"]').filter({ visible: true })).toHaveCount(0);
});
