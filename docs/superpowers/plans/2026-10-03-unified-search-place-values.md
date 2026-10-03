# 통합 검색 PR - 카카오 장소값을 주소에서 빼고 '일정에 담기'를 숨기는 구현 계획(1단계)

> **에이전트 작업자용:** 이 계획은 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 과제별로 실행한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 통합 검색 PR이 카카오 장소의 이름·주소·좌표를 주소(URL)에 싣지 않게 하고, 홈 장소 카드의 '일정에 담기'를 3단계 전까지 숨긴다.

**구조:** 주소에는 카카오 장소 ID와 사용자가 친 말만 둔다. 화면을 쓰는 동안 본 장소는 메모리 모듈(`placeMemory`)에서 꺼낸다. 새로 고침이나 받은 링크처럼 메모리에 없으면 같은 말로 카카오를 다시 검색해 같은 ID를 고르고, 없으면 검색 결과로 돌아간다. '일정에 담기' 버튼과 일정 고르기 창은 지운다. 일정 쪽 `?addPlace` 받기는 3단계에서 새 흐름으로 바꾸므로 그대로 둔다.

**기술:** React · TypeScript · React Router · Vitest + Testing Library

**설계:** `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`(브랜치 `feature/public-place-storage` 커밋 `f0668ff`, 과제 5에서 이 브랜치로 가져온다). 4절 '통합 검색 PR 변경'과 배포 순서 1단계를 구현한다.

## 전체 제약

- 카카오 장소값(이름·주소·좌표·전화)은 주소(URL), DB, 로그, 브라우저 저장소(localStorage·sessionStorage)에 남기지 않는다. 메모리(`placeMemory`)에는 앱을 쓰는 동안 최근 200곳을 30분까지만 두고, 새로 고침과 로그아웃 때 비운다.
- 이 단계는 노출을 줄이는 것이지 저장 문제의 해결이 아니다. 일정 안 장소 검색, 추천 카드, `?addPlace` 받기는 그대로 카카오 값을 저장한다(설계 2~4단계). PR 본문과 CHECKLIST에 그렇게 적는다.
- 주소에는 카카오 장소 ID(`pl`, `from`, `near.id`)와 사용자가 친 말(`q`, `near.q`)만 싣는다. `near.region`·`near.city`·`near.note`는 우리 데이터라 그대로 둔다.
- 카카오 실시간 검색과 화면 표시(장소 목록, 장소 카드, 이 근처, 카카오맵 링크)는 그대로 둔다.
- API 계약은 바꾸지 않는다(프론트 주소 상태만 바뀐다).
- 한글 파일은 UTF-8로 유지한다. 바꾼 diff에 U+FFFD가 없어야 하고 `git diff --check`를 통과해야 한다.
- 커밋은 과제마다 하지 않는다. 과제 5에서 전체 검증 뒤 사용자 승인을 받아 한다. 푸시와 PR은 그 뒤 따로 승인받는다. PR base는 develop이고 머지하지 않는다.
- 버튼 숨김뿐이라 시안은 고치지 않는다. 담는 흐름의 시안은 3단계에서 만든다.

## 검토 초점

1. 받은 링크로 이어 본 장소 카드(`lv=2`)를 메모리 없이 열면, 같은 말로 다시 찾아도 그 장소가 없다. 빈 카드나 끝없는 '찾는 중' 없이 검색 결과로 가야 한다. 과제 4가 시험한다.
2. 예전 형식의 `near`(이름·좌표를 실은 JSON)가 든 주소는 그 근처를 버리고 지역·시군만 보여야 한다. 과제 2가 시험한다.
3. 정책 탭에서 다시 찾기가 실패하거나 결과에서 사라지면 근처 줄과 핀 없이 그 시군 화면이어야 하고, 주소에서도 `near`가 지워져야 한다. 과제 3이 시험한다.
4. 다시 찾는 중에 다른 장소로 옮긴 뒤 앞 검색의 답이 늦게 오면 무시해야 한다. 새 장소가 '찾는 중'에 멈추거나 앞 장소가 보이면 안 된다. 과제 1이 요청별 응답 순서를 뒤집어 시험한다.
5. 홈 장소 카드 어디에도 '일정에 담기'가 없어야 한다. 근처 혜택·카카오맵·이 근처는 그대로 동작하고, 이 근처 안내 문구의 모양도 그대로여야 한다. 새로 고침 때 카카오 검색은 한 번만 나가야 한다. 과제 4가 시험한다.

---

### 과제 1: 본 장소 기억(`placeMemory`)

**파일:**
- 만들기: `frontend/src/components/map/placeMemory.ts`
- 만들기: `frontend/src/components/map/placeMemory.test.ts`
- 고치기: `frontend/src/test/setup.ts`(`forgetSheetMemory();` 다음 줄), `frontend/src/app/session.tsx`(`clearAuth`)

