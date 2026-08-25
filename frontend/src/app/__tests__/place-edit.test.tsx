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
      await user.click(document.querySelector(".place-actions .ghost") as HTMLButtonElement);
      await setPlaceTimeFromDefault(user, "10:20");
      await user.clear(document.querySelector('input[name="place-label"]') as HTMLInputElement);
      await user.type(document.querySelector('input[name="place-label"]') as HTMLInputElement, "Updated peak");
      await user.clear(document.querySelector('textarea[name="place-meta"]') as HTMLTextAreaElement);
      await user.type(document.querySelector('textarea[name="place-meta"]') as HTMLTextAreaElement, "New memo");
      await user.click(document.querySelector(".sheet-actions button") as HTMLButtonElement);

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
});
