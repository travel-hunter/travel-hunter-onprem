import { describe, expect, it } from "vitest";
import type { PlaceSearchItem } from "../api";
import { pickInputFromItem, pickInputFromKakaoId, readAddPlaceParam, writeAddPlaceParam } from "./placeHandoff";

const odongdo: PlaceSearchItem = {
  kind: "place",
  id: "kakao:8193468",
  name: "오동도",
  category: "여행 > 관광,명소 > 섬(내륙)",
  categoryCode: "AT4",
  address: "전남광주통합특별시 여수시 수정동 1-1",
  latitude: 34.744,
  longitude: 127.766,
  placeUrl: "http://place.map.kakao.com/8193468",
  sido: "전남",
  city: "여수",
};

describe("일정으로 넘기는 장소 - 주소에는 카카오 장소 ID 와 친 말만", () => {
  it("writes only the Kakao id and the typed words", () => {
    const params = writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: " 오동도 " });

    expect(params.get("addPlace")).toBe("kakao:8193468");
    expect(params.get("q")).toBe("오동도");
    expect([...params.keys()].sort()).toEqual(["addPlace", "q"]);
  });

  it("leaves other params alone and writes no q when nothing was typed", () => {
    const params = writeAddPlaceParam(new URLSearchParams({ day: "2" }), { kakaoPlaceId: "8193468", query: "  " });

    expect(params.get("day")).toBe("2");
    expect(params.has("q")).toBe(false);
  });

  it("reads what it wrote, from a search string or from URLSearchParams", () => {
    const params = writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" });

    expect(readAddPlaceParam(params)).toEqual({ kakaoPlaceId: "8193468", query: "오동도" });
    expect(readAddPlaceParam(`?${params.toString()}`)).toEqual({ kakaoPlaceId: "8193468", query: "오동도" });
  });

  it("drops anything that is not a numeric Kakao id", () => {
    expect(readAddPlaceParam("")).toBeNull();
    expect(readAddPlaceParam("addPlace=kakao:abc")).toBeNull();
    expect(readAddPlaceParam("addPlace=area:4613010100")).toBeNull();
    expect(readAddPlaceParam(`addPlace=kakao:${"1".repeat(21)}`)).toBeNull();
    // 예전 형식(장소 값을 통째로 실은 JSON)은 받지 않는다
    expect(readAddPlaceParam(new URLSearchParams({ addPlace: JSON.stringify({ kind: "place", id: "kakao:8193468", name: "오동도" }) }))).toBeNull();
  });

  it("treats a missing q as empty and caps the typed words", () => {
    expect(readAddPlaceParam("addPlace=kakao:8193468")).toEqual({ kakaoPlaceId: "8193468", query: "" });
    expect(readAddPlaceParam(new URLSearchParams({ addPlace: "kakao:8193468", q: "가".repeat(300) }))?.query).toHaveLength(100);
  });

  it("hands the picked place to the match step as just the five values it reads, in memory only", () => {
    expect(pickInputFromItem(odongdo)).toEqual({
      id: "kakao:8193468",
      title: "오동도",
      latitude: 34.744,
      longitude: 127.766,
      categoryCode: "AT4",
    });
  });

  it("falls back to an input without coordinates that keeps only the Kakao id", () => {
    expect(pickInputFromKakaoId("8193468")).toEqual({ id: "kakao:8193468", title: "" });
  });
});