**인터페이스:**
- 내놓는 것:
  - `rememberPlaces(items: readonly PlaceSearchItem[]): void`. 최근 200곳만 남긴다.
  - `recallPlace(id: string | null): PlaceSearchItem | null`. 30분이 지났으면 null이다.
  - `forgetPlaces(): void`
  - `usePlaceById(id: string | null, query: string): { place: PlaceSearchItem | null; missing: boolean }`. 정책 탭이 쓰고, 홈은 자기 검색 결과로 찾는다(과제 4). `missing`이 true면 다시 찾아도 없다는 뜻이다.

- [ ] **1단계: 실패하는 시험 쓰기** - `frontend/src/components/map/placeMemory.test.ts`

```ts
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
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/components/map/placeMemory.test.ts`
기대: FAIL. `./placeMemory`를 찾을 수 없다.

- [ ] **3단계: 구현** - `frontend/src/components/map/placeMemory.ts`

```ts
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

export type PlaceById = { place: PlaceSearchItem | null; missing: boolean };

/** 주소의 카카오 장소 ID → 장소. missing = 다시 찾아도 없다(이어 본 장소를 새로 고친 경우 등) - 부르는 쪽이 돌아간다 */
export function usePlaceById(id: string | null, query: string): PlaceById {
  const known = recallPlace(id);
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
```

`frontend/src/test/setup.ts`도 고친다. 위쪽 import에 `import { forgetPlaces } from "../components/map/placeMemory";`를 더하고, afterEach의 `forgetSheetMemory();` 다음 줄에 `forgetPlaces();`를 넣는다.

`frontend/src/app/session.tsx`도 고친다. import에 `import { forgetPlaces } from "../components/map/placeMemory";`를 더하고, `clearAuth()`의 `setPolicyConditions(NO_CONDITIONS);` 다음 줄에 아래를 넣는다.

```ts
  forgetPlaces();   // 본 카카오 장소 메모리도 그 사람의 것이다
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/components/map/placeMemory.test.ts && npx tsc --noEmit -p .`
기대: 5개 PASS, 타입 오류 없음. 늦은 답을 버리는 줄(`if (control.signal.aborted) return;`)을 빼면 마지막 시험이 FAIL하는지도 한 번 확인한다.

### 과제 2: `near`에는 카카오 장소 ID와 친 말만

**파일:**
- 고치기: `frontend/src/components/map/policyBrowse.ts`(`NearAnchor` 타입, `readNear`)
- 시험: `frontend/src/components/map/policyBrowse.test.ts`(near 시험 두 개)

**인터페이스:**
- 내놓는 것: `NearAnchor = { id: string; q: string; region: string; city: string | null; note: string | null }`. `nearOn`과 `writeBrowseState`는 시그니처가 그대로다.

- [ ] **1단계: 시험을 새 모양으로 바꾸기** - `policyBrowse.test.ts`의 `it("keeps the place found by location only while its region and city stay picked", …)`와 `it("drops a region or near place the map does not know", …)`의 본문을 아래로 바꾼다.

```ts
  it("keeps the place found by location only while its region and city stay picked", () => {
    const near = { id: "kakao:8193468", q: "오동도", region: "전남", city: "여수", note: null };
    const params = writeBrowseState(new URLSearchParams(), state({ region: "전남", city: "여수", near }));
    const read = readBrowseState(params);
    expect(read.near).toEqual(near);
    // 주소에는 카카오 장소 ID와 친 말만 - 이름 · 좌표는 싣지 않는다(카카오 운영정책)
    expect(Object.keys(JSON.parse(params.get("near")!)).sort()).toEqual(["city", "id", "note", "q", "region"]);
    expect(nearOn(read)).toEqual(near);
    expect(nearOn({ ...read, city: "광양" })).toBeNull();
    expect(readBrowseState(new URLSearchParams("near=%7Bbroken")).near).toBeNull();
    expect(readBrowseState(new URLSearchParams(`near=${encodeURIComponent('{"id":1}')}`)).near).toBeNull();
    // 한 칸 내려가면(뒤로 · ‹ · Esc) 주소에서도 지운다
    const lower = lowerBrowseState(read);
    expect(lower).toMatchObject({ region: "전남", city: null });
    expect(writeBrowseState(params, lower as BrowseState).get("near")).toBeNull();
  });

  it("drops a region or near place the map does not know", () => {
    expect(readBrowseState(new URLSearchParams("place=__proto__")).region).toBeNull();
    expect(readBrowseState(new URLSearchParams("region=constructor")).region).toBeNull();
    expect(readBrowseState(new URLSearchParams("place=전국")).region).toBe("전국");
    const near = JSON.stringify({ id: "kakao:8193468", q: "오동도", region: "전남", city: "여수", note: null });
    const read = (raw: string) => readBrowseState(new URLSearchParams(`place=전남&city=여수&near=${encodeURIComponent(raw)}`)).near;
    expect(read(near)).not.toBeNull();
    expect(read(near.replace('"region":"전남"', '"region":"constructor"'))).toBeNull();
    expect(read(near.replace('"id":"kakao:8193468"', '"id":""'))).toBeNull();
    // 예전 주소(이름 · 좌표를 실었던 near)는 버린다
    expect(read(JSON.stringify({ name: "오동도", lat: 34.745, lng: 127.766, sido: "전남", region: "전남", city: "여수", note: null }))).toBeNull();
  });
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/components/map/policyBrowse.test.ts`
기대: 두 시험이 FAIL. 타입이 아직 `name`·`lat`을 요구하고 `id`가 없다.

