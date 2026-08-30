# 일정 상세 — 다른 날짜로 장소 카드 옮기기 3종 개선

작성일: 2026-08-25
브랜치: `feature/itinerary-drag-preview-unified`

## 배경

장소 카드를 Day1에서 Day2로 끌어 옮기는 동작에서 세 가지 문제가 보고됐다.

1. 드래그 도중 화면이 상하로 흔들린다.
2. 날짜를 옮긴 뒤 그 날짜 안에서 삽입 위치를 잡을 때 카드들이 서로 밀려나지 않는다. 같은 날짜 안에서의 이동은 정상적으로 밀린다.
3. Day 탭 쪽으로 포인터를 옮겨도 마우스를 따라다니는 작은 장소 카드가 안 나올 때가 있다. Day 칸 / 타임라인 / 위쪽 장소추가 버튼 칸 사이에 판정이 닿지 않는 틈이 있다.

같은 브랜치에 먼저 올라가 있던 Day 탭 판정 개선(탭 경계 12px 여유, 자동 전환 250ms→10ms)과 3번이 같은 코드를 건드리므로 하나로 합쳐 진행했다.

순수 프론트엔드 변경이다. API 계약 / 백엔드 / DB 변경 없음.

## 원인

| # | 원인 |
|---|---|
| 1a | `.timeline-insertion-slot.over`가 `height: 0 → 44px`로 자라며 아래 카드를 밀어낸다. 슬롯은 `opacity: 0`이라 원인이 보이지 않는다 |
| 1b | 날짜가 전환되면 타임라인이 통째로 교체돼 문서 높이가 변한다. `restorePlaceDragScrollPosition`이 `scroll` 이벤트마다 되돌리려 해 브라우저와 싸운다. CSS 잠금은 `overscroll-behavior: none`뿐이라 실제로 스크롤을 막지 못했다 |
| 1c | `restrictPlaceDragToContent`가 드래그 시작 시점에 캐시한 `contentHeight`를 쓴다. 날짜가 바뀌면 실제 높이와 어긋나 오버레이 클램프가 튄다 |
| 2 | `timelineSortableIds`에 **보이는 날짜의 카드 id만** 들어갔다. 다른 날짜에서 온 활성 카드는 `SortableContext` 멤버가 아니므로 `verticalListSortingStrategy`가 아무 변형도 계산하지 않는다. 대신 쓰이던 것은 `translateY(72px)` 고정값과 `position: absolute`로 기존 카드 **위에 덧그리는** 미리보기라 자리가 생기지 않았다 |
| 3 | `.day-tabs` 행(실측 38px)과 타임라인 사이에 `.itinerary-drag-boundary` 16px 죽은 구간이 있고, 그 위 `.trip-primary-actions` 영역도 판정 대상이 아니었다 |

> **구현 중 정정 — 1a는 cross-day 흔들림의 원인이 아니었다.**
> `.timeline-insertion-slot.cross-day.over { height: 0 }` 규칙이 이미 존재해 다른 날짜 드래그에서는 슬롯이 자라지 않고 있었다. 44px 성장은 **같은 날짜** 드래그에만 걸렸고, 그때는 dnd-kit의 밀어내기와 겹쳐 간격이 두 배가 되는 별개 문제였다.
> 따라서 보고된 cross-day 흔들림은 **1b·1c가 전부 책임진다.** 1a 수정은 같은 날짜 쪽 개선으로 함께 넣었다.

## 변경 내용

### A. 카드 밀림 — SortableContext 편입

이미 작성돼 있었으나 컴포넌트에서 호출이 0건이던 `buildTimelineSortableIds`, `buildTimelineRenderItems`를 연결했다. 새로 만들지 않았다.

- `crossDayGhostPosition`이 있으면 활성 카드의 sortable id를 보이는 날짜의 `SortableContext` items에 삽입 위치대로 끼워 넣는다.
- 렌더 루프를 `timelineRenderItems` 기준으로 바꾸고, `type: "ghost"` 자리에 신규 `TimelineGhostCard`를 렌더한다. 이 컴포넌트는 `useSortable({ id: activeSortableId })`로 등록되어 dnd-kit이 **주변 카드를 같은 날짜와 동일하게 밀어낸다.**
- 실제 카드 순번(`placeNumber`)과 `DroppableTimelinePosition`의 `position`은 유령을 제외하고 센다.
- 죽은 수동 오프셋을 제거했다: `crossDayPreviewLayout`, `CrossDayPreviewCard`, `SortablePlaceItem`의 `crossDayPreviewBefore` / `crossDayPreviewOffset` prop, `--timeline-cross-day-preview-height` 및 관련 CSS.
- `.timeline-insertion-slot.over`의 44px 성장을 제거했다. 자리는 이제 dnd-kit이 만든다.

**계획에 없던 결함 — 유령 위 드롭이 무시됨**

유령은 활성 카드의 id로 등록돼 있어, 그 위에 드롭하면 `resolveTimelineDropTarget`의 자기 자신 방어(`if (overSortableId === activeSortableId) return null`)에 걸려 **드롭이 통째로 무시된다.** 가장 자연스러운 동작이 아무 일도 안 하는 셈이라 정적 검토에서 발견해 고쳤다.

`resolveGhostDropOverId`를 추가해 `overId`가 활성 id와 같으면 이미 계산해 둔 삽입 위치(`day-position:D:P`)로 치환한다. `handlePlaceDragOver`와 `handlePlaceDragEnd` 양쪽에 적용했다. `resolveTimelineDropTarget`은 순수 함수로 그대로 뒀다.

### B. 화면 고정

- 잠금 클래스에 `overflow: hidden`을 추가해 드래그 중 스크롤을 실제로 막는다. 스크롤바는 이미 폭 0(`::-webkit-scrollbar { display: none }`)이라 잠금으로 인한 밀림이 없다.
- `window.addEventListener("scroll", restorePlaceDragScrollPosition)`를 제거했다. 스크롤이 실제로 잠기면 불필요하고, 남으면 브라우저와 싸워 진동을 만든다. 날짜 전환 후 `requestAnimationFrame`에서 한 번 호출하는 것은 유지했다.
- `restrictPlaceDragToContent`가 호출 시점의 `appContainer.scrollHeight`를 읽도록 바꾸고 `placeDragContentBoundsRef`에서 `contentHeight` 필드를 없앴다.

