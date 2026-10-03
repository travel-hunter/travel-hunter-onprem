import { useEffect, useState } from "react";
import { appDataApi, type PlaceSearchItem } from "../../api";

/* 카카오 장소값은 주소(URL) · DB · 로그에 남기지 않는다(카카오 운영정책 - docs/superpowers/specs/2026-10-03-public-place-storage-design.md).
   주소에는 카카오 장소 ID와 사용자가 친 말만 두고, 본 장소는 여기(메모리)에서 다시 꺼낸다 - 화면을 오가는 동안의 캐시다.
   최근 200곳을 30분까지만 두고(오래된 값을 쓰지 않게), 새로 고침 · 로그아웃이면 비워진다. 없으면 같은 말로 다시 찾는다 */
const MAX_PLACES = 200;
const KEEP_MS = 30 * 60 * 1000;
const places = new Map<string, { item: PlaceSearchItem; at: number }>();

export function rememberPlaces(items: readonly PlaceSearchItem[]) {
  const at = Date.now();
  for (const item of items) {
    places.delete(item.id);
    places.set(item.id, { item, at });
  }
  for (const id of places.keys()) {
    if (places.size <= MAX_PLACES) break;
    places.delete(id);
  }
}

export function recallPlace(id: string | null): PlaceSearchItem | null {
  if (!id) return null;
  const kept = places.get(id);
  if (!kept) return null;
  if (Date.now() - kept.at > KEEP_MS) {
    places.delete(id);
    return null;
  }
  return kept.item;
}

/** 시험 사이 · 로그아웃 때 비운다(src/test/setup.ts, app/session.tsx) */
export function forgetPlaces() {
  places.clear();
}

/** 마지막으로 그린 한 곳을 쥔다 - 메모리(30분 · 200곳)에서 밀려나도 보던 카드 · 핀이 다음 그리기에서 사라지지 않게(10/4 리뷰).
    다른 ID 에는 주지 않고, 같은 ID 로 돌아오면 그대로 쓴다. current = 지금 꺼낼 수 있는 값(메모리 · 결과 목록) */
export function useHeldPlace(id: string | null, current: PlaceSearchItem | null): PlaceSearchItem | null {
  const [held, setHeld] = useState<PlaceSearchItem | null>(null);
  const place = current ?? (held && held.id === id ? held : null);
  if (place && place !== held) setHeld(place);
  return place;
}

export type PlaceById = { place: PlaceSearchItem | null; missing: boolean };

/** 주소의 카카오 장소 ID → 장소. missing = 다시 찾아도 없다(이어 본 장소를 새로 고친 경우 등) - 부르는 쪽이 돌아간다 */
export function usePlaceById(id: string | null, query: string): PlaceById {
  const known = useHeldPlace(id, recallPlace(id));
  const q = query.trim();
  const [found, setFound] = useState<{ id: string; q: string; place: PlaceSearchItem | null } | null>(null);
  useEffect(() => {
    if (!id || known || q.length < 2) return;
    const control = new AbortController();
    appDataApi.searchPlaces(q, { signal: control.signal }).then(
      (items) => {
        if (control.signal.aborted) return;   // 떠난 요청의 늦은 답은 버린다
        rememberPlaces(items);
        setFound({ id, q, place: items.find((item) => item.id === id) ?? null });
      },
      () => {
        if (!control.signal.aborted) setFound({ id, q, place: null });
      },
    );
    return () => control.abort();
  }, [id, q, known]);
  if (!id) return { place: null, missing: false };
  if (known) return { place: known, missing: false };
  if (q.length < 2) return { place: null, missing: true };
  if (found && found.id === id && found.q === q) return { place: found.place, missing: found.place === null };
  return { place: null, missing: false };
}
