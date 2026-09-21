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
  getPreviewUser,
  testEmail,
  testIsoDateFromToday,
  testPassword,
} from "../../test/fixtures";
import { getLink, goBack, login, renderAppRoute, routeLocation } from "../../test/renderAppRoute";

/* 지도 화면엔 지도 밑 목록이 없다(시안 그대로). 카드는 시트 손잡이 → 타일을 거쳐야 보인다.
   타일 이름은 "경남 1건 · …" 꼴 - 지도의 "경남 정책 1건" 버튼과 구분하려고 지역 뒤에 숫자를 건다. */
async function openSheetTile(user: ReturnType<typeof userEvent.setup>, tile: RegExp) {
  const grab = await waitFor(() => {
    const button = document.querySelector(".thmap-grab");
    expect(button).toBeTruthy();
    return button as HTMLButtonElement;
  });
  await user.click(grab);
  const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
  await user.click(within(sheet).getByRole("button", { name: tile }));
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

  it("filters policies from the unified filter sheet after applying", async () => {
    const policies: Policy[] = [
      examplePolicyDetail,
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
    ];
    const listPoliciesSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue(policies);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      // 지도 화면 - 카드는 없고 건수 줄과 지도만 있다
      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 3개 중 3개 표시"),
      );
      expect(document.querySelector(".thmap-host")).toBeTruthy();
      expect(screen.queryByText("강릉 숙박 할인권")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      await user.click(within(filterDialog).getByRole("button", { name: "지역할인" }));
      // 초안은 적용 전이라 건수가 그대로다
      expect(document.body).toHaveTextContent("전체 3개 중 3개 표시");
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

      await waitFor(() =>
        expect(document.body).toHaveTextContent("부산 카드 캐시백"),
      );
      expect(screen.queryByText("강릉 숙박 할인권")).not.toBeInTheDocument();

      // 카테고리 필터가 걸리면 목록 화면. 화면 위 초기화 버튼은 걷어냈으니 시트에서 푼다
      expect(document.querySelector(".thmap-host")).toBeNull();
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "초기화" }));
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));
      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 3개 중 3개 표시"),
      );
      expect(document.querySelector(".thmap-host")).toBeTruthy();
      expect(screen.queryByText("부산 카드 캐시백")).not.toBeInTheDocument();
    } finally {
      listPoliciesSpy.mockRestore();
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
      renderAppRoute("/policies");
      await openSheetTile(userEvent.setup(), /^경남\s*\d/);

      expect(await screen.findByText("[밀양] 디지털관광주민증 혜택")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("상시 발급");
      expect(document.body).toHaveTextContent("경남 · 제휴처별 운영기간 확인");
      expect(document.body).not.toHaveTextContent("마감일 확인 필요");
      expect(document.body).not.toHaveTextContent("경남 · ~");
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
      renderAppRoute("/policies");
      // 전국 정책은 지역 타일에 섞이지 않는다 - 홈 '전국 혜택' 카드 몫이다
      await openSheetTile(userEvent.setup(), /^강원\s*\d/);

      expect(await screen.findByText("기간 미확인 목록 정책")).toBeInTheDocument();
      expect(screen.queryByText("마감일만 확인된 목록 정책")).toBeNull();
      expect(document.body).not.toHaveTextContent("전국 · 2026.12.31 마감");
      expect(document.body).toHaveTextContent("강원");
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

      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 3개 중 3개 표시"),
      );
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      await user.click(within(filterDialog).getByRole("button", { name: "지역할인" }));
      expect(document.body).toHaveTextContent("전체 3개 중 3개 표시");

      await user.click(within(filterDialog).getByRole("button", { name: "필터 닫기" }));
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "정책 필터" })).not.toBeInTheDocument(),
      );

      // 초안을 버렸으니 지도 화면 그대로, 건수도 그대로
      expect(document.body).toHaveTextContent("전체 3개 중 3개 표시");
      expect(document.querySelector(".thmap-host")).toBeTruthy();
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      expect(within(filterDialog).getByRole("button", { name: "부산" })).not.toHaveClass("active");
      expect(within(filterDialog).getByRole("button", { name: "지역할인" })).not.toHaveClass("active");
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

      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 12개 중 12개 표시"),
      );
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      const regionFilter = within(filterDialog).getByRole("group", { name: "지역 필터" });

      expect(within(filterDialog).getByText("수도권")).toBeInTheDocument();
      expect(within(filterDialog).getByText("전라")).toBeInTheDocument();
      expect(within(filterDialog).queryByText("주요 지역")).not.toBeInTheDocument();
      expect(
        within(filterDialog).queryByRole("button", { name: "전체 지역 보기" }),
      ).not.toBeInTheDocument();

      await user.click(
        within(filterDialog).getByRole("button", { name: "광주" }),
      );
      expect(document.body).toHaveTextContent("전체 12개 중 12개 표시");
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

      // 지역 필터도 다른 필터와 같이 목록 화면으로 간다 - 지도는 필터를 안 비춘다
      await waitFor(() =>
        expect(document.body).toHaveTextContent("광주 지역 혜택"),
      );
      // 전국 정책은 지도 선택 결과에만 더한다. 목록 지역 필터는 선택한 지역과 정확히 일치해야 한다.
      expect(document.body).toHaveTextContent("전체 12개 중 1개 표시");
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
      // 지도 화면엔 카드가 없다 - 선택은 안내 줄과 알약으로 보인다
      expect(document.querySelectorAll(".policy-list-card")).toHaveLength(0);

      // 지역을 눌러도 필터는 그대로다 - URL 도 건수도 안 바뀐다
      await user.click(mapRegion("전남") as SVGGElement);
      await waitFor(() => expect(mapRegion("전남")?.classList.contains("thmap-on")).toBe(true));
      expect(document.body).toHaveTextContent("전남 선택됨 · 표시를 누르면 목록으로");
      expect(screen.getByRole("button", { name: "전남 정책 1건 보기" })).toBeInTheDocument();
      // 고른 지역은 URL 에 남는다(뒤로가기 복원용). 필터 파라미터는 여전히 안 붙는다
      expect(new URLSearchParams(routeLocation().search).get("place")).toBe("전남");
      expect(new URLSearchParams(routeLocation().search).get("region")).toBeNull();
      expect(document.body).toHaveTextContent("전체 2개 중 2개 표시");
      expect(screen.queryByRole("button", { name: "필터 초기화" })).not.toBeInTheDocument();

      await user.click(mapRegion("광주") as SVGGElement);
      await waitFor(() => expect(mapRegion("광주")?.classList.contains("thmap-on")).toBe(true));
      expect(mapRegion("전남")?.classList.contains("thmap-on")).toBe(false);
      await waitFor(() => expect(screen.getByRole("button", { name: "광주 정책 1건 보기" })).toBeInTheDocument());
      expect(screen.queryByRole("button", { name: "전남 정책 1건 보기" })).not.toBeInTheDocument();
      expect(new URLSearchParams(routeLocation().search).get("place")).toBe("광주");

      // 지도 아래 안내 줄과, 솟은 지역 머리 위 알약. 알약을 누르면 지도가 내려가고 지역 목록이 된다
      expect(document.body).toHaveTextContent("광주 선택됨 · 표시를 누르면 목록으로");
      await user.click(screen.getByRole("button", { name: "광주 정책 1건 보기" }));
      await waitFor(() => expect(document.querySelector(".thmap-host")).toBeNull());
      expect(screen.getByRole("heading", { level: 2, name: "광주" })).toBeInTheDocument();
      expect(document.body).toHaveTextContent("정책 1건 · 시·군 0곳");
      expect(document.body).toHaveTextContent("광주 도심 혜택");
      expect(screen.queryByText("전남 해안 혜택")).not.toBeInTheDocument();
      // 목록 화면에서는 시트가 없다 - 목록 위에 겹치면 안 된다
      expect(document.querySelector(".thmap-sheet")).toBeNull();
      await user.click(screen.getByRole("button", { name: "지도로" }));
      await waitFor(() => expect(document.querySelector(".thmap-host")).toBeTruthy());
      expect(mapRegion("광주")?.classList.contains("thmap-on")).toBe(true);
      // 지도 화면으로 돌아오면 시트가 손잡이만 내민 채 대기한다
      const grab = screen.getAllByRole("button").find((button) => button.classList.contains("thmap-grab"));
      expect(grab?.textContent?.replace(/\s+/g, "")).toBe("정책2건·시도2곳");
      expect(grab).toHaveAttribute("aria-expanded", "false");

      // 지도 밖 빈 곳을 누르면 선택이 풀린다
      await user.click(document.querySelector(".thmap-wrap") as HTMLElement);
      await waitFor(() => expect(mapRegion("광주")?.classList.contains("thmap-on")).toBe(false));
      expect(document.body).toHaveTextContent("지역을 누르면 그곳 정책을 모아 봅니다");
      expect(document.body).toHaveTextContent("전체 2개 중 2개 표시");
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("caps the map marker at three lines and folds the rest into one line", async () => {
    // 한 지역에 정책 종류가 넷이면 지도 위 표시가 네 줄이 된다 - 지도를 가리면 안 된다
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

      await waitFor(() => expect(document.querySelector(".thmap-pill")).toBeTruthy());
      // 큰 둘만 이름을 적고 나머지 둘은 한 줄로 묶는다
      expect(document.querySelectorAll(".thmap-pill-row")).toHaveLength(2);
      expect(screen.getByText("디지털관광주민증 혜택")).toBeInTheDocument();
      expect(screen.getByText("대한민국 반값여행 지원")).toBeInTheDocument();
      const more = document.querySelector(".thmap-pill-more") as HTMLElement;
      expect(more.textContent?.replace(/\s+/g, "")).toBe("외2종2건");
      expect(screen.queryByText("남도 기차 여행 할인")).not.toBeInTheDocument();
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("renders unified filter sheet controls and compact cards", async () => {
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

      // 제목 줄(정책 탐색 + ♡ 관심)은 걷어냈다 - 화면엔 안 보이고 낭독기용 h1 만 남는다
      await waitFor(() =>
        expect(screen.getByRole("heading", { level: 1, name: "정책 탐색" })).toBeInTheDocument(),
      );
      expect(document.body).not.toHaveTextContent("♡ 관심");
      expect(screen.getByRole("button", { name: "필터 열기" })).toBeInTheDocument();
      expect(screen.queryByText("정책 탐색 바로가기")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      const categoryFilter = within(filterDialog).getByRole("group", { name: "카테고리 필터" });
      expect(within(categoryFilter).getByRole("button", { name: "전체" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "교통" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "숙박" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "여행상품" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "지역할인" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "이벤트" })).toBeInTheDocument();
      expect(within(categoryFilter).getByRole("button", { name: "기타" })).toBeInTheDocument();

      await user.click(within(categoryFilter).getByRole("button", { name: "지역할인" }));
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

      await waitFor(() =>
        expect(document.body).toHaveTextContent("부산 카드 캐시백"),
      );
      expect(document.body).toHaveTextContent("부산 카드 캐시백");
      expect(document.body).toHaveTextContent(examplePolicyTitle);
      expect(screen.queryByText("강릉 숙박 할인권")).not.toBeInTheDocument();
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

      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 3개 중 3개 표시"),
      );
      // 검색어가 들어가면 지도 화면이 목록 화면으로 바뀐다 - 셋 다 "할인"이라 다 남는다
      const searchInput = screen.getByPlaceholderText("정책명, 지역, 혜택 검색");
      await user.type(searchInput, "할인");
      await waitFor(() =>
        expect(document.querySelector(".policy-list-card:first-child a")?.textContent).toContain("강릉 KTX 할인"),
      );
      expect(document.body).toHaveTextContent("전체 3개 중 3개 표시");
      expect(document.querySelector(".thmap-host")).toBeNull();

      await user.clear(searchInput);
      await user.type(searchInput, "부산");

      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 3개 중 1개 표시"),
      );
      expect(document.body).toHaveTextContent("부산 숙박 5만원 할인");
      expect(document.body).not.toHaveTextContent("강릉 KTX 할인");
    } finally {
      listPoliciesSpy.mockRestore();
    }
  });

  it("shows matching policies for transport and travel product categories from the sheet", async () => {
    const transportPolicy: Policy = {
      id: "transport-policy",
      slug: "transport-policy",
      label: "TR",
      tag: "교통",
      title: "남도 기차둘레길 1박 2일 최대 35% 할인행사",
      org: "한국관광공사",
      region: "전남",
      deadline: "2026-05-31",
      amount: "최대 35%",
      summary: "남도 기차 여행상품 할인",
      match: 90,
      category: "교통",
      requirements: [],
      documents: [],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const packagePolicy: Policy = {
      id: "package-policy",
      slug: "package-policy",
      label: "PK",
      tag: "여행상품",
      title: "K리그 지역 원정 경기 관람 및 체류여행 패키지 할인",
      org: "한국관광공사",
      region: "전국",
      deadline: "2026-05-31",
      amount: "할인",
      summary: "체류여행 패키지 할인",
      match: 88,
      category: "여행상품",
      requirements: [],
      documents: [],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const policyListSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue([transportPolicy, packagePolicy]);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.body).toHaveTextContent("전체 2개 중 2개 표시"),
      );
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "교통" }));
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));
      expect(document.body).toHaveTextContent(
        "남도 기차둘레길 1박 2일 최대 35% 할인행사",
      );
      expect(
        screen.queryByText("K리그 지역 원정 경기 관람 및 체류여행 패키지 할인"),
      ).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "여행상품" }));
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));
      expect(document.body).toHaveTextContent(
        "K리그 지역 원정 경기 관람 및 체류여행 패키지 할인",
      );
      expect(
        screen.queryByText("남도 기차둘레길 1박 2일 최대 35% 할인행사"),
      ).not.toBeInTheDocument();
    } finally {
      policyListSpy.mockRestore();
    }
  });

  it("restores the policy category tab from the URL", async () => {
    const transportPolicy: Policy = {
      id: "transport-policy",
      slug: "transport-policy",
      label: "TR",
      tag: "교통",
      title: "남도 기차둘레길 1박 2일 최대 35% 할인행사",
      org: "한국관광공사",
      region: "전남",
      deadline: "2026-05-31",
      amount: "최대 35%",
      summary: "남도 기차 여행상품 할인",
      match: 90,
      category: "교통",
      requirements: [],
      documents: [],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const packagePolicy: Policy = {
      id: "jeju-city-tour",
      slug: "jeju-city-tour",
      label: "JEJU",
      tag: "여행상품",
      title: "제주시티투어버스 1일 탑승권 33% 할인",
      org: "한국관광공사",
      region: "제주",
      deadline: "2026-05-31",
      amount: "33%",
      summary: "제주시티투어버스 탑승권 할인",
      match: 88,
      category: "여행상품",
      requirements: [],
      documents: [],
      officialUrl: "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
      applyUrl: null,
      sourceType: "external",
    };
    const policyListSpy = vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue([transportPolicy, packagePolicy]);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies?category=여행상품");

      await waitFor(() =>
        expect(document.body).toHaveTextContent(
          "제주시티투어버스 1일 탑승권 33% 할인",
        ),
      );
      // 필터 요약 칸을 걷어냈다 - 걸린 필터 개수는 필터 버튼이 단다
      expect(screen.getByText("필터 1")).toBeInTheDocument();
      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: "필터 열기" }));
      const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      expect(within(filterDialog).getByRole("button", { name: "여행상품" })).toHaveClass(
        "active",
      );
      expect(
        screen.queryByText("남도 기차둘레길 1박 2일 최대 35% 할인행사"),
      ).not.toBeInTheDocument();
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
      renderAppRoute("/policies");
      await openSheetTile(userEvent.setup(), /^부산\s*\d/);

      await waitFor(() =>
        expect(getLink("/policies/travelmonth-58")).toBeInTheDocument(),
      );
      expect(document.body).toHaveTextContent("부산 공식 캐시백");
      expect(document.body).not.toHaveTextContent("공식 수집");
      expect(document.body).not.toHaveTextContent("external");
      expect(
        screen.getByRole("button", { name: /부산 공식 캐시백 즐겨찾기/ }),
      ).toBeInTheDocument();
      expect(savePolicySpy).not.toHaveBeenCalled();
    } finally {
      listPoliciesSpy.mockRestore();
      savePolicySpy.mockRestore();
    }
  });

  it("opens the policy trip picker, attaches a policy, and links to the selected trip", async () => {
    const previewTrip = getPreviewTrip();
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
      .mockResolvedValue([{ ...getPreviewTrip(), id: "301", title: "기존 전남 일정" }]);

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

  it("shows all saved trips in the policy trip picker", async () => {
    const trips: Trip[] = [
      {
        ...getPreviewTrip(),
        id: "201",
        title: "부산 야호",
        dates: "2026.07.04 - 07.08",
        days: { 1: [] },
      },
      {
        ...getPreviewTrip(),
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
      ...getPreviewTrip(),
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

      // 지도 → 지역 선택 → 목록. 둘 다 URL 에 남아 뒤로가기가 한 단계씩 되짚는다
      await waitFor(() => expect(mapRegion("전남")).toBeTruthy());
      await user.click(mapRegion("전남") as SVGGElement);
      await user.click(await screen.findByRole("button", { name: "전남 정책 1건 보기" }));
      expect(await screen.findByRole("heading", { level: 2, name: "전남" })).toBeInTheDocument();
      expect(new URLSearchParams(routeLocation().search).get("view")).toBe("list");

      // 카드로 들어갔다 뒤로 오면 지도 홈이 아니라 이 목록으로 돌아온다
      await user.click(document.querySelector(".policy-list-card-link") as HTMLElement);
      await waitFor(() => expect(routeLocation().pathname).toBe("/policies/map-jeonnam"));
      goBack();
      await waitFor(() => expect(routeLocation().pathname).toBe("/policies"));
      expect(await screen.findByRole("heading", { level: 2, name: "전남" })).toBeInTheDocument();
      expect(document.querySelector(".thmap-host")).toBeNull();

      // 한 번 더 뒤로 가면 지도로
      goBack();
      await waitFor(() => expect(document.querySelector(".thmap-host")).toBeTruthy());
      expect(new URLSearchParams(routeLocation().search).get("view")).toBeNull();
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
      // 새로고침·북마크도 같은 길을 쓴다
      renderAppRoute("/policies?place=전남&view=list");
      expect(await screen.findByRole("heading", { level: 2, name: "전남" })).toBeInTheDocument();
      expect(document.querySelector(".thmap-host")).toBeNull();
      expect(document.body).toHaveTextContent("전남 해안 혜택");
    } finally {
      policyListSpy.mockRestore();
    }
  });
});