- [ ] **3단계: 구현** - `policyBrowse.ts`

`NearAnchor`를 아래로 바꾼다.

```ts
/** 위치로 찾은 곳 - 카카오 장소 ID와 사용자가 친 말만(이름 · 좌표는 placeMemory 에서 다시 꺼낸다). region · city · note 는 우리 데이터 */
export type NearAnchor = { id: string; q: string; region: string; city: string | null; note: string | null };
```

`readNear` 본문을 아래로 바꾼다.

```ts
function readNear(raw: string | null): NearAnchor | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<NearAnchor>;
    if (typeof v.id !== "string" || !v.id || v.id.length > 80 || typeof v.q !== "string" || typeof v.region !== "string") return null;
    if (v.region !== NATIONWIDE_REGION && !isRegionName(v.region)) return null;
    return { id: v.id, q: v.q.slice(0, 80), region: v.region, city: typeof v.city === "string" ? v.city : null, note: typeof v.note === "string" ? v.note.slice(0, 120) : null };
  } catch {
    return null;
  }
}
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/components/map/policyBrowse.test.ts`
기대: PASS. `npx tsc --noEmit -p .`는 과제 3·4 전까지 `PolicyPages.tsx`와 `HomeSearch.tsx`에서 `name`·`lat`·`lng`·`sido` 오류가 난다. 과제 3·4에서 없앤다.

### 과제 3: 정책 탭의 근처를 메모리와 다시 찾기로 그리기

**파일:**
- 고치기: `frontend/src/pages/PolicyPages.tsx`(장소 조회 효과, `nearHere`·`pin`, `pickNear`, 시트의 `near` 속성)
- 고치기: `frontend/src/components/map/PolicyMapPanels.tsx`(`NearGroup`, `onPickNear`)
- 시험: `frontend/src/app/__tests__/policies.test.tsx`

**인터페이스:**
- 쓰는 것: 과제 1의 `rememberPlaces`·`usePlaceById`, 과제 2의 `NearAnchor`
- 내놓는 것: `PolicySearchPanel`의 `onPickNear?: (item: PlaceSearchItem, target: NearTarget) => void`. `label` 인자를 없앤다.

- [ ] **1단계: 실패하는 시험 쓰기** - `policies.test.tsx`

`it("finds benefits near a place the user only half remembers and pins it on the map", …)`에서 `expect(new URLSearchParams(routeLocation().search).get("city")).toBe("여수");` 다음 줄에 더한다.

```ts
      // 주소의 near 에는 카카오 장소 ID와 친 말만 - 이름 · 좌표는 싣지 않는다(카카오 운영정책)
      const nearParam = JSON.parse(new URLSearchParams(routeLocation().search).get("near")!);
      expect(Object.keys(nearParam).sort()).toEqual(["city", "id", "note", "q", "region"]);
      expect([nearParam.id, nearParam.q]).toEqual(["kakao:1", "오동도"]);
```

같은 파일 위쪽 import에 `import { forgetPlaces } from "../../components/map/placeMemory";`를 더하고, 그 시험 바로 뒤에 새 시험을 더한다.

```ts
  it("draws a place found by location from its id after a reload, and drops it when it cannot be found again", async () => {
    const policies: Policy[] = [{ ...examplePolicyDetail, id: "ys", slug: "ys", title: "[여수] 숙박 할인", region: "전남" }];
    const policyListSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue(policies);
    const placeSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([
      { kind: "place", id: "kakao:1", name: "오동도", category: "섬", address: "전남광주통합특별시 여수시 수정동 1", latitude: 34.745, longitude: 127.766, sido: "전남", city: "여수" },
    ]);
    const near = JSON.stringify({ id: "kakao:1", q: "오동도", region: "전남", city: "여수", note: null });
    try {
      await login();
      cleanup();
      renderAppRoute(`/policies?place=전남&city=여수&near=${encodeURIComponent(near)}`);
      await waitForSheet("여수 1건");
      expect(await screen.findByText("오동도 근처")).toBeInTheDocument();
      expect(placeSpy).toHaveBeenCalledWith("오동도", expect.anything());
      expect(document.querySelector(".thmap-pin")).toBeTruthy();

      // 다시 찾아도 없으면 근처 줄 · 핀 없이 그 시군만
      cleanup();
      forgetPlaces();
      placeSpy.mockResolvedValue([]);
      renderAppRoute(`/policies?place=전남&city=여수&near=${encodeURIComponent(near)}`);
      await waitForSheet("여수 1건");
      await waitFor(() => expect(placeSpy).toHaveBeenCalledTimes(2));
      expect(screen.queryByText("오동도 근처")).toBeNull();
      expect(document.querySelector(".thmap-pin")).toBeNull();
      // 주소에서도 near 를 지운다 - 그 시군 화면은 그대로
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("near")).toBeNull());
      expect(new URLSearchParams(routeLocation().search).get("city")).toBe("여수");
    } finally {
      policyListSpy.mockRestore();
      placeSpy.mockRestore();
    }
  });
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/app/__tests__/policies.test.tsx -t "half remembers|after a reload"`
기대: FAIL. 앞 시험은 near 키에 `name`·`lat` 등이 있고, 새 시험은 '오동도 근처'를 찾지 못한다.

