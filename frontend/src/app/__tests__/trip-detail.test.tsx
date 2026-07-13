import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type LinkedTripPolicy,
  type Recommendation,
  type Trip,
} from "../../api";
import { App } from "../App";
import { AppProviders } from "../AppRoot";
import {
  examplePolicyPath,
  examplePolicySlug,
  examplePolicyTitle,
  getPreviewTrip,
} from "../../test/fixtures";
import { installAppKakaoSdkMock } from "../../test/kakaoMock";
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — trip detail & itinerary", () => {
  it("renders itinerary detail day tabs from trip data", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 4일 여행",
      dates: "2026.06.15 - 06.18",
      expectedSaving: "0원",
      linkedPolicies: undefined as unknown as Trip["linkedPolicies"],
      days: { 1: [], 2: [], 3: [], 4: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");

      await waitFor(() =>
        expect(screen.getByText("Day 4")).toBeInTheDocument(),
      );
      expect(
        screen.queryByText("Travel Hunter itinerary"),
      ).not.toBeInTheDocument();
      expect(screen.getByText("🏝️")).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "친구 초대" }),
      ).not.toBeInTheDocument();
      const inviteLinks = screen.getAllByRole("link", { name: "+ 친구 초대" });
      expect(inviteLinks).toHaveLength(1);
      expect(inviteLinks[0]).toHaveAttribute(
        "href",
        "/friend-invite?tripId=55",
      );
      expect(
        screen.getByRole("region", { name: "연결된 정책" }),
      ).toBeInTheDocument();
      expect(document.querySelector(".benefit-banner")).toHaveAttribute(
        "href",
        "/policies",
      );
      expect(
        screen.getByRole("region", { name: "이 일정에 어울리는 정책" }),
      ).toBeInTheDocument();
      await userEvent.setup().click(screen.getByText("Day 4"));
      expect(document.body).toHaveTextContent("아직 표시할 장소가 없어요");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows the friend invite entry for editor trip members", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      currentUserRole: "editor",
      title: "편집자 참여 일정",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57");

      await waitFor(() =>
        expect(screen.getAllByText("편집자 참여 일정").length).toBeGreaterThan(0),
      );
      expect(screen.getByRole("link", { name: "+ 친구 초대" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("hides the friend invite entry for viewer trip members", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      currentUserRole: "viewer",
      title: "뷰어 참여 일정",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/58");

      await waitFor(() =>
        expect(screen.getAllByText("뷰어 참여 일정").length).toBeGreaterThan(0),
      );
      expect(screen.queryByRole("link", { name: "+ 친구 초대" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("keeps saved places reorderable after recommendation preview completion", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "122",
      revision: 12,
      title: "저장 후 정렬 여행",
      days: {
        1: [
          { id: "saved-1", time: "09:00", label: "첫 장소", meta: "오전" },
          { id: "saved-2", time: "10:00", label: "둘째 장소", meta: "오전" },
        ],
        2: [
          { id: "saved-3", time: "11:00", label: "다른 날 장소", meta: "점심" },
        ],
      },
      currentUserRole: "owner",
    };
    const reorderedTrip: Trip = {
      ...trip,
      revision: 13,
      days: {
        1: [trip.days[1][1], trip.days[1][0]],
        2: trip.days[2],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockResolvedValue(reorderedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/122?day=1");

      const firstHandle = await screen.findByRole("button", {
        name: "첫 장소 순서 이동",
      });
      expect(firstHandle).toBeEnabled();
      expect(
        screen.getByRole("button", { name: "둘째 장소 순서 이동" }),
      ).toBeEnabled();

      firstHandle.focus();
      fireEvent.keyDown(firstHandle, { key: "ArrowDown" });

      await waitFor(() => expect(movePlaceSpy).toHaveBeenCalledTimes(1));
      expect(movePlaceSpy).toHaveBeenCalledWith(
        "122",
        "saved-1",
        expect.objectContaining({
          dayNumber: 1,
          position: 2,
          expectedRevision: 12,
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });

  it("moves saved places across days by keyboard but hides reorder handles for viewers", async () => {
    const editorTrip: Trip = {
      ...getPreviewTrip(),
      id: "123",
      revision: 21,
      title: "저장 후 Day 이동 여행",
      days: {
        1: [
          { id: "saved-a", time: "09:00", label: "이동할 장소", meta: "오전" },
        ],
        2: [
          { id: "saved-b", time: "10:00", label: "도착 Day 장소", meta: "점심" },
        ],
      },
      currentUserRole: "editor",
    };
    const movedTrip: Trip = {
      ...editorTrip,
      revision: 22,
      days: {
        1: [],
        2: [editorTrip.days[2][0], editorTrip.days[1][0]],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(editorTrip);
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockResolvedValue(movedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/123?day=1");

      const moveHandle = await screen.findByRole("button", {
        name: "이동할 장소 순서 이동",
      });
      fireEvent.keyDown(moveHandle, { key: "ArrowRight", shiftKey: true });

      await waitFor(() => expect(movePlaceSpy).toHaveBeenCalledTimes(1));
      expect(movePlaceSpy).toHaveBeenCalledWith(
        "123",
        "saved-a",
        expect.objectContaining({
          dayNumber: 2,
          position: 2,
          expectedRevision: 21,
        }),
      );

      movePlaceSpy.mockClear();
      getTripSpy.mockResolvedValueOnce({
        ...editorTrip,
        id: "124",
        currentUserRole: "viewer",
      });
      cleanup();
      renderAppRoute("/trips/124?day=1");

      await waitFor(() =>
        expect(
          screen.getAllByText("저장 후 Day 이동 여행").length,
        ).toBeGreaterThan(0),
      );
      expect(
        screen.queryByRole("button", { name: "이동할 장소 순서 이동" }),
      ).not.toBeInTheDocument();
      expect(movePlaceSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });

  it("shows linked policies from the trip detail response", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "56",
      status: "draft",
      currentUserRole: "owner",
      title: "부산 정책 여행",
      linkedPolicies: [
        {
          slug: "busan-digital-nomad",
          title: "부산 워케이션 지원",
          amount: "최대 10만원",
          region: "부산",
        },
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "최대 30만원",
          region: "전국",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/56");

      await waitFor(() =>
        expect(screen.getByText("부산 워케이션 지원")).toBeInTheDocument(),
      );
      expect(screen.getByText(examplePolicyTitle)).toBeInTheDocument();
      expect(document.querySelectorAll(".benefit-banner")).toHaveLength(2);
      expect(getLink("/policies/busan-digital-nomad")).toBeInTheDocument();
      expect(getLink(examplePolicyPath)).toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: /연결 삭제/ })).toHaveLength(
        2,
      );
      expect(document.body).toHaveTextContent("최대 10만원 · 부산");
      expect(document.body).toHaveTextContent("최대 30만원 · 전국");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("removes a linked policy from a confirmed owner trip detail card", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "61",
      status: "confirmed",
      currentUserRole: "owner",
      title: "정책 삭제 여행",
      linkedPolicies: [
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "최대 30만원",
          region: "전국",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const removePolicySpy = vi
      .spyOn(appDataApi, "removePolicyFromTrip")
      .mockResolvedValue({
        tripId: "61",
        policyId: examplePolicySlug,
        added: false,
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/61");

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();

      await userEvent.setup().click(
        within(linkedRegion).getByRole("button", {
          name: `${examplePolicyTitle} 연결 삭제`,
        }),
      );

      await waitFor(() =>
        expect(removePolicySpy).toHaveBeenCalledWith("61", examplePolicySlug),
      );
      await waitFor(() =>
        expect(
          within(linkedRegion).queryByText(examplePolicyTitle),
        ).not.toBeInTheDocument(),
      );
      expect(
        within(linkedRegion).getByText("연결된 정책이 없어요"),
      ).toBeInTheDocument();
      expect(document.body).toHaveTextContent("정책 연결을 해제했어요.");
    } finally {
      getTripSpy.mockRestore();
      removePolicySpy.mockRestore();
    }
  });

  it("keeps a route-state linked policy hidden after removing it from trip detail", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "62",
      status: "draft",
      currentUserRole: "owner",
      title: "방금 연결한 정책 삭제 여행",
      linkedPolicies: [],
      days: { 1: [] },
    };
    const routePolicy: LinkedTripPolicy = {
      slug: examplePolicySlug,
      title: examplePolicyTitle,
      amount: "최대 30만원",
      region: "전국",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const removePolicySpy = vi
      .spyOn(appDataApi, "removePolicyFromTrip")
      .mockResolvedValue({
        tripId: "62",
        policyId: examplePolicySlug,
        added: false,
      });

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/62",
              state: { linkedPolicy: routePolicy },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정하기" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정취소" }),
      ).not.toBeInTheDocument();

      await userEvent.setup().click(
        within(linkedRegion).getByRole("button", {
          name: `${examplePolicyTitle} 연결 삭제`,
        }),
      );

      await waitFor(() =>
        expect(removePolicySpy).toHaveBeenCalledWith("62", examplePolicySlug),
      );
      await waitFor(() =>
        expect(
          within(linkedRegion).queryByText(examplePolicyTitle),
        ).not.toBeInTheDocument(),
      );
      expect(
        within(linkedRegion).getByText("연결된 정책이 없어요"),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      removePolicySpy.mockRestore();
    }
  });

  it("links trip detail recommended policy cards to policy detail pages", async () => {
    const recommendedPolicies: LinkedTripPolicy[] = [
      {
        slug: "busan-card-cashback",
        title: "부산 카드 캐시백",
        amount: "카드 결제 5% 캐시백",
        region: "부산",
      },
      {
        slug: "busan-stay-coupon",
        title: "부산 숙박 쿠폰",
        amount: "숙박비 3만원",
        region: "부산",
      },
      {
        slug: "busan-food-pass",
        title: "부산 미식 패스",
        amount: "식사권 할인",
        region: "부산",
      },
    ];
    const trip: Trip & { recommendedPolicies: LinkedTripPolicy[] } = {
      ...getPreviewTrip(),
      id: "59",
      title: "부산 추천 여행",
      linkedPolicies: [],
      recommendedPolicies,
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/59");

      const recommendedRegion = await screen.findByRole("region", {
        name: "이 일정에 어울리는 정책",
      });
      expect(
        within(recommendedRegion).getByRole("link", {
          name: /부산 카드 캐시백/,
        }),
      ).toHaveAttribute("href", "/policies/busan-card-cashback");
      expect(
        within(recommendedRegion).getByRole("link", { name: /부산 숙박 쿠폰/ }),
      ).toHaveAttribute("href", "/policies/busan-stay-coupon");
      expect(
        within(recommendedRegion).getByRole("link", { name: /부산 미식 패스/ }),
      ).toHaveAttribute("href", "/policies/busan-food-pass");
      expect(
        within(recommendedRegion).getByText("카드 결제 5% 캐시백"),
      ).toBeInTheDocument();
      expect(
        within(recommendedRegion).queryByText("KTX 청년 여행 할인"),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("uses a region empty state instead of the generic policy-list card when no recommended policy exists", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "60",
      title: "부산 추천 대기 여행",
      linkedPolicies: [],
      recommendedPolicies: [],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/60");

      const recommendedRegion = await screen.findByRole("region", {
        name: "이 일정에 어울리는 정책",
      });
      expect(
        within(recommendedRegion).queryByText(
          "이 일정에 맞는 정책을 더 찾아보세요",
        ),
      ).not.toBeInTheDocument();
      expect(
        within(recommendedRegion).getByText("이 일정에 어울리는 정책이 없어요"),
      ).toBeInTheDocument();
      expect(
        within(recommendedRegion).getByText("정책 확인"),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("puts the just-attached policy first when the trip already has linked policies", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      title: "부산 야호",
      expectedSaving: "30만원",
      linkedPolicies: [
        {
          slug: "busan-card-cashback",
          title: "부산 카드 캐시백",
          amount: "카드 결제 5% 캐시백",
          region: "부산",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/58",
              state: {
                linkedPolicy: {
                  slug: examplePolicySlug,
                  title: examplePolicyTitle,
                  amount: "최대 30만원",
                  region: "전국",
                },
              },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();
      expect(
        within(linkedRegion).getByText("부산 카드 캐시백"),
      ).toBeInTheDocument();
      const banners = document.querySelectorAll(".benefit-banner");
      expect(banners).toHaveLength(2);
      const links = linkedRegion.querySelectorAll(".linked-policy-card-main");
      expect(decodeURIComponent(links[0].getAttribute("href") ?? "")).toBe(
        decodeURIComponent(examplePolicyPath),
      );
      expect(links[1]).toHaveAttribute("href", "/policies/busan-card-cashback");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("keeps the just-attached policy visible when trip detail response is stale", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      title: "부산 야호",
      expectedSaving: "30만원",
      linkedPolicies: undefined as unknown as Trip["linkedPolicies"],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/57",
              state: {
                linkedPolicy: {
                  slug: examplePolicySlug,
                  title: examplePolicyTitle,
                  amount: "최대 30만원",
                  region: "전국",
                },
              },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      await waitFor(() =>
        expect(screen.getByText(examplePolicyTitle)).toBeInTheDocument(),
      );
      expect(
        decodeURIComponent(
          document
            .querySelector(".linked-policy-card-main")
            ?.getAttribute("href") ?? "",
        ),
      ).toBe(decodeURIComponent(examplePolicyPath));
      expect(document.body).toHaveTextContent("최대 30만원 · 전국");
      expect(
        screen.queryByText("연결된 정책이 없어요"),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows trip detail as a map-first itinerary without list/map tabs", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          { id: "1", time: "09:00", label: "성산 일출봉", meta: "자연·관광지" },
          { id: "2", time: "12:30", label: "해녀의 집", meta: "맛집·한식" },
        ],
        2: [{ id: "3", time: "10:00", label: "한림공원", meta: "자연·관광지" }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&place=1");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(screen.getByLabelText("Day 1 지도")).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("tablist", { name: /일정 표시 방식/ }),
      ).not.toBeInTheDocument();
      expect(document.querySelector("[data-kakao-map-view]")).toBeTruthy();
      expect(screen.getAllByText("성산 일출봉").length).toBeGreaterThan(0);
      expect(
        screen.getByRole("button", { name: "1번 장소: 성산 일출봉" }),
      ).toBeInTheDocument();
      expect(screen.queryByText("장소 카드의 이동 핸들로 순서를 조정할 수 있어요")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Day 2/ })).toBeInTheDocument();
      expect(
        screen.getByRole("dialog", { name: "성산 일출봉 지도 상세" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /길찾기/ })).toHaveAttribute(
        "href",
        "https://map.kakao.com/link/search/%EC%84%B1%EC%82%B0%20%EC%9D%BC%EC%B6%9C%EB%B4%89",
      );

      await user.click(
        screen.getByRole("button", { name: "2번 장소: 해녀의 집" }),
      );
      expect(
        screen.getByRole("dialog", { name: "해녀의 집 지도 상세" }),
      ).toBeInTheDocument();

      await user.click(screen.getByText("Day 2"));
      await waitFor(() =>
        expect(screen.getByLabelText("Day 2 지도")).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("dialog", { name: "해녀의 집 지도 상세" }),
      ).not.toBeInTheDocument();
      expect(screen.getAllByText("한림공원").length).toBeGreaterThan(0);
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("opens an inspectable place detail dialog from the map bottom sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "성산 일출봉",
            meta: "일출 보기 좋은 자연 명소",
            address: "제주 서귀포시 성산읍 성산리 1",
            latitude: 33.458,
            longitude: 126.942,
            category: "관광명소",
            categoryCode: "AT4",
            placeUrl: "https://place.map.kakao.com/123",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map&place=1");
      const user = userEvent.setup();

      await screen.findByRole("dialog", { name: "성산 일출봉 지도 상세" });
      await user.click(screen.getByRole("button", { name: "상세 보기" }));

      const detailDialog = await screen.findByRole("dialog", {
        name: "성산 일출봉 장소 상세",
      });
      expect(within(detailDialog).getByText("Day 1")).toBeInTheDocument();
      expect(within(detailDialog).getByText("09:00")).toBeInTheDocument();
      expect(within(detailDialog).getByText("관광명소")).toBeInTheDocument();
      expect(
        within(detailDialog).getByText("제주 서귀포시 성산읍 성산리 1"),
      ).toBeInTheDocument();
      expect(
        within(detailDialog).getByText("일출 보기 좋은 자연 명소"),
      ).toBeInTheDocument();
      expect(within(detailDialog).getByText("33.458, 126.942")).toBeInTheDocument();
      expect(within(detailDialog).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute(
        "href",
        "https://place.map.kakao.com/123",
      );
      expect(screen.queryByText("장소 상세 보기는 준비 중이에요.")).not.toBeInTheDocument();

      await user.click(within(detailDialog).getByRole("button", { name: "닫기" }));
      expect(
        screen.queryByRole("dialog", { name: "성산 일출봉 장소 상세" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("renders a trip detail coordinate-less Kakao map through the shared query fallback", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const expectedQuery = "부산 중구 자갈치해안로 52";
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "부산 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          {
            id: "missing-coordinate-place",
            time: "10:00",
            label: "자갈치시장",
            meta: "시장·맛집",
            address: expectedQuery,
            latitude: null,
            longitude: null,
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map");

      await waitFor(() =>
        expect(kakao.addressSearch).toHaveBeenCalledWith(
          expectedQuery,
          expect.any(Function),
        ),
      );
      await waitFor(() =>
        expect(kakao.keywordSearch).toHaveBeenCalledWith(
          expectedQuery,
          expect.any(Function),
        ),
      );
      expect(kakao.addressQueries).toEqual([expectedQuery]);
      expect(kakao.keywordQueries).toEqual([expectedQuery]);
      expect(kakao.addressSearch.mock.invocationCallOrder[0]).toBeLessThan(
        kakao.keywordSearch.mock.invocationCallOrder[0],
      );
      await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
      expect(kakao.markerInstances).toHaveLength(1);
      expect(kakao.customOverlayInstances).toHaveLength(1);
      expect(kakao.customOverlayInstances[0].options.content).toHaveTextContent(
        "자갈치시장",
      );
      expect(
        screen.queryByRole("button", { name: "1번 장소: 자갈치시장" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      vi.unstubAllEnvs();
      delete window.kakao;
    }
  });

  it("uses stored Kakao place URL and address in the trip map detail sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      days: {
        1: [
          {
            id: "1",
            time: "13:00",
            label: "Kakao food place",
            meta: "Food · Busan",
            address: "Busan road 1",
            latitude: 35.1,
            longitude: 129.1,
            category: "Food",
            categoryCode: "FD6",
            placeUrl: "http://place.map.kakao.com/12345",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map&place=1");

      await waitFor(() =>
        expect(
          screen.getByRole("dialog", { name: "Kakao food place 지도 상세" }),
        ).toBeInTheDocument(),
      );
      expect(screen.getByText("Busan road 1")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /길찾기/ })).toHaveAttribute(
        "href",
        "http://place.map.kakao.com/12345",
      );
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows empty trip detail with policy actions, day tabs, map, and no itinerary list", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "101",
      title: "제주 3일 여행",
      days: { 1: [], 2: [], 3: [] },
      linkedPolicies: [],
      recommendedPolicies: [
        { slug: examplePolicySlug, title: examplePolicyTitle, amount: "최대 20만원", region: "전남" },
      ],
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/101");

      await waitFor(() => expect(screen.getAllByText("제주 3일 여행").length).toBeGreaterThan(0));
      expect(screen.getByRole("button", { name: /장소 추가/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /추천 일정만들기/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Day 1/ })).toBeInTheDocument();
      expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
      expect(screen.queryByText("Day 1 일정")).not.toBeInTheDocument();
      expect(screen.queryByRole("tablist", { name: /일정 표시 방식/ })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("places trip edit actions between the map and day selector", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "103",
      title: "지도 아래 액션 여행",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/103");

      await waitFor(() => expect(screen.getAllByText("지도 아래 액션 여행").length).toBeGreaterThan(0));
      const mapPanel = document.querySelector(".prototype-map-wrap");
      const editActions = screen.getByRole("region", { name: "일정 편집 작업" });
      const daySelector = screen.getByLabelText("일정 날짜 선택");

      expect(mapPanel).not.toBeNull();
      expect((mapPanel as HTMLElement).compareDocumentPosition(editActions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(editActions.compareDocumentPosition(daySelector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows unsaved recommendation preview cards in the timeline before save", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "102",
      revision: 4,
      title: "추천 미리보기 여행",
      days: { 1: [{ id: "existing-p1", time: "09:00", label: "기존 장소", meta: "제주 제주시" }], 2: [] },
    };
    const savedTrip: Trip = {
      ...trip,
      revision: 5,
      days: { 1: [trip.days[1][0], { id: "p1", time: "10:00", label: "성산일출봉", meta: "제주 서귀포시" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/102?day=1&place=stale-saved-place");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "추천 후보 편집" })).not.toBeInTheDocument();
      expect(screen.getAllByText("성산일출봉").length).toBeGreaterThan(0);
      expect(screen.getByText("추천 후보")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 제외" })).toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 메모")).not.toBeInTheDocument();
      expect(screen.getAllByText("10:00").length).toBeGreaterThan(0);
      const candidateMeta = document.querySelector(".recommendation-preview-meta");
      expect(candidateMeta).toHaveTextContent("10:00");
      expect(candidateMeta).toHaveTextContent("추천 후보");
      expect(candidateMeta).toHaveTextContent("오전 일정");
      expect(candidateMeta?.querySelector(".preview-candidate-index")).toHaveTextContent("추천 후보");
      expect(candidateMeta?.querySelector(".preview-phase-label")).toHaveTextContent("오전 일정");
      expect(document.querySelector('[aria-label="기존 장소 시간 수정"]')).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "1번 장소: 기존 장소" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "1번 장소: 성산일출봉" })).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: "성산일출봉 지도에서 보기" }));

      expect(screen.getByRole("button", { name: "1번 장소: 성산일출봉" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "1번 장소: 기존 장소" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "2번 장소: 성산일출봉" })).not.toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "성산일출봉 지도 상세" })).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: /Day 2/ }));
      expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /Day 1/ }));
      expect(screen.queryByRole("button", { name: "1번 장소: 성산일출봉" })).not.toBeInTheDocument();

      screen.getByRole("button", { name: "성산일출봉 지도에서 보기" }).focus();
      await user.keyboard("{Enter}");
      expect(screen.getByRole("button", { name: "1번 장소: 성산일출봉" })).toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: "성산일출봉 후보 저장" }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toHaveTextContent("저장됨");
      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("102", 1, expect.objectContaining({ label: "성산일출봉", time: "10:00", meta: "관광명소", category: "관광명소", categoryCode: "AT4", expectedRevision: 4 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      await waitFor(() => expect(screen.queryByRole("button", { name: "성산일출봉 후보 저장" })).not.toBeInTheDocument());
      expect(screen.queryByText("추천 후보")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("persists existing place time edits on completion even without selected candidates", async () => {
    const existingPlace = { id: "existing-time-1", time: "09:00", label: "기존 장소", meta: "제주 제주시" };
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "121",
      revision: 8,
      title: "기존 시간 수정 여행",
      days: { 1: [existingPlace], 2: [] },
    };
    const updatedTrip: Trip = {
      ...trip,
      revision: 9,
      days: { 1: [{ ...existingPlace, time: "10:00" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ]);
    const updatePlaceSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue(updatedTrip);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(updatedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/121");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      await screen.findByRole("button", { name: "1번 장소: 기존 장소" });
      const existingTimeEdit = document.querySelectorAll(".preview-time-edit")[0] as HTMLElement;
      await user.click(within(existingTimeEdit).getByText("수정"));
      await user.click(within(existingTimeEdit).getByRole("button", { name: "방문 시간 1시간 증가" }));
      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(updatePlaceSpy).toHaveBeenCalledTimes(1));
      expect(updatePlaceSpy).toHaveBeenCalledWith("121", "existing-time-1", expect.objectContaining({ time: "10:00", expectedRevision: 8 }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      expect(screen.queryByText("추천 후보")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      updatePlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("assigns category-based times to recommendation preview cards", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "112", revision: 1, title: "추천 시간 여행", days: { 1: [], 2: [] } };
    const recommendations: Recommendation[] = [
      { id: "attraction-1", title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "attraction-2", title: "한라산", label: "⛰️", meta: "제주", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "food-1", title: "해녀의 집", label: "🍽️", meta: "해산물", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "cafe-1", title: "오션 카페", label: "☕", meta: "디저트", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "stay-1", title: "제주 숙소", label: "🏨", meta: "숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "explicit-1", title: "노을 산책", label: "🌅", meta: "18:30 노을 명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/112");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect((await screen.findAllByText("성산일출봉")).length).toBeGreaterThan(0);
      expect(screen.getAllByText("10:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("11:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("12:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("15:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("17:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("18:30").length).toBeGreaterThan(0);
      expect(screen.getAllByText("오전 일정").length).toBeGreaterThan(0);
      expect(screen.getByText("점심")).toBeInTheDocument();
      expect(screen.getAllByText("카페").length).toBeGreaterThan(0);
      expect(screen.getAllByText("숙소").length).toBeGreaterThan(0);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("orders recommendation preview cards by assigned visit time without moving saved places", async () => {
    const existingPlace = { id: "existing-ordered", time: "09:00", label: "기존 장소", meta: "기존 동선" };
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "113",
      revision: 1,
      title: "추천 정렬 여행",
      days: { 1: [existingPlace], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "lunch", title: "점심 식당", label: "🍽️", meta: "12:00 음식점", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "early-cafe", title: "이른 카페", label: "☕", meta: "13:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "stay", title: "숙소 체크인", label: "🏨", meta: "17:00 숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "walk", title: "오후 산책", label: "🌳", meta: "14:00 관광명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "late-cafe", title: "오후 카페", label: "☕", meta: "15:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/113");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "1번 장소: 기존 장소" })).toBeInTheDocument();
      expect(screen.getAllByText("기존 장소").length).toBeGreaterThan(0);
      const previewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) => button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""));
      expect(previewOrder).toEqual(["점심 식당", "이른 카페", "오후 산책", "오후 카페", "숙소 체크인"]);
      expect(screen.getByText("오후 일정")).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("orders same-time recommendation preview cards by category before original response order", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "114", revision: 1, title: "추천 동시간 여행", days: { 1: [], 2: [] } };
    const recommendations: Recommendation[] = [
      { id: "stay-same", title: "동시간 숙소", label: "🏨", meta: "13:00 숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "cafe-same", title: "동시간 카페", label: "☕", meta: "13:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "food-same", title: "동시간 식당", label: "🍽️", meta: "13:00 음식점", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "attraction-same", title: "동시간 명소", label: "📍", meta: "13:00 관광명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/114");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect((await screen.findAllByText("동시간 명소")).length).toBeGreaterThan(0);
      const previewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) => button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""));
      expect(previewOrder).toEqual(["동시간 명소", "동시간 식당", "동시간 카페", "동시간 숙소"]);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("cancels recommendation preview cards before saving", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "103", revision: 7, title: "추천 삭제 여행", days: { 1: [], 2: [] } };
    const savedTrip: Trip = {
      ...trip,
      revision: 8,
      days: { 1: [{ id: "p2", time: "10:00", label: "협재해변", meta: "바다" }], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "r1", title: "성산일출봉", label: "⛰️", meta: "산", reason: "추천", suggestedDay: 1 },
      { id: "r2", title: "협재해변", label: "🌊", meta: "바다", reason: "추천", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/103");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("성산일출봉").length).toBeGreaterThan(0);
      expect(screen.getAllByText("협재해변").length).toBeGreaterThan(0);
      expect(screen.getAllByText("추천 후보")).toHaveLength(2);
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "협재해변 후보 제외" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "성산일출봉 후보 제외" }));

      expect(screen.queryByText("성산일출봉")).not.toBeInTheDocument();
      expect(screen.getAllByText("협재해변").length).toBeGreaterThan(0);

      await user.click(screen.getByRole("button", { name: "미리보기 취소" }));

      expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("appends preview candidates to the target day when moved by keyboard", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "125",
      revision: 1,
      title: "키보드 후보 이동 여행",
      days: { 1: [], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "move", title: "옮길 후보", label: "📍", meta: "이동", reason: "추천", suggestedDay: 1 },
      { id: "target-a", title: "도착 후보 A", label: "📍", meta: "도착", reason: "추천", suggestedDay: 2 },
      { id: "target-b", title: "도착 후보 B", label: "📍", meta: "도착", reason: "추천", suggestedDay: 2 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi
      .spyOn(appDataApi, "listRecommendations")
      .mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/125?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      const moveHandle = await screen.findByRole("button", {
        name: "옮길 후보 순서 이동",
      });
      fireEvent.keyDown(moveHandle, { key: "ArrowRight", shiftKey: true });

      await waitFor(() =>
        expect(screen.getByRole("button", { name: /Day 2/ })).toHaveClass(
          "active",
        ),
      );
      const dayTwoPreviewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) =>
          button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""),
        );
      expect(dayTwoPreviewOrder).toEqual([
        "도착 후보 A",
        "도착 후보 B",
        "옮길 후보",
      ]);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("adds an individual recommendation preview candidate while preserving existing places", async () => {
    const existingPlace = { id: "old-1", time: "09:00", label: "이미 저장된 장소", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "104", revision: 10, title: "부분 추가 여행", days: { 1: [existingPlace], 2: [] } };
    const savedTrip: Trip = {
      ...trip,
      revision: 11,
      days: { 1: [existingPlace, { id: "new-1", time: "09:00", label: "오설록", meta: "차" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "tea", title: "오설록", label: "☕", meta: "차", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/104");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("button", { name: /기존 유지하고 추가|추천 일정 추가하기|이 일정으로 저장|추천으로 대체/ })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "미리보기 취소" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "전체 저장" })).toBeInTheDocument();

      await user.click(await screen.findByRole("button", { name: "오설록 후보 저장" }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "오설록 후보 저장" })).toHaveTextContent("저장됨");
      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      expect(addPlaceSpy).toHaveBeenCalledWith("104", 1, expect.objectContaining({ label: "오설록", expectedRevision: 10 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
      deletePlaceSpy.mockRestore();
    }
  });

  it("saves all recommendation preview candidates without deleting existing places", async () => {
    const existingPlace = { id: "old-2", time: "09:00", label: "기존 식당", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "105", revision: 20, title: "전체 저장 여행", days: { 1: [existingPlace], 2: [] } };
    const afterAddTrip: Trip = {
      ...trip,
      revision: 21,
      days: { 1: [existingPlace, { id: "new-2", time: "10:00", label: "새 추천", meta: "추천" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "new", title: "새 추천", label: "📍", meta: "추천", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(afterAddTrip);
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/105");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(await screen.findByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("105", 1, expect.objectContaining({ label: "새 추천", expectedRevision: 20 }));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: "새 추천 후보 저장" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "전체 저장" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      deletePlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("refreshes on recommendation preview 409 and preserves hidden candidates for global retry", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "106", revision: 30, title: "추천 충돌 여행", days: { 1: [], 2: [] } };
    const latestTrip: Trip = { ...trip, revision: 31 };
    const savedTrip: Trip = { ...latestTrip, revision: 32, days: { 1: [{ id: "p3", time: "09:00", label: "우도", meta: "섬" }], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(latestTrip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "udo", title: "우도", label: "🌊", meta: "섬", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockRejectedValueOnce(new ApiError("conflict", { status: 409, statusText: "Conflict" }))
      .mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/106");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("우도").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "우도 후보 저장" })).toBeInTheDocument();
      expect(screen.queryByLabelText("우도 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("우도 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("우도 메모")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "우도 후보 저장" }));
      await user.click(screen.getByRole("button", { name: "완료" }));

      expect(await screen.findByText(/다른 사용자가 먼저 일정을 수정/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "우도 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(2));
      expect(addPlaceSpy).toHaveBeenLastCalledWith("106", 1, expect.objectContaining({ label: "우도", time: "10:00", meta: "섬", expectedRevision: 31 }));
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not retry transient recommendation preview save automatically and preserves hidden candidates for manual retry", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "107", revision: 40, title: "추천 재시도 여행", days: { 1: [], 2: [] } };
    const savedTrip: Trip = { ...trip, revision: 41, days: { 1: [{ id: "p4", time: "09:00", label: "동백정원", meta: "꽃" }], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "garden", title: "동백정원", label: "🌺", meta: "꽃", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockRejectedValueOnce(new Error("temporary network")).mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/107");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("동백정원").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "동백정원 후보 저장" })).toBeInTheDocument();
      expect(screen.queryByLabelText("동백정원 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("동백정원 메모")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "동백정원 후보 저장" }));
      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "동백정원 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "완료" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(2));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(1, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(2, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("keeps only unsaved recommendation preview candidates after a partial save failure", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "108", revision: 50, title: "부분 실패 여행", days: { 1: [], 2: [] } };
    const afterFirstSave: Trip = {
      ...trip,
      revision: 51,
      days: { 1: [{ id: "saved-tea", time: "09:00", label: "오설록", meta: "차" }], 2: [] },
    };
    const afterRetrySave: Trip = {
      ...trip,
      revision: 52,
      days: {
        1: [{ id: "saved-tea", time: "09:00", label: "오설록", meta: "차" }],
        2: [{ id: "saved-mountain", time: "09:00", label: "한라산", meta: "산" }],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockResolvedValueOnce(afterFirstSave)
      .mockResolvedValue(afterFirstSave);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "tea", title: "오설록", label: "☕", meta: "차", reason: "추천", suggestedDay: 1 },
      { id: "mountain", title: "한라산", label: "⛰️", meta: "산", reason: "추천", suggestedDay: 2 },
    ]);
    let mountainAttempts = 0;
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, payload) => {
      if (payload.label === "오설록") return afterFirstSave;
      if (payload.label === "한라산") {
        mountainAttempts += 1;
        if (mountainAttempts === 1) throw new Error("temporary network");
        return afterRetrySave;
      }
      throw new Error(`Unexpected place ${payload.label}`);
    });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/108");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      await waitFor(() => expect(screen.queryByRole("button", { name: "오설록 후보 제외" })).not.toBeInTheDocument());
      expect(screen.queryByLabelText("한라산 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Day 2 06.13 후보 1개" })).not.toBeInTheDocument();
      expect(screen.queryByText("후보 1")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /Day 2 06.13/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("한라산").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "한라산 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(screen.queryByRole("button", { name: "한라산 후보 저장" })).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: /기존 유지하고 추가|추천 일정 추가하기|이 일정으로 저장|추천으로 대체/ })).not.toBeInTheDocument();
      expect(addPlaceSpy.mock.calls.map((call) => call[2].label)).toEqual(["오설록", "한라산", "한라산"]);
      expect(addPlaceSpy).toHaveBeenLastCalledWith("108", 2, expect.objectContaining({ label: "한라산", expectedRevision: 51 }));
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not delete existing places when full-save preview candidates fail", async () => {
    const existingPlace = { id: "old-3", time: "09:00", label: "기존 장소", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "111", revision: 90, title: "안전 대체 여행", days: { 1: [existingPlace], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(trip).mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "new-safe", title: "새 안전 추천", label: "📍", meta: "추천", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockRejectedValueOnce(new Error("temporary network"));
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/111");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      expect(screen.queryByLabelText("새 안전 추천 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("새 안전 추천").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "새 안전 추천 후보 저장" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
      deletePlaceSpy.mockRestore();
    }
  });

});
