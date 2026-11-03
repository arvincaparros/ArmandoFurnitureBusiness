import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // The Playwright e2e specs are also *.spec.ts, which vitest's
    // default glob picks up - it then fails them, because
    // @playwright/test's test/expect are not vitest's. The two
    // runners own separate directories: vitest owns src/, Playwright
    // owns e2e/ (see playwright.config.ts testDir).
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
  },
})
