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

describe("backendApi trip mutation methods", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setApiAccessToken(null);
  });

  const tripResponse = {
    id: "7",
    title: "Updated trip",
    status: "draft",
    revision: 2,
    dates: "2026.06.15 - 06.20",
    startDate: "2026-06-15",
    endDate: "2026-06-20",
    people: ["Test User"],
    participantCount: 1,
    expectedSaving: "0원",
    linkedPolicies: [],
    recommendedPolicies: [],
    days: { 1: [] },
    currentUserRole: "owner",
  };

  it("patches trip settings through the contract endpoint", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      backendApi.updateTripSettings("7", {
        expectedRevision: 1,
        title: "Updated trip",
        startDate: "2026-06-15",
        endDate: "2026-06-20",
        overflowPlaceStrategy: "moveToLastDay",
      }),
    ).resolves.toMatchObject({ id: "7", title: "Updated trip" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/settings`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expectedRevision: 1,
          title: "Updated trip",
          startDate: "2026-06-15",
          endDate: "2026-06-20",
          overflowPlaceStrategy: "moveToLastDay",
        }),
      }),
    );
  });

  it("posts multiple places through the batch endpoint", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      backendApi.addTripPlaces("7", 2, {
        expectedRevision: 4,
        places: [
          {
            time: "",
            label: "Cafe stop",
            meta: "Dessert",
            sourceProvider: "kakao",
          },
        ],
      }),
    ).resolves.toMatchObject({ id: "7" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/2/places/batch`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedRevision: 4,
          places: [
            {
              time: "",
              label: "Cafe stop",
              meta: "Dessert",
              sourceProvider: "kakao",
            },
          ],
        }),
      }),
    );
  });
});
