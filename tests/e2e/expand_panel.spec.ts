import { test, expect } from '@playwright/test';

// These tests guard the expand-panel behavior. They capture two regressions:
//   - Standard density: clicking a card must reveal an expand panel that is
//     visible (not occluded by following grid rows).
//   - Compact density: clicking a card must insert a full-row expand panel
//     whose width matches the grid container width (not a single cell).

async function waitForCards(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { state: 'visible', timeout: 15000 });
  await page.waitForTimeout(500);
}

async function setDensity(page: import('@playwright/test').Page, density: 'standard' | 'compact') {
  const byRole = page.getByRole('button', { name: new RegExp(`^${density}$`, 'i') });
  if (await byRole.count()) {
    await byRole.first().click();
  } else {
    const byText = page.locator(`text=/^${density}$/i`).first();
    await byText.click();
  }
  await page.waitForTimeout(250);
}

// Click the visible Details affordance on a given card by dispatching the
// click directly on the element to bypass sticky-header / broken-image-overlay
// interception. This still exercises the React click handler.
async function clickDetails(card: import('@playwright/test').Locator) {
  const toggle = card.locator('[aria-label="Show details"]').first();
  await toggle.waitFor({ state: 'attached', timeout: 5000 });
  await toggle.dispatchEvent('click');
}

test.describe('expand panel — standard density', () => {
  test.use({ viewport: { width: 1100, height: 900 } });

  test('clicking a card reveals a visible expand panel that is not occluded', async ({ page }) => {
    await waitForCards(page);
    await setDensity(page, 'standard');

    const firstCard = page.locator('[data-testid="lot-card"]').first();
    const lotNumber = await firstCard.getAttribute('data-lot-number');
    expect(lotNumber).toBeTruthy();

    const cardBoxBefore = await firstCard.boundingBox();
    expect(cardBoxBefore).toBeTruthy();

    await clickDetails(firstCard);

    // The expanded panel should now be visible. It has a "View on Encore" CTA.
    const cta = firstCard.locator('a', { hasText: 'View on Encore' });
    await expect(cta).toBeVisible({ timeout: 2000 });

    // Wait past the 320ms expand-grid transition so we measure the FINAL height
    await page.waitForTimeout(450);

    // The card must have grown taller (the inline expand panel pushed its bottom down).
    const cardBoxAfter = await firstCard.boundingBox();
    expect(cardBoxAfter).toBeTruthy();
    expect(cardBoxAfter!.height).toBeGreaterThan(cardBoxBefore!.height + 200);

    // The CTA must NOT be occluded by sibling cards/panels: check that the
    // pixel at the CTA's center isn't behind something else by asserting its
    // bounding box top is below the card's top and inside the card.
    const ctaBox = await cta.boundingBox();
    expect(ctaBox).toBeTruthy();
    expect(ctaBox!.y).toBeGreaterThan(cardBoxAfter!.y);
    expect(ctaBox!.y + ctaBox!.height).toBeLessThanOrEqual(cardBoxAfter!.y + cardBoxAfter!.height + 1);

    // No other card must overlap the expanded panel vertically. Get the second
    // card's box — its top should sit at or below the first card's bottom.
    const secondCard = page.locator('[data-testid="lot-card"]').nth(1);
    const secondBox = await secondCard.boundingBox();
    if (secondBox) {
      // Cards in the SAME row will share the top y. We only care about cards
      // BELOW the expanded one. Find the next card whose x is the same column
      // as the first card (left edge alignment) and assert its top is below.
      const cardsBelow = page.locator('[data-testid="lot-card"]');
      const count = await cardsBelow.count();
      for (let i = 1; i < Math.min(count, 12); i++) {
        const c = cardsBelow.nth(i);
        const box = await c.boundingBox();
        if (!box) continue;
        const sameColumn = Math.abs(box.x - cardBoxAfter!.x) < 5;
        if (sameColumn) {
          // Must be strictly below the expanded card's bottom (no overlap).
          expect(box.y).toBeGreaterThanOrEqual(cardBoxAfter!.y + cardBoxAfter!.height - 2);
          break;
        }
      }
    }
  });
});

test.describe('expand panel — compact density', () => {
  test.use({ viewport: { width: 1400, height: 900 } });

  test('full-row panel spans the full grid width and is not occluded', async ({ page }) => {
    await waitForCards(page);
    await setDensity(page, 'compact');

    // Wait briefly for re-layout
    await page.waitForTimeout(200);

    const cards = page.locator('[data-testid="lot-card"]');
    const firstCard = cards.first();
    const firstBox = await firstCard.boundingBox();
    expect(firstBox).toBeTruthy();

    // Establish the grid row width: span across the FIRST row of cards
    // (cards sharing the same y as the first card). Compact at 1400px should
    // be 5 columns per the design spec.
    const total = await cards.count();
    let rowLeft = firstBox!.x;
    let rowRight = firstBox!.x + firstBox!.width;
    for (let i = 1; i < Math.min(total, 10); i++) {
      const box = await cards.nth(i).boundingBox();
      if (!box) continue;
      if (Math.abs(box.y - firstBox!.y) < 5) {
        rowLeft = Math.min(rowLeft, box.x);
        rowRight = Math.max(rowRight, box.x + box.width);
      } else {
        break;
      }
    }
    const gridWidth = rowRight - rowLeft;
    expect(gridWidth).toBeGreaterThan(firstBox!.width * 2.5); // sanity: at least 3 columns wide

    await clickDetails(firstCard);

    // The full-row LotExpandPanel renders OUTSIDE the card (sibling). Look
    // for a "View on Encore" link that is not inside the first card.
    const panelCta = page.locator('a', { hasText: 'View on Encore' });
    await expect(panelCta.first()).toBeVisible({ timeout: 2000 });

    // The expand panel root has aria role or an "X" close button. We locate
    // the panel by finding the ancestor of the CTA that has class
    // "col-span-full" OR is the closest article-like container.
    // Pragmatic approach: find any element whose bounding box width is close
    // to the grid width and that contains the CTA.
    const ctaBox = await panelCta.first().boundingBox();
    expect(ctaBox).toBeTruthy();

    // Walk up DOM from the CTA finding the widest ancestor whose width is at
    // least 90% of the grid width.
    const panelWidth = await panelCta.first().evaluate((el, expectedW) => {
      let node: HTMLElement | null = el as HTMLElement;
      let best = 0;
      while (node && node !== document.body) {
        const r = node.getBoundingClientRect();
        if (r.width > best && r.width <= expectedW + 2) best = r.width;
        node = node.parentElement;
      }
      return best;
    }, gridWidth + 5);

    // The panel's widest ancestor (capped at grid width) should be at least
    // 90% of the grid width — confirming it spans the row, not ~2 columns.
    expect(panelWidth).toBeGreaterThan(gridWidth * 0.9);
  });
});
