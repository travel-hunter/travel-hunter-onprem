import type { Policy, PolicyStructuredDetailItem } from "../../api";
import { won } from "../../utils/policyDetailText";

/* 정책 탭 목록 줄의 '받는 것' 한 줄(head)과 그 지역만의 한 줄(detail). 시안 v40 의 규칙(benefit_text.py)을 옮겼다.
   수집된 상세(structuredDetail)에서 규칙으로 뽑으므로 정책 상세 화면과 출처가 같다 - 검수된 카드 문구(cardSummary)만 쓰던
   목록에도 쓰기로 했다(2026-09-30 사용자 결정). partners = 디지털관광주민증 제휴처 수(묶음 머리의 합계용). */
export type PolicyListText = { head: string; detail: string; partners: number };

const supportItems = (policy: Policy): PolicyStructuredDetailItem[] => policy.structuredDetail?.supportContent ?? [];
const describedAs = (policy: Policy, title: string) =>
  supportItems(policy).filter((item) => item.title === title).map((item) => item.description ?? "");

/* 괄호 속 조건은 상세에서 - 목록 한 줄은 짧게 */
function tidy(text: string): string {
  return text
    .split(" / ")[0]
    .replace(/-->/g, "→")
    .replace(/>/g, "→")
    .replace(/\([^)]*\)/g, "")
    .replace(/\([^)]*$/, "")
    .replace(/○/g, " ")
    .replace(/(\d+%)\s*할인/g, "$1 할인")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[\s,]+|[\s,]+$/g, "");
}

/* 첫 문장만. 뒤보기(lookbehind) 없이 쓴다 - 옛 사파리는 그 문법에서 스크립트 전체가 멈춘다 */
function firstSentence(text: string, limit = 70): string {
  const flat = text.replace(/\s+/g, " ").trim();
  const end = /[다요]\.\s/.exec(flat);
  const cut = (end ? flat.slice(0, end.index + 1) : flat).replace(/\.+$/, "");
  return cut.length <= limit ? cut : `${cut.slice(0, limit - 1).trimEnd()}…`;
}

function partnerText(policy: Policy): PolicyListText {
  const core = describedAs(policy, "핵심 혜택")[0] ?? "";
  const count = Number(/제휴처\s*(\d+)곳/.exec(core)?.[1] ?? 0);
  const picks: string[] = [];
  for (const item of supportItems(policy)) {
    if (item.title !== "카테고리별 인기 혜택" || !item.url) continue;
    const line = (item.description ?? "").split("\n")[0].replace(/^[^\w가-힣]+/u, "");
    const colon = line.indexOf(":");
    const name = (colon < 0 ? line : line.slice(0, colon)).trim();
    let benefit = colon < 0 ? "" : line.slice(colon + 1).trim();
    const first = benefit.split(",")[0].trim();
    if (/할인|제공|리필/.test(first)) benefit = first; // 첫 조각만으로 뜻이 통할 때만 자른다
    if (name && benefit.startsWith(name)) benefit = benefit.slice(name.length).trim();
    benefit = tidy(won(benefit));
    if (benefit) picks.push(`${tidy(name)} ${benefit}`);
  }
  return {
    head: count ? `제휴처 ${count}곳 할인` : "지역 제휴 할인",
    detail: picks.slice(0, 2).join(" · ") || firstSentence(core),
    partners: count,
  };
}

const PAY_APPS: Record<string, string> = { chak: "chak 앱", 코나아이: "코나아이 앱", 제로페이: "제로페이 앱" };

function refundText(policy: Policy): PolicyListText {
  const conditions = describedAs(policy, "혜택 적용 조건").join(" ");
  const body = `${supportItems(policy).map((item) => item.description ?? "").join(" ")} ${policy.summary ?? ""}`;
  const parts: string[] = [];
  const spots = /관광지\s*(\d)\s*개소/.exec(conditions) ?? /관광사진\s*(\d)장/.exec(body);
  if (spots) parts.push(`관광지 ${spots[1]}곳 인증`);
  const spend = /(\d+)\s*만\s*원\s*이상\s*결제/.exec(conditions);
  if (spend) parts.push(`${spend[1]}만원 이상 결제`);
  const pay = /(제로페이|chak|코나아이)/.exec(conditions);
  if (pay) parts.push(`${PAY_APPS[pay[1]]}으로 결제`);
  else if (body.includes("상품권")) parts.push("지역 상품권으로 환급");
  const rate = body.includes("50%") ? "여행비 50% 환급" : "여행비 환급";
  const amount = /최대\s*(\d+)\s*만\s*원/.exec(policy.cardSummary ?? "");
  const plan = describedAs(policy, "지원내용").map((text) => firstSentence(text, 80));
  return {
    head: amount ? `${rate} · 최대 ${amount[1]}만원` : rate,
    detail: parts.join(" · ") || plan[0] || "",
    partners: 0,
  };
}

function otherText(policy: Policy): PolicyListText {
  const texts = supportItems(policy).map((item) => item.description ?? "").filter(Boolean);
  const first = texts[0] ?? policy.summary ?? "";
  return { head: won(policy.cardSummary ?? ""), detail: first ? firstSentence(won(first)) : "", partners: 0 };
}

export function policyListText(policy: Policy): PolicyListText {
  if (policy.title.includes("디지털관광주민증")) return partnerText(policy);
  if (policy.title.includes("반값여행")) return refundText(policy);
  // 숙박은 받는 것(할인권 금액)이 곧 내용이라 지역 줄이 따로 없다
  if (policy.category === "숙박") return { head: won(policy.cardSummary ?? ""), detail: "", partners: 0 };
  return otherText(policy);
}

/* 묶음 머리에 한 번 보일 공통 문구(시안 v40). 수집된 요약을 바탕으로 말투만 다듬은 고정 문구라,
   사업 내용이 바뀌면 여기도 다시 볼 것. {sum} = 보이는 지역의 제휴처 합 */
export const PROGRAM_GROUP_COPY: Record<string, { head: string; desc: string }> = {
  "디지털관광주민증 혜택": {
    head: "제휴처 {sum}곳에서 할인",
    desc: "주민증을 발급해 제휴처에서 보여 주면 숙박·식음·체험·관광지 할인을 받아요.",
  },
  "대한민국 반값여행 지원": {
    head: "여행비 50% 환급 · 최대 20만원",
    desc: "숙박·식사·체험에 쓴 돈의 절반을 돌려받아요. 1명 최대 10만원, 2명 이상 20만원.",
  },
  "대한민국 숙박세일 페스타 숙박 할인": {
    head: "숙박 할인권 2·3·5·7만원",
    desc: "참여 온라인 여행사에서 숙박을 예약하면 할인권을 받아요.",
  },
};
