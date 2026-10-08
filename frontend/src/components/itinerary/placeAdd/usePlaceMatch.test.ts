import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type PlaceMatchResult, type PublicPlaceItem } from "../../../api";
import type { PlaceBasketItem } from "./placeBasket";
import { kakaoPlaceIdOf, usePlaceMatch, type PlaceMatchState, type PlacePickInput } from "./usePlaceMatch";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  distanceMeters: 12,
};
const yeosuPark: PublicPlaceItem = {
  source: "sangga",
  sourceId: "MA010120220800000002",
  name: "오동도 공원",
  address: "전남 여수시 수정동 1",
  latitude: 34.745,
  longitude: 127.766,
  category: "sight",
  distanceMeters: 95,
};

function kakaoPick(overrides: Partial<PlacePickInput> = {}): PlacePickInput {
  return { id: "kakao:8193468", title: "오동도", latitude: 34.744, longitude: 127.766, categoryCode: "AT4", ...overrides };
}
// kakaoPick() 의 좌표 - 지도를 여는 자리(openAt)가 된다. 보여 주기만 하고 저장하지 않는다
const SPOT = { latitude: 34.744, longitude: 127.766 };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup() {
  const onMatched = vi.fn<(item: PlaceBasketItem) => void>();
  const hook = renderHook(() => usePlaceMatch({ onMatched }));
  return { onMatched, ...hook };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("kakaoPlaceIdOf", () => {
  it("takes only the digits of a kakao:{id} candidate id", () => {
    expect(kakaoPlaceIdOf({ id: "kakao:8193468" })).toBe("8193468");
    expect(kakaoPlaceIdOf({ id: "kakao:abc" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "kakao:12ab" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "kakao:" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "search-a" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: `kakao:${"9".repeat(21)}` })).toBeNull();
    expect(kakaoPlaceIdOf({ id: null })).toBeNull();
    expect(kakaoPlaceIdOf({})).toBeNull();
  });
});

describe("usePlaceMatch", () => {
  it("goes straight to a custom place when the pick has no coordinates", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ latitude: null, longitude: undefined }));
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "noCoords", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: null } });
    expect(matchSpy).not.toHaveBeenCalled();
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("hands one exact match to onMatched as a public basket item", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "match", places: [odongdo] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    // 맞춰 보기에는 이름 · 좌표 · 분류만 간다 - 카카오 장소 ID 는 보내지 않는다
    expect(matchSpy).toHaveBeenCalledWith({ name: "오동도", latitude: 34.744, longitude: 127.766, categoryCode: "AT4" });
    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("asks which place is right when candidates come back, then adds the chosen one", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo, yeosuPark] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({
      status: "choose",
      kakaoPlaceId: "8193468",
      candidates: [odongdo, yeosuPark],
      fallback: { typedName: "", fill: null, openAt: SPOT },
    });
    expect(onMatched).not.toHaveBeenCalled();

    act(() => {
      result.current.chooseCandidate(yeosuPark);
    });

    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: yeosuPark, kakaoPlaceId: "8193468" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("shows at most three candidates", async () => {
    const four = [odongdo, yeosuPark, { ...odongdo, sourceId: "3" }, { ...odongdo, sourceId: "4" }];
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: four });
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toMatchObject({ status: "choose" });
    expect(result.current.state.status === "choose" && result.current.state.candidates).toHaveLength(3);
  });

  it("turns to a custom place with the same Kakao id when the user says none of the candidates is right", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo] });
    const { result, onMatched } = setup();
    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    act(() => {
      result.current.chooseCustom();
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "pin", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: SPOT } });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("goes to a custom place when nothing matches", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "pin", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: SPOT } });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("treats an answer that names a result but carries no place as none", async () => {
    vi.spyOn(appDataApi, "matchPlace")
      .mockResolvedValueOnce({ result: "match", places: [] })
      .mockResolvedValueOnce({ result: "candidates", places: [] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "pin" });

    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "pin" });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("goes to a custom place when the match request fails", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockRejectedValue(new Error("network down"));
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "failed", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: null } });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("keeps no Kakao id when the candidate id is not kakao:digits", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ id: "search-a" }));
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: null, reason: "pin", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: SPOT } });
  });

  it("ignores the answer to an earlier pick when the user picks again", async () => {
    const first = deferred<PlaceMatchResult>();
    const second = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result, onMatched } = setup();
    let firstPick!: Promise<void>;
    let secondPick!: Promise<void>;

    act(() => {
      firstPick = result.current.pick(kakaoPick({ id: "kakao:1", title: "첫째" }));
    });
    act(() => {
      secondPick = result.current.pick(kakaoPick({ id: "kakao:2", title: "둘째" }));
    });
    expect(result.current.state).toEqual({ status: "matching" });

    await act(async () => {
      second.resolve({ result: "match", places: [yeosuPark] });
      await secondPick;
    });
    await act(async () => {
      first.resolve({ result: "candidates", places: [odongdo] });
      await firstPick;
    });

    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: yeosuPark, kakaoPlaceId: "2" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("ignores a failure of an earlier pick too", async () => {
    const first = deferred<PlaceMatchResult>();
    const second = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result } = setup();
    let firstPick!: Promise<void>;
    let secondPick!: Promise<void>;

    act(() => {
      firstPick = result.current.pick(kakaoPick({ id: "kakao:1" }));
    });
    act(() => {
      secondPick = result.current.pick(kakaoPick({ id: "kakao:2" }));
    });
    await act(async () => {
      second.resolve({ result: "none", places: [] });
      await secondPick;
    });
    await act(async () => {
      first.reject(new Error("late failure"));
      await firstPick;
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "2", reason: "pin", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: SPOT } });
  });

  it("drops a pending answer after reset", async () => {
    const pending = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValue(pending.promise);
    const { result, onMatched } = setup();
    let pickDone!: Promise<void>;

    act(() => {
      pickDone = result.current.pick(kakaoPick());
    });
    act(() => {
      result.current.reset();
    });
    await act(async () => {
      pending.resolve({ result: "match", places: [odongdo] });
      await pickDone;
    });

    expect(onMatched).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("opens an empty custom place from the direct entry without any Kakao id", () => {
    const { result } = setup();

    act(() => {
      result.current.startDirect();
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: null } });
  });

  it("gives every custom place form its own pick id, so a name typed for one pick cannot follow the next pick", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo] });
    const { result } = setup();
    const pickIdOf = (state: PlaceMatchState) => {
      if (state.status !== "custom") throw new Error(`expected a custom place form, got ${state.status}`);
      return state.pickId;
    };
    const noCoords = (id: string) => kakaoPick({ id, latitude: null, longitude: null });

    await act(async () => {
      await result.current.pick(noCoords("kakao:1"));
    });
    const first = pickIdOf(result.current.state);
    await act(async () => {
      await result.current.pick(noCoords("kakao:2"));
    });
    const second = pickIdOf(result.current.state);
    // 같은 카카오 장소를 다시 골라도 새 칸이다
    await act(async () => {
      await result.current.pick(noCoords("kakao:2"));
    });
    const third = pickIdOf(result.current.state);
    // 후보에서 '아니요, 직접 적을게요' 와 직접 적기 입구도 새 칸이다
    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    act(() => {
      result.current.chooseCustom();
    });
    const fourth = pickIdOf(result.current.state);
    act(() => {
      result.current.startDirect();
    });
    const fifth = pickIdOf(result.current.state);

    expect(new Set([first, second, third, fourth, fifth]).size).toBe(5);
  });

  it("calls the newest onMatched even when the answer arrives after a re-render", async () => {
    const pending = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValue(pending.promise);
    const stale = vi.fn();
    const latest = vi.fn();
    const { result, rerender } = renderHook(({ onMatched }) => usePlaceMatch({ onMatched }), {
      initialProps: { onMatched: stale },
    });
    let pickDone!: Promise<void>;

    act(() => {
      pickDone = result.current.pick(kakaoPick());
    });
    rerender({ onMatched: latest });
    await act(async () => {
      pending.resolve({ result: "match", places: [odongdo] });
      await pickDone;
    });

    expect(stale).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledTimes(1);
  });
});

