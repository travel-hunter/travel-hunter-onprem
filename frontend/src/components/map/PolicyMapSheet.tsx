import { useEffect, useMemo, useRef, useState } from "react";
import type { Policy } from "../../api";
import { PolicyListCard } from "../cards";
import { getPolicyPhoto, getPolicyVisual } from "../../data/displayConfig";
import { ChevronLeft } from "lucide-react";
import { groupByProgram, groupByRegion, type PolicyGroup } from "../../utils/policyPrograms";
import { REGION_NAMES } from "./regionMapEngine";
import { REGION_PHOTOS } from "./regionPhotos";

const PEEK = 20; /* 닫힌 시트가 내미는 높이 - 손잡이 줄까지만 */
/* 휠 한 칸(보통 deltaY 100)에 시트가 내려가는 거리. 1 이면 한두 번에 닫혀 손이 미끄러진다. */
const WHEEL_DAMP = 0.8;
/* 휠은 손을 떼는 순간이 없다 - 이만큼 조용하면 한 동작이 끝난 것으로 본다(ms). */
const WHEEL_SETTLE = 140;
/* 시트를 제자리로 미는 transform. CSS 의 translateX(-50%) 를 빼먹으면 시트가 가로로 튄다. */
const shift = (y: number) => `translateX(-50%) translateY(${y}px)`;

/* 지도 아래에서 올라오는 정책 시트. 92건을 한 줄로 늘어놓지 않고 지역 줄 또는
   정책 종류 줄로 접어 보여준다. 여는 방법 셋 - 손잡이 누르기, 아래로 휠, 손잡이 끌기.
   앱 탭바(72px) 바로 위에서 멈춘다 - 다 올려도 메뉴탭은 그대로 보인다. */
export function PolicyMapSheet({
  policies,
  enabled,
  savedSlugs,
  onToggleSave,
}: {
  policies: Policy[];
  /** 지도 화면일 때만 보인다. 목록 화면 위에 겹치면 안 된다. */
  enabled: boolean;
  savedSlugs: Set<string>;
  onToggleSave: (policy: Policy) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [groupBy, setGroupBy] = useState<"region" | "program">("region");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const sheetRef = useRef<HTMLElement | null>(null);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const grabRef = useRef<HTMLButtonElement | null>(null);
  const suppressGrabClickRef = useRef(false);

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

  /* 휠 - 지도 화면 어디서든 아래로 굴리면 열린다. 여는 건 가볍게 한 번이면 된다.
     닫을 때는 굴린 만큼 시트가 실제로 밀려 내려가고, 제 키의 절반을 넘겨야 닫힌다.
     절반 위에서 손을 멈추면 도로 올라가 열린 채로 남는다 - 한 칸에 닫혀 버리던 것을 고쳤다.
     지도 화면엔 지도 밑 목록이 없으므로(PolicyPages 의 showMap) 삼킬 스크롤도 없다. */
  useEffect(() => {
    if (!enabled) return;
    let pull = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    /* 한 동작이 끝난 자리에서 판정한다 - 절반을 넘겼으면 닫고 아니면 되돌린다. */
    const settle = () => {
      const sheet = sheetRef.current;
      const passedHalf = sheet ? pull > sheet.clientHeight / 2 : pull > 0;
      if (sheet) { sheet.classList.remove("thmap-drag"); sheet.style.transform = ""; }
      pull = 0;
      if (passedHalf) setOpen(false);
    };
    const onWheel = (event: WheelEvent) => {
      const body = bodyRef.current, sheet = sheetRef.current;
      if (open) {
        /* 시트 안을 아직 다 못 올렸으면 내용 스크롤이 먼저다 */
        if (body && body.contains(event.target as Node) && body.scrollTop > 0) return;
        /* 맨 위에서 아래로 굴리는 건 내용 스크롤 - 끌어내리던 중일 때만 되돌리는 데 쓴다 */
        if (event.deltaY >= 0 && pull === 0) return;
        if (!sheet) return;
        pull = Math.max(0, Math.min(sheet.clientHeight - PEEK, pull - event.deltaY * WHEEL_DAMP));
        sheet.classList.add("thmap-drag");
        sheet.style.transform = shift(pull);
        event.preventDefault();
        clearTimeout(timer);
        /* 절반을 넘긴 순간 바로 닫는다 - 넘기고도 기다리게 하면 굼떠 보인다 */
        if (pull > sheet.clientHeight / 2) { settle(); return; }
        timer = setTimeout(settle, WHEEL_SETTLE);
        return;
      }
      if (event.deltaY > 0) { setOpen(true); event.preventDefault(); }
    };
    document.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      document.removeEventListener("wheel", onWheel);
      clearTimeout(timer);
    };
  }, [enabled, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  /* 손잡이 끌기 - 손가락을 그대로 따라간다. 6px 안이면 클릭으로 본다.
     열 때는 조금만 올려도 열리고, 닫을 때는 제 키의 절반을 넘겨야 닫힌다.
     절반 위에서 놓으면 도로 올라가 열린 채로 남는다. */
  useEffect(() => {
    const grab = grabRef.current, sheet = sheetRef.current;
    if (!grab || !sheet) return;
    let startY: number | null = null, moved = false, pull = 0;
    const down = (event: PointerEvent) => {
      startY = event.clientY; moved = false; pull = 0; sheet.classList.add("thmap-drag");
      try { grab.setPointerCapture(event.pointerId); } catch { /* 지원 안 하는 브라우저 */ }
    };
    const move = (event: PointerEvent) => {
      if (startY === null) return;
      const dy = event.clientY - startY;
      if (Math.abs(dy) > 6) moved = true;
      if (!moved) return;
      const base = open ? 0 : sheet.clientHeight - PEEK;
      pull = Math.max(0, Math.min(sheet.clientHeight - PEEK, base + dy));
      sheet.style.transform = shift(pull);
    };
    const end = (event: PointerEvent) => {
      if (startY === null) return;
      const dy = event.clientY - startY; startY = null;
      sheet.classList.remove("thmap-drag"); sheet.style.transform = "";
      if (!moved) return; /* 그냥 클릭이면 click 이 처리 */
      /* pointerup 뒤에 합성되는 click 이 드래그 결과를 다시 뒤집지 못하게 한 번만 막는다. */
      suppressGrabClickRef.current = event.type === "pointerup";
      if (suppressGrabClickRef.current) {
        window.setTimeout(() => {
          suppressGrabClickRef.current = false;
        }, 0);
      }
      /* 열려 있었으면 절반을 넘겨 내려왔을 때만 닫는다. 아니면 그대로 열린 채 되돌아간다. */
      if (open) setOpen(!(pull > sheet.clientHeight / 2));
      else setOpen(dy < 0);
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
      <div className={open ? "thmap-dim thmap-dim-on" : "thmap-dim"} onClick={() => setOpen(false)} aria-hidden="true" />
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