### C. Day 투명 판정 박스

마크업과 CSS를 추가하지 않았다. 기존 랜드마크의 사각형에서 박스를 계산한다 — 선이 보이지 않는 박스가 그대로 된다.

- 신규 `resolveDayZoneRect({ actionsRect, dayTabsRect, timelineRect })` — 장소추가 버튼 줄 아래부터 타임라인 위까지. 랜드마크가 없으면 탭 행으로 폴백한다.
- `.trip-primary-actions`에 `data-itinerary-actions` 속성을 추가해 조회를 안정화했다.
- `isPointerOverDayRow`가 탭 행 대신 존을 본다. 죽은 16px 구간이 사라진다.
- `resolvePointerDayTarget`이 선택적 `dayZoneRect`를 받는다. 존 안이면 **거리 상한 없이 가장 가까운 탭**, 존을 못 재면 기존 `DAY_TAB_POINTER_TOLERANCE_PX`로 폴백.
- `shouldScheduleDaySwitch`도 같은 판정을 쓴다. 두 게이트가 어긋나면 "불은 켜지는데 안 열리는" 죽은 구간이 생긴다.
- 타임라인 안쪽 포인터는 기존대로 날짜를 전환하지 않는다.

## 수정 파일

```
frontend/src/pages/itinerary/ItineraryDetailPage.tsx
frontend/src/styles/app.css
frontend/src/app/__tests__/trip-detail.test.tsx
```

## 검증

```
npx vitest run src/app/__tests__/trip-detail.test.tsx src/utils.test.ts   → 82 passed
npm run build (typecheck 포함)                                            → 성공
```

기준선 76 − `crossDayPreviewLayout` 1 + Day 존 5 + 유령 드롭 2 = 82.

**브라우저 확인은 미수행이다.** Chrome 창이 백그라운드라 `requestAnimationFrame`이 완전히 멈춰(2.5초에 0틱) dnd-kit 드래그가 시작조차 하지 못했다. 창을 포그라운드로 두어야 검증할 수 있다.

## 남은 항목

- **B-4 (조건부, 미적용)** — 스크롤을 잠가도 날짜별 카드 수 차이로 문서가 짧아지면 브라우저가 `scrollTop`을 강제로 줄인다. 이건 잠금으로 못 막는다. B 적용 후에도 흔들림이 남으면 드래그 중 타임라인 높이를 인라인 `min-height`로 고정한다. 타임라인에 이미 `min-height: clamp(360px, calc(100dvh - 480px), 520px)`가 있어 어느 정도는 완충된다. **실측 후 판단.**
- **C-3 (미결)** — 자동 전환 지연 10ms. Day 존이 생겨 전환이 더 쉽게 걸리므로, Day1→Day5 가로 쓸기에서 중간 날짜가 연달아 열릴 가능성이 커졌다. 실측하고 조정이 필요하면 값과 이유를 함께 보고한다.

## 시도했다가 실패한 접근 (재시도 금지)

- absolute preview / offset 오버레이 — 자리를 차지하지 못해 카드가 밀리지 않는다
- `restrictPlaceDragToContent`에 y축 modifier 추가 — 오버레이가 포인터를 따라오지 못한다

---

# 후속 — 브라우저 실측에서 나온 3건 (2026-08-25)

사용자 실기기 테스트에서 위 구현 이후 세 가지가 새로 드러났다. **셋 다 위 변경이 만든 것**이며, 특히 ③은 승인받은 "드래그 중 완전 고정" 결정의 직접적 결과다.

## 증상과 원인

### ① 첫 순서에 겹치면 유령이 깜박이고 화면이 상하로 진동한다

`DndContext`에 `measuring` 설정이 없어 dnd-kit이 기본값 `MeasuringStrategy.WhileDragging`을 쓴다. **드래그 시작 시점에 droppable 좌표를 한 번만 재고 그 뒤로 갱신하지 않는다.**

유령이 DOM에 끼어들면 아래 카드들이 실제로 82px 남짓 내려간다. 그런데 dnd-kit은 옛 좌표로 충돌을 계산하므로 "유령 삽입 → 카드 이동 → 옛 좌표 기준 재판정 → 유령 제거 → 카드 복귀"가 반복된다. 첫 순서에서 특히 심한 이유는, 유령이 index 0에 들어가면 리스트 전체가 밀려 어긋난 좌표의 수가 최대가 되기 때문이다.

왼쪽 번호 배지가 같이 흔들리는 것은 유령이 `.timeline-item` 개수를 바꿔 `:last-child` 연결선 규칙과 마커 열이 함께 재배치되기 때문이다. 여기에 더해 `TimelineGhostCard`가 빈 `<span />`을 렌더해 **번호 없는 28px 빨간 원**이 하나 더 그려지고 있었다(`.timeline-marker span`이 배경·크기를 갖는다).

### ② 빈 날짜로 옮기면 이동도 안 되고 미리보기도 안 뜬다

빈 날짜에는 **포인터가 맞출 수 있는 드롭 영역이 하나도 없다.** 유일한 후보인 `DroppableTimelinePosition`은 `height: 0`이라 `pointerWithin`이 절대 잡지 못한다.

그 결과 `event.over`가 null → `verifiedOverId` null → `resolveTimelineDropTarget`이 null → `setCrossDayDragPreview(null)`로 **유령이 렌더되지 않는다.** 드롭 시에도 `overId`가 null이라 `if (!trip || !canEditTrip || movingPlaceId || !overId) return;`에서 빠져나가 **이동이 일어나지 않는다.** 원인 하나가 두 증상을 모두 만든다.

같은 이유로 **마지막 카드 아래 빈 공간**에 놓아도 먹지 않는다. 빈 날짜만의 문제가 아니다.

### ③ 드래그 중 화면이 아래로 안 내려간다

`.app-container`에 건 `overflow: hidden` 때문이다.

