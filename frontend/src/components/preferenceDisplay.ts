import type { Profile } from "../api";

const regionIcons: Record<string, string> = {
  서울: "🏙️",
  부산: "🌊",
  대구: "🏯",
  인천: "✈️",
  광주: "🎨",
  대전: "🚄",
  울산: "🏭",
  세종: "🌿",
  경기: "🏰",
  강원: "⛰️",
  충북: "🍎",
  충남: "🌾",
  전북: "🥘",
  전남: "🌅",
  경북: "🏞️",
  경남: "🌉",
  제주: "🏝️",
};

const preferenceIcons: Record<string, string> = {
  휴식: "🛌",
  맛집: "🍜",
  체험: "🎒",
  자연: "🌿",
  사진: "📸",
  "1인 30만원 이하": "💳",
  "1인 40만원 이하": "💰",
  "1인 60만원 이하": "🧳",
  상관없음: "✨",
};

export function getRegionIcon(region: string) {
  return regionIcons[region] ?? "📍";
}

export function getPreferenceIcon(value: string) {
  return preferenceIcons[value] ?? "✨";
}

export function formatPreferredRegions(regions: Profile["preferredRegions"]) {
  if (regions && regions.length > 0) return regions.join(" · ");
  return "관심지역 미정";
}

export function formatProfilePreference(value: string | null | undefined, fallback: string) {
  return value?.trim() ? value : fallback;
}