- [ ] **3단계: 구현** - `PolicyMapPanels.tsx`

`type NearGroup`에서 `label: string;`을 지운다. `nearGroups` 안의 `const label = area ? area.name : named[0].name;`를 지우고, `groups.push({ key, item, label, title, target });`를 `groups.push({ key, item, title, target });`로 바꾼다. 속성 타입은 `onPickNear?: (item: PlaceSearchItem, target: NearTarget) => void;`로, 버튼 onClick은 `onClick={() => onPickNear?.(group.item, group.target)}`로 바꾼다.

- [ ] **4단계: 구현** - `PolicyPages.tsx`

import에 `import { rememberPlaces, usePlaceById } from "../components/map/placeMemory";`를 더한다.

장소 조회 효과의 `appDataApi.searchPlaces(placeQuery, { signal: control.signal }).then(setPlaces, () => {`를 아래로 바꾼다.

```ts
      appDataApi.searchPlaces(placeQuery, { signal: control.signal }).then((items) => {
        rememberPlaces(items);
        setPlaces(items);
      }, () => {
```

`nearHere`와 `pin`을 아래로 바꾼다.

```ts
  /* 위치로 찾은 곳 - 지금 고른 지역 · 시군 것일 때만 핀 · 근처 줄 · 가까운 시군. 이름 · 좌표는 메모리 또는 같은 말로 다시 찾기 */
  const nearHere = nearOn(browse);
  const { place: nearPlace, missing: nearMissing } = usePlaceById(nearHere?.id ?? null, nearHere?.q ?? "");
  const pin = useMemo(
    () => (nearPlace?.sido && nearPlace.latitude != null && nearPlace.longitude != null ? geoToMap(nearPlace.sido, nearPlace.latitude, nearPlace.longitude) : null),
    [nearPlace],
  );
  /* 다시 찾아도 없으면 주소에서도 근처를 지운다(기록을 쌓지 않고 덮어쓴다, 그 시군 화면은 그대로) */
  useEffect(() => {
    if (nearHere && nearMissing) browseHistory.replace(writeBrowseState(searchParams, { ...browse, near: null }).toString());
  }, [nearHere?.id, nearMissing]);
```

`pickNear`를 아래로 바꾼다.

```ts
  /* 위치로 찾은 곳의 근처 혜택으로 - 그 시군(없으면 가장 가까운 시군 · 도 · 전국)을 고르고 지도에 핀. 주소에는 카카오 장소 ID와 친 말만 */
  const pickNear = (item: PlaceSearchItem, target: NearTarget) =>
    setBrowse({
      ...base,
      region: target.region,
      city: target.city,
      filter: dropMove(target.region),
      sheet: "mid",
      search: false,
      near: { id: item.id, q: panelQuery.trim(), region: target.region, city: target.city, note: target.note },
    });
```

시트에 넘기는 `near={nearHere ? {`를 `near={nearHere && nearPlace ? {`로, 그 안의 `label: \`${nearHere.name} 근처\`,`를 `label: \`${nearPlace.name} 근처\`,`로 바꾼다. 칩의 `near: { ...nearHere, region: city.region, city: city.city }`는 그대로 둔다.

