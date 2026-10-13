import { afterEach, describe, expect, it, vi } from "vitest";
import { backendApi } from "./backendApi";
import { apiConfig, setApiAccessToken } from "./client";
import type { PublicPlaceItem, TripPlaceAddItem } from "./types";

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

  it("sends the page of trip place search only when it is given", async () => {
    const fetchSpy = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.searchTripPlaces("7", { query: "카페", page: 2 });
    await backendApi.searchTripPlaces("7", { query: "카페" });

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      `${apiConfig.baseUrl}/api/trips/7/place-search?query=%EC%B9%B4%ED%8E%98&page=2`,
      expect.anything(),
    );
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      `${apiConfig.baseUrl}/api/trips/7/place-search?query=%EC%B9%B4%ED%8E%98`,
      expect.anything(),
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

  it("posts public and custom places through the batch endpoint without Kakao place values", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    const places: TripPlaceAddItem[] = [
      { publicPlace: { source: "tourapi", sourceId: "126508" }, kakaoPlaceId: "8193468" },
      { customPlace: { name: "할머니 댁", geoRef: { kind: "building", id: 501, pin: true } } },
    ];

    await expect(
      backendApi.addTripPlaces("7", 2, { expectedRevision: 4, places }),
    ).resolves.toMatchObject({ id: "7" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/2/places/batch`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expectedRevision: 4, places }),
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

describe("backendApi place add flow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setApiAccessToken(null);
  });

  const tripResponse = {
    id: "7",
    title: "담는 흐름 여행",
    status: "draft",
    revision: 5,
    region: "전남",
    travelAreaId: "whole:%EC%A0%84%EB%82%A8",
    dates: "2026.11.01 - 11.02",
    startDate: "2026-11-01",
    endDate: "2026-11-02",
    people: ["Test User"],
    participantCount: 1,
    expectedSaving: "0원",
    linkedPolicies: [],
    recommendedPolicies: [],
    days: { 1: [] },
    currentUserRole: "owner",
  };
  const jsonResponse = (body: unknown) =>
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

  it("posts one custom place with the Kakao place id as a link key only", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(tripResponse));
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.addTripPlace("7", 1, {
      expectedRevision: 4,
      customPlace: { name: "숙소 앞 편의점" },
      kakaoPlaceId: "8193468",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/1/places`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedRevision: 4,
          customPlace: { name: "숙소 앞 편의점" },
          kakaoPlaceId: "8193468",
        }),
      }),
    );
  });

  it("patches a place with only the changed fields", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(tripResponse));
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.updateTripPlace("7", "31", {
      expectedRevision: 5,
      customPlace: { name: "다시 적은 이름" },
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/places/31`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expectedRevision: 5,
          customPlace: { name: "다시 적은 이름" },
        }),
      }),
    );
  });

  it("reads the trip area center that the map picker opens on", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ latitude: 34.76, longitude: 127.66 }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.getTripAreaCenter("7")).resolves.toEqual({ latitude: 34.76, longitude: 127.66 });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/area-center`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("asks the server which building or parcel holds a picked point", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ fill: null, nearCenter: false }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.locatePlace(37.7712, 128.948)).resolves.toEqual({ fill: null, nearCenter: false });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/places/locate`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ latitude: 37.7712, longitude: 128.948 }) }),
    );
  });

  it("unwraps the public candidates of a legacy Kakao place", async () => {
    const candidate: PublicPlaceItem = {
      source: "sangga",
      sourceId: "MA010120220800000001",
      name: "여수 해물집",
      address: "전남 여수시 중앙로 1",
      latitude: 34.74,
      longitude: 127.74,
      category: "food",
      distanceMeters: 40,
    };
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ places: [candidate] }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.listLegacyPlaceCandidates("7", "31")).resolves.toEqual([candidate]);

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/places/31/public-candidates`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("keeps Kakao place values out of the add request type", () => {
    // tsc 가 보는 시험이다 - 카카오 값(이름 · 주소 · 좌표 · 분류)을 싣는 칸은 담기 요청에 없다
    const request: TripPlaceAddItem = {
      customPlace: { name: "직접 적은 곳" },
      // @ts-expect-error label 은 담기 요청에 없다(사용자가 쓴 이름은 customPlace.name)
      label: "카카오가 준 이름",
    };

    expect(Object.keys(request)).toContain("customPlace");
  });
});
