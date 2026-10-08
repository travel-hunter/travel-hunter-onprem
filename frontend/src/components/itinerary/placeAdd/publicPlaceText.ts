import type { PlaceMatchResult, PublicPlaceCategory } from "../../../api";

/* 공공데이터 장소 분류(서버 public_places.category 와 같은 7개)를 사람이 읽는 말로 */
export const PUBLIC_CATEGORY_LABEL: Record<PublicPlaceCategory, string> = {
  sight: "관광지",
  culture: "문화시설",
  leisure: "레포츠",
  stay: "숙박",
  shopping: "쇼핑",
  food: "음식점",
  cafe: "카페",
};

/* 한국관광공사 사진의 출처 표시. 공공누리 Type1 은 출처 표시, Type3 는 출처 표시 + 변경 금지다 */
export function photoCredit(license: string | null | undefined): string {
  return license === "Type3" ? "사진: 한국관광공사 · 변경 금지" : "사진: 한국관광공사";
}

/* 추천 미리보기의 시간대 묶음(오전 · 점심 · 카페 · 숙소)과 같은 네 갈래. 카카오 분류 코드 없이 공공데이터 분류만으로 가른다 */
export type PublicTimeSlotGroup = "attraction" | "food" | "cafe" | "stay";

export function publicTimeSlotGroup(category: PublicPlaceCategory): PublicTimeSlotGroup {
  if (category === "food") return "food";
  if (category === "cafe") return "cafe";
  if (category === "stay") return "stay";
  return "attraction";
}

/* 후보 카드의 거리 문구 - 고른 카카오 장소에서 얼마나 떨어졌는지(서버가 잰 값). 시안 v59 */
export function distanceText(meters: number): string {
  if (meters < 10) return "고른 곳과 같은 자리";
  if (meters < 1000) return `고른 곳에서 약 ${Math.round(meters)}m`;
  return `고른 곳에서 약 ${(meters / 1000).toFixed(1)}km`;
}

/* 검색 결과 줄 · 지도 미리보기에 붙이는 미리 맞춘 갈래(시안 v62). 맞춰 보지 못한 줄(null)은 표시가 없다.
   후보 수는 고른 뒤 보이는 후보 칸과 같게 3곳까지 센다 */
export type PublicMatchBadge = { tone: "ready" | "similar" | "fill" | "custom"; text: string };

export function publicMatchBadge(match: PlaceMatchResult | null | undefined): PublicMatchBadge | null {
  if (!match) return null;
  if (match.result === "match" && match.places.length > 0) return { tone: "ready", text: "바로 담기" };
  if (match.result === "candidates" && match.places.length > 0)
    return { tone: "similar", text: `비슷한 곳 ${Math.min(match.places.length, 3)}` };
  // 시안 v64: 우리 목록에 없으면 그 자리의 건물 · 가까운 땅 지번이 있는지로 가른다
  return match.fill ? { tone: "fill", text: "주소 채움" } : { tone: "custom", text: "위치 찍기" };
}
