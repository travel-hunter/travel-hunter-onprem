import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, appDataApi, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

const jejuCatalog = {
  sido: "제주",
  sourceAsOf: "2026-09-03",
  wholeArea: {
    travelAreaId: "jeju-all",
    travelAreaName: "제주 전체",
    sido: "제주",
    areaType: "whole" as const,
    includedCities: ["제주", "서귀포"],
  },
  recommendedAreas: [
    {
      travelAreaId: "jeju-east",
      travelAreaName: "제주 동부",
      sido: "제주",
      areaType: "recommended" as const,
      includedCities: ["제주", "서귀포"],
    },
    {
      travelAreaId: "jeju-west",
      travelAreaName: "제주 서부",
      sido: "제주",
      areaType: "recommended" as const,
      includedCities: ["제주", "서귀포"],
    },
  ],
  administrativeAreas: [],
};

describe("Travel Hunter app trip edit", () => {
  it("prefills canonical DTO dates and saves settings without parsing display dates", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "91",
      title: "Canonical date trip",
      revision: 7,
      dates: "June 1 through June 3",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const updatedTrip: Trip = {
      ...trip,
      title: "Updated canonical trip",
      revision: 8,
      startDate: "2026-06-02",
      endDate: "2026-06-04",
      dates: "2026-06-02 ~ 2026-06-04",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    // 지역 선택기가 실제 백엔드를 치면 결과가 로컬 DB 상태에 휘둘린다.
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jejuCatalog);
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockResolvedValue(updatedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/91/edit");
      const user = userEvent.setup();

      const titleInput = await screen.findByRole("textbox", {
        name: "Trip title",
      });
      // 네이티브 date 입력은 없어졌다. 생성 화면과 같은 범위 달력을 쓴다.
      expect(screen.queryByLabelText("Start date")).toBeNull();
      expect(screen.queryByLabelText("End date")).toBeNull();
      expect(screen.getByTestId("trip-date-range-summary")).toHaveTextContent(
        "2026-06-01 ~ 2026-06-03",
      );

      await user.clear(titleInput);
      await user.type(titleInput, "Updated canonical trip");
      await user.click(screen.getByTestId("trip-date-range-trigger"));
      await user.click(screen.getByRole("button", { name: "2026-06-02" }));
      await user.click(screen.getByRole("button", { name: "2026-06-04" }));
      await user.click(screen.getByRole("button", { name: "완료" }));
      await user.click(document.querySelector('button[type="submit"]') as HTMLButtonElement);

      await waitFor(() =>
        expect(updateSettingsSpy).toHaveBeenCalledWith("91", {
          expectedRevision: 7,
          title: "Updated canonical trip",
          startDate: "2026-06-02",
          endDate: "2026-06-04",
          overflowPlaceStrategy: "moveToLastDay",
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("saves a reversed edit date range as a forward range instead of failing", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "92",
      title: "Reversed range trip",
      revision: 3,
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    // 지역 선택기가 실제 백엔드를 치면 결과가 로컬 DB 상태에 휘둘린다.
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jejuCatalog);
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockResolvedValue({ ...trip, revision: 4 });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/92/edit");
      const user = userEvent.setup();

      await user.click(await screen.findByTestId("trip-date-range-trigger"));
      // 끝날을 첫날보다 앞서 고른다. 달력이 정방향으로 되돌려야 한다.
      await user.click(screen.getByRole("button", { name: "2026-06-10" }));
      await user.click(screen.getByRole("button", { name: "2026-06-03" }));
      await user.click(screen.getByRole("button", { name: "완료" }));
      await user.click(
        document.querySelector('button[type="submit"]') as HTMLButtonElement,
      );

      await waitFor(() =>
        expect(updateSettingsSpy).toHaveBeenCalledWith("92", {
          expectedRevision: 3,
          title: trip.title,
          startDate: "2026-06-03",
          endDate: "2026-06-10",
          overflowPlaceStrategy: "moveToLastDay",
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("restores the saved travel area and saves a different one", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "93",
      title: "제주 동부 여행",
      revision: 5,
      region: "제주 동부",
      travelAreaId: "jeju-east",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jejuCatalog);
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockResolvedValue({ ...trip, revision: 6 });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/93/edit");
      const user = userEvent.setup();

      // 저장돼 있던 제주 동부가 되살아나 있어야 한다.
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /제주 동부/ }),
        ).toHaveAttribute("aria-pressed", "true"),
      );
      expect(catalogSpy).toHaveBeenCalledWith("제주");

      await user.click(screen.getByRole("button", { name: /제주 서부/ }));
      await user.click(
        document.querySelector('button[type="submit"]') as HTMLButtonElement,
      );

      await waitFor(() =>
        expect(updateSettingsSpy).toHaveBeenCalledWith("93", {
          expectedRevision: 5,
          title: "제주 동부 여행",
          travelAreaId: "jeju-west",
          startDate: "2026-06-01",
          endDate: "2026-06-03",
          overflowPlaceStrategy: "moveToLastDay",
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("asks before dropping linked policies that do not fit the new travel area", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "94",
      title: "제주 동부 여행",
      revision: 5,
      region: "제주 동부",
      travelAreaId: "jeju-east",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const catalogSpy = vi.spyOn(appDataApi, "getTravelAreaCatalog").mockResolvedValue(jejuCatalog);
    const rejection = new ApiError("Request failed", {
      status: 409,
      statusText: "Conflict",
      detail: {
        code: "trip_policies_outside_travel_area",
        message: "Trip has policies outside the new travel area",
        policies: [
          { slug: "seogwipo-stay", title: "[서귀포] 숙박 할인", hasApplicationProgress: false },
          { slug: "island-support", title: "섬 방문 지원", hasApplicationProgress: true },
        ],
      },
    });
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockRejectedValueOnce(rejection)
      .mockResolvedValueOnce({ ...trip, revision: 6 });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/94/edit");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(screen.getByRole("button", { name: /제주 동부/ })).toHaveAttribute("aria-pressed", "true"),
      );
      await user.click(screen.getByRole("button", { name: /제주 서부/ }));
      await user.click(document.querySelector('button[type="submit"]') as HTMLButtonElement);

      // 말없이 빼지 않는다 - 무엇이 빠지는지, 신청 기록이 같이 지워지는지 먼저 알린다
      const dialog = await screen.findByRole("alertdialog", { name: "지역과 맞지 않는 정책" });
      expect(dialog).toHaveTextContent("맞지 않는 정책 2건");
      expect(dialog).toHaveTextContent("[서귀포] 숙박 할인");
      expect(dialog).toHaveTextContent("섬 방문 지원 · 신청 진행 기록도 함께 지워져요");
      expect(updateSettingsSpy).toHaveBeenCalledTimes(1);
      expect(updateSettingsSpy.mock.calls[0][1]).not.toHaveProperty("mismatchedPolicyStrategy");

      await user.click(screen.getByRole("button", { name: "정책 빼고 저장" }));

      await waitFor(() => expect(updateSettingsSpy).toHaveBeenCalledTimes(2));
      expect(updateSettingsSpy.mock.calls[1][1]).toMatchObject({
        expectedRevision: 5,
        travelAreaId: "jeju-west",
        mismatchedPolicyStrategy: "remove",
      });
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("omits travelAreaId when the region was not touched", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "94",
      title: "제주 동부 여행",
      revision: 2,
      region: "제주 동부",
      travelAreaId: "jeju-east",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jejuCatalog);
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockResolvedValue({ ...trip, revision: 3 });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/94/edit");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /제주 동부/ }),
        ).toHaveAttribute("aria-pressed", "true"),
      );
      await user.click(
        document.querySelector('button[type="submit"]') as HTMLButtonElement,
      );

      await waitFor(() => expect(updateSettingsSpy).toHaveBeenCalled());
      // 복원만 하고 손대지 않았으면 지역은 보내지 않는다.
      expect(updateSettingsSpy.mock.calls[0][1]).not.toHaveProperty(
        "travelAreaId",
      );
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("keeps viewer trips read-only on the direct edit route", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "92",
      title: "Viewer trip",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      currentUserRole: "viewer",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jejuCatalog);
    const updateSettingsSpy = vi.spyOn(appDataApi, "updateTripSettings");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/92/edit");

      expect(await screen.findByText("편집 권한이 없는 일정입니다.")).toBeInTheDocument();
      expect(screen.queryByRole("form", { name: "일정 편집" })).not.toBeInTheDocument();
      expect(updateSettingsSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      catalogSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });
});
