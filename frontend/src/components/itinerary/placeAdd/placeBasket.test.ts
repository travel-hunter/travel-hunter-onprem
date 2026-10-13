import { describe, expect, it } from "vitest";
import type { PublicPlaceItem } from "../../../api";
import {
  basketItemBadge,
  basketItemDetail,
  basketItemPayload,
  basketItemTitle,
  customBasketItem,
  publicBasketItem,
} from "./placeBasket";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  sido: "전남",
  city: "여수",
  photoUrl: "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
  photoLicense: "Type3",
  distanceMeters: 12,
};

describe("장소 바구니", () => {
  it("sends a public place as a reference plus the Kakao place id, nothing else", () => {
    const item = publicBasketItem(odongdo, "8193468");

    expect(item).toMatchObject({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" });
    expect(basketItemPayload(item)).toEqual({
      publicPlace: { source: "tourapi", sourceId: "126508" },
      kakaoPlaceId: "8193468",
    });
    // 공공데이터 값(이름 · 주소 · 좌표 · 사진)도 보내지 않는다 - 서버가 자기 표에서 채운다
    expect(JSON.stringify(basketItemPayload(item))).not.toContain("오동도");
    expect(JSON.stringify(basketItemPayload(item))).not.toContain("34.74");
  });

  it("fills publicPlace and customPlace with exactly the fields the server defines, because it rejects unknown ones inside them", () => {
    const publicPayload = basketItemPayload(publicBasketItem(odongdo, "8193468"));
    const customPayload = basketItemPayload(
      customBasketItem({ name: "숙소 앞 편의점", geoRef: { kind: "building", id: 501, pin: true } }, "123456"),
    );

    expect(Object.keys(publicPayload).sort()).toEqual(["kakaoPlaceId", "publicPlace"]);
    expect(Object.keys(publicPayload.publicPlace ?? {}).sort()).toEqual(["source", "sourceId"]);
    expect(Object.keys(customPayload).sort()).toEqual(["customPlace", "kakaoPlaceId"]);
    expect(Object.keys(customPayload.customPlace ?? {}).sort()).toEqual(["geoRef", "name"]);
  });

  it("leaves the Kakao place id out when there is none", () => {
    expect(basketItemPayload(publicBasketItem(odongdo, null))).toEqual({
      publicPlace: { source: "tourapi", sourceId: "126508" },
    });
    expect(basketItemPayload(customBasketItem({ name: "할머니 댁" }, null))).toEqual({
      customPlace: { name: "할머니 댁" },
    });
  });

  it("trims the name and keeps the public center of a pinned jibun for the preview map", () => {
    const item = customBasketItem(
      { name: "  숙소 앞 편의점  ", address: "부산광역시 해운대구 중동 1391-66", geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 },
      "123456",
    );

    expect(item).toMatchObject({ kind: "custom", name: "숙소 앞 편의점", latitude: 35.160131, longitude: 129.161383, kakaoPlaceId: "123456" });
  });

  it("drops half a point so the pair is always both or neither", () => {
    const item = customBasketItem({ name: "반쪽 위치", latitude: 35.1, longitude: null }, null);

    expect(item).toMatchObject({ latitude: null, longitude: null });
    expect(basketItemPayload(item)).toEqual({ customPlace: { name: "반쪽 위치" } });
  });

  it("keeps a point only for a pinned jibun, so a Kakao or picked coordinate never reaches the basket", () => {
    // 카카오 정책 방어선 - pin 이 아니거나 geoRef 가 없으면 좌표가 와도 버린다(geoRef?.pin 조건을 지우면 실패한다)
    const unpinned = customBasketItem(
      { name: "넓은 땅", address: "강릉시 견소동 1", geoRef: { kind: "parcel", id: 77, pin: false }, latitude: 37.77, longitude: 128.95 },
      null,
    );
    const noRef = customBasketItem({ name: "좌표만", latitude: 37.77, longitude: 128.95 }, null);

    expect(unpinned).toMatchObject({ latitude: null, longitude: null });
    expect(noRef).toMatchObject({ latitude: null, longitude: null });
  });

  it("gives every item its own basket id", () => {
    const first = publicBasketItem(odongdo, null);
    const second = publicBasketItem(odongdo, null);

    expect(first.basketId).not.toBe(second.basketId);
  });

  it("titles each row with public data or the typed name and describes it without Kakao values", () => {
    const publicItem = publicBasketItem(odongdo, "8193468");
    const pinned = customBasketItem({ name: "내 쉼터", address: "부산광역시 해운대구 중동 1391-66", geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 }, null);
    const nameOnly = customBasketItem({ name: "내 쉼터" }, null);

    expect(basketItemTitle(publicItem)).toBe("오동도");
    expect(basketItemBadge(publicItem)).toBe("관광지");
    expect(basketItemDetail(publicItem)).toBe("전남 여수시 오동도로 222");
    expect(basketItemDetail(publicBasketItem({ ...odongdo, address: null }, null))).toBe("주소 정보 없음");

    expect(basketItemTitle(pinned)).toBe("내 쉼터");
    expect(basketItemBadge(pinned)).toBe("직접 적은 장소");
    expect(basketItemDetail(pinned)).toBe("부산광역시 해운대구 중동 1391-66");
    expect(basketItemDetail(nameOnly)).toBe("위치 없이 이름만");
  });

  it("sends only the name and the geo reference of an address-filled custom place", () => {
    const item = customBasketItem(
      { name: "오동도", address: "전남광주통합특별시 여수시 수정동 1-6", geoRef: { kind: "parcel", id: 4401, pin: true }, latitude: 34.744764, longitude: 127.767783 },
      "777",
    );
    expect(basketItemPayload(item)).toEqual({ customPlace: { name: "오동도", geoRef: { kind: "parcel", id: 4401, pin: true } }, kakaoPlaceId: "777" });
    expect(basketItemDetail(item)).toBe("전남광주통합특별시 여수시 수정동 1-6");
  });

  it("keeps a wide parcel's address without a point and a plain custom place as a name only", () => {
    const wide = customBasketItem({ name: "넓은 공원", address: "강릉시 견소동 1", geoRef: { kind: "parcel", id: 77, pin: false } }, null);
    expect(basketItemPayload(wide)).toEqual({ customPlace: { name: "넓은 공원", geoRef: { kind: "parcel", id: 77, pin: false } } });
    expect(wide).toMatchObject({ latitude: null, longitude: null });
    expect(basketItemDetail(wide)).toBe("강릉시 견소동 1");
    const plain = customBasketItem({ name: "친구네 펜션" }, null);
    expect(basketItemPayload(plain)).toEqual({ customPlace: { name: "친구네 펜션" } });
    expect(basketItemDetail(plain)).toBe("위치 없이 이름만");
  });
});
