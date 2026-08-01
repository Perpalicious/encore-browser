import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// At most one lot is selected at a time. Opening a card opens the detail
// overlay for it; opening another replaces the selection rather than stacking.
//
// (Was collapse_all_clears_expanded.spec.ts. The toolbar's "Collapse all"
// button is gone with the inline expand it collapsed — the overlay is modal, so
// a button behind its scrim could never be clicked. ✕ and Escape close it.)
test('single selection: opening another card replaces the open one', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  const cards = page.locator('[data-testid="lot-card"]');
  const selected = page.locator('[data-testid="lot-card"][aria-expanded="true"]');
  const drawer = page.locator('[data-testid="lot-detail"]');

  // Nothing is selected on load, and no stale collapse affordance survives.
  await expect(selected).toHaveCount(0);
  await expect(drawer).toHaveCount(0);
  await expect(page.locator('[data-testid="collapse-all-btn"]')).toHaveCount(0);

  // Open card 0 → exactly one selected, overlay shows that lot.
  const lot0 = await cards.nth(0).getAttribute('data-lot-number');
  await cards.nth(0).dispatchEvent('click');
  await expect(selected).toHaveCount(1, { timeout: 2000 });
  await expect(drawer).toHaveAttribute('data-lot-number', lot0!);
  await expect(cards.nth(0)).toHaveAttribute('aria-label', 'Hide details');

  // Open card 1 → still exactly one selected; card 0 released it.
  const lot1 = await cards.nth(1).getAttribute('data-lot-number');
  await cards.nth(1).dispatchEvent('click');
  await expect(selected).toHaveCount(1, { timeout: 2000 });
  await expect(drawer).toHaveAttribute('data-lot-number', lot1!);
  await expect(cards.nth(0)).toHaveAttribute('aria-expanded', 'false');
  await expect(cards.nth(1)).toHaveAttribute('aria-expanded', 'true');

  // Closing from the overlay clears the selection entirely.
  await page.locator('[aria-label="Close details"]').click();
  await expect(drawer).toHaveCount(0, { timeout: 2000 });
  await expect(selected).toHaveCount(0);

  // Re-open, then clear with Escape.
  await cards.nth(2).dispatchEvent('click');
  await expect(selected).toHaveCount(1, { timeout: 2000 });
  await page.keyboard.press('Escape');
  await expect(selected).toHaveCount(0, { timeout: 2000 });
  await expect(drawer).toHaveCount(0);
});
