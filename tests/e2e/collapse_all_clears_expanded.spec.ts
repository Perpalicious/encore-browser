import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

test('Collapse all collapses every expanded card', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // Toolbar should be hidden when nothing is expanded and no filter is active.
  await expect(page.locator('[data-testid="grid-toolbar"]')).toHaveCount(0);

  const cards = page.locator('[data-testid="lot-card"]');

  // Expand cards 0 and 1 via the "Show details" affordance.
  for (const i of [0, 1]) {
    const toggle = cards.nth(i).locator('[aria-label="Show details"]').first();
    await toggle.dispatchEvent('click');
  }

  // Two cards' Details affordances should report aria-expanded="true".
  // (CTAs are present in DOM for every card via the collapsed inline expand-grid;
  // we assert on the toggle's aria-expanded which is the source of truth.)
  const expandedToggles = page.locator('[aria-label="Hide details"]');
  await expect(expandedToggles).toHaveCount(2, { timeout: 2000 });

  // Collapse all button should appear.
  const collapseAll = page.locator('[data-testid="collapse-all-btn"]');
  await expect(collapseAll).toBeVisible();
  await collapseAll.click();

  // After clicking, no toggles are in the "Hide details" (expanded) state, and
  // the toolbar should hide again (no filters active either).
  await expect(expandedToggles).toHaveCount(0, { timeout: 2000 });
  await expect(collapseAll).toHaveCount(0);

  // Both cards should now report aria-expanded="false" on their Details affordance.
  for (const i of [0, 1]) {
    const toggle = cards.nth(i).locator('[aria-label="Show details"]').first();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  }
});
