import type { PlaceSearchItem } from "../api";
import { kakaoPlaceIdOf, type PlacePickInput } from "../components/itinerary/placeAdd/usePlaceMatch";

/* 홈 장소 카드의 '일정에 담기'가 일정 화면으로 넘기는 것(카카오 운영정책 3단계, 설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md 4절).
   주소에는 카카오 장소 ID(addPlace=kakao:{id})와 사용자가 친 말(q)만 싣는다 - 이름 · 주소 · 좌표는 싣지 않는다.
   받는 쪽이 화면 메모리(없으면 같은 말 재검색, components/map/placeMemory.ts)에서 장소를 꺼내 맞춰 보기를 시작한다. */
const MAX_QUERY_LENGTH = 100;

export type AddPlaceHandoff = { kakaoPlaceId: string; query: string };

export function readAddPlaceParam(search: string | URLSearchParams): AddPlaceHandoff | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const kakaoPlaceId = kakaoPlaceIdOf({ id: params.get("addPlace") });
  if (!kakaoPlaceId) return null;
  return { kakaoPlaceId, query: (params.get("q") ?? "").trim().slice(0, MAX_QUERY_LENGTH) };
}

/** 주어진 params 에 addPlace · q 만 쓰고 그대로 돌려준다(다른 키는 건드리지 않는다) */
export function writeAddPlaceParam(params: URLSearchParams, { kakaoPlaceId, query }: AddPlaceHandoff): URLSearchParams {
  params.set("addPlace", `kakao:${kakaoPlaceId}`);
  const typed = query.trim().slice(0, MAX_QUERY_LENGTH);
  if (typed) params.set("q", typed);
  else params.delete("q");
  return params;
}

/** 메모리에서 꺼낸 카카오 장소를 맞춰 보기 입구(openAddPlace · usePlaceMatch.pick)가 읽는 다섯 값으로. 화면 메모리 안에서만 쓰고 저장하지 않는다 */
export function pickInputFromItem(item: PlaceSearchItem): PlacePickInput {
  return { id: item.id, title: item.name, latitude: item.latitude, longitude: item.longitude, categoryCode: item.categoryCode };
}

/** 장소를 다시 못 찾았을 때(새로 고침 · 오래된 링크) - 좌표 없는 입력으로 보내면 pick 이 바로 나만의 장소 칸으로 간다. 카카오 ID 는 남아 링크가 산다 */
export function pickInputFromKakaoId(kakaoPlaceId: string): PlacePickInput {
  return { id: `kakao:${kakaoPlaceId}`, title: "" };
}
