import { ChevronDown, ChevronLeft, ChevronUp } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";
import type { Policy } from "../../api";
import { BENEFIT_TYPES, BenefitTile, benefitTypeOf } from "../benefitTile";
import { cityOf, NATIONWIDE_REGION } from "../../utils/policyPrograms";
import { deadlineChip, programName, type BrowseEntry, type BrowseView, type SheetStop } from "./policyBrowse";
import { policyListText, PROGRAM_GROUP_COPY } from "./policyListText";

/* 지도 위 목록 시트. 자리는 셋 - 지도 중심(머리 한 줄) · 반반(지역을 고르면 2/3) · 한 페이지.
   반반·지역 선택에서는 시트가 제자리에 서고 목록만 안에서 스크롤한다 - 스크롤로 시트가 올라가지 않는다.
   한 페이지로는 머리를 끌거나, 제목 줄 ∧ 를 누르거나, 모든 지역에서 묶음을 열 때만 간다.
   한 번 올라간 한 페이지는 안의 묶음을 여닫아도 내려가지 않는다. */
const LOW = 92;
const STOPS: readonly SheetStop[] = ["low", "mid", "full"];
/* 놓는 순간 이보다 빠르면(px/ms) 거리와 상관없이 움직이던 쪽 다음 자리로 */
const FLICK = 0.4;
/* 멈춰 놓으면 가까운 자리로 - 움직이던 쪽에 이만큼(px) 가산점을 줘 살짝 밀어도 넘어가게 */
const BIAS = 60;
/* 휠은 손을 떼는 순간이 없다 - 이만큼 조용하면 한 동작이 끝난 것으로 본다(ms) */
const WHEEL_QUIET = 160;
/* 짧은 스크롤 막대 길이(px) - 5mm */
const BAR = 19;

export function sheetHeight(stop: SheetStop, picked: boolean, area: number) {
  if (stop === "low") return Math.min(LOW, area);
  if (stop === "full") return area;
  return Math.round(area * (picked ? 2 / 3 : 1 / 2));
}

