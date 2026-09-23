import { test, expect } from '@playwright/test';
import { ready } from './helpers';

/**
 * The recall legend — a reminder of the names Bat's List tends to miss.
 *
 * Tucked behind one rail button, collapsed by default. Open, it lists term
 * chips, each with this week's match count; a click on one only fills the
 * search box (which then shows as the usual query chip). It must be easy to tuck back away, and it must not touch
 * any filter.
 */

test.use({ viewport: { width: 1400, height: 900 } });

test('the legend is closed by default, opens from the rail and fills the search', async ({ page }) => {
  await ready(page);
  const button = page.locator('[data-testid="legend-button"]');
  const strip = page.locator('[data-testid="legend-strip"]');

  await expect(strip).toHaveCount(0);
  await expect(button).toHaveAttribute('aria-expanded', 'false');

  await button.click();
  await expect(strip).toBeVisible();
  await expect(button).toHaveAttribute('aria-expanded', 'true');
  expect(await page.locator('[data-testid="legend-group"]').count()).toBeGreaterThan(1);

  // Every chip carries this week's count, and it can be dimmed but never hidden.
  const terms = page.locator('[data-testid="legend-term"]');
  await expect(page.locator('[data-testid="legend-count"]')).toHaveCount(await terms.count());

  const term = terms.first();
  const text = (await term.getAttribute('data-term')) ?? '';
  await term.click();
  await expect(page.locator('[data-testid="search-input"]:visible')).toHaveValue(text);
  await expect(page.locator('[data-testid="chip-query"]')).toBeVisible();
  // The strip stays open — picking a term is not the same as putting it away.
  await expect(strip).toBeVisible();
});

test('✕ tucks it away and it stays away across a reload', async ({ page }) => {
  await ready(page);
  await page.locator('[data-testid="legend-button"]').click();
  const strip = page.locator('[data-testid="legend-strip"]');
  await expect(strip).toBeVisible();

  await page.locator('[data-testid="legend-close"]').click();
  await expect(strip).toHaveCount(0);

  await page.reload();
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await expect(strip).toHaveCount(0);
});

test('Escape closes the legend when nothing else is open', async ({ page }) => {
  await ready(page);
  await page.locator('[data-testid="legend-button"]').click();
  const strip = page.locator('[data-testid="legend-strip"]');
  await expect(strip).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(strip).toHaveCount(0);
});