- [ ] **5단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/app/__tests__/policies.test.tsx src/components/map && npx tsc --noEmit -p .`
기대: policies·map 시험 PASS. 타입 오류는 `HomeSearch.tsx`만 남는다(과제 4).

### 과제 4: 홈 장소 카드를 ID로 열고 '일정에 담기'를 숨기기

**파일:**
- 고치기: `frontend/src/components/HomeSearch.tsx`
- 고치기: `frontend/src/styles/home.css`(`.home-place-primary`, `.home-trip-pick*` 블록 삭제)
- 시험: `frontend/src/app/__tests__/home.test.tsx`

**인터페이스:**
- 쓰는 것: 과제 1의 `rememberPlaces`·`recallPlace`, 과제 2의 `NearAnchor`
- 내놓는 것: 주소 `pl` = 카카오 장소 ID, `from` = 앞 장소의 카카오 장소 ID

- [ ] **1단계: 실패하는 시험 쓰기** - `home.test.tsx`

위쪽 import의 `import { writePlaceParam } from "../../utils/placeHandoff";`를 `import { forgetPlaces } from "../../components/map/placeMemory";`로 바꾼다.

`it("searches places from the home search bar, opens a place card and hands the place to a trip", …)`의 이름을 `"searches places from the home search bar and opens a place card by its Kakao id, with no trip hand-off yet"`으로 바꾼다. 아래 세 군데를 고친다.

(가) `expect(routeLocation().search).toContain("pl=");`를 아래로 바꾼다.

```ts
      // 주소에는 카카오 장소 ID만 - 이름 · 주소 · 좌표는 싣지 않는다(카카오 운영정책)
      expect(new URLSearchParams(routeLocation().search).get("pl")).toBe("kakao:8193468");
      expect(routeLocation().search).not.toContain(encodeURIComponent("수정동"));
      // 카카오 장소값을 일정에 저장하지 않게 될 때(3단계)까지 '일정에 담기'는 없다
      expect(within(card).queryByRole("button", { name: "일정에 담기" })).toBeNull();
```

(나) 근처 혜택 링크 확인 줄 `expect([near.get("place"), near.get("city"), JSON.parse(near.get("near")!).name]).toEqual(["전남", "여수", "오동도"]);`를 아래로 바꾼다.

```ts
      expect([near.get("place"), near.get("city"), JSON.parse(near.get("near")!).id, JSON.parse(near.get("near")!).q]).toEqual(["전남", "여수", "kakao:8193468", "오동도"]);
```

(다) `// 일정에 담기: …` 주석부터 `expect(within(sheet).getByRole("button", { name: "Day 1에 1개 저장하기" })).toBeInTheDocument();`까지를 지우고 아래로 바꾼다.

```ts
      // 새로 고침(메모리 없음): 같은 말로 다시 찾아 같은 ID의 카드를 그린다
      cleanup();
      forgetPlaces();
      searchPlacesSpy.mockClear();
      renderAppRoute("/home?q=%EC%98%A4%EB%8F%99%EB%8F%84&pl=kakao%3A8193468");
      expect(await screen.findByRole("article", { name: "오동도 장소 카드" })).toBeInTheDocument();
      // 다시 찾기는 결과 목록 검색과 같은 요청 하나다
      expect(searchPlacesSpy).toHaveBeenCalledTimes(1);
```

이 시험의 `listTripsSpy`·`getTripSpy` 선언, `upcoming` 함수, finally의 두 `mockRestore()`도 지운다. 이 시험에서만 쓰였다.

`it("shows nearby places on the place card and follows one to its own card", …)`의 마지막 블록, 곧 `// 이어 본 카드를 주소로 바로 열었으면 …` 주석부터 `expect(await screen.findByRole("button", { name: /오동도.*섬/ })).toBeInTheDocument();`까지를 아래로 바꾼다.

```ts
      // 이어 본 카드를 주소로 바로 열었고(되감을 기록 없음) 메모리에는 있으면 - ‹ 는 검색 결과로
      cleanup();
      renderAppRoute(`/home?${new URLSearchParams({ q: "오동도", pl: "kakao:n2", lv: "2", from: "kakao:8193468" })}`);
      const direct = await screen.findByRole("article", { name: "오동도관광호텔 장소 카드" });
      await user.click(within(direct).getByRole("button", { name: "‹ 오동도" }));
      await waitFor(() => expect(screen.queryByRole("article", { name: "오동도관광호텔 장소 카드" })).toBeNull());
      expect(new URLSearchParams(routeLocation().search).get("q")).toBe("오동도");
      expect(await screen.findByRole("button", { name: /오동도.*섬/ })).toBeInTheDocument();

      // 받은 링크(메모리 없음)로 이어 본 카드를 열면 같은 말로 찾아도 없다 - 빈 카드 없이 검색 결과로
      cleanup();
      forgetPlaces();
      renderAppRoute(`/home?${new URLSearchParams({ q: "오동도", pl: "kakao:n2", lv: "2", from: "kakao:8193468" })}`);
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("pl")).toBeNull());
      expect(screen.queryByRole("article", { name: "오동도관광호텔 장소 카드" })).toBeNull();
      expect(await screen.findByRole("button", { name: /오동도.*섬/ })).toBeInTheDocument();
```

같은 시험의 앞부분, `await user.click(within(nearby).getByRole("button", { name: /오동도관광호텔/ }));` 바로 앞에 더한다. 이 근처 안내 문구는 새 클래스로 옮긴 뒤에도 같은 모양이어야 한다.

