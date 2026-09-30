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
  getUpcomingPreviewTrip,
  getPreviewUser,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — policy detail", () => {
  const ROUND2_APPLY_FORM = "https://forms.gle/HWrxX3iwEUrciZey6";
  const ROUND1_DOCUMENT_FORM = "https://forms.gle/adnDYssMNVjtA2Cx7";

  function islandGuidePolicy(guide: NonNullable<Policy["applicationGuide"]>): Policy {
    return {
      id: "travelmonth-81",
      slug: "travelmonth-81",
      label: "섬",
      tag: "10만원",
      title: "2026 섬 여행비 지원",
      org: "섬 방문의 해 추진위원회",
      region: "전국",
      deadline: "2026-09-21",
      amount: "최대 10만원",
      summary: "여행비 10만원 (숙박비, 왕복 배편 승선권, 식비 등)",
      match: 80,
      category: "여행상품",
      requirements: [],
      documents: [],
      officialUrl: "https://www.visitisland.kr/promotion2",
      applyUrl: guide.applyFormUrl,
      sourceType: "internal",
      structuredDetail: {
        supportContent: [
          { title: "핵심 혜택", description: "최대 10만원 혜택" },
          { title: "지원 내용", description: "여행비 10만원 (숙박비, 왕복 배편 승선권, 식비 등)" },
        ],
        periods: [
          { title: "1차 신청 기간", description: "2026-09-21 18:00", type: "application" },
        ],
        applicationTarget: [],
        requiredDocuments: [],
        notes: [],
      },
      applicationGuide: guide,
    };
  }

  function islandGuide(overrides: Partial<NonNullable<Policy["applicationGuide"]>> = {}): NonNullable<Policy["applicationGuide"]> {
    return {
      rounds: [
        { key: "1", label: "1차", status: "past", applyStart: "2026-06-17T10:00", applyUntil: "2026-06-30T23:59", travelStart: "2026-07-01", travelEnd: "2026-08-31", documentsDueBy: "2026-09-14", applicationFormUrl: null, documentFormUrl: ROUND1_DOCUMENT_FORM },
        { key: "2", label: "2차", status: "current", applyStart: null, applyUntil: "2026-09-21T18:00", travelStart: "2026-10-01", travelEnd: "2026-11-04", documentsDueBy: "2026-11-18", applicationFormUrl: ROUND2_APPLY_FORM, documentFormUrl: null },
        { key: "3", label: "3차", status: "upcoming", applyStart: "2027-03-02T10:00", applyUntil: "2027-03-20T18:00", travelStart: "2027-04-01", travelEnd: "2027-05-31", documentsDueBy: "2027-06-14", applicationFormUrl: null, documentFormUrl: null },
      ],
      currentRoundKey: "2",
      applyFormUrl: ROUND2_APPLY_FORM,
      documentDeadlineDaysAfterTrip: 14,
      minNights: 1,
      minPaymentKrw: 100000,
      requiredDocuments: ["신분증", "통장사본", "왕복 배편 승선권 혹은 영수증", "실 결제 영수증 (카드, 현금 영수증 또는 송금 계좌 이체 내역 등)", "OTA 이용 시, 예약 및 결제 내역"],
      photoRequirement: "이름, 주민등록번호, 날짜, 금액이 명확히 나온 사진만 인정됩니다.",
      exclusions: ["중복 영수증"],
      contacts: { email: "info@visitisland.kr", phones: ["070-4337-5058"] },
      ...overrides,
    };
  }

  it("guides the island support application by past, current and upcoming round", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-09-19T09:00:00+09:00"));
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(islandGuidePolicy(islandGuide()));

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-81");
      const section = await screen.findByRole("region", { name: "신청 절차" });

      // current round: open, deadline D-day emphasised within 3 days, five ordered steps
      expect(within(section).getByText("2차 · 진행 중")).toBeInTheDocument();
      const deadline = within(section).getByText("신청 마감 D-2");
      expect(deadline).toHaveClass("tag", "warning");
      const steps = within(section).getByRole("list", { name: "2차 진행 순서" });
      expect(within(steps).getAllByRole("listitem").map((item) => item.textContent ?? "")).toEqual([
        expect.stringContaining("신청"),
        expect.stringContaining("선정 발표"),
        expect.stringContaining("섬 여행"),
        expect.stringContaining("서류 제출"),
        expect.stringContaining("지원금 수령"),
      ]);
      expect(within(steps).getByText(/2026-10-01 ~ 2026-11-04/)).toBeInTheDocument();
      expect(within(steps).getByText(/여행 종료 후 14일 이내 \(2026-11-18까지\)/)).toBeInTheDocument();
      expect(within(section).queryByRole("link", { name: "신청 폼 열기" })).toBeNull();
      // 아래 버튼 줄: 신청 폼은 보조 링크, 주 버튼은 '내 일정에 담기' 하나
      const actionRow = document.querySelector(".policy-detail-actions") as HTMLElement;
      expect(actionRow).toHaveClass("policy-detail-bar");
      expect(within(actionRow).getByRole("link", { name: "신청 폼 열기" })).toHaveAttribute("href", ROUND2_APPLY_FORM);
      expect(within(actionRow).getByRole("button", { name: /내 일정에 담기/ })).toHaveClass("policy-detail-primary");
      expect(document.querySelector(".sticky-cta")).toBeNull();

      const periodSection = screen.getByRole("region", { name: "기간" });
      expect(within(periodSection).getByText(/1차 신청 기간: 2026-09-21 18:00/)).toBeInTheDocument();
      expect(screen.queryByText("핵심 혜택")).toBeNull();
      expect(screen.queryByText("최대 10만원 혜택")).toBeNull();
      expect(
        within(screen.getByRole("region", { name: "받는 혜택" })).getByText("여행비 10만원 (숙박비, 왕복 배편 승선권, 식비 등)"),
      ).toBeInTheDocument();

      // past round: collapsed, still offers its document form with the selected-applicant warning
      const past = within(section).getByText("1차 · 종료").closest("details");
      expect(past).not.toBeNull();
      expect(past).not.toHaveAttribute("open");
      expect(within(past as HTMLElement).getByRole("link", { name: "서류 제출 폼 열기" })).toHaveAttribute("href", ROUND1_DOCUMENT_FORM);
      expect(within(past as HTMLElement).getByText("선정 문자를 받은 분만 제출할 수 있어요")).toBeInTheDocument();

      // upcoming round: announced with its application start date
      expect(within(section).getByText("3차 · 예정")).toBeInTheDocument();
      expect(within(section).getByText(/신청 시작 2027-03-02/)).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
      vi.useRealTimers();
    }
  });

  it("closes the application form once the round deadline has passed", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-09-22T09:00:00+09:00"));
    const guide = islandGuide({ applyFormUrl: null });
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(islandGuidePolicy(guide));

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-81");
      const section = await screen.findByRole("region", { name: "신청 절차" });
      expect(within(section).getByText("신청 마감 마감")).toBeInTheDocument();
      expect(within(section).queryByRole("link", { name: "신청 폼 열기" })).toBeNull();
    } finally {
      getPolicySpy.mockRestore();
      vi.useRealTimers();
    }
  });

  it("shows the approved eligible island count and official link only for the island policy", async () => {
    const islandPolicy: Policy = {
      id: "2026-island-visit-support",
      slug: "2026-island-visit-support",
      label: "섬",
      tag: "최대 10만원",
      title: "2026 섬 여행비 지원",
      org: "섬 방문의 해 추진위원회",
      region: "전국",
      deadline: "2026-12-31",
      amount: "최대 10만원",
      summary: "대상 섬 여행 시 여행비 지원",
      match: 80,
      category: "여행상품",
      requirements: [],
      documents: [],
      officialUrl: "https://www.visitisland.kr/promotion2",
      applyUrl: null,
      sourceType: "external",
      eligibleIslandCount: 12,
      eligibleIslandsOfficialUrl: "https://www.visitisland.kr/notice/1",
    };
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(islandPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/2026-island-visit-support");
      // 제목 앞 연도는 뺀다
      expect(await screen.findByRole("heading", { level: 1, name: "섬 여행비 지원" })).toBeInTheDocument();
      expect(
        within(screen.getByRole("region", { name: "받을 수 있는 사람" })).getByText("대상 섬 12곳"),
      ).toBeVisible();
      expect(screen.getByRole("link", { name: "대상 섬 공식 안내" })).toHaveAttribute(
        "href",
        "https://www.visitisland.kr/notice/1",
      );
      expect(screen.getAllByText("최대 10만원").length).toBeGreaterThan(0);
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders no eligible island section when the count is missing or zero", async () => {
    const plainPolicy: Policy = {
      id: "plain-policy",
      slug: "plain-policy",
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
      requirements: [],
      documents: [],
      officialUrl: "https://korean.visitkorea.or.kr/travelmonth/benefit.do",
      applyUrl: null,
      sourceType: "external",
      eligibleIslandCount: 0,
      eligibleIslandsOfficialUrl: "https://www.visitisland.kr/notice/1",
    };
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(plainPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/plain-policy");
      expect(await screen.findByRole("heading", { name: "부산 공식 캐시백" })).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("대상 섬");
      expect(screen.queryByRole("region", { name: "신청 절차" })).toBeNull();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

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
      ...getUpcomingPreviewTrip(),
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
      deadline: "2026-08-31",
      amount: "확인 필요",
      summary: "기존 요약 fallback",
      match: 90,
      category: "지역할인",
      requirements: [],
      documents: ["기존 서류 fallback"],
      structuredDetail: {
        supportContent: [
          { title: "핵심 혜택", description: "합천 제휴처 17곳의 혜택을 제공합니다." },
          { title: "카테고리별 인기 혜택", description: "인기순 대표 제휴처와 주요 혜택을 카테고리별로 정리했습니다." },
          {
            title: "카테고리별 인기 혜택",
            description: "🍽️ 로우풀: 음료 구매시 아메리카노 리필 1회\n호수뷰와 마운틴뷰가 조화로운 대형카페",
            url: "https://korean.visitkorea.or.kr/dgtourcard/biz/mbrb/mbrbPtcl.do?mbrbId=cdb03f3e-180d-11ef-b16c-0242ac130002",
          },
        ],
        applicationTarget: [{ title: "대상", description: "비수도권 숙박 예약자" }],
        periods: [
          {
            title: "신청 기간",
            description: "2026-06-01 ~ 2026-08-31",
            type: "application",
            startDate: "2026-06-01",
            endDate: "2026-08-31",
          },
          {
            title: "여행 기간",
            description: "2026-06-01 ~ 2026-12-31",
            type: "usage",
            startDate: "2026-06-01",
            endDate: "2026-12-31",
          },
          {
            title: "쿠폰 발급 기간",
            description: "2026-06-15 ~ 2026-07-15",
            type: "issue",
            startDate: "2026-06-15",
            endDate: "2026-07-15",
          },
        ],
        requiredDocuments: [],
        notes: [{ title: "주의", description: "예산 소진 시 조기 종료" }],
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

      expect(await screen.findByRole("heading", { level: 1, name: "구조화 상세 정책" })).toBeInTheDocument();
      // 핵심 혜택 문장 대신 제휴처 수, 목록 소개 문장은 뺀다
      expect(screen.getByText("제휴처 17곳 할인")).toBeInTheDocument();
      const benefitSection = screen.getByRole("region", { name: "받는 혜택" });
      expect(within(benefitSection).getByText("제휴처 17곳")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("합천 제휴처 17곳의 혜택을 제공합니다.");
      expect(document.body).not.toHaveTextContent("인기순 대표 제휴처와 주요 혜택을 카테고리별로 정리했습니다.");
      expect(within(benefitSection).getByRole("heading", { name: "인기 제휴처" })).toBeInTheDocument();
      // 제휴처 한 줄마다 그 제휴처 안내 페이지로 간다
      const benefitLink = within(benefitSection).getByRole("link", { name: /로우풀/ });
      expect(benefitLink).toHaveAttribute(
        "href",
        "https://korean.visitkorea.or.kr/dgtourcard/biz/mbrb/mbrbPtcl.do?mbrbId=cdb03f3e-180d-11ef-b16c-0242ac130002",
      );
      expect(benefitLink).toHaveAttribute("target", "_blank");
      expect(benefitLink).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
      expect(within(benefitLink).getByText("식음")).toHaveClass("pick-category");
      expect(within(benefitLink).getByText("로우풀")).toBeInTheDocument();
      expect(within(benefitLink).getByText("음료 구매시 아메리카노 리필 1회")).toHaveClass("pick-benefit");
      expect(within(benefitLink).getByText("호수뷰와 마운틴뷰가 조화로운 대형카페")).toHaveClass("pick-note");
      expect(within(benefitSection).getByRole("link", { name: "전국 제휴처 17곳 모두 보기" })).toHaveAttribute(
        "href",
        "https://example.com/official",
      );
      // 날짜가 있는 기간은 막대로(라벨 끝 '기간'은 뺀다)
      const periodSection = screen.getByRole("region", { name: "기간" });
      expect(periodSection.querySelectorAll(".policy-timeline-row")).toHaveLength(3);
      expect(within(periodSection).getByText("신청")).toBeInTheDocument();
      expect(within(periodSection).getByText("여행")).toBeInTheDocument();
      expect(within(periodSection).getByText("쿠폰 발급")).toBeInTheDocument();
      expect(within(screen.getByRole("region", { name: "받을 수 있는 사람" })).getByText("비수도권 숙박 예약자")).toBeInTheDocument();
      expect(within(screen.getByRole("region", { name: "확인할 점" })).getByText("예산 소진 시 조기 종료")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("2026.05.01 ~ 2026.12.31");
      expect(screen.getByRole("link", { name: /혜택 안내 보기/ })).toHaveAttribute("href", "https://example.com/official");
      // 구조화된 서류 칸이 비면 옛 서류 문구를 끌어오지 않고 공식 안내 한 줄로 채운다
      const documentsSection = screen.getByRole("region", { name: "준비물" });
      expect(documentsSection).toHaveTextContent("필요한 서류는 공식 안내에서 확인해 주세요.");
      expect(within(documentsSection).getByRole("link", { name: "공식 안내 열기" })).toHaveAttribute(
        "href",
        "https://example.com/official",
      );
      expect(document.body).not.toHaveTextContent("기존 서류 fallback");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders confirmation-needed fallback instead of malformed period text when deadline is unknown", async () => {
    const unknownDeadlinePolicy: Policy = {
      id: "unknown-deadline-detail",
      slug: "unknown-deadline-detail",
      label: "UD",
      tag: "지역할인",
      title: "마감 확인 필요 상세 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "",
      amount: "확인 필요",
      summary: "공식 안내에서 기간 확인이 필요한 정책입니다.",
      match: 60,
      category: "지역할인",
      requirements: [],
      documents: [],
      officialUrl: "https://example.com/official",
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(unknownDeadlinePolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/unknown-deadline-detail");

      expect(await screen.findByRole("heading", { name: "마감 확인 필요 상세 정책" })).toBeInTheDocument();
      expect(document.body).toHaveTextContent("마감일 확인 필요");
      expect(document.body).not.toHaveTextContent("2026.05.01 ~ ");
      expect(document.body).not.toHaveTextContent("상시");
      expect(document.body).not.toHaveTextContent("마감일 확인 필요 마감");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders a confirmed deadline without inventing a structured start date", async () => {
    const deadlineOnlyPolicy: Policy = {
      id: "deadline-only-detail",
      slug: "deadline-only-detail",
      label: "DO",
      tag: "지역할인",
      title: "마감일만 확인된 상세 정책",
      org: "Travel Hunter",
      region: "전국",
      deadline: "2026-12-31",
      amount: "확인 필요",
      summary: "공식 안내에서 시작일 확인이 필요한 정책입니다.",
      match: 60,
      category: "지역할인",
      requirements: [],
      documents: [],
      officialUrl: "https://example.com/official",
      applyUrl: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(deadlineOnlyPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/deadline-only-detail");

      expect(await screen.findByRole("heading", { name: "마감일만 확인된 상세 정책" })).toBeInTheDocument();
      expect(screen.getByText("2026.12.31 마감")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("시작일 확인 필요");
      expect(document.body).not.toHaveTextContent("2026.05.01");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("does not mix legacy requirement or document text into structured detail sections", async () => {
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
        supportContent: [{ title: "혜택", description: "구조화 혜택" }],
        applicationTarget: [],
        periods: [],
        requiredDocuments: [],
        notes: [],
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
      // 짧은 '혜택' 줄은 받는 것 칸과 같은 말일 때만 뺀다 - 다른 말이면 남긴다
      expect(within(screen.getByRole("region", { name: "받는 혜택" })).getByText("구조화 혜택")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("기존 조건 fallback");
      expect(document.body).not.toHaveTextContent("기존 서류 fallback");
      expect(screen.getByRole("region", { name: "받을 수 있는 사람" })).toHaveTextContent(
        "대상과 조건은 공식 안내에서 확인해 주세요.",
      );
      expect(screen.queryByRole("link", { name: /위험 링크/ })).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("does not reclassify legacy requirements when structured conditions are present", async () => {
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
        supportContent: [{ title: "혜택", description: "구조화 혜택" }],
        applicationTarget: [{ title: "혜택 적용 조건", description: "구조화 결제 조건" }],
        periods: [],
        requiredDocuments: [],
        notes: [],
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
      const targetSection = screen.getByRole("region", { name: "받을 수 있는 사람" });
      expect(within(targetSection).getByText("구조화 결제 조건")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("모바일 지역화폐 결제");
      expect(document.body).not.toHaveTextContent("공식 공지사항 필독");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders stay discount semantics only from their structured sections", async () => {
    const legacyCompositeRequirement =
      "7만원 이상 숙박상품 3만원 할인 · 쿠폰 발급 2026.06.10~06.20 · 입실 2026.06.11~07.31 · 참여 온라인 여행사 선착순";
    const structuredStayPolicy: Policy = {
      id: "structured-stay-discount",
      slug: "structured-stay-discount",
      label: "강원",
      tag: "최대 7만원",
      title: "구조화 숙박세일 페스타",
      org: "한국관광공사",
      region: "강원",
      deadline: "2026-07-31",
      amount: "최대 7만원",
      summary: "숙박 할인권을 제공하는 정책입니다.",
      match: 90,
      category: "숙박",
      requirements: [legacyCompositeRequirement],
      documents: [],
      structuredDetail: {
        supportContent: [{ title: "할인 혜택", description: "숙박 결제 금액에 따라 2만~7만원 할인" }],
        applicationTarget: [{ title: "이용 조건", description: "비수도권 숙박시설 1박 이상 예약" }],
        periods: [
          { title: "쿠폰 발급 기간", description: "2026.06.10 ~ 2026.06.20", type: "issue" },
          { title: "입실 기간", description: "2026.06.11 ~ 2026.07.31", type: "usage" },
        ],
        requiredDocuments: [],
        notes: [{ title: "발급 안내", description: "참여 온라인 여행사에서 선착순 발급" }],
      },
      officialUrl: "https://ktostay.visitkorea.or.kr/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(structuredStayPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/structured-stay-discount");

      expect(
        await screen.findByRole("heading", { name: "구조화 숙박세일 페스타" }),
      ).toBeInTheDocument();
      const benefitSection = screen.getByRole("region", { name: "받는 혜택" });
      expect(within(benefitSection).getByRole("heading", { name: "할인 혜택" })).toBeInTheDocument();
      expect(within(benefitSection).getByText("숙박 결제 금액에 따라 2만~7만원 할인")).toBeInTheDocument();
      expect(screen.getByText("비수도권 숙박시설 1박 이상 예약")).toBeInTheDocument();
      // 연도가 붙은 점 날짜('2026.06.10 ~ 2026.06.20')도 막대로 읽는다
      const periodSection = screen.getByRole("region", { name: "기간" });
      expect(periodSection.querySelectorAll(".policy-timeline-row")).toHaveLength(2);
      expect(within(periodSection).getByText("쿠폰 발급")).toBeInTheDocument();
      expect(within(periodSection).getByText("입실")).toBeInTheDocument();
      expect(within(periodSection).getByText(/6\.10 – .*6\.20/)).toBeInTheDocument();
      expect(within(periodSection).getByText(/6\.11 – .*7\.31/)).toBeInTheDocument();
      expect(screen.getByText("참여 온라인 여행사에서 선착순 발급")).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent(legacyCompositeRequirement);
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders scoped half-trip five-section detail without moving proof text into application target", async () => {
    const pollutedLegacyRequirement = "영수증, 결제내역, 인증사진, 캡처본을 신청대상에 섞으면 안 되는 legacy 문자열";
    const halfTripPolicy: Policy = {
      id: "travelmonth-20",
      slug: "travelmonth-20",
      label: "거창",
      tag: "50%",
      title: "[거창] 대한민국 반값여행 지원",
      org: "거창군",
      region: "경남",
      deadline: "2026-08-30",
      amount: "여행비 50% 환급",
      summary: "거창 반값여행 지원",
      match: 90,
      category: "지역할인",
      requirements: [pollutedLegacyRequirement],
      documents: ["legacy 서류 fallback"],
      structuredDetail: {
        supportContent: [
          { title: "지원내용", description: "거창 여행 중 사용한 경비의 50%를 모바일 거창반값여행 정책발행용 상품권으로 지급한다." },
        ],
        periods: [
          { title: "사전신청 기간", description: "2026-04-13~2026-08-30", type: "application" },
          { title: "여행 기간", description: "2026-04-14~2026-08-31", type: "travel" },
        ],
        applicationTarget: [
          { title: "신청대상", description: "거창을 여행하고 싶은 타지역 거주 관광객." },
          { title: "신청대상", description: "거창군, 김천시, 함양군, 산청군, 합천군, 무주군 거주자는 제외한다." },
        ],
        requiredDocuments: [
          { title: "필요서류", description: "지정 관광지 2개소 이상 방문 인증 사진." },
          { title: "필요서류", description: "제로페이 가맹점 2개소 이상에서 정책발행용 상품권을 사용한 영수증." },
          { title: "필요서류", description: "숙박예약 또는 이용완료 내역 캡처본, 숙박업소 이용 확인서." },
        ],
        notes: [
          { title: "비고", description: "선착순 마감 기준은 경비 신청 순이며 예산 소진 시 마감된다." },
        ],
      },
      officialUrl: "https://geochangtour.kr/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(halfTripPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-20");

      // '[거창]' 은 제목에서 지역 줄로 옮긴다
      expect(
        await screen.findByRole("heading", { level: 1, name: "대한민국 반값여행 지원" }),
      ).toBeInTheDocument();
      expect(document.querySelector(".policy-detail-eyebrow")).toHaveTextContent("거창 · 경남");
      const supportSection = screen.getByRole("region", { name: "받는 혜택" });
      const targetSection = screen.getByRole("region", { name: "받을 수 있는 사람" });
      const documentSection = screen.getByRole("region", { name: "준비물" });
      expect(screen.getByRole("region", { name: "기간" })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "확인할 점" })).toHaveTextContent(
        "선착순 마감 기준은 경비 신청 순이며 예산 소진 시 마감된다.",
      );
      expect(within(supportSection).getByText(/거창 여행 중 사용한 경비의 50%/)).toBeInTheDocument();
      expect(within(targetSection).getByText("거창을 여행하고 싶은 타지역 거주 관광객.")).toBeInTheDocument();
      expect(targetSection).not.toHaveTextContent("영수증");
      expect(targetSection).not.toHaveTextContent("인증 사진");
      expect(targetSection).not.toHaveTextContent("캡처본");
      expect(within(documentSection).getByText(/영수증/)).toBeInTheDocument();
      expect(within(documentSection).getByText(/인증 사진/)).toBeInTheDocument();
      expect(within(documentSection).getByText(/캡처본/)).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent(pollutedLegacyRequirement);
      expect(document.body).not.toHaveTextContent("legacy 서류 fallback");
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
        await screen.findByRole("heading", { level: 1, name: "대한민국 반값여행 지원" }),
      ).toBeInTheDocument();
      // 구조화 전 정책은 조건 원문을 그대로 싣는다 - 분류하거나 설명을 지어 붙이지 않는다
      expect(document.body).not.toHaveTextContent("디지털관광주민증");
      const targetSection = screen.getByRole("region", { name: "받을 수 있는 사람" });
      expect(within(targetSection).getByText(gangjinRequirement)).toBeInTheDocument();
      expect(targetSection.querySelectorAll("li")).toHaveLength(1);
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

      await screen.findByRole("region", { name: "받는 혜택" });
      expect(
        screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent),
      ).toEqual(["받는 혜택", "기간", "받을 수 있는 사람", "준비물", "확인할 점"]);
      expect(screen.getByRole("region", { name: "받을 수 있는 사람" })).toHaveTextContent(
        "디지털관광주민증 발급 또는 지역별 신청 조건 확인",
      );
      expect(document.body).not.toHaveTextContent("조건 확인 요약");
      expect(document.body).not.toHaveTextContent("이 정책과 함께 확인할 혜택");
      expect(document.body).not.toHaveTextContent("자주 묻는 질문");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("lists collected requirements as they are, without generated explanations or generic notices", async () => {
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

      await screen.findByRole("heading", { level: 1, name: "부산 결제 캐시백" });
      const targetSection = screen.getByRole("region", { name: "받을 수 있는 사람" });
      expect(
        Array.from(targetSection.querySelectorAll("li")).map((item) => item.textContent),
      ).toEqual(["국내 여행자", "제휴 카드", "부산 결제", "월 한도 적용"]);
      // 수집 원문에 없는 설명 문장은 만들지 않는다(필요도 80 이하)
      expect(document.body).not.toHaveTextContent("제휴 카드로 결제한 건에 한해 혜택이 적용됩니다.");
      expect(document.body).not.toHaveTextContent("공식 안내에서 세부 조건과 최신 공지를 확인하세요.");
      expect(document.body).not.toHaveTextContent("공식 안내 확인 필요");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("shows a legacy summary as collected, with won amounts in 만원", async () => {
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
        name: "받는 혜택",
      });
      expect(screen.getByText("최대 14만원")).toBeInTheDocument();
      expect(within(supportSection).getByText(/정상가 대비 1만원 할인/)).toBeInTheDocument();
      expect(within(supportSection).getByText(/4월1일~5월29일/)).toBeInTheDocument();
      expect(within(supportSection).getByText(/캡쳐본 제시/)).toBeInTheDocument();
      expect(within(supportSection).getByText(/고향사랑기부제/)).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("uses the dgtour summary and renders it as always-issued instead of deadline-unknown", async () => {
    const dgtourPolicy: Policy = {
      id: "dgtour-밀양-1",
      slug: "dgtour-밀양-1",
      label: "경남",
      tag: "지역할인",
      title: "밀양 디지털관광주민증 혜택",
      org: "한국관광공사",
      region: "경남",
      deadline: "",
      amount: "혜택 제공",
      summary:
        "디지털관광주민증 소지자 대상 밀양(경남) 지역 방문 시 혜택을 제공합니다.",
      match: 75,
      category: "지역할인",
      requirements: ["디지털관광주민증 발급자", "경남 방문"],
      documents: ["디지털관광주민증"],
      officialUrl: "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48270",
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
        name: "받는 혜택",
      });
      // '혜택 제공' 같은 뜻 없는 금액은 받는 것 칸에서 주민증 혜택으로 바꿔 읽힌다
      expect(screen.getByText("디지털관광주민증 혜택")).toBeInTheDocument();
      expect(
        within(supportSection).getByText(
          "디지털관광주민증 소지자 대상 밀양(경남) 지역 방문 시 혜택을 제공합니다.",
        ),
      ).toBeInTheDocument();
      expect(screen.getByText("상시 발급")).toBeInTheDocument();
      expect(screen.getByText("제휴처별 운영기간 확인")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("마감일 없이 주민증을 발급하면 바로 쓸 수 있어요.");
      expect(document.body).not.toHaveTextContent("마감일 확인 필요");
      expect(document.body).not.toHaveTextContent("혜택 제공 혜택");
      expect(screen.getByText("주민증 발급 후 제시")).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("keeps a legacy TravelMonth summary in one piece next to its amount", async () => {
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
        name: "받는 혜택",
      });
      expect(screen.getByText("최대 30%")).toBeInTheDocument();
      expect(within(supportSection).getByText(welchonPolicy.summary)).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("공식 혜택 안내에서 조건을 확인하세요.");
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
        "강원 고성 등 숙박세일페스타 대상 지역 숙박 이용자",
        "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자",
        "할인권 발급 후 지정 기간 내 입실 가능한 사용자",
      ],
      documents: [],
      structuredDetail: {
        supportContent: [
          { title: "할인 혜택", description: "7만원 미만 국내 숙박상품 예약 시 2만원 할인" },
          { title: "할인 혜택", description: "7만원 이상 국내 숙박상품 예약 시 3만원 할인" },
          { title: "할인 혜택", description: "14만원 미만 국내 숙박상품 예약 시 5만원 할인" },
          { title: "할인 혜택", description: "14만원 이상 국내 숙박상품 예약 시 7만원 할인" },
        ],
        periods: [
          { title: "쿠폰 발급기간", description: "2026.06.11 ~ 2026.07.31", type: "application" },
          { title: "입실기간", description: "2026.06.11 ~ 2026.07.31", type: "usage" },
        ],
        applicationTarget: [
          { title: "신청대상", description: "강원 고성 등 숙박세일페스타 대상 지역 숙박 이용자" },
          { title: "신청대상", description: "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자" },
          { title: "신청대상", description: "할인권 발급 후 지정 기간 내 입실 가능한 사용자" },
        ],
        requiredDocuments: [
          { title: "필요서류", description: "별도 제출 서류 없음 · 온라인 할인권 발급 및 예약 기준으로 적용" },
        ],
        notes: [
          { title: "비고", description: "할인권은 매일 오전 10시부터 선착순 발급됩니다." },
          { title: "비고", description: "예산 소진 시 조기 종료될 수 있습니다." },
          { title: "비고", description: "세부 기준은 공식 안내에서 최종 확인하세요." },
        ],
      },
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
        name: "받는 혜택",
      });
      expect(
        await screen.findByRole("heading", {
          level: 1,
          name: "대한민국 숙박세일 페스타 숙박 할인",
        }),
      ).toBeInTheDocument();
      expect(screen.getByText("최대 7만원")).toBeInTheDocument();
      expect(
        within(supportSection).getByText("7만원 미만 국내 숙박상품 예약 시 2만원 할인"),
      ).toBeInTheDocument();
      expect(
        within(supportSection).getByText("14만원 이상 국내 숙박상품 예약 시 7만원 할인"),
      ).toBeInTheDocument();
      const periodSection = screen.getByRole("region", { name: "기간" });
      expect(within(periodSection).getByText("쿠폰 발급")).toBeInTheDocument();
      expect(within(periodSection).getByText("입실")).toBeInTheDocument();
      expect(screen.getByText("강원 고성 등 숙박세일페스타 대상 지역 숙박 이용자")).toBeInTheDocument();
      // '별도 제출 서류 없음' 은 확인 표시 한 줄 + 행정 말투를 푼 문장으로
      const documentsSection = screen.getByRole("region", { name: "준비물" });
      expect(within(documentsSection).getByText("따로 낼 서류가 없어요")).toBeInTheDocument();
      expect(within(documentsSection).getByText("온라인에서 할인권을 받아 예약하면 적용돼요.")).toBeInTheDocument();
      const notesSection = screen.getByRole("region", { name: "확인할 점" });
      expect(within(notesSection).getByText("할인권은 매일 오전 10시부터 선착순 발급됩니다.")).toBeInTheDocument();
      expect(within(notesSection).getByText("예산 소진 시 조기 종료될 수 있습니다.")).toBeInTheDocument();
      // 숫자 없는 '공식 안내에서 최종 확인' 류는 끝의 한 줄 안내로 모은다
      expect(document.body).not.toHaveTextContent("세부 기준은 공식 안내에서 최종 확인하세요.");
      expect(screen.getByText("참여 여행사 예약")).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: /혜택 적용 조건/ })).not.toBeInTheDocument();
      expect(
        screen.queryByText(/7만원 미만\* 국내 숙박상품 예약 시 2만원 할인/),
      ).not.toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("separates structured support conditions from core benefit cards", async () => {
    const halfTripPolicy: Policy = {
      id: "travelmonth-23",
      slug: "travelmonth-23",
      label: "전남",
      tag: "최대 20만원",
      title: "[강진] 대한민국 반값여행 지원",
      org: "강진 지자체, 한국관광공사",
      region: "전남",
      deadline: "2026-08-31",
      amount: "최대 20만원 환급",
      summary: "강진 반값여행 지원",
      match: 90,
      category: "지역할인",
      requirements: [],
      documents: [],
      structuredDetail: {
        supportContent: [
          { title: "혜택", description: "최대 20만원 환급" },
          { title: "혜택 적용 조건", description: "강진군 관광지 2개소 이상 방문" },
          { title: "혜택 적용 조건", description: "모바일 강진사랑상품권(Chak)으로 결제" },
          {
            title: "지원내용",
            description: "강진 지역 여행 후 공식 안내에서 정한 소비·방문 인증 기준을 충족하면 최대 20만원 환급 혜택을 받을 수 있습니다.",
          },
        ],
        periods: [],
        applicationTarget: [
          { title: "신청대상", description: "강진군 외 지역에 거주하는 사전신청 관광객 누구나" },
        ],
        requiredDocuments: [],
        notes: [],
      },
      officialUrl: "https://www.gangjintour.com/",
      applyUrl: null,
      sourceType: "external",
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(halfTripPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/travelmonth-23");

      const supportSection = await screen.findByRole("region", {
        name: "받는 혜택",
      });
      // 받는 것 칸과 같은 '혜택' 줄은 한 번만, 조건은 받는 혜택 안의 '혜택 적용 조건' 목록으로
      expect(screen.getAllByText("최대 20만원 환급")).toHaveLength(1);
      expect(within(supportSection).getByRole("heading", { name: "혜택 적용 조건" })).toBeInTheDocument();
      const conditions = Array.from(supportSection.querySelectorAll(".policy-detail-list.strong li")).map(
        (item) => item.textContent,
      );
      expect(conditions).toEqual(["강진군 관광지 2개소 이상 방문", "모바일 강진사랑상품권(Chak)으로 결제"]);
      // 지역 이름만 바뀌는 틀 문장은 뺀다
      expect(document.body).not.toHaveTextContent("공식 안내에서 정한 소비·방문 인증 기준");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("renders policy detail in prototype-only flow without FAQ accordion", async () => {
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(examplePolicyDetail);

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);

      // '[영광]' 은 제목에서 지역 줄로 옮긴다
      expect(examplePolicyTitle).toBe("[영광] 디지털관광주민증 혜택");
      expect(
        await screen.findByRole("heading", { level: 1, name: "디지털관광주민증 혜택" }),
      ).toBeInTheDocument();
      expect(document.querySelector(".policy-detail-eyebrow")).toHaveTextContent("영광 · 전남");
      // 주민증 혜택은 마감일이 지나도 '상시 발급' - 끝난 혜택 안내를 띄우지 않는다
      expect(document.body).not.toHaveTextContent("모집이 끝난 혜택이에요");
      expect(
        screen.queryByRole("button", { name: /어떤 서류가 필요한가요/ }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /내 일정에 담기|일정에 담김/ }),
      ).toBeInTheDocument();
    } finally {
      getPolicySpy.mockRestore();
    }
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

  it("shows the server's region rejection under the trip row and keeps the other trips selectable", async () => {
    const regionalPolicy: Policy = {
      ...examplePolicyDetail,
      id: "region-check",
      slug: "region-check",
      title: "[태안] 대한민국 반값여행 지원",
      region: "충남",
      deadline: "2099-12-31",
    };
    const jejuTrip: Trip = { ...getUpcomingPreviewTrip(), id: "401", title: "제주 3일 여행", linkedPolicies: [] };
    const taeanTrip: Trip = { ...getUpcomingPreviewTrip(), id: "402", title: "태안 2일 여행", linkedPolicies: [] };
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(regionalPolicy);
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips").mockResolvedValue([jejuTrip, taeanTrip]);
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockRejectedValue(new Error("Policy does not match trip travel area"));

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/region-check");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: /내 일정에 담기/ }));
      const sheet = await screen.findByRole("dialog", { name: "일정 선택" });
      expect(within(sheet).getByRole("heading", { name: "어느 일정에 담을까요?" })).toBeInTheDocument();
      await user.click(within(sheet).getByRole("button", { name: /제주 3일 여행/ }));

      // 지역이 맞는지는 서버가 판단한다 - 거절 까닭을 그 줄 아래에 적는다
      const alert = await within(sheet).findByRole("alert");
      expect(alert).toHaveTextContent(
        "선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요.",
      );
      const failedRow = within(sheet).getByRole("button", { name: /제주 3일 여행/ });
      expect(failedRow).toHaveAccessibleDescription(alert.textContent ?? "");
      expect(failedRow).toHaveTextContent("다시 선택");
      expect(within(sheet).getByRole("button", { name: /태안 2일 여행/ })).toBeEnabled();
      expect(addPolicyToTripSpy).toHaveBeenCalledWith("401", "region-check");
    } finally {
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
    }
  });

  it("marks trips that already hold the policy in the trip picker", async () => {
    const linkedTrip: Trip = {
      ...getUpcomingPreviewTrip(),
      id: "403",
      title: "영광 담은 여행",
      linkedPolicies: [{ slug: examplePolicyDetail.slug, title: examplePolicyDetail.title, amount: "", region: "전남" }],
    };
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail);
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips").mockResolvedValue([linkedTrip]);

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);
      await userEvent.setup().click(await screen.findByRole("button", { name: /내 일정에 담기|일정에 담김/ }));
      expect(await screen.findByRole("button", { name: /영광 담은 여행/ })).toHaveTextContent("담음");
    } finally {
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });

  it("uses the region photo behind a regional policy and a benefit tile for nationwide ones", async () => {
    const regionalPolicy: Policy = {
      ...examplePolicyDetail,
      id: "busan-photo",
      slug: "busan-photo",
      title: "[부산영도] 디지털관광주민증 혜택",
      region: "부산",
      photo: null,
    };
    const nationwidePolicy: Policy = {
      ...examplePolicyDetail,
      id: "nation-tile",
      slug: "nation-tile",
      title: "내일로패스 할인",
      region: "전국",
      category: "교통",
      photo: null,
    };
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockImplementation((slug) => Promise.resolve(slug === "nation-tile" ? nationwidePolicy : regionalPolicy));

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/busan-photo");
      await screen.findByRole("heading", { level: 1, name: "디지털관광주민증 혜택" });
      const regionalHero = document.querySelector(".policy-detail-hero") as HTMLElement;
      expect(regionalHero.style.backgroundImage).toMatch(/busan/);
      expect(regionalHero.querySelector(".benefit-tile")).toBeNull();

      cleanup();
      renderAppRoute("/policies/nation-tile");
      await screen.findByRole("heading", { level: 1, name: "내일로패스 할인" });
      const nationwideHero = document.querySelector(".policy-detail-hero") as HTMLElement;
      expect(nationwideHero.style.backgroundImage).not.toMatch(/url\(/);
      expect(nationwideHero.querySelector(".benefit-tile.family-move")).toBeTruthy();
      expect(document.querySelector(".policy-detail-eyebrow")).toHaveTextContent("전국 공통");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("keeps an ended policy readable and says it has closed", async () => {
    const endedPolicy: Policy = {
      ...examplePolicyDetail,
      id: "ended-policy",
      slug: "ended-policy",
      title: "[태안] 대한민국 반값여행 지원",
      region: "충남",
      deadline: "2020-01-31",
    };
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(endedPolicy);

    try {
      await login();
      cleanup();
      renderAppRoute("/policies/ended-policy");
      const note = await screen.findByRole("note");
      expect(note).toHaveTextContent("모집이 끝난 혜택이에요");
      expect(note).toHaveTextContent("2020.01.31에 마감됐어요.");
      expect(screen.getByText("끝남")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /내 일정에 담기/ })).toBeEnabled();
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("lays the detail out in two columns with a summary card on wide screens", async () => {
    // jsdom 에는 matchMedia 가 없어 늘 좁은 화면이다. 1024px 이상인 척한다
    const hadMatchMedia = "matchMedia" in window;
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === "(min-width: 1024px)",
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;
    const getPolicySpy = vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([{ ...getUpcomingPreviewTrip(), id: "301", title: "넓은 화면 여행" }]);

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);
      const summary = await screen.findByRole("complementary", { name: "요약과 담기" });
      expect(document.querySelector(".prototype-policy-detail-screen")).toHaveClass("desktop-wide", "policy-detail-desk");
      // 받는 것·기간은 오른쪽 카드로 옮기고, 탭바 자리의 버튼 줄은 그리지 않는다
      expect(within(summary).getByText("받는 것")).toBeInTheDocument();
      expect(within(summary).getByText("기간")).toBeInTheDocument();
      expect(document.querySelector(".policy-detail-bar")).toBeNull();
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
      await userEvent.setup().click(within(summary).getByRole("button", { name: /내 일정에 담기|일정에 담김/ }));
      expect(await screen.findByRole("dialog", { name: "일정 선택" })).toBeInTheDocument();
      expect(await screen.findByText("넓은 화면 여행")).toBeInTheDocument();
    } finally {
      if (hadMatchMedia) window.matchMedia = originalMatchMedia;
      else Reflect.deleteProperty(window, "matchMedia");
      getPolicySpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });
});
