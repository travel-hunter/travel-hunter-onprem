import type { GeoRef, PublicPlaceItem, TripPlaceAddItem } from "../../../api";
import { PUBLIC_CATEGORY_LABEL } from "./publicPlaceText";

/* 장소 추가 창 바구니의 한 칸. 공공데이터 장소(public)이거나 사용자가 직접 쓴 장소(custom)다.
   카카오가 준 이름 · 주소 · 좌표는 여기에 들어오지 않는다. 카카오에서는 장소 ID 숫자만 받아 '카카오맵에서 보기' 링크용으로 둔다 */
export type PlaceBasketItem =
  | { basketId: string; kind: "public"; place: PublicPlaceItem; kakaoPlaceId: string | null }
  | {
      basketId: string;
      kind: "custom";
      name: string;
      /** 주소 채움이면 건물 · 땅 지번 주소(공공데이터) - 보여 주기용. 저장은 geoRef 로 서버가 다시 읽는다 */
      address: string | null;
      geoRef: GeoRef | null;
      /** 미리보기 지도용 - pin 인 지번의 공공데이터 중심뿐(찍은 좌표 · 카카오 좌표는 여기에 오지 않는다) */
      latitude: number | null;
      longitude: number | null;
      kakaoPlaceId: string | null;
    };

let basketSequence = 0;
const nextBasketId = () => `place-basket-${++basketSequence}`;

export function publicBasketItem(place: PublicPlaceItem, kakaoPlaceId: string | null): PlaceBasketItem {
  return { basketId: nextBasketId(), kind: "public", place, kakaoPlaceId };
}

export function customBasketItem(
  input: { name: string; address?: string | null; geoRef?: GeoRef | null; latitude?: number | null; longitude?: number | null },
  kakaoPlaceId: string | null,
): PlaceBasketItem {
  // 점은 pin 인 지번의 중심만 - 둘 다 있거나 둘 다 없다(반쪽이면 버린다)
  const point =
    input.geoRef?.pin && typeof input.latitude === "number" && typeof input.longitude === "number"
      ? { latitude: input.latitude, longitude: input.longitude }
      : { latitude: null, longitude: null };
  return { basketId: nextBasketId(), kind: "custom", name: input.name.trim(), address: input.address ?? null, geoRef: input.geoRef ?? null, ...point, kakaoPlaceId };
}

/* 저장 요청 한 건. 공공데이터 장소는 참조(source · sourceId)만 보낸다 - 이름 · 주소 · 좌표 · 사진은 서버가 자기 표에서 채운다 */
export function basketItemPayload(item: PlaceBasketItem): TripPlaceAddItem {
  const kakao = item.kakaoPlaceId ? { kakaoPlaceId: item.kakaoPlaceId } : {};
  if (item.kind === "public") {
    return { publicPlace: { source: item.place.source, sourceId: item.place.sourceId }, ...kakao };
  }
  return { customPlace: { name: item.name, ...(item.geoRef ? { geoRef: item.geoRef } : {}) }, ...kakao };
}

export function basketItemTitle(item: PlaceBasketItem): string {
  return item.kind === "public" ? item.place.name : item.name;
}

/* 바구니 줄의 분류 이름. 시안 v59 */
export function basketItemBadge(item: PlaceBasketItem): string {
  return item.kind === "public" ? PUBLIC_CATEGORY_LABEL[item.place.category] : "직접 적은 장소";
}

/* 바구니 줄의 보조 글 - 공공데이터 주소, 또는 주소 채움으로 얻은 지번 주소. 시안 v59 */
export function basketItemDetail(item: PlaceBasketItem): string {
  if (item.kind === "public") return item.place.address ?? "주소 정보 없음";
  return item.address ?? "위치 없이 이름만";
}