- dnd-kit의 내장 autoScroll은 스크롤 가능한 조상을 찾아 동작하는데 `overflow: hidden`이면 후보에서 제외된다.
- 휠 브리지도 `shouldForwardWindowWheelToAppScroll`이 잠금 클래스를 보면 스스로 false를 돌려주게 돼 있다.

즉 잠금이 **의도치 않은 스크롤**뿐 아니라 **의도한 스크롤**까지 막았다. 진동의 직접 원인은 사실 B-2(되돌리기 리스너)와 B-3(높이 캐시)였고, `overflow: hidden`은 과잉이었다.

## 결정 사항 (승인 완료)

| 항목 | 결정 |
|---|---|
| ③ 스크롤 | `overflow: hidden` 제거, dnd-kit 내장 autoScroll 활용 |
| ① 진동 | 측정 전략을 `MeasuringStrategy.Always`로 |
| ② 빈 날짜 | 타임라인 전체를 덮는 드롭 영역 |
| 유령 배지 | 배지 없이 연결선만 |

## 작업 순서

TDD로 진행한다. 새 순수 함수는 실패 테스트를 먼저 쓰고 빨간 것을 확인한 뒤 구현한다.

### D. 스크롤 되돌리기 (③)

**D-1. `overflow: hidden` 제거**

`app.css`의 잠금 클래스에서 `overflow: hidden`만 뺀다. `overscroll-behavior: none`(스크롤 체이닝·당겨서 새로고침 방지)과 `scroll-behavior: auto`(smooth 스크롤이 autoScroll과 싸우는 것 방지)는 여전히 제 몫을 하므로 남긴다.

**D-2. 휠 브리지 되살리기**

`shouldForwardWindowWheelToAppScroll`에서 잠금 클래스 조기 반환을 제거한다. 카드를 잡은 채 휠을 굴리면 스크롤돼야 한다. 이 함수는 단위 테스트가 있으므로 테스트를 먼저 뒤집는다. `classList`가 더 이상 필요 없으면 시그니처에서 뺀다.

**D-3. 위치 되돌리기 로직 완전 제거**

스크롤이 의도적으로 허용되는 이상, 드래그 시작 시점 위치로 되돌리는 동작은 **사용자를 낚아채는 버그**가 된다. 자동 스크롤로 아래까지 내려간 상태에서 날짜가 전환되면 원위치로 튕겨 올라간다.

- `restorePlaceDragScrollPosition` 및 날짜 전환 후 `requestAnimationFrame` 호출부 제거
- `unlockPlaceDragViewportScroll`의 `window.scrollTo(...)` 및 `appContainer.scrollLeft/Top` 복원 제거
- `placeDragScrollLockRef`에서 좌표 필드 제거 → `lock`/`unlock`은 **클래스 토글만** 남는다

**D-4. autoScroll 확인**

`DndContext`의 `autoScroll` 기본값은 `true`다. D-1 후 그대로 동작하는지 먼저 실측한다. 반응이 둔하면 그때 `autoScroll={{ threshold, acceleration }}`을 조정하고 값과 근거를 보고한다. **먼저 튜닝하지 않는다.**

`restrictPlaceDragToContent`가 `transform.y`의 하단을 클램프하므로 자동 스크롤 중 오버레이가 포인터를 놓치지 않는지 함께 확인한다. 이전에 y축 modifier로 같은 문제를 겪은 전례가 있다.

### E. 유령 진동 (①)

**E-1. 측정 전략**

```
import { MeasuringStrategy } from "@dnd-kit/core";

<DndContext measuring={{ droppable: { strategy: MeasuringStrategy.Always } }} ... >
```

dnd-kit 다중 컨테이너 예제가 쓰는 공식 해법이다. 유령 삽입으로 레이아웃이 바뀌어도 매 프레임 좌표를 다시 재므로 되먹임이 끊긴다.

한 날짜의 카드 수는 많아야 십수 개라 매 프레임 측정 비용은 문제되지 않을 것으로 본다. 35일 여행처럼 긴 일정에서도 **보이는 날짜만** 렌더되므로 측정 대상은 그 날짜의 카드로 한정된다. 그래도 체감 지연이 있으면 보고한다.

**E-2. 유령 배지 제거**

`TimelineGhostCard`의 `<div className="timeline-marker"><span /></div>`에서 `<span />`을 뺀다. `.timeline-marker span`이 28px 빨간 원을 그리므로 빈 span도 원이 된다. 마커 div는 남겨 세로 연결선(`::after`)이 이어지게 한다.

실제 카드의 번호는 유령을 제외하고 세므로(이미 구현됨) 1, 2, 3 연속이 유지된다.

### F. 빈 날짜·마지막 카드 아래 드롭 (②)

**F-1. 타임라인 전체 드롭 영역**

`.timeline` 요소 자체를 `useDroppable({ id: dayAreaDropId(visibleDay) })`로 등록한다. 새 id 형식 `day-area:<D>`와 `parseDayAreaDropId`를 추가한다. 기존 `data-itinerary-timeline` ref와 합성한다.

**F-2. 구체적인 대상 우선**

`pointerWithin`은 겹치는 droppable을 모두 돌려주므로, 카드 위에 있을 때 큰 타임라인 영역이 카드를 이길 수 있다. 기존 `placeDragCollisionDetection`을 확장한다.

```
preferSpecificDropTargets(collisions)
  → day-area:* 항목은 다른 충돌이 하나라도 있으면 버린다
```

순수 함수로 두고 단위 테스트한다.

**F-3. 영역 id를 삽입 위치로 변환**

```
resolveDayAreaOverId({ overId, closestPosition })
  → "day-area:2"  이면 "day-position:2:<closestPosition>"
  → 그 외는 그대로 통과
```

`closestPosition`은 이미 있는 `getClosestCurrentDayTimelinePosition()` → `resolveClosestTimelinePosition`으로 구한다. 빈 날짜면 `itemRects`가 비어 1을 돌려주므로 그대로 맞는다. `resolveTimelineDropTarget`은 손대지 않는다.

