import { test, expect } from '@playwright/test';
import { ready, inFilters, shownCount } from './helpers';

/**
 * The header's LOT field. Its whole job is that you heard a number and want
 * that lot NOW, so the bar is: it always gets you there, or tells you the lot
 * does not exist. "Not in your current results" is not an acceptable answer.
 */

test.use({ viewport: { width: 1400, height: 900 } });

/** Type a lot number into the LOT field and commit it. */
async function jump(page: import('@playwright/test').Page, value: string) {
  const field = page.locator('[data-testid="jump-input"]');
  await field.fill(value);
  await field.press('Enter');
  await page.waitForTimeout(500);
}

test('jumps to a lot far down the list and marks it with the cursor', async ({ page }) => {
  await ready(page);

  // Take a lot number from well past the first screen.
  const grid = page.locator('[data-testid="lot-scroller"]');
  await grid.evaluate((el) => {
    el.scrollTop = 40000;
  });
  await page.waitForTimeout(400);
  const target = await page
    .locator('[data-testid="lot-card"]')
    .first()
    .getAttribute('data-lot-number');
  await grid.evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.waitForTimeout(400);

  await jump(page, target!);

  const card = page.locator(`[data-testid="lot-card"][data-lot-number="${target}"]`);
  await expect(card).toBeVisible();
  await expect(card).toHaveAttribute('data-cursor', 'true');
  // 'top' alignment: the row is parked near the top of the viewport, not just
  // barely scrolled into it.
  const gridBox = (await grid.boundingBox())!;
  const cardBox = (await card.boundingBox())!;
  expect(cardBox.y - gridBox.y).toBeLessThan(120);
});

test('a filtered-out lot is reached anyway, and the toast says why', async ({ page }) => {
  await ready(page);
  const target = await page
    .locator('[data-testid="lot-card"]')
    .first()
    .getAttribute('data-lot-number');

  // Filter to something that cannot contain it, and confirm it is gone.
  await inFilters(page, async () => {
    await page.locator('[data-testid="personal-picks-toggle"]').click();
  });
  const narrowed = await shownCount(page);
  await expect(
    page.locator(`[data-testid="lot-card"][data-lot-number="${target}"]`)
  ).toHaveCount(0);

  await jump(page, target!);

  await expect(page.locator('[data-testid="toast"]')).toContainText(target!);
  await expect(
    page.locator(`[data-testid="lot-card"][data-lot-number="${target}"]`)
  ).toBeVisible();
  expect(await shownCount(page)).toBeGreaterThan(narrowed);
});

test('a bare number resolves to the auction that actually has it', async ({ page }) => {
  await ready(page);
  const target = await page
    .locator('[data-testid="lot-card"]')
    .first()
    .getAttribute('data-lot-number');
  const digits = target!.replace(/\D/g, '');

  await jump(page, digits);
  await expect(
    page.locator(`[data-testid="lot-card"][data-cursor="true"]`)
  ).toHaveAttribute('data-lot-number', target!);
});

test('a lot number that does not exist says so and changes nothing', async ({ page }) => {
  await ready(page);
  const before = await shownCount(page);

  await jump(page, 'S-999999');

  await expect(page.locator('[data-testid="toast"]')).toContainText('No lot');
  expect(await shownCount(page)).toBe(before);
  await expect(page.locator('[data-testid="lot-card"][data-cursor="true"]')).toHaveCount(0);
});
