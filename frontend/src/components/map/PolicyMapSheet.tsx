import { useEffect, useMemo, useRef, useState } from "react";
import type { Policy } from "../../api";
import { PolicyListCard } from "../cards";
import { getPolicyPhoto, getPolicyVisual } from "../../data/displayConfig";
import { ChevronLeft } from "lucide-react";
import { groupByProgram, groupByRegion, type PolicyGroup } from "../../utils/policyPrograms";
import { REGION_NAMES } from "./regionMapEngine";
import { REGION_PHOTOS } from "./regionPhotos";

const PEEK = 20; /* 닫힌 시트가 내미는 높이 - 손잡이 줄까지만 */
/* 휠 한 칸(보통 deltaY 100)에 페이지가 움직이는 거리의 배율. 0.8 일 때는 페이지를 내리려면 휠을 여러 번
   굴려야 했다(사용자 확인) - 두 배로 올렸다. 한 칸에 160px 이라 두 칸이면 중간을 건너가 지도로 내려간다.
   테스트가 같은 값을 읽도록 내보낸다 - 감도를 다시 만져도 테스트의 px 계산이 따라온다. */
export const WHEEL_DAMP = 1.6;
/* 휠은 손을 떼는 순간이 없다 - 이만큼 조용하면 한 동작이 끝난 것으로 본다(ms).
   이제는 제자리로 되돌리는 데 쓰지 않는다. 전환을 도로 켜 주기만 한다. */
const WHEEL_QUIET = 140;
/* 끌어 올리고 내리는 도중 이 선을 건너가면 그 순간 끝까지 붙는다. 건너기 전에는 그 자리에 멈춘다. */
const MIDDLE = 0.5;
/* 어중간한 자리에 세워 둔 페이지가 가까운 끝으로 스스로 돌아가기까지 머무는 시간(ms).
   마지막으로 만진 때부터 센다 - 머무는 동안 다시 만지면 처음부터 다시 센다.
   영영 서 있으면 매번 손으로 다시 올려야 하고, 손을 떼자마자 튕기면 끌던 손과 부딪힌다.
   0.3초는 손을 뗀 것이 확실해질 만큼만 기다리는 값이다(사용자 확인 뒤 1.2초에서 줄였다). */
const AUTO_SETTLE_DELAY = 300;
/* 양 끝 여유. 중간을 이미 지난 쪽에서 더 밀면 선을 건널 일이 없어 끝 언저리에 어중간하게
   멈춘다 - 이만큼 가까우면 끝으로 붙여 준다. */
const EDGE = 0.08;

/* 지도 위로 붙어 올라오는 정책 페이지. 92건을 한 줄로 늘어놓지 않고 지역 줄 또는
   정책 종류 줄로 접어 보여준다. 올리는 방법 셋 - 손잡이 누르기, 아래로 휠, 끌어올리기.
   다 올라오면 검색줄 바로 아래에 붙고 탭바는 그 뒤로 가라앉는다. */
