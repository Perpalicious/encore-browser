import { defineConfig, devices } from '@playwright/test';

// Ensure bundled NSS/NSPR/ALSA libraries are found on systems where they
// are not globally installed (e.g. minimal CI / WSL environments).
process.env.LD_LIBRARY_PATH = [
  '/home/bat/lib',
  process.env.LD_LIBRARY_PATH,
].filter(Boolean).join(':');

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