describe("usePlaceMatch with a prematch from the search (시안 v62)", () => {
  it("puts a ready row straight into the basket without asking the server again", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { onMatched, result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: { result: "match", places: [odongdo] } }));
    });

    expect(matchSpy).not.toHaveBeenCalled();
    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched.mock.calls[0][0]).toMatchObject({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" });
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("opens the candidates or the own-place form right away", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: { result: "candidates", places: [odongdo, yeosuPark] } }));
    });
    expect(result.current.state).toEqual({ status: "choose", kakaoPlaceId: "8193468", candidates: [odongdo, yeosuPark], fallback: { typedName: "", fill: null, openAt: SPOT } });

    await act(async () => {
      await result.current.pick(kakaoPick({ id: "kakao:42", publicMatch: { result: "none", places: [] } }));
    });
    expect(result.current.state).toMatchObject({ status: "custom", kakaoPlaceId: "42", reason: "pin" });
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("still asks the server when the search carried no prematch", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] } satisfies PlaceMatchResult);
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: null }));
    });

    expect(matchSpy).toHaveBeenCalledTimes(1);
    expect(result.current.state).toMatchObject({ status: "custom", reason: "pin" });
  });
});

describe("usePlaceMatch with an address fill (시안 v64)", () => {
  const FILL = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 };
  const ROW = { id: "kakao:123", title: "카카오 이름(쓰지 않음)", latitude: 35.1602, longitude: 129.1614, categoryCode: "PK6" };

  it("opens an address-filled form named by the typed query when the row has a fill", () => {
    const { result } = setup();
    act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "none", places: [], fill: FILL } }, "해운대 공영주차장"); });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "building", kakaoPlaceId: "123",
      start: { typedName: "해운대 공영주차장", fill: FILL, openAt: { latitude: 35.1602, longitude: 129.1614 } } });
    expect(JSON.stringify(result.current.state)).not.toContain("카카오 이름");
  });

  it("opens the pin picker at the result spot when there is no fill", () => {
    const { result } = setup();
    act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "none", places: [], fill: null } }, "안목해변"); });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "pin", start: { typedName: "안목해변", fill: null, openAt: { latitude: 35.1602, longitude: 129.1614 } } });
  });

  it("falls from 'not this one' among candidates to the same fill", () => {
    const candidate = { source: "tourapi" as const, sourceId: "1", name: "오동도", latitude: 34.74, longitude: 127.76, category: "sight" as const, distanceMeters: 12 };
    const { result } = setup();
    act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "candidates", places: [candidate], fill: FILL } }, "오동도"); });
    act(() => result.current.chooseCustom());
    expect(result.current.state).toMatchObject({ status: "custom", reason: "building", start: { typedName: "오동도", fill: FILL } });
  });

  it("starts the last-resort form with the search box text", () => {
    const { result } = setup();
    act(() => result.current.startDirect("친구네 펜션"));
    expect(result.current.state).toMatchObject({ status: "custom", reason: "direct", kakaoPlaceId: null, start: { typedName: "친구네 펜션", fill: null, openAt: null } });
  });
});
