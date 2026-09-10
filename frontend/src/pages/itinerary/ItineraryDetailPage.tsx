import {
  DndContext,
  DragOverlay,
  MeasuringStrategy,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  pointerWithin,
  type CollisionDetection,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type Modifier,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlertTriangle,
  Car,
  ChevronLeft,
  GripVertical,
  Info,
  Map as MapIcon,
  X,
} from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type MutableRefObject,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { TripDateRangePicker } from "../../components/trip/TripDateRangePicker";
import type { TripDateRangeValue } from "../../utils/tripDateRange";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  appDataApi,
  isApiError,
  type ItineraryPlace,
  type LinkedTripPolicy,
  type PlaceSearchCandidate,
  type Recommendation,
  type Trip,
  type TripPlaceMutationRequest,
  type TripPlaceRequest,
} from "../../api";
import { useSession } from "../../app/session";
import { useAsyncResource } from "../../api/useAsyncResource";
import {
  KakaoMapView,
  type KakaoMapMarker,
} from "../../components/map/KakaoMapView";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  IconButton,
  LinkButton,
  LoadingState,
  Toast,
  TopBar,
} from "../../components/ui";
import {
  getPolicyMoodIcon,
  getPolicyMoodTone,
  getTripRegionEmojiFromTitle,
} from "../../data/displayConfig";
import {
  clearDraft,
  createDraftKey,
  readDraft,
  saveDraft,
} from "../../utils/draftStorage";
import { FriendInvitePanel } from "./FriendInvitePanel";
import { DraftRestoreNotice } from "./_shared";

const defaultPlaceTime = "09:00";
const placeMinuteStep = 10;
const placeMinuteOptions = [0, 10, 20, 30, 40, 50] as const;
const placeTimeErrorMessage = "방문 시간은 10분 단위로 선택해 주세요.";

type TripDetailLocationState = {
  linkedPolicy?: LinkedTripPolicy | null;
};
type TripPlaceEditDraft = TripPlaceRequest & {
  placeId: string;
};
type PreviewPlace = {
  previewId: string;
  dayNumber: number;
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};
type PlaceBasketItem = TripPlaceRequest & {
  basketId: string;
};
type BatchPlaceRecovery =
  | { kind: "none" }
  | { kind: "missingDay"; availableDays: number[] };
type DisplayedPlace = ItineraryPlace & {
  isRecommendationPreview?: boolean;
  previewId?: string;
  previewDayNumber?: number;
  previewTimelineId?: string;
  previewOriginalDayNumber?: number;
  isRecommendationSelected?: boolean;
};
type RecommendationPreviewTimeline = Record<number, DisplayedPlace[]>;
type RecommendationTimeBucket = "attraction" | "food" | "cafe" | "stay";
type RecommendationPreviewKind = {
  bucket: RecommendationTimeBucket;
  rank: number;
  phaseLabel: "오전 일정" | "오후 일정" | "점심" | "카페" | "숙소";
};
type RecommendationPreviewState = {
  status: "idle" | "loading" | "ready" | "saving";
  places: PreviewPlace[];
  selectedPreviewIds: string[];
  timeline: RecommendationPreviewTimeline;
  error: string;
};
type PlacePreviewSource =
  | "empty"
  | "recommendation"
  | "searchPreview"
  | "selected";
type PlaceSaveEligibility =
  | "empty"
  | "saveSelected"
  | "requiresExplicitCandidate";
type PlacePreviewCandidate = TripPlaceRequest & {
  previewId: string;
  source: Exclude<PlacePreviewSource, "empty">;
  dayNumber: number;
};
type PlacePreviewState =
  | { source: "empty"; place: null }
  | {
      source: Exclude<PlacePreviewSource, "empty">;
      place: PlacePreviewCandidate;
    };

function tripDayNumbers(days: Record<number, unknown[]>): number[] {
  return Object.keys(days)
    .map(Number)
    .filter((day) => Number.isFinite(day))
    .sort((a, b) => a - b);
}

function formatStayLabel(dayCount: number): string {
  return `${Math.max(dayCount - 1, 0)}박 ${dayCount}일`;
}

function hasPolicySaving(expectedSaving: string | undefined): boolean {
  const value = expectedSaving?.trim();
  return Boolean(value && !value.startsWith("0"));
}

function linkedTripPoliciesForDisplay(
  apiPolicies: LinkedTripPolicy[] | undefined,
  routePolicy: LinkedTripPolicy | null,
  hiddenRoutePolicySlugs: Set<string>,
): LinkedTripPolicy[] {
  const seen = new Set<string>();
  const policies: LinkedTripPolicy[] = [];
  const append = (policy: LinkedTripPolicy | null | undefined) => {
    if (!policy || seen.has(policy.slug)) return;
    seen.add(policy.slug);
    policies.push(policy);
  };

  if (!routePolicy || !hiddenRoutePolicySlugs.has(routePolicy.slug))
    append(routePolicy);
  for (const policy of apiPolicies ?? []) append(policy);
  return policies;
}

function formatDayDateLabel(dates: string, dayNumber: number): string {
  const match = /^(\d{4})\.(\d{2})\.(\d{2})/.exec(dates);
  if (!match) return `Day ${dayNumber}`;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]) + dayNumber - 1,
  );
  return `${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}`;
}

function parseTripDateInputs(dates: string): { startDate: string; endDate: string } | null {
  const match = /^(\d{4})\.(\d{2})\.(\d{2})\s*-\s*(?:(\d{4})\.)?(\d{2})\.(\d{2})/.exec(dates);
  if (!match) return null;
  const startYear = match[1];
  const endYear = match[4] ?? startYear;
  return {
    startDate: `${startYear}-${match[2]}-${match[3]}`,
    endDate: `${endYear}-${match[5]}-${match[6]}`,
  };
}

function dayCountFromDateInputs(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) return null;
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

function formatTripDday(dates: string): string {
  const match = /^(\d{4})\.(\d{2})\.(\d{2})/.exec(dates);
  if (!match) return "D-day";
  const start = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  const today = new Date();
  const todayDate = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  const diffDays = Math.ceil(
    (start.getTime() - todayDate.getTime()) / 86_400_000,
  );
  if (diffDays > 0) return `D-${diffDays}`;
  if (diffDays === 0) return "D-day";
  return `D+${Math.abs(diffDays)}`;
}

function getPlaceEmoji(place: ItineraryPlace): string {
  const text = `${place.label} ${place.meta}`.toLowerCase();
  if (/카페|커피|tea|cafe|오설록/.test(text)) return "☕";
  if (/식당|맛집|해녀|국수|흑돼지|밥|restaurant|food|meal/.test(text))
    return "🍽️";
  if (/바다|해변|해수욕|beach|sea|월정|섭지/.test(text)) return "🌊";
  if (/산|오름|일출|숲|공원|nature|park|peak/.test(text)) return "⛰️";
  if (/공항|역|터미널|airport|station/.test(text)) return "🧳";
  return "📍";
}

function getPlaceMapPoint(
  index: number,
  dayNumber: number,
): { x: number; y: number } {
  const basePoints = [
    { x: 78, y: 30 },
    { x: 72, y: 52 },
    { x: 84, y: 62 },
    { x: 52, y: 70 },
    { x: 33, y: 56 },
    { x: 25, y: 38 },
  ];
  const point = basePoints[index % basePoints.length];
  const offset = Math.max(dayNumber - 1, 0) * 3;
  return {
    x: Math.min(90, Math.max(10, point.x - offset)),
    y: Math.min(86, Math.max(18, point.y + (offset % 7))),
  };
}

function tripPlaceEditDraftKey(tripId: string, placeId: string): string {
  return createDraftKey(`trip-place:${tripId}:edit:${placeId}`);
}

function placeDragId(placeId: string): string {
  return `place:${placeId}`;
}

function previewPlaceDragId(previewId: string): string {
  return `preview:${previewId}`;
}

function displayedPlaceSortableId(
  place: Pick<DisplayedPlace, "id" | "previewTimelineId" | "previewId">,
): string | null {
  if (place.previewTimelineId) return place.previewTimelineId;
  if (place.previewId) return previewPlaceDragId(place.previewId);
  if (place.id) return placeDragId(place.id);
  return null;
}

function displayedPlaceSortableIds(
  places: Pick<DisplayedPlace, "id" | "previewTimelineId" | "previewId">[],
): string[] {
  return places.flatMap((place) => {
    const sortableId = displayedPlaceSortableId(place);
    return sortableId ? [sortableId] : [];
  });
}

export function buildTimelineSortableIds({
  activeSortableId,
  ghostPosition,
  sortableIds,
}: {
  activeSortableId: string;
  ghostPosition: number | null;
  sortableIds: string[];
}): string[] {
  if (ghostPosition == null) return sortableIds;
  const targetIds = sortableIds.filter((id) => id !== activeSortableId);
  const index = Math.max(0, Math.min(ghostPosition - 1, targetIds.length));
  return [
    ...targetIds.slice(0, index),
    activeSortableId,
    ...targetIds.slice(index),
  ];
}

export type TimelineRenderItem<T> =
  | { type: "item"; value: T }
  | { type: "ghost" };

export function buildTimelineRenderItems<T>({
  ghostPosition,
  items,
}: {
  ghostPosition: number | null;
  items: T[];
}): TimelineRenderItem<T>[] {
  const renderItems = items.map((value) => ({
    type: "item" as const,
    value,
  }));
  if (ghostPosition == null) return renderItems;
  const index = Math.max(0, Math.min(ghostPosition - 1, renderItems.length));
  return [
    ...renderItems.slice(0, index),
    { type: "ghost" },
    ...renderItems.slice(index),
  ];
}

export function shouldForwardWindowWheelToAppScroll(
  event: Pick<WheelEvent, "deltaY" | "defaultPrevented">,
  appContainer: Pick<
    HTMLElement,
    "clientHeight" | "scrollHeight" | "scrollTop" | "classList"
  > | null,
): boolean {
  if (!appContainer) return false;
  if (event.defaultPrevented) return false;
  if (event.deltaY === 0) return false;

  const maxScrollTop = Math.max(
    0,
    appContainer.scrollHeight - appContainer.clientHeight,
  );
  if (maxScrollTop <= 0) return false;
  if (event.deltaY < 0 && appContainer.scrollTop <= 0) return false;
  if (event.deltaY > 0 && appContainer.scrollTop >= maxScrollTop) return false;
  return true;
}

/**
 * 휠이 앱 컨테이너보다 안쪽의 스크롤 가능한 요소에서 났는지 본다.
 * 휠은 window까지 버블링되므로, 대상을 가리지 않으면 시트 위에서 굴려도
 * 브리지가 기본 스크롤을 취소하고 뒤 화면을 스크롤한다.
 *
 * 특정 모달 클래스를 나열하지 않는다. 새 모달이 생길 때마다 재발한다.
 */
export function isWheelInsideNestedScroller(
  path: { canScrollY: boolean; isAppContainer: boolean }[],
): boolean {
  for (const node of path) {
    if (node.isAppContainer) return false;
    if (node.canScrollY) return true;
  }
  return false;
}

function findSortableIdDay(
  sortableIdsByDay: Record<number, string[]>,
  sortableId: string,
): number | null {
  for (const [dayText, sortableIds] of Object.entries(sortableIdsByDay)) {
    if (sortableIds.includes(sortableId)) return Number(dayText);
  }
  return null;
}

export function isCrossDayTimelineDrag({
  activeSortableId,
  sortableIdsByDay,
  visibleDay,
}: {
  activeSortableId: string | null;
  sortableIdsByDay: Record<number, string[]>;
  visibleDay: number;
}): boolean {
  if (!activeSortableId) return false;
  const sourceDay = findSortableIdDay(sortableIdsByDay, activeSortableId);
  return sourceDay != null && sourceDay !== visibleDay;
}

function dayDropId(dayNumber: number): string {
  return `day:${dayNumber}`;
}

function draggingPlaceLabel(
  trip: Trip | null,
  placeId: string | null,
  timeline?: RecommendationPreviewTimeline,
): string {
  if (!placeId) return "장소";
  if (timeline) {
    for (const places of Object.values(timeline)) {
      const place = places.find(
        (item) =>
          item.previewTimelineId === placeId ||
          item.id === placeId ||
          item.previewId === placeId,
      );
      if (place) return place.label;
    }
  }
  if (!trip) return "장소";
  for (const places of Object.values(trip.days)) {
    const place = places.find((item) => item.id === placeId);
    if (place) return place.label;
  }
  return "장소";
}

type ParsedTimelineDragId =
  | { type: "saved"; id: string }
  | { type: "preview"; id: string };

function parsePlaceDragId(id: unknown): string | null {
  const value = String(id);
  return value.startsWith("place:") ? value.slice("place:".length) : null;
}

function parseTimelineDragId(id: unknown): ParsedTimelineDragId | null {
  const value = String(id);
  if (value.startsWith("place:"))
    return { type: "saved", id: value.slice("place:".length) };
  if (value.startsWith("saved:"))
    return { type: "saved", id: value.slice("saved:".length) };
  if (value.startsWith("preview:"))
    return { type: "preview", id: value.slice("preview:".length) };
  return null;
}

function parseDayDropId(id: unknown): number | null {
  const value = String(id);
  if (!value.startsWith("day:")) return null;
  const dayNumber = Number(value.slice("day:".length));
  return Number.isFinite(dayNumber) ? dayNumber : null;
}

export function isPointerInsideClientRect(
  point: { x: number; y: number } | null,
  rect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null,
): boolean {
  if (!point || !rect) return false;
  return (
    point.x >= rect.left &&
    point.x <= rect.right &&
    point.y >= rect.top &&
    point.y <= rect.bottom
  );
}

/**
 * Day 탭은 높이 24px짜리 얇은 띠라 드래그 중 포인터를 정확히 유지하기 어렵다.
 * 탭 경계 바깥 이 정도까지는 같은 탭을 가리킨 것으로 본다.
 */
export const DAY_TAB_POINTER_TOLERANCE_PX = 12;

/** 하이라이트가 켜진 뒤 실제로 날짜가 열리기까지의 지연. 사실상 즉시 전환에 가깝다. */
/* ── Day 스트립 ─────────────────────────────────────────────────
   탭 위를 지나가는 것으로는 날짜가 바뀌지 않는다. 화면 좌우 끝 이동영역에
   머무는 것으로만 바뀐다. 값은 시안에서 손으로 조절해 확정했다. */

/** 화면 좌우 끝에서 이만큼이 날짜 넘김 구역 */
export const DAY_EDGE_WIDTH_PX = 80;
/** 이동영역에 들어간 뒤 첫 전환까지. 스쳐 지나가는 것과 머무는 것을 가른다 */
export const DAY_EDGE_FIRST_DELAY_MS = 900;
/** 계속 대고 있을 때 다음 날짜까지 */
export const DAY_EDGE_REPEAT_MS = 620;
/** 맨 끝에서는 반복 간격을 이 값으로 나눈다 */
export const DAY_EDGE_ACCEL = 2.8;
export const PLACE_DRAG_TOUCH_DELAY_MS = 800;
export const PLACE_DRAG_TOUCH_TOLERANCE_PX = 8;
/** 마우스는 홀드가 아니라 거리 기준이다. 여기에 지연을 걸면 안 된다 */
export const PLACE_DRAG_MOUSE_DISTANCE_PX = 8;
/* 이만큼 넘게 밀어야 "끌었다"로 본다. 그 아래는 그냥 클릭이다. */
export const DRAG_SCROLL_THRESHOLD_PX = 6;

/** 첫날·마지막날도 가운데에 설 수 있도록 양 끝에 줄 여백 */
export function resolveDayStripPadding(
  containerWidth: number,
  firstWidth: number,
  lastWidth: number,
): { left: number; right: number } {
  return {
    left: Math.max(0, (containerWidth - firstWidth) / 2),
    right: Math.max(0, (containerWidth - lastWidth) / 2),
  };
}

/** 활성 탭을 중앙에 놓는 scrollLeft */
export function resolveDayStripScrollLeft({
  tabOffsetLeft,
  tabWidth,
  containerWidth,
  scrollWidth,
}: {
  tabOffsetLeft: number;
  tabWidth: number;
  containerWidth: number;
  scrollWidth: number;
}): number {
  const target = tabOffsetLeft - (containerWidth - tabWidth) / 2;
  return Math.max(0, Math.min(target, Math.max(0, scrollWidth - containerWidth)));
}

/** -1 왼쪽 · 0 없음 · 1 오른쪽 */
export function resolveDayEdgeZone({
  pointerX,
  left,
  right,
  edgeWidth = DAY_EDGE_WIDTH_PX,
}: {
  pointerX: number | null;
  left: number;
  right: number;
  edgeWidth?: number;
}): -1 | 0 | 1 {
  if (pointerX == null) return 0;
  /* 바깥쪽에는 경계를 두지 않는다. PC 에서는 앱이 화면 가운데 좁은 칸이라
     카드를 옆으로 끌면 칸 밖으로 쉽게 나간다. 거기서 판정이 꺼지면
     "사이드로 옮겨도 안 넘어간다"가 된다. 밖으로 나가면 가장 깊은 것으로 본다. */
  if (pointerX < left + edgeWidth) return -1;
  if (pointerX > right - edgeWidth) return 1;
  return 0;
}

/** 안쪽 경계 0 → 맨 끝 1 */
export function resolveDayEdgeDepth({
  pointerX,
  left,
  right,
  zone,
  edgeWidth = DAY_EDGE_WIDTH_PX,
}: {
  pointerX: number;
  left: number;
  right: number;
  zone: -1 | 1;
  edgeWidth?: number;
}): number {
  const raw =
    zone < 0
      ? (left + edgeWidth - pointerX) / edgeWidth
      : (pointerX - (right - edgeWidth)) / edgeWidth;
  return Math.max(0, Math.min(1, raw));
}

/** 바깥쪽으로 갈수록 짧아지는 반복 간격 */
export function resolveDayEdgeInterval(depth: number): number {
  const clamped = Math.max(0, Math.min(1, depth));
  return DAY_EDGE_REPEAT_MS / (1 + (DAY_EDGE_ACCEL - 1) * clamped);
}

export function pointerDistanceToClientRect(
  point: { x: number; y: number } | null,
  rect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null,
): number {
  if (!point || !rect) return Number.POSITIVE_INFINITY;
  const dx = Math.max(rect.left - point.x, 0, point.x - rect.right);
  const dy = Math.max(rect.top - point.y, 0, point.y - rect.bottom);
  return Math.hypot(dx, dy);
}

export function isPointerNearClientRect(
  point: { x: number; y: number } | null,
  rect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null,
  tolerance: number = DAY_TAB_POINTER_TOLERANCE_PX,
): boolean {
  return pointerDistanceToClientRect(point, rect) <= tolerance;
}

export function isPointerInsideTimelineArea(
  point: { x: number; y: number } | null,
  rect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null,
): boolean {
  return isPointerInsideClientRect(point, rect);
}

type PointerRect = Pick<DOMRect, "left" | "right" | "top" | "bottom">;

/**
 * Day 탭 판정에 쓰는 보이지 않는 박스. 장소추가 버튼 줄 바로 아래부터
 * 타임라인 첫 카드 바로 위까지를 하나로 묶는다. 탭 사이 6px 간격과
 * 탭·타임라인 사이 16px 구간이 판정에서 빠져 작은 오버레이 카드가
 * 끊기던 문제를 없앤다.
 */
export function resolveDayZoneRect({
  actionsRect,
  dayTabsRect,
  timelineRect,
}: {
  actionsRect: PointerRect | null;
  dayTabsRect: PointerRect | null;
  timelineRect: PointerRect | null;
}): PointerRect | null {
  if (!dayTabsRect) return null;
  return {
    left: dayTabsRect.left,
    right: dayTabsRect.right,
    top: actionsRect
      ? Math.min(actionsRect.bottom, dayTabsRect.top)
      : dayTabsRect.top,
    bottom: timelineRect
      ? Math.max(timelineRect.top, dayTabsRect.bottom)
      : dayTabsRect.bottom,
  };
}

export function shouldScheduleDaySwitch({
  pointer,
  dayTabRect,
  timelineRect,
  dayZoneRect = null,
}: {
  pointer: { x: number; y: number } | null;
  dayTabRect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
  timelineRect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
  dayZoneRect?: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
}): boolean {
  if (isPointerInsideTimelineArea(pointer, timelineRect)) return false;
  // resolvePointerDayTarget과 같은 판정을 써야 한다. 어긋나면 불은 켜지는데
  // 날짜는 안 열리는 죽은 구간이 생긴다.
  if (isPointerInsideClientRect(pointer, dayZoneRect)) return true;
  return isPointerNearClientRect(pointer, dayTabRect);
}

export function shouldUseDayRowDragOverlay({
  pointer,
  dayTabsRect,
  timelineRect,
}: {
  pointer: { x: number; y: number } | null;
  dayTabsRect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
  timelineRect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
}): boolean {
  return (
    isPointerInsideClientRect(pointer, dayTabsRect) &&
    !isPointerInsideTimelineArea(pointer, timelineRect)
  );
}

/**
 * 드래그 중 타임라인에 걸 인라인 min-height. 날짜를 바꾸면 타임라인 내용이
 * 통째로 교체되어 문서가 짧아질 수 있고, 그러면 브라우저가 scrollTop을 강제로
 * 줄여 화면이 출렁인다. 이건 브라우저 레이아웃 동작이라 JS 스크롤 잠금으로는
 * 막을 수 없다. 줄어드는 것만 막으면 되므로 max-height가 아니라 min-height다.
 */
export function resolveTimelineHeightLock(
  timelineHeight: number | null,
): string | null {
  if (timelineHeight == null) return null;
  if (!Number.isFinite(timelineHeight)) return null;
  if (timelineHeight <= 0) return null;
  return `${Math.max(1, Math.round(timelineHeight))}px`;
}

/**
 * 드래그 한 번 동안 고정값은 절대 내려가지 않는다. 장소가 적은 날짜에서
 * 시작해 많은 날짜를 거쳐 돌아오면 문서가 줄어 스크롤이 클램프되기 때문이다.
 * 시작 시점 높이가 아니라 관측한 최대 높이를 유지한다.
 */
export function resolveRaisedTimelineHeightLock(
  currentLock: string | null,
  timelineHeight: number | null,
): string | null {
  const nextLock = resolveTimelineHeightLock(timelineHeight);
  if (!nextLock) return currentLock || null;
  const currentPx = Number.parseFloat(currentLock ?? "");
  if (!Number.isFinite(currentPx)) return nextLock;
  return Number.parseFloat(nextLock) > currentPx ? nextLock : currentLock;
}

/** dnd-kit 자동 스크롤이 발동하는 가장자리 폭. 컨테이너 높이 대비 비율이다. */
export const PLACE_DRAG_AUTO_SCROLL_THRESHOLD = 0.2;
const PLACE_SEARCH_DEBOUNCE_MS = 350;


