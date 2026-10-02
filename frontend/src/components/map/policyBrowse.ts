import type { Policy } from "../../api";
import { BENEFIT_TYPES, benefitTypeOf, type BenefitType } from "../benefitTile";
import { daysUntilPolicyDeadline, isDigitalTourismResidentCardPolicy, isSafePolicyDeadline } from "../../utils";
import { cityOf, NATIONWIDE_REGION, programOf } from "../../utils/policyPrograms";

/* 정책 탭 지도 화면의 목록·검색·칩이 쓰는 계산. 화면 없이 돌아가는 순수 함수만 둔다. */

/* ── 위 칩: 혜택 형태 ─────────────────────────────────────────── */
export type BrowseFilter = "stay" | "refund" | "partner" | "move";

export const BROWSE_FILTERS: ReadonlyArray<{ key: BrowseFilter | null; label: string; icon?: BenefitType }> = [
  { key: null, label: "전체" },
  { key: "stay", label: "숙박", icon: "stay" },
  { key: "refund", label: "환급", icon: "refund" },
  { key: "partner", label: "제휴 할인", icon: "partner" },
  { key: "move", label: "교통", icon: "train" },
];

export function isBrowseFilter(value: string | null): value is BrowseFilter {
  return value === "stay" || value === "refund" || value === "partner" || value === "move";
}

/* 교통은 기차·항공·자동차·배·여행상품을 한데 묶는다 - 모두 '이동' 갈래 */
export function filterKeyOf(policy: Policy): BrowseFilter {
  const type = benefitTypeOf(policy);
  return BENEFIT_TYPES[type].family === "move" ? "move" : (type as BrowseFilter);
}

export function matchesBrowseFilter(policy: Policy, key: BrowseFilter | null): boolean {
  return !key || filterKeyOf(policy) === key;
}

export const filterLabel = (key: BrowseFilter) => BROWSE_FILTERS.find((f) => f.key === key)?.label ?? "";

/* 정책 이름에서 [시군]과 연도 머리를 뗀 사업 이름. 묶기와 검색의 열쇠다. */
export const programName = (policy: Pick<Policy, "title">) => programOf(policy).replace(/^20\d{2}\s+/, "");

export const REGION_FULL_NAMES: Readonly<Record<string, string>> = {
  서울: "서울특별시", 부산: "부산광역시", 대구: "대구광역시", 인천: "인천광역시", 광주: "광주광역시", 대전: "대전광역시",
  울산: "울산광역시", 세종: "세종특별자치시", 경기: "경기도", 강원: "강원특별자치도", 충북: "충청북도", 충남: "충청남도",
  전북: "전북특별자치도", 전남: "전라남도", 경북: "경상북도", 경남: "경상남도", 제주: "제주특별자치도",
};
/* 건수가 같을 때 쓰는 순서 */
export const REGION_ORDER = Object.keys(REGION_FULL_NAMES);

export function countByRegion(policies: Policy[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const policy of policies) counts[policy.region] = (counts[policy.region] ?? 0) + 1;
  return counts;
}

/* ── 마감 표 ───────────────────────────────────────────────────
   일주일 안은 붉게, 한 달 안은 노랗게, 그 뒤는 날짜만. 주민증은 짧은 칩이라 '상시'(시안 v40 - 상세의 기간 칸은 '상시 발급').
   earliest = 묶음처럼 여러 마감 중 가장 이른 것을 보일 때 - "D-5부터" */
export type DeadlineChip = { tone: "urgent" | "soon" | "later" | "always"; text: string };

export function deadlineChip(
  policy: Pick<Policy, "title" | "officialUrl" | "deadline">,
  earliest = false,
): DeadlineChip {
  if (isDigitalTourismResidentCardPolicy(policy)) return { tone: "always", text: "상시" };
  const days = isSafePolicyDeadline(policy.deadline) ? daysUntilPolicyDeadline(policy.deadline) : null;
  if (days === null) return { tone: "always", text: "기간 확인" };
  if (days < 0) return { tone: "later", text: "마감" };
  if (days <= 7) return { tone: "urgent", text: (days === 0 ? "오늘" : `D-${days}`) + (earliest ? "부터" : days === 0 ? " 마감" : "") };
  if (days <= 30) return { tone: "soon", text: `D-${days}${earliest ? "부터" : ""}` };
  const [, month, day] = (policy.deadline as string).split("-");
  return { tone: "later", text: `${Number(month)}.${Number(day)}${earliest ? "부터" : " 마감"}` };
}

