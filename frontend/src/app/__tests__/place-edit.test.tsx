import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type PlaceSearchCandidate,
  type Recommendation,
  type Trip,
} from "../../api";
import {
  getPreviewTrip,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

function makePlaceCandidate(title: string, meta: string, overrides: Partial<PlaceSearchCandidate> = {}): PlaceSearchCandidate {
  return {
    id: `kakao:${title}`,
    label: "📍",
    title,
    meta,
    categoryName: "장소",
    sourceProvider: "kakao",
    externalPlaceId: title,
    ...overrides,
  };
}

function makeRecommendation(title: string, overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    id: `recommendation:${title}`,
    label: "📍",
    title,
    meta: "추천 장소",
    reason: "일정과 잘 맞는 장소",
    categoryGroup: "attraction",
    categoryCode: "AT4",
    categoryName: "관광명소",
    address: "제주 제주시 추천로 1",
    latitude: 33.45,
    longitude: 126.57,
    placeUrl: `https://place.map.kakao.com/${encodeURIComponent(title)}`,
    suggestedDay: 1,
    sourceProvider: "kakao_local",
    externalPlaceId: `rec-${title}`,
    ...overrides,
  };
}

async function setPlaceTimeFromDefault(
  user: ReturnType<typeof userEvent.setup>,
  time: string,
) {
  const [hour, minute] = time.split(":").map(Number);
  const clearButton = screen.queryByRole("button", {
    name: "시간 비우기",
  }) as HTMLButtonElement | null;
  if (clearButton && !clearButton.disabled) await user.click(clearButton);

  const defaultButton = screen.queryByRole("button", { name: "09:00 설정" });
  if (defaultButton) await user.click(defaultButton);

  const hourUpButton = screen.getByRole("button", {
    name: "방문 시간 1시간 증가",
  });
  const minuteUpButton = screen.getByRole("button", {
    name: "방문 시간 10분 증가",
  });
  for (let index = 0; index < (hour - 9 + 24) % 24; index += 1) {
    await user.click(hourUpButton);
  }
  for (let index = 0; index < Math.floor(minute / 10); index += 1) {
    await user.click(minuteUpButton);
  }
}

