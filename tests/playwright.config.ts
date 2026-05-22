import { defineConfig, devices } from '@playwright/test';

// On minimal Linux environments (e.g. some WSL installs) Playwright's browser
// binaries need NSS/NSPR/ALSA system libraries. If they're missing, install
// via your distro (e.g. `sudo apt install libnss3 libnspr4 libasound2t64`)
// or `npx playwright install-deps chromium`. If you have a non-standard path,
// set EXTRA_LIB_PATH in the environment.
if (process.env.EXTRA_LIB_PATH) {
  process.env.LD_LIBRARY_PATH = [
    process.env.EXTRA_LIB_PATH,
    process.env.LD_LIBRARY_PATH,
  ].filter(Boolean).join(':');
}

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:4173',
    headless: true,
    viewport: { width: 1280, height: 900 },
    // Give the server-side loads a bit more room
    actionTimeout: 10000,
    navigationTimeout: 15000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run preview',
    cwd: '../viewer',
    url: 'http://localhost:4173',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