const deadlineKey = (policy: Policy) =>
  !isDigitalTourismResidentCardPolicy(policy) && isSafePolicyDeadline(policy.deadline) ? policy.deadline : "9999";

export function byDeadline(left: Policy, right: Policy) {
  return deadlineKey(left).localeCompare(deadlineKey(right)) || (cityOf(left) ?? "").localeCompare(cityOf(right) ?? "", "ko");
}

/* 한 줄씩 늘어놓을 때: 마감순, 같은 날이면 사업끼리 붙여 이어 쓰기가 되게 */
export function byListOrder(left: Policy, right: Policy) {
  return deadlineKey(left).localeCompare(deadlineKey(right))
    || programName(left).localeCompare(programName(right), "ko")
    || (cityOf(left) ?? "").localeCompare(cityOf(right) ?? "", "ko");
}

/* ── 목록 ──────────────────────────────────────────────────────
   지명만 다른 같은 사업은 한 줄로 묶는다(92건이 실은 몇 종이다). 모든 지역에서는 전국 공통을
   맨 위 한 묶음으로 - 서로 다른 사업이라 사업별 묶기에 안 걸린다. */
export const NATION_KEY = "전국 공통";

export type BrowseEntry =
  | { kind: "row"; policy: Policy }
  | { kind: "group"; key: string; items: Policy[] }
  | { kind: "nation"; key: typeof NATION_KEY; items: Policy[] };

export function groupEntries(policies: Policy[]): BrowseEntry[] {
  const groups = new Map<string, Policy[]>();
  for (const policy of policies) {
    const key = programName(policy);
    const bucket = groups.get(key) ?? [];
    bucket.push(policy);
    groups.set(key, bucket);
  }
  return Array.from(groups, ([key, items]) => ({ key, items: items.slice().sort(byDeadline) }))
    .sort((left, right) => byDeadline(left.items[0], right.items[0]) || right.items.length - left.items.length)
    .map((group): BrowseEntry => (group.items.length > 1
      ? { kind: "group", key: group.key, items: group.items }
      : { kind: "row", policy: group.items[0] }));
}

export type BrowseView = {
  title: string;
  count: number;
  sub: string;
  entries: BrowseEntry[];
  /** 고른 곳에 전용 혜택이 없을 때 한 줄 - 아래에 전국 공통을 대신 보인다 */
  empty: string | null;
  /** 고른 지역 목록 끝의 "전국 공통 혜택 N건도 여기서 쓸 수 있어요" */
  nationMore: number;
};

/* policies 는 칩·사업 고르기가 이미 걸린 것 */
export function browseView(
  policies: Policy[],
  region: string | null,
  city: string | null,
  filter: BrowseFilter | null,
): BrowseView {
  const word = filter ? `${filterLabel(filter)} ` : "";
  const nation = policies.filter((policy) => policy.region === NATIONWIDE_REGION);
  if (!region) {
    const local = policies.filter((policy) => policy.region !== NATIONWIDE_REGION);
    const head: BrowseEntry[] = nation.length ? [{ kind: "nation", key: NATION_KEY, items: nation.slice().sort(byListOrder) }] : [];
    return {
      title: "모든 지역",
      count: policies.length,
      sub: `${word}마감 임박순 · 지도를 눌러 지역을 고르세요`,
      entries: [...head, ...groupEntries(local)],
      empty: null,
      nationMore: 0,
    };
  }
  if (region === NATIONWIDE_REGION) {
    return { title: NATION_KEY, count: nation.length, sub: "어느 지역을 가도 쓸 수 있는 혜택", entries: groupEntries(nation), empty: null, nationMore: 0 };
  }
  const own = policies.filter((policy) => policy.region === region && (!city || cityOf(policy) === city));
  const title = city ?? region;
  const sub = `${city ? `${region} · ` : ""}${word}마감 임박순`;
  if (!own.length) {
    const hint = nation.length
      ? `전국 어디서나 쓰는 ${word}혜택 ${nation.length}건을 대신 보여 드려요.`
      : "지도에서 다른 지역을 눌러 보세요.";
    return { title, count: 0, sub, entries: groupEntries(nation), empty: `${title} 전용 ${word}혜택은 아직 없어요. ${hint}`, nationMore: 0 };
  }
  return { title, count: own.length, sub, entries: groupEntries(own), empty: null, nationMore: nation.length };
}

