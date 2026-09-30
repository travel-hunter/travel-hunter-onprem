import { describe, expect, it } from "vitest";
import type { Policy } from "../../api";
import { policyListText } from "./policyListText";

function policy(title: string, extra: Partial<Policy>): Policy {
  return {
    id: title,
    slug: title,
    label: "",
    tag: "",
    title,
    org: "",
    region: "전남",
    deadline: "2026-10-31",
    amount: "",
    summary: "",
    match: 0,
    category: "여행상품",
    requirements: [],
    documents: [],
    officialUrl: null,
    applyUrl: null,
    ...extra,
  };
}

describe("policy list text (시안 v40 목록 한 줄)", () => {
  it("reads a half-price refund's rate, cap and the place's own conditions", () => {
    const text = policyListText(
      policy("[영광] 대한민국 반값여행 지원", {
        cardSummary: "최대 20만원 환급",
        summary: "여행 경비의 50%를 돌려드립니다.",
        structuredDetail: {
          supportContent: [
            { title: "혜택 적용 조건", description: "지정 관광지 2개소 방문 인증(사진), 코나아이 앱으로 결제한 금액" },
          ],
        } as Policy["structuredDetail"],
      }),
    );
    expect(text).toEqual({ head: "여행비 50% 환급 · 최대 20만원", detail: "관광지 2곳 인증 · 코나아이 앱으로 결제", partners: 0 });
  });

  it("counts resident-card partners and shows the first two picks without their conditions", () => {
    const text = policyListText(
      policy("[하동] 디지털관광주민증 혜택", {
        structuredDetail: {
          supportContent: [
            { title: "핵심 혜택", description: "제휴처 29곳에서 할인을 받을 수 있어요." },
            { title: "카테고리별 인기 혜택", url: "https://example.com/a", description: "☕ 더로드101: 음료 10% 할인, 굿즈 증정" },
            { title: "카테고리별 인기 혜택", url: "https://example.com/b", description: "🏨 악양별서: 1박 당 10,000원 할인(주말 제외)" },
            { title: "카테고리별 인기 혜택", description: "링크 없는 줄은 뺀다: 무료" },
          ],
        } as Policy["structuredDetail"],
      }),
    );
    expect(text.head).toBe("제휴처 29곳 할인");
    expect(text.partners).toBe(29);
    expect(text.detail).toBe("더로드101 음료 10% 할인 · 악양별서 1박 당 1만원 할인");
  });

  it("keeps stay discounts to their amount and other benefits to the first sentence", () => {
    expect(policyListText(policy("숙박 할인", { category: "숙박", cardSummary: "30,000원 할인권" }))).toEqual({
      head: "3만원 할인권",
      detail: "",
      partners: 0,
    });
    const other = policyListText(
      policy("내일로패스 할인", {
        cardSummary: "2만원 할인",
        structuredDetail: {
          supportContent: [{ title: "지원내용", description: "내일로패스 탑승권을 2만원 할인해요. 기간 안에 한 번만 쓸 수 있어요." }],
        } as Policy["structuredDetail"],
      }),
    );
    expect(other).toEqual({ head: "2만원 할인", detail: "내일로패스 탑승권을 2만원 할인해요", partners: 0 });
  });
});
