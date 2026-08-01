import { test, expect } from '@playwright/test';
import { ready, shownCount, pickBatBucket } from './helpers';

test.use({ viewport: { width: 1280, height: 900 } });

// Bat's List navigation is two-level: groups as cards, then the buckets inside
// the chosen group as pills. Deterministic group/count math is unit-tested in
// viewer/src/lib/batNav.test.ts.
//
// (This replaced a native grouped <select>; the level structure is unchanged,
// but the counts are now visible before you commit to a choice.)
test("Bat's List picks a bucket through group → bucket, not a flood of cards", async ({ page }) => {
  await ready(page);
  await page.locator('[data-testid="tab-bat"]').click();

  // Default view: the group cards, no item cards.
  const prompt = page.locator('[data-testid="bat-prompt"]');
  await expect(prompt).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);

  const groups = prompt.locator('[data-testid^="bat-group-"]');
  const groupCount = await groups.count();
  expect(groupCount).toBeGreaterThanOrEqual(1);
  expect(groupCount).toBeLessThanOrEqual(12);
  // Group cards advertise their lot count.
  expect((await groups.first().textContent()) ?? '').toMatch(/\d[\d,]*\s*LOTS/);

  // Buckets only appear once a group is chosen.
  await expect(page.locator('[data-testid="bat-buckets"]')).toHaveCount(0);
  await groups.first().click();
  const buckets = page.locator('[data-testid="bat-buckets"] [data-testid^="bat-bucket-"]');
  await expect(buckets.first()).toBeVisible();

  // Picking one swaps in its lots and dismisses the prompt.
  await buckets.first().click();
  await page.waitForTimeout(400);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
  await expect(prompt).toHaveCount(0);
});

test('bucket counts match the lots actually shown', async ({ page }) => {
  await ready(page);
  const advertisedA = await pickBatBucket(page, 0, 0);
  expect(advertisedA).toBeGreaterThan(0);
  expect(await shownCount(page)).toBe(advertisedA);

  // Switching buckets needs no back-out: the active bucket is a rail chip, and
  // removing it returns to the picker in one click.
  await page.locator('[data-testid="chip-bucket"]').click();
  await page.waitForTimeout(300);
  const advertisedB = await pickBatBucket(page, 0, 1);
  expect(advertisedB).toBeGreaterThan(0);
  expect(await shownCount(page)).toBe(advertisedB);
});
