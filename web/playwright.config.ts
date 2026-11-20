import { defineConfig, devices } from '@playwright/test';

const URL_BASE = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';
const URL_API = process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:8000';
const isServizioEsterno = Boolean(process.env.PLAYWRIGHT_BASE_URL);

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : [['list']],
  use: {
    baseURL: URL_BASE,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: isServizioEsterno
    ? undefined
    : [
        {
          command:
            'cd ../api && CIVIC_ENV=dev CIVIC_RATE_LIMIT_REGISTRAZIONE=100 ' +
            'CIVIC_RATE_LIMIT_LOGIN=100 CIVIC_RATE_LIMIT_SEGNALAZIONI=100 ' +
            'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
          url: `${URL_API}/health/ready`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
        {
          command: 'NEXT_TELEMETRY_DISABLED=1 npm run dev',
          url: URL_BASE,
          reuseExistingServer: !process.env.CI,
          timeout: 180_000,
        },
      ],
});
