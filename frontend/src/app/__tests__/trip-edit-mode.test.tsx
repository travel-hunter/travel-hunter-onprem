import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, appDataApi, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

// jsdom 에는 scrollIntoView 가 없다. 이동 후 카드로 스크롤하는 코드가 여기서 터진다.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

describe("Travel Hunter app — itinerary edit mode", () => {
  it("stacks every day with checkboxes and hides day tabs while editing", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "61",
      revision: 2,
      currentUserRole: "owner",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
        2: [{ id: "2", time: "12:00", label: "Cafe stop", meta: "Dessert" }],
        3: [],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/61?day=1");
      const user = userEvent.setup();

      // 지도와 타임라인이 같은 이름을 함께 그린다. 존재만 본다.
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      expect(screen.queryByText("Cafe stop")).not.toBeInTheDocument(); // Day 1 만 보임

      await user.click(screen.getByRole("button", { name: "편집" }));

      const list = await screen.findByRole("list", {
        name: "전체 일정 편집 목록",
      });
      expect(within(list).getByText("Sunrise peak")).toBeInTheDocument();
      expect(within(list).getByText("Cafe stop")).toBeInTheDocument();
      expect(within(list).getAllByRole("heading", { level: 3 })).toHaveLength(3); // Day 1·2·3 헤더
      expect(screen.queryByLabelText("일정 날짜 선택")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Sunrise peak 순서 이동" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Sunrise peak 상세 열기" }),
      ).not.toBeInTheDocument();

      const bar = screen.getByRole("region", { name: "편집 도구" });
      expect(within(bar).getByText("0개 선택")).toBeInTheDocument();
      expect(within(bar).getByRole("button", { name: "삭제" })).toBeDisabled();

      await user.click(
        screen.getByRole("checkbox", { name: "Sunrise peak 선택" }),
      );
      await user.click(screen.getByRole("checkbox", { name: "Cafe stop 선택" }));
      expect(within(bar).getByText("2개 선택")).toBeInTheDocument();
      expect(within(bar).getByRole("button", { name: "삭제" })).toBeEnabled();

      expect(
        screen.queryByRole("button", { name: "편집" }),
      ).not.toBeInTheDocument(); // 진입 버튼은 편집 중 숨김
      await user.click(within(bar).getByRole("button", { name: "완료" }));
      expect(
        screen.queryByRole("list", { name: "전체 일정 편집 목록" }),
      ).not.toBeInTheDocument();
      expect(screen.getByLabelText("일정 날짜 선택")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "편집" })).toBeInTheDocument();
      expect(document.body).toHaveTextContent("Sunrise peak"); // activeDay 복원
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("does not offer edit mode to viewers", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "62",
      currentUserRole: "viewer",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/62");
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      expect(
        screen.queryByRole("button", { name: "편집" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("deletes the selected places with one batch call and stays in edit mode", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "63",
      revision: 5,
      currentUserRole: "owner",
      days: {
        1: [
          { id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" },
          { id: "2", time: "11:00", label: "Market", meta: "Food" },
        ],
        2: [{ id: "3", time: "12:00", label: "Cafe stop", meta: "Dessert" }],
      },
    };
    const afterDelete: Trip = {
      ...trip,
      revision: 6,
      days: { 1: [trip.days[1][1]], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const deleteSpy = vi
      .spyOn(appDataApi, "deleteTripPlaces")
      .mockResolvedValue(afterDelete);
    const singleDeleteSpy = vi
      .spyOn(appDataApi, "deleteTripPlace")
      .mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/63?day=1");
      const user = userEvent.setup();
      // 지도와 타임라인이 같은 이름을 함께 그린다. 존재만 본다.
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(screen.getByRole("button", { name: "편집" }));
      await user.click(
        await screen.findByRole("checkbox", { name: "Sunrise peak 선택" }),
      );
      await user.click(screen.getByRole("checkbox", { name: "Cafe stop 선택" }));

      const bar = screen.getByRole("region", { name: "편집 도구" });
      await user.click(within(bar).getByRole("button", { name: "삭제" }));
      const confirm = await screen.findByRole("dialog", {
        name: "선택한 장소 2개를 삭제할까요?",
      });
      await user.click(within(confirm).getByRole("button", { name: "삭제" }));

      await waitFor(() =>
        expect(deleteSpy).toHaveBeenCalledWith("63", {
          expectedRevision: 5,
          placeIds: ["1", "3"],
        }),
      );
      expect(deleteSpy).toHaveBeenCalledTimes(1);
      expect(singleDeleteSpy).not.toHaveBeenCalled();

      const list = await screen.findByRole("list", {
        name: "전체 일정 편집 목록",
      });
      await waitFor(() =>
        expect(within(list).queryByText("Sunrise peak")).not.toBeInTheDocument(),
      );
      expect(within(list).queryByText("Cafe stop")).not.toBeInTheDocument();
      expect(within(list).getByText("Market")).toBeInTheDocument();
      expect(within(bar).getByText("0개 선택")).toBeInTheDocument();
      expect(
        screen.getByText("장소 2개를 일정에서 삭제했어요."),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      deleteSpy.mockRestore();
      singleDeleteSpy.mockRestore();
    }
  });

  it("refreshes the trip and keeps the selection when the batch delete conflicts", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "64",
      revision: 1,
      currentUserRole: "owner",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      },
    };
    const latest: Trip = { ...trip, revision: 2 };
    const afterDelete: Trip = { ...latest, revision: 3, days: { 1: [] } };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockResolvedValue(latest);
    const deleteSpy = vi
      .spyOn(appDataApi, "deleteTripPlaces")
      .mockRejectedValueOnce(
        new ApiError("conflict", { status: 409, statusText: "Conflict" }),
      )
      .mockResolvedValueOnce(afterDelete);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/64?day=1");
      const user = userEvent.setup();
      // 지도와 타임라인이 같은 이름을 함께 그린다. 존재만 본다.
      await waitFor(() =>
        expect(document.body).toHaveTextContent("Sunrise peak"),
      );
      await user.click(screen.getByRole("button", { name: "편집" }));
      await user.click(
        await screen.findByRole("checkbox", { name: "Sunrise peak 선택" }),
      );
      await user.click(
        within(screen.getByRole("region", { name: "편집 도구" })).getByRole(
          "button",
          { name: "삭제" },
        ),
      );
      const confirm = await screen.findByRole("dialog", {
        name: "선택한 장소 1개를 삭제할까요?",
      });
      await user.click(within(confirm).getByRole("button", { name: "삭제" }));

      expect(
        await within(confirm).findByText(/다른 사용자가 먼저 일정을 수정/),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("checkbox", { name: "Sunrise peak 선택" }),
      ).toBeChecked();
      // 다이얼로그 유지, 재시도 가능
      expect(
        screen.getByRole("dialog", { name: "선택한 장소 1개를 삭제할까요?" }),
      ).toBeInTheDocument();

      await user.click(within(confirm).getByRole("button", { name: "삭제" }));
      await waitFor(() =>
        expect(deleteSpy).toHaveBeenLastCalledWith("64", {
          expectedRevision: 2,
          placeIds: ["1"],
        }),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("dialog", { name: /선택한 장소/ }),
        ).not.toBeInTheDocument(),
      );
    } finally {
      getTripSpy.mockRestore();
      deleteSpy.mockRestore();
    }
  });
});
