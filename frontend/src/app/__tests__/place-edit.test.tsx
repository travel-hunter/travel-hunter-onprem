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

// jsdom 에는 scrollIntoView 가 없다. 이동 후 카드로 스크롤하는 코드가 여기서 터진다.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

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
  it("edits places from the itinerary detail", async () => {
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
    const editedTrip: Trip = {
      ...initialTrip,
      revision: 2,
      days: {
        1: [{ id: "1", time: "10:20", label: "Updated peak", meta: "New memo" }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const updatePlaceSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue(editedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Sunrise peak"));
      await user.click(screen.getByRole("button", { name: "Sunrise peak 상세 열기" }));
      expect(document.querySelector(".place-actions")).toBeNull();
      await setPlaceTimeFromDefault(user, "10:20");
      await user.clear(document.querySelector('input[name="place-label"]') as HTMLInputElement);
      await user.type(document.querySelector('input[name="place-label"]') as HTMLInputElement, "Updated peak");
      await user.clear(document.querySelector('textarea[name="place-meta"]') as HTMLTextAreaElement);
      await user.type(document.querySelector('textarea[name="place-meta"]') as HTMLTextAreaElement, "New memo");
      await user.click(screen.getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(updatePlaceSpy).toHaveBeenCalledWith(
          "55",
          "1",
          expect.objectContaining({
            time: "10:20",
            label: "Updated peak",
            meta: "New memo",
            expectedRevision: 1,
          }),
        ),
      );
      await waitFor(() => expect(document.body).toHaveTextContent("Updated peak"));
    } finally {
      getTripSpy.mockRestore();
      updatePlaceSpy.mockRestore();
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
        screen.getByRole("button", { name: "Sunrise peak 상세 열기" }),
      );
      await user.clear(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
      );
      await user.type(
        document.querySelector('input[name="place-label"]') as HTMLInputElement,
        "My unsaved edit",
      );
      await user.click(screen.getByRole("button", { name: "저장하기" }));

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
        screen.getByRole("button", { name: "Sunrise peak 상세 열기" }),
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
        screen.getByRole("button", { name: "Sunrise peak 상세 열기" }),
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
        ".timeline-slot",
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
      await waitFor(() => {
        const moved = document.querySelector(".timeline-slot.just-moved");
        expect(moved).not.toBeNull();
        expect(moved).toHaveTextContent("Cafe stop");
      });

      const firstTimelineItem = document.querySelectorAll(
        ".timeline-slot",
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
        ".timeline-slot",
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

  it("deletes a place from the sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      revision: 3,
      currentUserRole: "owner",
      days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
    };
    const afterDelete: Trip = { ...trip, revision: 4, days: { 1: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const deleteSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(afterDelete);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      await user.click(within(sheet).getByRole("button", { name: "삭제" }));
      const confirm = await screen.findByRole("dialog", { name: "장소를 삭제할까요?" });
      await user.click(within(confirm).getByRole("button", { name: "삭제" }));
      await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("57", "1", 3));
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument(),
      );
      expect(document.body).not.toHaveTextContent("Sunrise peak");
    } finally {
      getTripSpy.mockRestore();
      deleteSpy.mockRestore();
    }
  });

  it("moves the place immediately when a day chip is chosen and saves fields without a move", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      revision: 5,
      currentUserRole: "owner",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
        2: [{ id: "2", time: "08:00", label: "Early market", meta: "Food" }],
      },
    };
    const movedTrip: Trip = {
      ...trip,
      revision: 6,
      days: { 1: [], 2: [trip.days[2][0], trip.days[1][0]] },
    };
    const savedTrip: Trip = {
      ...movedTrip,
      revision: 7,
      days: { 1: [], 2: [trip.days[2][0], { ...trip.days[1][0], label: "Renamed peak" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const moveSpy = vi.spyOn(appDataApi, "moveTripPlace").mockResolvedValue(movedTrip);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue(savedTrip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/58?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });

      await user.click(within(sheet).getByRole("radio", { name: /Day 2/ }));
      await waitFor(() =>
        expect(moveSpy).toHaveBeenCalledWith("58", "1", {
          dayNumber: 2,
          position: 2, // 09:00 은 08:00 뒤
          expectedRevision: 5,
        }),
      );
      // 시트는 열린 채, Day 2 가 선택됨 — setTrip/setPlaceEditor 는 spy 해결 뒤에 반영되므로 waitFor
      await waitFor(() =>
        expect(within(sheet).getByRole("radio", { name: /Day 2/ })).toHaveAttribute("aria-checked", "true"),
      );
      // 시트가 타임라인을 덮고 있으니 플래시는 아직 터지지 않는다 — 닫힐 때로 미뤄진다.
      expect(document.querySelector(".timeline-slot.just-moved")).toBeNull();

      await user.clear(document.querySelector('input[name="place-label"]') as HTMLInputElement);
      await user.type(document.querySelector('input[name="place-label"]') as HTMLInputElement, "Renamed peak");
      await user.click(within(sheet).getByRole("button", { name: "저장하기" }));

      await waitFor(() =>
        expect(updateSpy).toHaveBeenCalledWith("58", "1", expect.objectContaining({ label: "Renamed peak", expectedRevision: 6 })),
      );
      await waitFor(() => expect(document.body).toHaveTextContent("Renamed peak"));
      // PATCH 가 끝난 뒤에 센다. 먼저 세면 저장 뒤 move 가 되살아나도 못 잡는다.
      expect(moveSpy).toHaveBeenCalledTimes(1); // 저장은 move 를 다시 부르지 않는다
      // 저장이 시트를 닫았으니 미뤄 둔 플래시가 그제서야 풀린다.
      await waitFor(() => {
        const moved = document.querySelector(".timeline-slot.just-moved");
        expect(moved).toHaveTextContent("Renamed peak");
      });
    } finally {
      getTripSpy.mockRestore();
      moveSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("reports a failed day move from the sheet instead of swallowing it", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "59",
      revision: 1,
      currentUserRole: "owner",
      days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const moveSpy = vi.spyOn(appDataApi, "moveTripPlace").mockRejectedValue(new Error("network"));
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/59?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      await user.click(within(sheet).getByRole("radio", { name: /Day 2/ }));
      expect(await within(sheet).findByText("장소 순서를 변경하지 못했어요. 잠시 후 다시 시도해 주세요.")).toBeInTheDocument();
      expect(within(sheet).getByRole("radio", { name: /Day 1/ })).toHaveAttribute("aria-checked", "true");
    } finally {
      getTripSpy.mockRestore();
      moveSpy.mockRestore();
    }
  });
});
