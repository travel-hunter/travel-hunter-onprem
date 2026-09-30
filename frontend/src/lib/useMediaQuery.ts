import { useSyncExternalStore } from "react";

/* 넓은 화면(데스크톱) 배치 기준. CSS 의 @media (min-width: 1024px) 와 같은 값이어야 한다. */
export const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)";

/* matchMedia 가 없는 환경(jsdom 시험)은 좁은 화면으로 본다 - 모바일 배치가 기본이다. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = typeof window.matchMedia === "function" ? window.matchMedia(query) : null;
      if (!list) return () => {};
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => (typeof window.matchMedia === "function" ? window.matchMedia(query).matches : false),
  );
}

export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_MEDIA_QUERY);
}
