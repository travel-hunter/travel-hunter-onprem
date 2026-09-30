import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { createPolicyRegionMap, type PolicyRegionMapHandle, type RegionCounts, type RegionMapPlace } from "./regionMapEngine";

/* 지도 칸은 화면에 남은 높이를 그대로 쓴다. 그림 비율은 더 이상 높이를 정하지 않는다 -
   엔진이 viewBox 를 칸 비율에 맞추므로(regionMapEngine 의 target) 어떤 높이를 줘도 빈 띠 없이
   꽉 찬다. 그래서 기기마다 다른 것은 지도 크기가 아니라 바다 폭이다.
   스크롤은 window 가 아니라 .app-container 안에서 일어나고(768px 부터는 상단 내비 밑에
   74px 내려앉는다) 그 높이가 곧 화면이다. 탭바·시트 손잡이 몫은 .screen 의
   padding-bottom 이 이미 갖고 있어(폰 100, 데스크톱 40) 그대로 빼면 스크롤이 안 생긴다.
   HINT 는 지도 밑 안내문 한 줄 자리다. */
const HINT = 30, MIN_H = 220;
/* 시트에 가려 이보다 적게 보이면(px) 지도를 다시 맞추지 않는다 */
const MIN_VISIBLE = 60;
function fitHeight(host: HTMLElement) {
  const scroller = host.closest(".app-container");
  const boxTop = scroller ? scroller.getBoundingClientRect().top : 0;
  const boxHeight = scroller ? scroller.clientHeight : window.innerHeight;
  const top = host.getBoundingClientRect().top - boxTop + (scroller ? scroller.scrollTop : window.scrollY);
  const screen = host.closest(".screen");
  const reserved = screen ? parseFloat(getComputedStyle(screen).paddingBottom) || 0 : 0;
  /* 바다가 깔리는 칸(.thmap-stage)은 탭바 바로 위까지 내려간다. 지도는 그 안에서 안내문
     한 줄을 남기고 자리를 잡고, 지도가 짧아 남는 아래쪽은 바다로 채워진다.
     .screen 의 padding-bottom(폰 100)은 탭바(72)에 시트 손잡이 몫까지 얹은 값이라,
     그대로 두면 바다가 손잡이 위에서 끊긴다. 탭바를 뺀 나머지만큼 칸을 더 키우고
     같은 크기의 음수 여백으로 되돌린다 - 칠해지는 자리만 내려가고 글의 흐름은 그대로다. */
  const available = boxHeight - top - reserved;
  const tabbar = document.querySelector<HTMLElement>(".bottom-tabs")?.offsetHeight ?? 0;
  const spill = Math.max(0, reserved - tabbar);
  const stage = host.closest<HTMLElement>(".thmap-stage");
  if (stage) {
    stage.style.height = Math.max(MIN_H + HINT, Math.round(available + spill)) + "px";
    stage.style.marginBottom = -Math.round(spill) + "px";
  }
  return Math.max(MIN_H, Math.round(available - HINT));
}

/* 지역 지도 껍데기. 안은 regionMapEngine.ts 가 명령형으로 그리고 React 는 호스트만 든다.
   counts 가 바뀌면 통째로 다시 그린다 - 색·흐림이 여섯 속성에 구워져 있어 고치는 것보다
   다시 그리는 게 싸고, listPolicies 는 한 번만 오므로 실제로는 한 번 그린다.
   핀 알약만 React 가 그린다 - 솟은 지역 머리 위 좌표를 엔진에서 받아 그 자리에 세운다. */
