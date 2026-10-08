import { describe, expect, it } from "vitest";
import { markerQueryOf, placeCategoryText, previewAddItem, safeKakaoPlaceUrl } from "./placeDisplay";

describe("markerQueryOf", () => {
  it("keeps looking up an old row by its address, then by its name", () => {
    expect(markerQueryOf({ label: "자갈치시장", address: "부산 중구 자갈치해안로 52" })).toBe("부산 중구 자갈치해안로 52");
    expect(markerQueryOf({ label: "자갈치시장", address: null })).toBe("자갈치시장");
  });

  it("does not look up the user's own place or a row waiting for confirmation by its name", () => {
    expect(markerQueryOf({ placeOrigin: "custom", label: "내가 아는 식당", address: null })).toBeNull();
    expect(markerQueryOf({ placeOrigin: "needs_review", label: "장소 이름을 다시 적어 주세요", address: null })).toBeNull();
  });

  it("keeps the query for a public place, which always has coordinates anyway", () => {
    expect(markerQueryOf({ placeOrigin: "public", label: "오동도", address: "전남광주통합특별시 여수시 오동도로 222" })).toBe("전남광주통합특별시 여수시 오동도로 222");
  });
});

describe("placeCategoryText", () => {
  it("names a public place by its category, an own place by what it is, and an old row as before", () => {
    expect(placeCategoryText({ placeOrigin: "public", publicCategory: "sight" })).toBe("관광지");
    expect(placeCategoryText({ placeOrigin: "custom" })).toBe("나만의 장소");
    expect(placeCategoryText({ category: "관광명소", categoryCode: "AT4" })).toBe("관광명소");
    expect(placeCategoryText({ categoryCode: "AT4" })).toBe("AT4");
    expect(placeCategoryText({})).toBe("장소");
  });
});

describe("previewAddItem", () => {
  it("sends only the reference for a public recommendation", () => {
    expect(
      previewAddItem({ time: "10:00", label: "오동도", publicSource: "tourapi", publicSourceId: "126508", sourceProvider: null, externalPlaceId: null }),
    ).toEqual({ time: "10:00", publicPlace: { source: "tourapi", sourceId: "126508" } });
  });

  it("sends only the name, as the user's own place, when a recommendation has no public reference", () => {
    expect(previewAddItem({ time: "", label: "성산일출봉", sourceProvider: "kakao_local", externalPlaceId: "rec-1" })).toEqual({
      time: "",
      customPlace: { name: "성산일출봉" },
    });
  });

  it("keeps a numeric Kakao place id so the Kakao Map link survives", () => {
    expect(previewAddItem({ time: "12:00", label: "해녀의 집", sourceProvider: "kakao", externalPlaceId: "12345" })).toEqual({
      time: "12:00",
      customPlace: { name: "해녀의 집" },
      kakaoPlaceId: "12345",
    });
  });
});

describe("safeKakaoPlaceUrl", () => {
  it("keeps only Kakao place pages and Kakao map search links (코드 검토)", () => {
    expect(safeKakaoPlaceUrl("https://place.map.kakao.com/777")).toBe("https://place.map.kakao.com/777");
    expect(safeKakaoPlaceUrl("http://place.map.kakao.com/777")).toBe("http://place.map.kakao.com/777");
    expect(safeKakaoPlaceUrl("https://map.kakao.com/link/search/%EC%98%A4")).toBe("https://map.kakao.com/link/search/%EC%98%A4");
    expect(safeKakaoPlaceUrl("javascript:alert(1)")).toBeNull();
    expect(safeKakaoPlaceUrl("https://evil.example/place.map.kakao.com/1")).toBeNull();
    expect(safeKakaoPlaceUrl("https://place.map.kakao.com.evil.example/1")).toBeNull();
    expect(safeKakaoPlaceUrl(null)).toBeNull();
    expect(safeKakaoPlaceUrl(undefined)).toBeNull();
  });
});