`handlePlaceDragOver`와 `handlePlaceDragEnd` 양쪽에 적용한다. 한쪽만 적용하면 미리보기는 뜨는데 드롭이 안 먹는 식으로 갈린다.

**F-4. 유령을 위치 계산에서 제외**

`getClosestCurrentDayTimelinePosition`이 `[data-itinerary-timeline] [data-sortable-id]`를 훑는데, 유령도 `data-sortable-id`를 갖는다. `:not([data-timeline-ghost])`로 제외한다. 빼지 않으면 유령이 자기 위치 계산에 끼어들어 다시 되먹임이 생긴다.

## 수정 대상

앞선 작업과 같은 3개 파일이다.

```
frontend/src/pages/itinerary/ItineraryDetailPage.tsx
frontend/src/styles/app.css
frontend/src/app/__tests__/trip-detail.test.tsx
```

## 검증

**단위 테스트** — 현재 기준선 82 passed.

- `shouldForwardWindowWheelToAppScroll` — 잠금 중에도 휠을 통과시킨다 (기존 테스트를 뒤집는다)
- `preferSpecificDropTargets` — 카드와 영역이 함께 잡히면 카드를 남기고, 영역만 잡히면 영역을 남긴다
- `resolveDayAreaOverId` — 영역 id를 삽입 위치로 바꾸고 그 외는 통과시킨다
- `parseDayAreaDropId` — 형식과 경계값
- CSS 핀 — 잠금 클래스에 `overflow: hidden`이 **없어야** 한다 (기존 단언을 뒤집는다)

**브라우저** — `http://127.0.0.1:4174/trips/1`. 하드 리로드 후.

1. **첫 순서 겹치기** — 유령이 한 자리에 고정되고 번호 배지가 흔들리지 않는가. 빨간 원이 카드 수만큼만 있는가
2. **빈 날짜** — 미리보기가 뜨고, 드롭하면 실제로 옮겨지고, 새로고침 후에도 유지되는가
3. **마지막 카드 아래 빈 공간** — 같은 확인
4. **긴 날짜에서 아래로** — 카드를 화면 아래쪽으로 내리면 자동으로 스크롤되는가. 카드를 잡은 채 휠이 먹는가
5. **자동 스크롤 후 날짜 전환** — 원래 위치로 튕겨 올라가지 않는가 (D-3 확인)
6. **회귀** — 앞선 작업의 확인 항목(Day 존 연속 이동, 유령 위 드롭, 같은 날짜 이동)이 그대로인가

## 열린 위험

- **E-1의 비용** — 매 프레임 droppable 측정. 카드가 많은 날짜에서 체감 지연이 생기면 `Always` 대신 유령 위치가 바뀔 때만 강제 재측정하는 쪽으로 좁혀야 한다.
- **D-1 후 진동 재발** — `overflow: hidden`을 빼고도 흔들림이 없어야 B-2·B-3만으로 충분하다는 판단이 선다. 재발하면 원인을 다시 잡는다. 앞선 계획의 B-4(드래그 중 타임라인 인라인 `min-height`)가 그때의 후보다.
- **F-2의 우선순위** — `preferSpecificDropTargets`가 너무 공격적이면 영역 드롭이 영영 선택되지 않고, 너무 느슨하면 카드 위에서도 영역이 이긴다. 브라우저에서 양쪽 경계를 확인한다.

## 후속 구현 결과 (as-built)

D → E → F 순서로 TDD 구현 완료. 계획과 달라진 점 없음.

| 항목 | 구현 |
|---|---|
| D-1 | 잠금 클래스에서 `overflow: hidden` 제거. `overscroll-behavior: none`·`scroll-behavior: auto`는 유지 |
| D-2 | `shouldForwardWindowWheelToAppScroll`의 잠금 클래스 조기 반환 제거. 카드를 잡은 채 휠이 먹는다 |
| D-3 | `restorePlaceDragScrollPosition` 및 `unlockPlaceDragViewportScroll`의 좌표 복원 전부 제거. `placeDragScrollLockRef`는 `useRef(false)` 플래그가 되고 lock/unlock은 클래스 토글만 남았다 |
| D-4 | `autoScroll` 기본값 그대로. 튜닝하지 않음 — 실측 후 판단 |
| E-1 | `measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}` |
| E-2 | `TimelineGhostCard`의 마커에서 `<span />` 제거. 연결선만 남는다 |
| F-1 | `.timeline`에 `useDroppable({ id: dayAreaDropId(visibleDay) })` |
| F-2 | `preferSpecificDropTargets` — `placeDragCollisionDetection`의 `pointerWithin`·`closestCenter` 양쪽 결과에 적용 |
| F-3 | `resolveDayAreaOverId` — `handlePlaceDragOver`·`handlePlaceDragEnd` 양쪽에서 `resolveGhostDropOverId`보다 **먼저** 푼다 |
| F-4 | `getClosestCurrentDayTimelinePosition`의 선택자에 `:not([data-timeline-ghost])` |

**검증**

```
npx vitest run src/app/__tests__/trip-detail.test.tsx src/utils.test.ts   → 86 passed
npm run build (typecheck 포함)                                            → 성공
```

82 + `parseDayAreaDropId`/`preferSpecificDropTargets`×2/`resolveDayAreaOverId` 4개 = 86. 뒤집은 단언(휠 통과, `overflow: hidden` 부재, `restorePlaceDragScrollPosition` 부재, `MeasuringStrategy.Always` 존재, 유령 빈 span 부재)은 모두 먼저 빨간 것을 확인했다.

**브라우저 확인은 다시 미수행이다.** 창을 포그라운드로 두어도 이 탭이 창에서 선택된 탭이 아니면 `requestAnimationFrame`이 멈춘다(`visibilityState: hidden`). 한 번은 `resize_window`로 포커스가 잡혀 rAF가 살아났으나 재현되지 않았다. 자동 검증 하네스에는 별도 결함도 있었다 — dnd-kit은 `document`에서 `mousemove`를 듣는데 `window`로 디스패치하면 전파되지 않아 드래그가 활성화되지 않는다(반대 방향은 전파된다).

---

