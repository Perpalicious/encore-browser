import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// Parse the visible "Showing N of M lots" header into N.
async function shownCount(page: import('@playwright/test').Page): Promise<number> {
  const txt =
    (await page.locator('[data-testid="result-count"]').filter({ visible: true }).first().textContent()) ??
    '';
  return parseInt((txt.match(/(\d[\d,]*)/) ?? [])[1]?.replace(/,/g, '') ?? '-1', 10);
}

// Read the resale "~$X" figure from the first visible lot card (NaN if none).
async function firstCardResale(page: import('@playwright/test').Page): Promise<number> {
  const card = page.locator('[data-testid="lot-card"]').first();
  const summary = card.locator('[data-testid="resale-summary"]');
  const txt = (await summary.textContent()) ?? '';
  const m = txt.match(/~\$([\d,]+)/);
  return m ? parseInt(m[1].replace(/,/g, ''), 10) : NaN;
}

test('sort control reorders by resale (high→low vs low→high)', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const sort = page.locator('[data-testid="sort-select"]').filter({ visible: true }).first();
  await expect(sort).toBeVisible();

  // Resale high → low: the top card carries the largest resale figure.
  await sort.selectOption('resale-desc');
  await page.waitForTimeout(300);
  const top = await firstCardResale(page);
  expect(Number.isNaN(top)).toBeFalsy();

  // Resale low → high: the top card carries the smallest resale figure.
  await sort.selectOption('resale-asc');
  await page.waitForTimeout(300);
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
  const sort = page.locator('[data-testid="sort-select"]').filter({ visible: true }).first();
  await sort.selectOption('retail-desc');
  await page.waitForTimeout(300);
  const after = await shownCount(page);
  expect(after).toBe(before); // sort never filters
});

test('condition chips narrow the visible lots and compose with clear-filters', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const total = await shownCount(page);
  expect(total).toBeGreaterThan(0);

  // Toggle the "Good" condition chip → fewer lots than the unfiltered total.
  const chip = page.locator('[data-testid="condition-chip-Good"]').filter({ visible: true }).first();
  await expect(chip).toBeVisible();
  await chip.click();
  await page.waitForTimeout(300);
  await expect(chip).toHaveAttribute('aria-pressed', 'true');
  const narrowed = await shownCount(page);
  expect(narrowed).toBeLessThan(total);
  expect(narrowed).toBeGreaterThan(0);

  // Adding a second condition is a union → count grows vs the single chip.
  const chip2 = page.locator('[data-testid="condition-chip-New"]').filter({ visible: true }).first();
  await chip2.click();
  await page.waitForTimeout(300);
  const unioned = await shownCount(page);
  expect(unioned).toBeGreaterThan(narrowed);

  // Clear filters resets the condition chips and the count.
  await page.locator('[data-testid="clear-filters-btn"]').click();
  await page.waitForTimeout(300);
  await expect(chip).toHaveAttribute('aria-pressed', 'false');
  expect(await shownCount(page)).toBe(total);
});

test('sort + condition compose inside a Bat\'s List bucket', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  const dropdown = page.locator('[data-testid="bat-bucket-dropdown"]');
  // Pick the bucket with the largest advertised count for a roomy sample.
  const options = dropdown.locator('optgroup option');
  const n = await options.count();
  let bestVal = '';
  let bestCount = -1;
  for (let i = 0; i < n; i++) {
    const label = (await options.nth(i).textContent()) ?? '';
    const c = parseInt((label.match(/\((\d+)\)\s*$/) ?? [])[1] ?? '-1', 10);
    if (c > bestCount) {
      bestCount = c;
      bestVal = (await options.nth(i).getAttribute('value')) ?? '';
    }
  }
  await dropdown.selectOption(bestVal);
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();

  // Sort + condition controls are available inside the bucket view.
  await expect(page.locator('[data-testid="sort-select"]').filter({ visible: true }).first()).toBeVisible();
  await expect(page.locator('[data-testid="condition-filter"]').filter({ visible: true }).first()).toBeVisible();

  const inBucket = await shownCount(page);
  // A condition chip narrows within the bucket (never widens beyond it).
  const chip = page.locator('[data-testid="condition-chip-New"]').filter({ visible: true }).first();
  await chip.click();
  await page.waitForTimeout(300);
  const narrowed = await shownCount(page);
  expect(narrowed).toBeLessThanOrEqual(inBucket);
});