/**
 * 위쪽 자동 스크롤의 상한. Day 탭은 타임라인보다 위에 있어서, 탭을 겨냥해
 * 카드를 위로 끌면 자동 스크롤이 헤더와 버튼 줄을 불러와 탭을 아래로 밀어낸다.
 * 겨냥하던 대상이 움직이므로 삽입이 어려워진다.
 *
 * `anchorRect`가 멈춤 기준이다. 이 요소가 다 보이면 위로 더 갈 이유가 없으므로
 * 막고, 화면 밖이면 보일 때까지는 허용한다 — 아래로 한참 내려간 상태에서
 * 집었을 때 다른 날짜로 옮길 길이 막히면 안 되고, 모바일은 휠 대안도 없다.
 *
 * 기준은 Day 탭이 아니라 그 위의 장소추가 버튼 줄이다. Day 탭을 기준으로 하면
 * 탭이 화면 맨 위 가장자리에 딱 붙어 겨냥이 빡빡하다.
 *
 * 아래쪽 자동 스크롤은 건드리지 않는다. 화면 밖 장소에 닿으려면 필요하다.
 */
export function shouldAllowPlaceDragAutoScroll({
  pointerY,
  containerRect,
  anchorRect,
  thresholdRatio,
}: {
  pointerY: number | null;
  containerRect: Pick<DOMRect, "top" | "bottom"> | null;
  anchorRect: Pick<DOMRect, "top" | "bottom"> | null;
  thresholdRatio: number;
}): boolean {
  if (pointerY == null || !containerRect) return true;
  if (!anchorRect) return true;
  const containerHeight = containerRect.bottom - containerRect.top;
  if (containerHeight <= 0) return true;
  const isPointerInTopBand =
    pointerY <= containerRect.top + containerHeight * thresholdRatio;
  if (!isPointerInTopBand) return true;
  const isAnchorFullyVisible =
    anchorRect.top >= containerRect.top &&
    anchorRect.bottom <= containerRect.bottom;
  return !isAnchorFullyVisible;
}

export function resolveClosestTimelinePosition({
  itemRects,
  pointerY,
}: {
  itemRects: Pick<DOMRect, "top" | "bottom">[];
  pointerY: number | null;
}): number {
  if (pointerY == null || itemRects.length === 0) return 1;
  const nextIndex = itemRects.findIndex(
    (rect) => pointerY <= (rect.top + rect.bottom) / 2,
  );
  return nextIndex < 0 ? itemRects.length + 1 : nextIndex + 1;
}

/**
 * 같은 날짜 안에서의 삽입 위치. 백엔드 move_trip_place는 같은 날짜일 때
 * 끌고 있는 카드를 먼저 뺀 목록에 position-1로 끼우므로, 세는 목록에서도
 * 그 카드를 빼야 자리가 맞는다. 빼지 않으면 드래그한 카드가 놓는 지점보다
 * 위에 있을 때 한 칸씩 밀린다.
 */
export function resolveSameDayInsertPosition({
  items,
  activeSortableId,
  pointerY,
}: {
  items: { sortableId: string; top: number; bottom: number }[];
  activeSortableId: string | null;
  pointerY: number | null;
}): number {
  return resolveClosestTimelinePosition({
    itemRects: items.filter((item) => item.sortableId !== activeSortableId),
    pointerY,
  });
}

/**
 * 끌고 있는 카드 자신은 드롭 후보에서 뺀다. 슬롯의 판정 사각형은 원래 자리에
 * 그대로 있고 변형은 안쪽 카드에만 걸리므로, 카드 한 장 높이보다 적게 끌면
 * 포인터가 아직 자기 슬롯 안이라 over === active가 되어 드롭이 무시됐다.
 * 빼두면 타임라인 영역(day-area)이 받아 포인터 위치대로 자리가 정해진다.
 */
export function excludeActiveCollision<T extends { id: unknown }>(
  collisions: T[],
  activeId: unknown,
): T[] {
  if (activeId == null) return collisions;
  return collisions.filter(
    (collision) => String(collision.id) !== String(activeId),
  );
}

export function resolvePointerDayTarget({
  dayNumbers,
  pointer,
  rectByDay,
  timelineRect,
  dayZoneRect = null,
}: {
  dayNumbers: number[];
  pointer: { x: number; y: number } | null;
  rectByDay: Record<
    number,
    Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null | undefined
  >;
  timelineRect: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
  dayZoneRect?: Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null;
}): number | null {
  if (isPointerInsideTimelineArea(pointer, timelineRect)) return null;
  // Day 존 안이면 거리 상한 없이 가장 가까운 탭을 고른다. 존을 못 재면
  // 탭 경계 여유(DAY_TAB_POINTER_TOLERANCE_PX)로 폴백한다.
  const maxDistance = isPointerInsideClientRect(pointer, dayZoneRect)
    ? Number.POSITIVE_INFINITY
    : DAY_TAB_POINTER_TOLERANCE_PX;
  let closestDay: number | null = null;
  let closestDistance = Number.POSITIVE_INFINITY;
  for (const dayNumber of dayNumbers) {
    const distance = pointerDistanceToClientRect(
      pointer,
      rectByDay[dayNumber] ?? null,
    );
    if (distance > maxDistance) continue;
    if (distance < closestDistance) {
      closestDistance = distance;
      closestDay = dayNumber;
    }
  }
  return closestDay;
}

export function resolvePlaceDragOverId({
  collisionOverId,
  pointerDayTarget,
  isOverDayRow,
  visibleDay,
  closestVisibleDayPosition,
}: {
  collisionOverId: unknown | null;
  pointerDayTarget: number | null;
  isOverDayRow: boolean;
  visibleDay: number;
  closestVisibleDayPosition: number;
}): unknown | null {
  if (pointerDayTarget != null) return dayDropId(pointerDayTarget);
  if (isOverDayRow) {
    return dayPositionDropId(visibleDay, closestVisibleDayPosition);
  }
  return collisionOverId;
}

export function resolvePointerVerifiedTimelineOverId({
  dayNumbers,
  overId,
  pointer,
  rectByDay,
}: {
  dayNumbers: number[];
  overId: unknown;
  pointer: { x: number; y: number } | null;
  rectByDay: Record<
    number,
    Pick<DOMRect, "left" | "right" | "top" | "bottom"> | null | undefined
  >;
}): unknown | null {
  const targetDay = parseDayDropId(overId);
  if (!targetDay) return overId;
  if (!dayNumbers.includes(targetDay)) return null;
  return isPointerInsideClientRect(pointer, rectByDay[targetDay] ?? null)
    ? overId
    : null;
}

function dayPositionDropId(dayNumber: number, position: number): string {
  return `day-position:${dayNumber}:${position}`;
}

function parseDayPositionDropId(
  id: unknown,
): { dayNumber: number; position: number } | null {
  const match = /^day-position:(\d+):(\d+)$/.exec(String(id));
  if (!match) return null;
  const dayNumber = Number(match[1]);
  const position = Number(match[2]);
  if (!Number.isInteger(dayNumber) || !Number.isInteger(position)) return null;
  return { dayNumber, position };
}

export type TimelineDropTarget = {
  dayNumber: number;
  position: number;
};

export function resolveTimelineDropTarget({
  activeSortableId,
  dayNumbers,
  overId,
  sortableIdsByDay,
  visibleDay,
}: {
  activeSortableId: string;
  dayNumbers: number[];
  overId: unknown;
  sortableIdsByDay: Record<number, string[]>;
  visibleDay: number;
}): TimelineDropTarget | null {
  const explicitPosition = parseDayPositionDropId(overId);
  if (
    explicitPosition &&
    dayNumbers.includes(explicitPosition.dayNumber) &&
    explicitPosition.position >= 1
  ) {
    return explicitPosition;
  }

  const targetDay = parseDayDropId(overId);
  if (targetDay && dayNumbers.includes(targetDay)) {
    const targetIds = sortableIdsByDay[targetDay] ?? [];
    const sameVisibleDay = targetDay === visibleDay;
    const targetCount = sameVisibleDay
      ? targetIds.filter((id) => id !== activeSortableId).length
      : targetIds.length;
    return { dayNumber: targetDay, position: targetCount + 1 };
  }

  const overSortableId = String(overId);
  if (overSortableId === activeSortableId) return null;
  for (const dayNumber of dayNumbers) {
    const targetIds = sortableIdsByDay[dayNumber] ?? [];
    const targetIndex = targetIds.indexOf(overSortableId);
    if (targetIndex >= 0) {
      return { dayNumber, position: targetIndex + 1 };
    }
  }
  return null;
}

/**
 * 타임라인 영역 전체를 덮는 드롭 대상. 빈 날짜나 마지막 카드 아래 빈 공간에는
 * 포인터가 맞출 수 있는 droppable이 없었다 — 카드 사이 슬롯은 height:0이라
 * pointerWithin이 절대 잡지 못한다.
 */
function dayAreaDropId(dayNumber: number): string {
  return `day-area:${dayNumber}`;
}

export function parseDayAreaDropId(id: unknown): number | null {
  const match = /^day-area:(\d+)$/.exec(String(id));
  if (!match) return null;
  const dayNumber = Number(match[1]);
  return Number.isInteger(dayNumber) ? dayNumber : null;
}

/**
 * pointerWithin은 겹치는 droppable을 모두 돌려준다. 타임라인 영역은 카드보다
 * 훨씬 커서 카드를 이길 수 있고, 그러면 카드 사이 삽입 위치를 못 고른다.
 * 더 구체적인 대상이 하나라도 있으면 영역은 버린다.
 */
export function preferSpecificDropTargets<T extends { id: unknown }>(
  collisions: T[],
): T[] {
  const specific = collisions.filter(
    (collision) => parseDayAreaDropId(collision.id) == null,
  );
  return specific.length > 0 ? specific : collisions;
}

/**
 * 영역 드롭을 실제 삽입 위치로 바꾼다. closestPosition은 기존
 * resolveClosestTimelinePosition으로 구하며, 빈 날짜면 1이 나온다.
 */
export function resolveDayAreaOverId({
  overId,
  closestPosition,
}: {
  overId: unknown;
  closestPosition: number;
}): unknown {
  const dayNumber = parseDayAreaDropId(overId);
  if (dayNumber == null) return overId;
  return dayPositionDropId(dayNumber, closestPosition);
}

/**
 * 유령 자리표시는 활성 카드의 sortable id로 등록돼 있다. 그 위에 드롭하거나
 * 그 위를 지날 때 id를 그대로 넘기면 resolveTimelineDropTarget의 자기 자신
 * 방어에 걸려 null이 되고, 드롭이 통째로 무시되거나 유령이 깜빡인다.
 * 이미 계산해 둔 삽입 위치로 바꿔준다.
 */
export function resolveGhostDropOverId({
  activeSortableId,
  overId,
  crossDayPreview,
}: {
  activeSortableId: string;
  overId: unknown;
  crossDayPreview: TimelineDropTarget | null;
}): unknown {
  if (String(overId) !== activeSortableId) return overId;
  if (!crossDayPreview) return overId;
  return dayPositionDropId(crossDayPreview.dayNumber, crossDayPreview.position);
}

/**
 * 1등과 2등이 서로 뒤바뀌는 진동을 막는다.
 *
 * 자리를 벌리는 동작은 형제 카드를 transform 으로 민다. transform 은
 * getBoundingClientRect() 를 바꾸고, MeasuringStrategy.Always 라 매 프레임 다시
 * 잰다. 그래서 "벌린다 → 좌표가 바뀐다 → 판정이 뒤집힌다 → 닫힌다 → 좌표가
 * 돌아온다" 가 되먹임 고리를 이룬다. 카드가 겹칠 때 자리가 빠르게 깜박인 이유다.
 *
 * 직전 승자를 **무조건** 붙들면 안 된다. closestCenter 는 모든 대상을 순위로
 * 돌려주므로 직전 승자가 항상 목록에 남아 드래그가 굳어버린다.
 * 진동은 1등과 2등 사이에서만 일어나므로, 직전 승자가 **바로 다음 순위로
 * 밀려났을 때만** 유지한다. 3등 밖으로 밀렸다면 포인터가 실제로 떠난 것이다.
 *
 * 조정할 문턱값이 없다. 순위만 본다.
 */
export function preferPreviousCollision<T extends { id: unknown }>(
  collisions: T[],
  previousId: unknown,
): T[] {
  if (previousId == null || collisions.length < 2) return collisions;
  if (collisions[0]?.id === previousId) return collisions;
  if (collisions[1]?.id !== previousId) return collisions;
  return [collisions[1], collisions[0], ...collisions.slice(2)];
}

/** 직전 판정 결과. 드래그가 끝나면 resetPlaceDragCollisionMemory 로 지운다. */
let lastPlaceDragOverId: unknown = null;

export function resetPlaceDragCollisionMemory(): void {
  lastPlaceDragOverId = null;
}

const placeDragCollisionDetection: CollisionDetection = (args) => {
  // 순서가 중요하다. 구체적인 대상을 먼저 고르면 [day-area, 활성카드]에서
  // 활성카드가 남고, 그걸 빼면 후보가 통째로 비어 드롭이 무시된다.
  const narrow = <T extends { id: unknown }>(collisions: T[]): T[] =>
    preferSpecificDropTargets(
      excludeActiveCollision(collisions, args.active?.id ?? null),
    );
  const pointerCollisions = narrow(pointerWithin(args));
  const resolved =
    pointerCollisions.length > 0 ? pointerCollisions : narrow(closestCenter(args));
  const stable = preferPreviousCollision(resolved, lastPlaceDragOverId);
  lastPlaceDragOverId = stable[0]?.id ?? null;
  return stable;
};

function parsePlaceTime(
  value: string | null | undefined,
): { hour: number; minute: number } | null {
  const match = /^([01]\d|2[0-3]):([0-5]\d)$/.exec((value ?? "").trim());
  if (!match) return null;
  return { hour: Number(match[1]), minute: Number(match[2]) };
}

function formatPlaceTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function isTenMinutePlaceTime(value: string | null | undefined): boolean {
  if (!value || value.trim() === "") return true;
  const parsed = parsePlaceTime(value);
  return Boolean(
    parsed &&
    placeMinuteOptions.includes(
      parsed.minute as (typeof placeMinuteOptions)[number],
    ),
  );
}

function placeTimeBase(value: string | null | undefined): {
  hour: number;
  minute: number;
} {
  const parsed = parsePlaceTime(value);
  if (parsed && parsed.minute % placeMinuteStep === 0) return parsed;
  return parsePlaceTime(defaultPlaceTime) ?? { hour: 9, minute: 0 };
}

function recommendationPlaceDescription(item: Recommendation): string {
  const parts = [item.categoryName, item.address].filter(
    (part): part is string => Boolean(part?.trim()),
  );
  if (parts.length > 0) return parts.join(" · ");
  return item.meta || item.reason || "장소 정보 확인";
}

function recommendationPlacePayload(
  item: Recommendation,
  time: string | undefined,
): TripPlaceRequest {
  return {
    time: time ?? "",
    label: item.title,
    meta: recommendationPlaceDescription(item),
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.categoryName ?? item.categoryGroup ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: item.sourceProvider ?? null,
    externalPlaceId: item.externalPlaceId ?? null,
  };
}

function explicitRecommendationPlaceTime(item: Recommendation): string | null {
  return item.meta.match(/\b\d{2}:\d{2}\b/)?.[0] ?? null;
}

function recommendationPreviewKind(
  bucket: RecommendationTimeBucket,
  time: string | undefined,
): RecommendationPreviewKind {
  if (bucket === "food") return { bucket, rank: 1, phaseLabel: "점심" };
  if (bucket === "cafe") return { bucket, rank: 2, phaseLabel: "카페" };
  if (bucket === "stay") return { bucket, rank: 3, phaseLabel: "숙소" };

  const timeValue = previewPlaceTimeValue(time);
  return {
    bucket,
    rank: 0,
    phaseLabel: timeValue < 12 * 60 ? "오전 일정" : "오후 일정",
  };
}

function recommendationTimeBucketFromFields(fields: {
  category?: string | null;
  categoryCode?: string | null;
  categoryGroup?: string | null;
  label?: string | null;
  meta?: string | null;
  reason?: string | null;
}): RecommendationTimeBucket {
  const categoryCode = fields.categoryCode?.toUpperCase();
  if (categoryCode === "FD6") return "food";
  if (categoryCode === "CE7") return "cafe";
  if (categoryCode === "AD5") return "stay";
  if (fields.categoryGroup === "food") return "food";
  if (fields.categoryGroup === "stay") return "stay";

  const categoryText = [
    fields.category,
    fields.meta,
    fields.reason,
    fields.label,
  ]
    .filter(Boolean)
    .join(" ");
  if (/관광|명소/.test(categoryText)) return "attraction";
  if (/카페|커피|디저트/.test(categoryText)) return "cafe";
  if (
    /식당|음식|점심|맛집|밥|한식|양식|일식|중식|분식|레스토랑/.test(
      categoryText,
    )
  )
    return "food";
  if (/숙소|숙박|호텔|리조트|펜션|게스트하우스/.test(categoryText))
    return "stay";
  return "attraction";
}

function recommendationTimeBucket(
  item: Recommendation,
): RecommendationTimeBucket {
  return recommendationTimeBucketFromFields({
    category: item.categoryName,
    categoryCode: item.categoryCode,
    categoryGroup: item.categoryGroup,
    label: item.title,
    meta: item.meta,
    reason: item.reason,
  });
}

function recommendationBucketBaseTime(
  bucket: RecommendationTimeBucket,
): string {
  switch (bucket) {
    case "food":
      return "12:00";
    case "cafe":
      return "15:00";
    case "stay":
      return "17:00";
    case "attraction":
    default:
      return "10:00";
  }
}

function addHoursToPlaceTime(time: string, hours: number): string {
  const parsed = parsePlaceTime(time) ??
    parsePlaceTime(defaultPlaceTime) ?? { hour: 9, minute: 0 };
  return formatPlaceTime((parsed.hour + hours) % 24, parsed.minute);
}

function recommendationPlaceTime(
  item: Recommendation,
  bucketOffset = 0,
): string {
  const explicitTime = explicitRecommendationPlaceTime(item);
  if (explicitTime) return explicitTime;
  return addHoursToPlaceTime(
    recommendationBucketBaseTime(recommendationTimeBucket(item)),
    bucketOffset,
  );
}

function recommendationPreviewId(item: Recommendation, index: number): string {
  const stableId = item.id ?? item.externalPlaceId;
  if (stableId) return stableId;
  const randomId = globalThis.crypto?.randomUUID?.();
  return randomId ?? `preview-${index}-${Date.now()}`;
}

function previewPlaceFromRecommendation(
  item: Recommendation,
  index: number,
  dayNumber: number,
): PreviewPlace {
  const payload = recommendationPlacePayload(
    item,
    recommendationPlaceTime(item),
  );
  return {
    previewId: recommendationPreviewId(item, index),
    dayNumber,
    time: payload.time,
    label: payload.label,
    meta: payload.meta,
    address: payload.address,
    latitude: payload.latitude,
    longitude: payload.longitude,
    category: payload.category,
    categoryCode: payload.categoryCode,
    placeUrl: payload.placeUrl,
    sourceProvider: payload.sourceProvider,
    externalPlaceId: payload.externalPlaceId,
  };
}

type RecommendationPreviewOrderFields = Pick<
  PreviewPlace,
  "category" | "categoryCode" | "label" | "meta" | "time"
>;

function previewPlaceTimeValue(time: string | undefined): number {
  const parsed = parsePlaceTime(time);
  if (!parsed) return Number.MAX_SAFE_INTEGER;
  return parsed.hour * 60 + parsed.minute;
}

function recommendationPreviewCategoryRank(
  place: RecommendationPreviewOrderFields,
): number {
  return recommendationPreviewKind(
    recommendationTimeBucketFromFields(place),
    place.time,
  ).rank;
}

function recommendationPreviewPhaseLabel(
  place: RecommendationPreviewOrderFields,
): string {
  return recommendationPreviewKind(
    recommendationTimeBucketFromFields(place),
    place.time,
  ).phaseLabel;
}

function sortRecommendationPreviewPlaces(
  places: PreviewPlace[],
): PreviewPlace[] {
  return places
    .map((place, originalIndex) => ({ place, originalIndex }))
    .sort((left, right) => {
      const dayDiff = left.place.dayNumber - right.place.dayNumber;
      if (dayDiff !== 0) return dayDiff;

      const timeDiff =
        previewPlaceTimeValue(left.place.time) -
        previewPlaceTimeValue(right.place.time);
      if (timeDiff !== 0) return timeDiff;

      const categoryDiff =
        recommendationPreviewCategoryRank(left.place) -
        recommendationPreviewCategoryRank(right.place);
      if (categoryDiff !== 0) return categoryDiff;

      return left.originalIndex - right.originalIndex;
    })
    .map(({ place }) => place);
}

function previewPlacesFromRecommendations(
  items: Recommendation[],
  dayNumbers: number[],
  visibleDay: number,
): PreviewPlace[] {
  const bucketCounts = new Map<string, number>();
  const places = items.map((item, index) => {
    const dayNumber = dayNumbers.includes(item.suggestedDay ?? 1)
      ? (item.suggestedDay ?? 1)
      : visibleDay;
    const explicitTime = explicitRecommendationPlaceTime(item);
    const bucket = recommendationTimeBucket(item);
    const bucketKey = `${dayNumber}:${bucket}`;
    const offset = explicitTime ? 0 : (bucketCounts.get(bucketKey) ?? 0);
    if (!explicitTime) bucketCounts.set(bucketKey, offset + 1);
    const payload = recommendationPlacePayload(
      item,
      recommendationPlaceTime(item, offset),
    );
    return {
      previewId: recommendationPreviewId(item, index),
      dayNumber,
      time: payload.time,
      label: payload.label,
      meta: payload.meta,
      address: payload.address,
      latitude: payload.latitude,
      longitude: payload.longitude,
      category: payload.category,
      categoryCode: payload.categoryCode,
      placeUrl: payload.placeUrl,
      sourceProvider: payload.sourceProvider,
      externalPlaceId: payload.externalPlaceId,
    };
  });
  return sortRecommendationPreviewPlaces(places);
}

function tripPlaceMutationFromPreviewPlace(
  place: PreviewPlace,
  expectedRevision: number,
): TripPlaceMutationRequest {
  return {
    time: place.time ?? "",
    label: place.label,
    meta: place.meta,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    category: place.category,
    categoryCode: place.categoryCode,
    placeUrl: place.placeUrl,
    sourceProvider: place.sourceProvider,
    externalPlaceId: place.externalPlaceId,
    expectedRevision,
  };
}

function timelinePlaceFromPreviewPlace(
  place: PreviewPlace,
  isSelected = false,
): DisplayedPlace {
  return {
    time: place.time ?? "",
    label: place.label,
    meta: place.meta ?? "",
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    category: place.category,
    categoryCode: place.categoryCode,
    placeUrl: place.placeUrl,
    sourceProvider: place.sourceProvider,
    externalPlaceId: place.externalPlaceId,
    isRecommendationPreview: true,
    isRecommendationSelected: isSelected,
    previewId: place.previewId,
    previewDayNumber: place.dayNumber,
    previewTimelineId: previewPlaceDragId(place.previewId),
  };
}