# 후속 2 — 왼쪽 번호 열 고정 (2026-08-25)

D·E·F 적용 후 재테스트에서 나머지는 해결됐으나 **왼쪽 번호 열이 여전히 움직인다.**

## 원인

`.timeline-item`이 **행마다 독립된 그리드**다.

```css
.prototype-trip-detail-screen .timeline-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
```

배지(`.timeline-marker`)가 카드와 한 행에 묶여 있으므로, 유령이 DOM에 끼어들어 행 순서가 바뀌면 **배지도 함께 물리적으로 이동한다.** dnd-kit의 변형은 `<article>`에만 걸려 있어 배지가 안 움직일 것 같지만, 움직이는 주체는 변형이 아니라 **우리가 직접 바꾸는 DOM 순서**다.

여기에 E-2에서 유령 배지를 없앤 탓에 유령 자리에 **빈 칸**이 생기고, 그 빈 칸이 유령을 따라 위아래로 옮겨 다닌다.

## 결정 사항 (승인 완료)

| 항목 | 결정 |
|---|---|
| 정렬 | 타임라인을 **하나의 그리드**로 만들어 배지와 카드를 형제로 배치. 배지는 행 순서에 고정되고 행 높이는 카드가 결정하므로 정렬이 유지된다 |
| 번호 개수 | **화면에 렌더된 슬롯 수.** N = 그 날짜의 카드 수 + (다른 날짜에서 들고 온 카드가 이 날짜를 가리킬 때 1) |

빈 날짜에 들고 가면 슬롯이 1개이므로 **1번 빨간공이 생성된 채로 고정**된다. 같은 날짜 안 재정렬은 그 카드가 이미 이 날짜 소속이라 N이 그대로다. 다른 날짜를 보고 있을 때는 그 날짜의 실제 카드 수만 센다.

## 작업 순서

### G. 번호 열을 카드 목록에서 분리

**G-1. 타임라인을 단일 그리드로**

```css
.prototype-trip-detail-screen .timeline {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  column-gap: 12px;
}
```

`row-gap`은 **쓰지 않는다.** 높이 0인 `.timeline-insertion-slot`이 행마다 끼어 있어 `row-gap`을 주면 카드 사이마다 12px이 덧붙는다. 지금처럼 카드 셀의 `margin-bottom: 12px`로 간격을 만들고, 세로 연결선(`.timeline-marker::after`의 `bottom: -12px`)이 그 간격을 잇게 둔다.

**G-2. 배지를 부모가 렌더**

`SortablePlaceItem` 안의 `<div className="timeline-marker">`를 밖으로 뺀다. 렌더 루프가 슬롯마다 배지와 카드 셀을 **형제로** 내보낸다.

```
{timelineRenderItems.map((item, slotIndex) => (
  <Fragment key=...>
    <TimelineSlotMarker number={slotIndex + 1} isLast={slotIndex === last} />
    {item.type === "ghost" ? <TimelineGhostCard .../> : <SortablePlaceItem .../>}
  </Fragment>
))}
```

- 번호는 **슬롯 순번**이다. 유령도 한 칸을 차지하므로 자동으로 "들고 있는 카드 포함"이 된다.
- `SortablePlaceItem`에서 `placeNumber` prop을 제거한다(현재 배지 출력에만 쓰인다).
- `SortablePlaceItem`과 `TimelineGhostCard`의 루트가 `.timeline-item`(2열 그리드)에서 **카드 셀 하나**로 바뀐다. sortable ref와 `data-sortable-id`도 그 셀로 옮겨간다.

**G-3. 삽입 슬롯은 두 열을 가로지르게**

`.timeline-insertion-slot`에 `grid-column: 1 / -1`을 준다. 그렇지 않으면 배지 열의 한 칸을 차지해 배지·카드 짝이 어긋난다.

**G-4. 연결선 마지막 행 처리**

지금은 `.timeline-item:last-child .timeline-marker::after { display: none }`로 마지막 연결선을 숨긴다. 배지가 더 이상 `.timeline-item` 안에 없으므로 이 선택자는 무효가 된다. `:last-of-type`은 태그 기준이라 삽입 슬롯 `div`에도 걸려 위험하다. **`isLast` prop으로 `.timeline-marker.last` 클래스를 붙여** 명시적으로 처리한다.

**G-5. dragging 상태 선택자 보정**

`.timeline-item.dragging .timeline-marker { visibility: visible }`은 배지가 밖으로 나가면서 의미를 잃는다. 제거한다. `.timeline-item.dragging .timeline-sortable-card { opacity: 0 }`은 카드 셀에 그대로 남으므로 선택자만 새 구조에 맞춘다.

## 손대지 않는 것

`DroppableTimelinePosition`(높이 0 삽입 슬롯)은 이제 `pointerWithin`이 절대 못 잡고, F-1의 `day-area` 영역이 `closestCenter` 폴백까지 가로채므로 **사실상 죽은 요소**다. 다만 이번 수정의 목적이 아니고 제거하면 CSS 핀 테스트까지 번지므로 **이번에는 남긴다.** `grid-column: 1 / -1`만 준다. 별건으로 정리할 후보로 기록해 둔다.

## 검증

**단위 테스트** — 현재 기준선 86 passed.

- CSS 핀 — `.timeline`이 `grid-template-columns: 28px`을 갖는다 / `row-gap`이 없다 / `.timeline-insertion-slot`이 `grid-column: 1 / -1`을 갖는다 / `.timeline-item.dragging .timeline-marker` 규칙이 **없다**
- 소스 핀 — `SortablePlaceItem`에 `placeNumber` prop이 **없다**

번호 계산 자체는 `timelineRenderItems`의 인덱스라 이미 `buildTimelineRenderItems` 테스트가 덮는다. 새 순수 함수는 필요 없다.

**브라우저** — 사용자가 직접 확인한다. 확인 항목:

