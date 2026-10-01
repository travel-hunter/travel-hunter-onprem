import type { ReactNode } from "react";
import type { Policy } from "../api";
import "../styles/benefit-tile.css";

/* 혜택 형태 그림 칸. 홈·정책 목록·정책 상세가 같은 칸을 쓴다.
   색은 세 갈래 - 숙박(보라) · 돈(금색) · 이동(파랑) - 로 묶어 형태가 많아도 한눈에 갈린다.
   지금은 제목 키워드로 나눈다. 수집 단계에 형태 필드가 생기면 그 값으로 옮길 것. */
export type BenefitType = "stay" | "refund" | "partner" | "train" | "plane" | "car" | "ship" | "trip";
export type BenefitTileKind = BenefitType | "nation";
type BenefitFamily = "stay" | "money" | "move";

export const BENEFIT_TYPES: Record<BenefitTileKind, { label: string; family: BenefitFamily }> = {
  stay: { label: "숙박 할인", family: "stay" },
  refund: { label: "여행비 환급", family: "money" },
  partner: { label: "제휴 할인", family: "money" },
  train: { label: "기차", family: "move" },
  plane: { label: "항공", family: "move" },
  car: { label: "자동차", family: "move" },
  ship: { label: "배", family: "move" },
  trip: { label: "여행상품", family: "move" },
  nation: { label: "전국 공통", family: "move" },
};

export function benefitTypeOf(policy: Pick<Policy, "title" | "category"> & { cardSummary?: string | null }): BenefitType {
  const { title, category } = policy;
  if (/반값여행/.test(title)) return "refund";
  if (/디지털관광주민증/.test(title)) return "partner";
  if (category === "숙박" || /숙박/.test(title)) return "stay";
  // 받는 것(카드 요약)도 본다 - '바다가는 달'은 제목만 보면 배지만 실제는 렌터카 쿠폰이다
  if (/렌터카|자동차|운전/.test(`${title} ${policy.cardSummary ?? ""}`)) return "car";
  if (/열차|내일로|기차/.test(title)) return "train";
  if (/항공|비행기/.test(title)) return "plane";
  if (/바다|섬|여객선|배편/.test(title)) return "ship";
  return "trip";
}

/* 24px 칸, 선 1.75px. .f = 옅은 면, .w = 칸 바탕색으로 가리는 면, .dot = 선 색으로 채운 점 */
const ICONS: Record<BenefitTileKind, ReactNode> = {
  stay: (
    <>
      <path className="f" d="M3 12.5h14.5a3.5 3.5 0 0 1 3.5 3.5v1H3z" />
      <path d="M3 6v13M21 17v2" />
      <rect className="f" x="5.5" y="8.5" width="5.5" height="4" rx="1.5" />
    </>
  ),
  refund: (
    <>
      <circle className="f" cx="15.5" cy="6.5" r="3" />
      <rect className="f" x="3" y="8.5" width="18" height="11.5" rx="2.5" />
      <path d="M21 12h-3.5a2 2 0 0 0 0 4H21" />
      <circle className="dot" cx="17.5" cy="14" r="0.9" />
    </>
  ),
  partner: (
    <>
      <path
        className="f"
        d="M3 8.5A2.5 2.5 0 0 1 5.5 6h13A2.5 2.5 0 0 1 21 8.5v1.8a1.7 1.7 0 0 0 0 3.4v1.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 15.5v-1.8a1.7 1.7 0 0 0 0-3.4z"
      />
      <path d="M9.5 14.5l5-5" />
      <circle className="dot" cx="9.6" cy="9.6" r="1.1" />
      <circle className="dot" cx="14.4" cy="14.4" r="1.1" />
    </>
  ),
  train: (
    <>
      <rect className="f" x="5.5" y="3" width="13" height="14" rx="3.5" />
      <rect className="w" x="8" y="6" width="8" height="4.5" rx="1" />
      <circle className="dot" cx="9" cy="13.8" r="0.9" />
      <circle className="dot" cx="15" cy="13.8" r="0.9" />
      <path d="M8.5 17l-2 3.5M15.5 17l2 3.5" />
    </>
  ),
  plane: (
    <path
      className="f"
      d="M12 3.2c.9 0 1.5.8 1.5 1.8v5.3l7.2 4v2l-7.2-2.2v3.6l2 1.5v1.6L12 20l-3.5.8v-1.6l2-1.5v-3.6l-7.2 2.2v-2l7.2-4V5c0-1 .6-1.8 1.5-1.8z"
    />
  ),
  car: (
    <>
      <path
        className="f"
        d="M3 16.5v-3.2a1.5 1.5 0 0 1 .9-1.4l2.3-1 1.9-3.6A1.5 1.5 0 0 1 9.4 6.5h5.4a1.5 1.5 0 0 1 1.2.6l2.8 3.6 1.6.7a1.5 1.5 0 0 1 .9 1.4v3.7z"
      />
      <path d="M6.4 10.9h12.4M12 6.5v4.4" />
      <circle className="w" cx="7.5" cy="16.5" r="2" />
      <circle className="w" cx="16.5" cy="16.5" r="2" />
    </>
  ),
  ship: (
    <>
      <path d="M8 13.5v-4h8v4M10.5 9.5v-3h3v3" />
      <path className="f" d="M3.5 13.5h17l-2.4 4.3a1.5 1.5 0 0 1-1.3.7H7.2a1.5 1.5 0 0 1-1.3-.7z" />
      <path d="M3 21c1.5 0 1.5-.9 3-.9s1.5.9 3 .9 1.5-.9 3-.9 1.5.9 3 .9 1.5-.9 3-.9 1.5.9 3 .9" />
    </>
  ),
  trip: (
    <>
      <path d="M9 7.5V6a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 6v1.5" />
      <rect className="f" x="4" y="7.5" width="16" height="12" rx="2.5" />
      <path d="M8.5 7.5v12M15.5 7.5v12" />
    </>
  ),
  nation: (
    <>
      <circle className="f" cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5M12 3.5c-2.5 2.6-3.5 5.4-3.5 8.5s1 5.9 3.5 8.5" />
    </>
  ),
};

/* decorative(기본): 옆 글자가 이미 형태를 말할 때. false 면 칸 자체가 형태 이름을 읽힌다. */
export function BenefitTile({
  kind,
  decorative = true,
  size = "md",
}: {
  kind: BenefitTileKind;
  decorative?: boolean;
  size?: "sm" | "md";
}) {
  const meta = BENEFIT_TYPES[kind];
  const a11y = decorative ? { "aria-hidden": true } : { role: "img", "aria-label": meta.label };
  return (
    <span className={`benefit-tile ${size} family-${meta.family}`} {...a11y}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        {ICONS[kind]}
      </svg>
    </span>
  );
}
