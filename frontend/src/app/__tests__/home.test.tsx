import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { HERO_PHOTOS } from "../../components/heroPhotos";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type PlaceSearchItem,
  type Policy,
  type RegionRecommendation,
  type Trip,
} from "../../api";
import {
  examplePolicyDetail,
  getPreviewTrip,
  testIsoDateFromToday,
} from "../../test/fixtures";
import { login, renderAppRoute, routeLocation } from "../../test/renderAppRoute";

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
      name: "마감이 가까운 혜택",
    });
    // 홈 검색창은 모양 · 문구 그대로 입력칸이다(시안 v56)
    expect(screen.getByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" })).toHaveAttribute("placeholder", "어디로 떠나세요?");
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
    // 한 곳이면 그 상세, 여러 곳 묶음이면 정책 탭의 그 사업
    expect(cards[0].getAttribute("href")).toMatch(/^\/policies(\/.+|\?.*prog=.+)$/);
    expect(cards[0].querySelector(".home-deadline-badge")).toHaveTextContent(/D-|마감/);
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
    // 혜택이 많은 시군 카드 - 누르면 그 시군 대표 혜택 상세
    expect(regionLinks[0].getAttribute("href")).toMatch(/^\/policies\/.+/);
    expect(regionLinks[0]).toHaveTextContent(/혜택 \d+건/);

    // 인사 바로 아래 배너(임시 내용)
    const hero = screen.getByRole("region", { name: "이번 주 소식" });
    expect(hero.compareDocumentPosition(deadlineSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(hero).getAllByRole("link")).toHaveLength(1);

    // 넓은 화면 배치의 걸쇠: 이 표시가 있어야 1024px 이상에서 앱 틀이 넓어지고(app.css) 두 줄이 격자로 펴진다(home.css)
    expect(document.querySelector(".prototype-home-screen")).toHaveClass("desktop-wide");
    expect(deadlineSection.querySelector(".home-row")).toHaveClass("home-row-deadline");
    expect(regionSection.querySelector(".home-row")).toHaveClass("home-row-regions");
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

      const list = await screen.findByRole("list", { name: "마감이 가까운 혜택 목록" });
      const cards = within(list).getAllByRole("link");
      // 마감이 없는 디지털관광주민증은 '마감이 가까운 혜택'에 들지 않는다
      expect(cards).toHaveLength(3);
      expect(list).not.toHaveTextContent("디지털관광주민증");
      expect(cards[0]).toHaveTextContent("청년 여행 지원");
      expect(cards[0]).toHaveTextContent("서울");
      expect(cards[0]).toHaveAttribute("href", "/policies/youth-seoul");
      expect(cards[0].querySelector(".home-deadline-badge")).toHaveTextContent(/^D-20$/);

      // 지명만 다른 반값여행 세 곳이 한 장이다. 가장 빠른 마감의 곳부터 이름을 대고, 정책 탭의 그 사업으로 간다.
      // 받는 것은 사업 공통 문구(정책 탭 목록 묶음 머리와 같음)
      expect(cards[1]).toHaveTextContent("대한민국 반값여행 지원");
      expect(cards[1].querySelector(".home-deadline-summary")).toHaveTextContent("여행비 50% 환급 · 최대 20만원");
      expect(cards[1].querySelector(".home-deadline-where")).toHaveTextContent("강진 · 합천 외 1곳");
      expect(cards[1]).toHaveAttribute("href", `/policies?${new URLSearchParams({ prog: "대한민국 반값여행 지원" })}`);
      expect(screen.queryByText("[합천] 대한민국 반값여행 지원")).toBeNull();

      // 곳마다 금액이 다르면 첫 곳 금액을 묶음 전체 금액처럼 싣지 않는다. 한 지역 안의 묶음은 그 지역으로 좁혀 보낸다
      expect(cards[2]).toHaveTextContent("숙박세일 페스타 숙박 할인");
      expect(cards[2].querySelector(".home-deadline-summary")).toBeNull();
      expect(cards[2]).toHaveAttribute(
        "href",
        `/policies?${new URLSearchParams({ place: "강원", prog: "숙박세일 페스타 숙박 할인" })}`,
      );
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

      const list = await screen.findByRole("list", { name: "마감이 가까운 혜택 목록" });
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

  it("counts benefits and this week's deadlines, ranks places by their own policies, and builds the banner from them", async () => {
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
      // 시군 카드: 혜택 수가 같으면 마감이 빠른 곳부터. 전국 정책은 모든 곳에 걸려 순위를 흐리므로 뺀다
      expect(regionLinks.map((link) => link.querySelector("b")?.textContent)).toEqual(["강진", "영광", "합천"]);
      expect(regionLinks[0]).toHaveTextContent("전남 · 혜택 1건");
      expect(regionLinks[0].querySelector(".home-region-lead")).toHaveTextContent("D-3");
      expect(regionLinks[0]).toHaveAttribute("href", "/policies/jn-1");

      // 배너: 가장 가까운 마감(전국 포함) · 혜택이 가장 많은 지역 · 전국 공통. 보이는 장은 하나
      const slides = Array.from(document.querySelectorAll(".home-hero-slide"));
      expect(slides.map((slide) => slide.querySelector("b")?.textContent)).toEqual([
        "내일로패스 할인",
        "전라남도 2건",
        "전국 공통 혜택 1건",
      ]);
      expect(slides.map((slide) => slide.getAttribute("href"))).toEqual([
        "/policies/nation-1",
        `/policies?${new URLSearchParams({ place: "전남", sheet: "1" })}`,
        "/policies?place=전국",
      ]);
      expect(slides[0].querySelector(".home-hero-eyebrow")).toHaveTextContent("D-2전국 공통");
      // 장 바탕 사진은 장의 성격으로: 마감 장은 혜택 종류(내일로 = 교통), 지역 장은 그 도, 전국 장은 교통
      expect(slides.map((slide) => (slide as HTMLElement).style.getPropertyValue("--ph"))).toEqual([
        `url(${HERO_PHOTOS["theme:move"].src})`,
        `url(${HERO_PHOTOS["region:전남"].src})`,
        `url(${HERO_PHOTOS["theme:move"].src})`,
      ]);
      // 출처는 배너 아래 '사진 출처' 하나로 모은다(시안 v53)
      expect(screen.getByRole("button", { name: "사진 출처" })).toBeInTheDocument();
      // 가운데는 첫 장, 둘째 장은 오른쪽에 비친다(누르면 가운데로)
      expect(slides[0]).toHaveAttribute("data-pos", "0");
      expect(slides[1]).toHaveAttribute("data-pos", "1");
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 1건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?place=전국");
      expect(nationwideCard).toHaveTextContent("기차");
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("puts a place's own photo on its card and draws the benefit instead of a photo shared by several places", async () => {
    const photo = (name: string) => ({
      imageUrl: `https://tong.visitkorea.or.kr/${name}_2.jpg`,
      thumbnailUrl: `https://tong.visitkorea.or.kr/${name}_3.jpg`,
      alt: name,
      attribution: "사진: 한국관광공사",
    });
    const policies: Policy[] = [
      policy({ id: "yg-1", title: "[영광] 대한민국 반값여행 지원", region: "전남", deadline: testIsoDateFromToday(5), photo: photo("yeonggwang") }),
      policy({ id: "yg-2", title: "[영광] 디지털관광주민증 혜택", region: "전남", deadline: "", photo: photo("yeonggwang") }),
      // 두 시군이 같은 도 대표 사진을 나눠 쓴다
      policy({ id: "gj-1", title: "[거제] 숙박세일 페스타 숙박 할인", region: "경남", category: "숙박", deadline: testIsoDateFromToday(30), photo: photo("gyeongnam") }),
      policy({ id: "ty-1", title: "[통영] 숙박세일 페스타 숙박 할인", region: "경남", category: "숙박", deadline: testIsoDateFromToday(30), photo: photo("gyeongnam") }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = withoutPreferredRegions();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const regionSection = await screen.findByRole("region", { name: "혜택이 많은 지역" });
      const cards = within(regionSection)
        .getAllByRole("link")
        .filter((link) => link.classList.contains("home-region-card"));
      expect(cards.map((card) => card.querySelector("b")?.textContent)).toEqual(["영광", "거제", "통영"]);
      // 영광: 제 사진, 누르면 안 지난 가장 빠른 마감(반값여행) 상세
      expect(cards[0].querySelector("img")).toHaveAttribute("src", photo("yeonggwang").imageUrl);
      expect(cards[0]).toHaveAttribute("href", "/policies/yg-1");
      expect(cards[0].querySelector(".home-region-lead")).toHaveTextContent("여행비 환급 · D-5");
      // 거제·통영: 나눠 쓰는 사진 대신 혜택 그림
      for (const card of cards.slice(1)) {
        expect(card).toHaveClass("nophoto");
        expect(card.querySelector("img")).toBeNull();
        expect(card.querySelector(".benefit-tile")).toBeTruthy();
      }
      // 공공누리 출처는 줄 아래 한 번
      expect(within(regionSection).getAllByText("사진: 한국관광공사")).toHaveLength(1);
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("opens a place's own benefit before one whose page is shared by many places, and ranks ties by the earliest deadline", async () => {
    const shared = "https://stay-sale.example/"; // 숙박세일처럼 여러 시군이 첫 화면 하나를 나눠 쓴다
    const policies: Policy[] = [
      policy({ id: "ta-stay", title: "[태안] 숙박세일 페스타 숙박 할인", region: "충남", category: "숙박", deadline: testIsoDateFromToday(5), officialUrl: shared }),
      policy({ id: "ta-refund", title: "[태안] 대한민국 반값여행 지원", region: "충남", deadline: testIsoDateFromToday(20), officialUrl: "https://taean.example/" }),
      policy({ id: "ta-card", title: "[태안] 디지털관광주민증 혜택", region: "충남", deadline: "", officialUrl: "https://card.example/taean" }),
      policy({ id: "gj-stay", title: "[거제] 숙박세일 페스타 숙박 할인", region: "경남", category: "숙박", deadline: testIsoDateFromToday(5), officialUrl: shared }),
      policy({ id: "gj-card", title: "[거제] 디지털관광주민증 혜택", region: "경남", deadline: "", officialUrl: "https://card.example/geoje" }),
      policy({ id: "gh-refund", title: "[고흥] 대한민국 반값여행 지원", region: "전남", deadline: testIsoDateFromToday(10), officialUrl: "https://goheung.example/" }),
      policy({ id: "gh-stay", title: "[고흥] 숙박세일 페스타 숙박 할인", region: "전남", category: "숙박", deadline: testIsoDateFromToday(30), officialUrl: shared }),
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const getProfileSpy = withoutPreferredRegions();

    try {
      await login();
      cleanup();
      renderAppRoute("/home");

      const regionSection = await screen.findByRole("region", { name: "혜택이 많은 지역" });
      const cards = within(regionSection)
        .getAllByRole("link")
        .filter((link) => link.classList.contains("home-region-card"));
      // 거제·고흥은 둘 다 2건 - 순위는 안 지난 가장 빠른 마감(거제 숙박세일 D-5 < 고흥 D-10). 대표 혜택(거제는 주민증)과 따로 센다
      expect(cards.map((card) => card.querySelector("b")?.textContent)).toEqual(["태안", "거제", "고흥"]);
      // 태안: 마감이 더 빠른 숙박세일(나눠 쓰는 안내) 대신 그 시군 전용 안내가 있는 반값여행
      expect(cards[0]).toHaveAttribute("href", "/policies/ta-refund");
      // 거제: 전용 안내는 주민증뿐(상시)
      expect(cards[1]).toHaveAttribute("href", "/policies/gj-card");
      expect(cards[2]).toHaveAttribute("href", "/policies/gh-refund");
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("shows closing-soon benefits nationwide first, then the preferred regions' own row", async () => {
    const policies: Policy[] = [
      policy({ id: "b1", title: "부산 늦은 혜택", region: "부산", deadline: testIsoDateFromToday(90) }),
      policy({ id: "j1", title: "전남 임박 혜택", region: "전남", deadline: testIsoDateFromToday(3) }),
      policy({ id: "n1", title: "전국 교통 혜택", region: "전국", deadline: testIsoDateFromToday(10) }),
      policy({ id: "old", title: "지난 혜택", region: "전남", deadline: testIsoDateFromToday(-1) }),
      policy({
        id: "dgtour-busan",
        title: "[부산동구] 디지털관광주민증 혜택",
        region: "부산",
        deadline: "",
        cardSummary: "지역 제휴 혜택",
        officialUrl: "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=26&signguCd=26170",
      }),
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

      // 마감이 가까운 혜택: 지역을 가리지 않고(전국 포함) 아직 안 지난 마감순. 지난 것·상시는 빠진다
      const closing = await screen.findByRole("list", { name: "마감이 가까운 혜택 목록" });
      await waitFor(() =>
        expect(within(closing).getAllByRole("link").map((link) => link.querySelector("strong")?.textContent)).toEqual([
          "전남 임박 혜택",
          "전국 교통 혜택",
          "부산 늦은 혜택",
        ]),
      );
      expect(within(closing).getAllByRole("link")[1].querySelector(".home-deadline-where")).toHaveTextContent("전국 공통");

      // 그다음 줄이 내 관심 지역 혜택: 그 지역 정책만, 상시 주민증은 맨 뒤 '상시'
      const mine = await screen.findByRole("list", { name: "내 관심 지역 혜택 목록" });
      expect(closing.compareDocumentPosition(mine) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      const mineCards = within(mine).getAllByRole("link");
      expect(mineCards.map((link) => link.querySelector("strong")?.textContent)).toEqual([
        "부산 늦은 혜택",
        "디지털관광주민증 혜택",
      ]);
      expect(mineCards[1].querySelector(".home-deadline-badge")).toHaveTextContent(/^상시$/);
      expect(within(mine).queryByText("전남 임박 혜택")).toBeNull();
      expect(within(mine).queryByText("전국 교통 혜택")).toBeNull();
      // 전국 한 줄 카드는 그대로 - 정책을 늘어놓지 않고 목록으로 보낸다
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 1건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?place=전국");
      expect(within(nationwideCard).queryByText("전국 교통 혜택")).toBeNull();
    } finally {
      getProfileSpy.mockRestore();
      listPoliciesSpy.mockRestore();
    }
  });

  it("skips the preferred-region row without preferred regions and counts nationwide policies on the card", async () => {
    const nationwide = Array.from({ length: 7 }, (_, index) =>
      policy({
        id: `n${index}`,
        title: `전국 혜택 ${index + 1}`,
        region: "전국",
        deadline: testIsoDateFromToday(10 + index),
      }),
    );
    const policies: Policy[] = [
      ...nationwide,
      policy({ id: "j1", title: "전남 임박 혜택", region: "전남", deadline: testIsoDateFromToday(3) }),
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

      const list = await screen.findByRole("list", { name: "마감이 가까운 혜택 목록" });
      const nationwideCard = screen.getByRole("link", { name: /전국 공통 혜택 7건/ });
      expect(nationwideCard).toHaveAttribute("href", "/policies?place=전국");
      // 카드 안에는 정책 제목이 없다
      expect(within(nationwideCard).queryByText(/전국 혜택 \d/)).toBeNull();
      // 전국도 마감이 가까운 혜택에 든다 - 여섯 장까지
      await waitFor(() => expect(within(list).getAllByRole("link")).toHaveLength(6));
      expect(within(list).getAllByRole("link")[0]).toHaveTextContent("전남 임박 혜택");
      // 관심 지역을 안 골랐으면 그 줄은 없다(배너가 고르기를 권한다)
      expect(screen.queryByRole("region", { name: "내 관심 지역 혜택" })).toBeNull();

      // 누르면 정책 탭 지도의 '전국 공통'이 열린다. 지역 필터(region=전국)로 가면 예전 목록 화면이 떴다
      await userEvent.setup().click(nationwideCard);
      expect(await screen.findByRole("button", { name: /전국 공통 7/, pressed: true })).toBeInTheDocument();
      expect(screen.queryByText(/전체 \d+개 중/)).toBeNull();
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

  it("searches places from the home search bar, opens a place card and hands the place to a trip", async () => {
    const odongdo: PlaceSearchItem = {
      kind: "place",
      id: "kakao:8193468",
      name: "오동도",
      category: "여행 > 관광,명소 > 섬",
      categoryCode: "AT4",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.745,
      longitude: 127.766,
      placeUrl: "http://place.map.kakao.com/8193468",
      sido: "전남",
      city: "여수",
    };
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      policy({ id: "ys", title: "[여수] 숙박 할인", region: "전남" }),
      policy({ id: "gy", title: "[광양] 숙박 할인", region: "전남" }),
    ]);
    const getProfileSpy = withoutPreferredRegions();
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);
    const upcoming = (id: string, title: string, role: Trip["currentUserRole"], from: number): Trip => ({
      ...getPreviewTrip(),
      id,
      title,
      startDate: testIsoDateFromToday(from),
      endDate: testIsoDateFromToday(from + 2),
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: role,
    });
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips").mockResolvedValue([
      upcoming("301", "여수 여행", "owner", 10),
      upcoming("302", "지난 여행", "owner", -30),
      upcoming("303", "보기만 하는 여행", "viewer", 10),
    ]);
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(upcoming("301", "여수 여행", "owner", 10));
    try {
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();
      const searchbox = await screen.findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" });

      // 홈 화면 그대로 검색창이 입력이 되고 그 아래가 결과다. 닫으면 홈 내용이 그대로 돌아온다
      await user.click(searchbox);
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("q")).toBe(""));
      expect(screen.queryByText(/안녕,/)).toBeNull();
      await user.click(screen.getByRole("button", { name: "검색 닫기" }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).has("q")).toBe(false));
      expect(await screen.findByText(/안녕,/)).toBeInTheDocument();

      // 지역 · 혜택 줄과 장소 목록이 함께 - 장소는 지역 이름이 아니어도 늘 찾는다
      await user.click(searchbox);
      await user.type(searchbox, "오동도");
      const row = await screen.findByRole("button", { name: /오동도.*섬/ });
      expect(row).toHaveTextContent("혜택 1");
      expect(searchPlacesSpy).toHaveBeenLastCalledWith("오동도", expect.anything());

      // 장소 카드 - 뒤로(‹ 검색 결과)는 결과 그대로
      await user.click(row);
      let card = await screen.findByRole("article", { name: "오동도 장소 카드" });
      expect(routeLocation().search).toContain("pl=");
      expect(within(card).getByRole("link", { name: /카카오맵에서 자세히/ })).toHaveAttribute("href", "http://place.map.kakao.com/8193468");
      // 근처 혜택 버튼은 어느 시군 혜택인지 말한다(그 시군 전용이면 거리는 없다)
      const near = new URLSearchParams(within(card).getByRole("link", { name: /^여수 혜택 1건 보기/ }).getAttribute("href")!.split("?")[1]);
      expect([near.get("place"), near.get("city"), JSON.parse(near.get("near")!).name]).toEqual(["전남", "여수", "오동도"]);
      await user.click(within(card).getByRole("button", { name: "‹ 검색 결과" }));
      await waitFor(() => expect(screen.queryByRole("article", { name: "오동도 장소 카드" })).toBeNull());
      expect(searchbox).toHaveValue("오동도");
      await user.click(await screen.findByRole("button", { name: /오동도.*섬/ }));
      card = await screen.findByRole("article", { name: "오동도 장소 카드" });

      // 일정에 담기: 끝나지 않은 · 고칠 수 있는 일정만. 고르면 그 일정의 장소 추가 창이 이 장소를 바구니에 담은 채 열린다(시안 v57)
      await user.click(within(card).getByRole("button", { name: "일정에 담기" }));
      const picker = await within(card).findByRole("group", { name: "일정 고르기" });
      await within(picker).findByRole("button", { name: /여수 여행/ });
      expect(within(picker).queryByText("지난 여행")).toBeNull();
      expect(within(picker).queryByText("보기만 하는 여행")).toBeNull();
      await user.click(within(picker).getByRole("button", { name: /여수 여행/ }));
      await waitFor(() => expect(routeLocation().pathname).toBe("/trips/301"));
      const sheet = await screen.findByRole("dialog", { name: "장소 추가" });
      expect(within(sheet).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오동도");
      expect(within(sheet).getByRole("button", { name: "Day 1에 1개 저장하기" })).toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
      getProfileSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      listTripsSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("shows nearby places on the place card and follows one to its own card", async () => {
    const odongdo: PlaceSearchItem = {
      kind: "place",
      id: "kakao:8193468",
      name: "오동도",
      category: "여행 > 관광,명소 > 섬",
      categoryCode: "AT4",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.745,
      longitude: 127.766,
      placeUrl: "http://place.map.kakao.com/8193468",
      sido: "전남",
      city: "여수",
    };
    const near = (id: string, name: string, category: string, distanceMeters: number): PlaceSearchItem => ({
      ...odongdo,
      id,
      name,
      category,
      categoryCode: null,
      distanceMeters,
    });
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      policy({ id: "ys", title: "[여수] 숙박 할인", region: "전남" }),
      policy({ id: "gy", title: "[광양] 반값여행", region: "전남" }),
    ]);
    const getProfileSpy = withoutPreferredRegions();
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);
    const nearbySpy = vi.spyOn(appDataApi, "listNearbyPlaces").mockImplementation(async (_lat, _lng, category) =>
      category === "FD6"
        ? [{ ...odongdo, distanceMeters: 0 }, near("kakao:n1", "오동도해양식당", "음식점 > 한식 > 해물,생선", 320)]
        : category === "AD5"
          ? [near("kakao:n2", "오동도관광호텔", "여행 > 숙박 > 호텔", 1300)]
          : [],
    );
    try {
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();
      const searchbox = await screen.findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" });
      await user.click(searchbox);
      await user.type(searchbox, "오동도");
      await user.click(await screen.findByRole("button", { name: /오동도.*섬/ }));
      const card = await screen.findByRole("article", { name: "오동도 장소 카드" });

      // 이 근처: 맛집이 먼저, 가까운 순 - 기준 장소 자신은 빼고 거리를 적는다
      const nearby = within(card).getByRole("region", { name: "이 근처" });
      const restaurant = await within(nearby).findByRole("button", { name: /오동도해양식당/ });
      expect(restaurant).toHaveTextContent("해물,생선 · 약 320m");
      expect(within(nearby).queryByRole("button", { name: /^오동도 / })).toBeNull();
      expect(nearbySpy).toHaveBeenCalledWith(34.745, 127.766, "FD6", expect.anything());

      // 숙소 칸에는 그 지역 숙박 혜택 건수
      await user.click(within(nearby).getByRole("button", { name: "숙소" }));
      expect(await within(nearby).findByText("여수 숙박 혜택 1건 - 숙소마다 쓸 수 있는지는 혜택 조건에서 확인해요")).toBeInTheDocument();
      expect(within(nearby).getByRole("button", { name: /오동도관광호텔/ })).toHaveTextContent("약 1.3km");

      // 한 곳을 누르면 그 장소 카드로 이어 본다 - 뒤로는 앞 장소
      await user.click(within(nearby).getByRole("button", { name: /오동도관광호텔/ }));
      const hotel = await screen.findByRole("article", { name: "오동도관광호텔 장소 카드" });
      await user.click(within(hotel).getByRole("button", { name: "‹ 오동도" }));
      expect(await screen.findByRole("article", { name: "오동도 장소 카드" })).toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
      getProfileSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      nearbySpy.mockRestore();
    }
  });

  it("folds shop names away for benefit words and lists same-named neighbourhoods across the country", async () => {
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      policy({ id: "hc", title: "[합천] 대한민국 반값여행 지원", region: "경남" }),
      policy({ id: "ys", title: "[여수] 숙박 할인", region: "전남" }),
    ]);
    const getProfileSpy = withoutPreferredRegions();
    const shop: PlaceSearchItem = {
      kind: "place", id: "kakao:s1", name: "반값밧데리할인마트", category: "가정,생활 > 자동차용품", categoryCode: null,
      address: "경기 수원시 장안구 1", latitude: 37.3, longitude: 127.0, placeUrl: null, sido: "경기", city: "수원",
    };
    const dong: PlaceSearchItem = {
      kind: "area", id: "area:4613010100", name: "여수시 중앙동", category: null, categoryCode: null,
      address: "전남광주통합특별시 여수시 중앙동", latitude: 34.737, longitude: 127.738, placeUrl: null, sido: "전남", city: "여수",
    };
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchPlaces").mockImplementation(async (query) =>
      query === "반값" ? [shop] : query === "중앙동" ? [dong] : []);
    try {
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();
      const searchbox = await screen.findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" });
      await user.click(searchbox);

      // 혜택 이름이 맞으면 상호명 장소는 접는다 - 누르면 보인다
      await user.type(searchbox, "반값");
      const more = await screen.findByRole("button", { name: "‘반값’ 이름이 든 장소도 보기 · 1곳" });
      expect(screen.getByRole("button", { name: /대한민국.*반값.*여행 지원/ })).toBeInTheDocument();   // 찾은 말은 강조(mark)라 이름 계산에 틈이 생긴다
      expect(screen.queryByRole("button", { name: /반값밧데리할인마트/ })).toBeNull();
      await user.click(more);
      expect(await screen.findByRole("button", { name: /반값밧데리할인마트/ })).toBeInTheDocument();

      // 같은 이름의 동은 시군별 줄 - 누르면 그 근처 혜택(정책 탭)
      await user.clear(searchbox);
      await user.type(searchbox, "중앙동");
      const row = await screen.findByRole("link", { name: /여수시 중앙동.*→ 전남 여수 · 혜택 1건/ });
      const params = new URLSearchParams(row.getAttribute("href")!.split("?")[1]);
      expect([params.get("place"), params.get("city"), JSON.parse(params.get("near")!).name]).toEqual(["전남", "여수", "여수시 중앙동"]);

      // 아무것도 없으면 다음 행동 - 혜택 이름 칩과 전체 정책 보기
      await user.clear(searchbox);
      await user.type(searchbox, "없는말");
      expect(await screen.findByText("‘없는말’에 맞는 지역 · 혜택 · 장소가 없어요. 이렇게 찾아 보세요.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "전체 정책 보기" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "대한민국 반값여행 지원" })).toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
      getProfileSpy.mockRestore();
      searchPlacesSpy.mockRestore();
    }
  });
});
