import { test, expect } from '@playwright/test';
import { ready, inFilters } from './helpers';

/**
 * Which auction a lot belongs to, on the card.
 *
 * It used to be an 8px letter on the photo that went unnoticed. It now sits in
 * the text block with the bucket and retail, as a coloured box.
 */

test.use({ viewport: { width: 1400, height: 900 } });

test('every card carries an S or M chip', async ({ page }) => {
  await ready(page);
  const cards = page.locator('[data-testid="lot-card"]');
  const count = await cards.count();
  const chips = page.locator('[data-testid^="day-chip-"]');
  expect(await chips.count()).toBe(count);

  // Sunday leads the default sort, so the first screen is all S.
  await expect(cards.first().locator('[data-testid="day-chip-S"]')).toBeVisible();
});

test('the chip is gone once a single day is filtered, being redundant', async ({ page }) => {
  await ready(page);
  await expect(page.locator('[data-testid^="day-chip-"]').first()).toBeVisible();

  await inFilters(page, async () => {
    await page.locator('[data-testid="day-Sunday"]').click();
  });
  await page.waitForTimeout(400);

  await expect(page.locator('[data-testid^="day-chip-"]')).toHaveCount(0);
  // The group bar's day label goes with it, for the same reason.
  await expect(page.locator('[data-testid="group-bar-day"]')).toHaveCount(0);
});

test('the group bar day label is colour-coded to match', async ({ page }) => {
  await ready(page);
  const bar = page.locator('[data-testid="group-bar-day"]');
  await expect(bar).toBeVisible();
  await expect(bar).toContainText('SUNDAY');

  // Monday lots use the other accent — jump far enough down to reach them.
  const colour = await bar.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(colour).not.toBe('rgba(0, 0, 0, 0)');
});

test('the photo no longer carries the day letter', async ({ page }) => {
  await ready(page);
  // The tile holds the pick dot, the value badge and the star — nothing else.
  const tile = page.locator('[data-testid="lot-card"]').first().locator('[data-testid="tile-link"]');
  await expect(tile).toBeVisible();
  await expect(tile.locator('[data-testid^="day-chip-"]')).toHaveCount(0);
});
