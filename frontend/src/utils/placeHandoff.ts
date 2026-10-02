import type { PlaceSearchItem, TripPlaceRequest } from "../api";

/* 홈 장소 카드(?pl=)와 '일정에 담기'(?addPlace=)가 주소로 넘기는 장소 한 곳(시안 v57). 주소는 누구나 고칠 수 있어
   모양을 검사하고 길이를 자른다. 카카오맵 링크는 카카오 장소 주소만 받는다 - 카드가 그대로 링크로 그린다. */
const MAX_PARAM_LENGTH = 2000;
const KAKAO_PLACE_URL = /^https?:\/\/place\.map\.kakao\.com\/\d+$/;

const text = (value: unknown, max: number) => (typeof value === "string" && value.trim() ? value.trim().slice(0, max) : null);
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : null);

export function readPlaceParam(raw: string | null): PlaceSearchItem | null {
  if (!raw || raw.length > MAX_PARAM_LENGTH) return null;
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    const id = text(value.id, 80);
    const name = text(value.name, 120);
    if (value?.kind !== "place" || !id || !name) return null;
    const placeUrl = text(value.placeUrl, 200);
    return {
      kind: "place",
      id,
      name,
      category: text(value.category, 120),
      categoryCode: text(value.categoryCode, 10),
      address: text(value.address, 200),
      latitude: num(value.latitude),
      longitude: num(value.longitude),
      placeUrl: placeUrl && KAKAO_PLACE_URL.test(placeUrl) ? placeUrl : null,
      sido: text(value.sido, 10),
      city: text(value.city, 20),
    };
  } catch {
    return null;
  }
}

export function writePlaceParam(item: PlaceSearchItem): string {
  const { id, name, category, categoryCode, address, latitude, longitude, placeUrl, sido, city } = item;
  return JSON.stringify({ kind: "place", id, name, category, categoryCode, address, latitude, longitude, placeUrl, sido, city });
}

/** 일정 장소로 - 일정 안 장소 검색(GET /trips/{id}/place-search)이 같은 카카오 장소를 담을 때와 같은 값이 되게 */
export function tripPlaceFromSearchItem(item: PlaceSearchItem): TripPlaceRequest {
  return {
    time: "",
    label: item.name,
    meta: [item.category, item.address].filter(Boolean).join(" · ") || "장소 정보 확인",
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.category ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: "kakao",
    externalPlaceId: item.id.startsWith("kakao:") ? item.id.slice("kakao:".length) : item.id,
  };
}
