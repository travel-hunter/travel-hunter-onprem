import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type Policy,
  type Trip,
} from "../../api";
import { App } from "../App";
import { policyTripErrorMessage } from "../../pages/PolicyPages";
import { AppProviders } from "../AppRoot";
import {
  examplePolicyDetail,
  examplePolicyPath,
  examplePolicySlug,
  examplePolicyTitle,
  getPreviewTrip,
  getUpcomingPreviewTrip,
  getPreviewUser,
  testEmail,
  testIsoDateFromToday,
  testPassword,
} from "../../test/fixtures";
import { getLink, goBack, login, renderAppRoute, routeLocation } from "../../test/renderAppRoute";
import { DESKTOP_MEDIA_QUERY } from "../../lib/useMediaQuery";

/* 지도 화면: 지도 뒤로 목록 시트가 반반으로 선다. 목록 머리가 지금 목록의 이름과 건수를 말한다
   ("모든 지역 3건", "전남 1건"). 필터 · 글 검색도 이 화면 안에서 좁힌다(시안 v55) - 예전 카드 목록 화면은 없다. */
const conditionsLine = () => document.querySelector(".thmap-conds span")?.textContent ?? null;
const expectStillOnMap = () => {
  expect(document.querySelector(".thmap-host")).toBeTruthy();
  expect(document.querySelectorAll(".policy-list-card")).toHaveLength(0);
  expect(screen.queryByText(/전체 \d+개 중/)).toBeNull();
};
const sheetTitle = () => document.querySelector(".thmap-title")?.textContent?.replace(/\s+/g, " ").trim() ?? null;
async function waitForSheet(title: string) {
  await waitFor(() => expect(sheetTitle()).toBe(title));
}
/* 넓은 화면(1024px~). jsdom 에는 matchMedia 가 없어 앱이 늘 좁은 화면으로 본다 - 부른 시험 동안만 넓다고 답한다 */
function stubDesktop() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query === DESKTOP_MEDIA_QUERY,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }));
}

