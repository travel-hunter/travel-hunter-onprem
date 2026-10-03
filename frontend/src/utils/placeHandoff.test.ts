import { describe, expect, it } from "vitest";
import type { PlaceSearchItem } from "../api";
import { readPlaceParam, tripPlaceFromSearchItem, writePlaceParam } from "./placeHandoff";

const odongdo: PlaceSearchItem = {
  kind: "place",
  id: "kakao:8193468",
  name: "오동도",
  category: "여행 > 관광,명소 > 섬 > 섬(내륙)",
  categoryCode: "AT4",
  address: "전남광주통합특별시 여수시 수정동 1-1",
  latitude: 34.744,
  longitude: 127.766,
  placeUrl: "http://place.map.kakao.com/8193468",
  sido: "전남",
  city: "여수",
};

describe("주소로 넘기는 장소", () => {
  it("round-trips a place through the URL", () => {
    expect(readPlaceParam(writePlaceParam(odongdo))).toEqual(odongdo);
  });

  it("drops anything that is not a well-formed place", () => {
    expect(readPlaceParam(null)).toBeNull();
    expect(readPlaceParam("{broken")).toBeNull();
    expect(readPlaceParam(JSON.stringify({ ...odongdo, kind: "area" }))).toBeNull();
    expect(readPlaceParam(JSON.stringify({ ...odongdo, name: 7 }))).toBeNull();
    expect(readPlaceParam("x".repeat(2001))).toBeNull();
    // 링크는 카카오 장소 주소만 - 카드가 그대로 그린다
    expect(readPlaceParam(JSON.stringify({ ...odongdo, placeUrl: "javascript:alert(1)" }))?.placeUrl).toBeNull();
    expect(readPlaceParam(JSON.stringify({ ...odongdo, latitude: "34" }))?.latitude).toBeNull();
    // 지도 도는 아는 이름만 - '__proto__'가 지역 표에서 Object 를 꺼내 카드가 멈췄다(10/3 리뷰)
    expect(readPlaceParam(JSON.stringify({ ...odongdo, sido: "__proto__" }))?.sido).toBeNull();
  });

  it("becomes the same trip place the trip's own place search would add", () => {
    expect(tripPlaceFromSearchItem(odongdo)).toEqual({
      time: "",
      label: "오동도",
      meta: "여행 > 관광,명소 > 섬 > 섬(내륙) · 전남광주통합특별시 여수시 수정동 1-1",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.744,
      longitude: 127.766,
      category: "여행 > 관광,명소 > 섬 > 섬(내륙)",
      categoryCode: "AT4",
      placeUrl: "http://place.map.kakao.com/8193468",
      sourceProvider: "kakao",
      externalPlaceId: "8193468",
    });
  });
});
