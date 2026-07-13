import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type Trip,
} from "../../api";
import {
  examplePolicySlug,
  examplePolicyTitle,
  getPreviewTrip,
} from "../../test/fixtures";
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — trips list", () => {
  it("deletes trips from the trips list without using the home recommendation card", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "77",
      title: "부산 4일 여행",
      dates: "2026.06.15 - 06.18",
      days: { 1: [], 2: [], 3: [], 4: [] },
    };
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const deleteTripSpy = vi
      .spyOn(appDataApi, "deleteTrip")
      .mockResolvedValue({ tripId: "77", deleted: true });
    const confirmSpy = vi.spyOn(window, "confirm");

    try {
      await login();
      const homeAiCard = document.querySelector(".prototype-home-ai-card");
      expect(homeAiCard).toBeTruthy();
      expect(homeAiCard).not.toHaveTextContent("부산 4일 여행");
      expect(
        screen.queryByRole("button", { name: "삭제" }),
      ).not.toBeInTheDocument();

      cleanup();
      renderAppRoute("/trips");
      const tripHeader = document.querySelector(
        ".prototype-screen-head",
      ) as HTMLElement;
      expect(
        within(tripHeader).queryByText("여행 일정"),
      ).not.toBeInTheDocument();
      expect(within(tripHeader).getByText("내 일정")).toBeInTheDocument();
      expect(
        within(tripHeader).getByRole("link", { name: "+ 새 일정" }),
      ).toHaveAttribute("href", "/trips/new");
      expect(
        document.querySelector(".prototype-floating-create"),
      ).not.toBeInTheDocument();
      await screen.findByText("부산 4일 여행");
      expect(
        document.querySelector(".trip-visual-emoji")?.textContent,
      ).toContain("🌉");
      expect(document.body).toHaveTextContent(
        "2026.06.15 - 06.18 · 4일 · 장소 0개",
      );
      expect(document.body).not.toHaveTextContent("추천 정책 확인 가능");
      expect(document.body).toHaveTextContent("1명 참여 중");
      expect(document.body).toHaveTextContent("예상 혜택");

      const deleteButton = await screen.findByRole("button", { name: "삭제" });
      const user = userEvent.setup();
      await user.click(deleteButton);

      const cancelDialog = await screen.findByRole("dialog", {
        name: "일정을 삭제할까요?",
      });
      expect(document.body).toHaveTextContent(
        "부산 4일 여행 일정과 연결된 장소, 초대, 정책 연결이 함께 삭제됩니다.",
      );
      expect(confirmSpy).not.toHaveBeenCalled();
      await user.click(
        within(cancelDialog).getByRole("button", { name: "취소" }),
      );
      expect(deleteTripSpy).not.toHaveBeenCalled();

      await user.click(await screen.findByRole("button", { name: "삭제" }));
      const deleteDialog = await screen.findByRole("dialog", {
        name: "일정을 삭제할까요?",
      });
      await user.click(
        within(deleteDialog).getByRole("button", { name: "삭제" }),
      );

      await waitFor(() => expect(deleteTripSpy).toHaveBeenCalledWith("77"));
      await waitFor(() =>
        expect(screen.queryByText("부산 4일 여행")).not.toBeInTheDocument(),
      );
      expect(document.body).toHaveTextContent("아직 등록된 일정이 없어요");
    } finally {
      listTripsSpy.mockRestore();
      deleteTripSpy.mockRestore();
      confirmSpy.mockRestore();
    }
  });

  it("keeps a trip visible when trip deletion fails", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "88",
      title: "강원 2일 여행",
      dates: "2026.06.15 - 06.16",
      days: { 1: [], 2: [] },
    };
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const deleteTripSpy = vi
      .spyOn(appDataApi, "deleteTrip")
      .mockRejectedValue(new Error("Trip not found"));
    const confirmSpy = vi.spyOn(window, "confirm");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "삭제" }));
      const deleteDialog = await screen.findByRole("dialog", {
        name: "일정을 삭제할까요?",
      });
      expect(confirmSpy).not.toHaveBeenCalled();
      await user.click(
        within(deleteDialog).getByRole("button", { name: "삭제" }),
      );

      await waitFor(() =>
        expect(document.body).toHaveTextContent(
          "일정을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ),
      );
      expect(document.body).toHaveTextContent("강원 2일 여행");
    } finally {
      listTripsSpy.mockRestore();
      deleteTripSpy.mockRestore();
      confirmSpy.mockRestore();
    }
  });

  it("renders trips without list confirmation controls or status badges", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "91",
      title: "Draft trip",
      status: "draft",
      currentUserRole: "owner",
    };
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockResolvedValue({ ...trip, status: "confirmed" });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips");
      await screen.findByText("Draft trip");
      expect(
        document.querySelector(".trip-confirm-panel"),
      ).not.toBeInTheDocument();
      expect(document.querySelector(".trip-dday-chip")).not.toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
      const statusTags = Array.from(
        document.querySelectorAll(".itinerary-policy-row .tag"),
      );
      expect(statusTags).toHaveLength(1);
      expect(statusTags[0]).toHaveClass("benefit");
      expect(document.body).not.toHaveTextContent("작성 중");
      expect(document.body).not.toHaveTextContent("확정됨");
    } finally {
      listTripsSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("does not call trip confirmation from the trips list", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "92",
      title: "Draft trip without list action",
      status: "draft",
      currentUserRole: "owner",
    };
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockRejectedValue(new Error("save failed"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips");
      await screen.findByText("Draft trip without list action");
      expect(screen.queryByText("작성 중")).not.toBeInTheDocument();
      expect(screen.queryByText("확정됨")).not.toBeInTheDocument();
      expect(
        document.querySelector(".trip-confirm-check"),
      ).not.toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
    } finally {
      listTripsSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("hides trip confirmation controls for viewer trips", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "93",
      title: "Viewer trip",
      status: "draft",
      currentUserRole: "viewer",
    };
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockResolvedValue({ ...trip, status: "confirmed" });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips");
      await screen.findByText("Viewer trip");
      expect(
        document.querySelector(".trip-confirm-panel"),
      ).not.toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
    } finally {
      listTripsSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("keeps confirmed owner trip detail editable without confirmation controls", async () => {
    const confirmedTrip: Trip = {
      ...getPreviewTrip(),
      id: "94",
      title: "Confirmed detail trip",
      status: "confirmed",
      currentUserRole: "owner",
      linkedPolicies: [
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "10,000원 할인",
          region: "경남",
        },
      ],
      days: {
        1: [
          {
            id: "p1",
            time: "09:00",
            label: "Locked beach",
            meta: "확정 일정 장소",
          },
        ],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(confirmedTrip);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockRejectedValue(new Error("status update should not run"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/94");

      await waitFor(() =>
        expect(
          screen.getAllByText("Confirmed detail trip").length,
        ).toBeGreaterThan(0),
      );
      expect(
        screen.queryByRole("region", { name: "일정 확정 상태" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정취소" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정하기" }),
      ).not.toBeInTheDocument();
      expect(document.body).not.toHaveTextContent(
        "확정된 일정은 편집할 수 없어요",
      );
      expect(
        document.querySelector(".prototype-trip-action-add"),
      ).toBeInTheDocument();
      expect(document.querySelector(".drag-handle")).toBeInTheDocument();
      expect(document.querySelector(".place-actions")).toBeInTheDocument();
      expect(
        document.querySelector(".linked-policy-remove"),
      ).toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("does not render draft trip detail confirmation controls", async () => {
    const draftTrip: Trip = {
      ...getPreviewTrip(),
      id: "96",
      title: "Draft detail trip",
      status: "draft",
      currentUserRole: "owner",
      linkedPolicies: [
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "10,000원 할인",
          region: "경남",
        },
      ],
      days: {
        1: [
          {
            id: "p1",
            time: "09:00",
            label: "Editable beach",
            meta: "작성 중 장소",
          },
        ],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(draftTrip);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockRejectedValue(new Error("status update should not run"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/96");

      await waitFor(() =>
        expect(screen.getAllByText("Draft detail trip").length).toBeGreaterThan(
          0,
        ),
      );
      expect(
        screen.queryByRole("region", { name: "일정 확정 상태" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정하기" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정취소" }),
      ).not.toBeInTheDocument();
      expect(
        document.querySelector(".prototype-trip-action-add"),
      ).toBeInTheDocument();
      expect(document.querySelector(".drag-handle")).toBeInTheDocument();
      expect(document.querySelector(".place-actions")).toBeInTheDocument();
      expect(
        document.querySelector(".linked-policy-remove"),
      ).toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("does not show confirmation cancel controls for confirmed viewer trips", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "95",
      title: "Confirmed viewer trip",
      status: "confirmed",
      currentUserRole: "viewer",
      days: {
        1: [
          {
            id: "p1",
            time: "09:00",
            label: "Viewer locked place",
            meta: "읽기 전용",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateStatusSpy = vi
      .spyOn(appDataApi, "updateTripStatus")
      .mockResolvedValue({ ...trip, status: "draft" });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/95");

      await waitFor(() =>
        expect(
          screen.getAllByText("Confirmed viewer trip").length,
        ).toBeGreaterThan(0),
      );
      expect(
        screen.queryByRole("button", { name: "확정취소" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정하기" }),
      ).not.toBeInTheDocument();
      expect(updateStatusSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateStatusSpy.mockRestore();
    }
  });

  it("renders multiple saved trips on the trips list", async () => {
    const trips: Trip[] = [
      {
        ...getPreviewTrip(),
        id: "77",
        title: "부산 4일 여행",
        dates: "2026.06.15 - 06.18",
        participantCount: 1,
        people: ["나", "민수", "지윤", "현우"],
        days: { 1: [], 2: [], 3: [], 4: [] },
      },
      {
        ...getPreviewTrip(),
        id: "78",
        title: "경주 3일 여행",
        dates: "2026.07.01 - 07.03",
        days: { 1: [], 2: [], 3: [] },
      },
    ];
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue(trips);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips");

      await screen.findByText("부산 4일 여행");
      expect(screen.getByText("경주 3일 여행")).toBeInTheDocument();
      expect(document.querySelectorAll(".itinerary-card")).toHaveLength(2);
      expect(screen.getByText("4명 참여 중")).toBeInTheDocument();
      expect(screen.getByText("나, 민수 외 2명")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("실제");
      expect(getLink("/trips/77")).toBeInTheDocument();
      expect(getLink("/trips/78")).toBeInTheDocument();
    } finally {
      listTripsSpy.mockRestore();
    }
  });
});
