import { test, expect } from '@playwright/test';
import { ready, shownCount } from './helpers';

// Desktop Grid | List, and the mobile Rows | Cards toggle plus 2/3/4 stepper.
// The point of all of them is density: how many lots fit on one screen.

test.describe('desktop', () => {
  test.use({ viewport: { width: 1400, height: 900 } });

  test('List view swaps cards for rows without changing the result set', async ({ page }) => {
    await ready(page);
    const total = await shownCount(page);
    await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="lot-row"]')).toHaveCount(0);

    await page.locator('[data-testid="view-list"]').click();
    await page.waitForTimeout(400);

    await expect(page.locator('[data-testid="lot-row"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);
    expect(await shownCount(page)).toBe(total);

    // Rows are 67px on a pointing device, so many more fit on one screen.
    // Measured as the pitch between consecutive rows — that is the number the
    // virtualiser's spacer is built from, and it includes the 1px divider.
    const rows = page.locator('[data-testid="lot-row"]');
    const y0 = (await rows.nth(0).boundingBox())!.y;
    const y1 = (await rows.nth(1).boundingBox())!.y;
    expect(Math.round(y1 - y0)).toBe(67);
    expect(await rows.count()).toBeGreaterThan(10);

    await page.locator('[data-testid="view-grid"]').click();
    await page.waitForTimeout(400);
    await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
  });

  test('the view choice survives a reload', async ({ page }) => {
    await ready(page);
    await page.locator('[data-testid="view-list"]').click();
    await page.waitForTimeout(600); // past the 350ms persistence debounce

    await page.reload();
    await page.waitForSelector('[data-testid="lot-row"]', { timeout: 15000 });
    await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);
  });
});

test.describe('mobile', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test('Rows is the default, and the stepper changes the card column count', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="lot-row"]', { timeout: 15000 });
    await page.waitForTimeout(400);

    // ~9 lots per screen in rows mode, at 78px on a touch device.
    const rows = page.locator('[data-testid="lot-row"]');
    const y0 = (await rows.nth(0).boundingBox())!.y;
    const y1 = (await rows.nth(1).boundingBox())!.y;
    expect(Math.round(y1 - y0)).toBe(78);

    // The stepper only exists in cards mode.
    await expect(page.locator('[data-testid="cols-3"]')).toHaveCount(0);
    await page.locator('[data-testid="mview-cards"]').click();
    await page.waitForTimeout(400);

    const cards = page.locator('[data-testid="lot-card"]');
    await expect(cards.first()).toBeVisible();

    // 3-up is the recommended default.
    await expect(page.locator('[data-testid="cols-3"]')).toHaveAttribute('aria-pressed', 'true');
    const widthAt = async () => (await cards.first().boundingBox())!.width;
    const w3 = await widthAt();

    await page.locator('[data-testid="cols-2"]').click();
    await page.waitForTimeout(400);
    expect(await widthAt()).toBeGreaterThan(w3);

    await page.locator('[data-testid="cols-4"]').click();
    await page.waitForTimeout(400);
    expect(await widthAt()).toBeLessThan(w3);
    // At 4-up the figures move onto the image and the tick is suppressed.
    await expect(page.locator('[data-testid="value-badge"]')).toHaveCount(0);
  });
});
