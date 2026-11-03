import { defineConfig, devices } from '@playwright/test'

// The e2e suite stubs every /api/** call at the network layer (see
// e2e/fixtures/apiStubs.ts) and never talks to a real backend, so it
// touches no database. That is deliberate: these specs assert the UI's
// own behaviour - what it shows, blocks and sends - which is exactly
// the layer vitest/RTL cannot cover end to end.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  use: {
    // localhost, not 127.0.0.1: Vite's default bind answers on
    // localhost (::1 first on Windows) and does NOT respond on the
    // IPv4 loopback, so the plan's 127.0.0.1 URL made webServer time
    // out after 120s against a dev server that was already up.
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