/* 칩 옆 건수. 고른 지역(시군까지)·사업 안에서 센다 - 목록과 같은 범위여야 칩을 눌러 빈 목록이 안 나온다 */
export function chipCounts(policies: Policy[], region: string | null, program: string | null, city: string | null = null) {
  const base = policies.filter(
    (policy) => (!region || policy.region === region) && (!city || cityOf(policy) === city) && (!program || programName(policy) === program),
  );
  return new Map(BROWSE_FILTERS.map((f) => [f.key, base.filter((policy) => matchesBrowseFilter(policy, f.key)).length]));
}

/* ── 지역 요약 카드 ───────────────────────────────────────────── */
export type RegionSummary = {
  fullName: string;
  count: number;
  /** 가장 많은 형태 */
  lead: BrowseFilter | null;
  cities: number;
  kinds: Array<{ key: BrowseFilter; count: number }>;
  soonest: string | null;
};

export function regionSummary(policies: Policy[], region: string): RegionSummary {
  const list = policies.filter((policy) => policy.region === region);
  const fullName = REGION_FULL_NAMES[region] ?? region;
  const counts = new Map<BrowseFilter, number>();
  for (const policy of list) counts.set(filterKeyOf(policy), (counts.get(filterKeyOf(policy)) ?? 0) + 1);
  const kinds = Array.from(counts, ([key, count]) => ({ key, count })).sort((left, right) => right.count - left.count);
  const cities = new Set(list.map(cityOf).filter(Boolean)).size;
  const soon = list.filter((policy) => deadlineKey(policy) !== "9999").sort(byDeadline)[0];
  const soonest = soon
    ? `${cityOf(soon) ?? fullName} ${BENEFIT_TYPES[benefitTypeOf(soon)].label} ${deadlineChip(soon).text}`
    : null;
  return { fullName, count: list.length, lead: kinds[0]?.key ?? null, cities, kinds, soonest };
}

/* ── 돋보기 검색 ───────────────────────────────────────────────
   비워 두면 지역 목록, 치면 시도·시군·사업. 시군은 혜택이 있는 곳만 찾힌다(제목의 [시군]). */
export type BrowseSearch = {
  regions: Array<{ region: string; count: number }>;
  places: Array<{ place: string; region: string; count: number }>;
  programs: Array<{ name: string; count: number; type: BenefitType; nation: boolean }>;
};

export function searchBrowse(policies: Policy[], query: string): BrowseSearch {
  const q = query.trim();
  const counts = countByRegion(policies);
  const regions = REGION_ORDER
    .filter((region) => region.includes(q) || REGION_FULL_NAMES[region].includes(q))
    .map((region) => ({ region, count: counts[region] ?? 0 }));
  const places = new Map<string, { place: string; region: string; count: number }>();
  const programs = new Map<string, { name: string; count: number; type: BenefitType; nation: boolean }>();
  for (const policy of policies) {
    const place = cityOf(policy);
    if (place && place.includes(q)) {
      const key = `${place}|${policy.region}`;
      const entry = places.get(key) ?? { place, region: policy.region, count: 0 };
      entry.count += 1;
      places.set(key, entry);
    }
    const name = programName(policy);
    if (name.includes(q)) {
      const entry = programs.get(name) ?? { name, count: 0, type: benefitTypeOf(policy), nation: policy.region === NATIONWIDE_REGION };
      entry.count += 1;
      programs.set(name, entry);
    }
  }
  return { regions, places: Array.from(places.values()), programs: Array.from(programs.values()) };
}

/* 돋보기를 비워 두었을 때의 지역 사진 칸 - 혜택 많은 순, 같으면 REGION_ORDER */
export function regionTiles(policies: Policy[]) {
  const counts = countByRegion(policies);
  return [...REGION_ORDER]
    .sort((left, right) => (counts[right] ?? 0) - (counts[left] ?? 0))
    .map((region) => ({ region, count: counts[region] ?? 0 }));
}

/* ── 주소에 담는 화면 층 ────────────────────────────────────────
   지도 화면의 상태는 전부 주소에 둔다 - 상세에 갔다 뒤로 와도, 새로고침해도 같은 화면이다.
   뒤로는 '층'으로 걷는다: 검색 닫기 → 한 페이지 내리기 → 시군 → 지역·사업 → 목록 내리기(지도 전체) → 앱 밖.
   depth 가 늘 때만 기록을 쌓고(useBrowseHistory), 같은 층끼리 옮기는 건(지역 → 다른 지역) 덮어쓴다. */
export type SheetStop = "low" | "mid" | "full";

/** 위치로 찾은 곳(통합 검색) - 지도 핀과 '○○ 근처'. 고른 지역 · 시군이 region · city 와 같을 때만 그린다 */
export type NearAnchor = { name: string; lat: number; lng: number; sido: string; region: string; city: string | null; note: string | null };

