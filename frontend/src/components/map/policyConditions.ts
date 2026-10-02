import { useSyncExternalStore } from "react";

/* 정책 탭의 좁히기 조건(시안 v55): 마감 · 금액 · 관심 정책만 · 글 검색('…모두 보기').
   지도 층처럼 주소에 두지 않는다 - 조건은 층이 아니라서 뒤로가기(기기 · 화면 안 ‹)로 풀리면 안 되는데, 주소에 두면
   층마다 쌓아 둔 앞 칸이 조건 없는 주소라 기기 뒤로가기가 조건을 지웠다. 상세에 다녀와도 남고 새로 고쳐도 남게
   이 탭의 sessionStorage 에 둔다. 목록 머리의 ✕ 로만 푼다. 혜택 형태 · 지역은 위 칩 · 지도(주소의 type · place)다. */
export const PERIOD_FILTERS = ["전체", "7일 이내", "30일 이내", "3개월 이내"] as const;
export const AMOUNT_FILTERS = ["전체", "금액 명시", "10만원 이상", "30만원 이상"] as const;
export type PeriodFilter = (typeof PERIOD_FILTERS)[number];
export type AmountFilter = (typeof AMOUNT_FILTERS)[number];

export type PolicyConditions = { period: PeriodFilter; amount: AmountFilter; savedOnly: boolean; text: string };

export const NO_CONDITIONS: PolicyConditions = { period: "전체", amount: "전체", savedOnly: false, text: "" };

const STORAGE_KEY = "travel-hunter.policy-conditions";
const listeners = new Set<() => void>();
let current = load();

function load(): PolicyConditions {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? "null") as Partial<PolicyConditions> | null;
    if (!saved) return NO_CONDITIONS;
    return {
      period: PERIOD_FILTERS.includes(saved.period as PeriodFilter) ? (saved.period as PeriodFilter) : "전체",
      amount: AMOUNT_FILTERS.includes(saved.amount as AmountFilter) ? (saved.amount as AmountFilter) : "전체",
      savedOnly: saved.savedOnly === true,
      text: typeof saved.text === "string" ? saved.text.slice(0, 100) : "",
    };
  } catch {
    return NO_CONDITIONS;
  }
}

export function setPolicyConditions(next: PolicyConditions) {
  current = next;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // 저장소를 못 쓰면(사생활 보호 창 등) 이 화면에서만 산다
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function usePolicyConditions(): PolicyConditions {
  return useSyncExternalStore(subscribe, () => current);
}

/** 필터 단추의 수 - 글 검색까지 센다. 목록이 내려가(휴대폰 지도 중심) 조건 줄이 가려져도 단추가 조건이 걸렸다고 말한다 */
export const conditionCount = (c: PolicyConditions) =>
  Number(c.period !== "전체") + Number(c.amount !== "전체") + Number(c.savedOnly) + Number(Boolean(c.text));

/** 목록 머리 아래 한 줄. 걸린 게 없으면 null */
export function conditionLabel(c: PolicyConditions): string | null {
  const parts = [
    c.text && `‘${c.text}’ 검색`,
    c.period !== "전체" && `마감 ${c.period}`,
    c.amount !== "전체" && c.amount,
    c.savedOnly && "관심 정책만",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