describe("Travel Hunter app — place editing", () => {
  it("adds, edits, and deletes places from the itinerary detail", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju editable trip",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [
          ...initialTrip.days[1],
          { id: "2", time: "14:30", label: "Cafe stop", meta: "Dessert" },
        ],
      },
    };
    const editedTrip: Trip = {
      ...addedTrip,
      revision: 3,
      days: {
        1: [
          { id: "1", time: "10:20", label: "Updated peak", meta: "New memo" },
          addedTrip.days[1][1],
        ],
      },
    };
    const deletedTrip: Trip = {
      ...editedTrip,
      revision: 4,
      days: { 1: [editedTrip.days[1][1]] },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);
    const searchPlaceSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([makePlaceCandidate("Cafe stop", "Dessert")]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockResolvedValue(addedTrip);
    const updatePlaceSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockResolvedValue(editedTrip);
    const deletePlaceSpy = vi
      .spyOn(appDataApi, "deleteTripPlace")
      .mockResolvedValue(deletedTrip);
    const confirmSpy = vi.spyOn(window, "confirm");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );
      expect(
        screen.getByRole("group", { name: "방문 시간 선택" }),
      ).toBeInTheDocument();
      expect(
        document.querySelector('input[name="place-time"]:not([type="hidden"])'),
      ).toBeNull();
      await setPlaceTimeFromDefault(user, "14:30");
      const addDialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(
        within(addDialog).getByRole("textbox", { name: "장소 검색" }),
        "Cafe",
      );
      await waitFor(() =>
        expect(searchPlaceSpy).toHaveBeenLastCalledWith("55", { query: "Cafe" }),
      );
      await user.click(within(addDialog).getByRole("button", { name: "Cafe stop 선택" }));
      await waitFor(() =>
        expect(
          window.localStorage.getItem(
            "travel-hunter:draft:trip-place:55:add:1",
          ),
        ).toContain("Cafe stop"),
      );
      await user.click(
        document.querySelector(".sheet-actions button") as HTMLButtonElement,
      );

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "55",
          1,
          expect.objectContaining({
            time: "14:30",
            label: "Cafe stop",
            meta: "Dessert",
            expectedRevision: 1,
            sourceProvider: "kakao",
            externalPlaceId: "Cafe stop",
          }),
        ),
      );
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:add:1"),
      ).toBeNull();
      await waitFor(() => expect(document.body).toHaveTextContent("Cafe stop"));

      await user.click(
        document.querySelector(".place-actions .ghost") as HTMLButtonElement,
      );
      await setPlaceTimeFromDefault(user, "10:20");
      await user.clear(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
      );
      await user.type(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
        "Updated peak",
      );
      await user.clear(
        document.querySelector(
          'textarea[name="place-meta"]',
        ) as HTMLTextAreaElement,
      );
      await user.type(
        document.querySelector(
          'textarea[name="place-meta"]',
        ) as HTMLTextAreaElement,
        "New memo",
      );
      await waitFor(() =>
        expect(
          window.localStorage.getItem(
            "travel-hunter:draft:trip-place:55:edit:1",
          ),
        ).toContain("Updated peak"),
      );
      await user.click(
        document.querySelector(".sheet-actions button") as HTMLButtonElement,
      );

      await waitFor(() =>
        expect(updatePlaceSpy).toHaveBeenCalledWith(
          "55",
          "1",
          expect.objectContaining({ label: "Updated peak", time: "10:20", expectedRevision: 2 }),
        ),
      );
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:edit:1"),
      ).toBeNull();
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Updated peak"),
      );

      await user.click(
        document.querySelector(".place-actions .line") as HTMLButtonElement,
      );
      const deleteDialog = await screen.findByRole("dialog", {
        name: "장소를 삭제할까요?",
      });
      expect(confirmSpy).not.toHaveBeenCalled();
      await user.click(
        within(deleteDialog).getByRole("button", { name: "삭제" }),
      );
      await waitFor(() =>
        expect(deletePlaceSpy).toHaveBeenCalledWith("55", "1", 3),
      );
      await waitFor(() =>
        expect(screen.queryByText("Updated peak")).not.toBeInTheDocument(),
      );
    } finally {
      getTripSpy.mockRestore();
      searchPlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
      updatePlaceSpy.mockRestore();
      deletePlaceSpy.mockRestore();
      confirmSpy.mockRestore();
    }
  });

  it("refreshes the trip and preserves edit drafts when a stale place save conflicts", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "56",
      status: "draft",
      currentUserRole: "owner",
      title: "Conflict trip",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const refreshedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [{ id: "1", time: "09:00", label: "Friend edit", meta: "Updated elsewhere" }],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(initialTrip)
      .mockResolvedValueOnce(refreshedTrip);
    const updatePlaceSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockRejectedValue(
        new ApiError("Trip has changed. Refresh before saving.", {
          status: 409,
          statusText: "Conflict",
          detail: "Trip has changed. Refresh before saving.",
        }),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/56");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(
        document.querySelector(".place-actions .ghost") as HTMLButtonElement,
      );
      await user.clear(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
      );
      await user.type(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
        "My unsaved edit",
      );
      await user.click(
        document.querySelector(".sheet-actions button") as HTMLButtonElement,
      );

      await waitFor(() =>
        expect(updatePlaceSpy).toHaveBeenCalledWith(
          "56",
          "1",
          expect.objectContaining({ label: "My unsaved edit", expectedRevision: 1 }),
        ),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenLastCalledWith("56"));
      expect(
        await screen.findByText(
          "다른 사용자가 먼저 일정을 수정했어요. 최신 내용을 확인한 뒤 다시 저장해 주세요.",
        ),
      ).toBeInTheDocument();
      expect(document.body).toHaveTextContent("Friend edit");
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:56:edit:1"),
      ).toContain("My unsaved edit");
    } finally {
      getTripSpy.mockRestore();
      updatePlaceSpy.mockRestore();
    }
  });

  it("searches Kakao candidates from the add-place sheet and adds the selected place", async () => {
    const recommendation: Recommendation = {
      id: "kakao_local:jeju-food-1",
      label: "food",
      title: "동백 식당",
      meta: "음식점 · 제주 서귀포시 중문관광로 10",
      reason: "Day 1 점심 동선에 맞는 음식점입니다.",
      categoryGroup: "food",
      categoryCode: "FD6",
      categoryName: "음식점",
      address: "제주 서귀포시 중문관광로 10",
      latitude: 33.251,
      longitude: 126.412,
      placeUrl: "https://place.map.kakao.com/jeju-food-1",
      suggestedDay: 1,
      sourceProvider: "kakao_local",
      externalPlaceId: "jeju-food-1",
    };
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju place search trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      days: {
        1: [
          {
            id: "selected-place",
            time: "",
            label: recommendation.title,
            meta: "음식점 · 제주 서귀포시 중문관광로 10",
            address: recommendation.address,
            latitude: recommendation.latitude,
            longitude: recommendation.longitude,
            category: recommendation.categoryName,
            categoryCode: recommendation.categoryCode,
            placeUrl: recommendation.placeUrl,
            sourceProvider: recommendation.sourceProvider,
            externalPlaceId: recommendation.externalPlaceId,
          },
        ],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);
    const searchPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([recommendation]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57?day=1");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.body).toHaveTextContent("Jeju place search trip"),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );

      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(
        within(dialog).getByRole("textbox", { name: "장소 검색" }),
        "동백",
      );
      await waitFor(() =>
        expect(searchPlacesSpy).toHaveBeenLastCalledWith("57", { query: "동백" }),
      );
      await user.click(
        within(dialog).getByRole("button", { name: "동백 식당 선택" }),
      );

      expect(
        within(dialog).queryByRole("textbox", { name: "장소명" }),
      ).not.toBeInTheDocument();
      expect(within(dialog).getByLabelText("선택한 장소")).toHaveTextContent("동백 식당");
      expect(
        within(dialog).getByRole("textbox", { name: "메모" }),
      ).toHaveValue("음식점 · 제주 서귀포시 중문관광로 10");

      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "57",
          1,
          expect.objectContaining({
            label: "동백 식당",
            expectedRevision: 1,
            meta: "음식점 · 제주 서귀포시 중문관광로 10",
            address: "제주 서귀포시 중문관광로 10",
            latitude: 33.251,
            longitude: 126.412,
            category: "음식점",
            categoryCode: "FD6",
            placeUrl: "https://place.map.kakao.com/jeju-food-1",
            sourceProvider: "kakao_local",
            externalPlaceId: "jeju-food-1",
          }),
        ),
      );
      await waitFor(() => expect(document.body).toHaveTextContent("동백 식당"));
    } finally {
      getTripSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("shows a default recommendation in the add-place map preview and saves it by default", async () => {
    const recommendation = makeRecommendation("협재 해변", {
      meta: "15:00 바다 산책",
      categoryName: "해수욕장",
      categoryCode: "AT4",
      address: "제주 제주시 한림읍 협재리",
      latitude: 33.394,
      longitude: 126.239,
      externalPlaceId: "hyeopjae-beach",
    });
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "61",
      status: "draft",
      currentUserRole: "owner",
      title: "Preview recommendation trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [
          {
            id: "rec-1",
            time: "15:00",
            label: recommendation.title,
            meta: "해수욕장 · 제주 제주시 한림읍 협재리",
            address: recommendation.address,
            latitude: recommendation.latitude,
            longitude: recommendation.longitude,
            category: recommendation.categoryName,
            categoryCode: recommendation.categoryCode,
            placeUrl: recommendation.placeUrl,
            sourceProvider: recommendation.sourceProvider,
            externalPlaceId: recommendation.externalPlaceId,
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([recommendation]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/61?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Preview recommendation trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);

      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      const preview = await within(dialog).findByLabelText("장소 지도 미리보기");
      expect(preview).toHaveTextContent("협재 해변");
      expect(preview).toHaveTextContent("제주 제주시 한림읍 협재리");
      expect(listRecommendationsSpy).toHaveBeenCalledWith("61");

      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "61",
          1,
          expect.objectContaining({
            label: "협재 해변",
            meta: "해수욕장 · 제주 제주시 한림읍 협재리",
            address: "제주 제주시 한림읍 협재리",
            latitude: 33.394,
            longitude: 126.239,
            category: "해수욕장",
            categoryCode: "AT4",
            sourceProvider: "kakao_local",
            externalPlaceId: "hyeopjae-beach",
            expectedRevision: 1,
          }),
        ),
      );
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("keeps a search result as preview-only until the user explicitly selects it", async () => {
    const recommendation = makeRecommendation("기존 추천", { address: "제주 기존 추천로" });
    const candidate = makePlaceCandidate("새 검색 장소", "카페 · 제주 새 주소", {
      categoryName: "카페",
      categoryCode: "CE7",
      address: "제주 새 주소",
      latitude: 33.5,
      longitude: 126.5,
      placeUrl: "https://place.map.kakao.com/new-place",
      externalPlaceId: "new-place",
      sourceProvider: "kakao_local",
    });
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "62",
      status: "draft",
      currentUserRole: "owner",
      title: "Preview search trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: { 1: [{ id: "selected-new", time: "", label: candidate.title, meta: candidate.meta }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([recommendation]);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([candidate]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/62?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Preview search trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      expect(await within(dialog).findByLabelText("장소 지도 미리보기")).toHaveTextContent("기존 추천");

      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "새 검색");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("62", { query: "새 검색" }));
      const preview = within(dialog).getByLabelText("장소 지도 미리보기");
      expect(preview).toHaveTextContent("새 검색 장소");

      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(await within(dialog).findByText("검색 결과에서 저장할 장소를 직접 선택해 주세요.")).toBeInTheDocument();

      await user.click(within(dialog).getByRole("button", { name: "새 검색 장소 선택" }));
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));
      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "62",
          1,
          expect.objectContaining({
            label: "새 검색 장소",
            address: "제주 새 주소",
            sourceProvider: "kakao_local",
            externalPlaceId: "new-place",
            expectedRevision: 1,
          }),
        ),
      );
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("keeps a restored add-place draft ahead of delayed default recommendations", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "63",
      status: "draft",
      currentUserRole: "owner",
      title: "Draft preview trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: { 1: [{ id: "draft-place", time: "11:20", label: "보존되는 초안 장소", meta: "초안 메모" }] },
    };
    let resolveRecommendations: (items: Recommendation[]) => void = () => undefined;
    const delayedRecommendations = new Promise<Recommendation[]>((resolve) => {
      resolveRecommendations = resolve;
    });
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockReturnValue(delayedRecommendations);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      window.localStorage.setItem(
        "travel-hunter:draft:trip-place:63:add:1",
        JSON.stringify({
          version: 1,
          savedAt: Date.now(),
          value: {
            dayNumber: 1,
            time: "11:20",
            label: "보존되는 초안 장소",
            meta: "초안 메모",
          },
        }),
      );
      renderAppRoute("/trips/63?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Draft preview trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      const preview = await within(dialog).findByLabelText("장소 지도 미리보기");
      expect(preview).toHaveTextContent("보존되는 초안 장소");
      expect(within(dialog).getByRole("textbox", { name: "장소명" })).toHaveValue("보존되는 초안 장소");

      resolveRecommendations([makeRecommendation("늦게 온 추천")]);
      await waitFor(() => expect(listRecommendationsSpy).toHaveBeenCalledWith("63"));
      await waitFor(() => expect(preview).not.toHaveTextContent("늦게 온 추천"));

      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));
      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "63",
          1,
          expect.objectContaining({
            time: "11:20",
            label: "보존되는 초안 장소",
            meta: "초안 메모",
            expectedRevision: 1,
          }),
        ),
      );
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
      window.localStorage.removeItem("travel-hunter:draft:trip-place:63:add:1");
    }
  });

  it("does not let a delayed default recommendation overwrite an active search", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "66",
      status: "draft",
      currentUserRole: "owner",
      title: "Search race trip",
      days: { 1: [] },
    };
    let resolveRecommendations: (items: Recommendation[]) => void = () => undefined;
    const delayedRecommendations = new Promise<Recommendation[]>((resolve) => {
      resolveRecommendations = resolve;
    });
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockReturnValue(delayedRecommendations);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([makePlaceCandidate("검색 중 후보", "검색 주소")]);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/66?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Search race trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "검색 중");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("66", { query: "검색 중" }));

      resolveRecommendations([makeRecommendation("늦게 온 추천", { meta: "추천 메모" })]);
      await waitFor(() => expect(listRecommendationsSpy).toHaveBeenCalledWith("66"));
      const preview = within(dialog).getByLabelText("장소 지도 미리보기");
      await waitFor(() => expect(preview).toHaveTextContent("검색 중 후보"));
      expect(preview).not.toHaveTextContent("늦게 온 추천");
      expect(within(dialog).getByRole("button", { name: "저장하기" })).toBeEnabled();
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));
      expect(await within(dialog).findByText("검색 결과에서 저장할 장소를 직접 선택해 주세요.")).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      searchPlacesSpy.mockRestore();
    }
  });

  it("ignores stale place search responses when updating the preview card", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "64",
      status: "draft",
      currentUserRole: "owner",
      title: "Stale search trip",
      days: { 1: [] },
    };
    let resolveOldSearch: (items: PlaceSearchCandidate[]) => void = () => undefined;
    let resolveNewSearch: (items: PlaceSearchCandidate[]) => void = () => undefined;
    const oldSearch = new Promise<PlaceSearchCandidate[]>((resolve) => {
      resolveOldSearch = resolve;
    });
    const newSearch = new Promise<PlaceSearchCandidate[]>((resolve) => {
      resolveNewSearch = resolve;
    });
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([]);
    const searchPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockReturnValueOnce(oldSearch)
      .mockReturnValueOnce(newSearch);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/64?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Stale search trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      const searchInput = within(dialog).getByRole("textbox", { name: "장소 검색" });

      fireEvent.change(searchInput, { target: { value: "오래된" } });
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("64", { query: "오래된" }));
      fireEvent.change(searchInput, { target: { value: "최신" } });
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("64", { query: "최신" }));

      resolveNewSearch([makePlaceCandidate("최신 장소", "최신 주소")]);
      expect(await within(dialog).findByRole("button", { name: "최신 장소 선택" })).toBeInTheDocument();
      expect(within(dialog).getByLabelText("장소 지도 미리보기")).toHaveTextContent("최신 장소");

      resolveOldSearch([makePlaceCandidate("오래된 장소", "오래된 주소")]);
      await waitFor(() => expect(within(dialog).getByLabelText("장소 지도 미리보기")).not.toHaveTextContent("오래된 장소"));
      expect(within(dialog).queryByRole("button", { name: "오래된 장소 선택" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      searchPlacesSpy.mockRestore();
    }
  });

  it("keeps the add sheet actionable after clearing a preview-only search", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "68",
      status: "draft",
      currentUserRole: "owner",
      title: "Cleared search trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: { 1: [{ id: "manual-after-clear", time: "09:00", label: "검색 지운 뒤 직접 입력", meta: "" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([]);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([makePlaceCandidate("미리보기 후보", "후보 주소")]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/68?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Cleared search trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      const searchInput = within(dialog).getByRole("textbox", { name: "장소 검색" });

      await user.type(searchInput, "미리보기");
      expect(await within(dialog).findByRole("button", { name: "미리보기 후보 선택" })).toBeInTheDocument();
      expect(within(dialog).getByLabelText("장소 지도 미리보기")).toHaveTextContent("미리보기 후보");

      await user.clear(searchInput);
      const manualInput = await within(dialog).findByRole("textbox", { name: "장소명" });
      expect(manualInput).toHaveValue("");

      await user.type(manualInput, "검색 지운 뒤 직접 입력");
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "68",
          1,
          expect.objectContaining({
            label: "검색 지운 뒤 직접 입력",
            expectedRevision: 1,
          }),
        ),
      );
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not carry recommendation metadata into a no-result manual save", async () => {
    const recommendation = makeRecommendation("오래된 추천", {
      meta: "16:00 추천 메모",
      address: "제주 오래된 추천로",
      latitude: 33.41,
      longitude: 126.31,
      externalPlaceId: "old-rec",
    });
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "67",
      status: "draft",
      currentUserRole: "owner",
      title: "Manual stale metadata trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: { 1: [{ id: "manual-clean", time: "16:00", label: "직접 입력 장소", meta: "" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const listRecommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([recommendation]);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/67?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Manual stale metadata trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      expect(await within(dialog).findByLabelText("장소 지도 미리보기")).toHaveTextContent("오래된 추천");

      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "없는 새 장소");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("67", { query: "없는 새 장소" }));
      expect(await within(dialog).findByText("검색 결과가 없어요. 장소명을 직접 입력해 저장할 수 있어요.")).toBeInTheDocument();
      await user.type(within(dialog).getByRole("textbox", { name: "장소명" }), "직접 입력 장소");
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "67",
          1,
          expect.objectContaining({
            time: "16:00",
            label: "직접 입력 장소",
            expectedRevision: 1,
          }),
        ),
      );
      const payload = addPlaceSpy.mock.calls[0][2];
      expect(payload.meta).not.toBe("16:00 추천 메모");
      expect(payload).not.toHaveProperty("address");
      expect(payload).not.toHaveProperty("latitude");
      expect(payload).not.toHaveProperty("longitude");
      expect(payload).not.toHaveProperty("sourceProvider");
      expect(payload).not.toHaveProperty("externalPlaceId");
    } finally {
      getTripSpy.mockRestore();
      listRecommendationsSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("allows label-only manual place save when search returns no candidates", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      status: "draft",
      currentUserRole: "owner",
      title: "Manual place trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [{ id: "manual-1", time: "", label: "동네 산책길", meta: "" }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(addedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/58?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Manual place trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);

      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "없는장소");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("58", { query: "없는장소" }));
      expect(await within(dialog).findByText("검색 결과가 없어요. 장소명을 직접 입력해 저장할 수 있어요.")).toBeInTheDocument();

      await user.type(within(dialog).getByRole("textbox", { name: "장소명" }), "동네 산책길");
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "58",
          1,
          expect.objectContaining({
            label: "동네 산책길",
            expectedRevision: 1,
          }),
        ),
      );
      expect(addPlaceSpy.mock.calls[0][2]).not.toHaveProperty("address");
      expect(addPlaceSpy.mock.calls[0][2]).not.toHaveProperty("latitude");
      expect(addPlaceSpy.mock.calls[0][2]).not.toHaveProperty("longitude");
      expect(addPlaceSpy.mock.calls[0][2]).not.toHaveProperty("placeUrl");
      await waitFor(() => expect(document.body).toHaveTextContent("동네 산책길"));
    } finally {
      getTripSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not retry a transient add-place failure and preserves manual input", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "59",
      status: "draft",
      currentUserRole: "owner",
      title: "Retry place trip",
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockRejectedValueOnce(new Error("temporary network failure"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/59?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Retry place trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "재시도");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("59", { query: "재시도" }));
      await user.type(within(dialog).getByRole("textbox", { name: "장소명" }), "재시도 장소");
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("59", 1, expect.objectContaining({ label: "재시도 장소", expectedRevision: 1 }));
      expect(await within(dialog).findByText("장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.")).toBeInTheDocument();
      expect(within(dialog).getByRole("textbox", { name: "장소명" })).toHaveValue("재시도 장소");
    } finally {
      getTripSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("refreshes the trip and preserves manual add input when a stale place save conflicts", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "60",
      status: "draft",
      currentUserRole: "owner",
      title: "Manual conflict trip",
      days: { 1: [] },
    };
    const refreshedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [{ id: "friend-1", time: "10:00", label: "친구가 추가한 장소", meta: "최신 일정" }],
      },
    };
    const savedTrip: Trip = {
      ...refreshedTrip,
      revision: 3,
      days: {
        1: [
          ...refreshedTrip.days[1],
          { id: "manual-conflict-1", time: "", label: "보존되는 수동 장소", meta: "보존되는 메모" },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(initialTrip).mockResolvedValueOnce(refreshedTrip);
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockRejectedValueOnce(new ApiError("Trip has changed. Refresh before saving.", { status: 409, statusText: "Conflict" }))
      .mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/60?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Manual conflict trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(dialog).getByRole("textbox", { name: "장소 검색" }), "충돌수동");
      await waitFor(() => expect(searchPlacesSpy).toHaveBeenLastCalledWith("60", { query: "충돌수동" }));
      await user.type(within(dialog).getByRole("textbox", { name: "장소명" }), "보존되는 수동 장소");
      await user.type(within(dialog).getByRole("textbox", { name: "메모" }), "보존되는 메모");
      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(1, "60", 1, expect.objectContaining({ label: "보존되는 수동 장소", meta: "보존되는 메모", expectedRevision: 1 }));
      expect(await screen.findByText("다른 사용자가 먼저 일정을 수정했어요. 최신 내용을 확인한 뒤 다시 저장해 주세요.")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("친구가 추가한 장소");
      expect(within(dialog).getByRole("textbox", { name: "장소명" })).toHaveValue("보존되는 수동 장소");
      expect(within(dialog).getByRole("textbox", { name: "메모" })).toHaveValue("보존되는 메모");

      await user.click(within(dialog).getByRole("button", { name: "저장하기" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(2));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(2, "60", 1, expect.objectContaining({ label: "보존되는 수동 장소", meta: "보존되는 메모", expectedRevision: 2 }));
      await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 추가" })).not.toBeInTheDocument());
      expect(document.body).toHaveTextContent("보존되는 수동 장소");
    } finally {
      getTripSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("restores and clears edit-place drafts", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju editable trip",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(
        document.querySelector(".place-actions .ghost") as HTMLButtonElement,
      );
      await setPlaceTimeFromDefault(user, "11:20");
      await user.clear(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
      );
      await user.type(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
        "Draft peak",
      );
      await user.clear(
        document.querySelector(
          'textarea[name="place-meta"]',
        ) as HTMLTextAreaElement,
      );
      await user.type(
        document.querySelector(
          'textarea[name="place-meta"]',
        ) as HTMLTextAreaElement,
        "Draft memo",
      );
      await waitFor(() =>
        expect(
          window.localStorage.getItem(
            "travel-hunter:draft:trip-place:55:edit:1",
          ),
        ).toContain("Draft peak"),
      );

      cleanup();
      renderAppRoute("/trips/55");
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(
        document.querySelector(".place-actions .ghost") as HTMLButtonElement,
      );
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "11:20",
      );
      expect(document.querySelector('input[name="place-label"]')).toHaveValue(
        "Draft peak",
      );
      expect(document.querySelector('textarea[name="place-meta"]')).toHaveValue(
        "Draft memo",
      );

      await user.click(screen.getByRole("button", { name: "닫기" }));
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:edit:1"),
      ).toBeNull();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("restores and clears add-place drafts", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju editable trip",
      days: { 1: [] },
    };
    const addedTrip: Trip = {
      ...initialTrip,
      days: {
        1: [
          { id: "3", time: "16:00", label: "Tea house", meta: "Reservation" },
        ],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockResolvedValue(addedTrip);
    const searchPlaceSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation((_tripId, options) =>
        Promise.resolve([makePlaceCandidate(options.query === "Tea" ? "Tea house" : options.query, options.query === "Tea" ? "Reservation" : "Draft")]),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(
          document.querySelector(".prototype-trip-action-add"),
        ).toBeTruthy(),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );
      await setPlaceTimeFromDefault(user, "23:50");
      await user.click(
        screen.getByRole("button", { name: "방문 시간 10분 증가" }),
      );
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "00:00",
      );
      await setPlaceTimeFromDefault(user, "16:00");
      const firstAddDialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(firstAddDialog).getByRole("textbox", { name: "장소 검색" }), "Tea");
      await waitFor(() => expect(searchPlaceSpy).toHaveBeenLastCalledWith("55", { query: "Tea" }));
      await user.click(within(firstAddDialog).getByRole("button", { name: "Tea house 선택" }));
      await waitFor(() =>
        expect(
          window.localStorage.getItem(
            "travel-hunter:draft:trip-place:55:add:1",
          ),
        ).toContain("Tea house"),
      );

      cleanup();
      renderAppRoute("/trips/55");
      await waitFor(() =>
        expect(
          document.querySelector(".prototype-trip-action-add"),
        ).toBeTruthy(),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "16:00",
      );
      expect(document.querySelector('input[name="place-label"]')).toHaveValue(
        "Tea house",
      );
      expect(document.querySelector('textarea[name="place-meta"]')).toHaveValue(
        "Reservation",
      );

      await user.click(
        document.querySelector(".sheet-actions button") as HTMLButtonElement,
      );
      await waitFor(() =>
        expect(addPlaceSpy).toHaveBeenCalledWith(
          "55",
          1,
          expect.objectContaining({ label: "Tea house", expectedRevision: 1 }),
        ),
      );
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:add:1"),
      ).toBeNull();

      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );
      const secondAddDialog = await screen.findByRole("dialog", { name: "장소 추가" });
      await user.type(within(secondAddDialog).getByRole("textbox", { name: "장소 검색" }), "Will cancel");
      await waitFor(() => expect(searchPlaceSpy).toHaveBeenLastCalledWith("55", { query: "Will cancel" }));
      await user.click(within(secondAddDialog).getByRole("button", { name: "Will cancel 선택" }));
      await waitFor(() =>
        expect(
          window.localStorage.getItem(
            "travel-hunter:draft:trip-place:55:add:1",
          ),
        ).toContain("Will cancel"),
      );
      await user.click(screen.getByRole("button", { name: "닫기" }));
      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:add:1"),
      ).toBeNull();
    } finally {
      getTripSpy.mockRestore();
      addPlaceSpy.mockRestore();
      searchPlaceSpy.mockRestore();
    }
  });

  it("shows and discards a restored add-place draft", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju editable trip",
      days: { 1: [] },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);

    try {
      await login();
      cleanup();
      window.localStorage.setItem(
        "travel-hunter:draft:trip-place:55:add:1",
        JSON.stringify({
          version: 1,
          savedAt: Date.now(),
          value: {
            dayNumber: 1,
            time: "16:00",
            label: "Tea house",
            meta: "Reservation",
          },
        }),
      );
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(
          document.querySelector(".prototype-trip-action-add"),
        ).toBeTruthy(),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );

      expect(
        screen.getByText("작성 중이던 장소 내용을 불러왔어요."),
      ).toBeInTheDocument();
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "16:00",
      );
      expect(document.querySelector('input[name="place-label"]')).toHaveValue(
        "Tea house",
      );

      await user.click(screen.getByRole("button", { name: "삭제" }));

      expect(
        window.localStorage.getItem("travel-hunter:draft:trip-place:55:add:1"),
      ).toBeNull();
      expect(
        screen.queryByText("작성 중이던 장소 내용을 불러왔어요."),
      ).not.toBeInTheDocument();
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "",
      );
      expect(document.querySelector('input[name="place-label"]')).toHaveValue(
        "",
      );
      expect(document.querySelector('textarea[name="place-meta"]')).toHaveValue(
        "",
      );
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("validates place time as a 10 minute spinner value", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Jeju editable trip",
      days: { 1: [] },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockResolvedValue(initialTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();
      window.localStorage.setItem(
        "travel-hunter:draft:trip-place:55:add:1",
        JSON.stringify({
          version: 1,
          savedAt: Date.now(),
          value: {
            dayNumber: 1,
            time: "09:35",
            label: "Invalid time stop",
            meta: "",
          },
        }),
      );

      await waitFor(() =>
        expect(
          document.querySelector(".prototype-trip-action-add"),
        ).toBeTruthy(),
      );
      await user.click(
        document.querySelector(
          ".prototype-trip-action-add",
        ) as HTMLButtonElement,
      );
      expect(document.querySelector('input[name="place-time"]')).toHaveValue(
        "09:35",
      );
      await user.click(
        document.querySelector(".sheet-actions button") as HTMLButtonElement,
      );

      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(
        screen.getByText("방문 시간은 10분 단위로 선택해 주세요."),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("renders viewer trips as read-only in the itinerary detail", async () => {
    const viewerTrip: Trip = {
      ...getPreviewTrip(),
      id: "66",
      title: "Viewer trip",
      currentUserRole: "viewer",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(viewerTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/66");

      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      expect(document.body).toHaveTextContent("보기 권한으로 참여 중입니다");
      expect(
        document.querySelector(".prototype-trip-action-add"),
      ).toBeInTheDocument();
      await userEvent.setup().click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      expect(
        await screen.findByText(/편집 권한이 필요해요/),
      ).toBeInTheDocument();
      expect(document.querySelector(".place-actions")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Sunrise peak 순서 이동" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("moves places with drag handles within a day and to another day", async () => {
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Movable trip",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "Morning market",
            meta: "Breakfast",
          },
          { id: "2", time: "14:00", label: "Cafe stop", meta: "Dessert" },
        ],
        2: [{ id: "3", time: "10:00", label: "Beach walk", meta: "Sea" }],
      },
    };
    const movedUpTrip: Trip = {
      ...initialTrip,
      days: {
        1: [initialTrip.days[1][1], initialTrip.days[1][0]],
        2: initialTrip.days[2],
      },
    };
    const movedDayTrip: Trip = {
      ...initialTrip,
      days: {
        1: [initialTrip.days[1][0]],
        2: [initialTrip.days[2][0], initialTrip.days[1][1]],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(initialTrip);
    let resolveFirstMove: (trip: Trip) => void = () => undefined;
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockImplementationOnce(
        () =>
          new Promise<Trip>((resolve) => {
            resolveFirstMove = resolve;
          }),
      )
      .mockResolvedValueOnce(movedDayTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Cafe stop"));
      expect(
        screen.queryByText("장소 카드의 이동 핸들로 순서를 조정할 수 있어요"),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Day 1/ })).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "위로" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "아래로" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "이동" }),
      ).not.toBeInTheDocument();
      const secondTimelineItem = document.querySelectorAll(
        ".timeline-item",
      )[1] as HTMLElement;
      const cafeDragHandle = within(secondTimelineItem).getByRole("button", {
        name: "Cafe stop 순서 이동",
      });
      expect(cafeDragHandle).toHaveClass("drag-handle");
      fireEvent.keyDown(cafeDragHandle, { key: "ArrowUp" });

      await waitFor(() =>
        expect(movePlaceSpy).toHaveBeenCalledWith("55", "2", {
          dayNumber: 1,
          position: 1,
          expectedRevision: 1,
        }),
      );
      expect(await screen.findByText("이동 중")).toBeInTheDocument();
      resolveFirstMove(movedUpTrip);
      await waitFor(() =>
        expect(
          (document.querySelector(".place-detail h4") as HTMLElement)
            .textContent,
        ).toBe("Cafe stop"),
      );

      const firstTimelineItem = document.querySelectorAll(
        ".timeline-item",
      )[0] as HTMLElement;
      const movedCafeDragHandle = within(firstTimelineItem).getByRole(
        "button",
        { name: "Cafe stop 순서 이동" },
      );
      fireEvent.keyDown(movedCafeDragHandle, {
        key: "ArrowRight",
        shiftKey: true,
      });

      await waitFor(() =>
        expect(movePlaceSpy).toHaveBeenLastCalledWith("55", "2", {
          dayNumber: 2,
          position: 2,
          expectedRevision: 1,
        }),
      );
      await waitFor(() =>
        expect(screen.getByText("Day 2")).toBeInTheDocument(),
      );
      await user.click(screen.getByText("Day 2"));
      expect(document.body).toHaveTextContent("Cafe stop");
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });

  it("shows a message when moving a place fails", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      status: "draft",
      currentUserRole: "owner",
      title: "Move failure trip",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "Morning market",
            meta: "Breakfast",
          },
          { id: "2", time: "14:00", label: "Cafe stop", meta: "Dessert" },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockRejectedValue(new Error("move failed"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");

      await waitFor(() => expect(document.body).toHaveTextContent("Cafe stop"));
      const secondTimelineItem = document.querySelectorAll(
        ".timeline-item",
      )[1] as HTMLElement;
      const cafeDragHandle = within(secondTimelineItem).getByRole("button", {
        name: "Cafe stop 순서 이동",
      });
      fireEvent.keyDown(cafeDragHandle, { key: "ArrowUp" });

      await waitFor(() =>
        expect(movePlaceSpy).toHaveBeenCalledWith("55", "2", {
          dayNumber: 1,
          position: 1,
          expectedRevision: 1,
        }),
      );
      await waitFor(() =>
        expect(document.body).toHaveTextContent(
          "장소 순서를 변경하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ),
      );
      expect(
        (document.querySelector(".place-detail h4") as HTMLElement).textContent,
      ).toBe("Morning market");
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });
});
