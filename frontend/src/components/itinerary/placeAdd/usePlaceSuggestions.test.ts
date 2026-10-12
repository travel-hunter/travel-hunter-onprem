import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi } from "../../../api";
import { usePlaceSuggestions } from "./usePlaceSuggestions";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("usePlaceSuggestions", () => {
  it("keeps the later request's answer when the earlier request answers last", async () => {
    const early = deferred<string[]>();
    const late = deferred<string[]>();
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockReturnValueOnce(early.promise).mockReturnValueOnce(late.promise);
    const { result } = renderHook(() => usePlaceSuggestions("7"));

    act(() => result.current.request("메타"));
    act(() => result.current.request("메타세쿼"));
    await act(async () => late.resolve(["메타세쿼이아길"]));
    await act(async () => early.resolve(["메타 늦게 온 말"]));

    expect(result.current.suggestions).toEqual(["메타세쿼이아길"]);
    expect(result.current.query).toBe("메타세쿼");
  });

  it("aborts the earlier request when a new one starts", () => {
    const signals: (AbortSignal | undefined)[] = [];
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockImplementation((_tripId, _query, control) => {
      signals.push(control?.signal);
      return new Promise<string[]>(() => {});
    });
    const { result } = renderHook(() => usePlaceSuggestions("7"));

    act(() => result.current.request("메타"));
    expect(signals[0]?.aborted).toBe(false);
    act(() => result.current.request("메타세쿼"));

    expect(signals[0]?.aborted).toBe(true);
    expect(signals[1]?.aborted).toBe(false);
  });

  it("ignores an answer that arrives after clear() and aborts the request in flight", async () => {
    const pending = deferred<string[]>();
    let signal: AbortSignal | undefined;
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockImplementation((_tripId, _query, control) => {
      signal = control?.signal;
      return pending.promise;
    });
    const { result } = renderHook(() => usePlaceSuggestions("7"));

    act(() => result.current.request("메타세쿼"));
    act(() => result.current.clear());
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(["메타세쿼이아길"]));

    expect(result.current.suggestions).toEqual([]);
    expect(result.current.query).toBe("");
  });

  it("empties the list when clear() is called", async () => {
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockResolvedValue(["메타세쿼이아길"]);
    const { result } = renderHook(() => usePlaceSuggestions("7"));
    await act(async () => result.current.request("메타세쿼"));
    expect(result.current.suggestions).toEqual(["메타세쿼이아길"]);

    act(() => result.current.clear());

    expect(result.current.suggestions).toEqual([]);
    expect(result.current.query).toBe("");
  });

  it("falls back to an empty list when the request fails, without throwing", async () => {
    vi.spyOn(appDataApi, "suggestTripPlaceNames")
      .mockResolvedValueOnce(["메타세쿼이아길"])
      .mockRejectedValueOnce(new Error("offline"));
    const { result } = renderHook(() => usePlaceSuggestions("7"));
    await act(async () => result.current.request("메타"));
    expect(result.current.suggestions).toEqual(["메타세쿼이아길"]);

    await act(async () => result.current.request("메타세쿼"));

    expect(result.current.suggestions).toEqual([]);
    expect(result.current.query).toBe("");
  });

  it("does not ask for fewer than two characters and empties the old list instead", async () => {
    const spy = vi.spyOn(appDataApi, "suggestTripPlaceNames").mockResolvedValue(["메타세쿼이아길"]);
    const { result } = renderHook(() => usePlaceSuggestions("7"));
    await act(async () => result.current.request("메타"));
    expect(spy).toHaveBeenCalledTimes(1);

    act(() => result.current.request("메"));
    expect(result.current.suggestions).toEqual([]);
    act(() => result.current.request("  "));
    act(() => result.current.request(" 메 "));

    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("aborts the request in flight when fewer than two characters are left", async () => {
    const pending = deferred<string[]>();
    let signal: AbortSignal | undefined;
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockImplementation((_tripId, _query, control) => {
      signal = control?.signal;
      return pending.promise;
    });
    const { result } = renderHook(() => usePlaceSuggestions("7"));

    act(() => result.current.request("메타"));
    act(() => result.current.request("메"));
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(["메타세쿼이아길"]));

    expect(result.current.suggestions).toEqual([]);
  });

  it("sends the trimmed query and reports it as the query the list belongs to", async () => {
    const spy = vi.spyOn(appDataApi, "suggestTripPlaceNames").mockResolvedValue(["메타세쿼이아길"]);
    const { result } = renderHook(() => usePlaceSuggestions("7"));

    await act(async () => result.current.request(" 메타세쿼 "));

    expect(spy).toHaveBeenCalledExactlyOnceWith("7", "메타세쿼", { signal: expect.any(AbortSignal) });
    expect(result.current.query).toBe("메타세쿼");
    expect(result.current.suggestions).toEqual(["메타세쿼이아길"]);
  });

  it("asks nothing before the trip is known", () => {
    const spy = vi.spyOn(appDataApi, "suggestTripPlaceNames");
    const { result } = renderHook(() => usePlaceSuggestions(undefined));

    act(() => result.current.request("메타세쿼"));

    expect(spy).not.toHaveBeenCalled();
    expect(result.current.suggestions).toEqual([]);
  });

  it("aborts the request in flight on unmount", async () => {
    const pending = deferred<string[]>();
    let signal: AbortSignal | undefined;
    vi.spyOn(appDataApi, "suggestTripPlaceNames").mockImplementation((_tripId, _query, control) => {
      signal = control?.signal;
      return pending.promise;
    });
    const { result, unmount } = renderHook(() => usePlaceSuggestions("7"));
    act(() => result.current.request("메타세쿼"));

    unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(["메타세쿼이아길"]));
  });
});