export type BrowseState = {
  region: string | null;
  city: string | null;
  program: string | null;
  filter: BrowseFilter | null;
  sheet: SheetStop;
  search: boolean;
  /** 넓은 화면: 목록 패널이 보이는 정책 상세(slug). 좁은 화면은 쓰지 않는다 - 상세는 따로 연다 */
  detail: string | null;
  /** 위치로 찾은 곳. 층이 아니라 지금 층의 속성이다 */
  near: NearAnchor | null;
};

function readNear(raw: string | null): NearAnchor | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<NearAnchor>;
    if (typeof v.name !== "string" || typeof v.lat !== "number" || typeof v.lng !== "number" || typeof v.region !== "string" || typeof v.sido !== "string") return null;
    return { name: v.name.slice(0, 60), lat: v.lat, lng: v.lng, sido: v.sido, region: v.region, city: typeof v.city === "string" ? v.city : null, note: typeof v.note === "string" ? v.note.slice(0, 120) : null };
  } catch {
    return null;
  }
}

export function readBrowseState(params: URLSearchParams): BrowseState {
  /* region= 은 예전 지역 필터 주소다(필터 목록 화면이 없어진 뒤로 지도 선택과 같다) */
  const region = params.get("place") || params.get("region") || null;
  const sheet = params.get("sheet");
  const type = params.get("type");
  return {
    region,
    city: region ? params.get("city") || null : null,
    program: params.get("prog") || null,
    filter: isBrowseFilter(type) ? type : null,
    /* view=list 는 예전 '지역 목록 화면' 주소다 - 이제 그 자리는 한 페이지 목록이다.
       sheet=1 은 예전 '열린 시트' - 일정 화면 링크가 아직 이 모양으로 온다. */
    sheet: sheet === "low" ? "low" : sheet === "full" || params.get("view") === "list" ? "full" : "mid",
    search: params.get("find") === "1",
    detail: params.get("detail") || null,
    near: readNear(params.get("near")),
  };
}

/** 근처가 지금 화면 것인지 - 다른 지역 · 시군으로 옮기면 저절로 사라진다 */
export const nearOn = (state: BrowseState) =>
  state.near && state.near.region === state.region && state.near.city === state.city ? state.near : null;

export function writeBrowseState(params: URLSearchParams, state: BrowseState): URLSearchParams {
  const next = new URLSearchParams(params);
  const put = (key: string, value: string | null) => (value ? next.set(key, value) : next.delete(key));
  put("place", state.region);
  put("city", state.region ? state.city : null);
  put("prog", state.program);
  put("type", state.filter);
  put("sheet", state.sheet === "mid" ? null : state.sheet);
  put("find", state.search ? "1" : null);
  put("detail", state.detail);
  put("near", state.near ? JSON.stringify(state.near) : null);
  // 예전 필터 목록 화면의 키 - 조건은 이제 주소 밖(policyConditions)에 있다
  for (const legacy of ["view", "region", "category", "period", "amount", "saved"]) next.delete(legacy);
  return next;
}

const levelOf = (state: BrowseState) => (state.city ? 2 : state.region || state.program ? 1 : 0);

/* desk = 넓은 화면. 목록 패널이 늘 옆에 서 있어 시트 자리는 층이 아니다 */
export function browseDepth(state: BrowseState, desk = false): number {
  const level = levelOf(state);
  const top = (state.search ? 1 : 0) + (state.detail ? 1 : 0);
  if (desk) return level + top;
  return level + (state.sheet === "full" ? 1 : 0) + top + (level === 0 && state.sheet !== "low" ? 1 : 0);
}

export const browseDepthOf = (params: URLSearchParams) => browseDepth(readBrowseState(params));
export const deskBrowseDepthOf = (params: URLSearchParams) => browseDepth(readBrowseState(params), true);

/* 한 층 아래. 더 내려갈 데가 없으면 null(앱 밖으로) */
export function lowerBrowseState(state: BrowseState, desk = false): BrowseState | null {
  if (state.detail) return { ...state, detail: null };
  if (state.search) return { ...state, search: false };
  if (desk) {
    if (state.city) return { ...state, city: null };
    if (state.region || state.program) return { ...state, region: null, city: null, program: null };
    return null;
  }
  if (state.sheet === "full") return { ...state, sheet: "mid" };
  if (state.city) return { ...state, city: null };
  if (state.region || state.program) return { ...state, region: null, city: null, program: null, sheet: "mid" };
  if (state.sheet !== "low") return { ...state, sheet: "low" };
  return null;
}
