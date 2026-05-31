import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// Single-accordion behavior: at most one card is expanded at a time. Opening a
// card collapses any currently-open card; toggling the open card closes it.
test('single-accordion: only one card open at a time, Collapse all clears it', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // Toolbar hidden when nothing is expanded and no filter is active.
  await expect(page.locator('[data-testid="grid-toolbar"]')).toHaveCount(0);

  const cards = page.locator('[data-testid="lot-card"]');
  const expanded = page.locator('[aria-label="Hide details"]'); // toggles in the open state

  // Open card 0 → exactly one card expanded.
  await cards.nth(0).locator('[aria-label="Show details"]').first().dispatchEvent('click');
  await expect(expanded).toHaveCount(1, { timeout: 2000 });

  // Open card 1 → still exactly one expanded (card 0 was auto-collapsed).
  await cards.nth(1).locator('[aria-label="Show details"]').first().dispatchEvent('click');
  await expect(expanded).toHaveCount(1, { timeout: 2000 });
  // Card 0 is now collapsed; card 1 is the open one.
  await expect(cards.nth(0).locator('[aria-label="Show details"]').first()).toHaveAttribute('aria-expanded', 'false');
  await expect(cards.nth(1).locator('[aria-label="Hide details"]').first()).toHaveAttribute('aria-expanded', 'true');

  // Toggling the open card closes it → zero open.
  await cards.nth(1).locator('[aria-label="Hide details"]').first().dispatchEvent('click');
  await expect(expanded).toHaveCount(0, { timeout: 2000 });

  // Re-open one, then use Collapse all to clear it.
  await cards.nth(2).locator('[aria-label="Show details"]').first().dispatchEvent('click');
  await expect(expanded).toHaveCount(1, { timeout: 2000 });
  const collapseAll = page.locator('[data-testid="collapse-all-btn"]');
  await expect(collapseAll).toBeVisible();
  await collapseAll.click();
  await expect(expanded).toHaveCount(0, { timeout: 2000 });
  await expect(collapseAll).toHaveCount(0);
});
