import { describe, expect, it, vi } from "vitest";

import { adminUrl, isAdminHost, shouldShowPublicAuthActions } from "../adminHost";

describe("admin host routing", () => {
  it("builds an admin-host URL without accepting an external redirect", () => {
    vi.stubEnv("VITE_ADMIN_BASE_URL", "https://admin.dev.example");

    expect(adminUrl("/admin/policies?status=active")).toBe(
      "https://admin.dev.example/admin/policies?status=active",
    );
    expect(adminUrl("https://attacker.example")).toBe(
      "https://admin.dev.example/admin",
    );
  });

  it("recognizes only the configured admin origin", () => {
    vi.stubEnv("VITE_ADMIN_BASE_URL", "https://admin.dev.example");

    expect(isAdminHost("https://admin.dev.example")).toBe(true);
    expect(isAdminHost("https://dev.example")).toBe(false);
  });
  it("hides public signup and social login actions on the configured admin host", () => {
    vi.stubEnv("VITE_ADMIN_BASE_URL", "https://admin.dev.example");

    expect(shouldShowPublicAuthActions("https://admin.dev.example")).toBe(false);
    expect(shouldShowPublicAuthActions("https://dev.example")).toBe(true);
  });
});
