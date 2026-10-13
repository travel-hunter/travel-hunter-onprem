import { describe, expect, it } from "vitest";
import type { PublicPlaceCategory } from "../../../api";
import { PUBLIC_CATEGORY_LABEL, distanceText, photoCredit, publicMatchBadge, publicTimeSlotGroup } from "./publicPlaceText";

describe("공공데이터 장소 문구", () => {
  it("names all seven categories", () => {
    expect(PUBLIC_CATEGORY_LABEL).toEqual({
      sight: "관광지",
      culture: "문화시설",
      leisure: "레포츠",
      stay: "숙박",
      shopping: "쇼핑",
      food: "음식점",
      cafe: "카페",
    });
  });

  it("credits the Korea Tourism Organization and adds the no-change notice for Type3 only", () => {
    expect(photoCredit("Type1")).toBe("사진: 한국관광공사");
    expect(photoCredit(null)).toBe("사진: 한국관광공사");
    expect(photoCredit(undefined)).toBe("사진: 한국관광공사");
    expect(photoCredit("Type3")).toBe("사진: 한국관광공사 · 변경 금지");
  });

  it("groups the categories into the four time-slot groups", () => {
    const expected: Record<PublicPlaceCategory, string> = {
      sight: "attraction",
      culture: "attraction",
      leisure: "attraction",
      shopping: "attraction",
      food: "food",
      cafe: "cafe",
      stay: "stay",
    };
    for (const [category, group] of Object.entries(expected)) {
      expect(publicTimeSlotGroup(category as PublicPlaceCategory)).toBe(group);
    }
  });

  it("says how far a candidate is from the picked place", () => {
    expect(distanceText(0)).toBe("고른 곳과 같은 자리");
    expect(distanceText(120.4)).toBe("고른 곳에서 약 120m");
    expect(distanceText(1250)).toBe("고른 곳에서 약 1.3km");
  });
});

describe("publicMatchBadge", () => {
  const place = { source: "tourapi", sourceId: "1", name: "죽녹원", latitude: 35.3, longitude: 126.9, category: "sight", distanceMeters: 3 } as const;

  it("says which path a search row will take (시안 v62)", () => {
    expect(publicMatchBadge({ result: "match", places: [place] })).toEqual({ tone: "ready", text: "바로 담기" });
    expect(publicMatchBadge({ result: "candidates", places: [place, place] })).toEqual({ tone: "similar", text: "비슷한 곳 2" });
    expect(publicMatchBadge({ result: "candidates", places: [place, place, place, place] })).toEqual({ tone: "similar", text: "비슷한 곳 3" });
    expect(publicMatchBadge({ result: "none", places: [] })).toEqual({ tone: "custom", text: "위치 찍기" });
  });

  it("shows nothing for a row the server could not match, and treats an empty answer as none", () => {
    expect(publicMatchBadge(null)).toBeNull();
    expect(publicMatchBadge(undefined)).toBeNull();
    expect(publicMatchBadge({ result: "match", places: [] })).toEqual({ tone: "custom", text: "위치 찍기" });
  });

  it("labels a row without a public match by whether its spot has a jibun", () => {
    const fill = { kind: "parcel" as const, id: 11, pnu: "1213010200100010006", address: "여수시 수정동 1-6", latitude: 34.74, longitude: 127.76, distanceMeters: 2 };
    expect(publicMatchBadge({ result: "none", places: [], fill })).toEqual({ tone: "fill", text: "주소 채움" });
    expect(publicMatchBadge({ result: "none", places: [], fill: null })).toEqual({ tone: "custom", text: "위치 찍기" });
    expect(publicMatchBadge({ result: "none", places: [] })).toEqual({ tone: "custom", text: "위치 찍기" });
  });
});
