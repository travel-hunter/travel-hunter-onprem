const { spawnSync } = require("node:child_process");
const path = require("node:path");

const frontendDir = path.resolve(__dirname, "..");
const playwrightCli = path.join(frontendDir, "node_modules", "@playwright", "test", "cli.js");
const playwrightArgs = process.argv.slice(2);

const result = spawnSync(
  process.execPath,
  [playwrightCli, "test", "--config", "playwright.container.config.ts", ...playwrightArgs],
  {
    cwd: frontendDir,
    env: {
      ...process.env,
      E2E_FRONTEND_BASE_URL:
        process.env.E2E_FRONTEND_BASE_URL || "http://127.0.0.1:4173",
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
    },
    stdio: "inherit",
  },
);

if (result.error) {
  console.error(result.error);
  process.exit(1);
}

process.exit(result.status || 0);