export function PolicyMapSheet({
  policies,
  enabled,
  open,
  onOpenChange,
  savedSlugs,
  onToggleSave,
}: {
  policies: Policy[];
  /** 지도 화면일 때만 보인다. 목록 화면 위에 겹치면 안 된다. */
  enabled: boolean;
  /** 열림 상태는 URL 이 들고 있다 - 상세에 갔다 뒤로 와도 그대로 돌아오게. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  savedSlugs: Set<string>;
  onToggleSave: (policy: Policy) => Promise<void>;
}) {
  const setOpen = (next: boolean | ((value: boolean) => boolean)) => {
    onOpenChange(typeof next === "function" ? next(open) : next);
  };
  /* 진행도 하나(0=지도, 1=한 페이지)에 모든 표현을 건다. 리렌더 없이 CSS 변수로만 흐른다.
     변수를 body 에 쓰면 한 프레임마다 문서 전체의 스타일이 다시 계산된다 - 정책 카드 수십 장이
     걸린 화면에서 그게 프레임을 떨어뜨렸다. 이 값을 실제로 읽는 세 요소에만 직접 쓴다.
     (시트 안 손잡이는 시트에서 상속받는다.) */
  const tabsRef = useRef<HTMLElement | null>(null);
  const progressTargets = () => {
    if (!tabsRef.current) tabsRef.current = document.querySelector<HTMLElement>(".bottom-tabs");
    return [sheetRef.current, dimRef.current, tabsRef.current];
  };
  const progressRef = useRef(open ? 1 : 0);
  const writeProgress = (value: number) => {
    progressRef.current = value;
    const text = value.toFixed(3);
    for (const node of progressTargets()) node?.style.setProperty("--thmap-progress", text);
  };
  const autoSettleTimerRef = useRef(0);
  const cancelAutoSettle = () => window.clearTimeout(autoSettleTimerRef.current);
  /* 양 끝으로 붙인다 - 전환을 도로 켜고 열림 상태까지 맞춘다. */
  const settleTo = (target: 0 | 1) => {
    cancelAutoSettle();
    setDragging(false);
    writeProgress(target);
    setOpen(target === 1);
    return true;
  };
  /* 끌고 간 자리를 쓴다. 중간을 **건너간** 순간에만 끝까지 붙이고, 건너기 전에는 그 자리에
     멈춘다 - 손을 떼면 도로 올라가던 것을 없앴다(2026-09-20). 중간 아래에서 조금 더 내리는
     동안에도 멈춤이 유지되어야 하므로 "지금 어느 쪽인가"가 아니라 "건너갔는가"로 본다.
     확정했으면 true - 부르는 쪽은 이번 끌기를 거기서 끝낸다. */
  /* 끌기가 끝났다 - 어중간한 자리에 서 있으면 잠깐 뒤 가까운 끝으로 돌아간다.
     중간보다 위면 도로 올라붙고(다시 올리는 수고를 던다), 아래면 지도로 내려간다. */
  const scheduleAutoSettle = () => {
    cancelAutoSettle();
    const value = progressRef.current;
    if (value <= 0 || value >= 1) return;
    autoSettleTimerRef.current = window.setTimeout(
      () => settleTo(progressRef.current > MIDDLE ? 1 : 0),
      AUTO_SETTLE_DELAY,
    );
  };
  const moveTo = (next: number) => {
    const prev = progressRef.current;
    const value = Math.max(0, Math.min(1, next));
    writeProgress(value);
    /* 끝 여유는 그 끝으로 **다가갈 때만** 본다 - 끝에서 출발할 때도 보면 손을 대자마자
       도로 붙어 버린다(없앤 스프링백이 그 모습이다). */
    const toward = Math.sign(value - prev);
    if (value <= 0 || (toward < 0 && value <= EDGE) || (prev >= MIDDLE && value < MIDDLE)) return settleTo(0);
    if (value >= 1 || (toward > 0 && value >= 1 - EDGE) || (prev <= MIDDLE && value > MIDDLE)) return settleTo(1);
    return false;
  };
  /* 끄는 동안은 시트·딤·탭바의 전환을 같이 끈다. 시트에만 끄면 탭바가 한 박자 늦게 따라온다. */
  const setDragging = (on: boolean) => {
    document.body.classList.toggle("thmap-dragging", on);
  };
  /* 시트가 닫힌 자리까지 내려가는 거리(px). CSS 의 --thmap-closed-y 와 같은 식이어야 한다. */
  const travelOf = (sheet: HTMLElement) => {
    const tabbar = Number.parseFloat(getComputedStyle(sheet).getPropertyValue("--thmap-tabbar")) || 0;
    return Math.max(1, sheet.clientHeight - PEEK - tabbar);
  };

  const [groupBy, setGroupBy] = useState<"region" | "program">("region");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const sheetRef = useRef<HTMLElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const dimRef = useRef<HTMLDivElement | null>(null);
  const grabRef = useRef<HTMLButtonElement | null>(null);
  const suppressGrabClickRef = useRef(false);
  /* 끌기 한 번의 상태. 도중에 중간을 건너가 확정되면 open 이 바뀌며 아래 effect 가 다시 걸린다 -
     지역 변수로 두면 그 순간 끌기가 사라져, 뒤따르는 click 이 결과를 도로 뒤집었다. */
  const grabDragRef = useRef<{ y: number; from: number; moved: boolean; done: boolean } | null>(null);

  const rows = useMemo<PolicyGroup[]>(
    () => (groupBy === "region" ? groupByRegion(policies, REGION_NAMES) : groupByProgram(policies)),
    [policies, groupBy],
  );
  const detail = openKey ? rows.find((row) => row.key === openKey) ?? null : null;
  /* 카드 사진 출처. 목록 화면이 붙이던 것을 시트 안 카드에도 붙인다 - 사진이 보이는 곳엔 출처가 따라간다. */
  const attributions = detail
    ? Array.from(new Set(detail.items.flatMap((policy) => { const photo = getPolicyPhoto(policy); return photo?.attribution ? [photo.attribution] : []; })))
    : [];

  useEffect(() => {
    if (!enabled && open) setOpen(false);
  }, [enabled, open]);

  /* 올라온 페이지는 검색줄 바로 아래에서 멈춘다 - 검색창은 어느 화면에서도 계속 보여야 한다.
     줄 높이는 화면 폭·필터 칩·상단 내비(768px 이상)에 따라 달라지므로 상수 대신 재서 쓴다.
     같이: 지도 화면은 스크롤하지 않는다. 지도 칸 높이는 화면에 딱 맞게 잡히지만 주소창이
     여닫히며 몇 px 어긋나면 스크롤이 잠깐 생기고, 그 상태에서 굴리면 검색줄이 위로 밀려
     올라가 안 돌아온다. 칸 자체를 못 움직이게 막는 편이 확실하다 - 이 화면엔 볼 것이 없다. */
  useEffect(() => {
    if (!enabled) return;
    const scroller = document.querySelector(".app-container");
    document.body.classList.add("thmap-map-view");
    if (scroller) scroller.scrollTop = 0; /* 다른 화면에서 굴려 둔 자리를 물고 오지 않게 */
    const measure = () => {
      const toolbar = document.querySelector(".prototype-policy-toolbar");
      if (!toolbar) return;
      const bottom = Math.round(toolbar.getBoundingClientRect().bottom);
      if (bottom > 0) document.body.style.setProperty("--thmap-sheet-top", `${bottom}px`);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      document.body.classList.remove("thmap-map-view");
      document.body.style.removeProperty("--thmap-sheet-top");
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    /* 멈춰 세워 둔 자리는 그대로 둔다 - 여기서 덮어쓰면 끌던 손이 튕겨 나간다. */
    if (progressRef.current !== (open ? 1 : 0)) writeProgress(open ? 1 : 0);
    /* 다 올라오면 지도는 안 보인다 - 그 밑에서 파도와 알약 흐림이 계속 돌 이유가 없다.
       움직이는 동안도 멈춘다(policy-map.css 의 thmap-up · thmap-dragging). */
    document.body.classList.toggle("thmap-up", open);
    /* 정책 탭을 떠나면 지운다 - 안 지우면 다른 탭 탭바가 가라앉은 채로 남는다. */
    return () => {
      tabsRef.current?.style.removeProperty("--thmap-progress");
      document.body.classList.remove("thmap-up");
      cancelAutoSettle();
      setDragging(false);
    };
  }, [enabled, open]);

  /* 휠 - 지도 화면 어디서든 아래로 굴리면 올라온다. 올리는 건 가볍게 한 번이면 된다.
     내릴 때는 굴린 만큼 페이지가 실제로 따라 내려오고, 중간을 건너가면 그때 지도까지 간다.
     건너기 전에 멈추면 뒤로 지도가 보이는 채로 그 자리에 선다.
     지도 화면엔 지도 밑 목록이 없으므로(PolicyPages 의 showMap) 삼킬 스크롤도 없다. */
  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onWheel = (event: WheelEvent) => {
      const body = bodyRef.current, sheet = sheetRef.current;
      if (!open) {
        if (event.deltaY > 0) { setOpen(true); event.preventDefault(); }
        return;
      }
      /* 시트 안을 아직 다 못 올렸으면 내용 스크롤이 먼저다 */
      if (body && body.contains(event.target as Node) && body.scrollTop > 0) return;
      /* 다 올라와 있을 때 아래로 굴리는 건 내용 스크롤 - 내려오던 중일 때만 되올리는 데 쓴다 */
      if (event.deltaY >= 0 && progressRef.current >= 1) return;
      if (!sheet) return;
      event.preventDefault();
      cancelAutoSettle();
      setDragging(true);
      const settled = moveTo(progressRef.current + (event.deltaY * WHEEL_DAMP) / travelOf(sheet));
      clearTimeout(timer);
      if (settled) return;
      /* 굴림이 멎으면 전환을 도로 켜고, 그 자리에 잠깐 세워 뒀다가 가까운 끝으로 돌려보낸다 */
      timer = setTimeout(() => {
        setDragging(false);
        scheduleAutoSettle();
      }, WHEEL_QUIET);
    };
    document.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      document.removeEventListener("wheel", onWheel);
      clearTimeout(timer);
    };
  }, [enabled, open]);

  /* 모바일에서 페이지를 내리는 길. 다 올라오면 손잡이는 투명해져 잡을 자리가 안 보인다 -
     목록 맨 위에서 아래로 끌면 어디를 잡든 페이지가 따라 내려온다(터치 전용, 휠은 위 effect). */
  useEffect(() => {
    const body = bodyRef.current, sheet = sheetRef.current;
    if (!open || !body || !sheet) return;
    let startY: number | null = null, startP = 1, active = false, done = false;
    const start = (event: TouchEvent) => {
      if (body.scrollTop > 0) { startY = null; return; }
      cancelAutoSettle();
      startY = event.touches[0].clientY; startP = progressRef.current;
      active = false; done = false;
    };
    const move = (event: TouchEvent) => {
      if (startY === null || done) return;
      const dy = event.touches[0].clientY - startY;
      if (!active) {
        if (dy < 8) { if (dy < -8) startY = null; /* 위로 긋는 건 내용 스크롤이다 */ return; }
        active = true; setDragging(true);
      }
      event.preventDefault();
      if (moveTo(startP - dy / travelOf(sheet))) done = true;
    };
    const end = () => {
      if (active) setDragging(false);
      if (!done) scheduleAutoSettle();
      startY = null; active = false;
    };
    body.addEventListener("touchstart", start, { passive: true });
    body.addEventListener("touchmove", move, { passive: false });
    body.addEventListener("touchend", end);
    body.addEventListener("touchcancel", end);
    return () => {
      body.removeEventListener("touchstart", start);
      body.removeEventListener("touchmove", move);
      body.removeEventListener("touchend", end);
      body.removeEventListener("touchcancel", end);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  /* 손잡이 끌기 - 손가락을 그대로 따라간다. 6px 안이면 클릭으로 본다.
     중간을 건너가면 그 자리에서 끝까지 붙고, 건너기 전에 놓으면 그 자리에 멈춘다. */
  useEffect(() => {
    const grab = grabRef.current, sheet = sheetRef.current;
    if (!grab || !sheet) return;
    const down = (event: PointerEvent) => {
      cancelAutoSettle();
      grabDragRef.current = { y: event.clientY, from: progressRef.current, moved: false, done: false };
      setDragging(true);
      try { grab.setPointerCapture(event.pointerId); } catch { /* 지원 안 하는 브라우저 */ }
    };
    const move = (event: PointerEvent) => {
      const drag = grabDragRef.current;
      if (!drag || drag.done) return;
      const dy = event.clientY - drag.y;
      if (Math.abs(dy) > 6) drag.moved = true;
      if (!drag.moved) return;
      if (moveTo(drag.from - dy / travelOf(sheet))) drag.done = true;
    };
    const end = (event: PointerEvent) => {
      const drag = grabDragRef.current;
      if (!drag) return;
      grabDragRef.current = null;
      setDragging(false);
      if (!drag.done) scheduleAutoSettle();
      if (!drag.moved) return; /* 그냥 클릭이면 click 이 처리 */
      /* pointerup 뒤에 합성되는 click 이 드래그 결과를 다시 뒤집지 못하게 한 번만 막는다. */
      suppressGrabClickRef.current = event.type === "pointerup";
      if (suppressGrabClickRef.current) {
        window.setTimeout(() => {
          suppressGrabClickRef.current = false;
        }, 0);
      }
    };
    grab.addEventListener("pointerdown", down);
    grab.addEventListener("pointermove", move);
    grab.addEventListener("pointerup", end);
    grab.addEventListener("pointercancel", end);
    return () => {
      grab.removeEventListener("pointerdown", down);
      grab.removeEventListener("pointermove", move);
      grab.removeEventListener("pointerup", end);
      grab.removeEventListener("pointercancel", end);
    };
  }, [open]);

  const switchGroup = (next: "region" | "program") => {
    if (next === groupBy) return;
    setGroupBy(next); setOpenKey(null);
  };
  const openTile = (key: string) => { setOpenKey(key); if (bodyRef.current) bodyRef.current.scrollTop = 0; };
  const closeTile = () => { setOpenKey(null); if (bodyRef.current) bodyRef.current.scrollTop = 0; };

  if (!enabled) return null;

  const grabLabel = detail
    ? <>{detail.label} <b>{detail.items.length}</b>건</>
    : groupBy === "region"
      /* 0건 지역도 카드로 내므로 rows.length 는 늘 17 이다 - 세는 건 정책이 있는 시도다 */
      ? <>정책 <b>{policies.length}</b>건 · 시도 {rows.filter((row) => row.items.length > 0).length}곳</>
      : <>정책 <b>{policies.length}</b>건 · {rows.length}가지로 묶임</>;

  return (
    <>
      <div className={open ? "thmap-dim thmap-dim-on" : "thmap-dim"} ref={dimRef} onClick={() => setOpen(false)} aria-hidden="true" />
      <section className={open ? "thmap-sheet thmap-open" : "thmap-sheet"} ref={sheetRef} aria-label="정책 모아보기">
        <button
          className="thmap-grab"
          type="button"
          ref={grabRef}
          aria-expanded={open}
          aria-controls={open ? "thmap-sheet-body" : undefined}
          onClick={() => {
            if (suppressGrabClickRef.current) {
              suppressGrabClickRef.current = false;
              return;
            }
            setOpen((value) => !value);
          }}
        >
          <i aria-hidden="true" />
          <span>{grabLabel}</span>
        </button>
        {open && (
          <>
            <div className="thmap-sheet-head">
        <h2>정책 모아보기</h2>
        <div className="thmap-seg" role="group" aria-label="묶는 기준">
        <button type="button" aria-pressed={groupBy === "region"} onClick={() => switchGroup("region")}>지역별</button>
        <button type="button" aria-pressed={groupBy === "program"} onClick={() => switchGroup("program")}>정책별</button>
        </div>
        </div>
        <div className="thmap-sheet-body" id="thmap-sheet-body" ref={bodyRef}>
        {detail ? (
        <div className="thmap-detail">
          <div className="thmap-det-top">
            <button className="thmap-det-back" type="button" aria-label="카테고리로" onClick={closeTile}>‹</button>
            <span className="thmap-det-ttl">
              <strong>{detail.label}</strong>
              <em>정책 {detail.items.length}건 · {detail.subLabel}</em>
            </span>
          </div>
          {detail.items.length === 0 && (
            <p className="thmap-det-empty">{detail.label}에는 아직 등록된 정책이 없어요</p>
          )}
          {detail.items.map((policy) => (
            <PolicyListCard key={policy.id} policy={policy} isSaved={savedSlugs.has(policy.slug)} onToggleSave={onToggleSave} />
          ))}
          {attributions.map((attribution) => (
            <p className="policy-list-photo-credit" key={attribution}>{attribution}</p>
          ))}
        </div>
        ) : (
        <div className="thmap-tiles">
          {rows.map((row, index) => {
            /* 홀수 개면 마지막 하나를 가로로 눕혀 빈칸을 남기지 않는다 */
            const wide = rows.length % 2 === 1 && index === rows.length - 1;
            const visual = groupBy === "program" ? getPolicyVisual(row.items[0]) : null;
            /* 지역 카드는 그 지역 관광명소를 배경으로 깐다. 아이콘 자리에 지역 이름 두 글자를
               넣던 것도 같이 뺀다 - 바로 밑 <strong> 과 같은 글자라 이름이 두 번 보였다. */
            const photo = visual ? null : REGION_PHOTOS[row.label];
            return (
              <button
                className={
                  (wide ? "thmap-tile thmap-wide" : "thmap-tile") + (photo ? " thmap-photo" : "")
                }
                key={row.key}
                type="button"
                style={photo ? { backgroundImage: `url(${photo})` } : undefined}
                onClick={() => openTile(row.key)}
              >
                {visual && <span className="thmap-ic" style={{ background: visual.from }} aria-hidden="true">{visual.emoji}</span>}
                <strong>{row.label}</strong>
                <span className="thmap-foot"><b>{row.items.length}</b><span>건 · {row.subLabel}</span></span>
              </button>
            );
          })}
        </div>
        )}
        </div>
          </>
        )}
      </section>
      {/* 떠 있는 뒤로가기. 시트 안에 두면 시트의 transform 때문에 fixed 가 화면이 아니라 시트에
          붙으므로 밖에 둔다. 휴대폰 뒤로가기처럼 한 단계씩 - 상세면 목록으로, 목록이면 닫는다. */}
      {open && (
        <button className="thmap-fab" type="button" aria-label="뒤로 가기" onClick={() => (detail ? closeTile() : setOpen(false))}>
          <ChevronLeft size={26} strokeWidth={2.5} aria-hidden="true" />
        </button>
      )}
    </>
  );
}
