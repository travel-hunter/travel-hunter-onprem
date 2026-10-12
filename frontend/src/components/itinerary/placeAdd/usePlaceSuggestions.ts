import { useCallback, useEffect, useRef, useState } from "react";
import { appDataApi } from "../../../api";

/* 장소 검색 칸의 완성 검색어. query 는 이 목록을 받은 (앞뒤 공백을 자른) 질의 - 화면이 칸의 글과 맞을 때만 목록을 보인다.
   요청마다 번호를 올리고 앞 요청을 끊어, 늦게 온 앞 질의의 답이 뒤 목록을 덮지 않는다. 실패는 목록만 비운다(오류 문구 없음) */
const MIN_QUERY_LENGTH = 2;
const EMPTY = { query: "", suggestions: [] as string[] };

export function usePlaceSuggestions(tripId: string | undefined) {
  const [state, setState] = useState(EMPTY);
  const turnRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    turnRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  const clear = useCallback(() => {
    stop();
    setState((current) => (current === EMPTY ? current : EMPTY));
  }, [stop]);

  const request = useCallback(
    (raw: string) => {
      const query = raw.trim();
      if (!tripId || query.length < MIN_QUERY_LENGTH) {
        clear();
        return;
      }
      stop();
      const turn = turnRef.current;
      const controller = new AbortController();
      controllerRef.current = controller;
      appDataApi.suggestTripPlaceNames(tripId, query, { signal: controller.signal }).then(
        (suggestions) => {
          if (turnRef.current === turn) setState({ query, suggestions });
        },
        () => {
          if (turnRef.current === turn) setState(EMPTY);
        },
      );
    },
    [tripId, stop, clear],
  );

  useEffect(() => stop, [stop]);

  return { suggestions: state.suggestions, query: state.query, request, clear };
}
