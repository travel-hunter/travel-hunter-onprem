import type { Policy } from "../api";

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

export const featuredPolicySlug = "";

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

const HOME_RECOMMENDED_POLICY_MATCH_THRESHOLD = 90;

function compareRecommendedHomePolicies(left: Policy, right: Policy): number {
  const matchDifference = right.match - left.match;
  if (matchDifference !== 0) return matchDifference;
  const deadlineDifference = policyDeadlineTime(left) - policyDeadlineTime(right);
  if (deadlineDifference !== 0) return deadlineDifference;
  return left.title.localeCompare(right.title, "ko");
}

function compareDeadlineHomePolicies(left: Policy, right: Policy): number {
  const deadlineDifference = policyDeadlineTime(left) - policyDeadlineTime(right);
  if (deadlineDifference !== 0) return deadlineDifference;
  const matchDifference = right.match - left.match;
  if (matchDifference !== 0) return matchDifference;
  return left.title.localeCompare(right.title, "ko");
}

export function getHomeBenefitPolicies(
  policies: Policy[] | null | undefined,
  limit: number,
): Policy[] {
  const source = [...(policies ?? [])];
  const recommendedPolicies = source
    .filter((policy) => policy.match >= HOME_RECOMMENDED_POLICY_MATCH_THRESHOLD)
    .sort(compareRecommendedHomePolicies);
  const recommendedPolicyIds = new Set(recommendedPolicies.map((policy) => policy.id));
  const deadlinePolicies = source
    .filter((policy) => !recommendedPolicyIds.has(policy.id))
    .sort(compareDeadlineHomePolicies);

  return [...recommendedPolicies, ...deadlinePolicies].slice(0, limit);
}

const homePolicyIcons: Record<string, string> = {};

export function getFeaturedPolicy(policies: Policy[] | null | undefined): Policy | undefined {
  return policies?.find((policy) => policy.slug === featuredPolicySlug) ?? policies?.[0];
}

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
  emoji: string;
  description: string;
};

export const tripCreatePrimaryRegions: TripCreatePrimaryRegion[] = [
  { label: "제주", value: "제주", emoji: "🏝️", description: "섬, 바다, 자연" },
  { label: "부산", value: "부산", emoji: "🌉", description: "바다, 도시, 맛집" },
  { label: "서울", value: "서울", emoji: "🏙️", description: "도시, 전시, 미식" },
  { label: "대구", value: "대구", emoji: "🌆", description: "근대골목, 미식, 야경" },
  { label: "인천", value: "인천", emoji: "⛴️", description: "섬, 항구, 강화" },
  { label: "광주", value: "광주", emoji: "🎨", description: "예술, 역사, 무등산" },
  { label: "대전", value: "대전", emoji: "🔭", description: "과학, 온천, 미식" },
  { label: "울산", value: "울산", emoji: "🌅", description: "바다, 강, 일출" },
  { label: "세종", value: "세종", emoji: "🌳", description: "호수, 수목원, 가족" },
  { label: "경기", value: "경기", emoji: "🚲", description: "근교, 자연, 가족" },
  { label: "강원", value: "강원", emoji: "🏔️", description: "바다, 산, 드라이브" },
  { label: "충북", value: "충북", emoji: "🌿", description: "호수, 산, 힐링" },
  { label: "충남", value: "충남", emoji: "🌊", description: "서해, 역사, 온천" },
  { label: "전북", value: "전북", emoji: "🍲", description: "한옥, 미식, 역사" },
  { label: "전남", value: "전남", emoji: "🌊", description: "섬, 바다, 정원" },
  { label: "경북", value: "경북", emoji: "🏞️", description: "역사, 바다, 전통" },
  { label: "경남", value: "경남", emoji: "🛥️", description: "남해, 섬, 드라이브" },
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
