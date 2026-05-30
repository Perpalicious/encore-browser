import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// Two-level Bat's List navigation: groups → buckets → items, with back-nav.
// Runs against the real committed bundle (deterministic group/count math is
// unit-tested in viewer/src/lib/batNav.test.ts).
test('Bat\'s List uses two-level group → bucket → items navigation', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // Switch to Bat's List.
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  // Default Bat's List view is the GROUP selector — NOT a flood of item cards.
  const groupNav = page.locator('[data-testid="bat-group-nav"]');
  await expect(groupNav).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);

  // There is NO flat row of dozens of bucket chips at this level — only groups.
  const groups = page.locator('[data-testid="bat-group"]');
  const groupCount = await groups.count();
  expect(groupCount).toBeGreaterThanOrEqual(1);
  expect(groupCount).toBeLessThanOrEqual(12); // a handful of groups, never 44 chips

  // Each group shows a numeric count.
  const firstGroupText = (await groups.first().textContent()) ?? '';
  expect(firstGroupText).toMatch(/\d/);

  // Select a group → its buckets appear (still no item cards yet).
  await groups.first().click();
  await page.waitForTimeout(200);
  const buckets = page.locator('[data-testid="bat-bucket"]');
  await expect(buckets.first()).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);
  const bucketName = await buckets.first().getAttribute('data-bucket');
  expect(bucketName).toBeTruthy();

  // Select a bucket → item cards for that bucket appear.
  await buckets.first().click();
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
  await expect(groupNav).toHaveCount(0); // selector replaced by the grid
  // Breadcrumb shows where we are, with a way back.
  await expect(page.locator('[data-testid="bat-breadcrumb"]')).toBeVisible();

  // Back to that group's buckets.
  await page.locator('[data-testid="bat-back-to-buckets"]').click();
  await page.waitForTimeout(200);
  await expect(buckets.first()).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);

  // Back to all groups.
  await page.locator('[data-testid="bat-back-to-groups"]').click();
  await page.waitForTimeout(200);
  await expect(groups.first()).toBeVisible();
  expect(await groups.count()).toBe(groupCount);
});

test('selecting a bucket filters items to that bucket', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  // Drill into the first group, then read the first bucket's advertised count.
  await page.locator('[data-testid="bat-group"]').first().click();
  await page.waitForTimeout(200);
  const firstBucket = page.locator('[data-testid="bat-bucket"]').first();
  const bucketLabel = (await firstBucket.textContent()) ?? '';
  const advertised = parseInt((bucketLabel.match(/(\d+)\s*$/) ?? [])[1] ?? '0', 10);
  expect(advertised).toBeGreaterThan(0);

  await firstBucket.click();
  await page.waitForTimeout(300);

  // The breadcrumb's lot count should equal the bucket's advertised count.
  const crumb = (await page.locator('[data-testid="bat-breadcrumb"]').textContent()) ?? '';
  const shown = parseInt((crumb.match(/(\d+)\s*lots?/) ?? [])[1] ?? '-1', 10);
  expect(shown).toBe(advertised);
});
