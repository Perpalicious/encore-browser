import { test, expect, type Page } from '@playwright/test';
import { ready, inFilters } from './helpers';

/**
 * The desktop column ceiling. Without one the grid just kept adding columns on
 * a wide monitor — 9 at 2140px — and the cards got too small to scan.
 */

/** How many cards share the top row's y position. */
async function columnsOnScreen(page: Page): Promise<number> {
  const boxes = await page.locator('[data-testid="lot-card"]').evaluateAll((els) =>
    els.map((el) => el.getBoundingClientRect().top)
  );
  const top = Math.min(...boxes);
  return boxes.filter((t) => Math.abs(t - top) < 2).length;
}

test('standard density never exceeds 6 columns, at any width', async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await ready(page);
  expect(await columnsOnScreen(page)).toBe(6);

  // The width that used to produce 9.
  await page.setViewportSize({ width: 2140, height: 900 });
  await page.waitForTimeout(500);
  expect(await columnsOnScreen(page)).toBe(6);

  await page.setViewportSize({ width: 2560, height: 900 });
  await page.waitForTimeout(500);
  expect(await columnsOnScreen(page)).toBe(6);
});

test('compact density is still worth having: it goes to 8', async ({ page }) => {
  await page.setViewportSize({ width: 2140, height: 900 });
  await ready(page);
  const standardWidth = (await page.locator('[data-testid="lot-card"]').first().boundingBox())!
    .width;

  await inFilters(page, async () => {
    await page.locator('[data-testid="density-compact"]').click();
  });
  await page.waitForTimeout(400);

  expect(await columnsOnScreen(page)).toBe(8);
  const compactWidth = (await page.locator('[data-testid="lot-card"]').first().boundingBox())!
    .width;
  expect(compactWidth).toBeLessThan(standardWidth);
});

test('below the ceiling the count is still computed, not breakpointed', async ({ page }) => {
  // Stay above 760px: below that is the mobile layout, which opens in rows and
  // takes its column count from the 2/3/4 stepper instead.
  await page.setViewportSize({ width: 800, height: 900 });
  await ready(page);
  expect(await columnsOnScreen(page)).toBe(3);

  await page.setViewportSize({ width: 1100, height: 900 });
  await page.waitForTimeout(400);
  expect(await columnsOnScreen(page)).toBe(5);
});
