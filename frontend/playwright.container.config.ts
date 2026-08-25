import { defineConfig, devices } from "@playwright/test";

const frontendBaseUrl = process.env.E2E_FRONTEND_BASE_URL || "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./e2e-backend",
  timeout: 45_000,
  fullyParallel: false,
  reporter: process.env.CI ? "dot" : "list",
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: frontendBaseUrl,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
});
