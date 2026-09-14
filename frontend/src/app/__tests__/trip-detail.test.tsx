import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
// @ts-expect-error Vitest runs this assertion in Node, but this project does not install Node type declarations.
import { readFileSync } from "node:fs";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type LinkedTripPolicy,
  type Recommendation,
  type Trip,
} from "../../api";
import { App } from "../App";
import { AppProviders } from "../AppRoot";
import {
  examplePolicyPath,
  examplePolicySlug,
  examplePolicyTitle,
  getPreviewTrip,
} from "../../test/fixtures";
import { installAppKakaoSdkMock } from "../../test/kakaoMock";
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";
import {
  buildTimelineRenderItems,
  buildTimelineSortableIds,
  isCrossDayTimelineDrag,
  DAY_EDGE_WIDTH_PX,
  DAY_EDGE_FIRST_DELAY_MS,
  DAY_EDGE_REPEAT_MS,
  PLACE_DRAG_TOUCH_DELAY_MS,
  PLACE_DRAG_TOUCH_TOLERANCE_PX,
  PLACE_DRAG_MOUSE_DISTANCE_PX,
  resolveDayEdgeZone,
  resolveDayEdgeDepth,
  resolveDayEdgeInterval,
  preferPreviousCollision,
  resolveDayStripPadding,
  resolveDayStripScrollLeft,
  resolveTimeSortedPosition,
  DAY_TAB_POINTER_TOLERANCE_PX,
  PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
  shouldAllowPlaceDragAutoScroll,
  isPointerInsideClientRect,
  isWheelInsideNestedScroller,
  isPointerNearClientRect,
  parseDayAreaDropId,
  excludeActiveCollision,
  preferSpecificDropTargets,
  resolveSameDayInsertPosition,
  resolveDayAreaOverId,
  resolveDayZoneRect,
  resolveGhostDropOverId,
  resolvePointerDayTarget,
  resolvePointerVerifiedTimelineOverId,
  resolveNextOpenTimeEditorId,
  resolvePlaceDragOverId,
  resolveClosestTimelinePosition,
  resolveRaisedTimelineHeightLock,
  resolveTimelineHeightLock,
  resolveTimelineDropTarget,
  PlaceEditorSheet,
  shouldForwardWindowWheelToAppScroll,
  shouldUseDayRowDragOverlay,
  shouldScheduleDaySwitch,
} from "../../pages/itinerary/ItineraryDetailPage";

