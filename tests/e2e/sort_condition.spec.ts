import { test, expect } from '@playwright/test';
import { shownCount, inFilters, openFilters, closeFilters, clearAll, pickBatBucket } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

// Read the resale figure from the first visible lot card (NaN if unparseable).
// The redesign drops the "Resale ~" label — money is greyscale and unlabelled,
// separated from retail by size and weight — so the figure reads plain "$X".
async function firstCardResale(page: import('@playwright/test').Page): Promise<number> {
  const card = page.locator('[data-testid="lot-card"]').first();
  const summary = card.locator('[data-testid="resale-summary"]');
  // A lot the valuation pass could not price now shows no figure at all rather
  // than "$0"; its sort key is still 0, which is what it contributes here.
  if ((await summary.count()) === 0) return 0;
  const txt = (await summary.textContent()) ?? '';
  const m = txt.match(/\$([\d,]+)/);
  return m ? parseInt(m[1].replace(/,/g, ''), 10) : NaN;
}

test('sort control reorders by resale (high→low vs low→high)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // The explicit four-way sort now lives in the filters overlay; the rail
  // carries a button that cycles the three common orders.
  await inFilters(page, async () => {
    await page.locator('[data-testid="sort-select"]').selectOption('resale-desc');
  });
  const top = await firstCardResale(page);
  expect(Number.isNaN(top)).toBeFalsy();

  await inFilters(page, async () => {
    await page.locator('[data-testid="sort-select"]').selectOption('resale-asc');
  });
  const bottom = await firstCardResale(page);
  expect(Number.isNaN(bottom)).toBeFalsy();

  // High→low's leader must be >= low→high's leader.
  expect(top).toBeGreaterThanOrEqual(bottom);
});

test('sort changes order but not the result count', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const before = await shownCount(page);
  await inFilters(page, async () => {
    await page.locator('[data-testid="sort-select"]').selectOption('retail-desc');
  });
  const after = await shownCount(page);
  expect(after).toBe(before); // sort never filters
});

test('the rail sort button cycles lot → resale → retail', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const button = page.locator('[data-testid="sort-button"]');
  const before = await shownCount(page);
  await expect(button).toContainText('Lot number');

  await button.click();
  await expect(button).toContainText('Resale');
  await button.click();
  await expect(button).toContainText('Retail');
  await button.click();
  await expect(button).toContainText('Lot number'); // wraps

  expect(await shownCount(page)).toBe(before); // cycling never filters
});

test('condition chips narrow the visible lots and compose with clear-filters', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  expect(total).toBeGreaterThan(0);

  // Toggle the "Good" condition chip → fewer lots than the unfiltered total.
  const chip = page.locator('[data-testid="condition-chip-Good"]');
  await openFilters(page);
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(chip).toHaveAttribute('aria-pressed', 'true');
  await closeFilters(page);

  // The selection surfaces on the rail as a removable chip.
  await expect(page.locator('[data-testid="chip-condition-Good"]')).toBeVisible();
  const narrowed = await shownCount(page);
  expect(narrowed).toBeLessThan(total);
  expect(narrowed).toBeGreaterThan(0);

  // Adding a second condition is a union → count grows vs the single chip.
  await inFilters(page, async () => {
    await page.locator('[data-testid="condition-chip-New"]').click();
  });
  const unioned = await shownCount(page);
  expect(unioned).toBeGreaterThan(narrowed);

  // Clear resets the condition chips and the count.
  await clearAll(page);
  expect(await shownCount(page)).toBe(total);
  await inFilters(page, async () => {
    await expect(chip).toHaveAttribute('aria-pressed', 'false');
  });
});

test('sort + condition compose inside a Bat\'s List bucket', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await pickBatBucket(page);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();

  // Sort + condition controls are still reachable inside the bucket view.
  await openFilters(page);
  await expect(page.locator('[data-testid="sort-select"]')).toBeVisible();
  await expect(page.locator('[data-testid="condition-chip-New"]')).toBeVisible();
  await closeFilters(page);

  const inBucket = await shownCount(page);
  // A condition chip narrows within the bucket (never widens beyond it).
  await inFilters(page, async () => {
    await page.locator('[data-testid="condition-chip-New"]').click();
  });
  const narrowed = await shownCount(page);
  expect(narrowed).toBeLessThanOrEqual(inBucket);
});