```ts
      await user.click(within(nearby).getByRole("button", { name: "볼거리" }));
      expect(await within(nearby).findByText("반경 2km 안에 없어요.")).toHaveClass("home-nearby-tip");
      await user.click(within(nearby).getByRole("button", { name: "숙소" }));
```

`it("folds shop names away for benefit words and lists same-named neighbourhoods across the country", …)`의 동네 줄 확인 `expect([params.get("place"), params.get("city"), JSON.parse(params.get("near")!).name]).toEqual(["전남", "여수", "여수시 중앙동"]);`을 아래로 바꾼다.

```ts
      const nearParam = JSON.parse(params.get("near")!);
      expect([params.get("place"), params.get("city"), nearParam.id, nearParam.q]).toEqual(["전남", "여수", "area:4613010100", "중앙동"]);
      expect(Object.keys(nearParam).sort()).toEqual(["city", "id", "note", "q", "region"]);
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx -t "Kakao id|nearby places|neighbourhoods"`
기대: FAIL. `pl`이 아직 JSON이고 '일정에 담기'가 있으며 near에 `name`이 있다.

- [ ] **3단계: 구현** - `HomeSearch.tsx`

1. import를 정리한다. `import { useAsyncResource } from "../api/useAsyncResource";`, `import { tripStatus } from "../utils";`, `import { readPlaceParam, writePlaceParam } from "../utils/placeHandoff";`를 지우고 `import { recallPlace, rememberPlaces } from "./map/placeMemory";`를 더한다. 지우기 전에 `grep -n "useAsyncResource\|tripStatus" src/components/HomeSearch.tsx`로 `TripPicker` 밖에서 쓰이지 않는지 확인한다.
2. 파일 머리 주석의 둘째·셋째 줄을 바꾼다.

```ts
   주소에는 찾을 말(q)과 연 장소의 카카오 장소 ID(pl)만 둔다 - 장소 값은 placeMemory 에서 꺼내고, 없으면 같은 말로 다시 찾는다(카카오 운영정책).
   층: 검색(q) → 장소 카드(pl) → 이 근처로 이어 본 장소 카드(lv 2, 3 …, 앞 장소의 ID는 from). 치는 동안은 같은 층이라 기록이 쌓이지 않는다. */
```

3. `const { go, back } = useBrowseHistory(homeDepthOf);`를 `const { go, back, replace } = useBrowseHistory(homeDepthOf);`로 바꾼다.
4. `const place = readPlaceParam(searchParams.get("pl"));`를 `const placeId = searchParams.get("pl");`로 바꾼다.
5. `const query = text.trim();` 바로 다음에 더한다. 홈은 결과 목록 검색(같은 말)의 결과로 찾으므로 다시 찾기 요청을 따로 하지 않는다.

```ts
  /* 연 장소 - 이 화면에서 본 것(메모리)이거나, 주소로 바로 열었으면 위 결과 목록 검색(같은 말)에서 같은 ID. 다시 찾기 요청은 따로 하지 않는다 */
  const place = recallPlace(placeId) ?? places?.find((item) => item.id === placeId) ?? null;
  const placeMissing = Boolean(placeId && !place && (query.length < MIN_PLACE_QUERY || places !== null));
  /* 다시 찾아도 없으면(이어 본 장소를 새로 고친 경우 등) 검색 결과로 */
  useEffect(() => {
    if (placeMissing) replace(toResults().toString());
  }, [placeMissing]);
```

6. 장소 조회 효과의 성공 콜백 첫 줄에 `rememberPlaces(items);`를 넣는다.
7. Esc 처리의 `if (place) closePlace();`를 `if (placeId) closePlace();`로 바꾼다. 머리 단추 `aria-label={place ? …}`, `onClick={place ? …}`, `<b>{place ? "장소" : "검색"}</b>`의 `place`도 `placeId`로 바꾼다.
8. 카드 분기를 아래로 바꾼다.

```tsx
          {place ? (
            <HomePlaceCard
              key={place.id}
              item={place}
              query={query}
              policies={all}
              fromName={level > 1 ? recallPlace(searchParams.get("from"))?.name ?? null : null}
              nearCode={nearCode}
              nearbyCache={nearbyCache}
              onNearCode={setNearCode}
              onOpenNearby={(next) => {
                rememberPlaces([next]);
                go(withParams({ pl: next.id, lv: String(level + 1), from: place.id }));
              }}
              onBack={closePlace}
            />
          ) : placeId ? (
            <p className="thmap-sres-empty">장소를 찾는 중…</p>
          ) : !query ? (
```

9. 시작 안내 문구의 `장소 카드에서 그 근처 혜택을 보거나 일정에 담을 수 있어요.`를 `장소 카드에서 그 근처 혜택을 볼 수 있어요.`로 바꾼다.
10. 동네 줄은 `<HomeAreaRow key={item.id} item={item} policies={all} query={query} />`로, 장소 줄 열기는 `onOpen={() => go(withParams({ pl: item.id, lv: null, from: null }))}`로 바꾼다.
11. `nearUrlOf`를 아래로 바꾼다.

