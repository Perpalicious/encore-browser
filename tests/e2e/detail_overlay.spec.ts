import { test, expect } from '@playwright/test';

// The detail overlay is the fix for the inline-expand problem. Clicking a card
// used to stretch its grid column; expansion now happens in an overlay and the
// grid never reflows, so you keep your place while stepping through candidates.
//
// (Was expand_panel.spec.ts, which guarded the inline/full-row panel this
// replaces.)

test.use({ viewport: { width: 1400, height: 900 } });

async function waitForCards(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(500);
}

/**
 * The overlay's own layout box, relative to the layout viewport.
 *
 * Waits for the entry animation first: `slidein` translates the drawer 24px and
 * `sheetup` translates the sheet 30px, and getBoundingClientRect() includes the
 * transform — measuring early reads the overlay as overshooting the viewport by
 * exactly that much.
 */
async function measurePanel(page: import('@playwright/test').Page) {
  await page
    .locator('[data-testid="lot-detail"]')
    .evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)));
  return page.evaluate(() => {
    const r = document.querySelector('[data-testid="lot-detail"]')!.getBoundingClientRect();
    return {
      width: r.width,
      height: r.height,
      top: r.top,
      right: r.right,
      bottom: r.bottom,
      innerW: window.innerWidth,
      innerH: window.innerHeight,
    };
  });
}

/** Boxes of the first row of cards, used to prove the grid does not reflow. */
async function cardBoxes(page: import('@playwright/test').Page, n = 8) {
  const cards = page.locator('[data-testid="lot-card"]');
  const out = [];
  for (let i = 0; i < Math.min(n, await cards.count()); i++) {
    out.push(await cards.nth(i).boundingBox());
  }
  return out;
}

test('clicking a card opens the drawer without reflowing the grid', async ({ page }) => {
  await waitForCards(page);

  const before = await cardBoxes(page);
  const scrollBefore = await page.evaluate(
    () => document.querySelector('[data-testid="lot-scroller"]')!.scrollTop
  );

  const firstCard = page.locator('[data-testid="lot-card"]').first();
  const lotNumber = await firstCard.getAttribute('data-lot-number');
  await firstCard.dispatchEvent('click');

  const drawer = page.locator('[data-testid="lot-detail"]');
  await expect(drawer).toBeVisible({ timeout: 2000 });
  await expect(drawer).toHaveAttribute('data-lot-number', lotNumber!);
  await expect(drawer.locator('a', { hasText: 'View on Encore' })).toBeVisible();

  // A right drawer on a pointing device: full height, anchored to the right.
  // Measured in-page against the layout viewport — this is a CSS-layout claim,
  // and boundingBox()'s coordinate mapping for fixed elements is not.
  const box = await measurePanel(page);
  expect(Math.round(box.width)).toBe(430);
  expect(Math.round(box.right)).toBe(box.innerW);
  expect(Math.round(box.height)).toBe(box.innerH);
  expect(Math.round(box.top)).toBe(0);

  // Not one card moved, and the scroll position is untouched.
  const after = await cardBoxes(page);
  expect(after.length).toBe(before.length);
  for (let i = 0; i < before.length; i++) {
    expect(Math.abs(after[i]!.x - before[i]!.x)).toBeLessThan(1);
    expect(Math.abs(after[i]!.y - before[i]!.y)).toBeLessThan(1);
    expect(Math.abs(after[i]!.height - before[i]!.height)).toBeLessThan(1);
  }
  const scrollAfter = await page.evaluate(
    () => document.querySelector('[data-testid="lot-scroller"]')!.scrollTop
  );
  expect(scrollAfter).toBe(scrollBefore);
});

test('Escape and the scrim both close the drawer', async ({ page }) => {
  await waitForCards(page);
  const drawer = page.locator('[data-testid="lot-detail"]');

  await page.locator('[data-testid="lot-card"]').first().dispatchEvent('click');
  await expect(drawer).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0, { timeout: 2000 });

  await page.locator('[data-testid="lot-card"]').first().dispatchEvent('click');
  await expect(drawer).toBeVisible();
  // The scrim covers the viewport under the drawer; click clear of the panel.
  await page.mouse.click(100, 400);
  await expect(drawer).toHaveCount(0, { timeout: 2000 });
});

test('the stepper walks the result set without closing the drawer', async ({ page }) => {
  await waitForCards(page);

  const cards = page.locator('[data-testid="lot-card"]');
  const first = await cards.nth(0).getAttribute('data-lot-number');
  const second = await cards.nth(1).getAttribute('data-lot-number');

  await cards.nth(0).dispatchEvent('click');
  const drawer = page.locator('[data-testid="lot-detail"]');
  await expect(drawer).toHaveAttribute('data-lot-number', first!);

  // At the head of the list, back is unavailable and forward advances.
  await expect(page.locator('[data-testid="detail-prev"]')).toBeDisabled();
  await page.locator('[data-testid="detail-next"]').click();
  await expect(drawer).toBeVisible();
  await expect(drawer).toHaveAttribute('data-lot-number', second!);

  await page.locator('[data-testid="detail-prev"]').click();
  await expect(drawer).toHaveAttribute('data-lot-number', first!);

  // Stepping also moves the grid's cursor ring onto the open lot.
  await expect(page.locator('[data-testid="lot-card"][aria-expanded="true"]')).toHaveCount(1);
});

test('the drawer star toggles watch and agrees with the card', async ({ page }) => {
  await waitForCards(page);

  const card = page.locator('[data-testid="lot-card"]').first();
  const cardStar = card.locator('[data-testid="star-btn"]');
  await expect(cardStar).toHaveAttribute('aria-pressed', 'false');

  await card.dispatchEvent('click');
  const drawerStar = page.locator('[data-testid="detail-star-btn"]');
  await expect(drawerStar).toHaveAttribute('aria-pressed', 'false');
  await drawerStar.click();
  await expect(drawerStar).toHaveAttribute('aria-pressed', 'true');
  await expect(cardStar).toHaveAttribute('aria-pressed', 'true');

  await page.keyboard.press('Escape');
  await expect(cardStar).toHaveAttribute('aria-pressed', 'true');
});

test('renders as a bottom sheet on a touch device', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  await page.goto('/');
  // Mobile defaults to Rows, not Cards.
  await page.waitForSelector('[data-testid="lot-row"]', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(500);

  await page.locator('[data-testid="lot-row"]').first().dispatchEvent('click');
  const drawer = page.locator('[data-testid="lot-detail"]');
  await expect(drawer).toBeVisible();

  const box = await measurePanel(page);
  expect(Math.round(box.width)).toBe(box.innerW); // full width, not a 430px panel
  expect(Math.round(box.bottom)).toBe(box.innerH); // anchored to the bottom
  expect(box.height).toBeLessThan(box.innerH); // ...but not full height (88dvh)
  expect(box.height / box.innerH).toBeGreaterThan(0.8);

  await context.close();
});
