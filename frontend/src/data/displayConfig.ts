import type { Policy } from "../api";
import { NATIONWIDE_REGION } from "../utils/policyPrograms";

type PolicyMoodSource = {
  category?: string;
  title?: string;
  tag?: string;
  amount?: string;
};

type PolicyMoodKind = "traffic" | "stay" | "product" | "localDiscount" | "event" | "etc";

function getPolicyMoodKind(policy: PolicyMoodSource): PolicyMoodKind {
  switch (policy.category) {
    case "교통":
      return "traffic";
    case "숙박":
      return "stay";
    case "여행상품":
      return "product";
    case "지역할인":
      return "localDiscount";
    case "이벤트":
      return "event";
    case "기타":
      return "etc";
    default:
      break;
  }

  const text = `${policy.category ?? ""} ${policy.title ?? ""} ${policy.tag ?? ""} ${policy.amount ?? ""}`;
  if (text.includes("교통") || text.includes("KTX") || text.includes("기차") || text.includes("버스") || text.includes("셔틀") || text.includes("항공")) return "traffic";
  if (text.includes("숙박") || text.includes("숙소") || text.includes("호텔")) return "stay";
  if (text.includes("여행상품") || text.includes("패키지") || text.includes("관광상품") || text.includes("투어")) return "product";
  if (text.includes("지역할인") || text.includes("할인") || text.includes("캐시백") || text.includes("상품권") || text.includes("쿠폰")) return "localDiscount";
  if (text.includes("이벤트") || text.includes("행사") || text.includes("프로모션")) return "event";
  return "etc";
}

export function getPolicyMoodIcon(policy: PolicyMoodSource): string {
  switch (getPolicyMoodKind(policy)) {
    case "traffic":
      return "🚌";
    case "stay":
      return "🛏️";
    case "product":
      return "🗺️";
    case "localDiscount":
      return "💸";
    case "event":
      return "🎊";
    case "etc":
      return "📌";
  }
}

export function getPolicyMoodTone(policy: PolicyMoodSource): "blue" | "rose" | "peach" | "mint" | "sky" {
  switch (getPolicyMoodKind(policy)) {
    case "traffic":
      return "blue";
    case "stay":
      return "rose";
    case "product":
    case "event":
      return "peach";
    case "localDiscount":
      return "mint";
    case "etc":
      return "sky";
  }
}


function policyDeadlineTime(policy: Pick<Policy, "deadline">): number {
  const time = new Date(policy.deadline).getTime();
  return Number.isNaN(time) ? Number.MAX_SAFE_INTEGER : time;
}

export function getDeadlinePolicies(
  policies: Policy[] | null | undefined,
  limit: number,
): Policy[] {
  return [...(policies ?? [])]
    .sort((left, right) => policyDeadlineTime(left) - policyDeadlineTime(right))
    .slice(0, limit);
}

function compareDeadlineHomePolicies(left: Policy, right: Policy): number {
  const deadlineDifference = policyDeadlineTime(left) - policyDeadlineTime(right);
  if (deadlineDifference !== 0) return deadlineDifference;
  const matchDifference = right.match - left.match;
  if (matchDifference !== 0) return matchDifference;
  return left.title.localeCompare(right.title, "ko");
}

export type HomeBenefitPick = { title: string; policies: Policy[] };

/* 홈 목록. 근거 없는 "인기"(match 는 백엔드가 전부 90) 대신 실제 데이터로 고른다:
   관심 지역 정책이 있으면 그것만 마감순, 없으면 전체 지역 정책을 마감순. 전국은 홈 카드가 따로 맡는다. */
export function getHomeBenefitPolicies(
  policies: Policy[] | null | undefined,
  limit: number,
  preferredRegions: readonly string[] | null | undefined,
): HomeBenefitPick {
  const regional = (policies ?? []).filter((policy) => policy.region !== NATIONWIDE_REGION);
  const wanted = new Set((preferredRegions ?? []).map((region) => region.trim()).filter(Boolean));
  const mine = wanted.size > 0 ? regional.filter((policy) => wanted.has(policy.region)) : [];
  if (mine.length > 0) {
    return { title: "내 관심 지역 혜택", policies: [...mine].sort(compareDeadlineHomePolicies).slice(0, limit) };
  }
  return { title: "마감 임박 혜택", policies: [...regional].sort(compareDeadlineHomePolicies).slice(0, limit) };
}

export function getNationwideHomePolicies(policies: Policy[] | null | undefined): Policy[] {
  return (policies ?? [])
    .filter((policy) => policy.region === NATIONWIDE_REGION)
    .sort(compareDeadlineHomePolicies);
}