function recommendationPreviewTimelineFromTrip(
  trip: Trip,
  previewPlaces: PreviewPlace[],
  dayNumbers: number[],
): RecommendationPreviewTimeline {
  const timeline: RecommendationPreviewTimeline = {};
  for (const day of dayNumbers) {
    timeline[day] = (trip.days[day] ?? []).map((place) => ({
      ...place,
      previewOriginalDayNumber: day,
      previewTimelineId: place.id
        ? placeDragId(place.id)
        : `saved:${day}:${place.label}`,
    }));
  }
  for (const previewPlace of previewPlaces) {
    const day = previewPlace.dayNumber;
    timeline[day] = [
      ...(timeline[day] ?? []),
      timelinePlaceFromPreviewPlace(previewPlace),
    ];
  }
  return timeline;
}

function findDisplayedPlaceDay(
  timeline: RecommendationPreviewTimeline,
  timelineId: string,
): number | null {
  for (const [day, places] of Object.entries(timeline)) {
    if (places.some((place) => place.previewTimelineId === timelineId))
      return Number(day);
  }
  return null;
}

function moveTimelinePlace(
  timeline: RecommendationPreviewTimeline,
  timelineId: string,
  targetDay: number,
  targetIndex: number,
): RecommendationPreviewTimeline {
  let movingPlace: DisplayedPlace | null = null;
  const next: RecommendationPreviewTimeline = {};
  for (const [dayText, places] of Object.entries(timeline)) {
    const day = Number(dayText);
    next[day] = [];
    for (const place of places) {
      if (place.previewTimelineId === timelineId) movingPlace = place;
      else next[day].push(place);
    }
  }
  if (!movingPlace) return timeline;
  const targetPlaces = [...(next[targetDay] ?? [])];
  const boundedIndex = Math.max(0, Math.min(targetIndex, targetPlaces.length));
  targetPlaces.splice(boundedIndex, 0, {
    ...movingPlace,
    previewDayNumber: movingPlace.isRecommendationPreview
      ? targetDay
      : movingPlace.previewDayNumber,
  });
  next[targetDay] = targetPlaces;
  return next;
}

function updateTimelinePlaceTime(
  timeline: RecommendationPreviewTimeline,
  timelineId: string,
  time: string,
): RecommendationPreviewTimeline {
  const next: RecommendationPreviewTimeline = {};
  for (const [dayText, places] of Object.entries(timeline)) {
    const day = Number(dayText);
    next[day] = places.map((place) =>
      place.previewTimelineId === timelineId ? { ...place, time } : place,
    );
  }
  return next;
}

function placeTimeMinutes(time: string | undefined): number | null {
  if (!time) return null;
  const match = /^(\d{2}):(\d{2})$/.exec(time);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return hour * 60 + minute;
}

/**
 * 추천 미리보기의 시간 수정창은 한 번에 하나만 열린다. `<details>`는 자기
 * 열림 상태를 스스로 들고 서로를 모르므로, 부모가 열린 카드 하나를 기억한다.
 *
 * 닫는 신호는 그 카드가 실제로 열려 있을 때만 반영한다. 그렇지 않으면
 * 브라우저가 다른 카드에 보내는 닫힘 신호가 열린 창을 꺼버린다.
 */
export function resolveNextOpenTimeEditorId(
  currentOpenId: string | null,
  toggledId: string,
  willOpen: boolean,
): string | null {
  if (willOpen) return toggledId;
  return currentOpenId === toggledId ? null : currentOpenId;
}

function displayedPlaceWarningKey(place: DisplayedPlace): string | null {
  return place.id ?? place.previewTimelineId ?? null;
}

/**
 * 시간을 고친 장소가 들어갈 자리를 찾는다. 1부터 세는 위치를 돌려준다.
 *
 * 자기보다 **늦은** 첫 장소 앞에 선다. 같은 시간은 늦은 게 아니므로 그 뒤에 붙는다.
 * 15시를 9시로 고치면 기존 9시들 밑으로 간다.
 * 시간이 없는 장소는 맨 위에 모인다. 비교에서는 건너뛴다.
 *
 * 손으로 끌어 옮겨 생긴 시간 역전은 여기서 다루지 않는다.
 * 그건 timeOrderWarningPlaceIds 가 경고로 알린다.
 */
export function resolveTimeSortedPosition({
  places,
  movingPlaceId,
  nextTime,
}: {
  places: { id?: string | null; time?: string | null }[];
  movingPlaceId: string;
  nextTime: string | null;
}): number {
  const others = places.filter((place) => place.id !== movingPlaceId);
  const minutes = placeTimeMinutes(nextTime ?? "");

  /* 시간이 없으면 맨 위에 쌓는다. 시간 없는 것들끼리는 도착 순서로 쌓이도록
     이미 위에 있는 무시간 장소들 다음에 선다. 같은 시간이 뒤에 붙는 것과 같은 규칙이다. */
  if (minutes === null) {
    let index = 0;
    while (
      index < others.length &&
      placeTimeMinutes(others[index]?.time ?? "") === null
    ) {
      index += 1;
    }
    return index + 1;
  }

  let index = others.length;
  for (let i = 0; i < others.length; i += 1) {
    const other = placeTimeMinutes(others[i]?.time ?? "");
    // 시간 없는 장소는 위에 모여 있다. 건너뛰고 더 늦은 시간을 찾는다.
    if (other !== null && other > minutes) {
      index = i;
      break;
    }
  }
  return index + 1;
}

function timeOrderWarningPlaceIds(places: DisplayedPlace[]): Set<string> {
  const warningIds = new Set<string>();
  let previousMinutes: number | null = null;

  for (const place of places) {
    const currentMinutes = placeTimeMinutes(place.time);
    const key = displayedPlaceWarningKey(place);
    if (
      currentMinutes !== null &&
      previousMinutes !== null &&
      currentMinutes < previousMinutes &&
      key
    ) {
      warningIds.add(key);
    }
    if (currentMinutes !== null) previousMinutes = currentMinutes;
  }

  return warningIds;
}

function findTripPlaceById(
  trip: Trip,
  placeId: string,
): { dayNumber: number; place: ItineraryPlace; index: number } | null {
  for (const [dayText, places] of Object.entries(trip.days)) {
    const index = places.findIndex((place) => place.id === placeId);
    if (index >= 0)
      return { dayNumber: Number(dayText), place: places[index], index };
  }
  return null;
}

function tripPlaceMutationFromDisplayedPlace(
  place: DisplayedPlace,
  expectedRevision: number,
): TripPlaceMutationRequest {
  return {
    time: place.time ?? "",
    label: place.label,
    meta: place.meta,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    category: place.category,
    categoryCode: place.categoryCode,
    placeUrl: place.placeUrl,
    sourceProvider: place.sourceProvider,
    externalPlaceId: place.externalPlaceId,
    expectedRevision,
  };
}

function findAddedPlaceId(
  previousTrip: Trip,
  nextTrip: Trip,
  dayNumber: number,
  place: DisplayedPlace,
  usedPlaceIds: Set<string>,
): string | null {
  const previousIds = new Set(
    (previousTrip.days[dayNumber] ?? []).map((item) => item.id).filter(Boolean),
  );
  const candidates = (nextTrip.days[dayNumber] ?? []).filter(
    (item) =>
      item.id && !previousIds.has(item.id) && !usedPlaceIds.has(item.id),
  );
  const exact = candidates.find(
    (item) =>
      item.externalPlaceId && item.externalPlaceId === place.externalPlaceId,
  );
  const matched =
    exact ??
    candidates.find(
      (item) =>
        item.label === place.label && (item.time ?? "") === (place.time ?? ""),
    ) ??
    candidates.find((item) => item.label === place.label) ??
    candidates[candidates.length - 1];
  return matched?.id ?? null;
}

function previewFromPayload(
  payload: TripPlaceRequest,
  source: Exclude<PlacePreviewSource, "empty">,
  dayNumber: number,
  previewId: string,
): PlacePreviewCandidate {
  return {
    ...payload,
    label: payload.label,
    meta: payload.meta ?? "",
    previewId,
    source,
    dayNumber,
  };
}

function previewFromRecommendation(
  item: Recommendation,
  index: number,
  dayNumber: number,
): PlacePreviewCandidate {
  const time = recommendationPlaceTime(item);
  return previewFromPayload(
    recommendationPlacePayload(item, time),
    "recommendation",
    dayNumber,
    recommendationPreviewId(item, index),
  );
}

function placeSearchCandidatePayload(
  item: PlaceSearchCandidate,
  time: string | undefined,
): TripPlaceRequest {
  return {
    time: time ?? "",
    label: item.title,
    meta: item.meta,
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.categoryName ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: item.sourceProvider ?? null,
    externalPlaceId: item.externalPlaceId ?? item.id ?? null,
  };
}

function previewFromSearchCandidate(
  item: PlaceSearchCandidate,
  dayNumber: number,
  source: "searchPreview" | "selected",
  time = "",
): PlacePreviewCandidate {
  return previewFromPayload(
    placeSearchCandidatePayload(item, time),
    source,
    dayNumber,
    item.id ??
      item.externalPlaceId ??
      `${item.title}:${item.address ?? item.meta}`,
  );
}

function placePreviewMarker(
  place: PlacePreviewCandidate,
): KakaoMapMarker | null {
  const query =
    place.address?.trim() || place.label.trim() || place.meta?.trim() || null;
  if (!place.label.trim() && !query) return null;
  return {
    id: place.previewId,
    label: place.label,
    subtitle: place.address || place.meta || null,
    latitude: place.latitude ?? null,
    longitude: place.longitude ?? null,
    query,
  };
}

function placeSearchText(item: PlaceSearchCandidate): string {
  return [item.title, item.meta, item.categoryName, item.address]
    .filter((part): part is string => Boolean(part))
    .join(" ")
    .toLocaleLowerCase("ko-KR");
}

const TRIP_CONFLICT_MESSAGE =
  "다른 사용자가 먼저 일정을 수정했어요. 최신 내용을 확인한 뒤 다시 저장해 주세요.";

function isTripConflict(error: unknown): boolean {
  return isApiError(error) && error.status === 409;
}

export function isMissingTripDay(error: unknown): boolean {
  return (
    isApiError(error) &&
    error.status === 404 &&
    error.detail === "Trip day not found"
  );
}

