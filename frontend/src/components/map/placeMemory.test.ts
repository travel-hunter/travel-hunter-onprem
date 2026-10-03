import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type PlaceSearchItem } from "../../api";
import { forgetPlaces, recallPlace, rememberPlaces, usePlaceById } from "./placeMemory";

const odongdo: PlaceSearchItem = {
  kind: "place",
  id: "kakao:8193468",
  name: "오동도",
  category: "여행 > 관광,명소 > 섬",
  categoryCode: "AT4",
  address: "전남광주통합특별시 여수시 수정동 1-1",
  latitude: 34.745,
  longitude: 127.766,
  placeUrl: "http://place.map.kakao.com/8193468",
  sido: "전남",
  city: "여수",
};

afterEach(() => {
  forgetPlaces();
  vi.restoreAllMocks();
});

describe("본 장소 기억 - 주소에는 카카오 장소 ID만", () => {
  it("returns a place seen on this screen without asking Kakao again", () => {
    const spy = vi.spyOn(appDataApi, "searchPlaces");
    rememberPlaces([odongdo]);
    const { result } = renderHook(() => usePlaceById("kakao:8193468", "오동도"));
    expect(result.current).toEqual({ place: odongdo, missing: false });
    expect(spy).not.toHaveBeenCalled();
  });

  it("keeps at most 200 places for 30 minutes", () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    rememberPlaces([odongdo]);
    rememberPlaces(Array.from({ length: 200 }, (_, index) => ({ ...odongdo, id: `kakao:${index}` })));
    expect(recallPlace("kakao:8193468")).toBeNull();   // 가장 오래된 것부터 버린다
    expect(recallPlace("kakao:199")).not.toBeNull();
    now.mockReturnValue(1_000_000 + 30 * 60 * 1000 + 1);
    expect(recallPlace("kakao:199")).toBeNull();   // 30분이 지나면 다시 찾는다(오래된 값을 쓰지 않게)
  });

  it("keeps a place it has drawn while the id stays, after the memory lets it go", async () => {
    const spy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([]);
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    rememberPlaces([odongdo]);
    const { result, rerender } = renderHook(({ id }) => usePlaceById(id, "오동도"), { initialProps: { id: "kakao:8193468" } });
    now.mockReturnValue(1_000_000 + 30 * 60 * 1000 + 1);   // 30분이 지나도
    rerender({ id: "kakao:8193468" });
    expect(result.current).toEqual({ place: odongdo, missing: false });
    forgetPlaces();   // 메모리에서 밀려나도(200곳)
    rerender({ id: "kakao:8193468" });
    expect(result.current).toEqual({ place: odongdo, missing: false });
    expect(spy).not.toHaveBeenCalled();   // 보던 장소를 다시 묻지 않는다 - 핀 · '근처' 줄이 깜박이지 않게
    rerender({ id: "kakao:1" });   // 다른 장소로 옮기면 놓는다
    expect(result.current.place).toBeNull();
    await waitFor(() => expect(result.current.missing).toBe(true));
  });

  it("finds the same id again with the typed words after a reload, and says missing when it is gone", async () => {
    const spy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);
    const { result } = renderHook(() => usePlaceById("kakao:8193468", " 오동도 "));
    expect(result.current).toEqual({ place: null, missing: false });
    await waitFor(() => expect(result.current.place).toEqual(odongdo));
    expect(spy.mock.calls[0][0]).toBe("오동도");
    expect(recallPlace("kakao:8193468")).toEqual(odongdo);

    const gone = renderHook(() => usePlaceById("kakao:1", "오동도"));
    await waitFor(() => expect(gone.result.current).toEqual({ place: null, missing: true }));
  });

  it("is missing at once without words to search, and after a failed search", async () => {
    expect(renderHook(() => usePlaceById("kakao:1", "")).result.current).toEqual({ place: null, missing: true });
    vi.spyOn(appDataApi, "searchPlaces").mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => usePlaceById("kakao:1", "오동도"));
    await waitFor(() => expect(result.current.missing).toBe(true));
  });

  it("ignores a late answer to a search it has already left", async () => {
    const answers: Array<(items: PlaceSearchItem[]) => void> = [];
    vi.spyOn(appDataApi, "searchPlaces").mockImplementation(() => new Promise((done) => { answers.push(done); }));
    const { result, rerender } = renderHook(({ id }) => usePlaceById(id, "오동도"), { initialProps: { id: "kakao:8193468" } });
    rerender({ id: "kakao:2" });
    await waitFor(() => expect(answers).toHaveLength(2));
    answers[1]([odongdo]);   // 지금 요청이 먼저 끝난다 - kakao:2 는 없다
    await waitFor(() => expect(result.current).toEqual({ place: null, missing: true }));
    answers[0]([odongdo]);   // 떠난 요청의 늦은 답은 버린다
    await new Promise((done) => setTimeout(done, 0));
    expect(result.current).toEqual({ place: null, missing: true });
  });
});