const homePolicyIcons: Record<string, string> = {};

export function getHomePolicyIcon(policy: Policy): string {
  return homePolicyIcons[policy.slug] ?? "💸";
}

export type PolicyVisual = {
  emoji: string;
  from: string;
  to: string;
};

const policyVisuals: Record<string, PolicyVisual> = {
  "nongchon-stay": { emoji: "🗺️", from: "#d9f7f2", to: "#80dccd" },
  "rail-youth": { emoji: "🚌", from: "#dff0ff", to: "#8ac7ff" },
  "hotel-sale": { emoji: "🛏️", from: "#fff1ed", to: "#ffb4a6" },
  default: { emoji: "📌", from: "#fff1bd", to: "#ffcf66" },
};

export function getPolicyVisual(policy: Pick<Policy, "slug"> & PolicyMoodSource): PolicyVisual {
  const visual = policyVisuals[policy.slug];
  if (visual) return visual;
  const tone = getPolicyMoodTone(policy);
  const emoji = getPolicyMoodIcon(policy);
  if (tone === "blue") return { emoji, from: "#eef6ff", to: "#9bd1ff" };
  if (tone === "rose") return { emoji, from: "#fff1ed", to: "#ffb4a6" };
  if (tone === "peach") return { emoji, from: "#fff4e8", to: "#ffc97d" };
  if (tone === "mint") return { emoji, from: "#eefcf6", to: "#99e5c4" };
  return { emoji, from: "#f2f7ff", to: "#b9d4ff" };
}

// 사진은 그라디언트를 대체하지 않고 위에 얹는 레이어다. 지금은 통과 함수지만
// slug별 수동 오버라이드가 생기면 이 자리에서 갈아끼운다.
export function getPolicyPhoto(policy: Pick<Policy, "photo">) {
  return policy.photo ?? null;
}

export const tripCreateRegions = [
  "제주",
  "부산",
  "서울",
  "대구",
  "인천",
  "광주",
  "대전",
  "울산",
  "세종",
  "경기",
  "강원",
  "충북",
  "충남",
  "전북",
  "전남",
  "경북",
  "경남",
] as const;

export type TripCreatePrimaryRegion = {
  label: string;
  value: string;
  description: string;
};

export const tripCreatePrimaryRegions: TripCreatePrimaryRegion[] = [
  { label: "제주", value: "제주", description: "섬, 바다, 자연" },
  { label: "부산", value: "부산", description: "바다, 도시, 맛집" },
  { label: "서울", value: "서울", description: "도시, 전시, 미식" },
  { label: "대구", value: "대구", description: "근대골목, 미식, 야경" },
  { label: "인천", value: "인천", description: "섬, 항구, 강화" },
  { label: "광주", value: "광주", description: "예술, 역사, 무등산" },
  { label: "대전", value: "대전", description: "과학, 온천, 미식" },
  { label: "울산", value: "울산", description: "바다, 강, 일출" },
  { label: "세종", value: "세종", description: "호수, 수목원, 가족" },
  { label: "경기", value: "경기", description: "근교, 자연, 가족" },
  { label: "강원", value: "강원", description: "바다, 산, 드라이브" },
  { label: "충북", value: "충북", description: "호수, 산, 힐링" },
  { label: "충남", value: "충남", description: "서해, 역사, 온천" },
  { label: "전북", value: "전북", description: "한옥, 미식, 역사" },
  { label: "전남", value: "전남", description: "섬, 바다, 정원" },
  { label: "경북", value: "경북", description: "역사, 바다, 전통" },
  { label: "경남", value: "경남", description: "남해, 섬, 드라이브" },
];

export const tripCreatePrimaryRegionValues = tripCreatePrimaryRegions.map((region) => region.value);

export const tripRegionEmoji: Record<string, string> = {
  제주: "🏝️",
  부산: "🌉",
  대구: "🌆",
  광주: "🎨",
  대전: "🔭",
  울산: "🌅",
  세종: "🌳",
  강원: "🏔️",
  경주: "🏛️",
  서울: "🏙️",
  전남: "🌊",
  경남: "🛥️",
  경북: "🏞️",
  전북: "🍲",
  충남: "🌅",
  충북: "🌿",
  경기: "🚲",
  인천: "⛴️",
  강릉: "🌊",
  전국: "✈️",
};

export function getTripRegionEmojiFromTitle(title: string): string {
  const region = tripCreateRegions.find((item) => title.includes(item));
  return region ? tripRegionEmoji[region] : "🧳";
}
