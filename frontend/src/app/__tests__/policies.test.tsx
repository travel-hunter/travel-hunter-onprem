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
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — policies & trip picker", () => {
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

      await waitFor(() =>
        expect(document.body).toHaveTextContent(examplePolicyTitle),
      );
      expect(document.body).toHaveTextContent("강릉 숙박 할인권");
      expect(document.body).toHaveTextContent("부산 카드 캐시백");

      await user.click(screen.getByRole("button", { name: /^필터/ }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      await user.click(within(filterDialog).getByRole("button", { name: "지역할인" }));
      expect(document.body).toHaveTextContent("강릉 숙박 할인권");
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

      await waitFor(() =>
        expect(document.body).toHaveTextContent("부산 카드 캐시백"),
      );
      expect(screen.queryByText("강릉 숙박 할인권")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "초기화" }));
      await waitFor(() =>
        expect(document.body).toHaveTextContent(examplePolicyTitle),
      );
      expect(document.body).toHaveTextContent("강릉 숙박 할인권");
      expect(getLink(examplePolicyPath)).toBeInTheDocument();
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
        expect(document.body).toHaveTextContent(examplePolicyTitle),
      );
      expect(document.body).toHaveTextContent("부산 카드 캐시백");
      expect(screen.getByRole("button", { name: /^필터/ })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^필터/ }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "부산" }));
      await user.click(within(filterDialog).getByRole("button", { name: "지역할인" }));
      expect(document.body).toHaveTextContent("강릉 숙박 할인권");

      await user.click(within(filterDialog).getByRole("button", { name: "필터 닫기" }));
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "정책 필터" })).not.toBeInTheDocument(),
      );

      expect(document.body).toHaveTextContent(examplePolicyTitle);
      expect(document.body).toHaveTextContent("부산 카드 캐시백");
      expect(document.body).toHaveTextContent("강릉 숙박 할인권");
      expect(screen.getByRole("button", { name: /^필터/ })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^필터/ }));
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
        expect(document.body).toHaveTextContent("전국 여행 할인"),
      );
      await user.click(screen.getByRole("button", { name: /^필터/ }));
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
      expect(document.body).toHaveTextContent("전국 여행 할인");
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

      await waitFor(() =>
        expect(document.body).toHaveTextContent("광주 지역 혜택"),
      );
      expect(screen.queryByText("전국 여행 할인")).not.toBeInTheDocument();
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

      await waitFor(() =>
        expect(document.body).toHaveTextContent("♡ 관심"),
      );
      expect(screen.getByRole("button", { name: /^필터/ })).toBeInTheDocument();
      expect(screen.queryByText("정책 탐색 바로가기")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^필터/ }));
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
      const firstPolicyLink = document.querySelector(
        ".policy-list-card:first-child a",
      );
      expect(firstPolicyLink?.textContent).toContain("강릉 KTX 할인");

      await user.type(
        screen.getByPlaceholderText("정책명, 지역, 혜택 검색"),
        "부산",
      );

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
        expect(document.body).toHaveTextContent("남도 기차둘레길"),
      );
      await user.click(screen.getByRole("button", { name: /^필터/ }));
      let filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
      await user.click(within(filterDialog).getByRole("button", { name: "교통" }));
      await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));
      expect(document.body).toHaveTextContent(
        "남도 기차둘레길 1박 2일 최대 35% 할인행사",
      );
      expect(
        screen.queryByText("K리그 지역 원정 경기 관람 및 체류여행 패키지 할인"),
      ).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^필터/ }));
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
      expect(document.body).toHaveTextContent("여행상품 · 기간 전체 · 금액 전체");
      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: /^필터/ }));
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

      const addButton = await waitFor(() => {
        const button = document.querySelector(".sticky-cta button");
        expect(button).toBeTruthy();
        return button as HTMLButtonElement;
      });
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
        `/trips/new?policySlug=${encodeURIComponent(examplePolicySlug)}&region=%EC%98%81%EA%B4%91&sido=%EC%A0%84%EB%82%A8`,
      );
    } finally {
      listTripsSpy.mockRestore();
    }
  });

  it("keeps the trip-attached state scoped to the selected policy", async () => {
    const originalGetPolicy = appDataApi.getPolicy.bind(appDataApi);
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
    }
  });
});
