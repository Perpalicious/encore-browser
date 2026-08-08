import { test, expect } from '@playwright/test';
import { ready } from './helpers';

/**
 * Middle-clicking a tile opens that lot on Encore, skipping the trip through
 * the detail overlay. It is a real anchor rather than a click handler, so the
 * browser's own affordances (⌘-click, right-click → open in new tab) come with
 * it — and a plain click must still belong to the card.
 */

test.use({ viewport: { width: 1400, height: 900 } });

test('middle-click opens the lot on Encore and does not open the overlay', async ({ page }) => {
  // Stub Encore itself: the assertion is about which URL we send you to, and a
  // test should not depend on hibid.com being reachable.
  await page.context().route(/hibid\.com/, (route) =>
    route.fulfill({ contentType: 'text/html', body: '<title>encore stub</title>' })
  );
  await ready(page);
  const tile = page.locator('[data-testid="lot-card"] [data-testid="tile-link"]').first();
  const href = await tile.getAttribute('href');
  expect(href).toContain('hibid.com');

  const box = (await tile.boundingBox())!;
  const opened = page.context().waitForEvent('page');
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { button: 'middle' });

  // The popup starts on about:blank and navigates a beat later; Encore also
  // rewrites the query on arrival, so match on the lot id rather than the
  // literal string.
  const lotId = /\/lot\/(\d+)/.exec(href!)![1];
  const newTab = await opened;
  await newTab.waitForURL(new RegExp(`hibid\\.com/lot/${lotId}`), { timeout: 15000 });
  await newTab.close();

  await expect(page.locator('[data-testid="lot-detail"]')).toHaveCount(0);
});

test('a plain click on the tile still opens the detail overlay, and navigates nowhere', async ({
  page,
}) => {
  await ready(page);
  const url = page.url();
  const tile = page.locator('[data-testid="lot-card"] [data-testid="tile-link"]').first();

  await tile.click();
  await expect(page.locator('[data-testid="lot-detail"]')).toBeVisible();
  expect(page.url()).toBe(url);
});

test('the list view thumbnail carries the same link', async ({ page }) => {
  await ready(page);
  await page.locator('[data-testid="view-list"]').click();
  await page.waitForTimeout(400);

  const tile = page.locator('[data-testid="lot-row"] [data-testid="tile-link"]').first();
  await expect(tile).toHaveAttribute('href', /hibid\.com/);
  await expect(tile).toHaveAttribute('target', '_blank');
});
