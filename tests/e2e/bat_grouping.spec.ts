import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 900 } });

// Bat's List navigation is a single grouped dropdown: pick a bucket and its
// items show immediately; switch buckets by just changing the dropdown — no
// drill-in, no back-out. Deterministic group/count math is unit-tested in
// viewer/src/lib/batNav.test.ts.
test("Bat's List uses a grouped bucket dropdown (no drill-in)", async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  // Switch to Bat's List.
  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  // Default view: the dropdown selector + a "pick a bucket" prompt — NOT a
  // flood of item cards.
  const dropdown = page.locator('[data-testid="bat-bucket-dropdown"]');
  await expect(dropdown).toBeVisible();
  await expect(page.locator('[data-testid="bat-prompt"]')).toBeVisible();
  await expect(page.locator('[data-testid="lot-card"]')).toHaveCount(0);

  // The dropdown groups buckets under optgroup headings (one per group).
  const optgroupCount = await dropdown.locator('optgroup').count();
  expect(optgroupCount).toBeGreaterThanOrEqual(1);
  expect(optgroupCount).toBeLessThanOrEqual(12);
  // Options carry counts like "Dinnerware (10)".
  const someOption = dropdown.locator('optgroup option').first();
  expect((await someOption.textContent()) ?? '').toMatch(/\(\d+\)\s*$/);

  // Pick a bucket → its item cards appear immediately, prompt gone.
  const firstValue =
    (await dropdown.locator('optgroup option').first().getAttribute('value')) ?? '';
  expect(firstValue).toBeTruthy();
  await dropdown.selectOption(firstValue);
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
  await expect(page.locator('[data-testid="bat-prompt"]')).toHaveCount(0);

  // The dropdown is STILL visible — switching buckets needs no back-out.
  await expect(dropdown).toBeVisible();
});

test('switching the dropdown swaps buckets with no back-out', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="lot-card"]', { timeout: 15000 });
  await page.waitForTimeout(500);

  await page.locator('[data-testid="tab-bat"]').filter({ visible: true }).click();
  await page.waitForTimeout(300);

  const dropdown = page.locator('[data-testid="bat-bucket-dropdown"]');
  const options = dropdown.locator('optgroup option');
  const count = await options.count();
  expect(count).toBeGreaterThanOrEqual(2);

  // Read advertised counts for two distinct buckets from the option labels.
  const readCount = (label: string) =>
    parseInt((label.match(/\((\d+)\)\s*$/) ?? [])[1] ?? '-1', 10);

  const valA = (await options.nth(0).getAttribute('value')) ?? '';
  const labelA = (await options.nth(0).textContent()) ?? '';
  const advertisedA = readCount(labelA);

  const valB = (await options.nth(1).getAttribute('value')) ?? '';
  const labelB = (await options.nth(1).textContent()) ?? '';
  const advertisedB = readCount(labelB);

  expect(advertisedA).toBeGreaterThan(0);
  expect(advertisedB).toBeGreaterThan(0);

  // Select bucket A — shown lot count matches its advertised count.
  await dropdown.selectOption(valA);
  await page.waitForTimeout(300);
  await expect(page.locator('[data-testid="lot-card"]').first()).toBeVisible();
  const shownA = parseInt(
    ((await page.locator('[data-testid="grid-toolbar"]').textContent()) ?? '').match(
      /(\d+)\s*lots?/
    )?.[1] ?? '-1',
    10
  );
  expect(shownA).toBe(advertisedA);

  // Switch DIRECTLY to bucket B via the dropdown — no back-out step.
  await dropdown.selectOption(valB);
  await page.waitForTimeout(300);
  const shownB = parseInt(
    ((await page.locator('[data-testid="grid-toolbar"]').textContent()) ?? '').match(
      /(\d+)\s*lots?/
    )?.[1] ?? '-1',
    10
  );
  expect(shownB).toBe(advertisedB);
});
