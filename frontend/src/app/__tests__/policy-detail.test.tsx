import {
  cleanup,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type Policy,
  type Trip,
} from "../../api";
import {
  examplePolicyDetail,
  examplePolicyPath,
  examplePolicyTitle,
  getPreviewTrip,
  getPreviewUser,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — policy detail", () => {
  it("renders normalized official benefit detail with enabled save and trip controls", async () => {
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
      summary: "부산 야경투어 상품 할인",
      match: 80,
      category: "지역할인",
      requirements: ["공식 안내에서 신청 조건을 확인하세요."],
      documents: ["혜택 안내 확인"],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "201",
      title: "부산 공식 혜택 여행",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(collectedPolicy);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const savePolicySpy = vi
      .spyOn(appDataApi, "savePolicy")
      .mockResolvedValue({ policyId: "travelmonth-58", saved: true });
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        tripId: "201",
        policyId: "travelmonth-58",
        added: true,
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-58");
      const user = userEvent.setup();

      expect(
        await screen.findByRole("heading", { name: "부산 공식 캐시백" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "혜택 안내 보기" }),
      ).toHaveAttribute("href", collectedPolicy.officialUrl);
      expect(document.body).not.toHaveTextContent("공식 수집");
      const saveButton = screen.getByRole("button", { name: "저장" });
      const tripButton = screen.getByRole("button", {
        name: /내 일정에 담기|일정에 담김/,
      });
      expect(saveButton).not.toBeDisabled();
      expect(tripButton).not.toBeDisabled();
      await user.click(saveButton);
      await user.click(tripButton);
      await user.click(
        await screen.findByRole("button", { name: /부산 공식 혜택 여행/ }),
      );
      expect(savePolicySpy).toHaveBeenCalledWith("travelmonth-58");
      expect(listTripsSpy).toHaveBeenCalled();
      await waitFor(() =>
        expect(addPolicyToTripSpy).toHaveBeenCalledWith(
          "201",
          "travelmonth-58",
        ),
      );
    } finally {
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
      savePolicySpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
    }
  });



  it("renders structured detail sections when the policy provides structuredDetail", async () => {
    const structuredPolicy: Policy = {
      id: "structured-policy",
      slug: "structured-policy",
      label: "ST",
      tag: "구조화",
      title: "구조화 상세 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "기존 요약 fallback",
      match: 90,
      category: "지역할인",
      requirements: [],
      documents: ["기존 서류 fallback"],
      structuredDetail: {
        benefits: [{ title: "혜택", description: "숙박비를 최대 7만원 할인", amount: "최대 7만원" }],
        conditions: [{ title: "대상", description: "비수도권 숙박 예약자" }],
        periods: [{ title: "신청 기간", description: "2026-06-01 ~ 2026-07-31" }],
        links: [{ label: "공식 상세", url: "https://example.com/structured" }],
        documents: [],
        notices: [{ title: "주의", description: "예산 소진 시 조기 종료" }],
      },
      officialUrl: "https://example.com/official",
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(structuredPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/structured-policy");

      expect(await screen.findByRole("heading", { name: "구조화 상세 정책" })).toBeInTheDocument();
      expect(screen.getByText("최대 7만원")).toBeInTheDocument();
      expect(screen.getByText("2026-06-01 ~ 2026-07-31")).toBeInTheDocument();
      expect(screen.getByText("비수도권 숙박 예약자")).toBeInTheDocument();
      expect(screen.getByText("예산 소진 시 조기 종료")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /공식 상세/ })).toHaveAttribute("href", "https://example.com/structured");
      expect(screen.getByText("기존 서류 fallback")).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("falls back per section and ignores unsafe structured links", async () => {
    const mixedPolicy: Policy = {
      id: "mixed-structured-policy",
      slug: "mixed-structured-policy",
      label: "MX",
      tag: "구조화",
      title: "부분 구조화 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "기존 요약 fallback",
      match: 90,
      category: "지역할인",
      requirements: ["기존 조건 fallback"],
      documents: ["기존 서류 fallback"],
      structuredDetail: {
        benefits: [{ title: "혜택", description: "구조화 혜택" }],
        conditions: [],
        periods: [],
        links: [{ label: "위험 링크", url: "javascript:alert(1)" }],
        documents: [],
        notices: [],
      },
      officialUrl: "https://example.com/official",
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(mixedPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/mixed-structured-policy");

      expect(await screen.findByRole("heading", { name: "부분 구조화 정책" })).toBeInTheDocument();
      expect(screen.getByText("구조화 혜택")).toBeInTheDocument();
      expect(screen.getByText("기존 조건 fallback")).toBeInTheDocument();
      expect(screen.getByText("기존 서류 fallback")).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /위험 링크/ })).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("falls back legacy notice requirements when structured conditions are present", async () => {
    const mixedRequirementsPolicy: Policy = {
      id: "mixed-requirement-fallback",
      slug: "mixed-requirement-fallback",
      label: "MX",
      tag: "구조화",
      title: "조건 구조화와 확인사항 fallback 정책",
      org: "Travel Hunter",
      region: "전남",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "기존 요약 fallback",
      match: 90,
      category: "지역할인",
      requirements: ["공식 공지사항 필독", "모바일 지역화폐 결제"],
      documents: ["기존 서류 fallback"],
      structuredDetail: {
        benefits: [{ title: "혜택", description: "구조화 혜택" }],
        conditions: [{ title: "혜택 적용 조건", description: "구조화 결제 조건" }],
        periods: [],
        links: [],
        documents: [],
        notices: [],
      },
      officialUrl: "https://example.com/official",
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(mixedRequirementsPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/mixed-requirement-fallback");

      expect(await screen.findByRole("heading", { name: "조건 구조화와 확인사항 fallback 정책" })).toBeInTheDocument();
      const conditionCard = screen.getByRole("heading", { name: /혜택 적용 조건/ }).closest(".policy-requirement-group");
      expect(conditionCard).not.toBeNull();
      expect(within(conditionCard as HTMLElement).getByText("구조화 결제 조건")).toBeInTheDocument();
      expect(within(conditionCard as HTMLElement).queryByText("모바일 지역화폐 결제")).not.toBeInTheDocument();
      const noticeCard = screen.getByRole("heading", { name: /확인 필요 사항/ }).closest(".policy-requirement-group");
      expect(noticeCard).not.toBeNull();
      expect(within(noticeCard as HTMLElement).getByText("공식 공지사항 필독")).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("does not invent digital residency eligibility from visit-only fallback requirements", async () => {
    const gangjinRequirement =
      "강진군 관광지 2개소 이상 방문, 모바일 강진사랑상품권(Chak)으로 결제한 거래내역(영수증) *홈페이지 공지사항(고시공고) 필독";
    const legacyGangjinPolicy: Policy = {
      id: "travelmonth-23",
      slug: "travelmonth-23",
      label: "강진",
      tag: "지역할인",
      title: "[강진] 대한민국 반값여행 지원",
      org: "강진군",
      region: "전남",
      deadline: "2026-06-30",
      amount: "확인 필요",
      summary: "강진군 여행 지원 혜택",
      match: 80,
      category: "지역할인",
      requirements: [gangjinRequirement],
      documents: [],
      officialUrl: "https://www.gangjin.go.kr/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(legacyGangjinPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-23");

      expect(
        await screen.findByRole("heading", { name: "[강진] 대한민국 반값여행 지원" }),
      ).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("디지털관광주민증");
      expect(screen.queryByRole("heading", { name: /신청 대상/ })).not.toBeInTheDocument();
      const noticeCard = screen.getByRole("heading", { name: /확인 필요 사항/ }).closest(".policy-requirement-group");
      expect(noticeCard).not.toBeNull();
      expect(within(noticeCard as HTMLElement).getByText(gangjinRequirement)).toBeInTheDocument();
      expect(noticeCard).not.toHaveTextContent("디지털관광주민증");
    } finally {
      getPolicySpy.mockRestore();
    }
  });


  it("uses an official policy link as an official information CTA when no direct apply link is available", async () => {
    const officialUrl =
      "https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pMenuCD=0302000000&pSeq=22267";
    const officialOnlyPolicy: Policy = {
      id: "official-only-policy",
      slug: "official-only-policy",
      label: "OF",
      tag: "공식 안내",
      title: "공식 안내만 있는 정책",
      org: "문화체육관광부",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "공식 안내 페이지에서 세부 혜택을 확인하는 정책입니다.",
      match: 70,
      category: "지역할인",
      requirements: ["공식 안내 확인 필요"],
      documents: ["공식 안내 확인"],
      officialUrl,
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(officialOnlyPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/official-only-policy");

      const applicationLink = await screen.findByRole("link", {
        name: "혜택 안내 보기",
      });
      expect(applicationLink).toHaveAttribute("href", officialUrl);
      expect(applicationLink).toHaveAttribute("target", "_blank");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("uses a direct apply link as the primary application CTA when available", async () => {
    const applyPolicy: Policy = {
      id: "apply-policy",
      slug: "apply-policy",
      label: "AP",
      tag: "접수 가능",
      title: "직접 신청 가능 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "직접 신청 링크가 확인된 정책입니다.",
      match: 70,
      category: "지역할인",
      requirements: ["공식 공고 확인 필요"],
      documents: ["공식 공고 확인 필요"],
      officialUrl: "https://travel.example/notice",
      applyUrl: "https://travel.example/apply",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(applyPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/apply-policy");

      const applicationLink = await screen.findByRole("link", {
        name: "신청하러 가기",
      });
      expect(applicationLink).toHaveAttribute(
        "href",
        "https://travel.example/apply",
      );
      expect(applicationLink).toHaveAttribute("target", "_blank");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders the prototype policy detail section order", async () => {
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(examplePolicyDetail);

    await login();
    cleanup();
    try {
      renderAppRoute(examplePolicyPath);

      await waitFor(() => expect(document.body).toHaveTextContent("지원 내용"));
      const bodyText = document.body.textContent ?? "";
      expect(bodyText.indexOf("지원 내용")).toBeLessThan(
        bodyText.indexOf("신청 기간"),
      );
      expect(bodyText.indexOf("신청 기간")).toBeLessThan(
        bodyText.indexOf("신청 대상"),
      );
      expect(bodyText.indexOf("신청 대상")).toBeLessThan(
        bodyText.indexOf("필요 서류"),
      );
      expect(document.body).toHaveTextContent(
        "디지털관광주민증 발급 또는 지역별 신청 조건 확인",
      );
      expect(document.body).not.toHaveTextContent("조건 확인 요약");
      expect(document.body).not.toHaveTextContent("이 정책과 함께 확인할 혜택");
      expect(document.body).not.toHaveTextContent("자주 묻는 질문");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("splits policy requirements into target, usage condition, and confirmation sections", async () => {
    const cardPolicy: Policy = {
      id: "card-benefit-policy",
      slug: "card-benefit-policy",
      label: "BUSAN",
      tag: "지역할인",
      title: "부산 결제 캐시백",
      org: "부산관광공사",
      region: "부산",
      deadline: "2026-06-30",
      amount: "카드 결제 5% 캐시백",
      summary: "부산 결제 캐시백 혜택",
      match: 80,
      category: "지역할인",
      requirements: [
        "국내 여행자",
        "제휴 카드",
        "부산 결제",
        "월 한도 적용",
        "공식 안내 확인 필요",
      ],
      documents: ["혜택 안내 확인"],
      officialUrl: "https://travel.example/busan-card",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(cardPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/card-benefit-policy");

      await screen.findByText("부산 결제 캐시백");
      const bodyText = document.body.textContent ?? "";
      expect(bodyText.indexOf("신청 대상")).toBeLessThan(
        bodyText.indexOf("혜택 적용 조건"),
      );
      expect(bodyText.indexOf("혜택 적용 조건")).toBeLessThan(
        bodyText.indexOf("확인 필요 사항"),
      );
      expect(document.body).toHaveTextContent("국내 여행자");
      expect(document.body).toHaveTextContent(
        "제휴 카드로 결제한 건에 한해 혜택이 적용됩니다.",
      );
      expect(document.body).toHaveTextContent(
        "부산 지역 결제 또는 대상 가맹점 이용 건을 기준으로 적용됩니다.",
      );
      expect(document.body).toHaveTextContent(
        "월별 할인/캐시백 한도 내에서 혜택이 적용됩니다.",
      );
      expect(document.body).toHaveTextContent(
        "공식 안내에서 세부 조건과 최신 공지를 확인하세요.",
      );
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("breaks long policy benefit summaries into scannable detail groups", async () => {
    const longSummaryPolicy: Policy = {
      id: "long-summary-policy",
      slug: "long-summary-policy",
      label: "YW",
      tag: "지역할인",
      title: "왕과 사는 남자 영월봄기행 10,000 할인",
      org: "한국관광공사",
      region: "강원",
      deadline: "2026-05-29",
      amount: "최대 140000원",
      summary:
        "기간: 4월1일~5월29일 매주 주말 *이용일 20일 전 사전예약 여행가는 달 기간 한정 특별 할인 운영 · 정상가 대비 10,000원 할인 적용(1박2일 정상가 140,000원) ※여행가는 달 홈페이지 해당 내용 캡쳐본 제시할 경우, 할인 적용 · 고향사랑기부자 혜택 추가 할인 적용 40,000원 ※영월군 고향사랑기부제 100,000원 기부후 당사 답례품 “사계절 릴레이 축제 할인권” 지정시 30,000원할인 + 특별할인 10,000원 = 40,000원 할인 1. 기본 특별 할인 할인 혜택: 정상가에서 10,000원 할인 실구매가",
      match: 80,
      category: "지역할인",
      requirements: ["공식 안내에서 신청 조건을 확인하세요."],
      documents: ["혜택 안내 확인"],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(longSummaryPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/long-summary-policy");

      const supportSection = await screen.findByRole("region", {
        name: "지원 내용",
      });
      expect(
        within(supportSection).getByText("최대 140000원"),
      ).toBeInTheDocument();
      expect(within(supportSection).getByText("핵심 혜택")).toBeInTheDocument();
      expect(within(supportSection).getByText("운영 기간")).toBeInTheDocument();
      expect(within(supportSection).getByText("이용 조건")).toBeInTheDocument();
      expect(within(supportSection).getByText("유의사항")).toBeInTheDocument();
      expect(
        within(supportSection).getByText(/정상가 대비 10,000원 할인/),
      ).toBeInTheDocument();
      expect(
        within(supportSection).getByText(/4월1일~5월29일/),
      ).toBeInTheDocument();
      expect(
        within(supportSection).getByText(/캡쳐본 제시/),
      ).toBeInTheDocument();
      expect(
        within(supportSection).getByText(/고향사랑기부제/),
      ).toBeInTheDocument();
      expect(supportSection.querySelector(".highlight-box .meta")).toBeNull();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("uses the dgtour summary instead of repeating generic benefit text", async () => {
    const dgtourPolicy: Policy = {
      id: "dgtour-밀양-1",
      slug: "dgtour-밀양-1",
      label: "경남",
      tag: "지역할인",
      title: "밀양 디지털관광주민증 혜택",
      org: "한국관광공사",
      region: "경남",
      deadline: "2026-12-31",
      amount: "혜택 제공",
      summary:
        "디지털관광주민증 소지자 대상 밀양(경남) 지역 방문 시 혜택을 제공합니다.",
      match: 75,
      category: "지역할인",
      requirements: ["디지털관광주민증 발급자", "경남 방문"],
      documents: ["디지털관광주민증"],
      officialUrl: "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(dgtourPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/dgtour-%EB%B0%80%EC%96%91-1");

      const supportSection = await screen.findByRole("region", {
        name: "지원 내용",
      });
      expect(
        within(supportSection).getByText("디지털관광주민증 혜택"),
      ).toBeInTheDocument();
      expect(within(supportSection).getByText("핵심 혜택")).toBeInTheDocument();
      expect(
        within(supportSection).getByText(
          "디지털관광주민증 소지자 대상 밀양(경남) 지역 방문 시 혜택을 제공합니다.",
        ),
      ).toBeInTheDocument();
      expect(supportSection).not.toHaveTextContent("혜택 제공 혜택");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("separates TravelMonth condition text from trailing benefit period text", async () => {
    const welchonPolicy: Policy = {
      id: "travelmonth-44",
      slug: "travelmonth-44",
      label: "전국",
      tag: "여행상품",
      title: "웰촌 체험상품 30% 할인",
      org: "한국농어촌공사",
      region: "전국",
      deadline: "2026-05-31",
      amount: "최대 30%",
      summary:
        "행사 기간 중 온라인 체험상품 예약 결제 후 사용 완료 참여자 26년 4월 중순부터 5월 말",
      match: 90,
      category: "여행상품",
      requirements: ["공식 혜택 안내에서 조건을 확인하세요."],
      documents: [],
      officialUrl: "https://weektonongchon.netlify.app/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(welchonPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-44");

      const supportSection = await screen.findByRole("region", {
        name: "지원 내용",
      });
      expect(within(supportSection).getByText("최대 30%")).toBeInTheDocument();
      expect(within(supportSection).getByText("이용 조건")).toBeInTheDocument();
      expect(within(supportSection).getByText("운영 기간")).toBeInTheDocument();
      expect(
        within(supportSection).getByText(
          /온라인 체험상품 예약 결제 후 사용 완료 참여자/,
        ),
      ).toBeInTheDocument();
      expect(
        within(supportSection).getByText(/26년 4월 중순부터 5월 말/),
      ).toBeInTheDocument();
      expect(
        within(supportSection).queryByText(welchonPolicy.summary),
      ).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders cleaned stay discount detail without duplicated raw discount copy", async () => {
    const stayPolicy: Policy = {
      id: "stay-discount-gangwon-goseong",
      slug: "stay-discount-gangwon-goseong",
      label: "강원",
      tag: "최대 7만원",
      title: "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
      org: "문화체육관광부, 한국관광공사",
      region: "강원",
      deadline: "2026-07-31",
      amount: "최대 7만원",
      summary: "비수도권 인구감소지역 숙박 예약 시 결제 금액과 숙박 조건에 따라 2만~7만원 할인권을 제공합니다.",
      match: 90,
      category: "숙박",
      requirements: [
        "7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)",
        "7만원 이상 국내 숙박상품: 3만원 할인 (1박 이상)",
        "14만원 미만 국내 숙박상품: 5만원 할인 (연박 이상)",
        "14만원 이상 국내 숙박상품: 7만원 할인 (연박 이상)",
        "참여 온라인 여행사에서 매일 오전 10시부터 선착순 발급",
        "입실기간: 2026.6.11~7.31",
      ],
      documents: [],
      officialUrl: "https://ktostay.visitkorea.or.kr/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(stayPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/stay-discount-gangwon-goseong");

      const supportSection = await screen.findByRole("region", {
        name: "지원 내용",
      });
      expect(
        await screen.findByRole("heading", {
          name: "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        }),
      ).toBeInTheDocument();
      expect(within(supportSection).getByText("최대 7만원")).toBeInTheDocument();
      expect(
        within(supportSection).getByText(
          "비수도권 인구감소지역 숙박 예약 시 결제 금액과 숙박 조건에 따라 2만~7만원 할인권을 제공합니다.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByText("7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("14만원 이상 국내 숙박상품: 7만원 할인 (연박 이상)"),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/7만원 미만\* 국내 숙박상품 예약 시 2만원 할인/),
      ).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders policy detail in prototype-only flow without FAQ accordion", async () => {
    await login();
    cleanup();
    renderAppRoute(examplePolicyPath);

    await waitFor(() =>
      expect(document.body).toHaveTextContent(examplePolicyTitle),
    );
    expect(
      screen.queryByRole("button", { name: /어떤 서류가 필요한가요/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /내 일정에 담기|일정에 담김/ }),
    ).toBeInTheDocument();
  });

  it("keeps the application notice fallback when a policy has no official links", async () => {
    const fallbackPolicy: Policy = {
      id: "no-link-policy",
      slug: "no-link-policy",
      label: "NL",
      tag: "안내 준비",
      title: "신청 링크 준비 중 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "공식 신청 링크가 아직 확인되지 않은 정책입니다.",
      match: 70,
      category: "기타",
      requirements: ["공식 공고 확인 필요"],
      documents: ["공식 공고 확인 필요"],
      officialUrl: null,
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(fallbackPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/no-link-policy");
      const fallbackButton = await screen.findByRole("button", {
        name: "신청 링크 준비 중",
      });
      expect(fallbackButton).toBeDisabled();
      expect(fallbackButton).toHaveAttribute(
        "title",
        "공식 신청 연결은 준비 중입니다.",
      );
      expect(document.body).toHaveTextContent("공식 신청 연결은 준비 중입니다.");
      expect(fallbackButton).toHaveAccessibleDescription(
        "공식 신청 연결은 준비 중입니다.",
      );
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("blocks save and trip actions for info-only raw fallback policies", async () => {
    const rawFallbackPolicy: Policy = {
      id: "travelmonth-raw-58",
      slug: "travelmonth-raw-58",
      label: "RAW",
      tag: "공식 안내",
      title: "정규화 대기 중인 공식 혜택",
      org: "한국관광공사",
      region: "부산",
      deadline: "2026-06-30",
      amount: "최대 2만원",
      summary: "원문 수집 상세만 임시로 확인할 수 있는 혜택입니다.",
      match: 80,
      category: "지역할인",
      requirements: ["공식 안내 확인 필요"],
      documents: ["혜택 안내 확인"],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
      actionStatus: "infoOnly",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(rawFallbackPolicy);
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
    const savePolicySpy = vi.spyOn(appDataApi, "savePolicy");
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips");

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-raw-58");
      const user = userEvent.setup();

      await screen.findByText("정규화 대기 중인 공식 혜택");
      expect(document.body).toHaveTextContent(
        "이 혜택은 공식 원문 확인만 가능해요. 저장하거나 일정에 담으려면 정규화된 정책으로 승격되어야 합니다.",
      );
      const saveButton = screen.getByRole("button", { name: "저장" });
      const tripButton = screen.getByRole("button", {
        name: /내 일정에 담기/,
      });
      expect(saveButton).toBeDisabled();
      expect(tripButton).toBeDisabled();

      await user.click(saveButton);
      await user.click(tripButton);
      expect(savePolicySpy).not.toHaveBeenCalled();
      expect(listTripsSpy).not.toHaveBeenCalled();
    } finally {
      getPolicySpy.mockRestore();
      loginSpy.mockRestore();
      refreshSpy.mockRestore();
      profileSpy.mockRestore();
      savedPolicySpy.mockRestore();
      savePolicySpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });
});
