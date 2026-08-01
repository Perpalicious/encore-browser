import { test, expect } from '@playwright/test';
import { ready, shownCount, inFilters } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

// View state goes to BOTH the URL hash and localStorage, so a filtered view is
// a link you can send someone at the venue. The hash wins on load.

test('filters land in the URL hash and survive a reload', async ({ page }) => {
  await ready(page);
  const total = await shownCount(page);

  // A pristine view leaves the URL clean rather than writing default noise.
  expect(page.url()).not.toContain('#s=');

  await page.locator('[data-testid="search-input"]').fill('dewalt');
  await inFilters(page, async () => {
    await page.locator('[data-testid="condition-chip-New"]').click();
  });
  await page.waitForTimeout(600); // past the 350ms debounce

  const url = page.url();
  expect(url).toContain('#s=');
  const narrowed = await shownCount(page);
  expect(narrowed).toBeLessThan(total);

  await page.reload();
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(600);
  await expect(page.locator('[data-testid="search-input"]')).toHaveValue('dewalt');
  await expect(page.locator('[data-testid="chip-condition-New"]')).toBeVisible();
  expect(await shownCount(page)).toBe(narrowed);
});

test('a shared link reproduces the view in a clean session', async ({ page, browser }) => {
  await ready(page);
  await page.locator('[data-testid="search-input"]').fill('lego');
  await page.waitForTimeout(600);
  const shared = page.url();
  const expected = await shownCount(page);
  expect(shared).toContain('#s=');

  // A brand-new context has no localStorage — the hash alone must carry it.
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const fresh = await context.newPage();
  await fresh.goto(shared);
  await fresh.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await fresh.waitForTimeout(600);
  await expect(fresh.locator('[data-testid="search-input"]')).toHaveValue('lego');
  expect(await shownCount(fresh)).toBe(expected);
  await context.close();
});

test('a malformed hash falls back to defaults instead of breaking', async ({ page }) => {
  await page.goto('/#s=%7Bnot-json');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);
  await expect(page.locator('[data-testid="search-input"]')).toHaveValue('');
  expect(await shownCount(page)).toBeGreaterThan(100);
});

test('the watch list stays out of the shareable hash', async ({ page }) => {
  await ready(page);
  await page.locator('[data-testid="lot-card"]').first().locator('[data-testid="star-btn"]').click();
  await page.waitForTimeout(600);
  // Watched is yours alone: localStorage only, never the URL.
  expect(page.url()).not.toContain('#s=');
  await expect(page.locator('[data-testid="tab-watched"]')).toContainText('1');
});
