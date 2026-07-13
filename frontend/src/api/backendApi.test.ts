import { afterEach, describe, expect, it, vi } from "vitest";
import { backendApi } from "./backendApi";
import { apiConfig, setApiAccessToken } from "./client";

describe("backendApi account methods", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setApiAccessToken(null);
  });

  it("posts password change requests to the contract endpoint", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ changed: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      backendApi.changePassword({
        currentPassword: "old-password123",
        newPassword: "new-password123",
      }),
    ).resolves.toEqual({ changed: true });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/auth/password/change`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          currentPassword: "old-password123",
          newPassword: "new-password123",
        }),
        credentials: "include",
      }),
    );
  });

  it("posts withdrawal requests to the contract endpoint", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ withdrawn: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.withdraw({ confirmationPhrase: "탈퇴합니다" })).resolves.toEqual({ withdrawn: true });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/auth/withdraw`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ confirmationPhrase: "탈퇴합니다" }),
        credentials: "include",
      }),
    );
  });
});
