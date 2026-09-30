import { describe, expect, it } from "vitest";
import type { Policy } from "../api";
import { policyDetailText, policyHowTo, policyPlaceAndProgram, policyTimeline, won } from "./policyDetailText";

function policy(overrides: Partial<Policy>): Policy {
  return {
    id: "p",
    slug: "p",
    label: "P",
    tag: "지역할인",
    title: "정책",
    org: "기관",
    region: "경남",
    deadline: "",
    amount: "혜택 제공",
    summary: "",
    match: 50,
    category: "지역할인",
    requirements: [],
    documents: [],
    officialUrl: "https://example.com/official",
    applyUrl: null,
    ...overrides,
  };
}

const EMPTY_DETAIL = { supportContent: [], periods: [], applicationTarget: [], requiredDocuments: [], notes: [] };

describe("policy detail text", () => {
  it("turns a digital resident card policy into partner count, picks and a plain no-documents line", () => {
    const text = policyDetailText(
      policy({
        title: "[하동] 디지털관광주민증 혜택",
        summary: "디지털관광주민증 소지자 대상 하동(경남) 지역 방문 시 혜택을 제공합니다.",
        structuredDetail: {
          ...EMPTY_DETAIL,
          supportContent: [
            { title: "핵심 혜택", description: "하동 제휴처 29곳의 혜택을 제공합니다. 주요 분야: 관람 3곳, 숙박 5곳, 식음료 14곳." },
            { title: "카테고리별 인기 혜택", description: "인기순 대표 제휴처와 주요 혜택을 카테고리별로 정리했습니다." },
            {
              title: "카테고리별 인기 혜택",
              description: "🏨 악양별서: 1박 당 10,000원 할인\n감성 체험 숙소",
              url: "https://example.com/partner/1",
            },
            { title: "카테고리별 인기 혜택", description: "🍽️ 위험: 링크", url: "javascript:alert(1)" },
          ],
          requiredDocuments: [{ title: "필요서류", description: "별도 제출 서류 없음, 디지털관광주민증 발급 및 제시 기준으로 적용" }],
          notes: [
            { title: "비고", description: "제휴처별 할인율은 VisitKorea 공식 안내에서 최종 확인하세요." },
            { title: "비고", description: "지역별 제휴처와 혜택은 변동될 수 있습니다." },
            { title: "비고", description: "하동 제휴처 목록: 2026-09 수집" },
          ],
        },
      }),
    );

    expect(text.partnerCount).toBe(29);
    expect(text.partnerMix).toBe("식음료 14 · 숙박 5 · 관람 3");
    // 목록 소개 문장과 안전하지 않은 주소는 제휴처 줄이 되지 않는다
    expect(text.picks).toEqual([
      { category: "숙박", name: "악양별서", benefit: "1박 당 1만원 할인", note: "감성 체험 숙소", url: "https://example.com/partner/1" },
    ]);
    expect(text.extra).toEqual([]);
    expect(text.lead).toBe("");
    expect(text.noDocuments).toBe("디지털관광주민증을 발급받아 제휴처에 보여 주면 돼요.");
    expect(text.notes).toEqual([]);
    expect(text.provenance).toEqual(["하동 제휴처 목록: 2026-09 수집"]);
  });

  it("drops template sentences, keeps the specific lead and re-joins conditions split inside parentheses", () => {
    const text = policyDetailText(
      policy({
        title: "[강진] 대한민국 반값여행 지원",
        summary: "강진 반값여행 지원",
        amount: "최대 20만원 환급",
        structuredDetail: {
          ...EMPTY_DETAIL,
          supportContent: [
            { title: "혜택", description: "최대 20만원 환급" },
            { title: "혜택 적용 조건", description: "여행유형(가족" },
            { title: "혜택 적용 조건", description: "개인" },
            { title: "혜택 적용 조건", description: "청년) 중복신청 불가" },
            { title: "지원내용", description: "강진 지역 여행 후 공식 안내에서 정한 기준을 충족하면 최대 20만원 환급" },
            { title: "지원내용", description: "숙박·식사 등 지역 여행 지출을 대상으로 50%를 상품권으로 돌려줍니다." },
            { title: "받는 방법 ①", description: "① 사전 신청" },
            { title: "대상 열차", description: "KTX" },
            { title: "대상 열차", description: "ITX" },
          ],
          applicationTarget: [{ title: "신청대상", description: "강진군 외 지역 거주 사전 신청 관광객" }],
        },
      }),
    );

    expect(text.lead).toBe("숙박·식사 등 지역 여행 지출을 대상으로 50%를 상품권으로 돌려줍니다.");
    expect(text.more).toEqual([]);
    expect(text.spend).toBe("숙박·식사");
    expect(text.conditions).toEqual(["여행유형(가족, 개인, 청년) 중복신청 불가"]);
    expect(text.steps).toEqual(["사전 신청"]);
    expect(text.extra).toEqual([{ title: "대상 열차", items: ["KTX", "ITX"] }]);
    expect(policyHowTo({ applyUrl: null }, "refund", text.target)).toBe("사전 신청 후 여행");
    expect(policyHowTo({ applyUrl: "https://apply.example" }, "refund", text.target)).toBe("바로 신청");
  });

  it("reads period dates from collected dates first, then from dotted or short text", () => {
    const text = policyDetailText(
      policy({
        structuredDetail: {
          ...EMPTY_DETAIL,
          periods: [
            { title: "신청 기간", description: "신청 기간: 2026-04-01~2026-11-30 (예정)", startDate: "2026-04-01", endDate: "2026-11-30" },
            { title: "쿠폰 발급기간", description: "2026.06.11 ~ 2026.07.31" },
            { title: "3차 여행 기간", description: "3차 여행기간: 10.1~11.1" },
            { title: "1차 신청 기간", description: "2026-09-21 18:00" },
          ],
        },
      }),
    );

    expect(text.periods.map(({ start, end, note }) => [start, end, note])).toEqual([
      ["2026-04-01", "2026-11-30", "예정"],
      ["2026-06-11", "2026-07-31", null],
      [expect.stringMatching(/^\d{4}-10-01$/), expect.stringMatching(/^\d{4}-11-01$/), true],
      [null, null, null],
    ]);
    const timeline = policyTimeline(text.periods, null, null);
    expect(timeline.rows.map((row) => row.label)).toEqual(["신청", "쿠폰 발급", "3차 여행"]);
    expect(timeline.loose).toEqual(["1차 신청 기간: 2026-09-21 18:00"]);
    // 날짜 있는 기간이 없으면 시작~마감을 '기간' 한 줄로
    expect(policyTimeline([], "2026-05-01", "2026-06-30").rows).toEqual([
      { label: "기간", start: "2026-05-01", end: "2026-06-30", note: null },
    ]);
  });

  it("keeps only the original text for policies collected before structured detail", () => {
    const text = policyDetailText(
      policy({
        summary: "영광 방문 혜택을 확인할 수 있습니다.",
        requirements: ["전남 영광 방문", "공식 안내에서 신청 조건을 확인하세요."],
        documents: ["디지털관광주민증", "공식 공고 확인 필요"],
      }),
    );

    expect(text.lead).toBe("영광 방문 혜택을 확인할 수 있습니다.");
    expect(text.target).toEqual(["전남 영광 방문"]);
    expect(text.documents).toEqual(["디지털관광주민증"]);
  });

  it("formats won amounts and splits the place out of the title", () => {
    expect(won("정상가 140,000원 · 10000원 할인 · 2500원")).toBe("정상가 14만원 · 1만원 할인 · 2500원");
    expect(policyPlaceAndProgram("[고성] 2026 대한민국 숙박세일 페스타")).toEqual({ place: "고성", program: "대한민국 숙박세일 페스타" });
    expect(policyPlaceAndProgram("부산 공식 캐시백")).toEqual({ place: null, program: "부산 공식 캐시백" });
  });
});
