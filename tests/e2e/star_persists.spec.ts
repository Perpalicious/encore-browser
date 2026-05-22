import { test, expect } from '@playwright/test';

test('starring a card then reloading the page shows the card remains starred', async ({ page }) => {
  await page.goto('/');

  // Wait for skeleton to clear and cards to appear
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 5000 });

  // Get the first visible card and read its lot number
  const firstCard = page.locator('[data-testid="lot-card"]').first();
  const lotNumber = await firstCard.getAttribute('data-lot-number');
  expect(lotNumber).toBeTruthy();

  // Click the star button on the first card
  const starBtn = firstCard.locator('[data-testid="star-btn"]');
  await starBtn.click();

  // Verify star button is now pressed (watched = true)
  await expect(starBtn).toHaveAttribute('aria-pressed', 'true', { timeout: 3000 });

  // Reload the page
  await page.reload();

  // Wait for cards to appear again after reload
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 5000 });

  // Switch to the Watched tab — use the visible instance (at 1280px, desktop header is shown)
  await page.locator('[data-testid="tab-watched"]').filter({ visible: true }).click();

  // The watched tab should show a card with the same lot number
  const watchedCard = page.locator(`[data-lot-number="${lotNumber}"]`);
  await expect(watchedCard).toBeVisible({ timeout: 5000 });
});
