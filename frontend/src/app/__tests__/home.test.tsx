import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type Policy,
  type RegionRecommendation,
  type Trip,
} from "../../api";
import { examplePolicyDetail, getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — home", () => {
  it("renders the vertical top-three weekly benefit list with real policy links", async () => {
    await login();
    cleanup();
    renderAppRoute("/home");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("이번 주 혜택"),
    );
    expect(document.body).toHaveTextContent("어디로 떠나세요?");
    expect(screen.getByLabelText("마이페이지")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("안녕,");
    expect(document.body).toHaveTextContent(
      "이번 주 놓치면 아쉬운 혜택이 있어요",
    );
    expect(document.body).toHaveTextContent("AI 추천 맞춤 일정");
    expect(document.body).not.toHaveTextContent("인기 국내 여행지");
    expect(document.body).not.toHaveTextContent("추천 혜택");
    const benefitList = screen.getByLabelText("이번 주 혜택 정책 목록");
    expect(benefitList).toBeInTheDocument();
    expect(benefitList).toHaveClass("prototype-home-policy-list");
    expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
    expect(document.querySelector(".ds-home-rail")).toBeNull();
    expect(document.body).not.toHaveTextContent("⭐ 4.9");
    await waitFor(() =>
      expect(screen.getByText("이번 주 인기 정책")).toBeInTheDocument(),
    );
    await waitFor(() => {
      const policyLinks = within(benefitList).getAllByRole("link");
      expect(policyLinks.length).toBeGreaterThan(0);
      expect(policyLinks.length).toBeLessThanOrEqual(3);
      expect(policyLinks[0]).toHaveClass("prototype-home-policy-card");
      expect(
        policyLinks[0].querySelector(".prototype-home-policy-summary"),
      ).toHaveTextContent(/\S/);
      expect(
        policyLinks[0].querySelector(".prototype-home-policy-condition"),
      ).toHaveTextContent(/^조건: \S/);
      expect(policyLinks[0].querySelector("small")).toHaveTextContent(/D-|상시|마감/);
      expect(policyLinks[0].querySelector("small")).not.toHaveTextContent("·");
      expect(
        within(policyLinks[0]).queryByRole("button", { name: /신청|공식/ }),
      ).toBeNull();
    });

    expect(benefitList).not.toHaveAttribute("data-dragging");
    expect(document.body).not.toHaveTextContent("이번 주 혜택은 최대 3개만 보여줘요");
    expect(screen.getByText("자세히 보기 →")).toBeInTheDocument();
  });

  it("shows safe concise condition labels on weekly benefit cards", async () => {
    const policies: Policy[] = [
      {
        ...examplePolicyDetail,
        id: "travelmonth-25",
        slug: "travelmonth-25",
        title: "[합천] 대한민국 반값여행 지원",
        region: "경남",
        deadline: "2026-07-31",
        amount: "최대 20만원 환급",
        summary: "숙박, 식사, 체험 환급 혜택",
        category: "지역할인",
        requirements: [
          "1660-3067",
          "지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역",
        ],
      },
      {
        ...examplePolicyDetail,
        id: "stay-discount-gangwon-goseong",
        slug: "stay-discount-gangwon-goseong",
        title: "[고성] 대한민국 숙박세일 페스타 숙박 할인",
        region: "강원",
        deadline: "2026-08-31",
        amount: "최대 7만원 할인",
        summary: "비수도권 숙박 할인 혜택",
        category: "숙박",
        requirements: [
          "7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)",
        ],
      },
      {
        ...examplePolicyDetail,
        id: "official-fallback-policy",
        slug: "official-fallback-policy",
        title: "청년 여행 지원",
        region: "서울",
        deadline: "2026-09-30",
        amount: "최대 5만원 지원",
        summary: "청년 대상 여행 지원",
        category: "여행상품",
        requirements: ["공식 혜택 안내에서 조건을 확인하세요.", "만 19세 이상 청년"],
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const benefitList = await screen.findByLabelText("이번 주 혜택 정책 목록");
      await waitFor(() =>
        expect(within(benefitList).getByText("[합천] 대한민국 반값여행 지원"))
          .toBeInTheDocument(),
      );
      expect(document.body).not.toHaveTextContent("조건: 1660-3067");
      expect(document.body).toHaveTextContent(
        "조건: 지정관광지 2개소 방문 인증사진 및 제로페이…",
      );
      expect(document.body).toHaveTextContent("조건: 7만원 미만 숙박 2만원 할인");
      expect(document.body).not.toHaveTextContent("조건: 공식 혜택 안내");
      expect(document.body).toHaveTextContent("조건: 만 19세 이상 청년");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("uses deadline order for weekly benefits when no recommended policy is present", async () => {
    const policies: Policy[] = [
      {
        ...examplePolicyDetail,
        id: "later-fourth",
        slug: "later-fourth",
        title: "네 번째 늦은 혜택",
        deadline: "2026-12-31",
      },
      {
        ...examplePolicyDetail,
        id: "soon-first",
        slug: "soon-first",
        title: "첫 번째 임박 혜택",
        deadline: "2026-07-01",
      },
      {
        ...examplePolicyDetail,
        id: "soon-third",
        slug: "soon-third",
        title: "세 번째 임박 혜택",
        deadline: "2026-07-03",
      },
      {
        ...examplePolicyDetail,
        id: "soon-second",
        slug: "soon-second",
        title: "두 번째 임박 혜택",
        deadline: "2026-07-02",
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const benefitList = await screen.findByLabelText("이번 주 혜택 정책 목록");
      await waitFor(() =>
        expect(within(benefitList).getAllByRole("link")).toHaveLength(3),
      );
      expect(within(benefitList).getByText("첫 번째 임박 혜택"))
        .toBeInTheDocument();
      expect(within(benefitList).getByText("두 번째 임박 혜택"))
        .toBeInTheDocument();
      expect(within(benefitList).getByText("세 번째 임박 혜택"))
        .toBeInTheDocument();
      expect(within(benefitList).queryByText("네 번째 늦은 혜택"))
        .not.toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("prioritizes strongly recommended weekly benefits before filling by deadline", async () => {
    const policies: Policy[] = [
      {
        ...examplePolicyDetail,
        id: "soon-first",
        slug: "soon-first",
        title: "첫 번째 임박 혜택",
        deadline: "2026-07-01",
        match: 72,
      },
      {
        ...examplePolicyDetail,
        id: "soon-second",
        slug: "soon-second",
        title: "두 번째 임박 혜택",
        deadline: "2026-07-02",
        match: 74,
      },
      {
        ...examplePolicyDetail,
        id: "soon-third",
        slug: "soon-third",
        title: "세 번째 임박 혜택",
        deadline: "2026-07-03",
        match: 76,
      },
      {
        ...examplePolicyDetail,
        id: "recommended-later",
        slug: "recommended-later",
        title: "추천 우선 혜택",
        deadline: "2026-12-31",
        match: 94,
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const benefitList = await screen.findByLabelText("이번 주 혜택 정책 목록");
      await waitFor(() =>
        expect(within(benefitList).getAllByRole("link")).toHaveLength(3),
      );
      const policyTitles = within(benefitList)
        .getAllByRole("link")
        .map((link) => link.querySelector("strong")?.textContent);
      expect(policyTitles).toEqual([
        "추천 우선 혜택",
        "첫 번째 임박 혜택",
        "두 번째 임박 혜택",
      ]);
      expect(within(benefitList).queryByText("세 번째 임박 혜택"))
        .not.toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("uses preferred-region recommendations only for the home AI trip cards", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산", "강원"],
      style: "맛집",
      budget: "40만원 이하",
    });
    const preferredRegionRecommendations: RegionRecommendation[] = [
      {
        region: "강원",
        title: "강원 미식 지원",
        reason: "맛집 혜택이 많고 마감 임박 정책이 있습니다.",
        policyCount: 7,
        endingSoonCount: 2,
        estimatedValueKrw: 50000,
        score: 12,
        styleMatchedCount: 3,
      },
      {
        region: "부산",
        title: "부산 로컬 혜택",
        reason: "맛집 취향과 연결되는 지역 혜택입니다.",
        policyCount: 5,
        endingSoonCount: 0,
        estimatedValueKrw: 30000,
        score: 9,
        styleMatchedCount: 2,
      },
    ];
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue(preferredRegionRecommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      await waitFor(() =>
        expect(listRegionRecommendationsSpy).toHaveBeenCalledWith({
          style: "맛집",
          preferredRegions: ["부산", "강원"],
          limit: 3,
        }),
      );
      expect(
        listRegionRecommendationsSpy,
      ).not.toHaveBeenCalledWith(expect.objectContaining({ region: "부산" }));
      expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
      expect(
        await screen.findByRole("link", { name: /부산 맛집 코스 만들기/ }),
      ).toHaveAttribute("href", "/trips/new?region=%EB%B6%80%EC%82%B0");
      expect(
        screen.getByRole("link", { name: /강원 맛집 코스 만들기/ }),
      ).toHaveAttribute("href", "/trips/new?region=%EA%B0%95%EC%9B%90");
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("uses a non-region fallback home AI trip card when preferred regions are unset", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: "맛집",
      budget: "40만원 이하",
    });
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue([]);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
      await waitFor(() =>
        expect(document.querySelector(".prototype-home-ai-card")).toBeTruthy(),
      );
      expect(listRegionRecommendationsSpy).not.toHaveBeenCalled();
      expect(document.querySelector(".prototype-home-ai-card")).toHaveAttribute(
        "href",
        "/trips/new",
      );
      expect(document.querySelector(".prototype-home-ai-card")).toHaveTextContent(
        "코스 만들기",
      );
      expect(document.querySelector(".prototype-home-ai-card")).not.toHaveTextContent(
        "부산",
      );
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("prompts once per session when required profile preferences are unset", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: null,
      budget: null,
    });

    try {
      window.sessionStorage.clear();
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();

      const dialog = await screen.findByRole("dialog", {
        name: "프로필 설정을 완료해 주세요",
      });
      expect(dialog).toHaveClass("profile-completion-dialog");
      expect(document.querySelector(".profile-completion-card")).toBeNull();
      expect(dialog).toHaveTextContent(
        "관심 지역, 여행 스타일, 예산을 설정하면 홈 추천이 더 정확해져요.",
      );
      expect(
        within(dialog).getByRole("link", { name: "설정하러 가기" }),
      ).toHaveAttribute("href", "/profile-setup?redirect=/home");

      await user.click(within(dialog).getByRole("button", { name: "나중에" }));
      await waitFor(() =>
        expect(
          screen.queryByRole("dialog", {
            name: "프로필 설정을 완료해 주세요",
          }),
        ).not.toBeInTheDocument(),
      );

      cleanup();
      renderAppRoute("/home");
      await waitFor(() =>
        expect(document.body).toHaveTextContent("이번 주 혜택"),
      );
      expect(
        screen.queryByRole("dialog", {
          name: "프로필 설정을 완료해 주세요",
        }),
      ).not.toBeInTheDocument();

      window.sessionStorage.clear();
      cleanup();
      renderAppRoute("/home");
      expect(
        await screen.findByRole("dialog", {
          name: "프로필 설정을 완료해 주세요",
        }),
      ).toBeInTheDocument();
    } finally {
      getProfileSpy.mockRestore();
      window.sessionStorage.clear();
    }
  });

  it("dismisses the profile prompt modal with close and backdrop for the current session", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: null,
      budget: null,
    });

    try {
      window.sessionStorage.clear();
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();

      const firstDialog = await screen.findByRole("dialog", {
        name: "프로필 설정을 완료해 주세요",
      });
      await user.click(
        within(firstDialog).getByRole("button", {
          name: "프로필 설정 안내 닫기",
        }),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("dialog", {
            name: "프로필 설정을 완료해 주세요",
          }),
        ).not.toBeInTheDocument(),
      );

      window.sessionStorage.clear();
      cleanup();
      renderAppRoute("/home");
      await screen.findByRole("dialog", {
        name: "프로필 설정을 완료해 주세요",
      });
      fireEvent.mouseDown(
        document.querySelector(".profile-completion-backdrop")!,
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("dialog", {
            name: "프로필 설정을 완료해 주세요",
          }),
        ).not.toBeInTheDocument(),
      );
    } finally {
      getProfileSpy.mockRestore();
      window.sessionStorage.clear();
    }
  });

  it("uses the generic fallback AI trip card instead of an existing trip when no preferred region is loaded", async () => {
    const existingTrip: Trip = {
      ...getPreviewTrip(),
      id: "300",
      title: "경주 야호",
      dates: "2026.05.18 - 05.20",
      expectedSaving: "30만원",
    };
    const regionRecommendations: RegionRecommendation[] = [
      {
        region: "부산",
        title: "부산 맛집 추천",
        reason: "맛집 혜택이 많고 마감 임박 정책이 있습니다.",
        policyCount: 5,
        endingSoonCount: 1,
        estimatedValueKrw: 70000,
        score: 10,
        styleMatchedCount: 2,
      },
    ];
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([existingTrip]);
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue(regionRecommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      await waitFor(() =>
        expect(listRegionRecommendationsSpy).toHaveBeenCalled(),
      );
      expect(listTripsSpy).not.toHaveBeenCalled();
      const aiCard = document.querySelector(
        ".prototype-home-ai-card",
      ) as HTMLAnchorElement | null;
      expect(aiCard).toBeTruthy();
      expect(aiCard).toHaveAttribute("href", "/trips/new");
      expect(aiCard).not.toHaveTextContent("부산");
      expect(aiCard).not.toHaveTextContent("경주 야호");
      expect(aiCard).not.toHaveTextContent("2026.05.18 - 05.20");
      expect(aiCard).not.toHaveTextContent("예상 절약 30만원");
    } finally {
      listTripsSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("shows only the single preferred region in the home AI trip card even when recommendations rank another region first", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산"],
      style: "맛집",
      budget: "40만원 이하",
    });
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue([
        {
          region: "서울",
          title: "서울 전시 추천",
          reason: "혜택 수가 더 많습니다.",
          policyCount: 8,
          endingSoonCount: 0,
          estimatedValueKrw: 90000,
          score: 25,
          styleMatchedCount: 0,
        },
      ]);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const aiCard = await screen.findByRole("link", {
        name: /부산 맛집 코스 만들기/,
      });
      expect(aiCard).toHaveAttribute(
        "href",
        "/trips/new?region=%EB%B6%80%EC%82%B0",
      );
      expect(aiCard).toHaveTextContent("부산 코스 만들까요?");
      expect(aiCard).not.toHaveTextContent("서울");
      expect(
        screen.queryByRole("group", { name: "관심지역 AI 추천 일정 카드" }),
      ).not.toBeInTheDocument();
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("renders preferred regions as a looping snap carousel in the home AI trip area", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산", "강원", "제주"],
      style: "자연",
      budget: "40만원 이하",
    });
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue([
        {
          region: "서울",
          title: "서울 인기 추천",
          reason: "관심지역 밖 후보입니다.",
          policyCount: 9,
          endingSoonCount: 1,
          estimatedValueKrw: 100000,
          score: 30,
          styleMatchedCount: 1,
        },
        {
          region: "강원",
          title: "강원 자연 추천",
          reason: "자연 취향과 연결되는 혜택입니다.",
          policyCount: 3,
          endingSoonCount: 2,
          estimatedValueKrw: 50000,
          score: 20,
          styleMatchedCount: 2,
        },
      ]);
    const user = userEvent.setup();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const carousel = await screen.findByRole("group", {
        name: "관심지역 AI 추천 일정 카드",
      });
      expect(
        within(carousel).getByRole("link", { name: /부산 자연 코스 만들기/ }),
      ).toHaveAttribute("href", "/trips/new?region=%EB%B6%80%EC%82%B0");
      expect(
        within(carousel).getByRole("link", { name: /강원 자연 코스 만들기/ }),
      ).toHaveAttribute("href", "/trips/new?region=%EA%B0%95%EC%9B%90");
      expect(
        within(carousel).getByRole("link", { name: /제주 자연 코스 만들기/ }),
      ).toHaveAttribute("href", "/trips/new?region=%EC%A0%9C%EC%A3%BC");
      expect(
        within(carousel).queryByRole("link", { name: /서울/ }),
      ).not.toBeInTheDocument();
      const slides = carousel.querySelectorAll(".prototype-home-ai-slide");
      expect(slides).toHaveLength(5);
      expect(slides[0]).toHaveAttribute("data-carousel-clone", "true");
      expect(
        within(slides[0] as HTMLElement).getByRole("link", { hidden: true }),
      ).toHaveAttribute("tabindex", "-1");
      expect(slides[4]).toHaveAttribute("data-carousel-clone", "true");
      expect(
        within(slides[4] as HTMLElement).getByRole("link", { hidden: true }),
      ).toHaveAttribute("tabindex", "-1");

      const next = within(carousel).getByRole("button", {
        name: "다음 관심지역 일정",
      });
      const previous = within(carousel).getByRole("button", {
        name: "이전 관심지역 일정",
      });

      expect(carousel).toHaveAttribute("data-active-region", "부산");
      await user.click(next);
      expect(carousel).toHaveAttribute("data-active-region", "강원");
      await user.click(next);
      expect(carousel).toHaveAttribute("data-active-region", "제주");
      await user.click(next);
      expect(carousel).toHaveAttribute("data-active-region", "부산");
      await user.click(previous);
      expect(carousel).toHaveAttribute("data-active-region", "제주");

      const viewport = carousel.querySelector(
        ".prototype-home-ai-carousel-viewport",
      ) as HTMLElement;
      fireEvent.pointerDown(viewport, { clientX: 20 });
      fireEvent.pointerUp(viewport, { clientX: 120 });
      expect(carousel).toHaveAttribute("data-active-region", "강원");
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("keeps the fallback AI trip card when region recommendations fail", async () => {
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockRejectedValue(new Error("recommendation API unavailable"));

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
      expect(await screen.findByText("AI 추천 맞춤 일정")).toBeInTheDocument();
      expect(document.querySelector(".prototype-home-ai-card")).toBeTruthy();
    } finally {
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("keeps the fallback AI trip card when region recommendations are empty", async () => {
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockResolvedValue([]);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
      expect(await screen.findByText("AI 추천 맞춤 일정")).toBeInTheDocument();
      expect(document.querySelector(".prototype-home-ai-card")).toBeTruthy();
    } finally {
      listRegionRecommendationsSpy.mockRestore();
    }
  });
});
