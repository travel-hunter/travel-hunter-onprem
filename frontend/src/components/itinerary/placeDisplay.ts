import type { ItineraryPlace, TripPlaceAddItem } from "../../api";
import { PUBLIC_CATEGORY_LABEL } from "./placeAdd/publicPlaceText";

/* 일정 행 표시 규칙(카카오 운영정책 3단계). 우리가 담은 행(공공데이터 · 나만의 장소)은 place_origin 이 있고,
   없는 행이 예전 카카오 행이다 - 예전 행은 지금 그대로 보인다. */

/** 우리가 담은 행 - 공공데이터 장소 또는 나만의 장소 */
export function isOwnPlace(place: Pick<ItineraryPlace, "placeOrigin">): boolean {
  return place.placeOrigin === "public" || place.placeOrigin === "custom";
}

/** 지도가 이름 · 주소로 위치를 다시 찾을 말. 나만의 장소 · 확인 필요 행은 이름이 사용자 글(또는 안내 문구)이라 찾지 않는다 -
    좌표가 있는 행은 지도가 이 말을 보지 않으므로 '좌표 없는 행만 null' 과 같다. 공공데이터 행은 늘 좌표가 있다. 예전 행은 지금 그대로 */
export function markerQueryOf(place: Pick<ItineraryPlace, "placeOrigin" | "address" | "label">): string | null {
  if (place.placeOrigin === "custom" || place.placeOrigin === "needs_review") return null;
  return place.address || place.label;
}

/** 상세 시트 윗줄의 분류 글자 */
export function placeCategoryText(
  place: Pick<ItineraryPlace, "placeOrigin" | "publicCategory" | "category" | "categoryCode">,
): string {
  if (place.placeOrigin === "public" && place.publicCategory) return PUBLIC_CATEGORY_LABEL[place.publicCategory];
  if (place.placeOrigin === "custom") return "나만의 장소";
  return place.category || place.categoryCode || "장소";
}

type PreviewSource = Pick<
  ItineraryPlace,
  "time" | "label" | "publicSource" | "publicSourceId" | "sourceProvider" | "externalPlaceId"
>;

/** 추천 미리보기 한 곳을 일정에 담는 요청(expectedRevision 은 부르는 쪽이 더한다).
    공공데이터 추천은 참조만, 그 밖(저장 요약)은 이름만 나만의 장소로 보낸다 - 추천이 들고 있던 주소 · 좌표 · 분류는 옮기지 않는다.
    숫자인 카카오 장소 ID 는 '카카오맵에서 보기' 링크용으로 남긴다 */
export function previewAddItem(place: PreviewSource): TripPlaceAddItem {
  const time = place.time ?? "";
  const external = place.externalPlaceId ?? "";
  const kakao = place.sourceProvider?.startsWith("kakao") && /^\d{1,20}$/.test(external) ? { kakaoPlaceId: external } : {};
  if (place.publicSource && place.publicSourceId) {
    return { time, publicPlace: { source: place.publicSource, sourceId: place.publicSourceId }, ...kakao };
  }
  return { time, customPlace: { name: place.label }, ...kakao };
}

/* 저장된 장소 링크는 카카오 장소 페이지 · 카카오맵 검색 링크일 때만 그린다(코드 검토).
   예전 행의 place_url 은 3단계 전 클라이언트가 보낸 값이라 javascript: 같은 주소가 남아 있을 수 있다 */
const KAKAO_LINK = /^https?:\/\/(place\.map\.kakao\.com|map\.kakao\.com)\//;

export function safeKakaoPlaceUrl(url: string | null | undefined): string | null {
  return url && KAKAO_LINK.test(url) ? url : null;
}