export function PolicyMapSheet({
  enabled,
  mode = "sheet",
  view,
  stop,
  region,
  scopeKey,
  showBack,
  clearLabel,
  onStop,
  onBack,
  onClear,
  onNation,
  onRest,
  onOpen,
}: {
  /** panel = 넓은 화면의 오른쪽 목록 패널. 끌기·높이 자리 없이 제자리에 선다 */
  mode?: "sheet" | "panel";
  /** 있으면 줄을 누를 때 상세 페이지 대신 이것을 부른다(새 탭 열기 등은 그대로 상세 주소로) */
  onOpen?: (policy: Policy) => void;
  /** 지도 화면일 때만 보인다. 필터·검색 목록 위에 겹치면 안 된다. */
  enabled: boolean;
  view: BrowseView;
  stop: SheetStop;
  /** 고른 지역(전국 포함). 있으면 반반이 2/3 으로 커지고 묶음이 펼친 채로 시작한다. */
  region: string | null;
  /** 이 값이 바뀌면 다른 화면이다 - 스크롤 자리를 따로 기억하고, 지역에서 닫은 묶음을 되돌린다. */
  scopeKey: string;
  showBack: boolean;
  clearLabel: string | null;
  onStop: (stop: SheetStop) => void;
  onBack: () => void;
  onClear: () => void;
  onNation: () => void;
  /** 시트가 자리에 섰을 때 그 윗변(화면 y). 지도가 이 위쪽에 그림을 맞춘다. */
  onRest?: (coverTop: number) => void;
}) {
  const picked = region !== null;
  const panel = mode === "panel";
  const sheetRef = useRef<HTMLElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);
  const [area, setArea] = useState(0);
  const topRef = useRef(0);
  const heightRef = useRef(0);
  const dirRef = useRef(0);
  const swallowRef = useRef(false);
  /* 이벤트 처리기는 한 번 걸어 두고 최신 값은 여기서 읽는다 */
  const live = useRef({ stop, picked, area, onStop, onRest });
  live.current = { stop, picked, area, onStop, onRest };

  const apply = (height: number, animate: boolean) => {
    const sheet = sheetRef.current;
    heightRef.current = height;
    if (!sheet) return;
    sheet.classList.toggle("thmap-anim", animate);
    sheet.style.height = `${height}px`;
  };
  const rest = (height: number) => live.current.onRest?.(topRef.current + live.current.area - height);

  /* 멈추면 가까운 자리로. 튕기기면 움직이던 쪽의 다음 자리로 */
  const settle = (flick: boolean) => {
    const { picked: isPicked, area: full, stop: current } = live.current;
    const h = heightRef.current, dir = dirRef.current;
    const snaps = STOPS.map((s) => [s, sheetHeight(s, isPicked, full)] as const);
    let next: SheetStop | undefined;
    if (flick) {
      next = dir > 0 ? snaps.find(([, px]) => px > h + 1)?.[0] : [...snaps].reverse().find(([, px]) => px < h - 1)?.[0];
    }
    if (!next) {
      const score = (px: number) => Math.abs(px - h) - (Math.sign(px - h) === dir ? BIAS : 0);
      next = snaps.reduce((best, cand) => (score(cand[1]) < score(best[1]) ? cand : best))[0];
    }
    const px = sheetHeight(next, isPicked, full);
    apply(px, true);
    if (next !== current) live.current.onStop(next);
    else rest(px);
  };

  /* 지도 화면: 뒤 칸은 굴리지 않는다(검색줄이 밀려 올라가는 길을 막는다). 시트 윗선 = 검색줄·칩 아래 */
  useEffect(() => {
    if (!enabled) return;
    const scroller = document.querySelector(".app-container");
    document.body.classList.add("thmap-map-view");
    if (scroller) scroller.scrollTop = 0;
    const measure = () => {
      const toolbar = document.querySelector(".prototype-policy-toolbar");
      const top = toolbar ? Math.max(0, Math.round(toolbar.getBoundingClientRect().bottom)) : 0;
      topRef.current = top;
      if (top > 0) document.body.style.setProperty("--thmap-sheet-top", `${top}px`);
      const probe = sheetRef.current ?? document.body;
      const tabbar = Number.parseFloat(getComputedStyle(probe).getPropertyValue("--thmap-tabbar")) || 0;
      setArea(Math.max(LOW + 60, Math.round(window.innerHeight - top - tabbar)));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      document.body.classList.remove("thmap-map-view");
      document.body.style.removeProperty("--thmap-sheet-top");
    };
  }, [enabled]);

  /* 자리가 바뀌면(주소가 바뀌면) 그 높이로 */
  useLayoutEffect(() => {
    if (!enabled || !area || panel) return;
    const px = sheetHeight(stop, picked, area);
    apply(px, heightRef.current > 0);
    rest(px);
    updateScroll();
  }, [enabled, stop, picked, area, panel]);

  /* 끌기 - 머리·손잡이는 늘, 목록은 지도 중심(목록이 숨어 있다)과 한 페이지 맨 위에서만 */
  useEffect(() => {
    const sheet = sheetRef.current;
    if (!enabled || !sheet || panel) return;
    let drag: { id: number; y: number; from: number; last: number; t: number; v: number; moved: boolean } | null = null;
    const down = (event: PointerEvent) => {
      if (event.button !== 0) return;
      const list = listRef.current;
      const inList = Boolean(list && list.contains(event.target as Node));
      const { stop: current } = live.current;
      if (inList && current === "mid") return;
      if (inList && current === "full" && list && list.scrollTop > 0) return;
      drag = { id: event.pointerId, y: event.clientY, from: heightRef.current, last: event.clientY, t: event.timeStamp, v: 0, moved: false };
    };
    const move = (event: PointerEvent) => {
      if (!drag || event.pointerId !== drag.id) return;
      const dy = event.clientY - drag.y;
      if (!drag.moved) {
        if (Math.abs(dy) < 6) return;
        /* 다 올라온 뒤 위로 긋기는 내용 스크롤이다 */
        if (heightRef.current >= live.current.area && dy < 0) { drag = null; return; }
        drag.moved = true;
        try { sheet.setPointerCapture(drag.id); } catch { /* 지원 안 하는 브라우저 */ }
      }
      if (event.clientY !== drag.last) {
        dirRef.current = event.clientY < drag.last ? 1 : -1;
        drag.v = (drag.last - event.clientY) / Math.max(1, event.timeStamp - drag.t);
      }
      drag.last = event.clientY;
      drag.t = event.timeStamp;
      const { picked: isPicked, area: full } = live.current;
      apply(Math.min(full, Math.max(sheetHeight("low", isPicked, full), drag.from - dy)), false);
    };
    const end = (event: PointerEvent) => {
      if (!drag || event.pointerId !== drag.id) return;
      const { moved, v, t } = drag;
      drag = null;
      if (!moved) return;
      /* 끌기 뒤에 따라오는 click 이 버튼을 누르지 않게 한 번 막는다 */
      swallowRef.current = true;
      window.setTimeout(() => { swallowRef.current = false; }, 0);
      /* 멈췄다가 뗀 건 튕기기가 아니다 */
      settle(Math.abs(v) > FLICK && event.timeStamp - t < 80);
    };
    const swallow = (event: MouseEvent) => {
      if (!swallowRef.current) return;
      swallowRef.current = false;
      event.stopPropagation();
      event.preventDefault();
    };
    let timer = 0;
    const wheel = (event: WheelEvent) => {
      const list = listRef.current;
      const { stop: current, picked: isPicked, area: full } = live.current;
      if (current === "mid" && list && list.contains(event.target as Node)) return;
      const growing = event.deltaY > 0, atTop = !list || list.scrollTop <= 0;
      const low = sheetHeight("low", isPicked, full), h = heightRef.current;
      if (!(growing && h < full) && !(!growing && h > low && atTop)) return;
      event.preventDefault();
      window.clearTimeout(timer);
      dirRef.current = growing ? 1 : -1;
      apply(Math.min(full, Math.max(low, h + event.deltaY)), false);
      if (heightRef.current <= low || heightRef.current >= full) settle(false);
      else timer = window.setTimeout(() => settle(false), WHEEL_QUIET);
    };
    sheet.addEventListener("pointerdown", down);
    sheet.addEventListener("pointermove", move);
    sheet.addEventListener("pointerup", end);
    sheet.addEventListener("pointercancel", end);
    sheet.addEventListener("click", swallow, true);
    sheet.addEventListener("wheel", wheel, { passive: false });
    return () => {
      window.clearTimeout(timer);
      sheet.removeEventListener("pointerdown", down);
      sheet.removeEventListener("pointermove", move);
      sheet.removeEventListener("pointerup", end);
      sheet.removeEventListener("pointercancel", end);
      sheet.removeEventListener("click", swallow, true);
      sheet.removeEventListener("wheel", wheel);
    };
  }, [enabled, panel]);

  /* ── 묶음 여닫기 ─────────────────────────────────────────────
     모든 지역은 접힌 채로, 지역을 고르면 펼친 채로 시작한다. 다시 누르면 닫히고 열기 전 스크롤 자리로. */
  const [opened, setOpened] = useState<ReadonlySet<string>>(new Set());
  const [shut, setShut] = useState<ReadonlySet<string>>(new Set());
  const origins = useRef(new Map<string, { top: number; scope: string }>());
  const restoreRef = useRef<number | null>(null);
  const isOpen = (key: string) => (picked ? !shut.has(key) : opened.has(key));
  const flip = (set: ReadonlySet<string>, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  };
  const toggleGroup = (key: string, head: Element | null) => {
    const list = listRef.current;
    const opening = !isOpen(key);
    if (opening) origins.current.set(key, { top: list?.scrollTop ?? 0, scope: scopeKey });
    if (picked) setShut((set) => flip(set, key));
    else setOpened((set) => flip(set, key));
    if (opening && !picked && stop !== "full" && !panel) onStop("full");
    if (!opening && list) {
      const origin = origins.current.get(key);
      origins.current.delete(key);
      if (origin && origin.scope === scopeKey) restoreRef.current = origin.top;
      /* 처음부터 펼쳐져 있던 묶음(지역 화면)은 그 머리가 목록 맨 위에 오게 */
      else if (head) restoreRef.current = list.scrollTop + head.getBoundingClientRect().top - list.getBoundingClientRect().top;
    }
  };

  /* ── 화면마다 스크롤 자리 ─────────────────────────────────── */
  const scrolls = useRef(new Map<string, number>());
  const scopeRef = useRef(scopeKey);
  const lastTopRef = useRef(0);
  useLayoutEffect(() => {
    if (scopeRef.current === scopeKey) return;
    scrolls.current.set(scopeRef.current, lastTopRef.current);
    scopeRef.current = scopeKey;
    setShut(new Set());
    const list = listRef.current;
    if (list) list.scrollTop = scrolls.current.get(scopeKey) ?? 0;
  }, [scopeKey]);
  useLayoutEffect(() => {
    const list = listRef.current;
    if (restoreRef.current !== null && list) {
      list.scrollTop = restoreRef.current;
      restoreRef.current = null;
    }
    updateScroll();
  });

  /* 펼친 묶음의 머리가 목록 위로 넘어갔고 묶음이 아직 보이면 한 줄 고정 줄을 켠다. 짧은 막대도 여기서 */
  function updateScroll() {
    const list = listRef.current;
    if (!list) return;
    lastTopRef.current = list.scrollTop;
    const top = list.getBoundingClientRect().top;
    list.querySelectorAll<HTMLElement>(".thmap-grp.open").forEach((item) => {
      const head = item.querySelector(".thmap-grp-btn")?.getBoundingClientRect();
      const box = item.getBoundingClientRect();
      item.classList.toggle("pinned", Boolean(head && head.bottom <= top + 2 && box.bottom > top + 56));
    });
    const bar = barRef.current;
    if (!bar) return;
    const max = list.scrollHeight - list.clientHeight;
    const on = max > 1 && (panel || live.current.stop !== "low");
    bar.classList.toggle("on", on);
    if (on) bar.style.top = `${list.offsetTop + 4 + (list.clientHeight - 8 - BAR) * (list.scrollTop / max)}px`;
  }

  if (!enabled) return null;

  const toggle = () => onStop(stop === "mid" ? "full" : "mid");
  /* 패널은 늘 펼친 목록이다 - 시트 자리(낮게·한 페이지)가 없다 */
  const at = panel ? "panel" : stop;
  return (
    <section
      className={`thmap-sheet thmap-at-${at}`}
      ref={sheetRef}
      aria-label="정책 목록"
    >
      {!panel && (
        <button className="thmap-handle" type="button" aria-label="목록 펼치기 또는 접기" onClick={toggle}>
          <i aria-hidden="true" />
        </button>
      )}
      {/* 지도 중심에서는 머리 전체가 올리는 손잡이다. 키보드는 오른쪽 ∧ 버튼을 쓴다 */}
      <div className="thmap-head" onClick={at === "low" ? toggle : undefined}>
        <div className="thmap-head-main">
          {showBack && (
            <button className="thmap-hback" type="button" aria-label="뒤로" onClick={(event) => { event.stopPropagation(); onBack(); }}>
              <ChevronLeft size={22} aria-hidden="true" />
            </button>
          )}
          <div className="thmap-head-copy">
            <h2 className="thmap-title">{view.title} <span className="n">{view.count}건</span></h2>
            <p className="thmap-hsub">{at === "low" ? "누르거나 끌어 올리면 목록이 나와요" : view.sub}</p>
          </div>
        </div>
        <div className="thmap-head-actions">
          {clearLabel && (
            <button className="thmap-clear" type="button" onClick={(event) => { event.stopPropagation(); onClear(); }}>
              {clearLabel}
            </button>
          )}
          {!panel && (
            <button
              className="thmap-toggle"
              type="button"
              aria-expanded={stop === "full"}
              aria-label={stop === "full" ? "목록 접기" : "목록 펼치기"}
              onClick={(event) => { event.stopPropagation(); toggle(); }}
            >
              <ChevronUp size={22} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
      <ul className="thmap-list" ref={listRef} onScroll={updateScroll}>
        {view.empty && <li className="thmap-empty">{view.empty}</li>}
        {view.entries.map((entry) => (
          <EntryItem entry={entry} key={entry.kind === "row" ? entry.policy.id : entry.key} open={entry.kind !== "row" && isOpen(entry.key)} region={region} onToggle={toggleGroup} onOpen={onOpen} />
        ))}
        {view.nationMore > 0 && (
          <li>
            <button className="thmap-more" type="button" onClick={onNation}>
              전국 공통 혜택 {view.nationMore}건도 여기서 쓸 수 있어요
            </button>
          </li>
        )}
      </ul>
      <div className="thmap-sbar" ref={barRef} aria-hidden="true" />
    </section>
  );
}

/* 줄 누르기: onOpen 이 있으면(넓은 화면 패널) 그 자리에서 열고, 새 탭·가운데 누르기는 상세 주소 그대로 */
function openHandler(policy: Policy, onOpen?: (policy: Policy) => void) {
  if (!onOpen) return undefined;
  return (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onOpen(policy);
  };
}

function EntryItem({
  entry,
  open,
  region,
  onToggle,
  onOpen,
}: {
  entry: BrowseEntry;
  open: boolean;
  region: string | null;
  onToggle: (key: string, head: Element | null) => void;
  onOpen?: (policy: Policy) => void;
}) {
  if (entry.kind === "row") return <Row policy={entry.policy} prev={null} region={region} onOpen={onOpen} />;
  const { key, items } = entry;
  const id = `thmap-g-${encodeURIComponent(key)}`;
  const nation = entry.kind === "nation";
  const first = items[0];
  const sameDeadline = items.every((policy) => policy.deadline === first.deadline);
  const chip = deadlineChip(first, !sameDeadline);
  const kind = nation ? "nation" : benefitTypeOf(first);
  const title = nation ? "전국 공통 혜택" : key;
  /* 머리와 같은 말은 되풀이하지 않는다(시안 v40) - 받는 것·지역 한 줄이 지역마다 다를 때만 지역 줄에 보인다.
     묶음 머리는 사업 공통 문구(PROGRAM_GROUP_COPY)가 있으면 그것, 없으면 첫 곳의 받는 것 */
  const texts = items.map(policyListText);
  const firstText = texts[0];
  const headVaries = texts.some((text) => text.head !== firstText.head);
  const detailVaries = texts.some((text) => text.detail !== firstText.detail);
  const copy = nation ? undefined : PROGRAM_GROUP_COPY[key];
  const partnerSum = texts.reduce((sum, text) => sum + text.partners, 0);
  const head = copy ? copy.head.replace("{sum}", partnerSum.toLocaleString("ko-KR")) : firstText.head;
  const desc = copy?.desc ?? (detailVaries ? "" : firstText.detail);
  /* 사업 공통 문구가 설명 자리를 차지해도, 모든 곳이 같은 지역 한 줄은 머리에 한 번 보인다(지역 줄마다 되풀이하지 않고) */
  const shared = copy && !detailVaries ? firstText.detail : "";
  const kidText = (index: number) =>
    [headVaries ? texts[index].head : "", detailVaries ? texts[index].detail : ""].filter(Boolean).join(" · ");
  const lead = nation
    ? <><b>{items.length}건</b> · {Array.from(new Set(items.map((p) => BENEFIT_TYPES[benefitTypeOf(p)].label))).slice(0, 4).join("·")} 등</>
    : <><b>{items.length}곳</b> · {items.slice(0, 3).map((p) => cityOf(p) ?? p.region).join(", ")}{items.length > 3 ? " 등" : ""}</>;
  const toggle = (event: ReactMouseEvent<HTMLElement>) => onToggle(key, event.currentTarget.closest(".thmap-grp")?.querySelector(".thmap-grp-btn") ?? null);
  return (
    <li className={open ? "thmap-grp open" : "thmap-grp"}>
      <button className="thmap-grp-btn" type="button" aria-expanded={open} aria-controls={id} onClick={toggle}>
        <BenefitTile kind={kind} decorative={false} />
        <span className="thmap-body">
          <span className="l1">{lead}</span>
          <span className="t">{title}</span>
          {nation ? <span className="amt">어느 지역을 가도 쓸 수 있어요</span> : head && <span className="amt">{head}</span>}
          {!nation && desc && <span className="desc">{desc}</span>}
          {!nation && shared && <span className="desc shared">공통 · {shared}</span>}
        </span>
        <span className="thmap-side">
          <span className={`thmap-dday ${chip.tone}`}>{chip.text}</span>
          <ChevronDown className="thmap-chev" size={20} aria-hidden="true" />
        </span>
      </button>
      {open && (
        /* 손가락용 고정 줄. 키보드는 머리 버튼을 쓰므로 낭독·탭 순서에서 뺀다 */
        <div className="thmap-grp-pin" aria-hidden="true">
          <button className="thmap-pin-bar" type="button" tabIndex={-1} onClick={toggle}>
            <BenefitTile kind={kind} size="sm" />
            <b>{title}</b>
            <span className="n">{items.length}{nation ? "건" : "곳"}</span>
            <span className="thmap-pin-fold">접기<ChevronUp size={18} aria-hidden="true" /></span>
          </button>
        </div>
      )}
      <ul className={nation ? "thmap-natlist" : "thmap-kids"} id={id} hidden={!open}>
        {nation
          ? items.map((policy, index) => <Row key={policy.id} policy={policy} prev={items[index - 1] ?? null} region={region} onOpen={onOpen} />)
          : items.map((policy, index) => <Kid key={policy.id} policy={policy} showRegion={!region} text={kidText(index)} onOpen={onOpen} />)}
      </ul>
    </li>
  );
}

/* 앞 줄과 같은 사업이면 이름·받는 것을 되풀이하지 않고 지역과 그곳만의 내용만 보인다 */
function Row({ policy, prev, region, onOpen }: { policy: Policy; prev: Policy | null; region: string | null; onOpen?: (policy: Policy) => void }) {
  const cont = Boolean(prev) && programName(prev as Policy) === programName(policy);
  const chip = deadlineChip(policy);
  const place = cityOf(policy);
  const where = !place
    ? <b>{policy.region === NATIONWIDE_REGION ? "전국 공통" : policy.region}</b>
    : region === policy.region ? <b>{place}</b> : <><b>{place}</b> · {policy.region}</>;
  const text = policyListText(policy);
  const prevText = cont ? policyListText(prev as Policy) : null;
  const amount = text.head && !(prevText && prevText.head === text.head) ? text.head : null;
  const desc = text.detail && !(prevText && prevText.detail === text.detail) ? text.detail : null;
  return (
    <li className={cont ? "thmap-row cont" : "thmap-row"}>
      <Link className="thmap-row-link" to={`/policies/${policy.slug}`} onClick={openHandler(policy, onOpen)}>
        {!cont && <BenefitTile kind={benefitTypeOf(policy)} decorative={false} />}
        <span className="thmap-body">
          <span className="l1">{where}</span>
          {!cont && <span className="t">{programName(policy)}</span>}
          {amount && <span className="amt">{amount}</span>}
          {desc && <span className="desc">{desc}</span>}
        </span>
        <span className="thmap-side">
          <span className={`thmap-dday ${chip.tone}`}>{chip.text}</span>
        </span>
      </Link>
    </li>
  );
}

function Kid({ policy, showRegion, text, onOpen }: { policy: Policy; showRegion: boolean; text: string; onOpen?: (policy: Policy) => void }) {
  const chip = deadlineChip(policy);
  return (
    <li className="thmap-kid">
      <Link className="thmap-kid-link" to={`/policies/${policy.slug}`} onClick={openHandler(policy, onOpen)}>
        <span className="kn">
          <b>{cityOf(policy) ?? policy.region}</b>
          {showRegion && <span className="reg">{policy.region}</span>}
        </span>
        <span className={`thmap-dday ${chip.tone}`}>{chip.text}</span>
        {text && <span className="kd">{text}</span>}
      </Link>
    </li>
  );
}
