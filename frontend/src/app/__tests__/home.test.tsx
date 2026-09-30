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
  appDataApi,
  type Policy,
  type RegionRecommendation,
  type Trip,
} from "../../api";
import {
  examplePolicyDetail,
  getPreviewTrip,
  testIsoDateFromToday,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

function policy(overrides: Partial<Policy> & Pick<Policy, "id" | "title">): Policy {
  return { ...examplePolicyDetail, slug: overrides.id, ...overrides };
}

/* 앱 경로 시험은 공용 로컬 백엔드 계정을 쓴다. 관심 지역이 남아 있으면 줄이 그 지역으로 좁혀지므로 비운다. */
function withoutPreferredRegions() {
  return vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
    preferredRegions: null,
    style: "휴식",
    budget: "30만원",
  } as Awaited<ReturnType<typeof appDataApi.getProfile>>);
}

describe("Travel Hunter app — home", () => {
  it("renders the deadline row, region cards, and trip entry from real policies", async () => {
    await login();
    cleanup();
    renderAppRoute("/home");

    const deadlineSection = await screen.findByRole("region", {
      name: /내 관심 지역 혜택|마감 임박 혜택/,
    });
    expect(document.body).toHaveTextContent("어디로 떠나세요?");
    expect(screen.getByLabelText("마이페이지")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("안녕,");
    expect(document.body).toHaveTextContent(/지금 받을 수 있는 혜택 \d+건/);
    expect(document.body).not.toHaveTextContent("이번 주 놓치면 아쉬운 혜택이 있어요");
    expect(document.body).not.toHaveTextContent("인기 국내 여행지");
    expect(document.querySelector(".ds-home-rail")).toBeNull();
    expect(screen.queryByText("이번 주 인기 정책")).toBeNull();

    const cards = within(deadlineSection).getAllByRole("link").filter((link) =>
      link.classList.contains("home-deadline-card"),
    );
    expect(cards.length).toBeGreaterThan(0);
    expect(cards.length).toBeLessThanOrEqual(6);
    expect(cards[0].getAttribute("href")).toMatch(/^\/policies\/.+/);
    expect(cards[0].querySelector(".home-deadline-badge")).toHaveTextContent(/D-|상시|마감/);
    expect(cards[0].querySelector(".home-deadline-where")).toHaveTextContent(/\S/);
    // 조건 줄·'상세 보기' 꼬리는 카드에서 뺐다 - 상세 화면의 몫이다
    expect(cards[0]).not.toHaveTextContent("조건:");
    expect(cards[0]).not.toHaveTextContent("상세 보기");

    const regionSection = screen.getByRole("region", { name: "혜택이 많은 지역" });
    expect(within(regionSection).getByRole("link", { name: /지도로 보기/ })).toHaveAttribute(
      "href",
      "/policies",
    );
    const regionLinks = within(regionSection)
      .getAllByRole("link")
      .filter((link) => link.classList.contains("home-region-card"));
    expect(regionLinks.length).toBeGreaterThan(0);
    expect(regionLinks[0].getAttribute("href")).toMatch(/^\/policies\?place=.+&sheet=1$/);
  });

  it("folds places of the same program into one deadline card, soonest first", async () => {
    const policies: Policy[] = [
      policy({
        id: "halfprice-yeonggwang",
        title: "[영광] 대한민국 반값여행 지원",
        region: "전남",
        deadline: testIsoDateFromToday(90),
        cardSummary: "최대 20만원 환급",
      }),
      policy({
        id: "halfprice-hapcheon",
        title: "[합천] 대한민국 반값여행 지원",
        region: "경남",
        deadline: testIsoDateFromToday(60),
        cardSummary: "최대 20만원 환급",
      }),
      policy({
        id: "halfprice-gangjin",
        title: "[강진] 대한민국 반값여행 지원",
        region: "전남",
        deadline: testIsoDateFromToday(60),
        cardSummary: "최대 20만원 환급",
      }),
      policy({
        id: "youth-seoul",
        title: "청년 여행 지원",
        region: "서울",
        deadline: testIsoDateFromToday(20),
        cardSummary: "최대 5만원 지원",
      }),
      policy({
        id: "stay-goseong",
        title: "[고성] 숙박세일 페스타 숙박 할인",
        region: "강원",
        category: "숙박",
        deadline: testIsoDateFromToday(100),
        cardSummary: "최대 7만원 할인",
      }),
      policy({
        id: "stay-sokcho",
        title: "[속초] 숙박세일 페스타 숙박 할인",
        region: "강원",
        category: "숙박",
        deadline: testIsoDateFromToday(100),
        cardSummary: "최대 3만원 할인",
      }),
      policy({
        id: "dgtour-hadong",
        title: "[하동] 디지털관광주민증 혜택",
        region: "경남",
        deadline: "",
        startDate: null,
        cardSummary: "지역 제휴 혜택",
        officialUrl:
          "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48850",
      }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = withoutPreferredRegions();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const list = await screen.findByRole("list", { name: "마감 임박 혜택 목록" });
      const cards = within(list).getAllByRole("link");
      expect(cards).toHaveLength(4);
      expect(cards[0]).toHaveTextContent("청년 여행 지원");
      expect(cards[0]).toHaveTextContent("서울");

      // 지명만 다른 반값여행 세 곳이 한 장이다. 가장 빠른 마감의 곳부터 이름을 대고, 그곳 상세로 간다.
      expect(cards[1]).toHaveTextContent("대한민국 반값여행 지원");
      expect(cards[1]).toHaveTextContent("최대 20만원 환급");
      expect(cards[1].querySelector(".home-deadline-where")).toHaveTextContent("강진 · 합천 외 1곳");
      expect(cards[1]).toHaveAttribute("href", "/policies/halfprice-gangjin");
      expect(screen.queryByText("[합천] 대한민국 반값여행 지원")).toBeNull();

      // 곳마다 금액이 다르면 첫 곳 금액을 묶음 전체 금액처럼 싣지 않는다
      expect(cards[2]).toHaveTextContent("숙박세일 페스타 숙박 할인");
      expect(cards[2].querySelector(".home-deadline-summary")).toBeNull();

      // 마감일이 없는 디지털관광주민증은 맨 뒤, '상시 발급'
      expect(cards[3]).toHaveTextContent("디지털관광주민증 혜택");
      expect(cards[3].querySelector(".home-deadline-badge")).toHaveTextContent("상시 발급");
      expect(cards[3]).toHaveTextContent("지역 제휴 혜택");
      expect(document.body).not.toHaveTextContent("마감일 확인 필요");
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("caps the deadline row at six programs in deadline order", async () => {
    const policies: Policy[] = Array.from({ length: 7 }, (_, index) =>
      policy({
        id: `program-${index + 1}`,
        title: `${index + 1}번째 마감 혜택`,
        deadline: testIsoDateFromToday(30 + (7 - index)),
      }),
    );
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = withoutPreferredRegions();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const list = await screen.findByRole("list", { name: "마감 임박 혜택 목록" });
      const titles = within(list)
        .getAllByRole("link")
        .map((link) => link.querySelector("strong")?.textContent);
      expect(titles).toEqual([
        "7번째 마감 혜택",
        "6번째 마감 혜택",
        "5번째 마감 혜택",
        "4번째 마감 혜택",
        "3번째 마감 혜택",
        "2번째 마감 혜택",
      ]);
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("counts benefits and this week's deadlines, and ranks regions by their own policies", async () => {
    const policies: Policy[] = [
      policy({ id: "jn-1", title: "[강진] 반값여행", region: "전남", deadline: testIsoDateFromToday(3) }),
      policy({ id: "jn-2", title: "[영광] 반값여행", region: "전남", deadline: testIsoDateFromToday(4) }),
      policy({ id: "gn-1", title: "[합천] 반값여행", region: "경남", deadline: testIsoDateFromToday(40) }),
      policy({ id: "nation-1", title: "내일로패스 할인", region: "전국", deadline: testIsoDateFromToday(2) }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = withoutPreferredRegions();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      await waitFor(() =>
        expect(document.body).toHaveTextContent("지금 받을 수 있는 혜택 4건 · 이번 주 마감 3건"),
      );
      const regionSection = screen.getByRole("region", { name: "혜택이 많은 지역" });
      const regionLinks = within(regionSection)
        .getAllByRole("link")
        .filter((link) => link.classList.contains("home-region-card"));
      // 전국 정책은 모든 지역에 걸려 순위를 흐리므로 지역 카드 셈에서 뺀다
      expect(regionLinks.map((link) => link.textContent)).toEqual(["전남혜택 2건", "경남혜택 1건"]);
      expect(regionLinks[0]).toHaveAttribute(
        "href",
        `/policies?${new URLSearchParams({ place: "전남", sheet: "1" })}`,
      );
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 1건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?region=전국");
      expect(nationwideCard).toHaveTextContent("기차");
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("prefers preferred-region policies and labels the list by that rule", async () => {
    const policies: Policy[] = [
      policy({ id: "b1", title: "부산 늦은 혜택", region: "부산", deadline: "2026-12-31" }),
      policy({ id: "j1", title: "전남 임박 혜택", region: "전남", deadline: "2026-07-01" }),
      policy({ id: "n1", title: "전국 교통 혜택", region: "전국", deadline: "2026-07-02" }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산"],
      style: "휴식",
      budget: "30만원",
    } as Awaited<ReturnType<typeof appDataApi.getProfile>>);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      // 관심 지역이 있으면 그 지역 정책만, 제목도 그 규칙을 말한다
      const list = await screen.findByRole("list", { name: "내 관심 지역 혜택 목록" });
      await waitFor(() => expect(within(list).getAllByRole("link")).toHaveLength(1));
      expect(within(list).getByText("부산 늦은 혜택")).toBeInTheDocument();
      expect(within(list).queryByText("전남 임박 혜택")).toBeNull();
      // 전국은 지역 줄이 아니라 아래 전국 한 줄 카드 몫이다 - 카드는 정책을 늘어놓지 않고 목록으로 보낸다
      expect(within(list).queryByText("전국 교통 혜택")).toBeNull();
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 1건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?region=전국");
      expect(within(nationwideCard).queryByText("전국 교통 혜택")).toBeNull();
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("falls back to deadline order without preferred regions and counts nationwide policies on the card", async () => {
    const nationwide = Array.from({ length: 7 }, (_, index) =>
      policy({
        id: `n${index}`,
        title: `전국 혜택 ${index + 1}`,
        region: "전국",
        deadline: `2026-08-0${index + 1}`,
      }),
    );
    const policies: Policy[] = [
      ...nationwide,
      policy({ id: "j1", title: "전남 임박 혜택", region: "전남", deadline: "2026-07-01" }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: "휴식",
      budget: "30만원",
    } as Awaited<ReturnType<typeof appDataApi.getProfile>>);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const list = await screen.findByRole("list", { name: "마감 임박 혜택 목록" });
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 7건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?region=전국");
      // 카드 안에는 정책 제목이 없다
      expect(within(nationwideCard).queryByText(/전국 혜택 \d/)).toBeNull();
      await waitFor(() => expect(within(list).getAllByRole("link")).toHaveLength(1));
      expect(within(list).getByText("전남 임박 혜택")).toBeInTheDocument();
    } finally {
      getProfileSpy.mockRestore();
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
      // 관심 지역 코스 카드가 일정 만들기 자리를 맡으므로 한 줄 카드는 겹쳐 내지 않는다
      expect(document.querySelector(".home-trip-line")).toBeNull();
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("uses a one-line trip card when preferred regions are unset", async () => {
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

      const tripCard = await screen.findByRole("link", { name: /여행 일정 만들기/ });
      expect(tripCard).toHaveClass("home-trip-line");
      expect(tripCard).toHaveAttribute("href", "/trips/new");
      expect(tripCard).not.toHaveTextContent("부산");
      expect(listRegionRecommendationsSpy).not.toHaveBeenCalled();
      // 근거 없는 '숙소 포함·맛집 포함' 말풍선 카드는 없다
      expect(document.querySelector(".prototype-home-ai-card")).toBeNull();
      expect(document.body).not.toHaveTextContent("AI 추천 맞춤 일정");
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("keeps existing trips out of the home trip entry", async () => {
    const existingTrip: Trip = {
      ...getPreviewTrip(),
      id: "300",
      title: "경주 야호",
      dates: "2026.05.18 - 05.20",
      expectedSaving: "30만원",
    };
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: "맛집",
      budget: "40만원 이하",
    });
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([existingTrip]);

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const tripCard = await screen.findByRole("link", { name: /여행 일정 만들기/ });
      expect(tripCard).toHaveAttribute("href", "/trips/new");
      expect(listTripsSpy).not.toHaveBeenCalled();
      expect(document.body).not.toHaveTextContent("경주 야호");
      expect(document.body).not.toHaveTextContent("2026.05.18 - 05.20");
    } finally {
      getProfileSpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });

  it("shows the profile prompt as a dismissible banner once per session", async () => {
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

      const banner = await screen.findByRole("region", { name: "프로필 설정 안내" });
      // 가운데 뜨는 창이 아니다 - 홈을 가리지 않는다
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(banner).toHaveTextContent("관심 지역·취향·예산을 정하면 추천이 정확해져요");
      expect(within(banner).getByRole("link", { name: /설정하기/ })).toHaveAttribute(
        "href",
        "/profile-setup?redirect=/home",
      );

      await user.click(within(banner).getByRole("button", { name: "프로필 설정 안내 닫기" }));
      await waitFor(() =>
        expect(screen.queryByRole("region", { name: "프로필 설정 안내" })).not.toBeInTheDocument(),
      );

      cleanup();
      renderAppRoute("/home");
      await screen.findByRole("list", { name: /목록$/ });
      expect(screen.queryByRole("region", { name: "프로필 설정 안내" })).not.toBeInTheDocument();

      window.sessionStorage.clear();
      cleanup();
      renderAppRoute("/home");
      expect(
        await screen.findByRole("region", { name: "프로필 설정 안내" }),
      ).toBeInTheDocument();
    } finally {
      getProfileSpy.mockRestore();
      window.sessionStorage.clear();
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

  it("keeps the preferred-region trip card when region recommendations fail", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산"],
      style: "맛집",
      budget: "40만원 이하",
    });
    const listRegionRecommendationsSpy = vi
      .spyOn(appDataApi, "listRegionRecommendations")
      .mockRejectedValue(new Error("recommendation API unavailable"));

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      await waitFor(() => expect(listRegionRecommendationsSpy).toHaveBeenCalled());
      expect(await screen.findByText("AI 추천 맞춤 일정")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /부산 맛집 코스 만들기/ }),
      ).toHaveTextContent("관심지역 맞춤 일정");
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });

  it("keeps the preferred-region trip card when region recommendations are empty", async () => {
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["부산"],
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

      await waitFor(() => expect(listRegionRecommendationsSpy).toHaveBeenCalled());
      expect(await screen.findByText("AI 추천 맞춤 일정")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /부산 맛집 코스 만들기/ }),
      ).toHaveTextContent("관심지역 맞춤 일정");
    } finally {
      getProfileSpy.mockRestore();
      listRegionRecommendationsSpy.mockRestore();
    }
  });
});
