import { test, expect } from '@playwright/test';
import { shownCount, topCategories, pickCategory } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

// The category filter is a two-pane drill-down popover anchored under the rail:
// categories with counts on the left, sub-categories of the selection on the
// right. It replaces the cascading <select> chain, which needed one interaction
// per level and showed no counts.
test('the category popover drills down and narrows results', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  expect(total).toBeGreaterThan(100);

  // Before anything is picked, the rail button reads "All categories".
  const railButton = page.locator('[data-testid="category-button"]');
  await expect(railButton).toContainText('All categories');

  const cats = await topCategories(page);
  expect(cats.length).toBeGreaterThan(1);

  // Pick the largest top-level category (the popover sorts by count desc).
  await pickCategory(page, cats[0]);
  const afterTop = await shownCount(page);
  expect(afterTop).toBeGreaterThan(0);
  expect(afterTop).toBeLessThan(total); // narrowed to one branch
  // The rail button now names the selection and surfaces a removable chip.
  await expect(railButton).toContainText(cats[0]);
  await expect(page.locator('[data-testid="chip-category"]')).toBeVisible();

  // Drill into a sub-category — picking one closes the popover by itself.
  await railButton.click();
  const popover = page.locator('[data-testid="category-popover"]');
  await expect(popover).toBeVisible();
  const subs = await popover
    .locator('[data-testid="category-level-1"] button span:first-child')
    .allTextContents();
  expect(subs.length).toBeGreaterThan(0);
  await popover
    .locator('[data-testid="category-level-1"] button')
    .filter({ hasText: subs[0] })
    .first()
    .click();
  await expect(popover).toHaveCount(0);
  await page.waitForTimeout(300);

  const afterSub = await shownCount(page);
  expect(afterSub).toBeGreaterThan(0);
  expect(afterSub).toBeLessThanOrEqual(afterTop);
  await expect(railButton).toContainText(subs[0]);

  // "All categories" clears both levels.
  await railButton.click();
  await page.locator('[data-testid="category-all"]').click();
  await page.waitForTimeout(300);
  expect(await shownCount(page)).toBe(total);
  await expect(railButton).toContainText('All categories');
  await expect(page.locator('[data-testid="chip-category"]')).toHaveCount(0);
});

test('each pane shows lot counts, largest first', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await page.locator('[data-testid="category-button"]').click();
  const pane = page.locator('[data-testid="category-level-0"]');
  await expect(pane).toBeVisible();

  const counts = (await pane.locator('button span:last-child').allTextContents()).map((t) =>
    parseInt(t.replace(/,/g, ''), 10)
  );

  expect(counts.length).toBeGreaterThan(1);
  expect(counts.every((n) => n > 0)).toBe(true);
  // Sorted descending, so the biggest branches are reachable without scrolling.
  for (let i = 1; i < counts.length; i++) {
    expect(counts[i]).toBeLessThanOrEqual(counts[i - 1]);
  }
  // The right pane prompts rather than sitting blank until a category is picked.
  await expect(page.locator('[data-testid="category-level-1"]')).toContainText('PICK A CATEGORY');
});