```ts
/** 정책 탭의 그 근처 화면(위치로 찾기와 같은 핀 · '근처' 줄 · 가까운 시군). near 에는 카카오 장소 ID와 친 말만 - 이름 · 좌표는 placeMemory 에서 */
function nearUrlOf(item: PlaceSearchItem, target: NearTarget, query: string) {
  return policiesUrl({
    region: target.region,
    city: target.city,
    near: item.sido && item.latitude != null && item.longitude != null
      ? { id: item.id, q: query, region: target.region, city: target.city, note: target.note }
      : null,
  });
}
```

12. `HomeAreaRow`의 속성을 `{ item, policies, query }: { item: PlaceSearchItem; policies: Policy[]; query: string }`로 바꾸고 `to={nearUrlOf(item, target, query)}`로 쓴다.
13. `HomePlaceCard`에 `query` 속성을 더한다(타입 `query: string;`). `const nearUrl = nearUrlOf(item, target, query);`로 쓴다. `const [picking, setPicking] = useState(false);`, '일정에 담기' 버튼, `{picking && <TripPicker item={item} />}`를 지운다.
14. `TripPicker` 함수와 그 위 주석을 통째로 지운다.

이 근처 안내 문구 세 곳(`근처를 찾는 중…`, `근처 장소를 불러오지 못했어요. …`, `반경 2km 안에 없어요.`)의 `className="home-trip-pick-tip"`을 `className="home-nearby-tip"`으로 바꾼다. 이 클래스는 일정 고르기 창 밖에서도 쓰였다.

`home.css`에서는 `.home-trip-pick-tip { margin: 0; font-size: 13px; color: var(--gray-600); }`를 `.home-nearby-tip { margin: 0; font-size: 13px; color: var(--gray-600); }`으로 바꾼다. 그다음 `.home-place-primary { … }` 블록 하나와 `.home-trip-pick`, `.home-trip-pick h4`, `.home-trip-pick-row`(블록), `.home-trip-pick-row b`, `.home-trip-pick-row span`, `.home-trip-pick-new`(블록)를 지운다. 지운 뒤 `grep -rn "home-trip-pick\|home-place-primary" src`의 결과가 없어야 한다.

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx && npx tsc --noEmit -p .`
기대: home 시험 PASS, 타입 오류 없음.

### 과제 5: 문서, 전체 검증, 커밋

**파일:**
- 가져오기: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`(`git cherry-pick f0668ff`)
- 고치기: `docs/implemented-feature-spec.md`, `docs/screen-feature-status-screens.md`, `docs/superpowers/plans/2026-10-03-unified-search.md`, `CHECKLIST.md`
- 만들기: 이 계획 문서

- [x] **0단계: 서버 덤프 조치** - 2026-10-03에 사용자 승인으로 마쳤다(설계 '백업과 보존').
  - #54 개발 원본 덤프 `dev-full-20260830-1824.dump` 두 벌(운영 서버, 개발서버)을 지웠다.
  - 덤프 폴더의 파일을 모두 600으로 맞췄다. 운영 서버 `~/dbmig` 9개, 개발서버 `~/backups`·`~/travelhunter-db-backups` 6개다. 폴더는 모두 700이다.

- [ ] **1단계: 문서 고치기**
  - `docs/implemented-feature-spec.md`의 '장소로 근처 혜택 찾기' 행에서 일정에 담기 문장(`일정에 담기는 일정을 고르면 … (\`?addPlace=\`).`)을 아래로 바꾼다.
    > 홈 '일정에 담기'는 카카오 장소값 저장 문제로 3단계(담는 흐름) 전까지 숨긴다(설계: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). 주소에는 카카오 장소 ID와 검색어만 두고, 장소 값은 화면 메모리에서 꺼내거나 같은 말로 다시 찾는다.
  - 같은 파일의 일정 장소 추가 행에서 `홈 장소 카드에서 넘어온 장소는 바구니에 담긴 채 열린다`를 지운다.
  - `docs/screen-feature-status-screens.md`의 상단 검색창 행에서 `(근처 혜택 · 일정에 담기 · 카카오맵 · 이 근처)`를 `(근처 혜택 · 카카오맵 · 이 근처)`로 바꾼다. `찾을 말과 연 카드는 주소(\`q\` · \`pl\`)에 둬`는 `찾을 말과 연 장소의 카카오 ID는 주소(\`q\` · \`pl\`)에 둬`로 바꾼다.
  - `docs/superpowers/plans/2026-10-03-unified-search.md` 끝에 아래 절을 더한다.
    > ## PR 전 변경(카카오 운영정책)
    > 카카오 장소값을 주소에 싣지 않고 홈 '일정에 담기'를 숨긴다. 근거와 이후 단계는 `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`, 구현은 `docs/superpowers/plans/2026-10-03-unified-search-place-values.md`에 있다.