1. 드래그 중 왼쪽 배지가 **전혀 움직이지 않는가.** 유령을 위아래로 옮겨도 1..N이 제자리인가
2. 배지 개수가 **카드 수 + 들고 있는 카드**와 맞는가
3. **빈 날짜**로 들고 가면 1번 빨간공이 생긴 채 고정되는가
4. 세로 연결선이 끊기지 않고 이어지며 **마지막 행에서만** 사라지는가
5. **드래그가 아닌 평상시 화면**에서 배지가 카드와 정확히 정렬되는가 (기본 레이아웃 CSS를 건드리므로 회귀 확인이 필요하다)
6. 같은 날짜 안 재정렬에서 배지가 그대로인가

## 열린 위험

- **G-1이 기본 레이아웃을 바꾼다.** 드래그 중이 아닌 평상시 타임라인 모양이 회귀할 수 있다. 위 5번이 그 확인 지점이다.
- **행 높이 결정 주체가 바뀐다.** 지금은 행마다 독립 그리드라 각 행이 자기 높이를 정했다. 단일 그리드에서는 같은 행의 배지 셀과 카드 셀 중 큰 쪽이 행 높이가 된다. 배지는 28px이라 카드가 항상 크지만, 카드가 아주 짧은 경우 28px이 하한이 된다.

## G 구현 결과 (as-built)

계획대로. 다만 클래스 이름이 하나 더 바뀌었다.

| 항목 | 구현 |
|---|---|
| G-1 | `.prototype-trip-detail-screen .timeline`에 `display: grid; grid-template-columns: 28px minmax(0,1fr); align-items: start; column-gap: 12px`. `row-gap` 없음 |
| G-2 | `TimelineSlotMarker` 신규. 렌더 루프가 슬롯마다 배지와 카드 셀을 형제로 내보낸다. 번호 = `renderIndex + 1`(유령 포함). `SortablePlaceItem`의 `placeNumber` prop 제거 |
| G-3 | `.timeline-insertion-slot`에 `grid-column: 1 / -1` |
| G-4 | `.timeline-item:last-child .timeline-marker::after` → `.timeline-marker.last::after`. `isLast` prop으로 명시 |
| G-5 | `.timeline-item.dragging .timeline-marker` 규칙 제거 |

**계획에 없던 정리** — 카드 셀의 루트 클래스를 `timeline-item` → `timeline-slot`으로 바꿨다. 더 이상 2열 행이 아니라 그리드 셀 하나이므로 이름이 실제와 어긋났고, 남은 `.timeline-item.dragging` / `.timeline-item.moving` 규칙도 함께 옮겼다. `.timeline-item`은 코드베이스에서 사라졌다.

**회귀 범위** — `.timeline` 클래스는 `ItineraryDetailPage.tsx`에서만 쓰이고 그리드 규칙도 `.prototype-trip-detail-screen` 아래로 스코프돼 있다. 다른 화면에 번지지 않는다.

**검증**

```
npx vitest run src/app/__tests__/trip-detail.test.tsx src/utils.test.ts   → 86 passed
npm run build (typecheck 포함)                                            → 성공
```

테스트 수는 그대로다 — G는 새 순수 함수를 만들지 않고 기존 핀 테스트의 단언을 새 구조로 갱신했다(`.timeline` 그리드 존재 / `row-gap` 부재 / 삽입 슬롯 `grid-column` / `.timeline-item.dragging .timeline-marker` 부재 / `placeNumber` 부재 / 유령이 마커를 렌더하지 않음). 모두 먼저 빨간 것을 확인했다.

### G 회귀 — 카드 사이가 크게 벌어짐 (실측에서 발견, 수정 완료)

G-1 적용 직후 실기기에서 나온 회귀다. 계획의 "열린 위험 — G-1이 기본 레이아웃을 바꾼다"가 실제로 터진 사례이므로 함정을 기록해 둔다.

**증상** — 드래그와 무관한 평상시 화면에서 카드 사이가 100px 넘게 벌어지고 세로 연결선이 그 빈 공간을 관통했다. 카드가 적은 날짜일수록 심했다.

**원인** — `.timeline`에는 원래부터 `min-height: clamp(360px, calc(100dvh - 480px), 520px)`가 걸려 있다. 블록 컨테이너였을 때는 내용보다 큰 높이가 그냥 **아래에 빈 공간으로** 남았다.

그리드로 바꾸는 순간 `align-content`의 기본값 `normal`이 그리드에서는 **stretch로 동작한다.** 자동 크기 행들이 남는 세로 공간을 나눠 갖는다. 그래서 카드 2개짜리 날짜에서는 300px 가까운 여유가 두 행에 분배돼 카드 사이가 벌어졌다.

`row-gap`을 피한 것과는 **다른 함정이다.** row-gap은 간격을 명시적으로 더하는 것이고, 이건 명시하지 않은 기본값이 남는 공간을 퍼뜨리는 것이다. 둘 다 밟았다.

**수정** — `align-content: start` 한 줄. 행들이 위에 붙고 남는 공간은 아래에 남아 블록일 때와 같아진다.

G의 구조 변경(배지 분리, 슬롯 번호, 유령 포함)은 건드리지 않았다. `min-height`를 줄이거나 그리드를 되돌리는 방법도 있었으나 각각 F-1(빈 날짜 드롭 영역 확보)과 G 자체를 망가뜨린다.

CSS 핀에 단언을 추가했다 — `.timeline`에 `align-content: start`가 있어야 한다.

**교훈** — 기존 요소를 그리드/플렉스로 바꿀 때는 그 요소에 이미 걸린 `min-height`·`height`를 먼저 확인할 것. 블록에서 무해하던 여유 높이가 배치 알고리즘이 바뀌는 순간 내용 사이로 퍼진다.

## 브라우저 검증 현황 (2026-08-25, 사용자 실기기)

로컬 브라우저 테스트는 사용자가 직접 수행한다.

**확인됨**

- D·E·F 전반 — "다른건 해결됨" (자동 스크롤·휠, 빈 날짜, 유령 진동)
- G 회귀 수정 — 카드 사이 간격 정상 복귀
- G 핵심 — 드래그 중 왼쪽 배지 고정

**아직 확인 안 됨**