describe("Travel Hunter app — trip detail & itinerary", () => {
  it("keeps place search input responsive while deferring parent updates", async () => {
    const onSearchChange = vi.fn();

    try {
      vi.useFakeTimers();
      render(
        <PlaceEditorSheet
          batchRecovery={{ kind: "none" }}
          dayNumber={1}
          dayOptions={[]}
          error=""
          form={{ time: "", label: "", meta: "" }}
          isLoadingSearch={false}
          isSaving={false}
          mode="add"
          onChange={vi.fn()}
          onClose={vi.fn()}
          onDayChange={vi.fn()}
          onDiscardDraft={vi.fn()}
          onRemoveBasketItem={vi.fn()}
          onRetryBasketDay={vi.fn()}
          onSearchChange={onSearchChange}
          onSelectSearchCandidate={vi.fn()}
          onSelectedDayRef={vi.fn()}
          onSubmit={vi.fn()}
          placeBasket={[]}
          preview={{ source: "empty", place: null }}
          restoredDraftMessage=""
          saveEligibility="empty"
          searchCandidates={[]}
          searchError=""
          searchQuery=""
        />,
      );

      const input = screen.getByLabelText("장소 검색");
      fireEvent.change(input, { target: { value: "성산일출봉" } });

      expect(input).toHaveValue("성산일출봉");
      expect(onSearchChange).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(349);
      expect(onSearchChange).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(1);
      expect(onSearchChange).toHaveBeenCalledExactlyOnceWith("성산일출봉");
    } finally {
      vi.useRealTimers();
    }
  });

  it("forwards desktop window wheel only when the app container can scroll vertically", () => {
    const classList = { contains: vi.fn(() => false) };
    const appContainer = {
      classList,
      clientHeight: 600,
      scrollHeight: 1200,
      scrollTop: 100,
    } as unknown as HTMLElement;

    expect(
      shouldForwardWindowWheelToAppScroll(
        { defaultPrevented: false, deltaY: 80 },
        appContainer,
      ),
    ).toBe(true);
  });

  it("keeps forwarding wheel scrolling while a place drag is in progress", () => {
    // 카드를 잡은 채로 휠을 굴려 일정 아래쪽을 볼 수 있어야 한다.
    const classList = {
      contains: vi.fn((className: string) =>
        className === "itinerary-place-drag-scroll-locked",
      ),
    };
    const appContainer = {
      classList,
      clientHeight: 600,
      scrollHeight: 1200,
      scrollTop: 100,
    } as unknown as HTMLElement;

    expect(
      shouldForwardWindowWheelToAppScroll(
        { defaultPrevented: false, deltaY: 80 },
        appContainer,
      ),
    ).toBe(true);
  });

  it("leaves the wheel alone inside a nested scroller such as an open sheet", () => {
    // 휠은 window까지 버블링된다. 브리지가 대상을 안 가리면 시트 위에서 굴려도
    // preventDefault로 기본 스크롤을 죽이고 뒤 화면을 스크롤한다.
    expect(
      isWheelInsideNestedScroller([
        { canScrollY: false, isAppContainer: false },
        { canScrollY: true, isAppContainer: false },
        { canScrollY: true, isAppContainer: true },
      ]),
    ).toBe(true);
  });

  it("still bridges the wheel from the desktop gutter", () => {
    // 앱 컨테이너에 닿기 전 스크롤러가 없으면 브리지가 원래 하던 일을 한다.
    expect(
      isWheelInsideNestedScroller([
        { canScrollY: false, isAppContainer: false },
        { canScrollY: true, isAppContainer: true },
      ]),
    ).toBe(false);
    expect(isWheelInsideNestedScroller([])).toBe(false);
  });

  it("does not forward non-scrolling or already-handled wheel events", () => {
    const classList = { contains: vi.fn(() => false) };
    const appContainer = {
      classList,
      clientHeight: 600,
      scrollHeight: 600,
      scrollTop: 0,
    } as unknown as HTMLElement;

    expect(
      shouldForwardWindowWheelToAppScroll(
        { defaultPrevented: false, deltaY: 80 },
        appContainer,
      ),
    ).toBe(false);
    expect(
      shouldForwardWindowWheelToAppScroll(
        { defaultPrevented: true, deltaY: 80 },
        {
          ...appContainer,
          scrollHeight: 1200,
        } as unknown as HTMLElement,
      ),
    ).toBe(false);
    expect(
      shouldForwardWindowWheelToAppScroll(
        { defaultPrevented: false, deltaY: 0 },
        {
          ...appContainer,
          scrollHeight: 1200,
        } as unknown as HTMLElement,
      ),
    ).toBe(false);
  });

  it("inserts the active card once at the target Day ghost position", () => {
    expect(
      buildTimelineSortableIds({
        activeSortableId: "place:move-me",
        ghostPosition: 2,
        sortableIds: ["place:target-a", "place:target-b", "place:target-c"],
      }),
    ).toEqual([
      "place:target-a",
      "place:move-me",
      "place:target-b",
      "place:target-c",
    ]);
  });

  it("keeps the target Day sortable list unchanged without a ghost position", () => {
    expect(
      buildTimelineSortableIds({
        activeSortableId: "place:move-me",
        ghostPosition: null,
        sortableIds: ["place:target-a", "place:target-b"],
      }),
    ).toEqual(["place:target-a", "place:target-b"]);
  });

  it("renders a target Day ghost between the resolved adjacent cards", () => {
    expect(
      buildTimelineRenderItems({
        ghostPosition: 2,
        items: ["target-a", "target-b", "target-c"],
      }),
    ).toEqual([
      { type: "item", value: "target-a" },
      { type: "ghost" },
      { type: "item", value: "target-b" },
      { type: "item", value: "target-c" },
    ]);
  });

  it("resolves cross-day timeline card drops to the hovered place position", () => {
    expect(
      resolveTimelineDropTarget({
        activeSortableId: "place:move-me",
        dayNumbers: [1, 2, 3],
        overId: "place:target-b",
        sortableIdsByDay: {
          1: ["place:move-me"],
          2: ["place:target-a", "place:target-b", "place:target-c"],
          3: [],
        },
        visibleDay: 1,
      }),
    ).toEqual({ dayNumber: 2, position: 2 });
  });

  it("resolves day-tab timeline drops to the end of the target day", () => {
    expect(
      resolveTimelineDropTarget({
        activeSortableId: "place:move-me",
        dayNumbers: [1, 2, 3],
        overId: "day:3",
        sortableIdsByDay: {
          1: ["place:move-me"],
          2: ["place:target-a"],
          3: ["place:target-b", "place:target-c"],
        },
        visibleDay: 1,
      }),
    ).toEqual({ dayNumber: 3, position: 3 });
  });

  it("resolves explicit timeline insertion slots to the requested position", () => {
    expect(
      resolveTimelineDropTarget({
        activeSortableId: "place:move-me",
        dayNumbers: [1, 2, 3],
        overId: "day-position:2:1",
        sortableIdsByDay: {
          1: ["place:move-me"],
          2: ["place:target-a", "place:target-b"],
          3: [],
        },
        visibleDay: 1,
      }),
    ).toEqual({ dayNumber: 2, position: 1 });
  });

  it("detects cross-day timeline drags after switching to the target day", () => {
    expect(
      isCrossDayTimelineDrag({
        activeSortableId: "place:move-me",
        sortableIdsByDay: {
          1: ["place:move-me"],
          2: ["place:target-a", "place:target-b"],
        },
        visibleDay: 2,
      }),
    ).toBe(true);

    expect(
      isCrossDayTimelineDrag({
        activeSortableId: "place:move-me",
        sortableIdsByDay: {
          1: ["place:move-me", "place:target-a"],
          2: ["place:target-b"],
        },
        visibleDay: 1,
      }),
    ).toBe(false);
  });

  it("requires the pointer itself to be inside a Day tab before switching days", () => {
    const dayTabRect = {
      left: 100,
      right: 180,
      top: 40,
      bottom: 72,
    };

    expect(isPointerInsideClientRect({ x: 120, y: 60 }, dayTabRect)).toBe(
      true,
    );
    expect(isPointerInsideClientRect({ x: 120, y: 88 }, dayTabRect)).toBe(
      false,
    );
    expect(isPointerInsideClientRect({ x: 92, y: 60 }, dayTabRect)).toBe(
      false,
    );
    expect(isPointerInsideClientRect(null, dayTabRect)).toBe(false);
    expect(isPointerInsideClientRect({ x: 120, y: 60 }, null)).toBe(false);
  });

  it("prioritizes the timeline first-position area over an adjacent Day tab", () => {
    expect(
      shouldScheduleDaySwitch({
        pointer: { x: 124, y: 146 },
        dayTabRect: { left: 80, right: 170, top: 104, bottom: 150 },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(false);
  });

  it("keeps Day switching available inside the Day button above the timeline", () => {
    expect(
      shouldScheduleDaySwitch({
        pointer: { x: 124, y: 118 },
        dayTabRect: { left: 80, right: 170, top: 104, bottom: 150 },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(true);
  });

  it("reports strict containment misses for the gap between Day tabs", () => {
    const firstDayTabRect = {
      left: 100,
      right: 160,
      top: 40,
      bottom: 72,
    };
    const secondDayTabRect = {
      left: 174,
      right: 234,
      top: 40,
      bottom: 72,
    };
    const pointerBetweenTabs = { x: 167, y: 60 };

    expect(
      isPointerInsideClientRect(pointerBetweenTabs, firstDayTabRect),
    ).toBe(false);
    expect(
      isPointerInsideClientRect(pointerBetweenTabs, secondDayTabRect),
    ).toBe(false);
  });

  it("keeps the compact Day overlay in the gap between Day buttons", () => {
    expect(
      shouldUseDayRowDragOverlay({
        pointer: { x: 167, y: 60 },
        dayTabsRect: { left: 100, right: 234, top: 40, bottom: 72 },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(true);
  });

  it("uses the closest current-Day insertion position for a Day-row gap drop", () => {
    expect(
      resolveClosestTimelinePosition({
        pointerY: 84,
        itemRects: [
          { top: 160, bottom: 232 },
          { top: 244, bottom: 316 },
          { top: 328, bottom: 400 },
        ],
      }),
    ).toBe(1);
    expect(
      resolveClosestTimelinePosition({
        pointerY: 290,
        itemRects: [
          { top: 160, bottom: 232 },
          { top: 244, bottom: 316 },
          { top: 328, bottom: 400 },
        ],
      }),
    ).toBe(3);
  });

  it("rejects Day-tab drops when the pointer is outside the Day tab", () => {
    const dayTabRects = {
      3: {
        left: 200,
        right: 270,
        top: 80,
        bottom: 110,
      },
    };

    expect(
      resolvePointerVerifiedTimelineOverId({
        dayNumbers: [1, 2, 3],
        overId: "day:3",
        pointer: { x: 220, y: 220 },
        rectByDay: dayTabRects,
      }),
    ).toBeNull();
    expect(
      resolvePointerVerifiedTimelineOverId({
        dayNumbers: [1, 2, 3],
        overId: "day:3",
        pointer: { x: 220, y: 90 },
        rectByDay: dayTabRects,
      }),
    ).toBe("day:3");
    expect(
      resolvePointerVerifiedTimelineOverId({
        dayNumbers: [1, 2, 3],
        overId: "place:target-a",
        pointer: { x: 220, y: 220 },
        rectByDay: dayTabRects,
      }),
    ).toBe("place:target-a");
  });

  it("counts a same-day insert position without the card being dragged", () => {
    // 백엔드는 같은 날짜일 때 끌고 있는 카드를 먼저 빼고 position-1로 끼운다
    // (services/trips.py move_trip_place). 세는 목록에서도 빼야 자리가 맞는다.
    const items = [
      { sortableId: "place:a", top: 100, bottom: 170 },
      { sortableId: "place:b", top: 182, bottom: 252 },
      { sortableId: "place:c", top: 264, bottom: 334 },
    ];

    // A를 끌어 B와 C 사이에 놓는다 → 남은 목록 [B, C]의 1번 자리
    expect(
      resolveSameDayInsertPosition({
        items,
        activeSortableId: "place:a",
        pointerY: 258,
      }),
    ).toBe(2);
    // 거의 안 움직였으면 제자리 그대로여야 한다
    expect(
      resolveSameDayInsertPosition({
        items,
        activeSortableId: "place:a",
        pointerY: 140,
      }),
    ).toBe(1);
    // 맨 아래로 내리면 마지막
    expect(
      resolveSameDayInsertPosition({
        items,
        activeSortableId: "place:a",
        pointerY: 400,
      }),
    ).toBe(3);
    // 다른 날짜에서 온 카드는 애초에 이 목록에 없다
    expect(
      resolveSameDayInsertPosition({
        items,
        activeSortableId: "place:z",
        pointerY: 258,
      }),
    ).toBe(3);
  });

  it("drops the dragged card from its own collision candidates", () => {
    // 슬롯의 판정 사각형은 원래 자리에 그대로 있어서, 짧게 끌면 포인터가
    // 자기 슬롯 안이라 over === active가 되고 드롭이 통째로 무시됐다.
    expect(
      excludeActiveCollision(
        [{ id: "place:move-me" }, { id: "day-area:2" }],
        "place:move-me",
      ),
    ).toEqual([{ id: "day-area:2" }]);
    expect(
      excludeActiveCollision([{ id: "day-area:2" }], "place:move-me"),
    ).toEqual([{ id: "day-area:2" }]);
    expect(
      excludeActiveCollision([{ id: "place:move-me" }], "place:move-me"),
    ).toEqual([]);
    expect(excludeActiveCollision([{ id: "day-area:2" }], null)).toEqual([
      { id: "day-area:2" },
    ]);
  });

  it("parses the whole-timeline drop area id", () => {
    expect(parseDayAreaDropId("day-area:2")).toBe(2);
    expect(parseDayAreaDropId("day-area:0")).toBe(0);
    expect(parseDayAreaDropId("day:2")).toBeNull();
    expect(parseDayAreaDropId("day-position:2:3")).toBeNull();
    expect(parseDayAreaDropId(null)).toBeNull();
  });

  it("prefers a card over the whole-timeline area when both are hit", () => {
    // pointerWithin은 겹치는 droppable을 모두 돌려준다. 큰 영역이 카드를
    // 이기면 카드 사이 삽입 위치를 영영 못 고른다.
    expect(
      preferSpecificDropTargets([
        { id: "day-area:2" },
        { id: "place:target-b" },
      ]),
    ).toEqual([{ id: "place:target-b" }]);
    expect(
      preferSpecificDropTargets([
        { id: "day-area:2" },
        { id: "day-position:2:1" },
      ]),
    ).toEqual([{ id: "day-position:2:1" }]);
  });

  it("keeps the whole-timeline area when nothing more specific is hit", () => {
    // 빈 날짜에는 이것 말고 맞출 게 없다.
    expect(preferSpecificDropTargets([{ id: "day-area:2" }])).toEqual([
      { id: "day-area:2" },
    ]);
    expect(preferSpecificDropTargets([])).toEqual([]);
  });

  it("turns a whole-timeline area drop into the closest insert position", () => {
    expect(
      resolveDayAreaOverId({ overId: "day-area:2", closestPosition: 3 }),
    ).toBe("day-position:2:3");
    // 빈 날짜는 resolveClosestTimelinePosition이 1을 돌려준다.
    expect(
      resolveDayAreaOverId({ overId: "day-area:4", closestPosition: 1 }),
    ).toBe("day-position:4:1");
    expect(
      resolveDayAreaOverId({ overId: "place:target-b", closestPosition: 3 }),
    ).toBe("place:target-b");
    expect(
      resolveDayAreaOverId({ overId: null, closestPosition: 3 }),
    ).toBeNull();
  });

  it("keeps only one preview time editor open at a time", () => {
    // <details>는 서로를 모른다. 부모가 열린 카드 하나를 기억해야 아코디언이 된다.
    expect(resolveNextOpenTimeEditorId(null, "place:a", true)).toBe("place:a");
    expect(resolveNextOpenTimeEditorId("place:a", "place:b", true)).toBe(
      "place:b",
    );
  });

  it("closes the preview time editor when the open one is toggled shut", () => {
    expect(resolveNextOpenTimeEditorId("place:a", "place:a", false)).toBeNull();
    // 이미 닫힌 다른 카드를 닫는 신호가 와도 열린 것을 건드리지 않는다.
    expect(resolveNextOpenTimeEditorId("place:a", "place:b", false)).toBe(
      "place:a",
    );
  });

  it("pins the timeline height so a day switch cannot shrink the document", () => {
    // 날짜를 바꾸면 타임라인 내용이 통째로 바뀌어 문서가 짧아질 수 있다.
    // 그러면 브라우저가 scrollTop을 강제로 줄여 화면이 출렁인다.
    // min-height로 줄어드는 것만 막는다. 늘어나는 것은 스크롤을 건드리지 않는다.
    expect(resolveTimelineHeightLock(760.4)).toBe("760px");
    expect(resolveTimelineHeightLock(0.6)).toBe("1px");
  });

  it("refuses to pin an unusable timeline height", () => {
    expect(resolveTimelineHeightLock(null)).toBeNull();
    expect(resolveTimelineHeightLock(0)).toBeNull();
    expect(resolveTimelineHeightLock(-120)).toBeNull();
    expect(resolveTimelineHeightLock(Number.NaN)).toBeNull();
    expect(resolveTimelineHeightLock(Number.POSITIVE_INFINITY)).toBeNull();
  });

  it("stops scrolling further up once the action buttons are fully visible", () => {
    // 장소추가 버튼 줄이 다 보이는 지점에서 멈춘다. Day 탭을 기준으로 하면
    // 탭이 화면 맨 위 가장자리에 딱 붙어 겨냥이 빡빡하다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(false);
  });

  it("still scrolls up while the action buttons are off screen", () => {
    // 아래로 한참 내려간 상태에서 카드를 집으면 버튼 줄이 화면 밖이다.
    // 그때까지 막으면 다른 날짜로 옮길 방법이 없다. 모바일은 휠도 없다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: { top: -220, bottom: -180 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });

  it("never blocks downward place drag auto scroll", () => {
    // 아래쪽 자동 스크롤은 화면 밖 장소에 닿기 위해 필요하다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 860,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 450,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });

  it("does not interfere with auto scroll when it cannot measure", () => {
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: null,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: null,
        anchorRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        anchorRect: null,
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });

  it("raises the timeline pin but never lowers it during one drag", () => {
    // 장소가 적은 날짜에서 시작해 많은 날짜를 거쳐 다시 짧은 날짜로 가면
    // 문서가 줄어 스크롤이 클램프된다. 고정값은 관측한 최대 높이여야 한다.
    expect(resolveRaisedTimelineHeightLock("520px", 900)).toBe("900px");
    expect(resolveRaisedTimelineHeightLock("900px", 200)).toBe("900px");
    expect(resolveRaisedTimelineHeightLock("900px", 900)).toBe("900px");
  });

  it("starts the timeline pin from nothing and survives unusable input", () => {
    expect(resolveRaisedTimelineHeightLock(null, 640)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("640px", null)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("640px", 0)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock(null, null)).toBeNull();
    expect(resolveRaisedTimelineHeightLock("", 640)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("auto", 640)).toBe("640px");
  });

  it("turns a drop on the ghost placeholder into its resolved insert position", () => {
    // 유령은 활성 카드의 id로 등록돼 있어 그대로 두면 resolveTimelineDropTarget이
    // 자기 자신 방어로 null을 돌려주고 드롭이 통째로 무시된다.
    expect(
      resolveGhostDropOverId({
        activeSortableId: "place:move-me",
        overId: "place:move-me",
        crossDayPreview: { dayNumber: 2, position: 3 },
      }),
    ).toBe("day-position:2:3");
  });

  it("leaves a normal drop target untouched", () => {
    expect(
      resolveGhostDropOverId({
        activeSortableId: "place:move-me",
        overId: "place:target-b",
        crossDayPreview: { dayNumber: 2, position: 3 },
      }),
    ).toBe("place:target-b");
    expect(
      resolveGhostDropOverId({
        activeSortableId: "place:move-me",
        overId: "place:move-me",
        crossDayPreview: null,
      }),
    ).toBe("place:move-me");
  });

  it("spans the Day zone from below the action buttons to the timeline top", () => {
    expect(
      resolveDayZoneRect({
        actionsRect: { left: 559, right: 1347, top: 1120, bottom: 1160 },
        dayTabsRect: { left: 559, right: 1347, top: 1183, bottom: 1221 },
        timelineRect: { left: 559, right: 1347, top: 1259, bottom: 1690 },
      }),
    ).toEqual({ left: 559, right: 1347, top: 1160, bottom: 1259 });
  });

  it("falls back to the Day tab row when the neighbouring landmarks are missing", () => {
    expect(
      resolveDayZoneRect({
        actionsRect: null,
        dayTabsRect: { left: 559, right: 1347, top: 1183, bottom: 1221 },
        timelineRect: null,
      }),
    ).toEqual({ left: 559, right: 1347, top: 1183, bottom: 1221 });
    expect(
      resolveDayZoneRect({
        actionsRect: null,
        dayTabsRect: null,
        timelineRect: null,
      }),
    ).toBeNull();
  });

  it("resolves the nearest Day tab anywhere inside the Day zone", () => {
    const rectByDay = {
      1: { left: 575, right: 624, top: 1189, bottom: 1213 },
      2: { left: 630, right: 679, top: 1189, bottom: 1213 },
      3: { left: 685, right: 734, top: 1189, bottom: 1213 },
    };
    const dayZoneRect = { left: 559, right: 1347, top: 1160, bottom: 1259 };
    const timelineRect = { left: 559, right: 1347, top: 1259, bottom: 1690 };

    // 장소추가 버튼 바로 아래 — 탭에서 29px 위. 기존 12px 여유로는 잡히지 않는다.
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 700, y: 1160 },
        rectByDay,
        timelineRect,
        dayZoneRect,
      }),
    ).toBe(3);
    // 탭과 타임라인 사이 죽은 구간 — 탭에서 45px 아래.
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 600, y: 1258 },
        rectByDay,
        timelineRect,
        dayZoneRect,
      }),
    ).toBe(1);
  });

  it("still refuses a Day target inside the timeline even with a Day zone", () => {
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 700, y: 1300 },
        rectByDay: {
          1: { left: 575, right: 624, top: 1189, bottom: 1213 },
          2: { left: 630, right: 679, top: 1189, bottom: 1213 },
          3: { left: 685, right: 734, top: 1189, bottom: 1213 },
        },
        timelineRect: { left: 559, right: 1347, top: 1259, bottom: 1690 },
        dayZoneRect: { left: 559, right: 1347, top: 1160, bottom: 1259 },
      }),
    ).toBeNull();
  });

  it("schedules a Day switch anywhere inside the Day zone", () => {
    expect(
      shouldScheduleDaySwitch({
        pointer: { x: 700, y: 1170 },
        dayTabRect: { left: 685, right: 734, top: 1189, bottom: 1213 },
        timelineRect: { left: 559, right: 1347, top: 1259, bottom: 1690 },
        dayZoneRect: { left: 559, right: 1347, top: 1160, bottom: 1259 },
      }),
    ).toBe(true);
  });

  it("accepts a pointer just outside a Day tab edge as a hit", () => {
    const dayTabRect = { left: 100, right: 176, top: 40, bottom: 64 };

    expect(
      isPointerNearClientRect(
        { x: 120, y: 32 },
        dayTabRect,
        DAY_TAB_POINTER_TOLERANCE_PX,
      ),
    ).toBe(true);
    expect(
      isPointerNearClientRect(
        { x: 120, y: 72 },
        dayTabRect,
        DAY_TAB_POINTER_TOLERANCE_PX,
      ),
    ).toBe(true);
    expect(
      isPointerNearClientRect(
        { x: 120, y: 100 },
        dayTabRect,
        DAY_TAB_POINTER_TOLERANCE_PX,
      ),
    ).toBe(false);
    expect(
      isPointerNearClientRect(null, dayTabRect, DAY_TAB_POINTER_TOLERANCE_PX),
    ).toBe(false);
    expect(
      isPointerNearClientRect(
        { x: 120, y: 48 },
        null,
        DAY_TAB_POINTER_TOLERANCE_PX,
      ),
    ).toBe(false);
  });

  it("resolves a Day target when the pointer drifts just above the tab row", () => {
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 190, y: 72 },
        rectByDay: {
          1: { left: 80, right: 150, top: 80, bottom: 104 },
          2: { left: 158, right: 228, top: 80, bottom: 104 },
          3: { left: 236, right: 306, top: 80, bottom: 104 },
        },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(2);
  });

  it("resolves the nearest Day tab when the pointer sits in the gap between tabs", () => {
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 156, y: 92 },
        rectByDay: {
          1: { left: 80, right: 150, top: 80, bottom: 104 },
          2: { left: 158, right: 228, top: 80, bottom: 104 },
          3: { left: 236, right: 306, top: 80, bottom: 104 },
        },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(2);
  });

  it("still refuses a Day target while the pointer is inside the timeline", () => {
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 190, y: 136 },
        rectByDay: {
          1: { left: 80, right: 150, top: 80, bottom: 104 },
          2: { left: 158, right: 228, top: 80, bottom: 104 },
          3: { left: 236, right: 306, top: 80, bottom: 104 },
        },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBeNull();
  });

  it("schedules a Day switch when the pointer hovers just above the Day tab", () => {
    expect(
      shouldScheduleDaySwitch({
        pointer: { x: 124, y: 96 },
        dayTabRect: { left: 80, right: 170, top: 104, bottom: 128 },
        timelineRect: { left: 64, right: 820, top: 150, bottom: 760 },
      }),
    ).toBe(true);
  });

  it("does not switch the day merely by crossing the tab row", () => {
    // 탭 위를 지나가는 것은 이동영역이 아니다. 가운데는 순서 변경 자리다.
    expect(
      resolveDayEdgeZone({ pointerX: 200, left: 0, right: 390, edgeWidth: 80 }),
    ).toBe(0);
  });

  it("hides the cross-day placeholder like the same-day one", () => {
    // 같은 날짜는 끌던 카드를 opacity 0 으로 감춰 자리만 남긴다.
    // 다른 날짜의 자리표시도 똑같이 보이지 않아야 한다.
    const css = readFileSync("src/styles/app.css", "utf8");
    expect(css).toMatch(
      /\.timeline-slot\.dragging \.timeline-sortable-card\s*\{[^}]*opacity:\s*0/s,
    );
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.timeline-ghost-card\s*\{[^}]*opacity:\s*0;/s,
    );
    expect(css).not.toMatch(
      /\.prototype-trip-detail-screen \.timeline-ghost-card\s*\{[^}]*border:\s*1px dashed/s,
    );
  });

  it("keeps the runner-up winner to stop the two-way flicker", () => {
    const a = { id: "a" };
    const b = { id: "b" };
    const c = { id: "c" };
    // 직전 승자가 2등으로 밀렸으면 되돌린다. 이게 깜박임을 막는다.
    expect(preferPreviousCollision([b, a, c], "a")).toEqual([a, b, c]);
    // 이미 1등이면 손대지 않는다
    expect(preferPreviousCollision([a, b, c], "a")).toEqual([a, b, c]);
    // 3등 밖으로 밀렸으면 포인터가 실제로 떠난 것이다. 붙들지 않는다.
    expect(preferPreviousCollision([b, c, a], "a")).toEqual([b, c, a]);
    // 기억이 없거나 후보가 하나면 그대로
    expect(preferPreviousCollision([b, a], null)).toEqual([b, a]);
    expect(preferPreviousCollision([b], "a")).toEqual([b]);
  });

  it("styles the drag edge zones without color", () => {
    // 색 대신 은은한 어둠과 화살표로만 알린다. 붉은 채움을 되살리지 않는다.
    const css = readFileSync("src/styles/app.css", "utf8");
    expect(css).toMatch(/\.itinerary-day-edge\.left\s*\{[^}]*linear-gradient/s);
    expect(css).toMatch(/\.itinerary-day-edge\.right\s*\{[^}]*linear-gradient/s);
    expect(css).not.toMatch(/\.itinerary-day-edge[^{]*\{[^}]*rgba\(255,\s*94/s);
  });

  it("keeps the edge zone armed beyond the app column", () => {
    // PC 는 앱이 가운데 좁은 칸이라 카드를 옆으로 끌면 칸 밖으로 나간다.
    // 거기서 꺼지면 "사이드로 옮겨도 안 넘어간다"가 된다.
    expect(
      resolveDayEdgeZone({ pointerX: -120, left: 550, right: 1370, edgeWidth: 80 }),
    ).toBe(-1);
    expect(
      resolveDayEdgeZone({ pointerX: 1900, left: 550, right: 1370, edgeWidth: 80 }),
    ).toBe(1);
    // 밖으로 아무리 나가도 깊이는 1 을 넘지 않는다
    expect(
      resolveDayEdgeDepth({ pointerX: -500, left: 0, right: 390, zone: -1, edgeWidth: 80 }),
    ).toBe(1);
  });

  it("arms the edge zone only inside the edge band", () => {
    expect(
      resolveDayEdgeZone({ pointerX: 40, left: 0, right: 390, edgeWidth: 80 }),
    ).toBe(-1);
    expect(
      resolveDayEdgeZone({ pointerX: 360, left: 0, right: 390, edgeWidth: 80 }),
    ).toBe(1);
    expect(
      resolveDayEdgeZone({ pointerX: null, left: 0, right: 390, edgeWidth: 80 }),
    ).toBe(0);
  });

  it("measures depth from the inner boundary outward", () => {
    expect(
      resolveDayEdgeDepth({ pointerX: 80, left: 0, right: 390, zone: -1, edgeWidth: 80 }),
    ).toBe(0);
    expect(
      resolveDayEdgeDepth({ pointerX: 0, left: 0, right: 390, zone: -1, edgeWidth: 80 }),
    ).toBe(1);
    expect(
      resolveDayEdgeDepth({ pointerX: 390, left: 0, right: 390, zone: 1, edgeWidth: 80 }),
    ).toBe(1);
  });

  it("accelerates toward the outer edge", () => {
    expect(resolveDayEdgeInterval(0)).toBe(DAY_EDGE_REPEAT_MS);
    expect(Math.round(resolveDayEdgeInterval(1))).toBe(221);
    expect(resolveDayEdgeInterval(1)).toBeLessThan(resolveDayEdgeInterval(0));
  });

  it("holds the confirmed edge-zone tuning", () => {
    expect(DAY_EDGE_WIDTH_PX).toBe(80);
    expect(DAY_EDGE_FIRST_DELAY_MS).toBe(900);
    expect(DAY_EDGE_REPEAT_MS).toBe(620);
  });

  it("pads both ends so the first and last day can sit centered", () => {
    expect(resolveDayStripPadding(390, 60, 60)).toEqual({ left: 165, right: 165 });
    expect(resolveDayStripPadding(100, 200, 200)).toEqual({ left: 0, right: 0 });
  });

  it("clamps the centering scroll at both ends", () => {
    expect(
      resolveDayStripScrollLeft({
        tabOffsetLeft: 0,
        tabWidth: 60,
        containerWidth: 390,
        scrollWidth: 2000,
      }),
    ).toBe(0);
    expect(
      resolveDayStripScrollLeft({
        tabOffsetLeft: 1980,
        tabWidth: 60,
        containerWidth: 390,
        scrollWidth: 2000,
      }),
    ).toBe(1610);
  });

  it("drops an edited place below places sharing the same time", () => {
    // 15:00 을 09:00 으로 고치면 기존 09:00 들 밑, 11:00 앞에 선다
    const places = [
      { id: "a", time: "09:00" },
      { id: "b", time: "09:00" },
      { id: "c", time: "11:00" },
      { id: "d", time: "15:00" },
    ];
    expect(
      resolveTimeSortedPosition({ places, movingPlaceId: "d", nextTime: "09:00" }),
    ).toBe(3);
  });

  it("keeps an edited place last when nothing is later", () => {
    const places = [
      { id: "a", time: "09:00" },
      { id: "b", time: "11:00" },
    ];
    expect(
      resolveTimeSortedPosition({ places, movingPlaceId: "a", nextTime: "23:00" }),
    ).toBe(2);
  });

  it("moves an edited place to the front when everything is later", () => {
    const places = [
      { id: "a", time: "09:00" },
      { id: "b", time: "11:00" },
    ];
    expect(
      resolveTimeSortedPosition({ places, movingPlaceId: "b", nextTime: "07:00" }),
    ).toBe(1);
  });

  it("skips untimed places when finding the spot", () => {
    const places = [
      { id: "a", time: "09:00" },
      { id: "b", time: null },
      { id: "c", time: "15:00" },
      { id: "d", time: "20:00" },
    ];
    expect(
      resolveTimeSortedPosition({ places, movingPlaceId: "d", nextTime: "10:00" }),
    ).toBe(3);
  });

  it("stacks untimed places at the top in arrival order", () => {
    // 시간이 없으면 맨 위. 이미 위에 있는 무시간 장소들 다음에 선다.
    expect(
      resolveTimeSortedPosition({
        places: [{ id: "a", time: "09:00" }],
        movingPlaceId: "b",
        nextTime: null,
      }),
    ).toBe(1);
    expect(
      resolveTimeSortedPosition({
        places: [
          { id: "x", time: null },
          { id: "y", time: "" },
          { id: "a", time: "09:00" },
        ],
        movingPlaceId: "b",
        nextTime: null,
      }),
    ).toBe(3);
  });

  it("keeps untimed places above when placing a timed one", () => {
    // 무시간 장소는 위에 모여 있다. 건너뛰고 더 늦은 시간을 찾는다.
    expect(
      resolveTimeSortedPosition({
        places: [
          { id: "x", time: null },
          { id: "a", time: "09:00" },
          { id: "c", time: "15:00" },
        ],
        movingPlaceId: "d",
        nextTime: "10:00",
      }),
    ).toBe(3);
  });

  it("uses a long touch hold and leaves the mouse sensor alone", () => {
    // 목록 스크롤을 살리려면 터치 홀드가 길어야 한다.
    // 마우스는 거리 기준이라 지연을 걸면 오히려 어색해진다.
    expect(PLACE_DRAG_TOUCH_DELAY_MS).toBe(800);
    expect(PLACE_DRAG_TOUCH_TOLERANCE_PX).toBe(8);
    expect(PLACE_DRAG_MOUSE_DISTANCE_PX).toBe(8);
  });

  it("keeps a Day target when collision temporarily reports a timeline card", () => {
    expect(
      resolvePointerDayTarget({
        dayNumbers: [1, 2, 3],
        pointer: { x: 220, y: 92 },
        rectByDay: {
          1: { left: 80, right: 150, top: 80, bottom: 112 },
          2: { left: 158, right: 228, top: 80, bottom: 112 },
          3: { left: 236, right: 306, top: 80, bottom: 112 },
        },
        timelineRect: { left: 64, right: 820, top: 132, bottom: 760 },
      }),
    ).toBe(2);
  });

  it("keeps the physical Day target when a drag frame has no collision target", () => {
    expect(
      resolvePlaceDragOverId({
        collisionOverId: null,
        pointerDayTarget: 3,
        isOverDayRow: true,
        visibleDay: 1,
        closestVisibleDayPosition: 1,
      }),
    ).toBe("day:3");
  });

  it("resolves explicit timeline insertion slots for every visible gap", () => {
    const sortableIdsByDay = {
      1: ["place:a", "place:b", "place:c"],
      2: ["place:d", "place:e"],
    };

    expect(
      resolveTimelineDropTarget({
        activeSortableId: "place:a",
        dayNumbers: [1, 2],
        overId: "day-position:1:2",
        sortableIdsByDay,
        visibleDay: 1,
      }),
    ).toEqual({ dayNumber: 1, position: 2 });

    expect(
      resolveTimelineDropTarget({
        activeSortableId: "place:a",
        dayNumbers: [1, 2],
        overId: "day-position:2:3",
        sortableIdsByDay,
        visibleDay: 1,
      }),
    ).toEqual({ dayNumber: 2, position: 3 });
  });

  it("resolves cross-Day first, middle, and end slots without an active ghost", () => {
    const sortableIdsByDay = {
      1: ["place:move-me"],
      2: ["place:target-a", "place:target-b"],
    };

    for (const [overId, position] of [
      ["day-position:2:1", 1],
      ["day-position:2:2", 2],
      ["day-position:2:3", 3],
    ] as const) {
      expect(
        resolveTimelineDropTarget({
          activeSortableId: "place:move-me",
          dayNumbers: [1, 2],
          overId,
          sortableIdsByDay,
          visibleDay: 2,
        }),
      ).toEqual({ dayNumber: 2, position });
    }
  });

  it("starts the trip hero copy beside the back button", () => {
    const css = readFileSync("src/styles/app.css", "utf8");

    // 뒤로가기 버튼은 left 14px 에 20px 이다. 왼쪽 여백이 34px 보다 작으면 글이 버튼에 깔린다.
    const hero = /\.prototype-trip-detail-hero\s*\{([^}]*)\}/s.exec(css)?.[1] ?? "";
    const padding = /padding:\s*([^;]+);/.exec(hero)?.[1] ?? "";
    const left = Number(padding.trim().split(/\s+/)[3]?.replace("px", ""));
    expect(left).toBeGreaterThanOrEqual(34);
    // 글이 아래로 쏠리지 않도록 위 여백은 버튼 높이보다 작아야 한다.
    const top = Number(padding.trim().split(/\s+/)[0]?.replace("px", ""));
    expect(top).toBeLessThanOrEqual(38);
  });

  it("keeps the place editor day row scrollable in one line", () => {
    const css = readFileSync("src/styles/app.css", "utf8");

    // 날짜가 30개여도 줄바꿈 없이 한 줄로 밀어서 찾는다.
    expect(css).toMatch(/\.place-day-options\s*\{[^}]*flex-wrap:\s*nowrap/s);
    expect(css).toMatch(/\.place-day-options\s*\{[^}]*overflow-x:\s*auto/s);
    // PC 에서는 끌 수 있다는 표시가 없으면 안 움직이는 줄 안다.
    expect(css).toMatch(/\.place-day-options\s*\{[^}]*cursor:\s*grab/s);
  });

  it("keeps the itinerary drag target and spacing affordance styles present", () => {
    const css = readFileSync("src/styles/app.css", "utf8");

    expect(css).toMatch(/\.timeline-insertion-slot\s*\{/);
    expect(css).toMatch(/\.timeline-insertion-slot\.over\s*\{/);
    expect(css).toMatch(/\.timeline-insertion-slot\s*\{[^}]*height:\s*0/s);
    expect(css).toMatch(/\.timeline-insertion-slot\s*\{[^}]*opacity:\s*0/s);
    expect(css).toMatch(
      /\.timeline-insertion-slot\.over\s*\{[^}]*border-color:\s*transparent/s,
    );
    expect(css).toMatch(
      /\.timeline-insertion-slot\.over\s*\{[^}]*background:\s*transparent/s,
    );
    // 자리는 dnd-kit이 만든다. 슬롯이 같이 자라면 간격이 두 배가 되고 화면이 흔들린다.
    expect(css).toMatch(
      /\.timeline-insertion-slot\.over\s*\{[^}]*min-height:\s*0/s,
    );
    expect(css).not.toMatch(
      /\.timeline-insertion-slot\.over\s*\{[^}]*min-height:\s*44px/s,
    );
    // 수동 오프셋 미리보기는 SortableContext 편입으로 대체됐다.
    expect(css).not.toMatch(/\.timeline-cross-day-preview\s*\{/);
    expect(css).not.toMatch(/--timeline-cross-day-preview-height/);
    expect(css).toMatch(/\.timeline-ghost-card\s*\{/);
    expect(css).toMatch(
      /\.itinerary-drag-boundary\s*\{[^}]*height:\s*16px/s,
    );
    expect(css).toMatch(
      /\.itinerary-drag-boundary\s*\{[^}]*pointer-events:\s*none/s,
    );
    expect(css).toMatch(
      /\.timeline-insertion-slot\.over\s*\{[^}]*opacity:\s*0/s,
    );
    expect(css).toMatch(/\.place-drag-overlay\s*\{/);
    // 잠금이 스크롤 자체를 막으면 dnd-kit 자동 스크롤과 휠까지 죽는다.
    // 진동은 되돌리기 리스너와 높이 캐시를 없앤 것으로 잡는다.
    expect(css).toMatch(/itinerary-place-drag-scroll-locked/);
    expect(css).not.toMatch(
      /\.app-container\.itinerary-place-drag-scroll-locked\s*\{[^}]*overflow:\s*hidden/s,
    );
    // 드롭 대상 폭은 평소 폭과 같아야 한다. 커지면 30개 탭이 한꺼번에
    // 밀려 드래그를 시작하는 순간 가운데 정렬이 어긋난다.
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.day-tab\.drop-target\s*\{[^}]*min-width:\s*74px/s,
    );
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.day-tab\s*\{[^}]*min-width:\s*74px/s,
    );
    expect(css).not.toMatch(
      /\.prototype-trip-detail-screen \.day-tab\.drop-target em\s*\{/,
    );
    expect(css).toMatch(/\.timeline-sortable-card\s*\{/);
    // 번호 열을 카드 목록에서 떼어내 행 순서에 고정한다. 타임라인 자체가
    // 2열 그리드가 되고, 배지와 카드가 형제로 같은 행에 놓인다.
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.timeline\s*\{[^}]*grid-template-columns:\s*28px/s,
    );
    // min-height가 크므로 남는 공간을 행에 분배하면 카드 사이가 벌어진다.
    // 그리드 기본값(normal = stretch)을 start로 눌러야 한다.
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.timeline\s*\{[^}]*align-content:\s*start/s,
    );
    // 브라우저 스크롤 앵커링은 위쪽 콘텐츠가 바뀌면 scrollTop을 임의로 보정한다.
    // 날짜를 갈아치우는 순간이 정확히 그 조건이고, 휴리스틱이라 가끔만 튄다.
    expect(css).toMatch(/\.app-container\s*\{[^}]*overflow-anchor:\s*none/s);
    // 시트를 끝까지 굴리면 그 다음 휠이 부모로 넘어가 뒤 화면이 스크롤된다.
    expect(css).toMatch(
      /\.trip-select-sheet\s*\{[^}]*overscroll-behavior:\s*contain/s,
    );
    // 드롭 직후 인라인 min-height가 사라지며 타임라인이 한 프레임에 줄어든다.
    // 계산값이 바뀌는 것이므로 removeProperty로도 트랜지션이 걸린다.
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.timeline\s*\{[^}]*transition:\s*min-height/s,
    );
    expect(css).toMatch(
      /prefers-reduced-motion[\s\S]{0,400}\.prototype-trip-detail-screen \.timeline\s*\{[^}]*transition:\s*none/,
    );
    // row-gap을 쓰면 높이 0인 삽입 슬롯 행마다 간격이 덧붙는다.
    expect(css).not.toMatch(
      /\.prototype-trip-detail-screen \.timeline\s*\{[^}]*row-gap/s,
    );
    expect(css).toMatch(
      /\.timeline-insertion-slot\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/s,
    );
    // 배지가 밖으로 나가면서 이 규칙은 의미를 잃는다.
    expect(css).not.toMatch(
      /\.timeline-item\.dragging \.timeline-marker\s*\{/,
    );
    expect(css).toMatch(
      /\.prototype-trip-detail-screen \.timeline\s*\{[^}]*min-height:\s*clamp\(360px,\s*calc\(100dvh - 480px\),\s*520px\)/s,
    );
  });

  it("installs a non-passive window wheel bridge for desktop gutters", () => {
    const source = readFileSync(
      "src/pages/itinerary/ItineraryDetailPage.tsx",
      "utf8",
    );

    expect(source).toContain('window.addEventListener("wheel"');
    // 스크롤을 의도적으로 허용하므로 시작 위치로 되돌리면 사용자를 낚아챈다.
    expect(source).not.toContain("restorePlaceDragScrollPosition");
    // 날짜가 바뀌면 문서 높이도 바뀐다. 시작 시점 높이를 캐시하면 어긋난다.
    expect(source).not.toContain("bounds.contentHeight");
    expect(source).toContain("shouldForwardWindowWheelToAppScroll");
    // 유령이 끼어들어 카드가 이동하면 droppable 좌표를 다시 재야 한다.
    // 기본값(WhileDragging)은 드래그 시작 때 한 번만 재서 진동을 만든다.
    expect(source).toContain("MeasuringStrategy.Always");
    // dnd-kit도 레이아웃 변화를 감지해 스크롤을 보정한다. 날짜 전환은 거대한
    // 레이아웃 변화라 이 보정이 화면을 크게 움직인다. 우리가 직접 관리한다.
    expect(source).toContain("layoutShiftCompensation: false");
    // 날짜가 바뀌어 타임라인이 커지면 고정값도 따라 올라가야 한다.
    // 함수 정의가 아니라 호출부가 있는지를 본다.
    expect(source).toContain("raiseTimelineHeightLock()");
    // 위쪽 자동 스크롤 상한. threshold를 명시해야 판정 함수와 기준이 같아진다.
    expect(source).toContain("canScroll: canPlaceDragAutoScroll");
    expect(source).toContain("y: PLACE_DRAG_AUTO_SCROLL_THRESHOLD");
    // 멈춤 기준은 Day 탭이 아니라 그 위의 장소추가 버튼 줄이다.
    expect(source).toContain("anchorRect: actionsElement");
    // 시트 등 중첩 스크롤러 위에서는 브리지가 손대지 않는다.
    expect(source).toContain("isWheelInsideNestedScroller(path)");
    // 시간 수정창 아코디언은 부모가 열린 카드를 하나 들고 있어야 성립한다.
    expect(source).toContain("resolveNextOpenTimeEditorId(current");
    expect(source).toContain("openTimeEditorId");
    // 동작은 이미 선택 저장인데 문구만 완료로 남아 있었다.
    expect(source).toContain('"저장 중" : "선택 저장"');
    // 금지 범위는 미리보기 저장 바 안뿐이다. 편집 모드 하단 바의 `완료` 는
    // 문구와 동작이 실제로 같아(편집 종료) 이 버그와 무관하다.
    expect(source).not.toMatch(
      /recommendation-preview-action-bar[\s\S]{0,1200}>\s*완료\s*</,
    );
    // 드래그 중에는 타임라인 높이를 고정해 날짜 전환이 문서를 줄이지 못하게 한다.
    expect(source).toContain("resolveTimelineHeightLock");
    expect(source).toContain("timelineElement.style.minHeight");
    expect(source).toContain('removeProperty("min-height")');
    // 번호는 슬롯 순번이라 카드 컴포넌트가 알 필요가 없다.
    expect(source).not.toContain("placeNumber");
    // 유령도 슬롯 하나를 차지하므로 배지는 부모가 슬롯 순번으로 그린다.
    // 유령 컴포넌트 자체는 카드 셀만 렌더한다.
    expect(source).toMatch(/timeline-slot timeline-ghost/);
    expect(source).not.toMatch(
      /timeline-slot timeline-ghost[\s\S]{0,400}timeline-marker/,
    );
    expect(source).toContain("passive: false");
    expect(source).toContain(".app-container");
  });

  it("keeps long trip day selectors visible by wrapping day tabs", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "155",
      title: "15 day trip",
      dates: "2026.09.01 - 09.15",
      days: Object.fromEntries(
        Array.from({ length: 15 }, (_, index) => [index + 1, []]),
      ),
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/155");

      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /Day 15/ }),
        ).toBeInTheDocument(),
      );

      // 30일 일정에서 감싸면 알약이 다섯 줄로 쌓여 화면을 덮는다.
      // 한 줄로 두고 가로로 스크롤한다.
      const dayTabsCss = readFileSync("src/styles/app.css", "utf8");
      expect(dayTabsCss).toMatch(
        /\.prototype-trip-detail-screen \.day-tabs\s*\{[^}]*flex-wrap:\s*nowrap/s,
      );
      expect(dayTabsCss).toMatch(
        /\.prototype-trip-detail-screen \.day-tabs\s*\{[^}]*overflow-x:\s*auto/s,
      );
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("renders itinerary detail day tabs from trip data", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 4일 여행",
      dates: "2026.06.15 - 06.18",
      expectedSaving: "0원",
      linkedPolicies: undefined as unknown as Trip["linkedPolicies"],
      days: { 1: [], 2: [], 3: [], 4: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55");

      await waitFor(() =>
        expect(screen.getByText("Day 4")).toBeInTheDocument(),
      );
      expect(
        screen.queryByText("Travel Hunter itinerary"),
      ).not.toBeInTheDocument();
      expect(screen.getByText("🏝️")).toBeInTheDocument();
      expect(
        screen.queryByRole("link", { name: "친구 초대" }),
      ).not.toBeInTheDocument();
      /* 초대는 페이지 이동이 아니라 이 화면 위의 시트로 뜬다. */
      expect(
        screen.getAllByRole("button", { name: "+ 친구 초대" }),
      ).toHaveLength(1);
      expect(screen.queryByRole("dialog", { name: "친구 초대" })).toBeNull();
      expect(
        screen.getByRole("region", { name: "연결된 정책" }),
      ).toBeInTheDocument();
      expect(document.querySelector(".benefit-banner")).toHaveAttribute(
        "href",
        "/policies",
      );
      expect(
        screen.getByRole("region", { name: "이 일정에 어울리는 정책" }),
      ).toBeInTheDocument();
      await userEvent.setup().click(screen.getByText("Day 4"));
      expect(document.body).toHaveTextContent("아직 표시할 장소가 없어요");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows the friend invite entry for editor trip members", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      currentUserRole: "editor",
      title: "편집자 참여 일정",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57");

      await waitFor(() =>
        expect(screen.getAllByText("편집자 참여 일정").length).toBeGreaterThan(0),
      );
      expect(screen.getByRole("button", { name: "+ 친구 초대" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("opens the friend invite sheet on the trip screen instead of leaving for a page", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      currentUserRole: "editor",
      title: "초대 시트 일정",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    /* 한 번도 초대한 적 없는 일정이다. 링크가 아직 없다. */
    const emptyInvite = {
      id: "9",
      tripId: "57",
      inviteToken: "",
      inviteUrl: "",
      expiresAt: "2026-12-30T00:00:00Z",
      createdAt: "2026-09-10T00:00:00Z",
      acceptedAt: null,
      invited: false,
      copied: false,
      role: "editor" as const,
      alreadyMember: false,
    };
    const getInviteSpy = vi
      .spyOn(appDataApi, "getInviteState")
      .mockResolvedValue(emptyInvite);
    const confirmInviteSpy = vi
      .spyOn(appDataApi, "confirmInviteSent")
      .mockResolvedValue({
        ...emptyInvite,
        inviteToken: "sheet-token",
        inviteUrl: "http://127.0.0.1:5173/invites/sheet-token/accept",
        invited: true,
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(screen.getAllByText("초대 시트 일정").length).toBeGreaterThan(0),
      );
      await user.click(screen.getByRole("button", { name: "+ 친구 초대" }));

      const sheet = await screen.findByRole("dialog", { name: "친구 초대" });
      await waitFor(() => expect(getInviteSpy).toHaveBeenCalledWith("57"));
      /* 링크를 보려고 여는 시트다. "편집 링크 만들기"를 한 번 더 누르게 하지 않는다. */
      expect(
        await within(sheet).findByText(
          "http://127.0.0.1:5173/invites/sheet-token/accept",
        ),
      ).toBeInTheDocument();
      expect(confirmInviteSpy).toHaveBeenCalledWith("57");
      expect(confirmInviteSpy).toHaveBeenCalledTimes(1);
      // 자동 준비는 사용자가 누른 게 아니므로 안내 토스트를 띄우지 않는다.
      expect(within(sheet).queryByText("함께 편집 링크가 준비됐어요.")).toBeNull();
      // 일정 화면을 떠나지 않는다.
      expect(screen.getAllByText("초대 시트 일정").length).toBeGreaterThan(0);

      await user.click(within(sheet).getByRole("button", { name: "닫기" }));
      expect(screen.queryByRole("dialog", { name: "친구 초대" })).toBeNull();
    } finally {
      getTripSpy.mockRestore();
      getInviteSpy.mockRestore();
      confirmInviteSpy.mockRestore();
    }
  });

  it("hides the friend invite entry for viewer trip members", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      currentUserRole: "viewer",
      title: "뷰어 참여 일정",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/58");

      await waitFor(() =>
        expect(screen.getAllByText("뷰어 참여 일정").length).toBeGreaterThan(0),
      );
      expect(screen.queryByRole("button", { name: "+ 친구 초대" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("keeps saved places reorderable after recommendation preview completion", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "122",
      revision: 12,
      title: "저장 후 정렬 여행",
      days: {
        1: [
          { id: "saved-1", time: "09:00", label: "첫 장소", meta: "오전" },
          { id: "saved-2", time: "10:00", label: "둘째 장소", meta: "오전" },
        ],
        2: [
          { id: "saved-3", time: "11:00", label: "다른 날 장소", meta: "점심" },
        ],
      },
      currentUserRole: "owner",
    };
    const reorderedTrip: Trip = {
      ...trip,
      revision: 13,
      days: {
        1: [trip.days[1][1], trip.days[1][0]],
        2: trip.days[2],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockResolvedValue(reorderedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/122?day=1");

      const firstHandle = await screen.findByRole("button", {
        name: "첫 장소 순서 이동",
      });
      expect(firstHandle).toBeEnabled();
      expect(
        screen.getByRole("button", { name: "둘째 장소 순서 이동" }),
      ).toBeEnabled();

      firstHandle.focus();
      fireEvent.keyDown(firstHandle, { key: "ArrowDown" });

      await waitFor(() => expect(movePlaceSpy).toHaveBeenCalledTimes(1));
      expect(movePlaceSpy).toHaveBeenCalledWith(
        "122",
        "saved-1",
        expect.objectContaining({
          dayNumber: 1,
          position: 2,
          expectedRevision: 12,
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });

  it("marks saved places whose visit time is earlier than the previous place", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "130",
      revision: 3,
      title: "시간 확인 여행",
      days: {
        1: [
          { id: "time-a", time: "11:00", label: "늦은 장소", meta: "오전" },
          { id: "time-b", time: "10:00", label: "이른 장소", meta: "오전" },
          {
            id: "time-c",
            time: "10:00",
            label: "같은 시간 장소",
            meta: "오전",
          },
        ],
        2: [
          {
            id: "time-d",
            time: "09:00",
            label: "다른 Day 장소",
            meta: "오전",
          },
        ],
      },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/130?day=1");

      await waitFor(() =>
        expect(screen.getAllByText("시간 확인 여행").length).toBeGreaterThan(0),
      );
      expect(
        screen.getByRole("button", { name: "이른 장소 방문 시간 확인" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "늦은 장소 방문 시간 확인" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "같은 시간 장소 방문 시간 확인" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("opens the existing place editor when the time warning is clicked", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "131",
      revision: 4,
      title: "시간 수정 진입 여행",
      days: {
        1: [
          { id: "edit-a", time: "12:00", label: "점심 장소", meta: "식사" },
          { id: "edit-b", time: "11:00", label: "오전 장소", meta: "관광" },
        ],
        2: [],
      },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/131?day=1");

      fireEvent.click(
        await screen.findByRole("button", {
          name: "오전 장소 방문 시간 확인",
        }),
      );

      expect(
        await screen.findByRole("heading", { name: "장소 수정" }),
      ).toBeInTheDocument();
      expect(screen.getByText("방문 시간")).toBeInTheDocument();
      expect(screen.getByDisplayValue("오전 장소")).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("moves saved places across days by keyboard but hides reorder handles for viewers", async () => {
    const editorTrip: Trip = {
      ...getPreviewTrip(),
      id: "123",
      revision: 21,
      title: "저장 후 Day 이동 여행",
      days: {
        1: [
          { id: "saved-a", time: "09:00", label: "이동할 장소", meta: "오전" },
        ],
        2: [
          { id: "saved-b", time: "10:00", label: "도착 Day 장소", meta: "점심" },
        ],
      },
      currentUserRole: "editor",
    };
    const movedTrip: Trip = {
      ...editorTrip,
      revision: 22,
      days: {
        1: [],
        2: [editorTrip.days[2][0], editorTrip.days[1][0]],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(editorTrip);
    const movePlaceSpy = vi
      .spyOn(appDataApi, "moveTripPlace")
      .mockResolvedValue(movedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/123?day=1");

      const moveHandle = await screen.findByRole("button", {
        name: "이동할 장소 순서 이동",
      });
      fireEvent.keyDown(moveHandle, { key: "ArrowRight", shiftKey: true });

      await waitFor(() => expect(movePlaceSpy).toHaveBeenCalledTimes(1));
      expect(movePlaceSpy).toHaveBeenCalledWith(
        "123",
        "saved-a",
        expect.objectContaining({
          dayNumber: 2,
          position: 2,
          expectedRevision: 21,
        }),
      );

      movePlaceSpy.mockClear();
      getTripSpy.mockResolvedValueOnce({
        ...editorTrip,
        id: "124",
        currentUserRole: "viewer",
      });
      cleanup();
      renderAppRoute("/trips/124?day=1");

      await waitFor(() =>
        expect(
          screen.getAllByText("저장 후 Day 이동 여행").length,
        ).toBeGreaterThan(0),
      );
      expect(
        screen.queryByRole("button", { name: "이동할 장소 순서 이동" }),
      ).not.toBeInTheDocument();
      expect(movePlaceSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      movePlaceSpy.mockRestore();
    }
  });

  it("shows linked policies from the trip detail response", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "56",
      status: "draft",
      currentUserRole: "owner",
      title: "부산 정책 여행",
      linkedPolicies: [
        {
          slug: "busan-digital-nomad",
          title: "부산 워케이션 지원",
          amount: "최대 10만원",
          region: "부산",
        },
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "최대 30만원",
          region: "전국",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/56");

      await waitFor(() =>
        expect(screen.getByText("부산 워케이션 지원")).toBeInTheDocument(),
      );
      expect(screen.getByText(examplePolicyTitle)).toBeInTheDocument();
      expect(document.querySelectorAll(".benefit-banner")).toHaveLength(2);
      expect(getLink("/policies/busan-digital-nomad")).toBeInTheDocument();
      expect(getLink(examplePolicyPath)).toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: /연결 삭제/ })).toHaveLength(
        2,
      );
      expect(document.body).toHaveTextContent("최대 10만원 · 부산");
      expect(document.body).toHaveTextContent("최대 30만원 · 전국");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  function islandLinkedTrip(
    overrides: Partial<Trip> = {},
    application: Partial<NonNullable<LinkedTripPolicy["application"]>> = {},
  ): Trip {
    return {
      ...getPreviewTrip(),
      id: "201",
      status: "draft",
      currentUserRole: "owner",
      title: "가거도 섬 여행",
      linkedPolicies: [
        {
          slug: "travelmonth-81",
          title: "2026 섬 여행비 지원",
          amount: "최대 10만원",
          region: "전국",
          deadline: "2026-09-21",
          application: {
            status: "applied",
            roundKey: "2",
            checklist: [
              { key: "신분증", label: "신분증", checked: false },
              { key: "통장사본", label: "통장사본", checked: true },
            ],
            checks: {
              inTravelWindow: true,
              meetsMinNights: false,
              eligibleIslandMatched: false,
              applyDeadline: "2026-09-21T18:00",
              documentsDueDate: "2026-10-18",
            },
            updatedAt: "2026-09-19T00:00:00Z",
            updatedBy: "Minseo",
            ...application,
          },
        },
      ],
      days: { 1: [] },
      ...overrides,
    };
  }

  it("guides island support progress from the linked policy card for trip editors", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-15T09:00:00+09:00"));
    const trip = islandLinkedTrip();
    const base = trip.linkedPolicies[0].application!;
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPolicyApplication")
      .mockResolvedValueOnce({ ...base, status: "selected", updatedBy: "Test User" })
      .mockResolvedValueOnce({
        ...base,
        status: "selected",
        updatedBy: "Test User",
        checklist: [
          { key: "신분증", label: "신분증", checked: true },
          { key: "통장사본", label: "통장사본", checked: true },
        ],
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/201");

      const panel = await screen.findByRole("region", { name: "2026 섬 여행비 지원 신청 진행" });
      expect(within(panel).getByText("현재 단계 · 신청함")).toBeInTheDocument();
      expect(within(panel).getByText("✓ 일정이 이번 회차 여행 기간 안이에요")).toBeInTheDocument();
      expect(within(panel).getByText("⚠ 당일치기 일정은 지원 대상이 아니에요 (1박 이상)")).toBeInTheDocument();
      expect(
        within(panel).getByText("⚠ 일정에 대상 섬이 없어요 (장소 이름이 대상 섬 이름과 같아야 해요)"),
      ).toBeInTheDocument();
      expect(within(panel).getByText("서류 제출 D-3")).toHaveClass("tag", "warning");
      expect(within(panel).queryByText(/신청 마감/)).toBeNull(); // already applied
      expect(within(panel).getByText("마지막 변경 · Minseo")).toBeInTheDocument();
      // the progress panel is not a policy card: the linked card count stays one
      expect(document.querySelectorAll(".benefit-banner")).toHaveLength(1);

      const user = userEvent.setup();
      await user.click(within(panel).getByRole("button", { name: "선정됨" }));
      await waitFor(() =>
        expect(updateSpy).toHaveBeenCalledWith("201", "travelmonth-81", { status: "selected" }),
      );
      expect(await within(panel).findByText("현재 단계 · 선정됨")).toBeInTheDocument();
      expect(within(panel).getByRole("button", { name: "여행 완료로 표시" })).toBeInTheDocument();
      expect(within(panel).getByRole("button", { name: "이전 단계로" })).toBeInTheDocument();

      await user.click(within(panel).getByRole("checkbox", { name: "신분증" }));
      await waitFor(() =>
        expect(updateSpy).toHaveBeenLastCalledWith("201", "travelmonth-81", { checklist: { 신분증: true } }),
      );
      await waitFor(() => expect(within(panel).getByRole("checkbox", { name: "신분증" })).toBeChecked());
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
      vi.useRealTimers();
    }
  });

  it("shows island support progress read-only to trip viewers", async () => {
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValue(islandLinkedTrip({ currentUserRole: "viewer" }));
    const updateSpy = vi.spyOn(appDataApi, "updateTripPolicyApplication");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/201");

      const panel = await screen.findByRole("region", { name: "2026 섬 여행비 지원 신청 진행" });
      expect(within(panel).queryByRole("button", { name: "선정됨" })).toBeNull();
      expect(within(panel).queryByRole("button", { name: "이전 단계로" })).toBeNull();
      expect(within(panel).getByRole("checkbox", { name: "통장사본" })).toBeDisabled();
      expect(within(panel).getByRole("checkbox", { name: "통장사본" })).toBeChecked();
      expect(within(panel).getByText("보기 권한이라 진행 상태를 바꿀 수 없어요")).toBeInTheDocument();
      expect(updateSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("reloads the trip when someone else changed the island progress first", async () => {
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(islandLinkedTrip());
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPolicyApplication")
      .mockRejectedValue(
        new ApiError("Invalid application status transition", { status: 409, statusText: "Conflict" }),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/201");

      const panel = await screen.findByRole("region", { name: "2026 섬 여행비 지원 신청 진행" });
      const callsBefore = getTripSpy.mock.calls.length;
      await userEvent.setup().click(within(panel).getByRole("button", { name: "선정됨" }));

      expect(
        await screen.findByText("다른 사람이 먼저 진행 상태를 바꿨어요. 최신 상태를 다시 불러왔어요."),
      ).toBeInTheDocument();
      await waitFor(() => expect(getTripSpy.mock.calls.length).toBeGreaterThan(callsBefore));
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("removes a linked policy from a confirmed owner trip detail card", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "61",
      status: "confirmed",
      currentUserRole: "owner",
      title: "정책 삭제 여행",
      linkedPolicies: [
        {
          slug: examplePolicySlug,
          title: examplePolicyTitle,
          amount: "최대 30만원",
          region: "전국",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const removePolicySpy = vi
      .spyOn(appDataApi, "removePolicyFromTrip")
      .mockResolvedValue({
        tripId: "61",
        policyId: examplePolicySlug,
        added: false,
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/61");

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();

      await userEvent.setup().click(
        within(linkedRegion).getByRole("button", {
          name: `${examplePolicyTitle} 연결 삭제`,
        }),
      );

      await waitFor(() =>
        expect(removePolicySpy).toHaveBeenCalledWith("61", examplePolicySlug),
      );
      await waitFor(() =>
        expect(
          within(linkedRegion).queryByText(examplePolicyTitle),
        ).not.toBeInTheDocument(),
      );
      expect(
        within(linkedRegion).getByText("연결된 정책이 없어요"),
      ).toBeInTheDocument();
      expect(document.body).toHaveTextContent("정책 연결을 해제했어요.");
    } finally {
      getTripSpy.mockRestore();
      removePolicySpy.mockRestore();
    }
  });

  it("keeps a route-state linked policy hidden after removing it from trip detail", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "62",
      status: "draft",
      currentUserRole: "owner",
      title: "방금 연결한 정책 삭제 여행",
      linkedPolicies: [],
      days: { 1: [] },
    };
    const routePolicy: LinkedTripPolicy = {
      slug: examplePolicySlug,
      title: examplePolicyTitle,
      amount: "최대 30만원",
      region: "전국",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const removePolicySpy = vi
      .spyOn(appDataApi, "removePolicyFromTrip")
      .mockResolvedValue({
        tripId: "62",
        policyId: examplePolicySlug,
        added: false,
      });

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/62",
              state: { linkedPolicy: routePolicy },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정하기" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "확정취소" }),
      ).not.toBeInTheDocument();

      await userEvent.setup().click(
        within(linkedRegion).getByRole("button", {
          name: `${examplePolicyTitle} 연결 삭제`,
        }),
      );

      await waitFor(() =>
        expect(removePolicySpy).toHaveBeenCalledWith("62", examplePolicySlug),
      );
      await waitFor(() =>
        expect(
          within(linkedRegion).queryByText(examplePolicyTitle),
        ).not.toBeInTheDocument(),
      );
      expect(
        within(linkedRegion).getByText("연결된 정책이 없어요"),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      removePolicySpy.mockRestore();
    }
  });

  it("links trip detail recommended policy cards to policy detail pages", async () => {
    const recommendedPolicies: LinkedTripPolicy[] = [
      {
        slug: "busan-card-cashback",
        title: "부산 카드 캐시백",
        amount: "카드 결제 5% 캐시백",
        region: "부산",
      },
      {
        slug: "busan-stay-coupon",
        title: "부산 숙박 쿠폰",
        amount: "숙박비 3만원",
        region: "부산",
      },
      {
        slug: "busan-food-pass",
        title: "부산 미식 패스",
        amount: "식사권 할인",
        region: "부산",
      },
    ];
    const trip: Trip & { recommendedPolicies: LinkedTripPolicy[] } = {
      ...getPreviewTrip(),
      id: "59",
      title: "부산 추천 여행",
      linkedPolicies: [],
      recommendedPolicies,
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/59");

      const recommendedRegion = await screen.findByRole("region", {
        name: "이 일정에 어울리는 정책",
      });
      expect(
        within(recommendedRegion).getByRole("link", {
          name: /부산 카드 캐시백/,
        }),
      ).toHaveAttribute("href", "/policies/busan-card-cashback");
      expect(
        within(recommendedRegion).getByRole("link", { name: /부산 숙박 쿠폰/ }),
      ).toHaveAttribute("href", "/policies/busan-stay-coupon");
      expect(
        within(recommendedRegion).getByRole("link", { name: /부산 미식 패스/ }),
      ).toHaveAttribute("href", "/policies/busan-food-pass");
      expect(
        within(recommendedRegion).getByText("카드 결제 5% 캐시백"),
      ).toBeInTheDocument();
      expect(
        within(recommendedRegion).queryByText("KTX 청년 여행 할인"),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("uses a region empty state instead of the generic policy-list card when no recommended policy exists", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "60",
      title: "부산 추천 대기 여행",
      linkedPolicies: [],
      recommendedPolicies: [],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/60");

      const recommendedRegion = await screen.findByRole("region", {
        name: "이 일정에 어울리는 정책",
      });
      expect(
        within(recommendedRegion).queryByText(
          "이 일정에 맞는 정책을 더 찾아보세요",
        ),
      ).not.toBeInTheDocument();
      expect(
        within(recommendedRegion).getByText("이 일정에 어울리는 정책이 없어요"),
      ).toBeInTheDocument();
      expect(
        within(recommendedRegion).getByText("정책 확인"),
      ).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("puts the just-attached policy first when the trip already has linked policies", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      title: "부산 야호",
      expectedSaving: "30만원",
      linkedPolicies: [
        {
          slug: "busan-card-cashback",
          title: "부산 카드 캐시백",
          amount: "카드 결제 5% 캐시백",
          region: "부산",
        },
      ],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/58",
              state: {
                linkedPolicy: {
                  slug: examplePolicySlug,
                  title: examplePolicyTitle,
                  amount: "최대 30만원",
                  region: "전국",
                },
              },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      expect(
        within(linkedRegion).getByText(examplePolicyTitle),
      ).toBeInTheDocument();
      expect(
        within(linkedRegion).getByText("부산 카드 캐시백"),
      ).toBeInTheDocument();
      const banners = document.querySelectorAll(".benefit-banner");
      expect(banners).toHaveLength(2);
      const links = linkedRegion.querySelectorAll(".linked-policy-card-main");
      expect(decodeURIComponent(links[0].getAttribute("href") ?? "")).toBe(
        decodeURIComponent(examplePolicyPath),
      );
      expect(links[1]).toHaveAttribute("href", "/policies/busan-card-cashback");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("keeps the just-attached policy visible when trip detail response is stale", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      title: "부산 야호",
      expectedSaving: "30만원",
      linkedPolicies: undefined as unknown as Trip["linkedPolicies"],
      days: { 1: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/trips/57",
              state: {
                linkedPolicy: {
                  slug: examplePolicySlug,
                  title: examplePolicyTitle,
                  amount: "최대 30만원",
                  region: "전국",
                },
              },
            },
          ]}
        >
          <AppProviders>
            <App />
          </AppProviders>
        </MemoryRouter>,
      );

      await waitFor(() =>
        expect(screen.getByText(examplePolicyTitle)).toBeInTheDocument(),
      );
      expect(
        decodeURIComponent(
          document
            .querySelector(".linked-policy-card-main")
            ?.getAttribute("href") ?? "",
        ),
      ).toBe(decodeURIComponent(examplePolicyPath));
      expect(document.body).toHaveTextContent("최대 30만원 · 전국");
      expect(
        screen.queryByText("연결된 정책이 없어요"),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows trip detail as a map-first itinerary without list/map tabs", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          { id: "1", time: "09:00", label: "성산 일출봉", meta: "자연·관광지" },
          { id: "2", time: "12:30", label: "해녀의 집", meta: "맛집·한식" },
        ],
        2: [{ id: "3", time: "10:00", label: "한림공원", meta: "자연·관광지" }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&place=1");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(screen.getByLabelText("Day 1 지도")).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("tablist", { name: /일정 표시 방식/ }),
      ).not.toBeInTheDocument();
      expect(document.querySelector("[data-kakao-map-view]")).toBeTruthy();
      expect(screen.getAllByText("성산 일출봉").length).toBeGreaterThan(0);
      expect(
        screen.getByRole("button", { name: "1번 장소: 성산 일출봉" }),
      ).toBeInTheDocument();
      expect(screen.queryByText("장소 카드의 이동 핸들로 순서를 조정할 수 있어요")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Day 2/ })).toBeInTheDocument();
      expect(
        screen.getByRole("dialog", { name: "성산 일출봉 지도 상세" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /길찾기/ })).toHaveAttribute(
        "href",
        "https://map.kakao.com/link/search/%EC%84%B1%EC%82%B0%20%EC%9D%BC%EC%B6%9C%EB%B4%89",
      );

      await user.click(
        screen.getByRole("button", { name: "2번 장소: 해녀의 집" }),
      );
      expect(
        screen.getByRole("dialog", { name: "해녀의 집 지도 상세" }),
      ).toBeInTheDocument();

      await user.click(screen.getByText("Day 2"));
      await waitFor(() =>
        expect(screen.getByLabelText("Day 2 지도")).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("dialog", { name: "해녀의 집 지도 상세" }),
      ).not.toBeInTheDocument();
      expect(screen.getAllByText("한림공원").length).toBeGreaterThan(0);
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("opens an inspectable place detail dialog from the map bottom sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "제주 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "성산 일출봉",
            meta: "일출 보기 좋은 자연 명소",
            address: "제주 서귀포시 성산읍 성산리 1",
            latitude: 33.458,
            longitude: 126.942,
            category: "관광명소",
            categoryCode: "AT4",
            placeUrl: "https://place.map.kakao.com/123",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map&place=1");
      const user = userEvent.setup();

      await screen.findByRole("dialog", { name: "성산 일출봉 지도 상세" });
      await user.click(screen.getByRole("button", { name: "상세 보기" }));

      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      expect(within(sheet).getByText("제주 서귀포시 성산읍 성산리 1")).toBeInTheDocument();
      expect(within(sheet).getByText("33.458, 126.942")).toBeInTheDocument();
      expect(within(sheet).getByText("관광명소")).toBeInTheDocument();
      expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute(
        "href",
        "https://place.map.kakao.com/123",
      );
      expect(within(sheet).getByDisplayValue("성산 일출봉")).toBeInTheDocument();

      await user.click(within(sheet).getByRole("button", { name: "닫기" }));
      expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("opens a read-only place sheet for viewers", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "56",
      currentUserRole: "viewer",
      days: { 1: [{ id: "1", time: "09:00", label: "성산 일출봉", meta: "메모", address: "제주 성산읍" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/56?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "성산 일출봉 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 상세" });
      expect(within(sheet).getByText("제주 성산읍")).toBeInTheDocument();
      expect(within(sheet).queryByRole("button", { name: "저장하기" })).not.toBeInTheDocument();
      expect(within(sheet).queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
      expect(within(sheet).getByDisplayValue("성산 일출봉")).toBeDisabled();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("renders a trip detail coordinate-less Kakao map through the shared query fallback", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const expectedQuery = "부산 중구 자갈치해안로 52";
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "부산 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          {
            id: "missing-coordinate-place",
            time: "10:00",
            label: "자갈치시장",
            meta: "시장·맛집",
            address: expectedQuery,
            latitude: null,
            longitude: null,
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map");

      await waitFor(() =>
        expect(kakao.addressSearch).toHaveBeenCalledWith(
          expectedQuery,
          expect.any(Function),
        ),
      );
      await waitFor(() =>
        expect(kakao.keywordSearch).toHaveBeenCalledWith(
          expectedQuery,
          expect.any(Function),
        ),
      );
      expect(kakao.addressQueries).toEqual([expectedQuery]);
      expect(kakao.keywordQueries).toEqual([expectedQuery]);
      expect(kakao.addressSearch.mock.invocationCallOrder[0]).toBeLessThan(
        kakao.keywordSearch.mock.invocationCallOrder[0],
      );
      await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
      expect(kakao.markerInstances).toHaveLength(1);
      expect(kakao.customOverlayInstances).toHaveLength(1);
      expect(kakao.customOverlayInstances[0].options.content).toHaveTextContent(
        "자갈치시장",
      );
      expect(
        screen.queryByRole("button", { name: "1번 장소: 자갈치시장" }),
      ).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      vi.unstubAllEnvs();
      delete window.kakao;
    }
  });

  it("uses stored Kakao place URL and address in the trip map detail sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      days: {
        1: [
          {
            id: "1",
            time: "13:00",
            label: "Kakao food place",
            meta: "Food · Busan",
            address: "Busan road 1",
            latitude: 35.1,
            longitude: 129.1,
            category: "Food",
            categoryCode: "FD6",
            placeUrl: "http://place.map.kakao.com/12345",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map&place=1");

      await waitFor(() =>
        expect(
          screen.getByRole("dialog", { name: "Kakao food place 지도 상세" }),
        ).toBeInTheDocument(),
      );
      expect(screen.getByText("Busan road 1")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /길찾기/ })).toHaveAttribute(
        "href",
        "http://place.map.kakao.com/12345",
      );
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows empty trip detail with policy actions, day tabs, map, and no itinerary list", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "101",
      title: "제주 3일 여행",
      days: { 1: [], 2: [], 3: [] },
      linkedPolicies: [],
      recommendedPolicies: [
        { slug: examplePolicySlug, title: examplePolicyTitle, amount: "최대 20만원", region: "전남" },
      ],
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/101");

      await waitFor(() => expect(screen.getAllByText("제주 3일 여행").length).toBeGreaterThan(0));
      expect(screen.getByRole("button", { name: /장소 추가/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /추천 일정만들기/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Day 1/ })).toBeInTheDocument();
      expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
      expect(screen.queryByText("Day 1 일정")).not.toBeInTheDocument();
      expect(screen.queryByRole("tablist", { name: /일정 표시 방식/ })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("places trip edit actions between the map and day selector", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "103",
      title: "지도 아래 액션 여행",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/103");

      await waitFor(() => expect(screen.getAllByText("지도 아래 액션 여행").length).toBeGreaterThan(0));
      const mapPanel = document.querySelector(".prototype-map-wrap");
      const editActions = screen.getByRole("region", { name: "일정 편집 작업" });
      const daySelector = screen.getByLabelText("일정 날짜 선택");

      expect(mapPanel).not.toBeNull();
      expect((mapPanel as HTMLElement).compareDocumentPosition(editActions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(editActions.compareDocumentPosition(daySelector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("keeps the add-sheet search-only before a place selection", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "125",
      title: "검색 전용 장소 추가 여행",
      days: { 1: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([]);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/125");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: /장소 추가/ }));

      expect(screen.getByLabelText("장소 검색")).toBeInTheDocument();
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();

      await user.type(screen.getByLabelText("장소 검색"), "등록되지 않은 장소");

      await waitFor(() =>
        expect(searchTripPlacesSpy).toHaveBeenCalledWith(
          "125",
          { query: "등록되지 않은 장소" },
          { signal: expect.any(AbortSignal) },
        ),
      );
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
    }
  });

  it("debounces a rapid place search to one final request", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "126",
      title: "장소 검색 디바운스 여행",
      days: { 1: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([]);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/126");
      await screen.findByRole("button", { name: /장소 추가/ });
      await userEvent.click(screen.getByRole("button", { name: /장소 추가/ }));

      vi.useFakeTimers();
      const searchInput = screen.getByLabelText("장소 검색");
      fireEvent.change(searchInput, { target: { value: "성" } });
      fireEvent.change(searchInput, { target: { value: "성산" } });
      fireEvent.change(searchInput, { target: { value: "성산일" } });
      fireEvent.change(searchInput, { target: { value: "성산일출" } });
      fireEvent.change(searchInput, { target: { value: "성산일출봉" } });

      expect(searchTripPlacesSpy).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(349);
      expect(searchTripPlacesSpy).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(1);
      expect(searchTripPlacesSpy).toHaveBeenCalledTimes(1);
      expect(searchTripPlacesSpy).toHaveBeenLastCalledWith(
        "126",
        { query: "성산일출봉" },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    } finally {
      vi.useRealTimers();
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
    }
  });

  it("aborts an in-flight place search when the query changes", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "127",
      title: "장소 검색 취소 여행",
      days: { 1: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    let firstSignal: AbortSignal | undefined;
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation((_tripId, _options, control) => {
        firstSignal = control?.signal;
        return new Promise((_, reject) => {
          control?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/127");
      await screen.findByRole("button", { name: /장소 추가/ });
      await userEvent.click(screen.getByRole("button", { name: /장소 추가/ }));

      vi.useFakeTimers();
      const searchInput = screen.getByLabelText("장소 검색");
      fireEvent.change(searchInput, { target: { value: "성산" } });
      await vi.advanceTimersByTimeAsync(350);
      expect(firstSignal?.aborted).toBe(false);

      fireEvent.change(searchInput, { target: { value: "동문시장" } });
      expect(firstSignal?.aborted).toBe(true);
      expect(
        screen.queryByText("장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요."),
      ).toBeNull();
    } finally {
      vi.useRealTimers();
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
    }
  });

  it("keeps selected place search candidates in an add-sheet place basket", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "126",
      title: "장소 바구니 여행",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("성산")) {
          return [
            {
              id: "search-a",
              label: "성산일출봉",
              title: "성산일출봉",
              meta: "제주 서귀포시",
              address: "제주 서귀포시 성산읍",
              categoryCode: "AT4",
              categoryName: "관광명소",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-a",
            },
          ];
        }
        if (request.query.includes("시장")) {
          return [
            {
              id: "search-b",
              label: "동문시장",
              title: "동문시장",
              meta: "제주 제주시",
              address: "제주 제주시 관덕로",
              categoryCode: "FD6",
              categoryName: "음식점",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-b",
            },
          ];
        }
        return [];
      });
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/126");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: /장소 추가/ }));
      const searchInput = screen.getByLabelText("장소 검색");
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
      expect(searchInput).toHaveValue("");
      expect(screen.queryByRole("button", { name: "성산일출봉 선택" })).not.toBeInTheDocument();
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 1개");
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("관광명소");
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("제주 서귀포시 성산읍");
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "1개 저장하기" })).toBeInTheDocument();

      await user.type(searchInput, "시장");
      await user.click(await screen.findByRole("button", { name: "동문시장 선택" }));
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      const basket = screen.getByRole("region", { name: "추가할 장소 목록" });
      expect(basket).toHaveTextContent("추가할 장소 3개");
      expect(within(basket).getAllByText("성산일출봉")).toHaveLength(2);
      expect(within(basket).getByText("동문시장")).toBeInTheDocument();

      const removeButton = within(basket).getAllByRole("button", { name: "성산일출봉 제거" })[0];
      expect(removeButton).toHaveTextContent(/^제거$/);
      await user.click(removeButton);

      expect(basket).toHaveTextContent("추가할 장소 2개");
      expect(within(basket).getAllByText("성산일출봉")).toHaveLength(1);
      expect(screen.getByRole("button", { name: "2개 저장하기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "2개 저장하기" }));

      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("saves an add-sheet place basket with one batch request and closes the sheet", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "127",
      revision: 7,
      title: "Batch place trip",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const savedTrip: Trip = {
      ...trip,
      revision: 8,
      days: {
        1: [
          { id: "saved-a", time: "", label: "Alpha cafe", meta: "Cafe" },
          { id: "saved-b", time: "", label: "Beta park", meta: "Park" },
        ],
        2: [],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("Alpha")) {
          return [
            {
              id: "alpha",
              label: "Alpha cafe",
              title: "Alpha cafe",
              meta: "Cafe",
              address: "Alpha address",
              categoryCode: "CE7",
              categoryName: "Cafe",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-alpha",
            },
          ];
        }
        if (request.query.includes("Beta")) {
          return [
            {
              id: "beta",
              label: "Beta park",
              title: "Beta park",
              meta: "Park",
              address: "Beta address",
              categoryCode: "AT4",
              categoryName: "Park",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-beta",
            },
          ];
        }
        return [];
      });
    const addPlacesSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockResolvedValue(savedTrip);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/127");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.querySelector(".prototype-trip-action-add")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".prototype-trip-action-add")!);
      const searchInput = document.querySelector<HTMLInputElement>(
        'input[name="place-search"]',
      )!;
      await user.type(searchInput, "Alpha");
      await waitFor(() =>
        expect(document.querySelector(".place-search-results button")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.type(searchInput, "Beta");
      await waitFor(() =>
        expect(document.querySelector(".place-search-results button")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.click(screen.getByRole("button", { name: /2개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(addPlacesSpy).toHaveBeenCalledWith("127", 1, {
        expectedRevision: 7,
        places: [
          {
            time: "",
            label: "Alpha cafe",
            meta: "Cafe",
            address: "Alpha address",
            latitude: null,
            longitude: null,
            category: "Cafe",
            categoryCode: "CE7",
            placeUrl: null,
            sourceProvider: "kakao",
            externalPlaceId: "kakao-alpha",
          },
          {
            time: "",
            label: "Beta park",
            meta: "Park",
            address: "Beta address",
            latitude: null,
            longitude: null,
            category: "Park",
            categoryCode: "AT4",
            placeUrl: null,
            sourceProvider: "kakao",
            externalPlaceId: "kakao-beta",
          },
        ],
      });
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "장소 추가" })).not.toBeInTheDocument(),
      );
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("keeps a place basket after a batch conflict and waits for explicit retry", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "128",
      revision: 3,
      title: "Batch conflict trip",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const latestTrip: Trip = { ...trip, revision: 4 };
    const savedTrip: Trip = {
      ...latestTrip,
      revision: 5,
      days: { 1: [{ id: "saved-gamma", time: "", label: "Gamma beach", meta: "Beach" }], 2: [] },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockResolvedValueOnce(latestTrip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([
        {
          id: "gamma",
          label: "Gamma beach",
          title: "Gamma beach",
          meta: "Beach",
        },
      ]);
    const addPlacesSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValueOnce(new ApiError("conflict", { status: 409, statusText: "Conflict" }))
      .mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/128");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.querySelector(".prototype-trip-action-add")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".prototype-trip-action-add")!);
      const searchInput = document.querySelector<HTMLInputElement>(
        'input[name="place-search"]',
      )!;
      await user.type(searchInput, "Gamma");
      await waitFor(() =>
        expect(document.querySelector(".place-search-results button")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.click(screen.getByRole("button", { name: /1개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      await waitFor(() =>
        expect(screen.getByRole("dialog")).toHaveTextContent("Gamma beach"),
      );
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("Gamma beach");
      await new Promise((resolve) => window.setTimeout(resolve, 20));
      expect(addPlacesSpy).toHaveBeenCalledTimes(1);

      await user.click(screen.getByRole("button", { name: /1개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(2));
      expect(addPlacesSpy).toHaveBeenLastCalledWith(
        "128",
        1,
        expect.objectContaining({ expectedRevision: 4 }),
      );
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });

  it("lets a user choose a current Day before retrying a missing Day batch save", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "129",
      revision: 10,
      title: "Missing day batch trip",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const latestTrip: Trip = {
      ...trip,
      revision: 11,
      days: { 1: [], 2: [] },
    };
    const savedTrip: Trip = {
      ...latestTrip,
      revision: 12,
      days: { 1: [], 2: [{ id: "saved-delta", time: "", label: "Delta museum", meta: "Museum" }] },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockResolvedValueOnce(latestTrip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([
        {
          id: "delta",
          label: "Delta museum",
          title: "Delta museum",
          meta: "Museum",
        },
      ]);
    const addPlacesSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValueOnce(
        new ApiError("Trip day not found", {
          status: 404,
          statusText: "Not Found",
          detail: "Trip day not found",
        }),
      )
      .mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/129?day=3");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.querySelector(".prototype-trip-action-add")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".prototype-trip-action-add")!);
      const searchInput = document.querySelector<HTMLInputElement>(
        'input[name="place-search"]',
      )!;
      await user.type(searchInput, "Delta");
      await waitFor(() =>
        expect(document.querySelector(".place-search-results button")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.click(screen.getByRole("button", { name: /1개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      expect(addPlacesSpy).toHaveBeenLastCalledWith("129", 3, expect.any(Object));
      const recovery = await screen.findByRole("region", {
        name: "batch place missing day recovery",
      });
      expect(within(recovery).getByRole("button", { name: /Day 1/ })).toBeInTheDocument();
      expect(within(recovery).getByRole("button", { name: /Day 2/ })).toBeInTheDocument();
      expect(within(recovery).queryByRole("button", { name: /Day 3/ })).not.toBeInTheDocument();
      expect(addPlacesSpy).toHaveBeenCalledTimes(1);

      await user.click(within(recovery).getByRole("button", { name: /Day 2/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(2));
      expect(addPlacesSpy).toHaveBeenLastCalledWith(
        "129",
        2,
        expect.objectContaining({ expectedRevision: 11 }),
      );
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });

  it("does not offer stale Day recovery when refreshing after a missing Day batch failure fails", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "129-refresh-failure",
      revision: 10,
      title: "Missing day refresh failure trip",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockRejectedValueOnce(new ApiError("Trip not found", {
        status: 404,
        statusText: "Not Found",
        detail: "Trip not found",
      }));
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([
        {
          id: "delta-refresh-failure",
          label: "Delta museum",
          title: "Delta museum",
          meta: "Museum",
        },
      ]);
    const addPlacesSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValueOnce(
        new ApiError("Trip day not found", {
          status: 404,
          statusText: "Not Found",
          detail: "Trip day not found",
        }),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/129-refresh-failure?day=3");
      const user = userEvent.setup();

      await user.click(
        await screen.findByRole("button", { name: /장소 추가/ }),
      );
      const searchInput = screen.getByRole("textbox", { name: "장소 검색" });
      await user.type(searchInput, "Delta");
      await user.click(
        await screen.findByRole("button", { name: "Delta museum 선택" }),
      );
      await user.click(screen.getByRole("button", { name: /1개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledTimes(2));
      expect(
        screen.queryByRole("region", { name: "batch place missing day recovery" }),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent(
        "Delta museum",
      );
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });

  it("does not show missing Day recovery for a generic trip 404 batch failure", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "130",
      revision: 12,
      title: "Generic batch 404 trip",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValue([
        {
          id: "epsilon",
          label: "Epsilon market",
          title: "Epsilon market",
          meta: "Market",
        },
      ]);
    const addPlacesSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValue(
        new ApiError("Trip not found", {
          status: 404,
          statusText: "Not Found",
          detail: "Trip not found",
        }),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/130");
      const user = userEvent.setup();

      await waitFor(() =>
        expect(document.querySelector(".prototype-trip-action-add")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".prototype-trip-action-add")!);
      const searchInput = document.querySelector<HTMLInputElement>(
        'input[name="place-search"]',
      )!;
      await user.type(searchInput, "Epsilon");
      await waitFor(() =>
        expect(document.querySelector(".place-search-results button")).toBeInTheDocument(),
      );
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.click(screen.getByRole("button", { name: /1개 저장하기/ }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      expect(
        screen.queryByRole("region", { name: "batch place missing day recovery" }),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent(
        "Epsilon market",
      );
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });

  it("links to the trip edit page from the detail hero", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "104",
      title: "Editable trip",
      dates: "2026.06.15 - 06.17",
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/104");

      const editLink = await screen.findByRole("link", { name: "일정 편집" });
      const hero = editLink.closest(".prototype-trip-detail-hero");
      const title = hero?.querySelector(".prototype-trip-hero-copy h1");
      expect(editLink).toHaveAttribute("href", "/trips/104/edit");
      expect(hero).not.toBeNull();
      expect(editLink.parentElement).toBe(hero);
      expect(title).toHaveTextContent("Editable trip");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows unsaved recommendation preview cards in the timeline before save", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "102",
      revision: 4,
      title: "추천 미리보기 여행",
      days: { 1: [{ id: "existing-p1", time: "09:00", label: "기존 장소", meta: "제주 제주시" }], 2: [] },
    };
    const savedTrip: Trip = {
      ...trip,
      revision: 5,
      days: { 1: [trip.days[1][0], { id: "p1", time: "10:00", label: "성산일출봉", meta: "제주 서귀포시" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/102?day=1&place=stale-saved-place");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "추천 후보 편집" })).not.toBeInTheDocument();
      expect(screen.getAllByText("성산일출봉").length).toBeGreaterThan(0);
      expect(screen.getByText("추천 후보")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 제외" })).toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("성산일출봉 메모")).not.toBeInTheDocument();
      expect(screen.getAllByText("10:00").length).toBeGreaterThan(0);
      const candidateMeta = document.querySelector(".recommendation-preview-meta");
      expect(candidateMeta).toHaveTextContent("10:00");
      expect(candidateMeta).toHaveTextContent("추천 후보");
      expect(candidateMeta).toHaveTextContent("오전 일정");
      expect(candidateMeta?.querySelector(".preview-candidate-index")).toHaveTextContent("추천 후보");
      expect(candidateMeta?.querySelector(".preview-phase-label")).toHaveTextContent("오전 일정");
      expect(document.querySelector('[aria-label="기존 장소 시간 수정"]')).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "1번 장소: 기존 장소" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "1번 장소: 성산일출봉" })).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: "성산일출봉 지도에서 보기" }));

      expect(screen.getByRole("button", { name: "1번 장소: 성산일출봉" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "1번 장소: 기존 장소" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "2번 장소: 성산일출봉" })).not.toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "성산일출봉 지도 상세" })).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: /Day 2/ }));
      expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /Day 1/ }));
      expect(screen.queryByRole("button", { name: "1번 장소: 성산일출봉" })).not.toBeInTheDocument();

      screen.getByRole("button", { name: "성산일출봉 지도에서 보기" }).focus();
      await user.keyboard("{Enter}");
      expect(screen.getByRole("button", { name: "1번 장소: 성산일출봉" })).toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: "성산일출봉 후보 저장" }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toHaveTextContent("저장됨");
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("102", 1, expect.objectContaining({ label: "성산일출봉", time: "10:00", meta: "관광명소", category: "관광명소", categoryCode: "AT4", expectedRevision: 4 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      await waitFor(() => expect(screen.queryByRole("button", { name: "성산일출봉 후보 저장" })).not.toBeInTheDocument());
      expect(screen.queryByText("추천 후보")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("persists existing place time edits on completion even without selected candidates", async () => {
    const existingPlace = { id: "existing-time-1", time: "09:00", label: "기존 장소", meta: "제주 제주시" };
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "121",
      revision: 8,
      title: "기존 시간 수정 여행",
      days: { 1: [existingPlace], 2: [] },
    };
    const updatedTrip: Trip = {
      ...trip,
      revision: 9,
      days: { 1: [{ ...existingPlace, time: "10:00" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ]);
    const updatePlaceSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue(updatedTrip);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(updatedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/121");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      await screen.findByRole("button", { name: "1번 장소: 기존 장소" });
      const existingTimeEdit = document.querySelectorAll(".preview-time-edit")[0] as HTMLElement;
      await user.click(within(existingTimeEdit).getByText("수정"));
      await user.click(within(existingTimeEdit).getByRole("button", { name: "방문 시간 1시간 증가" }));
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(updatePlaceSpy).toHaveBeenCalledTimes(1));
      expect(updatePlaceSpy).toHaveBeenCalledWith("121", "existing-time-1", expect.objectContaining({ time: "10:00", expectedRevision: 8 }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      expect(screen.queryByText("추천 후보")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      updatePlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("assigns category-based times to recommendation preview cards", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "112", revision: 1, title: "추천 시간 여행", days: { 1: [], 2: [] } };
    const recommendations: Recommendation[] = [
      { id: "attraction-1", title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "attraction-2", title: "한라산", label: "⛰️", meta: "제주", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "food-1", title: "해녀의 집", label: "🍽️", meta: "해산물", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "cafe-1", title: "오션 카페", label: "☕", meta: "디저트", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "stay-1", title: "제주 숙소", label: "🏨", meta: "숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "explicit-1", title: "노을 산책", label: "🌅", meta: "18:30 노을 명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/112");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect((await screen.findAllByText("성산일출봉")).length).toBeGreaterThan(0);
      expect(screen.getAllByText("10:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("11:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("12:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("15:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("17:00").length).toBeGreaterThan(0);
      expect(screen.getAllByText("18:30").length).toBeGreaterThan(0);
      expect(screen.getAllByText("오전 일정").length).toBeGreaterThan(0);
      expect(screen.getByText("점심")).toBeInTheDocument();
      expect(screen.getAllByText("카페").length).toBeGreaterThan(0);
      expect(screen.getAllByText("숙소").length).toBeGreaterThan(0);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("orders recommendation preview cards by assigned visit time without moving saved places", async () => {
    const existingPlace = { id: "existing-ordered", time: "09:00", label: "기존 장소", meta: "기존 동선" };
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "113",
      revision: 1,
      title: "추천 정렬 여행",
      days: { 1: [existingPlace], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "lunch", title: "점심 식당", label: "🍽️", meta: "12:00 음식점", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "early-cafe", title: "이른 카페", label: "☕", meta: "13:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "stay", title: "숙소 체크인", label: "🏨", meta: "17:00 숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "walk", title: "오후 산책", label: "🌳", meta: "14:00 관광명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
      { id: "late-cafe", title: "오후 카페", label: "☕", meta: "15:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/113");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "1번 장소: 기존 장소" })).toBeInTheDocument();
      expect(screen.getAllByText("기존 장소").length).toBeGreaterThan(0);
      const previewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) => button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""));
      expect(previewOrder).toEqual(["점심 식당", "이른 카페", "오후 산책", "오후 카페", "숙소 체크인"]);
      expect(screen.getByText("오후 일정")).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("orders same-time recommendation preview cards by category before original response order", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "114", revision: 1, title: "추천 동시간 여행", days: { 1: [], 2: [] } };
    const recommendations: Recommendation[] = [
      { id: "stay-same", title: "동시간 숙소", label: "🏨", meta: "13:00 숙소", reason: "추천", categoryCode: "AD5", categoryName: "숙박", suggestedDay: 1 },
      { id: "cafe-same", title: "동시간 카페", label: "☕", meta: "13:00 카페", reason: "추천", categoryCode: "CE7", categoryName: "카페", suggestedDay: 1 },
      { id: "food-same", title: "동시간 식당", label: "🍽️", meta: "13:00 음식점", reason: "추천", categoryCode: "FD6", categoryName: "음식점", suggestedDay: 1 },
      { id: "attraction-same", title: "동시간 명소", label: "📍", meta: "13:00 관광명소", reason: "추천", categoryCode: "AT4", categoryName: "관광명소", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/114");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      expect((await screen.findAllByText("동시간 명소")).length).toBeGreaterThan(0);
      const previewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) => button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""));
      expect(previewOrder).toEqual(["동시간 명소", "동시간 식당", "동시간 카페", "동시간 숙소"]);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("cancels recommendation preview cards before saving", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "103", revision: 7, title: "추천 삭제 여행", days: { 1: [], 2: [] } };
    const savedTrip: Trip = {
      ...trip,
      revision: 8,
      days: { 1: [{ id: "p2", time: "10:00", label: "협재해변", meta: "바다" }], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "r1", title: "성산일출봉", label: "⛰️", meta: "산", reason: "추천", suggestedDay: 1 },
      { id: "r2", title: "협재해변", label: "🌊", meta: "바다", reason: "추천", suggestedDay: 1 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/103");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("성산일출봉").length).toBeGreaterThan(0);
      expect(screen.getAllByText("협재해변").length).toBeGreaterThan(0);
      expect(screen.getAllByText("추천 후보")).toHaveLength(2);
      expect(screen.getByRole("button", { name: "성산일출봉 후보 저장" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "협재해변 후보 제외" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "성산일출봉 후보 제외" }));

      expect(screen.queryByText("성산일출봉")).not.toBeInTheDocument();
      expect(screen.getAllByText("협재해변").length).toBeGreaterThan(0);

      await user.click(screen.getByRole("button", { name: "미리보기 취소" }));

      expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument();
      expect(addPlaceSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("appends preview candidates to the target day when moved by keyboard", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "125",
      revision: 1,
      title: "키보드 후보 이동 여행",
      days: { 1: [], 2: [] },
    };
    const recommendations: Recommendation[] = [
      { id: "move", title: "옮길 후보", label: "📍", meta: "이동", reason: "추천", suggestedDay: 1 },
      { id: "target-a", title: "도착 후보 A", label: "📍", meta: "도착", reason: "추천", suggestedDay: 2 },
      { id: "target-b", title: "도착 후보 B", label: "📍", meta: "도착", reason: "추천", suggestedDay: 2 },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi
      .spyOn(appDataApi, "listRecommendations")
      .mockResolvedValue(recommendations);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/125?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

      const moveHandle = await screen.findByRole("button", {
        name: "옮길 후보 순서 이동",
      });
      fireEvent.keyDown(moveHandle, { key: "ArrowRight", shiftKey: true });

      await waitFor(() =>
        expect(screen.getByRole("button", { name: /Day 2/ })).toHaveClass(
          "active",
        ),
      );
      const dayTwoPreviewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) =>
          button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""),
        );
      expect(dayTwoPreviewOrder).toEqual([
        "도착 후보 A",
        "도착 후보 B",
        "옮길 후보",
      ]);
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
    }
  });

  it("adds an individual recommendation preview candidate while preserving existing places", async () => {
    const existingPlace = { id: "old-1", time: "09:00", label: "이미 저장된 장소", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "104", revision: 10, title: "부분 추가 여행", days: { 1: [existingPlace], 2: [] } };
    const savedTrip: Trip = {
      ...trip,
      revision: 11,
      days: { 1: [existingPlace, { id: "new-1", time: "09:00", label: "오설록", meta: "차" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "tea", title: "오설록", label: "☕", meta: "차", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/104");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("button", { name: /기존 유지하고 추가|추천 일정 추가하기|이 일정으로 저장|추천으로 대체/ })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "미리보기 취소" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "전체 저장" })).toBeInTheDocument();

      await user.click(await screen.findByRole("button", { name: "오설록 후보 저장" }));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "오설록 후보 저장" })).toHaveTextContent("저장됨");
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      expect(addPlaceSpy).toHaveBeenCalledWith("104", 1, expect.objectContaining({ label: "오설록", expectedRevision: 10 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
      deletePlaceSpy.mockRestore();
    }
  });

  it("saves all recommendation preview candidates without deleting existing places", async () => {
    const existingPlace = { id: "old-2", time: "09:00", label: "기존 식당", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "105", revision: 20, title: "전체 저장 여행", days: { 1: [existingPlace], 2: [] } };
    const afterAddTrip: Trip = {
      ...trip,
      revision: 21,
      days: { 1: [existingPlace, { id: "new-2", time: "10:00", label: "새 추천", meta: "추천" }], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "new", title: "새 추천", label: "📍", meta: "추천", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(afterAddTrip);
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/105");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(await screen.findByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("105", 1, expect.objectContaining({ label: "새 추천", expectedRevision: 20 }));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: "새 추천 후보 저장" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "전체 저장" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      deletePlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("refreshes on recommendation preview 409 and preserves hidden candidates for global retry", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "106", revision: 30, title: "추천 충돌 여행", days: { 1: [], 2: [] } };
    const latestTrip: Trip = { ...trip, revision: 31 };
    const savedTrip: Trip = { ...latestTrip, revision: 32, days: { 1: [{ id: "p3", time: "09:00", label: "우도", meta: "섬" }], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(latestTrip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "udo", title: "우도", label: "🌊", meta: "섬", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi
      .spyOn(appDataApi, "addTripPlace")
      .mockRejectedValueOnce(new ApiError("conflict", { status: 409, statusText: "Conflict" }))
      .mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/106");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("우도").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "우도 후보 저장" })).toBeInTheDocument();
      expect(screen.queryByLabelText("우도 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("우도 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("우도 메모")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "우도 후보 저장" }));
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      expect(await screen.findByText(/다른 사용자가 먼저 일정을 수정/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "우도 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(2));
      expect(addPlaceSpy).toHaveBeenLastCalledWith("106", 1, expect.objectContaining({ label: "우도", time: "10:00", meta: "섬", expectedRevision: 31 }));
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not retry transient recommendation preview save automatically and preserves hidden candidates for manual retry", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "107", revision: 40, title: "추천 재시도 여행", days: { 1: [], 2: [] } };
    const savedTrip: Trip = { ...trip, revision: 41, days: { 1: [{ id: "p4", time: "09:00", label: "동백정원", meta: "꽃" }], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "garden", title: "동백정원", label: "🌺", meta: "꽃", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockRejectedValueOnce(new Error("temporary network")).mockResolvedValueOnce(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/107");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("동백정원").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "동백정원 후보 저장" })).toBeInTheDocument();
      expect(screen.queryByLabelText("동백정원 방문 시간")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("동백정원 메모")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "동백정원 후보 저장" }));
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "동백정원 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(2));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(1, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(2, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
      await waitFor(() => expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument());
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("keeps only unsaved recommendation preview candidates after a partial save failure", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "108", revision: 50, title: "부분 실패 여행", days: { 1: [], 2: [] } };
    const afterFirstSave: Trip = {
      ...trip,
      revision: 51,
      days: { 1: [{ id: "saved-tea", time: "09:00", label: "오설록", meta: "차" }], 2: [] },
    };
    const afterRetrySave: Trip = {
      ...trip,
      revision: 52,
      days: {
        1: [{ id: "saved-tea", time: "09:00", label: "오설록", meta: "차" }],
        2: [{ id: "saved-mountain", time: "09:00", label: "한라산", meta: "산" }],
      },
    };
    const getTripSpy = vi
      .spyOn(appDataApi, "getTrip")
      .mockResolvedValueOnce(trip)
      .mockResolvedValueOnce(afterFirstSave)
      .mockResolvedValue(afterFirstSave);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "tea", title: "오설록", label: "☕", meta: "차", reason: "추천", suggestedDay: 1 },
      { id: "mountain", title: "한라산", label: "⛰️", meta: "산", reason: "추천", suggestedDay: 2 },
    ]);
    let mountainAttempts = 0;
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, payload) => {
      if (payload.label === "오설록") return afterFirstSave;
      if (payload.label === "한라산") {
        mountainAttempts += 1;
        if (mountainAttempts === 1) throw new Error("temporary network");
        return afterRetrySave;
      }
      throw new Error(`Unexpected place ${payload.label}`);
    });

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/108");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      await waitFor(() => expect(screen.queryByRole("button", { name: "오설록 후보 제외" })).not.toBeInTheDocument());
      expect(screen.queryByLabelText("한라산 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Day 2 06.13 후보 1개" })).not.toBeInTheDocument();
      expect(screen.queryByText("후보 1")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /Day 2 06.13/ }));
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("한라산").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "한라산 후보 저장" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(screen.queryByRole("button", { name: "한라산 후보 저장" })).not.toBeInTheDocument());
      expect(screen.queryByRole("button", { name: /기존 유지하고 추가|추천 일정 추가하기|이 일정으로 저장|추천으로 대체/ })).not.toBeInTheDocument();
      expect(addPlaceSpy.mock.calls.map((call) => call[2].label)).toEqual(["오설록", "한라산", "한라산"]);
      expect(addPlaceSpy).toHaveBeenLastCalledWith("108", 2, expect.objectContaining({ label: "한라산", expectedRevision: 51 }));
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("does not delete existing places when full-save preview candidates fail", async () => {
    const existingPlace = { id: "old-3", time: "09:00", label: "기존 장소", meta: "기존" };
    const trip: Trip = { ...getPreviewTrip(), id: "111", revision: 90, title: "안전 대체 여행", days: { 1: [existingPlace], 2: [] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValueOnce(trip).mockResolvedValueOnce(trip).mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue([
      { id: "new-safe", title: "새 안전 추천", label: "📍", meta: "추천", reason: "추천", suggestedDay: 1 },
    ]);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockRejectedValueOnce(new Error("temporary network"));
    const deletePlaceSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/111");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      await user.click(screen.getByRole("button", { name: "전체 저장" }));

      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(deletePlaceSpy).not.toHaveBeenCalled();
      expect((await screen.findAllByText(/저장되지 않은 미리보기 입력은 그대로 보존/)).length).toBeGreaterThan(0);
      expect(screen.queryByLabelText("새 안전 추천 Day 선택")).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Day별 추천 일정 리스트" })).not.toBeInTheDocument();
      expect(screen.getAllByText("새 안전 추천").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "새 안전 추천 후보 저장" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
      deletePlaceSpy.mockRestore();
    }
  });

});
