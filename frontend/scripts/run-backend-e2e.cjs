const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..", "..");
const backendDir = path.join(repoRoot, "backend");
const frontendDir = path.join(repoRoot, "frontend");

function resolvePythonCommand() {
  if (process.env.PYTHON) return process.env.PYTHON;

  const venvPython =
    process.platform === "win32"
      ? path.join(backendDir, ".venv", "Scripts", "python.exe")
      : path.join(backendDir, ".venv", "bin", "python");

  if (fs.existsSync(venvPython)) return venvPython;
  return process.platform === "win32" ? "python" : "python3";
}

const pythonCommand = resolvePythonCommand();
const dockerCommand = process.platform === "win32" ? "docker.exe" : "docker";
const playwrightCli = path.join(frontendDir, "node_modules", "@playwright", "test", "cli.js");
const playwrightArgs = process.argv.slice(2);
const apiPort = process.env.E2E_API_PORT || "8001";
const frontendPort = process.env.E2E_FRONTEND_PORT || "5174";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;

const backendEnv = {
  ...process.env,
  APP_ENV: process.env.APP_ENV || "e2e",
  DATABASE_URL:
    process.env.DATABASE_URL ||
    "postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter",
  AUTH_SECRET_KEY:
    process.env.AUTH_SECRET_KEY || "dev-only-change-me-secret-key-32-bytes",
  REFRESH_COOKIE_SECURE: "false",
  CORS_ORIGINS:
    process.env.CORS_ORIGINS ||
    [
      `http://127.0.0.1:${frontendPort}`,
      `http://localhost:${frontendPort}`,
      "http://127.0.0.1:5173",
      "http://localhost:5173",
      "http://127.0.0.1:4173",
      "http://localhost:4173",
    ].join(","),
};

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || repoRoot,
    env: options.env || process.env,
    stdio: "inherit",
  });

  if (result.error) {
    console.error(result.error);
    process.exit(1);
  }

  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function waitForCommand(command, args, timeoutMs = 60_000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt <= timeoutMs) {
    const result = spawnSync(command, args, {
      cwd: repoRoot,
      env: process.env,
      stdio: "ignore",
    });
    if (result.status === 0) return;
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 750);
  }

  throw new Error(`Timed out waiting for command: ${command} ${args.join(" ")}`);
}

function waitForHealth(url, timeoutMs = 60_000) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    function attempt() {
      const request = http.get(url, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 500) {
          resolve();
          return;
        }
        retry();
      });

      request.on("error", retry);
      request.setTimeout(2_000, () => {
        request.destroy();
        retry();
      });
    }

    function retry() {
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error(`Timed out waiting for ${url}`));
        return;
      }
      setTimeout(attempt, 750);
    }

    attempt();
  });
}

function stopProcess(child) {
  if (!child || child.killed) return;
  child.kill();
}

async function main() {
  if (!process.env.SKIP_E2E_DB_START) {
    console.log("[backend-e2e] Starting compose PostgreSQL on 127.0.0.1:55432...");
    run(dockerCommand, ["compose", "-f", path.join(repoRoot, "compose.yaml"), "up", "-d", "db"]);
    console.log("[backend-e2e] Waiting for PostgreSQL readiness...");
    waitForCommand(dockerCommand, [
      "compose",
      "-f",
      path.join(repoRoot, "compose.yaml"),
      "exec",
      "-T",
      "db",
      "pg_isready",
      "-U",
      "travelhunter",
      "-d",
      "travelhunter",
    ]);
  }

  console.log("[backend-e2e] Applying Alembic migrations...");
  run(pythonCommand, ["-m", "alembic", "upgrade", "head"], {
    cwd: backendDir,
    env: backendEnv,
  });
  console.log("[backend-e2e] Applying idempotent development seed data...");
  run(pythonCommand, ["-m", "app.db.seed"], {
    cwd: backendDir,
    env: backendEnv,
  });

  console.log(`[backend-e2e] Starting FastAPI on ${apiBaseUrl}...`);
  const backendServer = spawn(
    pythonCommand,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", apiPort],
    {
      cwd: backendDir,
      env: backendEnv,
      stdio: "inherit",
    },
  );

  const cleanup = () => stopProcess(backendServer);
  process.on("exit", cleanup);
  process.on("SIGINT", () => {
    cleanup();
    process.exit(130);
  });
  process.on("SIGTERM", () => {
    cleanup();
    process.exit(143);
  });

  try {
    await waitForHealth(`${apiBaseUrl}/api/health`);
    console.log("[backend-e2e] Running Playwright backend-mode smoke...");
    const playwrightResult = spawnSync(
      process.execPath,
      [playwrightCli, "test", "--config", "playwright.backend.config.ts", ...playwrightArgs],
      {
        cwd: frontendDir,
        env: {
          ...process.env,
          E2E_FRONTEND_PORT: frontendPort,
          VITE_API_BASE_URL: apiBaseUrl,
        },
        stdio: "inherit",
      },
    );
    if (playwrightResult.error) {
      console.error(playwrightResult.error);
      process.exitCode = 1;
    } else {
      process.exitCode = playwrightResult.status || 0;
    }
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  } finally {
    cleanup();
  }
}

void main();
