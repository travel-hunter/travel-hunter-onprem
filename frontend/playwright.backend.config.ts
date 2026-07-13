import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.E2E_FRONTEND_PORT || "5174";
const apiBaseUrl = process.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "./e2e-backend",
  timeout: 45_000,
  fullyParallel: false,
  reporter: process.env.CI ? "dot" : "list",
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      VITE_API_BASE_URL: apiBaseUrl,
    },
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
