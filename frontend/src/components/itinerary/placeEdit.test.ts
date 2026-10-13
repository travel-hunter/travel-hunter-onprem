import { describe, expect, it } from "vitest";
import type { ItineraryPlace } from "../../api";
import { placeEditDraftOf, placeEditFormFor, placeUpdateOf, userMemoOf } from "./placeEdit";

const legacy: ItineraryPlace = {
  id: "9",
  time: "09:00",
  label: "카카오 예전 식당",
  meta: "음식점 · 부산 중구 카카오로 1",
  address: "부산 중구 카카오로 1",
  latitude: 35.1,
  longitude: 129.03,
  category: "음식점 > 한식",
  categoryCode: "FD6",
  placeUrl: "http://place.map.kakao.com/777",
  sourceProvider: "kakao",
  externalPlaceId: "777",
  needsConfirmation: true,
};

const address = "전남광주통합특별시 여수시 오동도로 222";
const publicRow: ItineraryPlace = {
  id: "1",
  time: "09:00",
  label: "오동도",
  meta: address,
  address,
  latitude: 34.7443,
  longitude: 127.7663,
  placeOrigin: "public",
  publicSource: "tourapi",
  publicSourceId: "126508",
  publicCategory: "sight",
};
const withMemo: ItineraryPlace = { ...publicRow, meta: "동백꽃 철에 가기" };

describe("userMemoOf", () => {
  it("is empty when the server only filled meta with the address", () => {
    expect(userMemoOf(publicRow)).toBe("");
    expect(userMemoOf({ ...publicRow, meta: "" })).toBe("");
  });

  it("is the user's memo when meta differs from the address", () => {
    expect(userMemoOf(withMemo)).toBe("동백꽃 철에 가기");
  });

  it("prefers a separate memo field when the server sends one", () => {
    expect(userMemoOf({ ...publicRow, memo: null })).toBe("");
    expect(userMemoOf({ ...publicRow, memo: "따로 받은 메모" })).toBe("따로 받은 메모");
  });
});

describe("placeEditFormFor", () => {
  it("fills the form from the row", () => {
    expect(placeEditFormFor(withMemo, null)).toEqual({ time: "09:00", label: "오동도", meta: "동백꽃 철에 가기" });
  });

  it("takes back only what the draft kept", () => {
    expect(placeEditFormFor(withMemo, { placeId: "1", time: "11:20" })).toEqual({ time: "11:20", label: "오동도", meta: "동백꽃 철에 가기" });
    expect(placeEditFormFor(withMemo, { placeId: "1", time: "09:00", label: "내가 부르는 이름", memo: "" })).toEqual({
      time: "09:00",
      label: "내가 부르는 이름",
      meta: "",
    });
  });

  it("never copies an old Kakao row's name, address or memo into the form", () => {
    const form = placeEditFormFor(legacy, null);
    expect(form).toEqual({ time: "09:00", label: "", meta: "" });
    expect(JSON.stringify(form)).not.toMatch(/카카오|부산 중구|음식점/);
  });
});

describe("placeEditDraftOf", () => {
  it("keeps only the time while the name and memo are untouched", () => {
    expect(placeEditDraftOf(publicRow, { time: "10:00", label: "오동도", meta: "" })).toEqual({ placeId: "1", time: "10:00" });
  });

  it("adds the name and memo only when the user changed them", () => {
    expect(placeEditDraftOf(withMemo, { time: "09:00", label: "내가 부르는 이름", meta: "동백꽃 철에 가기" })).toEqual({
      placeId: "1",
      time: "09:00",
      label: "내가 부르는 이름",
    });
    expect(placeEditDraftOf(withMemo, { time: "09:00", label: "오동도", meta: "" })).toEqual({ placeId: "1", time: "09:00", memo: "" });
  });

  it("never holds an address, coordinates or a category", () => {
    const draft = placeEditDraftOf(publicRow, { time: "10:00", label: "새 이름", meta: "새 메모" });
    expect(Object.keys(draft ?? {}).sort()).toEqual(["label", "memo", "placeId", "time"]);
  });

  it("leaves no draft at all for an old Kakao row", () => {
    expect(placeEditDraftOf(legacy, { time: "10:00", label: "", meta: "" })).toBeNull();
  });
});

