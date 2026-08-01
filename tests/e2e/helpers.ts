import { expect, type Page } from '@playwright/test';

/**
 * Shared helpers for driving the redesigned header.
 *
 * The rail keeps only three buttons — category, sort, filters — and everything
 * they set surfaces as removable chips. So most specs now have to open an
 * overlay to reach a control, and must close it again before touching the rail:
 * the overlays are modal, and their scrim intercepts clicks.
 */

export async function ready(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(400);
}

/**
 * [filtered, total] from the rail's "N / M LOTS" readout.
 * Commas are stripped first — the figures are thousands-separated.
 */
export async function counts(page: Page): Promise<[number, number]> {
  const text = (await page.locator('[data-testid="result-count"]:visible').textContent()) ?? '';
  const nums = (text.replace(/,/g, '').match(/\d+/g) ?? []).map(Number);
  return [nums[0] ?? -1, nums[1] ?? -1];
}

/** Just the filtered count. */
export async function shownCount(page: Page): Promise<number> {
  return (await counts(page))[0];
}

export async function openFilters(page: Page): Promise<void> {
  await page.locator('[data-testid="filters-button"]:visible').first().click();
  await expect(page.locator('[data-testid="filters-overlay"]')).toBeVisible({ timeout: 5000 });
}

export async function closeFilters(page: Page): Promise<void> {
  await page.locator('[data-testid="filters-apply"]').click();
  await expect(page.locator('[data-testid="filters-overlay"]')).toHaveCount(0, { timeout: 5000 });
  await page.waitForTimeout(300);
}

/** Open the filters overlay, run `fn` inside it, then close it. */
export async function inFilters(page: Page, fn: () => Promise<void>): Promise<void> {
  await openFilters(page);
  await fn();
  await closeFilters(page);
}

/**
 * Drill the category popover. `sub` picks a sub-category (which closes the
 * popover by itself); without it, the popover is dismissed via Escape.
 */
export async function pickCategory(page: Page, category: string, sub?: string): Promise<void> {
  await page.locator('[data-testid="category-button"]').click();
  const popover = page.locator('[data-testid="category-popover"]');
  await expect(popover).toBeVisible({ timeout: 5000 });
  await popover.locator('[data-testid="category-level-0"] button', { hasText: category }).first().click();
  if (sub) {
    await popover.locator('[data-testid="category-level-1"] button', { hasText: sub }).first().click();
    await expect(popover).toHaveCount(0, { timeout: 5000 });
  } else {
    await page.keyboard.press('Escape');
    await expect(popover).toHaveCount(0, { timeout: 5000 });
  }
  await page.waitForTimeout(300);
}

/** Names of the top-level categories, in the popover's order. */
export async function topCategories(page: Page): Promise<string[]> {
  await page.locator('[data-testid="category-button"]').click();
  const popover = page.locator('[data-testid="category-popover"]');
  await expect(popover).toBeVisible({ timeout: 5000 });
  const names = await popover
    .locator('[data-testid="category-level-0"] button span:first-child')
    .allTextContents();
  await page.keyboard.press('Escape');
  await expect(popover).toHaveCount(0, { timeout: 5000 });
  return names;
}

/** The rail's CLEAR, which only exists while at least one chip does. */
export async function clearAll(page: Page): Promise<void> {
  await page.locator('[data-testid="clear-filters-btn"]').click();
  await page.waitForTimeout(400);
}

/**
 * Pick a Bat's List bucket from the group → bucket empty state (which replaced
 * the native <select>). Returns the bucket's advertised lot count.
 */
export async function pickBatBucket(page: Page, groupIndex = 0, bucketIndex = 0): Promise<number> {
  await page.locator('[data-testid="tab-bat"]').click();
  const prompt = page.locator('[data-testid="bat-prompt"]');
  await expect(prompt).toBeVisible({ timeout: 5000 });

  const groups = prompt.locator('[data-testid^="bat-group-"]');
  await expect(groups.first()).toBeVisible();
  await groups.nth(groupIndex).click();

  const buckets = page.locator('[data-testid="bat-buckets"] [data-testid^="bat-bucket-"]');
  await expect(buckets.first()).toBeVisible({ timeout: 5000 });
  const label = (await buckets.nth(bucketIndex).textContent()) ?? '';
  const advertised = parseInt((label.match(/(\d[\d,]*)\s*$/) ?? [])[1]?.replace(/,/g, '') ?? '-1', 10);
  await buckets.nth(bucketIndex).click();
  await page.waitForTimeout(400);
  return advertised;
}
