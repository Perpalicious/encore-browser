import { test, expect } from '@playwright/test';
import { ready, shownCount } from './helpers';

test.describe('keyboard navigation', () => {
  test.use({ viewport: { width: 1400, height: 900 } });

  test('arrows move the cursor, space opens, w watches, / focuses search', async ({ page }) => {
    await ready(page);
    const cards = page.locator('[data-testid="lot-card"]');
    // The cursor is its own state, distinct from "this lot's overlay is open".
    const cursor = page.locator('[data-testid="lot-card"][data-cursor="true"]');

    // → sets the cursor on the first lot; the ring is the visible cursor.
    await page.keyboard.press('ArrowRight');
    await expect(cursor).toHaveCount(1);
    const second = await cards.nth(1).getAttribute('data-lot-number');
    await expect(cursor).toHaveAttribute('data-lot-number', second!);

    // ← steps back, and ↓ moves a whole row (so past the column count).
    await page.keyboard.press('ArrowLeft');
    await expect(cursor).toHaveAttribute('data-lot-number', (await cards.nth(0).getAttribute('data-lot-number'))!);
    await page.keyboard.press('ArrowDown');
    const afterDown = await cursor.getAttribute('data-lot-number');
    expect(afterDown).not.toBe(await cards.nth(1).getAttribute('data-lot-number'));

    // Space opens the overlay for the cursor lot.
    await page.keyboard.press(' ');
    const drawer = page.locator('[data-testid="lot-detail"]');
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveAttribute('data-lot-number', afterDown!);

    // Arrow movement advances the overlay too, without closing it.
    await page.keyboard.press('ArrowRight');
    await expect(drawer).toBeVisible();
    await expect(drawer).not.toHaveAttribute('data-lot-number', afterDown!);

    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);

    // w watches the cursor lot and fires a toast.
    await page.keyboard.press('w');
    await expect(page.locator('[data-testid="toast"]')).toBeVisible();
    await expect(page.locator('[data-testid="tab-watched"]')).toContainText('1');

    // / focuses search, and Escape blurs it rather than closing anything.
    await page.keyboard.press('/');
    await expect(page.locator('[data-testid="search-input"]')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-testid="search-input"]')).not.toBeFocused();
  });

  test('f toggles the filters overlay', async ({ page }) => {
    await ready(page);
    await page.keyboard.press('f');
    await expect(page.locator('[data-testid="filters-overlay"]')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-testid="filters-overlay"]')).toHaveCount(0);
  });

  test('keys typed into the search field are not swallowed as shortcuts', async ({ page }) => {
    await ready(page);
    const search = page.locator('[data-testid="search-input"]');
    await search.click();
    await search.type('walk');
    await expect(search).toHaveValue('walk');
    await expect(page.locator('[data-testid="filters-overlay"]')).toHaveCount(0);
  });
});

test.describe('swipe triage', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  /** Drag a row horizontally with pointer events, as a thumb would. */
  async function swipe(page: import('@playwright/test').Page, dx: number) {
    const row = page.locator('[data-testid="lot-row"]').first();
    const box = (await row.boundingBox())!;
    const y = box.y + box.height / 2;
    const startX = box.x + box.width / 2;
    await page.mouse.move(startX, y);
    await page.mouse.down();
    for (let i = 1; i <= 6; i++) await page.mouse.move(startX + (dx * i) / 6, y);
    await page.mouse.up();
    await page.waitForTimeout(400);
  }

  test('swiping right watches the lot, left hides it from the results', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="lot-row"]', { timeout: 15000 });
    await page.waitForTimeout(400);

    const before = await shownCount(page);

    // Right past the +70px threshold → watched, with a toast.
    await swipe(page, 110);
    await expect(page.locator('[data-testid="toast"]')).toBeVisible();
    await expect(page.locator('[data-testid="tab-watched"]')).toContainText('1');

    // Left past −70px → hidden, so the result count drops by one.
    const hiddenLot = await page.locator('[data-testid="lot-row"]').first().getAttribute('data-lot-number');
    await swipe(page, -110);
    await expect(page.locator('[data-testid="toast"]')).toBeVisible();
    expect(await shownCount(page)).toBe(before - 1);
    await expect(
      page.locator(`[data-testid="lot-row"][data-lot-number="${hiddenLot}"]`)
    ).toHaveCount(0);

    // Hidden lots surface as a chip that restores them.
    const chip = page.locator('[data-testid="chip-hidden"]');
    await expect(chip).toBeVisible();
    await chip.click();
    await page.waitForTimeout(400);
    expect(await shownCount(page)).toBe(before);
  });

  test('a short swipe snaps back without committing', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="lot-row"]', { timeout: 15000 });
    await page.waitForTimeout(400);
    const before = await shownCount(page);

    await swipe(page, 40); // under the ±70px threshold
    expect(await shownCount(page)).toBe(before);
    await expect(page.locator('[data-testid="tab-watched"]')).toContainText('0');
  });
});