- 배지 개수가 카드 수 + 들고 있는 카드와 맞는가
- 빈 날짜로 들고 갔을 때 1번 빨간공이 생긴 채 고정되는가
- 세로 연결선이 이어지고 마지막 행에서만 사라지는가
- 같은 날짜 안 재정렬에서 배지가 그대로인가
- 앞선 계획의 C-3(자동 전환 지연 10ms에서 Day1→Day5 가로 쓸기)

**미해결로 남은 관찰**

- `.timeline-ghost-card`에 높이 지정이 없어 실제 카드(70~74px)보다 얇을 수 있다. 벌어지는 자리가 삽입될 카드보다 작아 보이면 손볼 대상이다. 아직 지적된 바 없어 건드리지 않았다.
- `DroppableTimelinePosition`(높이 0 삽입 슬롯)은 F-1 이후 `pointerWithin`도 `closestCenter`도 도달하지 않는 죽은 요소다. 별건 정리 후보.

---

# 후속 3 — 드롭해도 순서가 안 바뀜 (2026-08-25)

드래그 동작은 대부분 해결됐는데 정작 드롭 후 순서가 원래대로 돌아온다는 보고. 간헐적이었다(다시 시도하니 되는 경우도 있었다). 검토에서 원인 두 개를 찾았다.

## ① 빈 공간에 놓을 때 위치가 한 칸 밀림 — 실제 버그

백엔드 `move_trip_place`(`backend/app/services/trips.py:1262-1272`)는 같은 날짜일 때 **끌고 있는 카드를 먼저 뺀 목록**에 `position - 1`로 끼운다.

```python
source_places_without_place = [c for c in _ordered_places(source_day) if c.id != place.id]
target_places = source_places_without_place if same_day else _ordered_places(target_day)
target_places.insert(payload.position - 1, place)
```

그런데 F-3에서 넣은 `day-area` 경로가 쓰는 `getClosestCurrentDayTimelinePosition`은 유령만 제외하고 **끌고 있는 카드는 포함**해서 셌다.

```
[A, B, C]에서 A를 끌어 B와 C 사이에 놓으면
  itemRects = [A, B, C] → C의 인덱스 2 → position 3
  백엔드: [B, C]에 인덱스 2로 삽입 → [B, C, A]   (맨 뒤로 감)
  기대:   [B, A, C]
```

끌고 있는 카드가 **놓는 지점보다 위에 있을 때만** 어긋난다. 아래면 맞는다 — 그래서 간헐적으로 보였다. 카드 위에 정확히 겹쳐 놓는 경로(`resolveTimelineDropTarget`이 `sortableIdsByDay`의 인덱스를 쓰는 쪽)는 전 경우 검산 결과 정확하다. **빈 공간(카드 사이 12px 간격, 마지막 카드 아래)에 놓을 때만** 틀렸다.

## ② 짧게 끌면 드롭이 통째로 무시됨

`.timeline-slot`은 dnd-kit이 측정하는 노드인데 변형은 안쪽 `<article>`에만 걸린다. 슬롯의 판정 사각형이 **원래 자리에 그대로** 있으므로, 카드 한 장 높이(약 70px)보다 적게 끌면 포인터가 아직 자기 슬롯 안이다. `over === active`가 되고 `resolveTimelineDropTarget`이 자기 자신 방어로 `null`을 돌려 드롭이 무시된다.

dnd-kit 기준으로는 "원래 자리로 되돌림"이라 정상 동작이다. 다만 오버레이는 커서를 따라 눈에 띄게 움직였으므로 사용자에게는 고장으로 보인다.

## 결정 사항 (승인 완료)

둘 다 고친다.

**②에 트레이드오프가 없다는 점이 검토 중 확인됐다.** 처음에는 "제자리에 도로 놓기가 불가능해진다"고 판단했으나 틀렸다. ①과 ②를 함께 적용하면 제자리 놓기는 기하학적으로 자연히 보존된다.

```
[A, B, C]에서 A를 30px만 끌고 놓으면
  itemRects(A 제외) = [B, C], 포인터는 아직 B의 중점 위 → position 1
  백엔드: [B, C]에 0번 삽입 → [A, B, C]   변화 없음
```

즉 "안 움직였으면 안 바뀌고 넘어갔으면 바뀐다"가 **포인터 위치로** 결정된다. 기존 판정("원래 슬롯 사각형 안이냐")은 그 사각형이 화면상 카드와 어긋나 있어 틀린 결과를 냈다.

시각적으로도 ②가 낫다. 활성 카드를 후보에서 빼면 포인터가 자기 슬롯 안일 때 충돌이 `day-area`뿐이고, 그 id는 `items`에 없어 `overIndex = -1`이 되어 `verticalListSortingStrategy`가 아무것도 밀지 않는다. 집어 들자마자 목록이 흔들리는 일이 없다. F-1의 `day-area`가 없었다면 `closestCenter` 폴백으로 이웃 카드가 잡혀 목록이 튀었을 것이다.

## H. 구현

| 항목 | 내용 |
|---|---|
| H-1 | `resolveSameDayInsertPosition` 신규. 세기 전에 활성 카드를 목록에서 뺀다. 백엔드의 "자기 자신 뺀 목록" 의미와 일치 |
| H-2 | `excludeActiveCollision` 신규. 활성 카드를 드롭 후보에서 제거 |
| H-3 | `placeDragCollisionDetection`이 **제외를 먼저, 구체화를 나중에** 수행. 순서가 반대면 `[day-area, 활성카드]`에서 활성카드가 남고 그걸 빼면 후보가 통째로 비어 드롭이 무시된다 |
| H-4 | `getClosestCurrentDayTimelinePosition(activeSortableId)`로 시그니처 변경. 호출부 4곳 전부 `String(event.active.id)` 전달 |

**검증** — 88 passed (86 + 신규 2개: 같은 날짜 삽입 위치 4케이스, 충돌 제외 4케이스). 빌드 성공.

## 지켜볼 것

②로 유령도 충돌 후보에서 빠진다. 유령 위에 포인터가 있으면 `resolveGhostDropOverId`가 고정해주던 것 대신 `day-area` 경로로 위치가 계산되어 포인터를 더 민감하게 따라간다. `MeasuringStrategy.Always`(E-1)가 좌표 되먹임은 막지만, 유령이 다시 떨리면 이게 원인이다.