export function PolicyRegionMap({
  counts,
  selected,
  onSelect,
  renderPill,
  focus = false,
  showCounts = false,
  coverTop = null,
  sheetLow = false,
  places,
  selectedPlace = null,
  onSelectPlace,
  onBackground,
}: {
  counts: RegionCounts;
  selected: string | null;
  onSelect: (region: string | null) => void;
  renderPill?: (region: string) => ReactNode;
  /** 고른 지역으로 다가가고 둘레를 옅게 눌러 둔다(정책 탭 지도) */
  focus?: boolean;
  /** 이름표 옆에 건수 */
  showCounts?: boolean;
  /** 지도 아래쪽을 덮는 시트의 윗변(화면 y). 그 위쪽에 그림을 맞춘다 */
  coverTop?: number | null;
  /** 시트가 머리만 남긴 지도 중심 자리 */
  sheetLow?: boolean;
  /** 고른 지역 안의 시·군 점 */
  places?: readonly RegionMapPlace[];
  selectedPlace?: string | null;
  onSelectPlace?: (place: string | null) => void;
  /** 아무것도 안 고른 채 빈 바다를 누르면 */
  onBackground?: () => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const handleRef = useRef<PolicyRegionMapHandle | null>(null);
  const onSelectRef = useRef(onSelect);
  const selectedRef = useRef(selected);
  onSelectRef.current = onSelect;
  selectedRef.current = selected;
  const onPlaceRef = useRef(onSelectPlace);
  onPlaceRef.current = onSelectPlace;
  /* 다시 그릴 때(건수가 바뀌면) 새 엔진에 그대로 다시 건다 */
  const viewRef = useRef({ coverTop, sheetLow, places, selectedPlace });
  viewRef.current = { coverTop, sheetLow, places, selectedPlace };
  const applyView = (handle: PolicyRegionMapHandle) => {
    const host = hostRef.current, current = viewRef.current;
    if (!host) return;
    const visible = current.coverTop === null ? null : current.coverTop - host.getBoundingClientRect().top;
    /* 목록이 한 페이지로 올라가 지도가 거의 안 보이면 다시 맞추지 않는다 - 내려올 때 제자리에서 드러나야 한다 */
    if (visible === null || visible >= MIN_VISIBLE) handle.setView({ visible, low: current.sheetLow });
    handle.setPlaces(current.places ?? [], current.selectedPlace);
  };
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const marksRef = useRef<HTMLDivElement | null>(null);
  /* 알약이 카드만큼 커져서 동쪽·서쪽 끝 지역에서는 지도 밖으로 흘러나간다. 그려진 크기를 재서
     지도 칸 안으로 물린다. 위쪽도 마찬가지 - 아래변이 기준점이라 키가 크면 머리가 위로 넘친다. */
  const [fitted, setFitted] = useState<{ x: number; y: number } | null>(null);
  useLayoutEffect(() => {
    const host = hostRef.current, marks = marksRef.current;
    if (!host || !marks || !anchor) { setFitted(null); return; }
    const halfW = marks.offsetWidth / 2, h = marks.offsetHeight;
    const x = Math.min(Math.max(anchor.x, halfW + 8), Math.max(halfW + 8, host.clientWidth - halfW - 8));
    const y = Math.max(anchor.y, h + 8);
    setFitted((prev) => (prev && prev.x === x && prev.y === y ? prev : { x, y }));
  }, [anchor]);

  /* 그리기와 높이 잡기를 한 자리에서, 그리기 단계(useLayoutEffect)에 한다. 그림 비율을 알아야
     높이가 나오고, 첫 그림부터 제 크기여야 알약 좌표(아래 effect)가 어긋나지 않는다. */
  useLayoutEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    /* StrictMode 는 효과를 두 번 돌린다 - 앞 것을 비우지 않으면 지도가 둘이 된다. */
    host.replaceChildren();
    const handle = createPolicyRegionMap(host, counts, (name) => onSelectRef.current(name), {
      focus,
      showCounts,
      onPlace: (place) => onPlaceRef.current?.(place),
    });
    handle.setSelected(selectedRef.current);
    handleRef.current = handle;
    /* 높이를 정한 다음 엔진에 다시 맞추라고 이른다 - 엔진은 칸 비율을 보고 viewBox 를 잡는데
       처음 그릴 때는 아직 CSS 기본 높이다. */
    const size = () => {
      host.style.height = fitHeight(host) + "px";
      handle.resize();
    };
    size();
    applyView(handle);
    window.addEventListener("resize", size);
    /* 창 크기만으로는 놓치는 변화가 있다 - 회전, 주소창 여닫힘, 시트가 밀어내는 폭.
       칸 자체를 본다. 잇달아 들어오면 마지막 것만 처리한다(물마루를 다시 심는 값이다). */
    let timer = 0;
    const ro = typeof ResizeObserver === "function"
      ? new ResizeObserver(() => {
          window.clearTimeout(timer);
          timer = window.setTimeout(() => handle.resize(), 120);
        })
      : null;
    ro?.observe(host);
    return () => {
      window.clearTimeout(timer);
      ro?.disconnect();
      window.removeEventListener("resize", size);
      handle.destroy();
      handleRef.current = null;
    };
  }, [counts, focus, showCounts]);

  /* 시트가 자리에 서면 그 위쪽에 맞춰 다가가고, 고른 지역의 시·군 점을 다시 찍는다 */
  useEffect(() => {
    if (handleRef.current) applyView(handleRef.current);
  }, [coverTop, sheetLow, places, selectedPlace, selected]);

  useEffect(() => {
    const handle = handleRef.current;
    handle?.setSelected(selected);
    const place = () => setAnchor(selected && handle ? handle.anchorScreen(selected) : null);
    place();
    if (!selected) return;
    /* 알약은 화면 좌표라 창 크기가 바뀌면 지도만 따라가고 알약은 남는다. 같이 옮긴다. */
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [selected, counts]);

  const pill = selected && renderPill ? renderPill(selected) : null;
  /* 빈 바다를 누르면 선택이 풀린다(아무것도 안 골랐으면 onBackground). 지도 칸 전체를 여기서 받는다.
     지역·작은 지역 누르기 범위·시군 점·알약 위에서 난 클릭은 제 일을 하고 여기까지 올라오니 걸러낸다. */
  const clearOnOutside = (event: ReactMouseEvent<HTMLDivElement>) => {
    if ((event.target as Element).closest(".thmap-rg, .thmap-hit, .thmap-marks, .thmap-dot")) return;
    if (selected) onSelect(null);
    else onBackground?.();
  };
  return (
    <div className="thmap-wrap" onClick={clearOnOutside}>
      <div className="thmap-host" ref={hostRef} role="group" aria-label="지역별 정책 지도" />
      {pill && (
        <div
          className="thmap-marks"
          ref={marksRef}
          /* 좌표를 못 재는 환경(jsdom)에서도 알약은 떠야 한다 - 가운데 위로 보낸다 */
          style={anchor ? { left: (fitted ?? anchor).x, top: (fitted ?? anchor).y - 8 } : { left: "50%", top: 46 }}
        >
          {pill}
        </div>
      )}
    </div>
  );
}