describe("Travel Hunter app — policies & trip picker", () => {
  it("explains that only one stay discount policy fits a trip", () => {
    // 숙박세일은 지역마다 정책 행이 따로 있어 백엔드가 409로 막는다.
    // 기본 문구는 "잠시 후 다시 시도"라 원인을 오해하게 만든다.
    expect(
      policyTripErrorMessage(
        new Error("Trip already has a stay discount policy"),
      ),
    ).toBe(
      "숙박세일 페스타 정책은 일정당 하나만 연결할 수 있어요. 기존 정책을 먼저 해제해 주세요.",
    );
  });

  it("explains when a policy does not match the trip travel area", () => {
    expect(policyTripErrorMessage(new Error("Policy does not match trip travel area"))).toBe(
      "선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요.",
    );
  });

  it("keeps the existing policy link error messages", () => {
    expect(policyTripErrorMessage(new Error("Policy not found"))).toBe(
      "정책 정보를 찾을 수 없어요. 다시 확인해 주세요.",
    );
    expect(policyTripErrorMessage(new Error("Trip not found"))).toBe(
      "일정을 찾을 수 없어요. 다른 일정을 선택해 주세요.",
    );
    expect(policyTripErrorMessage(new Error("boom"))).toBe(
      "일정에 혜택을 담지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
  });

  it("picks the map region and benefit kind from the filter sheet without leaving the map", async () => {
    const policies: Policy[] = [
      examplePolicyDetail,
      { ...examplePolicyDetail, id: "gangneung-stay", slug: "gangneung-stay", title: "강릉 숙박 할인권", region: "강원", category: "숙박", summary: "강릉 숙박 혜택" },
      { ...examplePolicyDetail, id: "busan-card-cashback", slug: "busan-card-cashback", title: "부산 카드 캐시백", region: "부산", category: "지역할인", summary: "부산 지역 결제 혜택" },
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();
      await waitForSheet("모든 지역 3건");

      // 필터 창의 지역은 지도 선택과 같은 값이다 - 적용하면 지도에서 부산을 고른 것과 같다(예전엔 지도를 떠나 카드 목록)
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      expectStillOnMap();
      await user.click(within(filterDialog).getByRole("button", { name: "1건 보기" }));
      await waitForSheet("부산 1건");
      expectStillOnMap();
      expect(routeLocation().search).toContain(`place=${encodeURIComponent("부산")}`);
      // 지역 · 혜택 형태는 조건 줄에 적지 않는다 - 지도와 칩이 말한다
      expect(conditionsLine()).toBeNull();

      // 초기화하고 적용하면 처음 화면
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "초기화" }));
      await user.click(within(filterDialog).getByRole("button", { name: "3건 보기" }));
      await waitForSheet("모든 지역 3건");
      expectStillOnMap();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("narrows the map and list with conditions, keeps them on back, and clears them with ✕", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "soon", slug: "soon", title: "곧 마감 혜택", region: "강원", deadline: testIsoDateFromToday(3) },
      { ...examplePolicyDetail, id: "later", slug: "later", title: "넉넉한 혜택", region: "부산", deadline: testIsoDateFromToday(60) },
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();
      await waitForSheet("모든 지역 2건");

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      // 아래 단추는 미리 센다. 맞는 게 없으면 적용할 수 없다
      await user.click(within(filterDialog).getByRole("button", { name: "30만원 이상" }));
      expect(within(filterDialog).getByRole("button", { name: "맞는 혜택 없음" })).toBeDisabled();
      await user.click(within(filterDialog).getByRole("button", { name: "금액 전체" }));
      await user.click(within(filterDialog).getByRole("button", { name: "강원" }));
      await user.click(within(filterDialog).getByRole("button", { name: "7일 이내" }));
      await user.click(within(filterDialog).getByRole("button", { name: "1건 보기" }));

      // 지도를 떠나지 않는다 - 목록 머리 아래 조건 한 줄, 필터 단추에 조건 수
      await waitForSheet("강원 1건");
      expectStillOnMap();
      expect(conditionsLine()).toBe("마감 7일 이내");
      expect(screen.getByRole("button", { name: "필터 열기" })).toHaveTextContent("필터 1");

      // 뒤로가기는 지도 층(강원)만 걷는다 - 조건은 층이 아니라 남는다
      await user.click(screen.getByRole("button", { name: "뒤로" }));
      await waitForSheet("모든 지역 1건");
      expect(conditionsLine()).toBe("마감 7일 이내");

      // ✕ 로 푼다
      await user.click(screen.getByRole("button", { name: "조건 모두 풀기" }));
      await waitForSheet("모든 지역 2건");
      expect(conditionsLine()).toBeNull();
      expect(screen.getByRole("button", { name: "필터 열기" })).toHaveTextContent(/^필터$/);

      // 다시 열면 초안은 지금 값에서 시작한다
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      expect(within(filterDialog).getByRole("button", { name: "기간 전체" })).toHaveAttribute("aria-pressed", "true");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("draws the map frame while policies load instead of the old full-width loading card", async () => {
    // 응답이 늦을 때: 지도 칸이 먼저 서고 '불러오는 중'은 목록 자리에 선다. 예전엔 빈 화면에 그 카드만 떠서 예전 목록 화면처럼 보였다
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockReturnValue(new Promise(() => {}));
    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const status = await screen.findByRole("status");
      expect(status).toHaveTextContent("정책을 불러오는 중입니다");
      expect(status.closest(".thmap-loading")).toBeTruthy();
      expect(document.querySelector(".thmap-stage .thmap-host")).toBeTruthy();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("keeps the desktop panel on the loading state while a deep-linked detail waits for policies", async () => {
    // 넓은 화면 detail= 주소로 바로 열 때: 정책이 오기 전에 '이 정책은 지금 목록에 없어요'를 띄우지 않는다
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockReturnValue(new Promise(() => {}));
    try {
      await login();
      cleanup();
      stubDesktop();
      renderAppRoute("/policies?detail=some-policy");
      await screen.findByText("정책을 불러오는 중입니다");
      expect(document.querySelector(".thmap-split .thmap-panel .thmap-loading")).toBeTruthy();
      expect(screen.queryByText("이 정책은 지금 목록에 없어요.")).toBeNull();
    } finally {
      listPoliciesSpy.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it("shows digital resident policies as always-issued instead of deadline-unknown on the list", async () => {
    const policies: Policy[] = [
      {
        ...examplePolicyDetail,
        id: "travelmonth-dgtour-miryang",
        slug: "travelmonth-dgtour-miryang",
        label: "DG",
        tag: "지역할인",
        title: "[밀양] 디지털관광주민증 혜택",
        org: "밀양 지자체 · 한국관광공사",
        region: "경남",
        deadline: "",
        amount: "지역 제휴 혜택",
        summary: "디지털관광주민증 발급 지역의 제휴 혜택입니다.",
        category: "지역할인",
        officialUrl: "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48270",
        applyUrl: null,
        sourceType: "external",
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      // 정책 탭 안의 짧은 칩은 지도 목록 줄도 검색 목록 카드도 '상시'(시안 v40, 2026-09-30 사용자 결정)
      renderAppRoute("/policies?place=경남");
      await waitForSheet("경남 1건");
      expect(within(document.querySelector(".thmap-sheet") as HTMLElement).getByText("상시")).toBeInTheDocument();

      // 글 전체 검색('모두 보기')도 지도 화면 안에서 좁힌다 - 줄의 칩은 그대로 '상시'
      const user = userEvent.setup();
      await user.type(screen.getByRole("searchbox", { name: "정책 검색" }), "밀양");
      await user.click(await screen.findByRole("button", { name: /‘밀양’ 들어간 정책 \d+건 모두 보기/ }));
      await waitFor(() => expect(conditionsLine()).toBe("‘밀양’ 검색"));
      expectStillOnMap();
      expect(within(document.querySelector(".thmap-sheet") as HTMLElement).getByText("상시")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("마감일 확인 필요");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("does not show start-date unknown copy on policy list cards", async () => {
    const policies: Policy[] = [
      {
        ...examplePolicyDetail,
        id: "deadline-only-list-policy",
        slug: "deadline-only-list-policy",
        title: "마감일만 확인된 목록 정책",
        region: "전국",
        deadline: "2026-12-31",
        startDate: null,
      },
      {
        ...examplePolicyDetail,
        id: "unknown-period-list-policy",
        slug: "unknown-period-list-policy",
        title: "기간 미확인 목록 정책",
        region: "강원",
        deadline: "",
        startDate: null,
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      // 고른 지역 목록에 전국 정책은 섞이지 않는다 - 끝에 '전국 공통 혜택 N건' 한 줄로 잇는다
      renderAppRoute("/policies?place=강원");
      await waitForSheet("강원 1건");
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      expect(within(sheet).getByText("기간 미확인 목록 정책")).toBeInTheDocument();
      expect(within(sheet).queryByText("마감일만 확인된 목록 정책")).toBeNull();
      expect(within(sheet).getByRole("button", { name: "전국 공통 혜택 1건도 여기서 쓸 수 있어요" })).toBeInTheDocument();

      // 글 전체 검색으로 좁혀도 시작일 모름 문구는 없다
      const user = userEvent.setup();
      await user.type(screen.getByRole("searchbox", { name: "정책 검색" }), "목록 정책");
      await user.click(await screen.findByRole("button", { name: /‘목록 정책’ 들어간 정책 \d+건 모두 보기/ }));
      await waitFor(() => expect(conditionsLine()).toBe("‘목록 정책’ 검색"));
      // 글 검색은 전체에서 찾는다 - 고른 강원은 풀리고 두 정책이 다 나온다
      await waitForSheet("모든 지역 2건");
      expectStillOnMap();
      expect(document.body).not.toHaveTextContent("시작일 확인 필요");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("discards draft filter changes when the sheet closes", async () => {
    const policies: Policy[] = [
      examplePolicyDetail,
      {
        ...examplePolicyDetail,
        id: "busan-card-cashback",
        slug: "busan-card-cashback",
        label: "BS",
        tag: "지역할인",
        title: "부산 카드 캐시백",
        region: "부산",
        category: "지역할인",
        summary: "부산 지역 결제 혜택",
      },
      {
        ...examplePolicyDetail,
        id: "gangneung-stay",
        slug: "gangneung-stay",
        label: "GN",
        tag: "숙박",
        title: "강릉 숙박 할인권",
        region: "강원",
        category: "숙박",
        summary: "강릉 숙박 혜택",
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      await waitForSheet("모든 지역 3건");
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      await user.click(within(filterDialog).getByRole("button", { name: "7일 이내" }));
      expect(document.querySelector(".thmap-host")).toBeTruthy();

      await user.click(within(filterDialog).getByRole("button", { name: "필터 닫기" }));
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "정책 필터" })).not.toBeInTheDocument(),
      );

      // 초안을 버렸으니 지도 화면 그대로, 건수도 그대로
      await waitForSheet("모든 지역 3건");
      expect(document.querySelector(".thmap-host")).toBeTruthy();
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      expect(within(filterDialog).getByRole("button", { name: "부산" })).not.toHaveClass("active");
      expect(within(filterDialog).getByRole("button", { name: "7일 이내" })).not.toHaveClass("active");
      expect(conditionsLine()).toBeNull();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("shows grouped region choices in the unified filter sheet", async () => {
    const regionalPolicies: Policy[] = [
      {
        id: "nationwide",
        slug: "nationwide",
        label: "ALL",
        tag: "지역할인",
        title: "전국 여행 할인",
        org: "한국관광공사",
        region: "전국",
        deadline: "2026-06-30",
        amount: "할인",
        summary: "전국 혜택",
        match: 92,
        category: "지역할인",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal",
      },
      {
        id: "jeju",
        slug: "jeju",
        label: "JEJU",
        tag: "숙박",
        title: "제주 숙박 할인",
        org: "제주관광공사",
        region: "제주",
        deadline: "2026-06-30",
        amount: "할인",
        summary: "제주 혜택",
        match: 91,
        category: "숙박",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal",
      },
      ...[
        "부산",
        "부산",
        "서울",
        "서울",
        "강원",
        "강원",
        "경기",
        "전남",
        "대구",
        "광주",
      ].map((region, index) => ({
        id: `region-${index}`,
        slug: `region-${index}`,
        label: region,
        tag: "지역할인",
        title: `${region} 지역 혜택`,
        org: `${region}관광공사`,
        region,
        deadline: "2026-06-30",
        amount: "할인",
        summary: `${region} 혜택`,
        match: 80 - index,
        category: "지역할인" as const,
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal" as const,
      })),
    ];
    const policyListSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(regionalPolicies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      await waitForSheet("모든 지역 12건");
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });

      expect(within(filterDialog).getByText("수도권")).toBeInTheDocument();
      expect(within(filterDialog).getByText("전라")).toBeInTheDocument();
      expect(within(filterDialog).queryByText("주요 지역")).not.toBeInTheDocument();
      expect(
        within(filterDialog).queryByRole("button", { name: "전체 지역 보기" }),
      ).not.toBeInTheDocument();

      await user.click(
        within(filterDialog).getByRole("button", { name: "광주" }),
      );
      expect(document.querySelector(".thmap-host")).toBeTruthy();
      await user.click(within(filterDialog).getByRole("button", { name: "1건 보기" }));

      // 지도에서 광주를 고른 것과 같다 - 목록은 광주 전용 혜택만, 전국 정책은 끝의 한 줄로 잇는다
      await waitForSheet("광주 1건");
      expectStillOnMap();
      expect(document.body).toHaveTextContent("광주 지역 혜택");
      expect(document.querySelector('a[href="/policies/nationwide"]')).toBeNull();
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("selects the map region from the URL and writes the clicked region back to the filter", async () => {
    // 지도는 새 상태가 아니라 filters.region 의 UI 다. URL → 지도, 지도 → URL 이 한 바퀴 돌아야 한다.
    const mapPolicies: Policy[] = [
      { ...examplePolicyDetail, id: "map-jeonnam", slug: "map-jeonnam", title: "전남 해안 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "map-gwangju", slug: "map-gwangju", title: "광주 도심 혜택", region: "광주" },
    ];
    const policyListSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(mapPolicies);
    const mapRegion = (name: string) =>
      document.querySelector(`.thmap-rg[data-region="${name}"]`) as SVGGElement | null;

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      await waitFor(() => expect(mapRegion("전남")).toBeTruthy());
      await waitForSheet("모든 지역 2건");
      // 지도 화면엔 목록 카드가 없다 - 목록은 지도 뒤 시트의 한 줄들이다
      expect(document.querySelectorAll(".policy-list-card")).toHaveLength(0);
      const sheet = () => document.querySelector(".thmap-sheet") as HTMLElement;

      // 지역을 눌러도 필터는 그대로다 - 고른 지역은 URL 의 place, 필터 region 은 안 붙는다
      await user.click(mapRegion("전남") as SVGGElement);
      await waitFor(() => expect(mapRegion("전남")?.classList.contains("thmap-on")).toBe(true));
      expect(screen.getByRole("region", { name: "전남 요약" })).toHaveTextContent(/전라남도\s*1건/);
      await waitForSheet("전남 1건");
      expect(within(sheet()).getByText("전남 해안 혜택")).toBeInTheDocument();
      expect(new URLSearchParams(routeLocation().search).get("place")).toBe("전남");
      expect(new URLSearchParams(routeLocation().search).get("region")).toBeNull();
      expect(screen.queryByRole("button", { name: "필터 초기화" })).not.toBeInTheDocument();

      // 다른 지역으로 옮기는 건 같은 층 - 목록만 바뀐다
      await user.click(mapRegion("광주") as SVGGElement);
      await waitFor(() => expect(mapRegion("광주")?.classList.contains("thmap-on")).toBe(true));
      expect(mapRegion("전남")?.classList.contains("thmap-on")).toBe(false);
      await waitForSheet("광주 1건");
      expect(within(sheet()).getByText("광주 도심 혜택")).toBeInTheDocument();
      expect(within(sheet()).queryByText("전남 해안 혜택")).not.toBeInTheDocument();
      expect(new URLSearchParams(routeLocation().search).get("place")).toBe("광주");

      // 목록을 한 페이지로 올리면 기록이 쌓이고, 뒤로 한 번이면 반반으로 돌아온다
      await user.click(screen.getByRole("button", { name: "목록 펼치기" }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("sheet")).toBe("full"));
      goBack();
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("sheet")).toBeNull());
      expect(new URLSearchParams(routeLocation().search).get("place")).toBe("광주");

      // 지도 밖 빈 곳을 누르면 선택이 풀린다
      await user.click(document.querySelector(".thmap-wrap") as HTMLElement);
      await waitFor(() => expect(mapRegion("광주")?.classList.contains("thmap-on")).toBe(false));
      await waitForSheet("모든 지역 2건");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("sums up the picked region on the map card and filters by its kinds", async () => {
    // 고른 지역이 어떤 곳인지: 무슨 혜택 위주인지, 몇 곳에 있는지 - 형태 단추는 위 칩과 같은 거르기다
    const fourKinds: Policy[] = [
      { ...examplePolicyDetail, id: "k1", slug: "k1", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "k2", slug: "k2", title: "[완도] 디지털관광주민증 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "k3", slug: "k3", title: "[해남] 디지털관광주민증 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "k4", slug: "k4", title: "[강진] 대한민국 반값여행 지원", region: "전남" },
      { ...examplePolicyDetail, id: "k5", slug: "k5", title: "[고흥] 대한민국 반값여행 지원", region: "전남" },
      { ...examplePolicyDetail, id: "k6", slug: "k6", title: "[담양] 숙박세일 페스타 할인", region: "전남" },
      { ...examplePolicyDetail, id: "k7", slug: "k7", title: "[보성] 남도 기차 여행 할인", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(fourKinds);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();
      await waitFor(() => expect(document.querySelector('.thmap-rg[data-region="전남"]')).toBeTruthy());
      await user.click(document.querySelector('.thmap-rg[data-region="전남"]') as unknown as Element);

      const card = await screen.findByRole("region", { name: "전남 요약" });
      expect(card).toHaveTextContent(/전라남도\s*7건/);
      expect(card).toHaveTextContent("제휴 할인 위주 · 7개 시군");
      const kinds = within(card).getByRole("group", { name: "이 지역 혜택 종류로 거르기" });
      expect(within(kinds).getAllByRole("button").map((button) => button.textContent)).toEqual(["제휴 할인 3", "환급 2", "숙박 1", "교통 1"]);
      await user.click(within(kinds).getByRole("button", { name: "환급 2" }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("type")).toBe("refund"));
      await waitForSheet("전남 2건");
      // 위 칩도 같이 눌린다
      const chips = screen.getByRole("group", { name: "혜택 형태" });
      expect(within(chips).getByRole("button", { name: /^환급/ })).toHaveAttribute("aria-pressed", "true");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("searches the whole text from any map layer so the count matches the list", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "busan", slug: "busan", title: "부산 숙박 할인", region: "부산" },
      { ...examplePolicyDetail, id: "gangwon", slug: "gangwon", title: "강원 체험 혜택", region: "강원" },
    ];
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      // 강원을 고른 채 '부산'으로 찾아도 칸이 센 1건이 그대로 목록에 나온다 - 고른 지역은 풀린다
      renderAppRoute(`/policies?place=${encodeURIComponent("강원")}`);
      await waitForSheet("강원 1건");
      const user = userEvent.setup();
      await user.type(screen.getByRole("searchbox", { name: "정책 검색" }), "부산");
      await user.click(await screen.findByRole("button", { name: "‘부산’ 들어간 정책 1건 모두 보기 ›" }));
      await waitForSheet("모든 지역 1건");
      expect(routeLocation().search).not.toContain("place=");
      // 글 검색만 걸려도 필터 단추가 조건이 걸렸다고 말한다(지도 중심이면 조건 줄이 가려진다)
      expect(screen.getByRole("button", { name: "필터 열기" })).toHaveTextContent("필터 1");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("renders the filter sheet sections that match the map screen", async () => {
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([examplePolicyDetail]);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      // 제목 줄(정책 탐색 + ♡ 관심)은 걷어냈다 - 화면엔 안 보이고 낭독기용 h1 만 남는다
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "정책 탐색" })).toBeInTheDocument(),
      );
      expect(document.body).not.toHaveTextContent("♡ 관심");

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      // 혜택 형태는 위 칩과 같은 다섯 가지(예전 카테고리 여섯 가지가 아니다)
      const kinds = within(filterDialog).getByRole("group", { name: "혜택 형태" });
      expect(within(kinds).getAllByRole("button").map((button) => button.textContent)).toEqual(["전체", "숙박", "환급", "제휴 할인", "교통"]);
      expect(within(filterDialog).queryByRole("button", { name: "여행상품" })).toBeNull();
      const regions = within(filterDialog).getByRole("group", { name: "지역" });
      expect(within(regions).getByRole("button", { name: "전국 공통" })).toBeInTheDocument();
      expect(within(filterDialog).getByRole("group", { name: "마감" })).toBeInTheDocument();
      expect(within(filterDialog).getByRole("group", { name: "금액" })).toBeInTheDocument();
      expect(within(filterDialog).getByRole("button", { name: "관심 정책만" })).toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("shows policy result counts, search, and priority ordering", async () => {
    const policies: Policy[] = [
      {
        id: "far-discount",
        slug: "far-discount",
        label: "할인",
        tag: "지역할인",
        title: "장기 지역 할인",
        org: "Travel Hunter",
        region: "전국",
        deadline: testIsoDateFromToday(120),
        amount: "혜택 제공",
        summary: "공식 안내 확인",
        match: 99,
        category: "지역할인",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal",
      },
      {
        id: "transport-expiring",
        slug: "transport-expiring",
        label: "교통",
        tag: "교통",
        title: "강릉 KTX 할인",
        org: "Travel Hunter",
        region: "강원",
        deadline: testIsoDateFromToday(3),
        amount: "30% 할인",
        summary: "강릉 여행 교통 할인",
        match: 70,
        category: "교통",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal",
      },
      {
        id: "lodging-clear",
        slug: "lodging-clear",
        label: "숙박",
        tag: "숙박",
        title: "부산 숙박 5만원 할인",
        org: "Travel Hunter",
        region: "부산",
        deadline: testIsoDateFromToday(30),
        amount: "최대 5만원",
        summary: "부산 숙박 할인",
        match: 80,
        category: "숙박",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
        sourceType: "internal",
      },
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      await waitForSheet("모든 지역 3건");
      // 검색창은 지역·혜택 검색 칸을 열고, 칸 끝 '모두 보기'가 그 말이 든 정책만 지도 · 목록에 남긴다
      // - 셋 다 "할인"이라 다 남는다
      const searchInput = screen.getByPlaceholderText("정책명, 지역, 혜택 검색");
      await user.type(searchInput, "할인");
      await user.click(await screen.findByRole("button", { name: "‘할인’ 들어간 정책 3건 모두 보기 ›" }));
      await waitFor(() => expect(conditionsLine()).toBe("‘할인’ 검색"));
      await waitForSheet("모든 지역 3건");
      expectStillOnMap();

      // 다른 말로 다시 찾으면 그 말로 바뀐다
      await user.type(screen.getByPlaceholderText("정책명, 지역, 혜택 검색"), "부산");
      await user.click(await screen.findByRole("button", { name: "‘부산’ 들어간 정책 1건 모두 보기 ›" }));
      await waitFor(() => expect(conditionsLine()).toBe("‘부산’ 검색"));
      await waitForSheet("모든 지역 1건");
      expect(document.body).toHaveTextContent("부산 숙박 5만원 할인");
      expect(document.body).not.toHaveTextContent("강릉 KTX 할인");
      expectStillOnMap();
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("reads an old filter link as the map selection instead of the old list", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "jeonnam", slug: "jeonnam", title: "전남 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "jeju", slug: "jeju", title: "제주 혜택", region: "제주" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      // 예전 지역 필터 주소(region=)는 지도에서 그 지역을 고른 것과 같다. 예전 카테고리(category=)는 버린다
      renderAppRoute(`/policies?region=${encodeURIComponent("전남")}&category=${encodeURIComponent("여행상품")}`);
      await waitForSheet("전남 1건");
      expectStillOnMap();
      expect(screen.getByRole("button", { name: "필터 열기" })).toHaveTextContent(/^필터$/);
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("renders collected TravelMonth benefits in the policy list", async () => {
    const collectedPolicy: Policy = {
      id: "travelmonth-58",
      slug: "travelmonth-58",
      label: "부산",
      tag: "최대 2만원",
      title: "부산 공식 캐시백",
      org: "부산관광공사",
      region: "부산",
      deadline: "2026-06-30",
      amount: "최대 2만원",
      summary: "부산 공식 캐시백 상품 할인",
      match: 80,
      category: "지역할인",
      requirements: ["공식 안내에서 신청 조건을 확인하세요."],
      documents: ["혜택 안내 확인"],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue([collectedPolicy]);
    const savePolicySpy = vi.spyOn(appDataApi, "savePolicy");

    try {
      await login();
      cleanup();
      renderAppRoute("/policies?place=부산");
      // 지도 목록 한 줄
      await waitForSheet("부산 1건");
      expect(getLink("/policies/travelmonth-58")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("부산 공식 캐시백");
      expect(document.body).not.toHaveTextContent("공식 수집");
      expect(document.body).not.toHaveTextContent("external");
      expect(savePolicySpy).not.toHaveBeenCalled();
    } finally {
      listPoliciesSpy.mockRestore();
      savePolicySpy.mockRestore();
    }
  });

  it("opens the policy trip picker, attaches a policy, and links to the selected trip", async () => {
    const previewTrip = getUpcomingPreviewTrip();
    const user = userEvent.setup();
    const loginSpy = vi
      .spyOn(appDataApi, "login")
      .mockResolvedValue({ accessToken: "test-token", user: getPreviewUser() });
    const refreshSpy = vi
      .spyOn(appDataApi, "refreshSession")
      .mockResolvedValue({ accessToken: "test-token", user: getPreviewUser() });
    const profileSpy = vi
      .spyOn(appDataApi, "getProfile")
      .mockResolvedValue({ preferredRegions: ["부산"], style: "휴식", budget: "20만원" });
    const savedPolicySpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockResolvedValue([]);
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(examplePolicyDetail);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([previewTrip]);
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: previewTrip.id,
        policyId: examplePolicySlug,
        added: true,
      });
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue({ ...previewTrip, linkedPolicies: [] });

    try {
      renderAppRoute("/login");
      await user.type(
        document.querySelector('input[name="email"]') as HTMLInputElement,
        testEmail,
      );
      await user.type(
        document.querySelector('input[name="password"]') as HTMLInputElement,
        testPassword,
      );
      await user.click(document.querySelector('button[type="submit"]') as HTMLButtonElement);

      await waitFor(() => expect(getLink("/policies")).toBeInTheDocument());
      cleanup();
      renderAppRoute(examplePolicyPath);

      // 하단 고정 바가 없어지고 액션이 본문 상단으로 올라갔다 - 자리가 아니라 이름으로 찾는다
      const addButton = await screen.findByRole("button", { name: /내 일정에 담기/ });
      await user.click(addButton);

      const row = await waitFor(() => {
        const tripRow = document.querySelector(".trip-select-row");
        expect(tripRow).toBeTruthy();
        return tripRow as HTMLButtonElement;
      });
      await user.click(row);

      await screen.findByText(`${examplePolicyTitle}을 부산 여행 1에 담았어요`);
      expect(screen.getByText("부산 여행 1에서 연결된 정책을 확인할 수 있어요.")).toBeInTheDocument();
      expect(addPolicyToTripSpy).toHaveBeenCalledWith(previewTrip.id, examplePolicySlug);

      await user.click(screen.getByRole("button", { name: "일정에서 보기" }));

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(within(linkedRegion).getByText(examplePolicyTitle)).toBeInTheDocument();
    } finally {
      loginSpy.mockRestore();
      refreshSpy.mockRestore();
      profileSpy.mockRestore();
      savedPolicySpy.mockRestore();
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("passes a title-local municipality to new-trip creation for digital resident policies", async () => {
    const dgtourPolicy: Policy = {
      ...examplePolicyDetail,
      id: "dgtour-yeonggwang",
      slug: "dgtour-yeonggwang",
      title: "영광 디지털관광주민증 혜택",
      org: "한국관광공사",
      region: "전남",
      sourceType: "internal",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(dgtourPolicy);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([{ ...getUpcomingPreviewTrip(), id: "301", title: "기존 전남 일정" }]);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/dgtour-yeonggwang");

      await userEvent.setup().click(
        await screen.findByRole("button", {
          name: /내 일정에 담기|일정에 담김/,
        }),
      );

      expect(await screen.findByRole("link", { name: "새 일정에 담기" })).toHaveAttribute(
        "href",
        "/trips/new?policySlug=dgtour-yeonggwang&region=%EC%98%81%EA%B4%91&sido=%EC%A0%84%EB%82%A8",
      );
    } finally {
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });

  it("shows only trips that have not ended in the policy trip picker", async () => {
    const trips: Trip[] = [
      {
        ...getPreviewTrip(),
        id: "200",
        title: "지난 제주 여행",
        days: { 1: [] },
      },
      {
        ...getUpcomingPreviewTrip(),
        id: "201",
        title: "부산 야호",
        dates: "2026.07.04 - 07.08",
        days: { 1: [] },
      },
      {
        ...getUpcomingPreviewTrip(),
        id: "202",
        title: "경주 야호",
        dates: "2026.05.18 - 05.20",
        days: { 1: [] },
      },
    ];
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue(trips);

    // 정책 상세가 실제 DB 행을 읽으면 그 슬러그가 아래 링크 기대값과 어긋난다.
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(examplePolicyDetail);

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);

      await userEvent.setup().click(
        await screen.findByRole("button", {
          name: /내 일정에 담기|일정에 담김/,
        }),
      );
      await screen.findByText("부산 야호");
      expect(screen.getByText("경주 야호")).toBeInTheDocument();
      // 끝난 여행(2026-06)은 담을 곳으로 보이지 않는다.
      expect(screen.queryByText("지난 제주 여행")).not.toBeInTheDocument();
      expect(document.querySelectorAll(".trip-select-row")).toHaveLength(2);
      expect(screen.getByRole("link", { name: "새 일정에 담기" })).toHaveAttribute(
        "href",
        `/trips/new?policySlug=${encodeURIComponent("dgtour-영광")}&region=%EC%98%81%EA%B4%91&sido=%EC%A0%84%EB%82%A8`,
      );
    } finally {
      listTripsSpy.mockRestore();
      getPolicySpy.mockRestore();
    }
  });

  it("keeps the trip-attached state scoped to the selected policy", async () => {
    const originalGetPolicy = appDataApi.getPolicy.bind(appDataApi);
    const previewTrip = {
      ...getUpcomingPreviewTrip(),
      id: "policy-scope-trip",
      title: "제주 3일 여행",
    };
    const otherPolicy: Policy = {
      id: "city-pass",
      slug: "city-pass",
      label: "CP",
      tag: "추천",
      title: "도시 여행 패스",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "다른 정책 상세 CTA 상태를 확인하기 위한 정책입니다.",
      match: 72,
      category: "지역할인",
      requirements: ["국내 여행자"],
      documents: ["신분증"],
      officialUrl: null,
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockImplementation((slug) =>
        slug === "city-pass"
          ? Promise.resolve(otherPolicy)
          : originalGetPolicy(slug),
      );
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([previewTrip]);
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: previewTrip.id,
        policyId: examplePolicySlug,
        added: true,
      });
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(previewTrip);

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter initialEntries={[examplePolicyPath]}>
          <AppProviders>
            <App />
            <Link to="/policies/city-pass">다른 정책 테스트 이동</Link>
          </AppProviders>
        </MemoryRouter>,
      );

      const user = userEvent.setup();
      await user.click(
        await screen.findByRole("button", { name: /내 일정에 담기/ }),
      );
      await user.click(
        await screen.findByRole("button", { name: /제주 3일 여행/ }),
      );
      await waitFor(() =>
        expect(document.querySelector(".toast")).toBeTruthy(),
      );
      await user.click(
        screen.getByRole("link", { name: "다른 정책 테스트 이동" }),
      );

      await waitFor(() =>
        expect(screen.getByText("도시 여행 패스")).toBeInTheDocument(),
      );
      expect(
        screen.getByRole("button", { name: /내 일정에 담기/ }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "일정에 담김" }),
      ).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
      getTripSpy.mockRestore();
    }
  });

  it("keeps the map screen state in the URL so back from a policy returns to it", async () => {
    const mapPolicies: Policy[] = [
      { ...examplePolicyDetail, id: "map-jeonnam", slug: "map-jeonnam", title: "전남 해안 혜택", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(mapPolicies);
    const mapRegion = (name: string) =>
      document.querySelector(`.thmap-rg[data-region="${name}"]`) as SVGGElement | null;

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      // 지도 → 지역 선택 → 한 페이지. 셋 다 URL 에 남는다
      await waitFor(() => expect(mapRegion("전남")).toBeTruthy());
      await user.click(mapRegion("전남") as SVGGElement);
      await waitForSheet("전남 1건");
      await user.click(screen.getByRole("button", { name: "목록 펼치기" }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("sheet")).toBe("full"));

      // 목록 줄로 들어갔다 뒤로 오면 지도 처음이 아니라 이 목록으로 돌아온다
      await user.click(document.querySelector(".thmap-row-link") as HTMLElement);
      await waitFor(() => expect(routeLocation().pathname).toBe("/policies/map-jeonnam"));
      goBack();
      await waitFor(() => expect(routeLocation().pathname).toBe("/policies"));
      await waitForSheet("전남 1건");
      expect(document.querySelector(".thmap-sheet")).toHaveClass("thmap-at-full");

      // 뒤로는 한 층씩: 한 페이지 → 반반 → (화면 안 ‹) 모든 지역
      goBack();
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("sheet")).toBeNull());
      expect(document.querySelector(".thmap-sheet")).toHaveClass("thmap-at-mid");
      await user.click(screen.getByRole("button", { name: "뒤로" }));
      await waitForSheet("모든 지역 1건");
      expect(new URLSearchParams(routeLocation().search).get("place")).toBeNull();
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("opens the same screen straight from the URL", async () => {
    const mapPolicies: Policy[] = [
      { ...examplePolicyDetail, id: "map-jeonnam", slug: "map-jeonnam", title: "전남 해안 혜택", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(mapPolicies);
    try {
      await login();
      cleanup();
      // 새로고침·북마크도 같은 길을 쓴다. 예전 '지역 목록 화면' 주소(view=list)는 한 페이지 목록으로 연다
      renderAppRoute("/policies?place=전남&view=list");
      await waitForSheet("전남 1건");
      expect(document.querySelector(".thmap-sheet")).toHaveClass("thmap-at-full");
      expect(document.body).toHaveTextContent("전남 해안 혜택");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("drops the region and opens one page when the 교통 chip is picked, since transport is nationwide", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "yg", slug: "yg", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "rail", slug: "rail", title: "내일로패스 할인", region: "전국", category: "교통" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    try {
      await login();
      cleanup();
      renderAppRoute("/policies?place=전남");
      await waitForSheet("전남 1건");
      const user = userEvent.setup();
      await user.click(within(screen.getByRole("group", { name: "혜택 형태" })).getByRole("button", { name: /^교통/ }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("type")).toBe("move"));
      const params = new URLSearchParams(routeLocation().search);
      expect(params.get("place")).toBeNull();
      expect(params.get("sheet")).toBe("full");
      await waitForSheet("모든 지역 1건");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("finds a city from the magnifier, lists only it, and steps back one layer at a time", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "yg", slug: "yg", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
      { ...examplePolicyDetail, id: "wd", slug: "wd", title: "[완도] 디지털관광주민증 혜택", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      await waitForSheet("모든 지역 2건");
      const user = userEvent.setup();
      // 검색창은 맨 위 하나 - 누르면 지역·혜택 검색 칸이 열리고 '필터' 자리에 '닫기'
      const searchbox = screen.getByRole("searchbox", { name: "정책 검색" });
      await user.click(searchbox);
      const panel = await screen.findByRole("region", { name: "지역·혜택 검색 결과" });
      expect(screen.queryByRole("button", { name: "지역·혜택 검색" })).toBeNull();
      expect(screen.queryByRole("button", { name: "필터 열기" })).toBeNull();
      expect(screen.getByRole("button", { name: "닫기" })).toBeInTheDocument();
      // 비워 두면 지역 사진 칸 - 혜택 많은 순
      expect(within(panel).getAllByRole("button", { pressed: false })[0]).toHaveTextContent("전라남도혜택 2건");
      await user.type(searchbox, "완도");
      await user.click(within(panel).getByRole("button", { name: /완도.*전남 · 혜택 1건/ }));
      await waitForSheet("완도 1건");
      expect(screen.queryByRole("region", { name: "지역·혜택 검색 결과" })).toBeNull();
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();
      const params = new URLSearchParams(routeLocation().search);
      expect([params.get("place"), params.get("city")]).toEqual(["전남", "완도"]);
      expect(screen.getByRole("button", { name: "전남 전체" })).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "뒤로" }));
      await waitForSheet("전남 2건");
      await user.click(screen.getByRole("button", { name: "뒤로" }));
      await waitForSheet("모든 지역 2건");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("on wide screens keeps the list in a panel beside the map and opens a policy there", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "yg", slug: "yg", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([{ ...getUpcomingPreviewTrip(), id: "301", title: "전남 담기 여행" }]);
    const panelList = () => document.querySelector(".thmap-panel-list");
    stubDesktop();
    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      await waitForSheet("모든 지역 1건");
      const user = userEvent.setup();
      // 목록은 지도 오른쪽 패널에 늘 서 있다 - 끌 손잡이도 펼치기 단추도 없다
      expect(document.querySelector(".prototype-policy-list-screen")).toHaveClass("desktop-wide");
      expect(document.querySelector(".thmap-split .thmap-panel .thmap-sheet")).toHaveClass("thmap-at-panel");
      expect(document.querySelector(".thmap-handle")).toBeNull();
      expect(screen.queryByRole("button", { name: "목록 펼치기" })).toBeNull();

      // 지역을 고르면 요약 카드와 시군 점(다가가지는 않는다 - PolicyRegionMap 시험)
      await user.click(document.querySelector('.thmap-rg[data-region="전남"]') as SVGGElement);
      await waitForSheet("전남 1건");
      expect(document.querySelector('.thmap-dot[data-place="영광"]')).toBeTruthy();

      // 줄을 누르면 패널이 그 정책의 상세가 된다. 주소에 남아 뒤로가 목록으로 돌아온다
      await user.click(document.querySelector(".thmap-row-link") as HTMLElement);
      const detail = await screen.findByRole("region", { name: /상세$/ });
      expect(routeLocation().pathname).toBe("/policies");
      expect(new URLSearchParams(routeLocation().search).get("detail")).toBe("yg");
      expect(panelList()).toHaveAttribute("inert");
      // 초점은 상세의 ‹ 로 갔다가, 목록으로 돌아오면 연 줄로 돌아온다
      expect(within(detail).getByRole("button", { name: "목록으로" })).toHaveFocus();
      expect(within(detail).getByRole("link", { name: "크게 보기" })).toHaveAttribute("href", "/policies/yg");
      // 주 버튼은 지도 화면을 떠나지 않고 일정 고르기 창을 바로 연다. 창은 패널 밖(body)에 뜬다
      await user.click(within(detail).getByRole("button", { name: "내 일정에 담기" }));
      const tripWindow = await screen.findByRole("dialog", { name: "일정 선택" });
      expect(tripWindow.closest(".policy-trip-window")).toBeTruthy();
      expect(tripWindow.closest(".thmap-panel")).toBeNull();
      expect(await within(tripWindow).findByText("전남 담기 여행")).toBeInTheDocument();
      expect(routeLocation().pathname).toBe("/policies");
      await user.click(within(tripWindow).getByRole("button", { name: "닫기" }));
      await waitFor(() => expect(screen.queryByRole("dialog", { name: "일정 선택" })).toBeNull());
      await user.click(within(detail).getByRole("button", { name: "목록으로" }));
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("detail")).toBeNull());
      expect(screen.queryByRole("region", { name: /상세$/ })).toBeNull();
      expect(panelList()).not.toHaveAttribute("inert");
      expect(document.querySelector(".thmap-row-link")).toHaveFocus();
      await waitForSheet("전남 1건");

      await user.click(document.querySelector(".thmap-row-link") as HTMLElement);
      await screen.findByRole("region", { name: /상세$/ });
      goBack();
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("detail")).toBeNull());
      await waitForSheet("전남 1건");

      // 맨 위 검색창의 지역·혜택 검색 칸도 패널 안에서 열린다
      await user.click(screen.getByRole("searchbox", { name: "정책 검색" }));
      const search = await screen.findByRole("region", { name: "지역·혜택 검색 결과" });
      expect(search.closest(".thmap-panel")).toBeTruthy();
      expect(panelList()).toHaveAttribute("inert");
    } finally {
      vi.unstubAllGlobals();
      policyListSpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });

  it("sends a wide-screen panel address to the policy page on a phone", async () => {
    const policies: Policy[] = [
      { ...examplePolicyDetail, id: "yg", slug: "yg", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
    ];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    try {
      await login();
      cleanup();
      renderAppRoute("/policies?place=전남&detail=yg");
      await waitFor(() => expect(routeLocation().pathname).toBe("/policies/yg"));
    } finally {
      policyListSpy.mockRestore();
    }
  });
});