export function ItineraryDetailPage() {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { removeAddedPolicy } = useSession();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeDay, setActiveDay] = useState(1);
  const [selectedMapPlaceId, setSelectedMapPlaceId] = useState<string | null>(
    () => searchParams.get("place"),
  );
  const {
    data: loadedTrip,
    error,
    isLoading,
  } = useAsyncResource(() => {
    if (!tripId) return Promise.reject(new Error("Trip not found"));
    return appDataApi.getTrip(tripId);
  }, [tripId]);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [placeEditor, setPlaceEditor] = useState<
    | { mode: "add"; dayNumber: number }
    | { mode: "edit"; dayNumber: number; place: ItineraryPlace }
    | null
  >(null);
  const [placeForm, setPlaceForm] = useState<TripPlaceRequest>({
    time: "",
    label: "",
    meta: "",
  });
  const [placeError, setPlaceError] = useState("");
  const [placeDeleteError, setPlaceDeleteError] = useState("");
  const [isSavingPlace, setIsSavingPlace] = useState(false);
  const [placeSearchQuery, setPlaceSearchQuery] = useState("");
  const [placeSearchCandidates, setPlaceSearchCandidates] = useState<
    PlaceSearchCandidate[]
  >([]);
  const [placeBasket, setPlaceBasket] = useState<PlaceBasketItem[]>([]);
  const [batchPlaceRecovery, setBatchPlaceRecovery] =
    useState<BatchPlaceRecovery>({ kind: "none" });
  const [isLoadingPlaceSearch, setIsLoadingPlaceSearch] = useState(false);
  const [placeSearchError, setPlaceSearchError] = useState("");
  const [placePreview, setPlacePreview] = useState<PlacePreviewState>({
    source: "empty",
    place: null,
  });
  const [placeSaveEligibility, setPlaceSaveEligibility] =
    useState<PlaceSaveEligibility>("empty");
  const [movingPlaceId, setMovingPlaceId] = useState<string | null>(null);
  const [draggingPlaceId, setDraggingPlaceId] = useState<string | null>(null);
  // 추천 미리보기 시간 수정창은 한 번에 하나만 열린다. <details>가 서로를
  // 모르므로 부모가 열린 카드를 하나 들고 있어야 한다.
  const [openTimeEditorId, setOpenTimeEditorId] = useState<string | null>(null);
  const [dragOverDay, setDragOverDay] = useState<number | null>(null);
  const [isDragOverDayRow, setIsDragOverDayRow] = useState(false);
  const [crossDayDragPreview, setCrossDayDragPreview] = useState<
    { dayNumber: number; position: number } | null
  >(null);
  const [moveError, setMoveError] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [placeDetail, setPlaceDetail] = useState<{
    dayNumber: number;
    place: ItineraryPlace;
  } | null>(null);
  const [deleteCandidatePlace, setDeleteCandidatePlace] =
    useState<ItineraryPlace | null>(null);
  const [dateEditor, setDateEditor] = useState<{
    startDate: string;
    endDate: string;
    overflowPlaceStrategy: "moveToLastDay" | "delete";
    error: string;
    isSaving: boolean;
  } | null>(null);
  const [removingPolicySlug, setRemovingPolicySlug] = useState<string | null>(
    null,
  );
  const [policyRemoveError, setPolicyRemoveError] = useState("");
  const [hiddenRoutePolicySlugs, setHiddenRoutePolicySlugs] = useState<
    Set<string>
  >(() => new Set());
  const [placeDraftNotice, setPlaceDraftNotice] = useState("");
  const [recommendationPreview, setRecommendationPreview] =
    useState<RecommendationPreviewState>({
      status: "idle",
      places: [],
      selectedPreviewIds: [],
      timeline: {},
      error: "",
  });
  const placeEditorSessionRef = useRef(0);
  const placeSearchRequestRef = useRef(0);
  const placeSearchAbortControllerRef = useRef<AbortController | null>(null);
  const placeBasketIdRef = useRef(0);
  const placeDragAutoSwitchTimerRef = useRef<number | null>(null);
  const dayTabsRef = useRef<HTMLDivElement | null>(null);
  const dayStripDragScroll = useDragScroll(dayTabsRef);
  const dayEdgeLeftRef = useRef<HTMLDivElement | null>(null);
  const dayEdgeRightRef = useRef<HTMLDivElement | null>(null);
  /* 자동 스크롤을 멈춰야 할 때 이 값을 올린다. canPlaceDragAutoScroll 의
     정체성이 바뀌고, 그게 dnd-kit 자동 스크롤 effect 의 의존성이라
     effect 가 다시 돌면서 스스로 clearAutoScrollInterval() 을 부른다. */
  const [autoScrollBrakeTick, setAutoScrollBrakeTick] = useState(0);
  const autoScrollBrakedRef = useRef(false);
  const placeDragScrollLockRef = useRef(false);
  const placeDragPointerRef = useRef<{ x: number; y: number } | null>(null);
  const placeDragContentBoundsRef = useRef<{
    activeBottomWithMargin: number;
  } | null>(null);
  const placePreviewRef = useRef<PlacePreviewState>({
    source: "empty",
    place: null,
  });
  const dayNumbers = trip ? tripDayNumbers(trip.days) : [];
  const visibleDay = dayNumbers.includes(activeDay)
    ? activeDay
    : (dayNumbers[0] ?? 1);
  const dayPlaces = trip?.days[visibleDay] ?? [];
  const isPreviewActive =
    recommendationPreview.status === "ready" ||
    recommendationPreview.status === "saving";
  const previewDayPlaces = isPreviewActive
    ? recommendationPreview.places.filter(
        (place) => place.dayNumber === visibleDay,
      )
    : [];
  const displayedPlaces: DisplayedPlace[] = isPreviewActive
    ? (recommendationPreview.timeline[visibleDay] ?? [])
    : dayPlaces;
  const timeWarningPlaceIds = timeOrderWarningPlaceIds(displayedPlaces);
  const selectedPreviewMapPlace = isPreviewActive
    ? (previewDayPlaces.find(
        (place) => place.previewId === selectedMapPlaceId,
      ) ?? null)
    : null;
  const mapPlaces: DisplayedPlace[] = selectedPreviewMapPlace
    ? [timelinePlaceFromPreviewPlace(selectedPreviewMapPlace)]
    : displayedPlaces;
  const sortablePlaceIds = displayedPlaces.flatMap((place) => {
    const sortableId = displayedPlaceSortableId(place);
    return sortableId ? [sortableId] : [];
  });
  const sortableIdsByDay = dayNumbers.reduce<Record<number, string[]>>(
    (idsByDay, day) => {
      const places = isPreviewActive
        ? (recommendationPreview.timeline[day] ?? [])
        : (trip?.days[day] ?? []);
      idsByDay[day] = displayedPlaceSortableIds(places);
      return idsByDay;
    },
    {},
  );
  const stayLabel = formatStayLabel(dayNumbers.length || 3);
  const canManageTripStatus =
    trip?.currentUserRole === "owner" || trip?.currentUserRole === "editor";
  const [isInviteSheetOpen, setIsInviteSheetOpen] = useState(false);
  const isTripViewer = Boolean(trip && !canManageTripStatus);
  const canEditTrip = Boolean(canManageTripStatus);
  const activeDraggingPlaceLabel = draggingPlaceLabel(
    trip,
    draggingPlaceId,
    isPreviewActive ? recommendationPreview.timeline : undefined,
  );
  const draggingPlaceSortableId = draggingPlaceId
    ? isPreviewActive
      ? draggingPlaceId
      : placeDragId(draggingPlaceId)
    : null;
  const isCrossDayPlaceDrag = isCrossDayTimelineDrag({
    activeSortableId: draggingPlaceSortableId,
    sortableIdsByDay,
    visibleDay,
  });
  /**
   * 다른 날짜에서 끌고 온 카드가 들어갈 자리. 이 값이 있으면 활성 카드의 id를
   * 보이는 날짜의 SortableContext에 끼워 넣어, 같은 날짜 이동과 똑같이
   * dnd-kit이 주변 카드를 밀어내게 한다.
   */
  const crossDayGhostPosition =
    isCrossDayPlaceDrag && crossDayDragPreview?.dayNumber === visibleDay
      ? crossDayDragPreview.position
      : null;
  const timelineGhostPosition =
    crossDayGhostPosition != null && draggingPlaceSortableId
      ? crossDayGhostPosition
      : null;
  const timelineSortableIds =
    timelineGhostPosition == null || !draggingPlaceSortableId
      ? sortablePlaceIds
      : buildTimelineSortableIds({
          activeSortableId: draggingPlaceSortableId,
          ghostPosition: timelineGhostPosition,
          sortableIds: sortablePlaceIds,
        });
  const timelineRenderItems = buildTimelineRenderItems({
    ghostPosition: timelineGhostPosition,
    items: displayedPlaces,
  });
  const tripPeople = trip?.people.length
    ? trip.people
    : ["지영", "민수", "수현"];
  const tripRegionEmojiLabel = trip
    ? getTripRegionEmojiFromTitle(trip.title)
    : "🧳";
  const tripDdayLabel = trip ? formatTripDday(trip.dates) : "D-day";
  const dateEditorDayCount = dateEditor
    ? dayCountFromDateInputs(dateEditor.startDate, dateEditor.endDate)
    : null;
  const dateEditorOverflowPlaceCount =
    trip && dateEditorDayCount != null && dateEditorDayCount < dayNumbers.length
      ? dayNumbers
          .filter((day) => day > dateEditorDayCount)
          .reduce((sum, day) => sum + (trip.days[day]?.length ?? 0), 0)
      : 0;
  const routeLinkedPolicy =
    (location.state as TripDetailLocationState | null)?.linkedPolicy ?? null;
  const linkedPolicies = linkedTripPoliciesForDisplay(
    trip?.linkedPolicies,
    routeLinkedPolicy,
    hiddenRoutePolicySlugs,
  );
  const recommendedPolicies = trip?.recommendedPolicies ?? [];
  const hasLinkedPolicyFallback =
    linkedPolicies.length === 0 && hasPolicySaving(trip?.expectedSaving);
  const dragSensors = useSensors(
    /* 마우스는 홀드가 아니라 거리 기준이다. 여기에 지연을 걸면 안 된다. */
    useSensor(MouseSensor, {
      activationConstraint: { distance: PLACE_DRAG_MOUSE_DISTANCE_PX },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: PLACE_DRAG_TOUCH_DELAY_MS,
        tolerance: PLACE_DRAG_TOUCH_TOLERANCE_PX,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const clearPlaceDragAutoSwitch = useCallback(() => {
    if (placeDragAutoSwitchTimerRef.current !== null) {
      window.clearTimeout(placeDragAutoSwitchTimerRef.current);
    }
    placeDragAutoSwitchTimerRef.current = null;
  }, []);
  const updatePlaceDragPointer = useCallback((event: Event) => {
    if (event instanceof PointerEvent || event instanceof MouseEvent) {
      placeDragPointerRef.current = {
        x: event.clientX,
        y: event.clientY,
      };
      return;
    }
    if (event instanceof TouchEvent) {
      const touch = event.touches[0] ?? event.changedTouches[0] ?? null;
      if (touch) {
        placeDragPointerRef.current = {
          x: touch.clientX,
          y: touch.clientY,
        };
      }
    }
  }, []);
  const getPointerVerifiedTimelineOverId = useCallback(
    (overId: unknown): unknown | null => {
      const targetDay = parseDayDropId(overId);
      if (!targetDay) return overId;
      const dayTabElement = document.querySelector<HTMLElement>(
        `[data-day-drop-id="${dayDropId(targetDay)}"]`,
      );
      return resolvePointerVerifiedTimelineOverId({
        dayNumbers,
        overId,
        pointer: placeDragPointerRef.current,
        rectByDay: {
          [targetDay]: dayTabElement?.getBoundingClientRect() ?? null,
        },
      });
    },
    [dayNumbers],
  );
  // 빈 날짜와 마지막 카드 아래 빈 공간을 위한 드롭 대상. 카드 사이 슬롯은
  // height:0이라 포인터가 맞출 수 없어 이 영역이 유일한 후보가 된다.
  const { setNodeRef: setTimelineAreaRef } = useDroppable({
    id: dayAreaDropId(visibleDay),
  });
  const getDayZoneRect = useCallback(() => {
    const actionsElement = document.querySelector<HTMLElement>(
      "[data-itinerary-actions]",
    );
    const dayTabsElement = document.querySelector<HTMLElement>(
      "[data-itinerary-day-tabs]",
    );
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    return resolveDayZoneRect({
      actionsRect: actionsElement?.getBoundingClientRect() ?? null,
      dayTabsRect: dayTabsElement?.getBoundingClientRect() ?? null,
      timelineRect: timelineElement?.getBoundingClientRect() ?? null,
    });
  }, []);
  const getPointerDayTarget = useCallback((): number | null => {
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    const rectByDay = Object.fromEntries(
      dayNumbers.map((dayNumber) => {
        const dayTabElement = document.querySelector<HTMLElement>(
          `[data-day-drop-id="${dayDropId(dayNumber)}"]`,
        );
        return [dayNumber, dayTabElement?.getBoundingClientRect() ?? null];
      }),
    );
    return resolvePointerDayTarget({
      dayNumbers,
      pointer: placeDragPointerRef.current,
      rectByDay,
      timelineRect: timelineElement?.getBoundingClientRect() ?? null,
      dayZoneRect: getDayZoneRect(),
    });
  }, [dayNumbers, getDayZoneRect]);
  const isPointerOverDayRow = useCallback((): boolean => {
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    // 탭 행이 아니라 Day 존 전체를 본다. 탭 사이 간격과 탭·타임라인 사이
    // 죽은 구간에서도 작은 오버레이 카드가 끊기지 않는다.
    return shouldUseDayRowDragOverlay({
      pointer: placeDragPointerRef.current,
      dayTabsRect: getDayZoneRect(),
      timelineRect: timelineElement?.getBoundingClientRect() ?? null,
    });
  }, [getDayZoneRect]);
  const getClosestCurrentDayTimelinePosition = useCallback(
    (activeSortableId: string | null): number => {
      const items = Array.from(
        document.querySelectorAll<HTMLElement>(
          "[data-itinerary-timeline] [data-sortable-id]:not([data-timeline-ghost])",
        ),
      ).map((item) => {
        const rect = item.getBoundingClientRect();
        return {
          sortableId: item.dataset.sortableId ?? "",
          top: rect.top,
          bottom: rect.bottom,
        };
      });
      return resolveSameDayInsertPosition({
        items,
        activeSortableId,
        pointerY: placeDragPointerRef.current?.y ?? null,
      });
    },
    [],
  );
  /**
   * 드래그 중에는 스크롤 체이닝(당겨서 새로고침 등)과 smooth 스크롤만 끈다.
   * 스크롤 자체를 막으면 dnd-kit 자동 스크롤과 휠까지 죽는다. 시작 위치로
   * 되돌리는 로직도 두지 않는다 — 자동 스크롤로 내려간 사용자를 낚아챈다.
   */
  const lockPlaceDragViewportScroll = useCallback(() => {
    if (typeof window === "undefined" || placeDragScrollLockRef.current) return;
    const appContainer = document.querySelector<HTMLElement>(".app-container");
    placeDragScrollLockRef.current = true;
    document.documentElement.classList.add("itinerary-place-drag-scroll-locked");
    document.body.classList.add("itinerary-place-drag-scroll-locked");
    appContainer?.classList.add("itinerary-place-drag-scroll-locked");
    // 날짜를 바꿔도 문서가 짧아지지 않게 현재 높이를 바닥으로 고정한다.
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    if (timelineElement) {
      const lockedHeight = resolveTimelineHeightLock(
        timelineElement.getBoundingClientRect().height,
      );
      if (lockedHeight) timelineElement.style.minHeight = lockedHeight;
    }
  }, []);
  const unlockPlaceDragViewportScroll = useCallback(() => {
    if (!placeDragScrollLockRef.current) return;
    const appContainer = document.querySelector<HTMLElement>(".app-container");
    placeDragScrollLockRef.current = false;
    document.documentElement.classList.remove(
      "itinerary-place-drag-scroll-locked",
    );
    document.body.classList.remove("itinerary-place-drag-scroll-locked");
    appContainer?.classList.remove("itinerary-place-drag-scroll-locked");
    // 인라인 값을 지우면 app.css의 min-height: clamp(...)가 다시 적용된다.
    // 계산값이 바뀌므로 .timeline의 min-height 트랜지션이 걸린다.
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    timelineElement?.style.removeProperty("min-height");
  }, []);
  /**
   * 날짜가 바뀌면 타임라인 높이가 달라진다. 커졌으면 고정값을 올려서,
   * 나중에 짧은 날짜로 돌아갔을 때 문서가 줄지 않게 한다.
   */
  const raiseTimelineHeightLock = useCallback(() => {
    if (!placeDragScrollLockRef.current) return;
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    if (!timelineElement) return;
    const raised = resolveRaisedTimelineHeightLock(
      timelineElement.style.minHeight || null,
      timelineElement.getBoundingClientRect().height,
    );
    if (raised) timelineElement.style.minHeight = raised;
  }, []);
  useEffect(() => {
    if (!draggingPlaceId) return;
    raiseTimelineHeightLock();
  }, [draggingPlaceId, visibleDay, raiseTimelineHeightLock]);
  const canPlaceDragAutoScroll = useCallback((element: Element): boolean => {
    // 멈춤 기준은 Day 탭이 아니라 그 위의 장소추가 버튼 줄이다. 버튼 줄까지
    // 보이는 지점에서 멈춰야 Day 탭이 화면 위 가장자리에 붙지 않는다.
    const actionsElement = document.querySelector<HTMLElement>(
      "[data-itinerary-actions]",
    );
    return shouldAllowPlaceDragAutoScroll({
      pointerY: placeDragPointerRef.current?.y ?? null,
      containerRect: element.getBoundingClientRect(),
      anchorRect: actionsElement?.getBoundingClientRect() ?? null,
      thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
    });
    // autoScrollBrakeTick 은 이 함수의 정체성을 바꾸기 위한 것이다.
    // dnd-kit 은 canScroll 을 의존성으로 들고 있어, 정체성이 바뀌면
    // 자동 스크롤 effect 가 다시 돌며 멈출지 다시 판단한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoScrollBrakeTick]);
  const restrictPlaceDragToContent = useCallback<Modifier>(({ transform }) => {
    const bounds = placeDragContentBoundsRef.current;
    const appContainer = document.querySelector<HTMLElement>(".app-container");
    if (!bounds || !appContainer) return transform;
    // 날짜가 바뀌면 문서 높이도 바뀐다. 드래그 시작 시점 값을 쓰면 클램프가 튄다.
    const contentBottom =
      appContainer.getBoundingClientRect().top +
      appContainer.scrollHeight -
      appContainer.scrollTop;
    return {
      ...transform,
      y: Math.min(transform.y, contentBottom - bounds.activeBottomWithMargin),
    };
  }, []);
  const refreshTripAfterConflict = async (
    setError: (message: string) => void,
  ) => {
    if (!trip) return;
    const latestTrip = await appDataApi.getTrip(trip.id).catch(() => null);
    if (latestTrip) setTrip(latestTrip);
    setError(TRIP_CONFLICT_MESSAGE);
  };
  const refreshTripQuietly = async (tripIdToRefresh: string) => {
    const latestTrip = await appDataApi
      .getTrip(tripIdToRefresh)
      .catch(() => null);
    if (latestTrip) setTrip(latestTrip);
    return latestTrip;
  };
  const updatePlacePreview = (nextPreview: PlacePreviewState) => {
    placePreviewRef.current = nextPreview;
    setPlacePreview(nextPreview);
  };
  const clearPlacePreview = () => {
    updatePlacePreview({ source: "empty", place: null });
    setPlaceSaveEligibility("empty");
  };

  useEffect(() => {
    if (loadedTrip) setTrip(loadedTrip);
  }, [loadedTrip]);

  useEffect(() => {
    if (dayNumbers.length > 0) {
      const requestedDay = Number(searchParams.get("day"));
      setActiveDay(
        dayNumbers.includes(requestedDay) ? requestedDay : dayNumbers[0],
      );
    }
  }, [trip?.id]);

  useEffect(() => {
    const nextPlaceId = searchParams.get("place");
    setSelectedMapPlaceId((currentPlaceId) => {
      if (
        !nextPlaceId &&
        currentPlaceId &&
        recommendationPreview.places.some(
          (place) => place.previewId === currentPlaceId,
        )
      ) {
        return currentPlaceId;
      }
      return nextPlaceId;
    });
  }, [recommendationPreview.places, searchParams]);

  useEffect(() => {
    if (trip && tripId && trip.id !== tripId) {
      navigate(`/trips/${trip.id}`, { replace: true });
    }
  }, [navigate, trip, tripId]);

  useEffect(() => {
    if (!draggingPlaceId) return undefined;
    window.addEventListener("pointermove", updatePlaceDragPointer, {
      passive: true,
    });
    window.addEventListener("touchmove", updatePlaceDragPointer, {
      passive: true,
    });
    return () => {
      window.removeEventListener("pointermove", updatePlaceDragPointer);
      window.removeEventListener("touchmove", updatePlaceDragPointer);
    };
  }, [draggingPlaceId, updatePlaceDragPointer]);

  useEffect(() => {
    const handleWindowWheel = (event: WheelEvent) => {
      const appContainer = document.querySelector<HTMLElement>(".app-container");
      if (!appContainer) return;
      // 휠은 window까지 버블링된다. 시트처럼 안쪽에 스크롤러가 있으면
      // 브리지가 기본 스크롤을 취소하고 뒤 화면을 스크롤해버린다.
      const path: { canScrollY: boolean; isAppContainer: boolean }[] = [];
      let node = event.target instanceof Element ? event.target : null;
      while (node) {
        path.push({
          canScrollY: node.scrollHeight > node.clientHeight,
          isAppContainer: node === appContainer,
        });
        if (node === appContainer) break;
        node = node.parentElement;
      }
      if (isWheelInsideNestedScroller(path)) return;
      if (!shouldForwardWindowWheelToAppScroll(event, appContainer)) return;

      event.preventDefault();
      appContainer.scrollTop += event.deltaY;
    };

    window.addEventListener("wheel", handleWindowWheel, { passive: false });
    return () => {
      window.removeEventListener("wheel", handleWindowWheel);
    };
  }, []);

  const updateDetailSearchParams = (nextValues: {
    day?: number;
    place?: string | null;
  }) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (nextValues.day) next.set("day", String(nextValues.day));
        if ("place" in nextValues) {
          if (nextValues.place) next.set("place", nextValues.place);
          else next.delete("place");
        }
        return next;
      },
      { replace: true },
    );
  };

  /* 편집기의 날짜 선택지. 일정의 모든 날짜가 들어간다. */
  const placeEditorDayOptions = dayNumbers.map((day) => ({
    dayNumber: day,
    dateLabel: trip ? formatDayDateLabel(trip.dates, day) : "",
    count: trip ? (trip.days[day]?.length ?? 0) : 0,
  }));

  /* 편집기를 열면 고른 날짜가 바로 보여야 한다. 35일 일정에서 Day 30 을
     수정하는데 줄이 맨 앞에 있으면 어디가 선택됐는지 알 수 없다. */
  const scrollSelectedDayIntoView = useCallback(
    (node: HTMLButtonElement | null) => {
      if (!node) return;
      const strip = node.parentElement;
      if (!strip) return;
      strip.scrollLeft = Math.max(
        0,
        node.offsetLeft - (strip.clientWidth - node.offsetWidth) / 2,
      );
    },
    [],
  );

  const selectTripDay = (day: number) => {
    setActiveDay(day);
    setSelectedMapPlaceId(null);
    updateDetailSearchParams({ day, place: null });
  };

  /* 날짜를 한 칸씩 옮긴다. 이동영역·휠·화살표가 모두 이걸 쓴다. */
  const shiftVisibleDay = useCallback(
    (step: number) => {
      if (!dayNumbers.length) return;
      const first = dayNumbers[0];
      const last = dayNumbers[dayNumbers.length - 1];
      setActiveDay((current) => {
        const target = Math.min(Math.max(current + step, first), last);
        if (target !== current) {
          updateDetailSearchParams({ day: target, place: null });
        }
        return target;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dayNumbers.join(",")],
  );

  /* 보고 있는 날짜를 스트립 가운데로. 양 끝 여백 덕분에 첫날·마지막날도 중앙에 선다.
     드래그 중에는 부드러운 스크롤을 쓰지 않는다. 포인터 판정과 어긋난다. */
  const layoutDayStrip = useCallback((smooth: boolean) => {
    const strip = dayTabsRef.current;
    if (!strip) return;
    const first = strip.firstElementChild as HTMLElement | null;
    const last = strip.lastElementChild as HTMLElement | null;
    if (!first || !last) return;

    const pad = resolveDayStripPadding(
      strip.clientWidth,
      first.offsetWidth,
      last.offsetWidth,
    );
    strip.style.paddingLeft = `${pad.left}px`;
    strip.style.paddingRight = `${pad.right}px`;

    const active = strip.querySelector<HTMLElement>(
      `[data-day-drop-id="${dayDropId(visibleDay)}"]`,
    );
    if (!active) return;
    const left = resolveDayStripScrollLeft({
      tabOffsetLeft: active.offsetLeft,
      tabWidth: active.offsetWidth,
      containerWidth: strip.clientWidth,
      scrollWidth: strip.scrollWidth,
    });
    if (typeof strip.scrollTo === "function") {
      strip.scrollTo({ left, behavior: smooth ? "smooth" : "auto" });
    } else {
      strip.scrollLeft = left;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleDay]);

  useEffect(() => {
    layoutDayStrip(!draggingPlaceId);
  }, [layoutDayStrip, dayNumbers.length, draggingPlaceId]);

  /* 창 크기가 바뀌면 여백이 낡는다. 여백은 컨테이너 폭으로 계산하기 때문이다.
     화면 회전이나 창 크기 변경 뒤 날짜를 바꾸기 전까지 어긋난 채로 남았다. */
  useEffect(() => {
    const onResize = () => layoutDayStrip(false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [layoutDayStrip]);

  /* 이동영역 표시를 그린다. 매 포인터 이동마다 리렌더하면 무거우므로
     상태가 아니라 DOM 을 직접 만진다. 색은 쓰지 않고 어둠과 화살표로만 알린다. */
  const paintDayEdges = useCallback(
    (rect: DOMRect, pointerX: number | null) => {
      const left = dayEdgeLeftRef.current;
      const right = dayEdgeRightRef.current;
      if (!left || !right) return;
      for (const [el, side] of [
        [left, "left"],
        [right, "right"],
      ] as const) {
        el.style.top = `${rect.top}px`;
        el.style.height = `${rect.height}px`;
        el.style.width = `${DAY_EDGE_WIDTH_PX}px`;
        if (side === "left") el.style.left = `${rect.left}px`;
        else el.style.left = `${rect.right - DAY_EDGE_WIDTH_PX}px`;
      }
      const zone = resolveDayEdgeZone({
        pointerX,
        left: rect.left,
        right: rect.right,
      });
      for (const [el, side] of [
        [left, -1],
        [right, 1],
      ] as const) {
        const mark = el.firstElementChild as HTMLElement | null;
        if (!mark) continue;
        if (zone !== side || pointerX == null) {
          mark.style.opacity = "";
          mark.style.transform = "";
          continue;
        }
        const depth = resolveDayEdgeDepth({
          pointerX,
          left: rect.left,
          right: rect.right,
          zone: side,
        });
        mark.style.opacity = (0.4 + 0.6 * depth).toFixed(2);
        mark.style.transform = `scale(${(1 + 0.35 * depth).toFixed(2)})`;
      }
    },
    [],
  );

  /* 좌우 이동영역. 포인터가 멈춰 있어도 진행해야 하므로 이벤트가 아니라 타이머로 돈다.
     pointermove 안에서 처리하면 손가락을 흔들어야만 날짜가 넘어간다. */
  useEffect(() => {
    if (!draggingPlaceId) return;
    let zone: -1 | 0 | 1 = 0;
    let nextAt = 0;
    autoScrollBrakedRef.current = false;
    /* 첫 틱(50ms) 전에 요소가 엉뚱한 자리에 잠깐 보이지 않도록 즉시 한 번 그린다. */
    const startContainer = document.querySelector<HTMLElement>(".app-container");
    if (startContainer) {
      paintDayEdges(
        startContainer.getBoundingClientRect(),
        placeDragPointerRef.current?.x ?? null,
      );
    }
    const timer = window.setInterval(() => {
      const container = document.querySelector<HTMLElement>(".app-container");
      const pointer = placeDragPointerRef.current;
      if (!container) return;
      if (!pointer) {
        paintDayEdges(container.getBoundingClientRect(), null);
        zone = 0;
        nextAt = 0;
        return;
      }
      const rect = container.getBoundingClientRect();
      paintDayEdges(rect, pointer.x);

      /* 자동 스크롤 제동. dnd-kit 은 한 번 시작한 스크롤을 멈출 판정을
         포인터가 멈춰 있는 동안 다시 하지 않는다. 여기서 직접 붙잡는다. */
      const actions = document.querySelector<HTMLElement>(
        "[data-itinerary-actions]",
      );
      if (actions) {
        /* 스크롤을 되돌리지 않는다. 되돌리면 dnd-kit 이 다시 올리고 우리가 다시
           내리는 싸움이 되어 화면이 드드득거린다. 대신 canScroll 의 정체성을
           바꿔 dnd-kit 이 스스로 멈추게 한다. 한 번만 알리면 된다. */
        const allowed = shouldAllowPlaceDragAutoScroll({
          pointerY: pointer.y,
          containerRect: rect,
          anchorRect: actions.getBoundingClientRect(),
          thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
        });
        if (!allowed && !autoScrollBrakedRef.current) {
          autoScrollBrakedRef.current = true;
          setAutoScrollBrakeTick((tick) => tick + 1);
        } else if (allowed && autoScrollBrakedRef.current) {
          autoScrollBrakedRef.current = false;
        }
      }
      const next = resolveDayEdgeZone({
        pointerX: pointer.x,
        left: rect.left,
        right: rect.right,
      });
      if (next === 0) {
        zone = 0;
        nextAt = 0;
        return;
      }
      if (next !== zone) {
        zone = next;
        nextAt = Date.now() + DAY_EDGE_FIRST_DELAY_MS;
        return;
      }
      if (Date.now() < nextAt) return;
      const depth = resolveDayEdgeDepth({
        pointerX: pointer.x,
        left: rect.left,
        right: rect.right,
        zone: next,
      });
      shiftVisibleDay(next);
      nextAt = Date.now() + resolveDayEdgeInterval(depth);
    }, 50);
    return () => window.clearInterval(timer);
  }, [draggingPlaceId, shiftVisibleDay, paintDayEdges]);

  /* 드래그 중 키보드로 날짜를 옮긴다.
     휠은 쓰지 않는다. 드래그 중에도 휠은 목록 상하 스크롤을 맡아야 하고,
     둘을 같이 걸면 한 번 굴릴 때 스크롤과 날짜 전환이 동시에 일어난다. */
  useEffect(() => {
    if (!draggingPlaceId) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        shiftVisibleDay(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        shiftVisibleDay(1);
      } else if (event.key === "Home") {
        event.preventDefault();
        shiftVisibleDay(-dayNumbers.length);
      } else if (event.key === "End") {
        event.preventDefault();
        shiftVisibleDay(dayNumbers.length);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [draggingPlaceId, shiftVisibleDay, dayNumbers.length]);

  const openDateEditor = () => {
    if (!trip) return;
    const parsedDates = parseTripDateInputs(trip.dates);
    if (!parsedDates) {
      setNotice("현재 여행기간을 읽지 못했어요. 새로고침 후 다시 시도해 주세요.");
      return;
    }
    setDateEditor({
      ...parsedDates,
      overflowPlaceStrategy: "moveToLastDay",
      error: "",
      isSaving: false,
    });
  };

  const submitDateEditor = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trip || !dateEditor || dateEditor.isSaving) return;
    const nextDayCount = dayCountFromDateInputs(
      dateEditor.startDate,
      dateEditor.endDate,
    );
    if (nextDayCount == null || nextDayCount < 1) {
      setDateEditor((current) =>
        current
          ? {
              ...current,
              error: "종료일은 시작일과 같거나 이후여야 합니다.",
            }
          : current,
      );
      return;
    }

    setDateEditor((current) =>
      current ? { ...current, error: "", isSaving: true } : current,
    );
    try {
      const updatedTrip = await appDataApi.updateTripSettings(trip.id, {
        expectedRevision: trip.revision,
        startDate: dateEditor.startDate,
        endDate: dateEditor.endDate,
        overflowPlaceStrategy: dateEditor.overflowPlaceStrategy,
      });
      const updatedDayNumbers = tripDayNumbers(updatedTrip.days);
      const nextActiveDay = updatedDayNumbers.includes(visibleDay)
        ? visibleDay
        : (updatedDayNumbers[updatedDayNumbers.length - 1] ?? 1);
      setTrip(updatedTrip);
      setDateEditor(null);
      setActiveDay(nextActiveDay);
      setSelectedMapPlaceId(null);
      updateDetailSearchParams({ day: nextActiveDay, place: null });
      setNotice("여행기간을 수정했어요.");
    } catch (nextError) {
      setDateEditor((current) =>
        current
          ? {
              ...current,
              error: isApiError(nextError)
                ? nextError.message
                : "여행기간을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.",
              isSaving: false,
            }
          : current,
      );
    }
  };

  const selectMapPlace = (placeId: string | null) => {
    setSelectedMapPlaceId(placeId);
    if (
      placeId &&
      recommendationPreview.places.some((place) => place.previewId === placeId)
    )
      return;
    updateDetailSearchParams({ day: visibleDay, place: placeId });
  };

  const selectRecommendationPreviewMapPlace = (previewId: string) => {
    setSelectedMapPlaceId(previewId);
    updateDetailSearchParams({ day: visibleDay, place: null });
  };

  const showEditPermissionRequired = () => {
    setNotice(
      "편집 권한이 필요해요. 이 일정은 보기 권한으로 참여 중이라 장소 추가나 추천 일정 저장을 할 수 없어요.",
    );
    window.setTimeout(() => setNotice(null), 2200);
  };

  const openRecommendationPreview = async () => {
    if (!trip) return;
    if (!canEditTrip) {
      showEditPermissionRequired();
      return;
    }
    setRecommendationPreview({
      status: "loading",
      places: [],
      selectedPreviewIds: [],
      timeline: {},
      error: "",
    });
    try {
      const recommendations = await appDataApi.listRecommendations(trip.id);
      const nextPlaces = previewPlacesFromRecommendations(
        recommendations,
        dayNumbers,
        visibleDay,
      );
      setRecommendationPreview({
        status: "ready",
        places: nextPlaces,
        selectedPreviewIds: [],
        timeline: recommendationPreviewTimelineFromTrip(
          trip,
          nextPlaces,
          dayNumbers,
        ),
        error: "",
      });
    } catch {
      setRecommendationPreview({
        status: "idle",
        places: [],
        selectedPreviewIds: [],
        timeline: {},
        error: "추천 일정을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
      });
    }
  };

  const commitRecommendationPreview = async ({
    saveAllCandidates,
  }: {
    saveAllCandidates: boolean;
  }) => {
    if (!trip) return;
    const selectedPreviewIds = new Set(
      recommendationPreview.selectedPreviewIds,
    );
    const timeline = recommendationPreview.timeline;
    const candidatePlaces = Object.entries(timeline).flatMap(
      ([dayText, places]) =>
        places
          .filter(
            (place) =>
              place.isRecommendationPreview &&
              place.previewId &&
              (saveAllCandidates || selectedPreviewIds.has(place.previewId)),
          )
          .map((place) => ({ dayNumber: Number(dayText), place })),
    );
    const invalidTimePlace = Object.values(timeline)
      .flat()
      .find((place) => !isTenMinutePlaceTime(place.time ?? ""));
    if (invalidTimePlace) {
      setRecommendationPreview((current) => ({
        ...current,
        status: "ready",
        error: `${invalidTimePlace.label} 방문 시간은 10분 단위로 입력해 주세요.`,
      }));
      return;
    }
    setRecommendationPreview((current) => ({
      ...current,
      status: "saving",
      error: "",
    }));
    const savedPreviewIds = new Set<string>();
    const addedPlaceIdsByPreviewId = new Map<string, string>();
    try {
      let currentTrip = trip;
      for (const places of Object.values(timeline)) {
        for (const place of places) {
          if (place.isRecommendationPreview || !place.id) continue;
          const currentPlace = findTripPlaceById(currentTrip, place.id)?.place;
          if (!currentPlace) continue;
          if ((currentPlace.time ?? "") === (place.time ?? "")) continue;
          currentTrip = await appDataApi.updateTripPlace(
            currentTrip.id,
            place.id,
            {
              ...currentPlace,
              time: place.time ?? "",
              expectedRevision: currentTrip.revision,
            },
          );
        }
      }
      for (const { dayNumber, place } of candidatePlaces) {
        if (!place.previewId) continue;
        const beforeAddTrip = currentTrip;
        currentTrip = await appDataApi.addTripPlace(
          currentTrip.id,
          dayNumber,
          tripPlaceMutationFromDisplayedPlace(place, currentTrip.revision),
        );
        savedPreviewIds.add(place.previewId);
        const addedPlaceId = findAddedPlaceId(
          beforeAddTrip,
          currentTrip,
          dayNumber,
          place,
          new Set(addedPlaceIdsByPreviewId.values()),
        );
        if (addedPlaceId)
          addedPlaceIdsByPreviewId.set(place.previewId, addedPlaceId);
      }
      for (const [dayText, places] of Object.entries(timeline)) {
        const dayNumber = Number(dayText);
        const targetPlaceIds = places
          .map((place) => {
            if (place.isRecommendationPreview)
              return place.previewId
                ? (addedPlaceIdsByPreviewId.get(place.previewId) ?? null)
                : null;
            return place.id ?? null;
          })
          .filter((placeId): placeId is string => Boolean(placeId));
        for (const [index, placeId] of targetPlaceIds.entries()) {
          const currentLocation = findTripPlaceById(currentTrip, placeId);
          if (!currentLocation) continue;
          if (
            currentLocation.dayNumber === dayNumber &&
            currentLocation.index === index
          )
            continue;
          currentTrip = await appDataApi.moveTripPlace(
            currentTrip.id,
            placeId,
            {
              dayNumber,
              position: index + 1,
              expectedRevision: currentTrip.revision,
            },
          );
        }
      }
      setTrip(currentTrip);
      setRecommendationPreview({
        status: "idle",
        places: [],
        selectedPreviewIds: [],
        timeline: {},
        error: "",
      });
      setOpenTimeEditorId(null);
      setSelectedMapPlaceId((currentPlaceId) =>
        currentPlaceId && savedPreviewIds.has(currentPlaceId)
          ? null
          : currentPlaceId,
      );
      setNotice(
        saveAllCandidates
          ? "추천 후보 전체를 기존 일정에 추가했어요."
          : "선택한 추천 후보를 일정에 반영했어요.",
      );
      window.setTimeout(() => setNotice(null), 1800);
    } catch (error) {
      const preservePreviewState = (message: string) => {
        setRecommendationPreview((current) => ({
          ...current,
          status: "ready",
          error: message,
          places: current.places.filter(
            (place) => !savedPreviewIds.has(place.previewId),
          ),
          selectedPreviewIds: current.selectedPreviewIds.filter(
            (previewId) => !savedPreviewIds.has(previewId),
          ),
          timeline: Object.fromEntries(
            Object.entries(current.timeline).map(([day, places]) => [
              day,
              places.filter(
                (place) =>
                  !place.previewId || !savedPreviewIds.has(place.previewId),
              ),
            ]),
          ),
        }));
      };
      if (isTripConflict(error)) {
        await refreshTripAfterConflict((message) =>
          preservePreviewState(message),
        );
      } else {
        await refreshTripQuietly(trip.id);
        preservePreviewState(
          "추천 일정을 저장하지 못했어요. 최신 일정은 다시 불러왔고, 저장되지 않은 미리보기 입력은 그대로 보존했어요.",
        );
      }
    }
  };

  const saveRecommendationPreviewPlace = (previewId: string) => {
    const previewPlace = recommendationPreview.places.find(
      (place) => place.previewId === previewId,
    );
    if (!previewPlace) return;
    if (!isTenMinutePlaceTime(previewPlace.time ?? "")) {
      setRecommendationPreview((current) => ({
        ...current,
        status: "ready",
        error: `${previewPlace.label} 방문 시간은 10분 단위로 입력해 주세요.`,
      }));
      return;
    }
    setRecommendationPreview((current) => {
      const selectedPreviewIds = current.selectedPreviewIds.includes(previewId)
        ? current.selectedPreviewIds
        : [...current.selectedPreviewIds, previewId];
      return {
        ...current,
        status: "ready",
        error: "",
        selectedPreviewIds,
        timeline: Object.fromEntries(
          Object.entries(current.timeline).map(([day, places]) => [
            day,
            places.map((place) =>
              place.previewId === previewId
                ? { ...place, isRecommendationSelected: true }
                : place,
            ),
          ]),
        ),
      };
    });
    setNotice(`${previewPlace.label} 후보를 저장 대상으로 선택했어요.`);
    window.setTimeout(() => setNotice(null), 1800);
  };

  const cancelRecommendationPreviewPlace = (previewId: string) => {
    setRecommendationPreview((current) => ({
      ...current,
      status: current.status === "saving" ? current.status : "ready",
      places: current.places.filter((place) => place.previewId !== previewId),
      selectedPreviewIds: current.selectedPreviewIds.filter(
        (id) => id !== previewId,
      ),
      timeline: Object.fromEntries(
        Object.entries(current.timeline).map(([day, places]) => [
          day,
          places.filter((place) => place.previewId !== previewId),
        ]),
      ),
    }));
  };

  const cancelRecommendationPreview = () => {
    if (recommendationPreview.status === "saving") return;
    setRecommendationPreview({
      status: "idle",
      places: [],
      selectedPreviewIds: [],
      timeline: {},
      error: "",
    });
    setOpenTimeEditorId(null);
    setSelectedMapPlaceId((currentPlaceId) =>
      currentPlaceId &&
      recommendationPreview.places.some(
        (place) => place.previewId === currentPlaceId,
      )
        ? null
        : currentPlaceId,
    );
  };

  const updateRecommendationPreviewPlaceTime = (
    place: DisplayedPlace,
    time: string,
  ) => {
    if (!place.previewTimelineId) return;
    setRecommendationPreview((current) => ({
      ...current,
      timeline: updateTimelinePlaceTime(
        current.timeline,
        place.previewTimelineId!,
        time,
      ),
      places: place.previewId
        ? current.places.map((previewPlace) =>
            previewPlace.previewId === place.previewId
              ? { ...previewPlace, time }
              : previewPlace,
          )
        : current.places,
      error: "",
    }));
  };

  const cancelPendingPlaceSearch = () => {
    placeSearchAbortControllerRef.current?.abort();
    placeSearchAbortControllerRef.current = null;
  };

  const invalidatePlaceSearch = () => {
    placeSearchRequestRef.current += 1;
    cancelPendingPlaceSearch();
  };

  const openAddPlace = () => {
    if (!canEditTrip) {
      showEditPermissionRequired();
      return;
    }
    cancelPendingPlaceSearch();
    placeEditorSessionRef.current += 1;
    placeSearchRequestRef.current = 0;
    setPlaceSearchQuery("");
    setPlaceSearchCandidates([]);
    setPlaceSearchError("");
    setPlaceBasket([]);
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceEditor({ mode: "add", dayNumber: visibleDay });
    setPlaceForm({ time: "", label: "", meta: "" });
    clearPlacePreview();
    setPlaceSaveEligibility("empty");
    setPlaceDraftNotice("");
    setPlaceError("");
  };

  const openEditPlace = (place: ItineraryPlace) => {
    if (!canEditTrip) {
      setPlaceError("이 일정은 보기 권한으로 참여 중이라 편집할 수 없어요.");
      return;
    }
    const draft =
      trip && place.id
        ? readDraft<TripPlaceEditDraft>(
            tripPlaceEditDraftKey(trip.id, place.id),
          )
        : null;
    cancelPendingPlaceSearch();
    placeEditorSessionRef.current += 1;
    setPlaceSearchQuery("");
    setPlaceSearchError("");
    setPlaceSearchCandidates([]);
    setPlaceBasket([]);
    clearPlacePreview();
    setPlaceEditor({ mode: "edit", dayNumber: visibleDay, place });
    setPlaceForm(
      draft
        ? { time: draft.time ?? "", label: draft.label, meta: draft.meta ?? "" }
        : { ...place, time: place.time, label: place.label, meta: place.meta },
    );
    setPlaceDraftNotice(draft ? "수정 중이던 장소 내용을 불러왔어요." : "");
    setPlaceError("");
  };

  const loadPlaceSearchCandidates = async (
    nextTripId: string,
    query: string,
    sessionId: number,
    requestId: number,
  ) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      if (
        placeEditorSessionRef.current === sessionId &&
        placeSearchRequestRef.current === requestId
      ) {
        setPlaceSearchCandidates([]);
        setPlaceSearchError("");
        setIsLoadingPlaceSearch(false);
        setPlaceSaveEligibility("empty");
      }
      return;
    }
    const controller = new AbortController();
    placeSearchAbortControllerRef.current?.abort();
    placeSearchAbortControllerRef.current = controller;
    setIsLoadingPlaceSearch(true);
    setPlaceSearchError("");
    try {
      const candidates = await appDataApi.searchTripPlaces(
        nextTripId,
        { query: trimmedQuery },
        { signal: controller.signal },
      );
      if (
        placeEditorSessionRef.current !== sessionId ||
        placeSearchRequestRef.current !== requestId
      )
        return;
      setPlaceSearchCandidates(candidates);
      if (candidates.length > 0 && placeEditor?.mode === "add") {
        const preview = previewFromSearchCandidate(
          candidates[0],
          placeEditor.dayNumber,
          "searchPreview",
          placeForm.time ?? "",
        );
        updatePlacePreview({ source: "searchPreview", place: preview });
        setPlaceSaveEligibility("requiresExplicitCandidate");
      } else if (placeEditor?.mode === "add") {
        setPlaceSaveEligibility("empty");
      }
    } catch {
      if (controller.signal.aborted) return;
      if (
        placeEditorSessionRef.current !== sessionId ||
        placeSearchRequestRef.current !== requestId
      )
        return;
      setPlaceSearchCandidates([]);
      setPlaceSearchError(
        "장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
      if (placeEditor?.mode === "add") setPlaceSaveEligibility("empty");
    } finally {
      if (placeSearchAbortControllerRef.current === controller)
        placeSearchAbortControllerRef.current = null;
      if (
        placeEditorSessionRef.current === sessionId &&
        placeSearchRequestRef.current === requestId
      )
        setIsLoadingPlaceSearch(false);
    }
  };

  const updatePlaceSearchQuery = (query: string) => {
    setPlaceSearchQuery(query);
    if (placeEditor?.mode === "add") {
      setPlaceError("");
      const trimmedQuery = query.trim();
      setPlaceSaveEligibility(
        trimmedQuery ? "requiresExplicitCandidate" : "empty",
      );
      setPlaceForm((current) => ({
        time: current.time ?? "",
        label: trimmedQuery ? "" : current.label,
        meta: trimmedQuery ? "" : (current.meta ?? ""),
      }));
    }
    invalidatePlaceSearch();
    const requestId = placeSearchRequestRef.current;
    setIsLoadingPlaceSearch(false);
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setPlaceSearchCandidates([]);
      setPlaceSearchError("");
      return;
    }
    if (!trip) return;
    void loadPlaceSearchCandidates(
      trip.id,
      query,
      placeEditorSessionRef.current,
      requestId,
    );
  };

  const selectPlaceSearchCandidate = (candidate: PlaceSearchCandidate) => {
    if (placeEditor?.mode === "add") {
      const basketPayload = placeSearchCandidatePayload(candidate, "");
      placeBasketIdRef.current += 1;
      setPlaceBasket((current) => [
        ...current,
        {
          ...basketPayload,
          basketId: `place-basket-${placeBasketIdRef.current}`,
        },
      ]);
      updatePlacePreview({
        source: "selected",
        place: previewFromSearchCandidate(
          candidate,
          placeEditor.dayNumber,
          "selected",
          "",
        ),
      });
      cancelPendingPlaceSearch();
      placeSearchRequestRef.current += 1;
      setPlaceSearchQuery("");
      setPlaceSearchCandidates([]);
      setPlaceSearchError("");
      setIsLoadingPlaceSearch(false);
      setPlaceSaveEligibility("empty");
      setPlaceForm({ time: "", label: "", meta: "" });
      setBatchPlaceRecovery({ kind: "none" });
      setPlaceError("");
      return;
    }
    const preview = previewFromSearchCandidate(
      candidate,
      placeEditor?.dayNumber ?? visibleDay,
      "selected",
      placeForm.time ?? "",
    );
    updatePlacePreview({ source: "selected", place: preview });
    setPlaceSaveEligibility("saveSelected");
    updatePlaceForm(placeSearchCandidatePayload(candidate, placeForm.time));
    setPlaceSearchQuery(candidate.title);
    setPlaceError("");
  };

  const removePlaceBasketItem = (basketId: string) => {
    setPlaceBasket((current) =>
      current.filter((item) => item.basketId !== basketId),
    );
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceError("");
  };

  const submitPlaceBasket = async (dayNumber: number) => {
    if (!trip || !placeEditor || placeEditor.mode !== "add") return;
    if (placeBasket.length === 0) return;
    setIsSavingPlace(true);
    setPlaceError("");
    setBatchPlaceRecovery({ kind: "none" });
    const places = placeBasket.map(({ basketId: _basketId, ...place }) => place);
    try {
      const nextTrip = await appDataApi.addTripPlaces(trip.id, dayNumber, {
        expectedRevision: trip.revision,
        places,
      });
      setTrip(nextTrip);
      setPlaceBasket([]);
      setPlaceEditor(null);
      clearPlacePreview();
      setPlaceDraftNotice("");
      setNotice("장소를 일정에 추가했어요.");
      window.setTimeout(() => setNotice(null), 1800);
    } catch (error) {
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setPlaceError);
      } else if (isMissingTripDay(error)) {
        const latestTrip = await refreshTripQuietly(trip.id);
        if (latestTrip) {
          setBatchPlaceRecovery({
            kind: "missingDay",
            availableDays: tripDayNumbers(latestTrip.days),
          });
          setPlaceError(
            "저장할 Day가 변경되었어요. 최신 일정의 Day를 선택해 다시 저장해 주세요.",
          );
        } else {
          setPlaceError(
            "최신 일정을 불러오지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요.",
          );
        }
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const retryPlaceBasket = (dayNumber: number) => {
    void submitPlaceBasket(dayNumber);
  };

  const submitPlaceEditor = async () => {
    if (!trip || !placeEditor) return;
    if (!canEditTrip) {
      setPlaceError("이 일정은 보기 권한으로 참여 중이라 편집할 수 없어요.");
      return;
    }
    if (placeEditor.mode === "add" && placeBasket.length > 0) {
      void submitPlaceBasket(placeEditor.dayNumber);
      return;
    }
    if (placeEditor.mode === "add") {
      setPlaceError("검색 결과에서 저장할 장소를 선택해 주세요.");
      return;
    }
    const label = placeForm.label.trim();
    if (!label) {
      setPlaceError("장소명을 입력해 주세요.");
      return;
    }
    const time = placeForm.time?.trim() ?? "";
    if (!isTenMinutePlaceTime(time)) {
      setPlaceError(placeTimeErrorMessage);
      return;
    }
    setIsSavingPlace(true);
    setPlaceError("");
    try {
      const payload: TripPlaceRequest & { expectedRevision: number } = {
        time,
        label,
        meta: placeForm.meta?.trim() || undefined,
        expectedRevision: trip.revision,
      };
      if (placeForm.address !== undefined) payload.address = placeForm.address;
      if (placeForm.latitude !== undefined)
        payload.latitude = placeForm.latitude;
      if (placeForm.longitude !== undefined)
        payload.longitude = placeForm.longitude;
      if (placeForm.category !== undefined)
        payload.category = placeForm.category;
      if (placeForm.categoryCode !== undefined)
        payload.categoryCode = placeForm.categoryCode;
      if (placeForm.placeUrl !== undefined)
        payload.placeUrl = placeForm.placeUrl;
      if (placeForm.sourceProvider !== undefined)
        payload.sourceProvider = placeForm.sourceProvider;
      if (placeForm.externalPlaceId !== undefined)
        payload.externalPlaceId = placeForm.externalPlaceId;
      let nextTrip = await appDataApi.updateTripPlace(
        trip.id,
        placeEditor.place.id ?? "",
        payload,
      );

      /* 날짜나 시간을 고쳤으면 그 카드만 알맞은 자리로 옮긴다.
         손으로 끌어 옮겨 생긴 역전은 건드리지 않는다 — 그건 "시간 확인" 경고가 맡는다. */
      const editedPlaceId = placeEditor.place.id;
      if (placeEditor.mode === "edit" && editedPlaceId) {
        const located = findTripPlaceById(nextTrip, editedPlaceId);
        const targetDay = placeEditor.dayNumber;
        const timeChanged = (placeEditor.place.time ?? "") !== time;
        const dayChanged = Boolean(located) && located!.dayNumber !== targetDay;
        if (located && (timeChanged || dayChanged)) {
          const targetPlaces = nextTrip.days[targetDay] ?? [];
          const position = resolveTimeSortedPosition({
            places: targetPlaces,
            movingPlaceId: editedPlaceId,
            nextTime: time,
          });
          const alreadyThere =
            !dayChanged && position === located.index + 1;
          if (!alreadyThere) {
            try {
              nextTrip = await appDataApi.moveTripPlace(
                nextTrip.id,
                editedPlaceId,
                {
                  dayNumber: targetDay,
                  position,
                  expectedRevision: nextTrip.revision,
                },
              );
              if (dayChanged) {
                // 옮긴 날짜로 화면이 따라가지 않으면 카드가 사라진 것처럼 보인다.
                setActiveDay(targetDay);
                updateDetailSearchParams({ day: targetDay, place: null });
              }
            } catch {
              /* 자리 이동만 실패한 경우다. 나머지 수정은 이미 저장됐으니 되돌리지 않는다.
                 되돌리면 사용자가 방금 한 수정이 사라진다. */
            }
          }
        }
      }

      if (placeEditor.mode === "edit" && placeEditor.place.id)
        clearDraft(tripPlaceEditDraftKey(trip.id, placeEditor.place.id));
      setTrip(nextTrip);
      setPlaceEditor(null);
      clearPlacePreview();
      setPlaceDraftNotice("");
      setNotice("장소 정보를 수정했어요.");
      window.setTimeout(() => setNotice(null), 1800);
    } catch (error) {
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setPlaceError);
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const requestDeletePlace = (place: ItineraryPlace) => {
    if (!trip || !place.id || isSavingPlace) return;
    if (!canEditTrip) {
      setPlaceError("이 일정은 보기 권한으로 참여 중이라 편집할 수 없어요.");
      return;
    }
    setDeleteCandidatePlace(place);
    setPlaceDeleteError("");
  };

  const movePlaceTo = async (
    place: DisplayedPlace,
    dayNumber: number,
    position: number,
  ) => {
    if (isPreviewActive && place.previewTimelineId) {
      setRecommendationPreview((current) => ({
        ...current,
        timeline: moveTimelinePlace(
          current.timeline,
          place.previewTimelineId!,
          dayNumber,
          position - 1,
        ),
      }));
      setActiveDay(dayNumber);
      updateDetailSearchParams({ day: dayNumber, place: null });
      return;
    }
    if (!trip || !place.id || movingPlaceId) return;
    if (!canEditTrip) {
      setPlaceError("이 일정은 보기 권한으로 참여 중이라 편집할 수 없어요.");
      return;
    }
    setMovingPlaceId(place.id);
    setMoveError("");
    try {
      const nextTrip = await appDataApi.moveTripPlace(trip.id, place.id, {
        dayNumber,
        position,
        expectedRevision: trip.revision,
      });
      setTrip(nextTrip);
      setActiveDay(dayNumber);
      updateDetailSearchParams({ day: dayNumber, place: null });
      setNotice("장소 순서를 변경했어요.");
      window.setTimeout(() => setNotice(null), 1800);
    } catch (error) {
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setMoveError);
      } else {
        setMoveError(
          "장소 순서를 변경하지 못했어요. 잠시 후 다시 시도해 주세요.",
        );
      }
    } finally {
      setMovingPlaceId(null);
    }
  };

  const handlePlaceDragStart = (event: DragStartEvent) => {
    resetPlaceDragCollisionMemory();
    const placeId = isPreviewActive
      ? String(event.active.id)
      : parsePlaceDragId(event.active.id);
    if (!placeId) return;
    const activeSortableId = String(event.active.id);
    const activeNode =
      typeof document !== "undefined"
        ? (Array.from(
            document.querySelectorAll<HTMLElement>("[data-sortable-id]"),
          ).find((node) => node.dataset.sortableId === activeSortableId) ??
          null)
        : null;
    const appContainer =
      typeof document !== "undefined"
        ? document.querySelector<HTMLElement>(".app-container")
        : null;
    placeDragContentBoundsRef.current =
      activeNode && appContainer
        ? {
            activeBottomWithMargin:
              activeNode.getBoundingClientRect().bottom +
              (Number.parseFloat(
                window.getComputedStyle(activeNode).marginBottom,
              ) || 0),
          }
        : null;
    updatePlaceDragPointer(event.activatorEvent);
    lockPlaceDragViewportScroll();
    setCrossDayDragPreview(null);
    setIsDragOverDayRow(false);
    setDraggingPlaceId(placeId);
  };

  const handlePlaceDragOver = (event: DragOverEvent) => {
    if (!trip || !canEditTrip || movingPlaceId) return;
    let verifiedOverId = event.over
      ? getPointerVerifiedTimelineOverId(event.over.id)
      : null;
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    const isOverDayRow = isPointerOverDayRow();
    setIsDragOverDayRow(isOverDayRow);
    const pointerDayTarget = getPointerDayTarget();
    verifiedOverId = resolvePlaceDragOverId({
      collisionOverId: verifiedOverId,
      pointerDayTarget,
      isOverDayRow,
      visibleDay,
      closestVisibleDayPosition: getClosestCurrentDayTimelinePosition(String(event.active.id)),
    });
    if (!pointerDayTarget && !isOverDayRow) {
      const dayTarget = parseDayDropId(verifiedOverId);
      if (
        dayTarget &&
        isPointerInsideTimelineArea(
          placeDragPointerRef.current,
          timelineElement?.getBoundingClientRect() ?? null,
        )
      ) {
        verifiedOverId = dayPositionDropId(dayTarget, 1);
      }
    }
    const activeSortableId = String(event.active.id);
    verifiedOverId = resolveDayAreaOverId({
      overId: verifiedOverId,
      closestPosition: getClosestCurrentDayTimelinePosition(String(event.active.id)),
    });
    verifiedOverId = resolveGhostDropOverId({
      activeSortableId,
      overId: verifiedOverId,
      crossDayPreview: isCrossDayPlaceDrag ? crossDayDragPreview : null,
    });
    const targetDay = parseDayDropId(verifiedOverId);
    if (!targetDay || !dayNumbers.includes(targetDay)) {
      clearPlaceDragAutoSwitch();
      setDragOverDay(null);
      const target = resolveTimelineDropTarget({
        activeSortableId,
        dayNumbers,
        overId: verifiedOverId,
        sortableIdsByDay,
        visibleDay,
      });
      const sourceDay = findSortableIdDay(sortableIdsByDay, activeSortableId);
      setCrossDayDragPreview(
        target && sourceDay != null && target.dayNumber !== sourceDay
          ? target
          : null,
      );
      return;
    }
    const dayTabElement = document.querySelector<HTMLElement>(
      `[data-day-drop-id="${dayDropId(targetDay)}"]`,
    );
    if (
      !shouldScheduleDaySwitch({
        pointer: placeDragPointerRef.current,
        dayTabRect: dayTabElement?.getBoundingClientRect() ?? null,
        timelineRect: timelineElement?.getBoundingClientRect() ?? null,
        dayZoneRect: getDayZoneRect(),
      })
    ) {
      clearPlaceDragAutoSwitch();
      setDragOverDay(null);
      return;
    }
    setDragOverDay(targetDay);
    const sourceDay = findSortableIdDay(sortableIdsByDay, activeSortableId);
    if (sourceDay != null && targetDay !== sourceDay) {
      setCrossDayDragPreview({
        dayNumber: targetDay,
        position: (sortableIdsByDay[targetDay] ?? []).length + 1,
      });
    }
    /* 탭 위를 지나가는 것으로는 날짜를 바꾸지 않는다. 30일 일정에서 이 경로가
       스쳐 지나가기만 해도 발동해 의도치 않은 전환을 만들었다.
       화면을 바꾸는 일은 좌우 이동영역과 화살표 키가 맡는다.
       탭 강조(setDragOverDay)와 탭에 드롭해 옮기는 길은 그대로 둔다. */
    clearPlaceDragAutoSwitch();
  };

  const handlePlaceDragEnd = (event: DragEndEvent) => {
    let verifiedOverId = event.over
      ? getPointerVerifiedTimelineOverId(event.over.id)
      : null;
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    const pointerDayTarget = getPointerDayTarget();
    const isOverDayRow = isPointerOverDayRow();
    verifiedOverId = resolvePlaceDragOverId({
      collisionOverId: verifiedOverId,
      pointerDayTarget,
      isOverDayRow,
      visibleDay,
      closestVisibleDayPosition: getClosestCurrentDayTimelinePosition(String(event.active.id)),
    });
    if (!pointerDayTarget && !isOverDayRow) {
      const dayTarget = parseDayDropId(verifiedOverId);
      if (
        dayTarget &&
        isPointerInsideTimelineArea(
          placeDragPointerRef.current,
          timelineElement?.getBoundingClientRect() ?? null,
        )
      ) {
        verifiedOverId = dayPositionDropId(dayTarget, 1);
      }
    }
    const activeSortableId = String(event.active.id);
    // dragOver와 같은 순서로 풀어야 한다. 한쪽만 적용하면 미리보기는 뜨는데
    // 드롭이 안 먹는 식으로 갈린다.
    const overId = resolveGhostDropOverId({
      activeSortableId,
      overId: resolveDayAreaOverId({
        overId: verifiedOverId,
        closestPosition: getClosestCurrentDayTimelinePosition(String(event.active.id)),
      }),
      crossDayPreview: isCrossDayPlaceDrag ? crossDayDragPreview : null,
    });
    placeDragContentBoundsRef.current = null;
    placeDragPointerRef.current = null;
    resetPlaceDragCollisionMemory();
    clearPlaceDragAutoSwitch();
    unlockPlaceDragViewportScroll();
    setCrossDayDragPreview(null);
    setDraggingPlaceId(null);
    setDragOverDay(null);
    setIsDragOverDayRow(false);
    if (!trip || !canEditTrip || movingPlaceId || !overId) return;
    if (isPreviewActive) {
      const activeId = String(event.active.id);
      const activeDay = findDisplayedPlaceDay(
        recommendationPreview.timeline,
        activeId,
      );
      if (!activeDay) return;
      const target = resolveTimelineDropTarget({
        activeSortableId: activeId,
        dayNumbers,
        overId,
        sortableIdsByDay,
        visibleDay: activeDay,
      });
      if (!target) return;
      setRecommendationPreview((current) => ({
        ...current,
        timeline: moveTimelinePlace(
          current.timeline,
          activeId,
          target.dayNumber,
          target.position - 1,
        ),
      }));
      setActiveDay(target.dayNumber);
      updateDetailSearchParams({ day: target.dayNumber, place: null });
      return;
    }
    const placeId = parsePlaceDragId(event.active.id);
    if (!placeId) return;
    const place =
      Object.values(trip.days)
        .flat()
        .find((item) => item.id === placeId) ?? null;
    if (!place) return;

    const target = resolveTimelineDropTarget({
      activeSortableId: String(event.active.id),
      dayNumbers,
      overId,
      sortableIdsByDay,
      visibleDay,
    });
    if (!target) return;
    void movePlaceTo(place, target.dayNumber, target.position);
  };

  const handlePlaceDragCancel = () => {
    placeDragContentBoundsRef.current = null;
    placeDragPointerRef.current = null;
    resetPlaceDragCollisionMemory();
    clearPlaceDragAutoSwitch();
    unlockPlaceDragViewportScroll();
    setCrossDayDragPreview(null);
    setDraggingPlaceId(null);
    setDragOverDay(null);
    setIsDragOverDayRow(false);
  };

  const cancelDeletePlace = () => {
    if (isSavingPlace) return;
    setDeleteCandidatePlace(null);
    setPlaceDeleteError("");
  };

  const confirmDeletePlace = async () => {
    const place = deleteCandidatePlace;
    if (!trip || !place?.id || isSavingPlace) return;
    setIsSavingPlace(true);
    setPlaceDeleteError("");
    try {
      const nextTrip = await appDataApi.deleteTripPlace(
        trip.id,
        place.id,
        trip.revision,
      );
      clearDraft(tripPlaceEditDraftKey(trip.id, place.id));
      setTrip(nextTrip);
      setDeleteCandidatePlace(null);
      setPlaceDraftNotice("");
      setNotice("장소를 일정에서 삭제했어요.");
      window.setTimeout(() => setNotice(null), 1800);
    } catch (error) {
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setPlaceDeleteError);
      } else {
        setPlaceDeleteError(
          "장소를 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const removeLinkedPolicy = async (policy: LinkedTripPolicy) => {
    if (!trip || removingPolicySlug) return;
    if (!canEditTrip) {
      setPolicyRemoveError(
        "이 일정은 보기 권한으로 참여 중이라 정책 연결을 삭제할 수 없어요.",
      );
      return;
    }
    setRemovingPolicySlug(policy.slug);
    setPolicyRemoveError("");
    try {
      await appDataApi.removePolicyFromTrip(trip.id, policy.slug);
      if (routeLinkedPolicy?.slug === policy.slug) {
        setHiddenRoutePolicySlugs((current) =>
          new Set(current).add(policy.slug),
        );
      }
      removeAddedPolicy(policy.slug);
      const nextLinkedPolicies = trip.linkedPolicies.filter(
        (linkedPolicy) => linkedPolicy.slug !== policy.slug,
      );
      setTrip({
        ...trip,
        expectedSaving:
          nextLinkedPolicies.length === 0 ? "0원" : trip.expectedSaving,
        linkedPolicies: nextLinkedPolicies,
      });
      setNotice("정책 연결을 해제했어요.");
      window.setTimeout(() => setNotice(null), 1800);
    } catch {
      setPolicyRemoveError(
        "정책 연결을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setRemovingPolicySlug(null);
    }
  };

  const updatePlaceForm = (nextForm: TripPlaceRequest) => {
    setPlaceForm(nextForm);
    if (!trip || !placeEditor) return;
    if (placeEditor.mode === "edit" && placeEditor.place.id) {
      saveDraft<TripPlaceEditDraft>(
        tripPlaceEditDraftKey(trip.id, placeEditor.place.id),
        {
          placeId: placeEditor.place.id,
          time: nextForm.time ?? "",
          label: nextForm.label,
          meta: nextForm.meta ?? "",
        },
      );
    }
  };

  const closePlaceEditor = () => {
    if (isSavingPlace) return;
    if (trip && placeEditor?.mode === "edit" && placeEditor.place.id)
      clearDraft(tripPlaceEditDraftKey(trip.id, placeEditor.place.id));
    cancelPendingPlaceSearch();
    placeEditorSessionRef.current += 1;
    setPlaceDraftNotice("");
    setPlaceSearchCandidates([]);
    setPlaceSearchQuery("");
    setPlaceBasket([]);
    setBatchPlaceRecovery({ kind: "none" });
    clearPlacePreview();
    setPlaceEditor(null);
  };

  const discardPlaceDraft = () => {
    if (!trip || !placeEditor) return;
    if (placeEditor.mode === "edit" && placeEditor.place.id) {
      clearDraft(tripPlaceEditDraftKey(trip.id, placeEditor.place.id));
      setPlaceForm({
        time: placeEditor.place.time,
        label: placeEditor.place.label,
        meta: placeEditor.place.meta,
      });
    }
    setPlaceDraftNotice("");
  };

  const normalizedPlaceSearchQuery = placeSearchQuery
    .trim()
    .toLocaleLowerCase("ko-KR");
  const placeSearchResults = placeSearchCandidates
    .filter((candidate) => {
      if (!normalizedPlaceSearchQuery) return true;
      return placeSearchText(candidate).includes(normalizedPlaceSearchQuery);
    })
    .slice(0, 6);

  if (isLoading) {
    return (
      <section className="screen with-tabs prototype-trip-detail-screen">
        <LoadingState label="일정 상세를 불러오는 중입니다" />
      </section>
    );
  }

  if (error || !trip) {
    return (
      <section className="screen with-tabs prototype-trip-detail-screen">
        <ErrorState
          message={error ?? "일정 정보를 찾지 못했어요."}
          action={
            <LinkButton to="/trips" variant="line">
              일정 목록으로
            </LinkButton>
          }
        />
      </section>
    );
  }

  return (
    <section
      className={
        [
          "screen with-tabs prototype-trip-detail-screen",
          canEditTrip ? "" : "readonly-trip",
          isPreviewActive ? "recommendation-preview-active" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      <TopBar
        title={trip.title}
        left={
          <IconButton label="일정 목록" to="/trips">
            <ChevronLeft size={20} />
          </IconButton>
        }
      />
      <div className="prototype-trip-detail-hero">
        <div className="prototype-trip-hero-copy">
          <span className="prototype-detail-dday-chip">{tripDdayLabel}</span>
          <h1>{trip.title}</h1>
          <p>📅 {trip.dates}</p>
        </div>
        <div className="prototype-trip-hero-icon" aria-hidden="true">
          {tripRegionEmojiLabel}
        </div>
        {canEditTrip && (
          <Link
            aria-label="일정 편집"
            className="prototype-trip-hero-edit"
            to={`/trips/${encodeURIComponent(trip.id)}/edit`}
          >
            편집
          </Link>
        )}
      </div>
      <div className="trip-summary">
        <div className="between">
          <div className="row">
            <div className="avatar-stack">
              {tripPeople.slice(0, 3).map((name) => (
                <span className="avatar-mini" key={name}>
                  {name[0]}
                </span>
              ))}
            </div>
            <span className="meta">{tripPeople.length}명 참여 중</span>
          </div>
          {canManageTripStatus && (
            <button
              className="prototype-invite-pill"
              onClick={() => setIsInviteSheetOpen(true)}
              type="button"
            >
              + 친구 초대
            </button>
          )}
        </div>
      </div>
      <section
        className="prototype-linked-policy-section"
        aria-label="연결된 정책"
      >
        <h2>🎯 연결된 정책</h2>
        {linkedPolicies.length > 0 ? (
          linkedPolicies.map((policy) => {
            const isHiddenPolicy = policy.status === "hidden";
            return (
              <div
                className={
                  isHiddenPolicy
                    ? "benefit-banner linked-policy-card hidden-policy"
                    : "benefit-banner linked-policy-card"
                }
                key={policy.slug}
              >
                {isHiddenPolicy ? (
                  <div
                    className="linked-policy-card-main"
                    aria-label={`${policy.title} 숨김 정책`}
                  >
                    <span className="benefit-banner-icon" aria-hidden="true">
                      🚫
                    </span>
                    <div>
                      <strong>{policy.title}</strong>
                      <div className="meta">{`${policy.amount || "혜택 확인"} · 숨김 처리됨`}</div>
                    </div>
                  </div>
                ) : (
                  <Link
                    className="linked-policy-card-main"
                    to={`/policies/${policy.slug}`}
                  >
                    <span className="benefit-banner-icon" aria-hidden="true">
                      💴
                    </span>
                    <div>
                      <strong>{policy.title}</strong>
                      <div className="meta">{`${policy.amount || "혜택 확인"} · ${policy.region || "전국"}`}</div>
                    </div>
                  </Link>
                )}
                {canEditTrip && (
                  <button
                    aria-label={`${policy.title} 연결 삭제`}
                    className="linked-policy-remove"
                    disabled={removingPolicySlug === policy.slug}
                    onClick={() => void removeLinkedPolicy(policy)}
                    type="button"
                  >
                    {removingPolicySlug === policy.slug ? "삭제 중" : "삭제"}
                  </button>
                )}
              </div>
            );
          })
        ) : (
          <Link className="benefit-banner" to="/policies">
            <span className="benefit-banner-icon" aria-hidden="true">
              💴
            </span>
            <div>
              <strong>
                {hasLinkedPolicyFallback
                  ? "연결된 정책이 있어요"
                  : "연결된 정책이 없어요"}
              </strong>
              <div className="meta">
                {hasLinkedPolicyFallback
                  ? `${trip?.expectedSaving ?? "혜택 확인"} · 정책 목록에서 확인`
                  : "정책 상세에서 일정을 연결할 수 있어요"}
              </div>
            </div>
            <span className="benefit-banner-arrow" aria-hidden="true">
              ›
            </span>
          </Link>
        )}
        {policyRemoveError && <p className="form-error">{policyRemoveError}</p>}
      </section>
      <section
        className="trip-benefit-grid"
        aria-label="이 일정에 어울리는 정책"
      >
        <h2>💡 이 일정에 어울리는 정책</h2>
        <div className="prototype-matching-policy-rail">
          {recommendedPolicies.length > 0 ? (
            recommendedPolicies.map((policy) => (
              <Link
                className="prototype-matching-policy-card"
                key={policy.slug}
                to={`/policies/${policy.slug}`}
              >
                <div className="matching-card-head">
                  <span aria-hidden="true">💡</span>
                  <em>{policy.amount || "정책 확인"}</em>
                </div>
                <strong>{policy.title}</strong>
              </Link>
            ))
          ) : (
            <Link className="prototype-matching-policy-card" to="/policies">
              <div className="matching-card-head">
                <span aria-hidden="true">💡</span>
                <em>정책 확인</em>
              </div>
              <strong>이 일정에 어울리는 정책이 없어요</strong>
            </Link>
          )}
        </div>
      </section>
      <div className="prototype-trip-detail-divider" aria-hidden="true" />
      <DndContext
        sensors={dragSensors}
        collisionDetection={placeDragCollisionDetection}
        modifiers={[restrictPlaceDragToContent]}
        /* 유령이 끼어들면 카드가 실제로 이동한다. 기본값(WhileDragging)은
           드래그 시작 때 한 번만 재므로 옛 좌표로 판정해 진동이 생긴다. */
        measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
        /* dnd-kit의 레이아웃 시프트 보정은 끄고(날짜 전환이 거대한 변화라
           보정량이 커진다), 위쪽 자동 스크롤에는 상한을 둔다. threshold를
           명시해야 shouldAllowPlaceDragAutoScroll과 기준이 일치한다. */
        autoScroll={{
          layoutShiftCompensation: false,
          canScroll: canPlaceDragAutoScroll,
          threshold: { x: 0, y: PLACE_DRAG_AUTO_SCROLL_THRESHOLD },
        }}
        onDragStart={handlePlaceDragStart}
        onDragOver={handlePlaceDragOver}
        onDragCancel={handlePlaceDragCancel}
        onDragEnd={handlePlaceDragEnd}
      >
        {isTripViewer && (
          <div className="card">
            <div className="card-body stack tight">
              <strong>보기 권한으로 참여 중입니다</strong>
              <p className="meta">
                일정과 정책은 확인할 수 있지만 장소 편집은 할 수 없어요.
              </p>
            </div>
          </div>
        )}

        {recommendationPreview.status === "loading" && (
          <p className="place-search-status">추천 일정을 불러오는 중입니다.</p>
        )}
        {recommendationPreview.error && (
          <p className="form-error">{recommendationPreview.error}</p>
        )}

        <PrototypeTripMap
          dayNumber={visibleDay}
          onSelectPlace={selectMapPlace}
          onShowPlaceDetail={(place) => {
            setNotice(null);
            setPlaceDetail({ dayNumber: visibleDay, place });
          }}
          places={mapPlaces}
          selectedPlaceId={selectedMapPlaceId}
        />

        <section
          className="trip-primary-actions"
          aria-label="일정 편집 작업"
          data-itinerary-actions
        >
          <button
            className="prototype-trip-action-button prototype-trip-action-add"
            type="button"
            onClick={openAddPlace}
          >
            + 장소 추가
          </button>
          <button
            className="prototype-trip-action-button prototype-trip-action-ai"
            type="button"
            onClick={() => void openRecommendationPreview()}
          >
            ✨ 추천 일정만들기
          </button>
        </section>

        {isPreviewActive && (
          <section
            className="recommendation-preview-banner"
            aria-label="추천 일정 저장 전 미리보기"
          >
            <div>
              <strong>저장 전 미리보기</strong>
              <p className="meta">
                기존 장소와 추천 후보를 임시로 편집 중입니다.
              </p>
              {recommendationPreview.places.length === 0 ? (
                <p className="place-search-status">
                  저장할 추천 일정이 없어요. 다시 추천을 불러와 주세요.
                </p>
              ) : null}
            </div>
          </section>
        )}

        {canEditTrip && draggingPlaceId && (
          <>
            {/* 카드를 집으면 양옆에 이동영역이 드러난다. 여기 머물면 날짜가 넘어간다.
                깊이는 화살표가 진해지고 커지는 것으로만 알린다. */}
            <div
              aria-hidden="true"
              className="itinerary-day-edge left"
              data-itinerary-day-edge="left"
              ref={dayEdgeLeftRef}
            >
              <span>‹</span>
            </div>
            <div
              aria-hidden="true"
              className="itinerary-day-edge right"
              data-itinerary-day-edge="right"
              ref={dayEdgeRightRef}
            >
              <span>›</span>
            </div>
          </>
        )}

        <div
          aria-label="일정 날짜 선택"
          className="day-tabs"
          data-itinerary-day-tabs
          {...dayStripDragScroll}
        >
          {dayNumbers.map((day) => (
            <DroppableDayTab
              canDrop={canEditTrip && Boolean(draggingPlaceId)}
              count={trip.days[day]?.length ?? 0}
              dateLabel={formatDayDateLabel(trip.dates, day)}
              day={day}
              isActive={visibleDay === day}
              isDragOver={dragOverDay === day}
              key={day}
              onSelect={selectTripDay}
            />
          ))}
        </div>

        <div aria-hidden="true" className="itinerary-drag-boundary" />
        <div
          className={draggingPlaceId ? "timeline dnd-active" : "timeline"}
          data-itinerary-timeline
          ref={setTimelineAreaRef}
        >
          <SortableContext
            items={timelineSortableIds}
            strategy={verticalListSortingStrategy}
          >
            {timelineRenderItems.map((renderItem, renderIndex) => {
              // 번호는 슬롯 순번이다. 유령도 한 칸을 차지하므로 들고 있는
              // 카드가 자동으로 포함된다. 배지는 카드와 형제로 놓여
              // 카드가 재정렬돼도 행 순서에 고정된다.
              const marker = (
                <TimelineSlotMarker
                  isLast={renderIndex === timelineRenderItems.length - 1}
                  number={renderIndex + 1}
                />
              );
              if (renderItem.type === "ghost") {
                return (
                  <Fragment key="timeline-cross-day-ghost">
                    {marker}
                    <TimelineGhostCard
                      label={activeDraggingPlaceLabel}
                      sortableId={draggingPlaceSortableId ?? ""}
                    />
                  </Fragment>
                );
              }
              const place = renderItem.value;
              const index = timelineRenderItems
                .slice(0, renderIndex)
                .filter((item) => item.type === "item").length;
              return (
              <Fragment
                key={
                  place.id ??
                  place.previewId ??
                  `${place.time}-${place.label}`
                }
              >
                {canEditTrip && draggingPlaceId && (
                  <DroppableTimelinePosition
                    dayNumber={visibleDay}
                    isCrossDay={isCrossDayPlaceDrag}
                    position={index + 1}
                  />
                )}
                {marker}
                <SortablePlaceItem
                  canEditTrip={canEditTrip}
                  currentDay={visibleDay}
                  dayNumbers={dayNumbers}
                  disabled={
                    Boolean(movingPlaceId) ||
                    isSavingPlace ||
                    recommendationPreview.status === "saving"
                  }
                  isMoving={movingPlaceId === place.id}
                  isPreviewMode={isPreviewActive}
                  previewDayPlaceCounts={Object.fromEntries(
                    dayNumbers.map((day) => [
                      day,
                      recommendationPreview.timeline[day]?.length ?? 0,
                    ]),
                  )}
                  hasTimeOrderWarning={Boolean(
                    displayedPlaceWarningKey(place) &&
                      timeWarningPlaceIds.has(displayedPlaceWarningKey(place)!),
                  )}
                  onCancelRecommendationPreviewPlace={
                    cancelRecommendationPreviewPlace
                  }
                  onDelete={requestDeletePlace}
                  onEdit={openEditPlace}
                  onMove={movePlaceTo}
                  onSelectRecommendationPreviewPlace={
                    selectRecommendationPreviewMapPlace
                  }
                  onSaveRecommendationPreviewPlace={(previewId) =>
                    void saveRecommendationPreviewPlace(previewId)
                  }
                  place={place}
                  places={displayedPlaces}
                  openTimeEditorId={openTimeEditorId}
                  onToggleTimeEditor={(cardId, willOpen) =>
                    setOpenTimeEditorId((current) =>
                      resolveNextOpenTimeEditorId(current, cardId, willOpen),
                    )
                  }
                  onPreviewTimeChange={updateRecommendationPreviewPlaceTime}
                  trip={trip}
                />
              </Fragment>
              );
            })}
            {canEditTrip && draggingPlaceId && (
              <DroppableTimelinePosition
                dayNumber={visibleDay}
                isCrossDay={isCrossDayPlaceDrag}
                position={displayedPlaces.length + 1}
              />
            )}
          </SortableContext>
        </div>
        <DragOverlay dropAnimation={null}>
          {draggingPlaceId && (
            <div
              aria-hidden="true"
              className={
                dragOverDay || isDragOverDayRow
                  ? "place-drag-overlay over-day-target"
                  : "place-drag-overlay"
              }
            >
              <GripVertical size={16} />
              <strong>{activeDraggingPlaceLabel}</strong>
            </div>
          )}
        </DragOverlay>
      </DndContext>
      {isPreviewActive && (
        <aside
          className="recommendation-preview-action-bar"
          aria-label="추천 일정 미리보기 저장 작업"
        >
          <button
            className="btn sm ghost"
            type="button"
            disabled={recommendationPreview.status === "saving"}
            onClick={cancelRecommendationPreview}
          >
            미리보기 취소
          </button>
          <button
            className="btn sm line"
            type="button"
            disabled={recommendationPreview.status === "saving"}
            onClick={() =>
              void commitRecommendationPreview({ saveAllCandidates: false })
            }
          >
            {recommendationPreview.status === "saving" ? "저장 중" : "선택 저장"}
          </button>
          <button
            className="btn sm primary"
            type="button"
            disabled={
              recommendationPreview.status === "saving" ||
              recommendationPreview.places.length === 0
            }
            onClick={() =>
              void commitRecommendationPreview({
                saveAllCandidates: true,
              })
            }
          >
            {recommendationPreview.status === "saving" ? "저장 중" : "전체 저장"}
          </button>
        </aside>
      )}
      {placeError && !placeEditor && <Toast>{placeError}</Toast>}
      {moveError && <Toast>{moveError}</Toast>}
      {notice && <Toast>{notice}</Toast>}
      {dateEditor && (
        <TripDateEditorSheet
          error={dateEditor.error}
          endDate={dateEditor.endDate}
          isSaving={dateEditor.isSaving}
          onChangeDateRange={({ startDate, endDate }) =>
            setDateEditor((current) =>
              current ? { ...current, startDate, endDate, error: "" } : current,
            )
          }
          onChangeStrategy={(overflowPlaceStrategy) =>
            setDateEditor((current) =>
              current ? { ...current, overflowPlaceStrategy } : current,
            )
          }
          onClose={() => setDateEditor(null)}
          onSubmit={submitDateEditor}
          overflowPlaceCount={dateEditorOverflowPlaceCount}
          overflowPlaceStrategy={dateEditor.overflowPlaceStrategy}
          startDate={dateEditor.startDate}
        />
      )}
      {placeEditor && (
        <PlaceEditorSheet
          dayNumber={placeEditor.dayNumber}
          dayOptions={placeEditorDayOptions}
          error={placeError}
          form={placeForm}
          isLoadingSearch={isLoadingPlaceSearch}
          isSaving={isSavingPlace}
          mode={placeEditor.mode}
          onChange={updatePlaceForm}
          onClose={closePlaceEditor}
          onDayChange={(nextDay) =>
            setPlaceEditor((current) =>
              current ? { ...current, dayNumber: nextDay } : current,
            )
          }
          onSelectedDayRef={scrollSelectedDayIntoView}
          onDiscardDraft={discardPlaceDraft}
          onSearchInput={invalidatePlaceSearch}
          onSearchChange={updatePlaceSearchQuery}
          onSelectSearchCandidate={selectPlaceSearchCandidate}
          onRemoveBasketItem={removePlaceBasketItem}
          onRetryBasketDay={retryPlaceBasket}
          onSubmit={submitPlaceEditor}
          batchRecovery={batchPlaceRecovery}
          placeBasket={placeBasket}
          preview={placePreview}
          saveEligibility={placeSaveEligibility}
          searchCandidates={placeSearchResults}
          searchError={placeSearchError}
          searchQuery={placeSearchQuery}
          restoredDraftMessage={placeDraftNotice}
        />
      )}
      {placeDetail && (
        <PlaceDetailDialog
          dayNumber={placeDetail.dayNumber}
          onClose={() => setPlaceDetail(null)}
          place={placeDetail.place}
        />
      )}
      {/* 껍데기는 장소 편집 시트와 같은 것을 쓴다. 새 클래스를 만들면 같은 시트가 셋이 된다. */}
      {isInviteSheetOpen && trip && (
        <div
          className="sheet-backdrop"
          role="presentation"
          onMouseDown={() => setIsInviteSheetOpen(false)}
        >
          <section
            aria-labelledby="trip-invite-sheet-title"
            aria-modal="true"
            className="trip-select-sheet"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="sheet-head">
              <div>
                <h2 id="trip-invite-sheet-title">친구 초대</h2>
                <p className="meta">
                  초대 링크를 보내면 친구가 이 일정에 참여해요.
                </p>
              </div>
              <button
                className="btn sm ghost"
                onClick={() => setIsInviteSheetOpen(false)}
                type="button"
              >
                닫기
              </button>
            </div>
            <FriendInvitePanel autoPrepareLink requestedTripId={trip.id} />
          </section>
        </div>
      )}
      <ConfirmDialog
        open={Boolean(deleteCandidatePlace)}
        title="장소를 삭제할까요?"
        body={`${deleteCandidatePlace?.label ?? "선택한 장소"} 장소가 이 일정에서 삭제됩니다.`}
        error={placeDeleteError}
        confirmLabel="삭제"
        isSubmitting={isSavingPlace}
        onCancel={cancelDeletePlace}
        onConfirm={confirmDeletePlace}
      />
    </section>
  );
}

function TripDateEditorSheet({
  endDate,
  error,
  isSaving,
  onChangeDateRange,
  onChangeStrategy,
  onClose,
  onSubmit,
  overflowPlaceCount,
  overflowPlaceStrategy,
  startDate,
}: {
  endDate: string;
  error: string;
  isSaving: boolean;
  onChangeDateRange: (value: TripDateRangeValue) => void;
  onChangeStrategy: (value: "moveToLastDay" | "delete") => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  overflowPlaceCount: number;
  overflowPlaceStrategy: "moveToLastDay" | "delete";
  startDate: string;
}) {
  return (
    <div className="sheet-backdrop trip-date-editor-backdrop" role="presentation">
      <form
        aria-labelledby="trip-date-editor-title"
        aria-modal="true"
        className="trip-date-editor-sheet"
        onSubmit={onSubmit}
        role="dialog"
      >
        <div className="sheet-head">
          <div>
            <h2 id="trip-date-editor-title">여행기간 수정</h2>
            <p className="meta">
              기간을 줄이면 제외되는 날짜의 장소를 마지막 날로 옮길 수 있어요.
            </p>
          </div>
          <IconButton label="닫기" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </div>

        {/* 생성 화면과 같은 범위 달력을 쓴다. 네이티브 date 입력은 항목 높이와
            표기를 운영체제가 정해 화면마다 달라 보였다. */}
        <TripDateRangePicker
          disabled={isSaving}
          onChange={onChangeDateRange}
          value={{ startDate, endDate }}
        />

        {overflowPlaceCount > 0 && (
          <fieldset className="trip-date-overflow-options">
            <legend>
              제외되는 날짜의 장소 {overflowPlaceCount}개를 어떻게 처리할까요?
            </legend>
            <label>
              <input
                checked={overflowPlaceStrategy === "moveToLastDay"}
                name="overflowPlaceStrategy"
                type="radio"
                value="moveToLastDay"
                onChange={() => onChangeStrategy("moveToLastDay")}
              />
              마지막 Day로 이동
            </label>
            <label>
              <input
                checked={overflowPlaceStrategy === "delete"}
                name="overflowPlaceStrategy"
                type="radio"
                value="delete"
                onChange={() => onChangeStrategy("delete")}
              />
              제외되는 장소 삭제
            </label>
          </fieldset>
        )}

        {error && <p className="form-error">{error}</p>}
        <div className="sheet-actions">
          <button className="btn line" disabled={isSaving} type="button" onClick={onClose}>
            취소
          </button>
          <button className="btn primary" disabled={isSaving} type="submit">
            {isSaving ? "저장 중" : "기간 저장"}
          </button>
        </div>
      </form>
    </div>
  );
}

function PrototypeTripMap({
  dayNumber,
  onSelectPlace,
  onShowPlaceDetail,
  places,
  selectedPlaceId,
}: {
  dayNumber: number;
  onSelectPlace: (placeId: string | null) => void;
  onShowPlaceDetail: (place: ItineraryPlace) => void;
  places: DisplayedPlace[];
  selectedPlaceId: string | null;
}) {
  const selectedPlace =
    places.find(
      (place, index) =>
        mapPlaceId(place, index) === selectedPlaceId &&
        !place.isRecommendationPreview,
    ) ?? null;
  const mapPlaces = places.map((place, index) => ({
    place,
    index,
    point: getPlaceMapPoint(index, dayNumber),
  }));
  const routePoints = mapPlaces
    .map(({ point }) => `${point.x},${point.y}`)
    .join(" ");
  const markers: KakaoMapMarker[] = places.map((place, index) => ({
    id: mapPlaceId(place, index),
    label: place.label,
    subtitle: place.address || place.meta,
    latitude: place.latitude,
    longitude: place.longitude,
    query: place.address || place.label,
  }));

  if (places.length === 0) {
    return (
      <div className="prototype-map-wrap">
        <div className="prototype-map-empty">
          <MapIcon size={28} />
          <strong>아직 표시할 장소가 없어요</strong>
          <p>장소 추가 버튼으로 방문지를 일정에 저장해 보세요.</p>
        </div>
      </div>
    );
  }

  const fallbackMap = (
    <div className="prototype-full-map" onMouseDown={() => onSelectPlace(null)}>
      <svg
        className="prototype-map-terrain"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M 8,22 Q 30,5 55,15 T 95,30 L 95,75 Q 70,90 40,82 Q 12,78 5,55 Z"
          fill="rgba(255,255,255,.2)"
          stroke="rgba(255,255,255,.45)"
          strokeWidth=".3"
        />
        <path
          d="M 8,42 Q 35,46 55,42 T 95,55"
          fill="none"
          stroke="rgba(255,255,255,.55)"
          strokeWidth=".7"
          strokeDasharray="1.5,1"
        />
        <path
          d="M 25,15 Q 30,40 35,60 T 50,90"
          fill="none"
          stroke="rgba(255,255,255,.45)"
          strokeWidth=".55"
          strokeDasharray="1,1"
        />
        <circle cx="50" cy="50" r="3" fill="rgba(255,255,255,.5)" />
        <text
          x="50"
          y="46"
          textAnchor="middle"
          fontSize="2.5"
          fill="rgba(255,255,255,.85)"
          fontWeight="700"
        >
          중심지
        </text>
        {mapPlaces.length > 1 && (
          <polyline
            points={routePoints}
            fill="none"
            stroke="#ff5e5b"
            strokeWidth=".9"
            strokeDasharray="2.5,1.5"
            opacity=".85"
          />
        )}
      </svg>
      <div className="prototype-map-controls" aria-label="지도 컨트롤">
        <button aria-label="확대" type="button">
          ＋
        </button>
        <button aria-label="축소" type="button">
          −
        </button>
        <button aria-label="전체 보기" type="button">
          🧭
        </button>
      </div>
      {mapPlaces.map(({ index, place, point }) => {
        const markerId = mapPlaceId(place, index);
        const selected = markerId === selectedPlaceId;
        return (
          <button
            aria-label={`${index + 1}번 장소: ${place.label}`}
            className={
              selected ? "prototype-map-pin selected" : "prototype-map-pin"
            }
            key={markerId}
            onMouseDown={(event) => event.stopPropagation()}
            onClick={() => onSelectPlace(selected ? null : markerId)}
            style={{ left: `${point.x}%`, top: `${point.y}%` }}
            type="button"
          >
            <span className="prototype-map-pin-dot">{index + 1}</span>
            <span className="prototype-map-pin-label">{place.label}</span>
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="prototype-map-wrap">
      <KakaoMapView
        ariaLabel={`Day ${dayNumber} 지도`}
        fallback={fallbackMap}
        markers={markers}
        onSelectMarker={(markerId) => onSelectPlace(markerId)}
        selectedMarkerId={selectedPlaceId}
      />
      {selectedPlace && (
        <PlaceMapBottomSheet
          onClose={() => onSelectPlace(null)}
          onShowPlaceDetail={onShowPlaceDetail}
          place={selectedPlace}
        />
      )}
      <div className="prototype-map-caption">
        <span>
          Day {dayNumber} · <strong>{places.length}곳</strong>
        </span>
        <span>핀을 탭하면 상세가 나타나요</span>
      </div>
    </div>
  );
}

function mapPlaceId(place: DisplayedPlace, index: number): string {
  return place.id ?? place.previewId ?? `${place.label}-${index}`;
}

function PlaceMapBottomSheet({
  onClose,
  onShowPlaceDetail,
  place,
}: {
  onClose: () => void;
  onShowPlaceDetail: (place: ItineraryPlace) => void;
  place: ItineraryPlace;
}) {
  const kakaoSearchUrl =
    place.placeUrl ||
    `https://map.kakao.com/link/search/${encodeURIComponent(place.label)}`;
  const detailText = place.address || place.meta || "상세 메모가 아직 없어요.";

  return (
    <section
      className="place-map-bottom-sheet"
      aria-label={`${place.label} 지도 상세`}
      role="dialog"
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div className="place-map-sheet-main">
        <div className="place-map-sheet-icon" aria-hidden="true">
          {getPlaceEmoji(place)}
        </div>
        <div>
          <div className="place-map-sheet-tags">
            {place.time && <span>{place.time}</span>}
            <em>Day 장소</em>
          </div>
          <strong>{place.label}</strong>
          <p>{detailText}</p>
        </div>
        <button
          aria-label="지도 장소 상세 닫기"
          className="place-map-sheet-close"
          onClick={onClose}
          type="button"
        >
          <X size={14} />
        </button>
      </div>
      <div className="place-map-sheet-actions">
        <a href={kakaoSearchUrl} rel="noreferrer" target="_blank">
          <Car size={14} />
          길찾기
        </a>
        <button onClick={() => onShowPlaceDetail(place)} type="button">
          <Info size={14} />
          상세 보기
        </button>
      </div>
    </section>
  );
}

function PlaceDetailDialog({
  dayNumber,
  onClose,
  place,
}: {
  dayNumber: number;
  onClose: () => void;
  place: ItineraryPlace;
}) {
  const titleId = "place-detail-title";
  const detailText = place.meta || "메모가 아직 없어요.";
  const addressText = place.address || "주소 정보 없음";
  const categoryText = place.category || place.categoryCode || "장소";
  const coordinateText =
    Number.isFinite(place.latitude) && Number.isFinite(place.longitude)
      ? `${place.latitude}, ${place.longitude}`
      : "좌표 정보 없음";
  const kakaoPlaceUrl =
    place.placeUrl ||
    `https://map.kakao.com/link/search/${encodeURIComponent(place.address || place.label)}`;

  return (
    <div
      className="sheet-backdrop place-detail-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="trip-select-sheet place-detail-dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-head">
          <div>
            <h2 id={titleId}>{place.label} 장소 상세</h2>
            <p className="meta">Day {dayNumber} 지도에서 선택한 장소</p>
          </div>
          <button className="btn sm ghost" type="button" onClick={onClose}>
            닫기
          </button>
        </div>
        <div className="place-detail-summary" aria-label="장소 요약">
          <span>Day {dayNumber}</span>
          {place.time && <span>{place.time}</span>}
          <span>{categoryText}</span>
        </div>
        <div className="place-detail-fields">
          <section>
            <strong>주소</strong>
            <p>{addressText}</p>
          </section>
          <section>
            <strong>메모</strong>
            <p>{detailText}</p>
          </section>
          <section>
            <strong>좌표</strong>
            <p>{coordinateText}</p>
          </section>
        </div>
        <a
          className="btn primary"
          href={kakaoPlaceUrl}
          rel="noreferrer"
          target="_blank"
        >
          카카오맵에서 보기
        </a>
      </section>
    </div>
  );
}

function DroppableDayTab({
  canDrop,
  count,
  dateLabel,
  day,
  isActive,
  isDragOver,
  onSelect,
}: {
  canDrop: boolean;
  count: number;
  dateLabel: string;
  day: number;
  isActive: boolean;
  isDragOver: boolean;
  onSelect: (day: number) => void;
}) {
  const { setNodeRef } = useDroppable({
    id: dayDropId(day),
    disabled: !canDrop,
  });
  const isOver = isDragOver;
  const className = [
    "day-tab",
    isActive ? "active" : "",
    canDrop ? "drop-target" : "",
    isOver ? "over" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      aria-label={`Day ${day} ${dateLabel} ${
        count > 0 ? `${count}곳` : "비어 있음"
      }`}
      className={className}
      data-day-drop-id={dayDropId(day)}
      key={day}
      onClick={() => onSelect(day)}
      ref={setNodeRef}
      type="button"
    >
      <strong>Day {day}</strong>
      <span>{dateLabel}</span>
      <i>{count > 0 ? `${count}곳` : "비어 있음"}</i>
    </button>
  );
}

/**
 * 다른 날짜에서 끌고 온 카드가 들어갈 자리표시. 활성 카드의 sortable id로 등록해
 * 대상 날짜의 SortableContext 멤버가 되게 한다. dnd-kit이 이 항목을 활성 항목으로
 * 보고 주변 카드를 밀어내므로, 같은 날짜 이동과 동일한 동작이 나온다.
 */
/**
 * 왼쪽 번호 열. 카드 목록과 형제로 놓여 행 순서에 고정된다. 카드가 재정렬되거나
 * 유령이 끼어들어도 이 배지는 자리를 지킨다. 번호는 슬롯 순번이라 들고 있는
 * 카드(유령)도 자동으로 한 칸을 차지한다.
 */
function TimelineSlotMarker({
  isLast,
  number,
}: {
  isLast: boolean;
  number: number;
}) {
  return (
    <div
      aria-hidden="true"
      className={isLast ? "timeline-marker last" : "timeline-marker"}
    >
      <span>{number}</span>
    </div>
  );
}

function TimelineGhostCard({
  label,
  sortableId,
}: {
  label: string;
  sortableId: string;
}) {
  const { setNodeRef, transform, transition } = useSortable({ id: sortableId });

  return (
    <div
      aria-hidden="true"
      className="timeline-slot timeline-ghost"
      data-sortable-id={sortableId}
      data-timeline-ghost
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <div className="timeline-sortable-card">
        <article className="place-detail timeline-ghost-card">
          <GripVertical size={16} />
          <strong>{label}</strong>
        </article>
      </div>
    </div>
  );
}

function DroppableTimelinePosition({
  dayNumber,
  isCrossDay,
  position,
}: {
  dayNumber: number;
  isCrossDay: boolean;
  position: number;
}) {
  const { isOver, setNodeRef } = useDroppable({
    id: dayPositionDropId(dayNumber, position),
  });
  const className = [
    "timeline-insertion-slot",
    isCrossDay ? "cross-day" : "",
    isOver ? "over" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      aria-hidden="true"
      className={className}
      data-day={dayNumber}
      data-position={position}
      ref={setNodeRef}
    />
  );
}

function SortablePlaceItem({
  canEditTrip,
  currentDay,
  dayNumbers,
  disabled,
  hasTimeOrderWarning,
  isMoving,
  isPreviewMode,
  onCancelRecommendationPreviewPlace,
  onDelete,
  onEdit,
  onMove,
  onPreviewTimeChange,
  onSaveRecommendationPreviewPlace,
  onToggleTimeEditor,
  openTimeEditorId,
  onSelectRecommendationPreviewPlace,
  place,
  previewDayPlaceCounts,
  places,
  trip,
}: {
  canEditTrip: boolean;
  currentDay: number;
  dayNumbers: number[];
  disabled: boolean;
  hasTimeOrderWarning: boolean;
  isMoving: boolean;
  isPreviewMode: boolean;
  onCancelRecommendationPreviewPlace: (previewId: string) => void;
  onDelete: (place: ItineraryPlace) => void;
  onEdit: (place: ItineraryPlace) => void;
  onMove: (
    place: DisplayedPlace,
    dayNumber: number,
    position: number,
  ) => Promise<void>;
  onPreviewTimeChange: (place: DisplayedPlace, time: string) => void;
  onSaveRecommendationPreviewPlace: (previewId: string) => void;
  onToggleTimeEditor: (cardId: string, willOpen: boolean) => void;
  openTimeEditorId: string | null;
  onSelectRecommendationPreviewPlace: (previewId: string) => void;
  place: DisplayedPlace;
  previewDayPlaceCounts: Record<number, number>;
  places: DisplayedPlace[];
  trip: Trip;
}) {
  const sortablePlaceId = displayedPlaceSortableId(place);
  const sortableId =
    sortablePlaceId ?? `missing:${place.time}-${place.label}`;
  const canSortPlace = Boolean(sortablePlaceId);
  const isRecommendationPreviewPlace = Boolean(
    place.isRecommendationPreview && place.previewId,
  );
  const {
    attributes,
    isDragging,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({
    id: sortableId,
    disabled: !canEditTrip || !canSortPlace || disabled,
  });
  const cardStyle = {
    // Horizontal pointer movement is still used for Day-tab collision detection,
    // but rendering it expands the scrollable timeline beyond the viewport.
    transform: CSS.Transform.toString(
      transform ? { ...transform, x: 0 } : null,
    ),
    transition,
  };
  // 시간 수정창 아코디언 식별자. 미리보기 카드와 기존 카드 모두 값이 있다.
  const timeEditorCardId = displayedPlaceWarningKey(place);
  const className = [
    "timeline-slot",
    isDragging ? "dragging" : "",
    isMoving ? "moving" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const sortableListeners = listeners ?? {};
  /* 카드 전체에는 포인터 리스너만 건다. onKeyDown 까지 걸면 카드 안쪽 버튼에서
     올라온 Enter·Space 가 키보드 드래그를 시작시킨다. 키보드 경로는 아래
     화면에서 감춘 활성자 버튼이 맡는다. */
  const { onKeyDown: _sortableKeyDown, ...cardPointerListeners } =
    sortableListeners as Record<string, unknown>;
  const moveWithKeyboard = (
    event: KeyboardEvent<HTMLButtonElement>,
  ): boolean => {
    if (!canSortPlace || disabled) return false;
    const currentIndex = places.findIndex(
      (item) => displayedPlaceSortableId(item) === sortableId,
    );
    if (currentIndex < 0) return false;
    if (event.key === "ArrowUp" && currentIndex > 0) {
      event.preventDefault();
      void onMove(place, currentDay, currentIndex);
      return true;
    }
    if (event.key === "ArrowDown" && currentIndex < places.length - 1) {
      event.preventDefault();
      void onMove(place, currentDay, currentIndex + 2);
      return true;
    }
    if (
      event.shiftKey &&
      (event.key === "ArrowLeft" || event.key === "ArrowRight")
    ) {
      const currentDayIndex = dayNumbers.indexOf(currentDay);
      const nextDayIndex =
        event.key === "ArrowRight" ? currentDayIndex + 1 : currentDayIndex - 1;
      const targetDay = dayNumbers[nextDayIndex];
      if (!targetDay) return false;
      event.preventDefault();
      const targetCount = isPreviewMode
        ? (previewDayPlaceCounts[targetDay] ?? 0)
        : (trip.days[targetDay]?.length ?? 0);
      void onMove(place, targetDay, targetCount + 1);
      return true;
    }
    return false;
  };

  return (
    <div
      className={className}
      data-place-id={place.id}
      data-sortable-id={sortableId}
      ref={setNodeRef}
    >
      <div className="timeline-sortable-card">
      {/* 손잡이를 없애고 카드 아무 데나 잡을 수 있게 한다. 34px 짜리 목표를
          겨냥하는 것보다 손에 맞는다. 안쪽 버튼들은
          activationConstraint(마우스 8px · 터치 800ms) 덕분에 짧은 탭으로 그대로 눌린다.

          포인터 리스너만 카드에 건다. useSortable 의 attributes 에는
          role="button" 이 들어 있는데, 그걸 카드에 붙이면 ARIA 규칙상
          안쪽 컨트롤이 접근성 트리에서 사라진다. attributes 는 아래
          화면에서 감춘 활성자 버튼이 계속 들고 있는다. */}
      <article
        style={cardStyle}
        className={
          isRecommendationPreviewPlace
            ? "place-detail recommendation-preview-place"
            : "place-detail"
        }
        {...(canEditTrip && canSortPlace && !disabled ? cardPointerListeners : {})}
      >
        {canEditTrip && canSortPlace && (
          <button
            className="drag-handle sr-only"
            type="button"
            aria-label={`${place.label} 순서 이동`}
            disabled={disabled}
            {...attributes}
            {...sortableListeners}
            onKeyDown={(event) => {
              if (!moveWithKeyboard(event))
                sortableListeners.onKeyDown?.(event);
            }}
          />
        )}
        {isRecommendationPreviewPlace && place.previewId ? (
          <button
            className="place-copy recommendation-preview-place-select"
            type="button"
            aria-label={`${place.label} 지도에서 보기`}
            onClick={() => onSelectRecommendationPreviewPlace(place.previewId!)}
            disabled={disabled}
          >
            <div className="place-prototype-meta recommendation-preview-meta">
              {place.time && (
                <>
                  <span>{place.time}</span>
                  <span className="preview-meta-separator" aria-hidden="true">
                    ·
                  </span>
                </>
              )}
              <em aria-hidden="true">{getPlaceEmoji(place)}</em>
              <span className="preview-meta-separator" aria-hidden="true">
                ·
              </span>
              <span className="preview-candidate-index">
                {place.isRecommendationSelected ? "저장 선택" : "추천 후보"}
              </span>
              <span className="preview-meta-separator" aria-hidden="true">
                ·
              </span>
              <span className="preview-phase-label">
                {recommendationPreviewPhaseLabel(place)}
              </span>
            </div>
            <h4>{place.label}</h4>
            <div className="meta">{place.meta}</div>
          </button>
        ) : (
          <div className="place-copy">
            <div className="place-prototype-meta">
              {place.time && (
                <span className="place-time-with-warning">
                  <span>{place.time}</span>
                  {hasTimeOrderWarning && canEditTrip && !isPreviewMode && (
                    <button
                      type="button"
                      className="place-time-warning-button"
                      aria-label={`${place.label} 방문 시간 확인`}
                      title="앞 장소보다 이른 시간입니다. 방문 시간을 확인해 주세요."
                      onClick={() => onEdit(place)}
                    >
                      <AlertTriangle size={13} aria-hidden="true" />
                      <span>시간 확인</span>
                    </button>
                  )}
                </span>
              )}
              <em aria-hidden="true">{getPlaceEmoji(place)}</em>
            </div>
            <h4>{place.label}</h4>
            <div className="meta">{place.meta}</div>
          </div>
        )}
        {isMoving && <span className="place-moving-badge">이동 중</span>}
        {isRecommendationPreviewPlace && place.previewId ? (
          <div className="place-actions recommendation-preview-place-actions">
            <button
              className="btn sm ghost"
              type="button"
              aria-label={`${place.label} 후보 저장`}
              onClick={(event) => {
                event.stopPropagation();
                onSaveRecommendationPreviewPlace(place.previewId!);
              }}
              disabled={disabled || place.isRecommendationSelected}
            >
              {place.isRecommendationSelected ? "저장됨" : "저장"}
            </button>
            <details
              className="preview-time-edit"
              aria-label={`${place.label} 시간 수정`}
              open={
                timeEditorCardId
                  ? openTimeEditorId === timeEditorCardId
                  : undefined
              }
              onToggle={(event) => {
                if (!timeEditorCardId) return;
                onToggleTimeEditor(
                  timeEditorCardId,
                  (event.currentTarget as HTMLDetailsElement).open,
                );
              }}
            >
              <summary>수정</summary>
              <PlaceTimePicker
                disabled={disabled}
                value={place.time ?? ""}
                onChange={(time) => onPreviewTimeChange(place, time)}
              />
            </details>
            <button
              className="btn sm line"
              type="button"
              aria-label={`${place.label} 후보 제외`}
              onClick={(event) => {
                event.stopPropagation();
                onCancelRecommendationPreviewPlace(place.previewId!);
              }}
              disabled={disabled}
            >
              후보 제외
            </button>
          </div>
        ) : canEditTrip ? (
          <div className="place-actions">
            {isPreviewMode ? (
              <details
                className="preview-time-edit"
                aria-label={`${place.label} 시간 수정`}
                open={
                  timeEditorCardId
                    ? openTimeEditorId === timeEditorCardId
                    : undefined
                }
                onToggle={(event) => {
                  if (!timeEditorCardId) return;
                  onToggleTimeEditor(
                    timeEditorCardId,
                    (event.currentTarget as HTMLDetailsElement).open,
                  );
                }}
              >
                <summary>수정</summary>
                <PlaceTimePicker
                  disabled={disabled}
                  value={place.time ?? ""}
                  onChange={(time) => onPreviewTimeChange(place, time)}
                />
              </details>
            ) : (
              <button
                className="btn sm ghost"
                type="button"
                onClick={() => onEdit(place)}
                disabled={!place.id || disabled}
              >
                수정
              </button>
            )}
            {!isPreviewMode && (
              <button
                className="btn sm line"
                type="button"
                onClick={() => onDelete(place)}
                disabled={!place.id || disabled || isMoving}
              >
                삭제
              </button>
            )}
          </div>
        ) : null}
      </article>
      </div>
    </div>
  );
}

function PlaceTimePicker({
  disabled,
  onChange,
  value,
}: {
  disabled: boolean;
  onChange: (time: string) => void;
  value: string;
}) {
  const parsed = parsePlaceTime(value);
  const isTimeSet = Boolean(value && parsed);
  const base = placeTimeBase(value);
  const displayValue =
    isTimeSet && parsed
      ? formatPlaceTime(parsed.hour, parsed.minute)
      : "시간 없음";

  const setTime = (hour: number, minute: number) => {
    onChange(formatPlaceTime((hour + 24) % 24, minute));
  };
  const shiftHour = (amount: number) => {
    setTime(base.hour + amount, base.minute);
  };
  const shiftMinute = (amount: number) => {
    const totalMinutes = base.hour * 60 + base.minute + amount;
    const normalized = (totalMinutes + 24 * 60) % (24 * 60);
    setTime(Math.floor(normalized / 60), normalized % 60);
  };

  return (
    <div className="field place-time-picker">
      <span>방문 시간</span>
      <div
        className="time-picker-control"
        role="group"
        aria-label="방문 시간 선택"
      >
        <div className="time-picker-display" aria-live="polite">
          <strong>{displayValue}</strong>
        </div>
        <div className="time-picker-spinners">
          <div className="time-stepper" aria-label="방문 시 조절">
            <span>시</span>
            <button
              type="button"
              className="time-stepper-button"
              onClick={() => shiftHour(-1)}
              disabled={disabled}
              aria-label="방문 시간 1시간 감소"
            >
              -
            </button>
            <strong>{String(base.hour).padStart(2, "0")}</strong>
            <button
              type="button"
              className="time-stepper-button"
              onClick={() => shiftHour(1)}
              disabled={disabled}
              aria-label="방문 시간 1시간 증가"
            >
              +
            </button>
          </div>
          <div className="time-stepper" aria-label="방문 분 조절">
            <span>분</span>
            <button
              type="button"
              className="time-stepper-button"
              onClick={() => shiftMinute(-placeMinuteStep)}
              disabled={disabled}
              aria-label="방문 시간 10분 감소"
            >
              -10
            </button>
            <strong>{String(base.minute).padStart(2, "0")}</strong>
            <button
              type="button"
              className="time-stepper-button"
              onClick={() => shiftMinute(placeMinuteStep)}
              disabled={disabled}
              aria-label="방문 시간 10분 증가"
            >
              +10
            </button>
          </div>
        </div>
        <div className="time-picker-actions">
          {!isTimeSet && (
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => onChange(defaultPlaceTime)}
              disabled={disabled}
            >
              {defaultPlaceTime} 설정
            </button>
          )}
          <button
            type="button"
            className="btn sm line"
            onClick={() => onChange("")}
            disabled={disabled || !isTimeSet}
          >
            시간 비우기
          </button>
        </div>
      </div>
    </div>
  );
}

function PlacePreviewMapCard({
  preview,
  saveEligibility,
}: {
  preview: PlacePreviewState;
  saveEligibility: PlaceSaveEligibility;
}) {
  const place = preview.place;
  const marker = place ? placePreviewMarker(place) : null;
  const helperText =
    saveEligibility === "requiresExplicitCandidate"
      ? "검색 결과를 지도에 미리 표시했어요. 저장하려면 후보를 직접 선택해 주세요."
      : saveEligibility === "saveSelected"
        ? "저장할 장소로 선택되어 있어요."
        : "장소를 검색하면 지도에 표시돼요.";
  const fallback = (
    <div
      className={
        place ? "place-preview-fallback has-place" : "place-preview-fallback"
      }
    >
      <MapIcon size={18} aria-hidden="true" />
      <div>
        <strong>{place?.label || "장소를 검색하면 지도에 표시돼요"}</strong>
        <span>
          {place?.address ||
            place?.meta ||
            "추천 장소나 검색 후보가 여기에 미리 표시됩니다."}
        </span>
      </div>
    </div>
  );

  return (
    <section className="place-preview-map-card" aria-label="장소 지도 미리보기">
      <div className="place-preview-map-head">
        <div>
          <span className="eyebrow">지도 미리보기</span>
          <h3>{place?.label || "선택할 장소 확인"}</h3>
        </div>
        <span
          className={
            saveEligibility === "saveSelected"
              ? "place-preview-state ready"
              : "place-preview-state"
          }
        >
          {saveEligibility === "saveSelected"
            ? "저장 가능"
            : "확인 필요"}
        </span>
      </div>
      {marker ? (
        <KakaoMapView
          ariaLabel={`${place?.label ?? "장소"} 지도 미리보기`}
          fallback={fallback}
          markers={[marker]}
          onSelectMarker={() => undefined}
          selectedMarkerId={marker.id}
        />
      ) : (
        fallback
      )}
      {place && (
        <div className="place-preview-details">
          <strong>{place.label}</strong>
          <span>{place.address || place.meta || "장소 정보 확인"}</span>
        </div>
      )}
      <p className="place-preview-helper">{helperText}</p>
    </section>
  );
}

/**
 * 가로 줄을 손이나 마우스로 끌어서 민다.
 *
 * `overflow-x: auto` 만으로는 마우스로 끌 수 없다. 손가락은 브라우저가
 * 알아서 굴려주지만 마우스는 휠뿐이라, 데스크톱에서 "안 넘어간다" 가 된다.
 *
 * 끌고 나서 손을 떼면 그 자리의 칩이 눌리면 안 된다. 6px 넘게 움직였으면
 * 뒤따라오는 click 을 잡아 삼킨다.
 */
/* 가로 줄을 마우스로 잡고 밀 수 있게 한다.
   바깥에서 이미 ref 를 쓰고 있으면(예: 날짜 스트립 중앙 정렬) 그것을 받아 쓴다.

   setPointerCapture 는 쓰지 않는다. 캡처가 걸리면 뒤따르는 click 이
   눌린 버튼이 아니라 캡처한 컨테이너로 간다. 그러면 날짜를 눌러도 선택이 안 된다.
   대신 window 에 리스너를 걸어 줄 밖으로 나가도 끝을 놓치지 않는다. */
function useDragScroll(externalRef?: MutableRefObject<HTMLDivElement | null>) {
  const ownRef = useRef<HTMLDivElement | null>(null);
  const ref = externalRef ?? ownRef;
  const swallowClick = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    // 끌고 밖에서 손을 떼면 click 이 아예 안 온다. 그대로 두면 다음 클릭이 대신 먹힌다.
    swallowClick.current = false;
    const node = ref.current;
    if (!node) return;
    // 손가락은 브라우저 기본 가로 스크롤이 이미 잘 돈다.
    // 여기서 가로채면 그 관성까지 뺏는다. 마우스·펜만 처리한다.
    if (event.pointerType === "touch") return;

    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startLeft = node.scrollLeft;
    let moved = false;

    const onMove = (moveEvent: globalThis.PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return;
      const dx = moveEvent.clientX - startX;
      if (!moved && Math.abs(dx) > DRAG_SCROLL_THRESHOLD_PX) moved = true;
      if (!moved) return;
      // 끄는 동안 글자가 잡혀 반전되면 지저분하다.
      moveEvent.preventDefault();
      node.scrollLeft = startLeft - dx;
    };
    const finish = (endEvent: globalThis.PointerEvent) => {
      if (endEvent.pointerId !== pointerId) return;
      swallowClick.current = moved;
      cleanupRef.current?.();
    };

    cleanupRef.current = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", finish);
      cleanupRef.current = null;
    };
    window.addEventListener("pointermove", onMove, { passive: false });
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", finish);
  };

  /* 밀다가 칩 위에서 손을 떼면 그 날짜가 선택돼 버린다. 그 클릭만 먹는다. */
  const onClickCapture = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!swallowClick.current) return;
    swallowClick.current = false;
    event.preventDefault();
    event.stopPropagation();
  };

  return { ref, onPointerDown, onClickCapture };
}

export function PlaceEditorSheet({
  batchRecovery,
  dayNumber,
  dayOptions,
  error,
  form,
  isLoadingSearch,
  isSaving,
  mode,
  onChange,
  onClose,
  onDayChange,
  onSelectedDayRef,
  onDiscardDraft,
  onRemoveBasketItem,
  onRetryBasketDay,
  onSearchInput,
  onSearchChange,
  onSelectSearchCandidate,
  onSubmit,
  placeBasket,
  preview,
  saveEligibility,
  searchCandidates,
  searchError,
  searchQuery,
  restoredDraftMessage,
}: {
  batchRecovery: BatchPlaceRecovery;
  dayNumber: number;
  dayOptions: { dayNumber: number; dateLabel: string; count: number }[];
  error: string;
  form: TripPlaceRequest;
  isLoadingSearch: boolean;
  isSaving: boolean;
  mode: "add" | "edit";
  onChange: (form: TripPlaceRequest) => void;
  onClose: () => void;
  onDayChange: (dayNumber: number) => void;
  onSelectedDayRef: (node: HTMLButtonElement | null) => void;
  onDiscardDraft: () => void;
  onRemoveBasketItem: (basketId: string) => void;
  onRetryBasketDay: (dayNumber: number) => void;
  onSearchInput?: () => void;
  onSearchChange: (query: string) => void;
  onSelectSearchCandidate: (candidate: PlaceSearchCandidate) => void;
  onSubmit: () => void;
  placeBasket: PlaceBasketItem[];
  preview: PlacePreviewState;
  saveEligibility: PlaceSaveEligibility;
  searchCandidates: PlaceSearchCandidate[];
  searchError: string;
  searchQuery: string;
  restoredDraftMessage: string;
}) {
  const dayDragScroll = useDragScroll();
  const [inputSearchQuery, setInputSearchQuery] = useState(searchQuery);
  const searchDebounceTimerRef = useRef<number | null>(null);
  const hasPlaceBasket = mode === "add" && placeBasket.length > 0;

  useEffect(() => {
    if (searchDebounceTimerRef.current === null)
      setInputSearchQuery(searchQuery);
  }, [searchQuery]);

  useEffect(
    () => () => {
      if (searchDebounceTimerRef.current !== null)
        window.clearTimeout(searchDebounceTimerRef.current);
    },
    [],
  );

  const updateInputSearchQuery = (query: string) => {
    setInputSearchQuery(query);
    onSearchInput?.();
    if (searchDebounceTimerRef.current !== null)
      window.clearTimeout(searchDebounceTimerRef.current);
    searchDebounceTimerRef.current = window.setTimeout(() => {
      searchDebounceTimerRef.current = null;
      onSearchChange(query);
    }, PLACE_SEARCH_DEBOUNCE_MS);
  };

  return (
    <div className="sheet-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="trip-select-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="place-editor-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-head">
          <div>
            <h2 id="place-editor-title">
              {mode === "add" ? "장소 추가" : "장소 수정"}
            </h2>
            <p className="meta">
              {mode === "add"
                ? "장소를 검색해 선택한 뒤 목록에 담아 저장하세요."
                : "장소명, 방문 시간, 메모를 수정하세요."}
            </p>
          </div>
          <button
            className="btn sm ghost"
            type="button"
            onClick={onClose}
            disabled={isSaving}
          >
            닫기
          </button>
        </div>
        <div className="form place-editor-form">
          {restoredDraftMessage && (
            <DraftRestoreNotice
              message={restoredDraftMessage}
              onDiscard={onDiscardDraft}
            />
          )}
          {mode === "add" && (
            <div className="place-search-panel">
              <label className="field">
                장소 검색
                <input
                  name="place-search"
                  placeholder="장소명이나 주소 검색"
                  value={inputSearchQuery}
                  onChange={(event) => updateInputSearchQuery(event.target.value)}
                />
              </label>
              {isLoadingSearch && (
                <p className="place-search-status">
                  장소 검색 결과를 불러오는 중입니다.
                </p>
              )}
              {searchError && (
                <p className="place-search-status error">{searchError}</p>
              )}
              {searchCandidates.length > 0 && (
                <div
                  className="place-search-results"
                  role="list"
                  aria-label="장소 검색 결과"
                >
                  {searchCandidates.map((candidate, index) => (
                    <button
                      aria-label={`${candidate.title} 선택`}
                      className="place-search-result"
                      key={
                        candidate.id ??
                        candidate.externalPlaceId ??
                        `${candidate.title}:${index}`
                      }
                      type="button"
                      onClick={() => onSelectSearchCandidate(candidate)}
                    >
                      <span>
                        <strong>{candidate.title}</strong>
                        <em>{candidate.categoryName ?? "장소"}</em>
                      </span>
                      <small>{candidate.address ?? candidate.meta}</small>
                    </button>
                  ))}
                </div>
              )}
              {hasPlaceBasket && (
                <section
                  className="place-basket"
                  aria-label="추가할 장소 목록"
                >
                  <div className="place-basket-head">
                    <strong>추가할 장소 {placeBasket.length}개</strong>
                  </div>
                  <div className="place-basket-list" role="list">
                    {placeBasket.map((item) => (
                      <div
                        className="place-basket-row"
                        key={item.basketId}
                        role="listitem"
                      >
                        <span>
                          <strong>{item.label}</strong>
                          <em>{item.category ?? item.categoryCode ?? "장소"}</em>
                          <small>{item.address ?? item.meta ?? "장소 정보 확인"}</small>
                        </span>
                        <button
                          aria-label={`${item.label} 제거`}
                          className="btn sm ghost"
                          type="button"
                          onClick={() => onRemoveBasketItem(item.basketId)}
                          disabled={isSaving}
                        >
                          제거
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {hasPlaceBasket && batchRecovery.kind === "missingDay" && (
                <section
                  className="place-basket-recovery"
                  aria-label="batch place missing day recovery"
                >
                  <strong>최신 일정에서 저장할 Day를 선택해 주세요.</strong>
                  <div className="place-basket-recovery-actions">
                    {batchRecovery.availableDays.map((dayNumber) => (
                      <button
                        className="btn sm line"
                        disabled={isSaving}
                        key={dayNumber}
                        type="button"
                        onClick={() => onRetryBasketDay(dayNumber)}
                      >
                        Day {dayNumber} 저장하기
                      </button>
                    ))}
                  </div>
                </section>
              )}
              {!hasPlaceBasket && form.label && (
                <div
                  className="place-selected-summary"
                  aria-label="선택한 장소"
                >
                  <strong>{form.label}</strong>
                  <span>{form.meta || "장소 정보 확인"}</span>
                </div>
              )}
              {!hasPlaceBasket && searchQuery.trim() && !isLoadingSearch && searchCandidates.length === 0 && !searchError && (
                <p className="place-search-status">
                  검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.
                </p>
              )}
            </div>
          )}
          {mode === "add" && (
            <PlacePreviewMapCard
              preview={preview}
              saveEligibility={saveEligibility}
            />
          )}
          {mode === "edit" && (
            <>
              {dayOptions.length > 1 && (
                <div className="field place-day-picker">
                  <span>날짜</span>
                  {/* 네이티브 select 는 항목 높이를 운영체제가 정해 손댈 수 없다.
                      칩 줄로 두면 칸을 넉넉히 잡고 장소 수까지 같이 보여줄 수 있다. */}
                  <div
                    aria-label="날짜 선택"
                    className="place-day-options"
                    role="radiogroup"
                    {...dayDragScroll}
                  >
                    {dayOptions.map((option) => {
                      const selected = option.dayNumber === dayNumber;
                      return (
                        <button
                          aria-checked={selected}
                          className={
                            selected
                              ? "place-day-chip selected"
                              : "place-day-chip"
                          }
                          disabled={isSaving}
                          key={option.dayNumber}
                          onClick={() => onDayChange(option.dayNumber)}
                          ref={selected ? onSelectedDayRef : undefined}
                          role="radio"
                          type="button"
                        >
                          <strong>Day {option.dayNumber}</strong>
                          {option.dateLabel && <em>{option.dateLabel}</em>}
                          <i>
                            {option.count > 0 ? `${option.count}곳` : "비어 있음"}
                          </i>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              <PlaceTimePicker
                disabled={isSaving}
                value={form.time ?? ""}
                onChange={(time) => onChange({ ...form, time })}
              />
              <input
                type="hidden"
                name="place-time"
                value={form.time ?? ""}
                readOnly
              />
            </>
          )}
          {mode === "edit" ? (
            <label className="field">
              장소명
              <input
                name="place-label"
                placeholder="성산일출봉"
                value={form.label}
                onChange={(event) =>
                  onChange({ ...form, label: event.target.value })
                }
              />
            </label>
          ) : null}
          {mode === "edit" && (
            <label className="field">
              메모
              <textarea
                name="place-meta"
                placeholder="이동 메모나 예약 정보를 적어주세요"
                value={form.meta ?? ""}
                onChange={(event) =>
                  onChange({ ...form, meta: event.target.value })
                }
              />
            </label>
          )}
          {error && <p className="form-error">{error}</p>}
        </div>
        <div className="sheet-actions">
          <Button full disabled={isSaving} onClick={onSubmit}>
            {isSaving
              ? "저장 중입니다"
              : hasPlaceBasket
                ? `${placeBasket.length}개 저장하기`
                : "저장하기"}
          </Button>
        </div>
      </section>
    </div>
  );
}
