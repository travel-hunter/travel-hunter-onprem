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
    region: "제주",
    travelAreaId: "jeju-west",
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

  it("requests one complete sido travel-area catalog", async () => {
    const catalogResponse = {
      sido: "제주",
      sourceAsOf: "2026-09-04",
      wholeArea: {
        travelAreaId: "jeju-all",
        travelAreaName: "제주 전체",
        sido: "제주",
        areaType: "whole",
        includedCities: ["제주시", "서귀포시"],
      },
      recommendedAreas: [],
      administrativeAreas: [],
    };
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(catalogResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.getTravelAreaCatalog("제주")).resolves.toEqual(catalogResponse);

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/travel-areas?sido=%EC%A0%9C%EC%A3%BC`,
      // GET 은 method 를 넘기지 않는다. 다른 조회 메서드와 같은 모양이다.
      expect.objectContaining({
        credentials: "include",
      }),
    );
  });

  it("forwards an abort signal for trip place search", async () => {
    const controller = new AbortController();
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.searchTripPlaces(
      "7",
      { query: "성산일출봉" },
      { signal: controller.signal },
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/place-search?query=%EC%84%B1%EC%82%B0%EC%9D%BC%EC%B6%9C%EB%B4%89`,
      expect.objectContaining({
        credentials: "include",
        signal: controller.signal,
      }),
    );
  });

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

  it("serializes travelAreaId in trip settings", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.updateTripSettings("7", {
      expectedRevision: 4,
      travelAreaId: "jeju-west",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/settings`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expectedRevision: 4,
          travelAreaId: "jeju-west",
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

  it("posts a batch delete with numeric place ids", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      backendApi.deleteTripPlaces("7", { expectedRevision: 4, placeIds: ["3", "5"] }),
    ).resolves.toMatchObject({ id: "7" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/places/batch-delete`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expectedRevision: 4, placeIds: [3, 5] }),
      }),
    );
  });
});

describe("backendApi place matching", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the picked place to the match endpoint and returns the server's answer", async () => {
    const answer = { result: "none", places: [] };
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(answer), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    const request = { name: "오동도", latitude: 34.7443, longitude: 127.7663, categoryCode: "AT4" };

    await expect(backendApi.matchPlace(request)).resolves.toEqual(answer);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/places/match`,
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });
});