---

# 별건 — 일정 만들기 달력 한글화 및 역순 날짜 정규화 (2026-08-25)

드래그 작업과 주제가 다르지만 같은 브랜치에서 이어서 처리했으므로 여기 기록한다.

## 요청

1. 새 일정 만들기의 달력이 영어로 표기된다. 한글화.
2. 첫날·마지막 날을 반대 순서로 고르면 일수가 음수가 되어 오류가 난다. 역순으로 골라도 자동으로 절댓값 범위가 되게 하고, 음수는 설정될 수 없게.
3. (추가 요청) 일정 수정 화면도 같이.

## 원인

`tripDateDayCount`(`ItineraryCreatePage.tsx:49-54`)가 `(end - start) / 86_400_000 + 1`을 그대로 돌려준다. 역순 선택을 막는 곳이 **아무 데도 없다.**

`selectCalendarDate`(`:519`)는 첫 클릭이면 시작=끝으로 두고 앵커를 `end`로 넘긴 뒤, 두 번째 클릭에서 무조건 `updateDates(startDate, value)`를 부른다. 이전 날짜를 고르면 그대로 역전되고 `dayCount`가 0 이하가 되어 `dateRangeError`가 뜨며 생성 버튼이 잠긴다.

`ItineraryEditPage.tsx`의 `dayCountFromDateInputs`(`:9-15`)도 같은 구조다.

## 결정 사항 (승인 완료)

| 항목 | 결정 |
|---|---|
| 정규화 | 끝이 시작보다 앞이면 맞바꾼다 |
| 적용 위치 | create는 `updateDates` 한 곳, edit는 파생값과 저장 값 |
| 날짜 칸 aria-label | ISO(`2026-08-26`) 유지 |
| edit 페이지 | 같이 고친다 |

## 구현

**공용 순수 함수** — `src/utils/dateDefaults.ts`에 `normalizeTripDateRange(startDate, endDate)` 추가. 끝이 앞이면 맞바꾸고, 값이 비었으면 그대로 돌려준다(순서 문제가 아니라 입력이 없는 것이므로 호출부가 따로 알려야 한다). ISO 문자열이라 사전순 비교가 곧 날짜순 비교다.

**create 페이지** — `updateDates` 안에 넣었다. 달력 클릭과 숨겨진 네이티브 `<input type="date">` 두 경로가 모두 이 함수를 지나므로 한 곳만 막으면 UI에서 음수가 나올 길이 없다.

**edit 페이지** — 시작·종료 입력이 서로 독립이라 입력 도중에 맞바꾸면 **방금 고친 칸이 튄다.** 화면에는 입력한 그대로 두고, 미리보기 일수(`nextDayCount`)와 저장 payload에만 정규화한 값을 쓴다. 결과적으로 음수는 나올 수 없고 역순으로 넣어도 절댓값 범위로 저장된다.

`tripDateDayCount`와 `dateRangeError`는 남겼다. 정규화 뒤엔 도달하지 않지만 파싱 실패 같은 경우의 방어선이다.

**한글화 9곳** (`ItineraryCreatePage.tsx`)

| 위치 | 이전 | 이후 |
|---|---|---|
| `:17` | `["Sun","Mon",…]` | `["일","월","화","수","목","금","토"]` |
| `:73` | `2026-08` | `2026년 8월` |
| `:212-214` | `Select start and end dates.` / `End date must be on or after the start date.` | `첫날과 마지막 날을 선택하세요.` / `마지막 날은 첫날과 같거나 뒤여야 해요.` |
| `:744` | `Travel dates` | `여행 날짜` |
| `:748` | `${dayCount} days` / `Select dates` | `${dayCount}일` / `날짜를 선택하세요` |
| `:773` | aria `Travel date range` | `여행 날짜 범위` |
| `:781,790` | `Prev` / `Next`, aria `Previous month` / `Next month` | `이전` / `다음`, `이전 달` / `다음 달` |
| `:798` | `Select start date` / `Select end date` | `첫날을 선택하세요` / `마지막 날을 선택하세요` |

날짜 칸의 `aria-label`은 ISO를 유지했다. 화면에 보이는 것은 숫자뿐이라 영어 표기 문제가 아니고, 테스트가 이 값으로 버튼을 찾는다.

## 검증

**뒤집은 테스트 1개** — `trip-create.test.tsx`의 `"blocks creating a trip when the calendar end date is before the start date"`가 옛 동작(오류 표시 + 생성 버튼 잠김)을 고정하고 있었다. 정확히 바꾸길 원한 동작이므로 `"normalizes a reversed calendar selection into a forward date range"`로 갱신했다 — 역순으로 골라도 `오늘 ~ 내일` 범위가 되고 버튼이 활성화된다.

**신규 테스트** — `normalizeTripDateRange` 4케이스(역순 swap / 정순·같은 날 유지 / 빈 값 통과), edit 페이지 역순 저장 1케이스. 모두 빨간 것을 먼저 확인했다.

```
dateDefaults    6 passed
trip-create    22 passed
trip-edit       3 passed
```

## 범위 밖으로 둔 것

**장소 편집 저장 실패의 오해를 부르는 문구.** 백엔드 로그 확인 결과 `PATCH /api/trips/244/places/806`가 **401 Unauthorized**였는데, 화면에는 `장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.`가 떴다. 프론트가 충돌(409)이 아닌 모든 오류를 이 한 문구로 뭉뚱그리기 때문이다. `ACCESS_TOKEN_EXPIRE_MINUTES` 기본값이 30분이라 세션이 만료되면 입력값 탓처럼 보인다. 401은 "다시 로그인해 주세요"로 분리해야 한다. 별건 후보.

같은 로그에 `PATCH /api/trips/244/places/806/move` **422**도 있었다. 카드가 1개인 날짜에서 그 카드를 아래로 끌면 `position 2`를 보내는데 `max_position`이 1이라 거부된 것으로, H-1이 고친 바로 그 결함이다. H 빌드를 하드 리로드하기 전 번들에서 난 기록이다.