describe("placeUpdateOf", () => {
  it("sends only the changed fields", () => {
    expect(placeUpdateOf(withMemo, { time: "10:00", label: "오동도", meta: "동백꽃 철에 가기" }, 3)).toEqual({ expectedRevision: 3, time: "10:00" });
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "새 이름", meta: "동백꽃 철에 가기" }, 3)).toEqual({ expectedRevision: 3, label: "새 이름" });
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "오동도", meta: "새 메모" }, 3)).toEqual({ expectedRevision: 3, memo: "새 메모" });
  });

  it("sends nothing when nothing changed", () => {
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "오동도", meta: "동백꽃 철에 가기" }, 3)).toBeNull();
    expect(placeUpdateOf(publicRow, { time: "09:00", label: " 오동도 ", meta: "" }, 3)).toBeNull();
  });

  it("trims the typed name and memo, and sends an emptied memo as an empty string", () => {
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "  새 이름  ", meta: "" }, 3)).toEqual({ expectedRevision: 3, label: "새 이름", memo: "" });
  });

  it("sends an emptied time as an empty string", () => {
    expect(placeUpdateOf(publicRow, { time: "", label: "오동도", meta: "" }, 3)).toEqual({ expectedRevision: 3, time: "" });
  });

  it("sends only the time for an old Kakao row, never a name or memo", () => {
    expect(placeUpdateOf(legacy, { time: "10:00", label: "", meta: "" }, 4)).toEqual({ expectedRevision: 4, time: "10:00" });
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4)).toBeNull();
  });

  it("replaces an old Kakao row by reference, keeping a changed time", () => {
    const publicPlace = { source: "tourapi" as const, sourceId: "126508" };
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4, { publicPlace })).toEqual({ expectedRevision: 4, publicPlace });
    expect(placeUpdateOf(legacy, { time: "10:00", label: "", meta: "" }, 4, { publicPlace })).toEqual({ expectedRevision: 4, time: "10:00", publicPlace });
  });

  it("replaces an old Kakao row with the user's own place", () => {
    const customPlace = { name: "내가 아는 식당", geoRef: { kind: "building" as const, id: 501, pin: true } };
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4, { customPlace })).toEqual({ expectedRevision: 4, customPlace });
  });

  it("renames a public place by sending the label alone, never swapping it for another place", () => {
    const update = placeUpdateOf(publicRow, { time: "09:00", label: "내가 부르는 이름", meta: "" }, 3);

    // 서버가 공공데이터 이름 · 주소 · 사진 · 위치는 그대로 두고 사용자 이름만 따로 담는다 - 클라이언트는 이름 하나만 보낸다
    expect(update).toEqual({ expectedRevision: 3, label: "내가 부르는 이름" });
    expect(update).not.toHaveProperty("publicPlace");
    expect(update).not.toHaveProperty("customPlace");
  });

  it("starts from the name the row shows, which is the name the user gave once the place was renamed", () => {
    const renamed: ItineraryPlace = { ...publicRow, label: "내가 부르는 이름" };

    expect(placeEditFormFor(renamed, null).label).toBe("내가 부르는 이름");
    // 이름을 안 건드리면 요청도 초안도 이름을 싣지 않는다
    expect(placeUpdateOf(renamed, { time: "10:00", label: "내가 부르는 이름", meta: "" }, 3)).toEqual({ expectedRevision: 3, time: "10:00" });
    expect(placeEditDraftOf(renamed, { time: "10:00", label: "내가 부르는 이름", meta: "" })).toEqual({ placeId: "1", time: "10:00" });
  });
});