- [ ] **2단계: 전체 검증**
  - 백엔드: `/c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --deselect tests/test_stay_discount_semantics_snapshot.py`. 백엔드는 바뀌지 않았지만 PR 직전 전체 검증으로 돌린다.
  - 프론트: `npx tsc --noEmit -p .`, `npm run test:mojibake`, `npx vitest run`, `npm run build`
  - 4173 프론트 재빌드: `docker compose --env-file /c/dev/travel-hunter/travel-hunter-onprem/.env -p travel-hunter-onprem -f compose.local.yaml up -d --build --no-deps frontend`
  - `npm run test:e2e:containers`
  - headless 실측(390): 홈 '오동도' → 카드의 주소가 `pl=kakao:…`이고 이름·주소가 없는지, '일정에 담기'가 없는지, 새로 고침하면 같은 카드가 나오는지, 정책 탭 근처 주소에 `name`·`lat`이 없는지, 핀과 '○○ 근처'가 나오는지 본다.
  - `git diff --check`, 바꾼 diff의 U+FFFD 0건
- [ ] **3단계: CHECKLIST**
  - Current Status: 범위에 '일정에 담기 숨김, 주소에 카카오 ID와 검색어만'을 더한다.
  - Recent Validation: 이번 실행 결과로 바꾼다.
  - Active Risks:
    - '일정 고르기 창은 기기 뒤로가기로…' 줄을 지운다.
    - 아래 두 줄을 더한다.
      - 주소로 연 장소 카드는 같은 말로 다시 찾아 그린다. 이어 본 장소(`lv` 2 이상)를 받은 링크로 열면 검색 결과로 돌아간다.
      - 이 PR은 카카오 장소값 노출을 줄인 것이지 저장 문제의 해결이 아니다. 일정 안 장소 검색·추천 카드·`?addPlace` 받기·편집 초안(localStorage)에 남아 있고, 설계 2~4단계에서 고친다.
    - `#54 운영 DB 이전` 절의 '롤백 자산(이전 운영 DB, 덤프 2개)은 안정화 기간 종료 전까지 삭제하지 않는다.'를 아래로 바꾼다.
      > 롤백 자산: 안정화 기간의 끝은 운영을 최신 develop으로 맞추는 배포다. 그 배포를 확인한 뒤 옛 운영 DB(`travelhunter_before_20260830_1824`)와 `prod-before-20260830-1824.dump`를 지운다(승인 후). 개발 원본 덤프 `dev-full-20260830-1824.dump` 두 벌은 카카오 값과 정제 전 개발 데이터가 있어 2026-10-03에 지웠다. 두 서버의 덤프 파일은 600, 폴더는 700이다. 근거: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md` '백업과 보존'.
- [ ] **4단계: 커밋 승인받기** - 사용자에게 아래 세 커밋을 보이고 승인받은 뒤 만든다.
  1. `git cherry-pick f0668ff`: 설계 문서
  2. `fix: 카카오 장소값을 주소에 싣지 않고 홈 '일정에 담기'를 숨긴다`: 과제 1~4, 문서, 이 계획
  3. `docs: CHECKLIST 를 통합 검색 PR 기준으로 갱신한다`
- [ ] **5단계: 푸시와 Draft PR** - 따로 승인받은 뒤 `.codex/local-workflow.md`의 PR 게이트를 따른다. PR 본문 초안의 변경 내용과 검증을 이 변경에 맞춰 고친다. '참고'에 '이 PR은 노출 축소이고 저장 문제는 설계 2~4단계에서 고친다'를 적는다.

## 최종 리뷰 반영(10/4)

새 리뷰어의 최종 리뷰(고친 뒤 머지)에서 과제 1 · 4 설계가 만든 퇴행 두 가지를 고쳤다.
- 그린 장소를 그릴 때마다 메모리에서 다시 꺼내, 30분 · 200곳에서 밀려나면 보던 카드 · '‹ 앞 장소' · 핀이 다음 그리기에서 사라졌다. `useHeldPlace` 로 같은 ID 동안 붙잡는다(`usePlaceById` · 홈 카드 · 앞 장소 이름).
- 홈에서 다시 못 찾으면 `replace` 로 검색 결과를 덮어써 기록이 층을 건너뛰었다(기기 뒤로가기가 닫은 카드를 다시 염). `go(toResults())` 로 쌓인 기록을 되감는다 - 기록이 없으면(받은 링크) 전처럼 덮어쓴다.
- (Minor, 사용자 승인) 구역 ID 는 법정동 번호가 없으면 카카오 주소 글자로 대신해 `near.id` 로 주소창에 실렸다('중앙동' 30곳 중 16곳 - 행정동으로 온 구역). 백엔드가 행정동 번호(`h_code`)로 채우고, 둘 다 없을 때의 글자 ID 는 `writeBrowseState` · `readNear` 가 싣지 않는다.
