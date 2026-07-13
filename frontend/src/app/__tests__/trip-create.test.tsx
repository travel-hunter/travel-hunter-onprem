import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { appDataApi, type Trip } from "../../api";
import {
  examplePolicySlug,
  getBusanTravelAreaResponse,
  getGangneungTravelAreaResponse,
  getGangwonTravelAreaResponse,
  getGyeongjuTravelAreaResponse,
  getHapcheonTravelAreaResponse,
  getJejuTravelAreaResponse,
  getPreviewTrip,
  getSokchoTravelAreaResponse,
  getYeonggwangTravelAreaResponse,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — trip creation", () => {
  it("shows all 17 broad regions when choosing a new trip region", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getJejuTravelAreaResponse());

    try {
      renderAppRoute("/trips/new");

      for (const region of [
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
      ]) {
        expect(
          screen.getByRole("button", { name: region }),
        ).toBeInTheDocument();
      }
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("uses selected dates and opens an empty itinerary when creating a trip", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getJejuTravelAreaResponse());
    renderAppRoute(
      `/trips/new?policySlug=${encodeURIComponent(examplePolicySlug)}`,
    );
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "44",
      title: "부산 맛집 여행",
      dates: "2026.07.12 - 07.18",
      participantCount: 3,
      people: ["나"],
      days: {
        1: [],
        2: [],
        3: [],
        4: [],
        5: [],
        6: [],
        7: [],
      },
    };
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const addPolicySpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: "44",
        policyId: examplePolicySlug,
        added: true,
      });
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([createdTrip]);

    try {
      expect(
        screen.getByRole("heading", { name: "여행 지역 선택" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("선택한 정책을 새 일정에 연결할게요"),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /제주 전체/ })).toHaveClass(
          "active",
        ),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      expect(
        screen.getByRole("heading", { name: "여행 정보를 한 번에 확인해요" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "일정 제목" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "여행 기간" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "코스 취향" }),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /변경/ }));
      const styleDialog = screen.getByRole("dialog", {
        name: "코스 취향 선택",
      });
      expect(styleDialog).toBeInTheDocument();
      await user.click(
        within(styleDialog).getByRole("button", { name: "맛집" }),
      );
      expect(screen.getByText(/^취향 · /)).toBeInTheDocument();
      await user.click(
        within(styleDialog).getByRole("button", { name: "선택 완료" }),
      );
      await waitFor(() =>
        expect(screen.getByText("취향 · 맛집")).toBeInTheDocument(),
      );
      fireEvent.change(screen.getByLabelText("출발일"), {
        target: { value: "2026-07-12" },
      });
      fireEvent.change(screen.getByLabelText("도착일"), {
        target: { value: "2026-07-18" },
      });
      expect(
        screen.getByText(/2026\.07\.12.*2026\.07\.18.*7일/),
      ).toBeInTheDocument();
      expect(
        screen.queryByLabelText("여행 인원 선택"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText(/인원 ·/)).not.toBeInTheDocument();
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      expect((titleInput as HTMLInputElement).value).toMatch(/^.+ \d일 여행$/);
      await user.clear(titleInput);
      await user.type(titleInput, "부산 맛집 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "부산 맛집 여행",
            region: expect.any(String),
            style: expect.any(String),
            policySlug: examplePolicySlug,
            startDate: "2026-07-12",
            endDate: "2026-07-18",
          }),
        ),
      );
      expect(createTripSpy.mock.calls[0]?.[0]).not.toHaveProperty(
        "participantCount",
      );
      expect(
        await screen.findByRole("button", { name: "✨ 추천 일정만들기" }),
      ).toBeInTheDocument();
      expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
      expect(screen.queryByText("10:00")).not.toBeInTheDocument();
      expect(screen.queryByText("14:00")).not.toBeInTheDocument();
      expect(screen.queryByText("18:00")).not.toBeInTheDocument();

      cleanup();
      renderAppRoute("/trips");
      await waitFor(() =>
        expect(
          screen.getByRole("heading", { name: "부산 맛집 여행", level: 4 }),
        ).toBeInTheDocument(),
      );
      expect(screen.getByText("1명 참여 중")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("나");
    } finally {
      createTripSpy.mockRestore();
      addPolicySpy.mockRestore();
      getTripSpy.mockRestore();
      listTripsSpy.mockRestore();
      travelAreasSpy.mockRestore();
    }
  });

  it("does not ask for planned party size on the checkout step", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getJejuTravelAreaResponse());

    try {
      renderAppRoute("/trips/new");
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /제주 전체/ })).toHaveClass(
          "active",
        ),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));

      expect(
        screen.getByRole("heading", { name: "여행 기간" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByLabelText("여행 인원 선택"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "여행 인원 1명 줄이기" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "여행 인원 1명 늘리기" }),
      ).not.toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("uses the home recommendation region query when creating a trip", async () => {
    await login();
    cleanup();
    renderAppRoute("/trips/new?region=%EB%B6%80%EC%82%B0");
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "45",
      title: "부산 추천 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [],
        2: [],
        3: [],
      },
    };
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /부산/ })).toHaveClass(
          "active",
        ),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "부산 추천 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "부산 추천 여행",
            region: "부산 전체",
            travelAreaId: "busan-all",
          }),
        ),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("45"));
    } finally {
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("preselects a policy municipality region query when linking a policy to a new trip", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "50",
      title: "영광 반값여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getYeonggwangTravelAreaResponse());
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const addPolicySpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: "50",
        policyId: examplePolicySlug,
        added: true,
      });
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute(
        `/trips/new?policySlug=${encodeURIComponent(examplePolicySlug)}&region=${encodeURIComponent("영광")}&sido=${encodeURIComponent("전남")}`,
      );

      expect(
        await screen.findByRole("heading", {
          name: "여행 정보를 한 번에 확인해요",
        }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: "여행 지역 선택" }),
      ).not.toBeInTheDocument();
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "영광", sido: "전남" }),
      );
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "영광 반값여행");
      const createButton = screen.getByRole("button", {
        name: "확인하고 만들기",
      });
      await waitFor(() => expect(createButton).toBeEnabled());
      await user.click(createButton);

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "영광 반값여행",
            region: "영광",
            travelAreaId: "policy-region:%EC%A0%84%EB%82%A8:%EC%98%81%EA%B4%91",
            policySlug: examplePolicySlug,
          }),
        ),
      );
      expect(addPolicySpy).toHaveBeenCalledWith("50", examplePolicySlug);
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("50"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      addPolicySpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("preselects a fallback municipality card and broad sido from a direct region query", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "51",
      title: "합천 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getHapcheonTravelAreaResponse());
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute(`/trips/new?region=${encodeURIComponent("합천")}`);

      expect(await screen.findByRole("button", { name: /합천/ })).toHaveClass(
        "active",
      );
      expect(screen.getByRole("button", { name: "경남" })).toHaveClass(
        "active",
      );
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "합천" }),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "합천 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "합천 여행",
            region: "합천",
            travelAreaId: "policy-region:%EA%B2%BD%EB%82%A8:%ED%95%A9%EC%B2%9C",
          }),
        ),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("51"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("preselects a travelAreaId query travel-area when creating a trip", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "47",
      title: "속초 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValueOnce(getGangwonTravelAreaResponse())
      .mockResolvedValue(getBusanTravelAreaResponse());
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute("/trips/new?travelAreaId=gangwon-sokcho-goseong-yangyang");
      expect(
        await screen.findByRole("button", { name: /속초·고성·양양/ }),
      ).toHaveClass("active");
      await user.click(screen.getByRole("button", { name: "다음" }));
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            region: "속초·고성·양양",
            travelAreaId: "gangwon-sokcho-goseong-yangyang",
          }),
        ),
      );
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "gangwon-sokcho-goseong-yangyang" }),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("47"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("shows 강원 travel-area choices for the legacy region query", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGangwonTravelAreaResponse());

    try {
      renderAppRoute("/trips/new?region=%EA%B0%95%EC%9B%90");
      expect(
        await screen.findByRole("heading", { name: "강원 세부 지역 선택" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /속초·고성·양양/ }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /강릉·동해·삼척/ }),
      ).toBeInTheDocument();
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ sido: "강원" }),
      );
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("shows broad region selection first without course preference choices", async () => {
    await login();
    cleanup();

    renderAppRoute("/trips/new");

    expect(await screen.findByText("여행 지역 선택")).toBeInTheDocument();
    expect(screen.queryByText("코스 취향 선택")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /강원/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /전남/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /경남/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^강릉$/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^경주$/ }),
    ).not.toBeInTheDocument();
  });

  it("resolves the default primary region into a travel-area candidate", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getJejuTravelAreaResponse());

    try {
      renderAppRoute("/trips/new");

      expect(
        await screen.findByRole("button", { name: /제주 전체/ }),
      ).toHaveClass("active");
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ sido: "제주" }),
      );
      expect(screen.queryByText("코스 취향 선택")).not.toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("resolves a legacy city region query through travel-area search", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGyeongjuTravelAreaResponse());

    try {
      renderAppRoute("/trips/new?region=%EA%B2%BD%EC%A3%BC");

      expect(await screen.findByRole("button", { name: /경주/ })).toHaveClass(
        "active",
      );
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "경주" }),
      );
      expect(screen.queryByText("코스 취향 선택")).not.toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("resolves the legacy Sokcho region query from home destination links", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getSokchoTravelAreaResponse());

    try {
      renderAppRoute("/trips/new?region=%EC%86%8D%EC%B4%88");

      expect(
        await screen.findByRole("button", { name: /속초·고성·양양/ }),
      ).toHaveClass("active");
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "속초" }),
      );
      expect(screen.queryByText("코스 취향 선택")).not.toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("resolves the legacy Gangneung region query through travel-area search", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGangneungTravelAreaResponse());

    try {
      renderAppRoute("/trips/new?region=%EA%B0%95%EB%A6%89");

      expect(
        await screen.findByRole("button", { name: /강릉·동해·삼척/ }),
      ).toHaveClass("active");
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: "강릉" }),
      );
      expect(screen.queryByText("코스 취향 선택")).not.toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("asks course preference after a travel area is selected", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGangwonTravelAreaResponse());

    try {
      renderAppRoute("/trips/new?region=%EA%B0%95%EC%9B%90");

      await user.click(
        await screen.findByRole("button", { name: /속초·고성·양양/ }),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));

      expect(
        await screen.findByRole("heading", {
          name: "여행 정보를 한 번에 확인해요",
        }),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /변경/ }));
      const styleDialog = screen.getByRole("dialog", {
        name: "코스 취향 선택",
      });
      expect(styleDialog).toBeInTheDocument();
      expect(
        within(styleDialog).getByRole("button", { name: /맛집/ }),
      ).toBeInTheDocument();
      expect(
        within(styleDialog).getByRole("button", { name: /휴식/ }),
      ).toBeInTheDocument();
    } finally {
      travelAreasSpy.mockRestore();
    }
  });

  it("includes travelAreaId in the createTrip payload after selecting a travel-area card", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "48",
      title: "강원 권역 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGangwonTravelAreaResponse());
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute("/trips/new?region=%EA%B0%95%EC%9B%90");
      await user.click(
        await screen.findByRole("button", { name: /속초·고성·양양/ }),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "강원 권역 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "강원 권역 여행",
            region: "속초·고성·양양",
            travelAreaId: "gangwon-sokcho-goseong-yangyang",
          }),
        ),
      );
      expect(travelAreasSpy).toHaveBeenCalledWith(
        expect.objectContaining({ sido: "강원" }),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("48"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("clears a direct travelAreaId requirement when the user switches back to a normal region", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "49",
      title: "부산 일반 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockImplementation((options) => {
        if (options?.sido === "부산")
          return Promise.resolve(getBusanTravelAreaResponse());
        return Promise.resolve(getGangwonTravelAreaResponse());
      });
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute("/trips/new?travelAreaId=gangwon-sokcho-goseong-yangyang");
      expect(
        await screen.findByRole("button", { name: /속초·고성·양양/ }),
      ).toHaveClass("active");
      await user.click(screen.getByRole("button", { name: /부산/ }));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /부산 전체/ })).toHaveClass(
          "active",
        ),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      expect(
        screen.getByRole("heading", { name: "여행 정보를 한 번에 확인해요" }),
      ).toBeInTheDocument();
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "부산 일반 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() =>
        expect(createTripSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "부산 일반 여행",
            region: "부산 전체",
            travelAreaId: "busan-all",
          }),
        ),
      );
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("49"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("links normalized TravelMonth policy slugs when creating a trip", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "46",
      title: "공식 혜택 참고 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(createdTrip);
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getBusanTravelAreaResponse());
    const addPolicySpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: "46",
        policyId: "travelmonth-58",
        added: true,
      });
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(createdTrip);

    try {
      renderAppRoute(
        "/trips/new?policySlug=travelmonth-58&region=%EB%B6%80%EC%82%B0",
      );
      expect(
        screen.getByText("선택한 정책까지 일정에 연결할게요"),
      ).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("공식 수집 혜택");
      expect(
        await screen.findByRole("heading", {
          name: "여행 정보를 한 번에 확인해요",
        }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: "여행 지역 선택" }),
      ).not.toBeInTheDocument();
      expect(document.body).toHaveTextContent("연결 정책 · 선택한 정책");
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "공식 혜택 참고 여행");
      await user.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      await waitFor(() => expect(createTripSpy).toHaveBeenCalled());
      expect(createTripSpy.mock.calls[0][0]).toEqual(
        expect.objectContaining({ policySlug: "travelmonth-58" }),
      );
      expect(addPolicySpy).toHaveBeenCalledWith("46", "travelmonth-58");
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("46"));
    } finally {
      travelAreasSpy.mockRestore();
      createTripSpy.mockRestore();
      addPolicySpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("blocks trip creation until the inline title step is valid", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getJejuTravelAreaResponse());
    renderAppRoute("/trips/new");
    const user = userEvent.setup();
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockResolvedValue(getPreviewTrip());

    try {
      await user.click(screen.getByRole("button", { name: "다음" }));
      expect(
        screen.getByRole("heading", { name: "여행 정보를 한 번에 확인해요" }),
      ).toBeInTheDocument();
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      expect(
        screen.getByRole("button", { name: "확인하고 만들기" }),
      ).toBeDisabled();
      expect(createTripSpy).not.toHaveBeenCalled();
    } finally {
      createTripSpy.mockRestore();
      travelAreasSpy.mockRestore();
    }
  });

  it("shows generic creation copy and a longer wait hint while trip creation is pending", async () => {
    await login();
    cleanup();
    const user = userEvent.setup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getGangwonTravelAreaResponse());
    const createTripSpy = vi
      .spyOn(appDataApi, "createTrip")
      .mockReturnValue(new Promise(() => undefined));

    try {
      renderAppRoute("/trips/new?travelAreaId=gangwon-sokcho-goseong-yangyang");

      await waitFor(() =>
        expect(screen.getByRole("button", { name: "다음" })).toBeEnabled(),
      );
      await user.click(screen.getByRole("button", { name: "다음" }));
      fireEvent.click(screen.getByRole("button", { name: "확인하고 만들기" }));

      expect(
        screen.getByRole("button", { name: "일정 생성 중" }),
      ).toBeDisabled();
      expect(screen.getByText("새 일정을 만들고 있어요.")).toBeInTheDocument();

      await waitFor(
        () =>
          expect(
            screen.getByText(
              "조금만 더 기다려주세요. 응답이 늦으면 잠시 후 다시 시도할 수 있어요.",
            ),
          ).toBeInTheDocument(),
        {
          timeout: 7000,
        },
      );
      expect(createTripSpy).toHaveBeenCalled();
    } finally {
      createTripSpy.mockRestore();
      travelAreasSpy.mockRestore();
    }
  }, 10000);
});
