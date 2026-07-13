import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

function parseAllowedHosts(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const previewAllowedHosts = Array.from(
    new Set([
      ".trycloudflare.com",
      ...parseAllowedHosts(env.STAGING_DOMAIN),
      ...parseAllowedHosts(env.__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS),
    ])
  );

  return {
    plugins: [react()],
    build: {
      sourcemap: false,
    },
    preview: {
      allowedHosts: previewAllowedHosts,
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      setupFiles: "./src/test/setup.ts",
      // The app route tests drive a shared, stateful dev backend (login/session),
      // so test files must run serially to avoid cross-file contention.
      fileParallelism: false,
    },
  };
});
