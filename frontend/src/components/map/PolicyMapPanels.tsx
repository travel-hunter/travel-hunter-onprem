import { ChevronLeft, MapPin, Search } from "lucide-react";
import { useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";
import type { PlaceSearchItem, Policy } from "../../api";
import { BenefitTile } from "../benefitTile";
import { NATIONWIDE_REGION } from "../../utils/policyPrograms";
import { geoToMap, nearTarget, type NearTarget } from "./nearby";
import { REGION_PHOTOS } from "./regionPhotos";
import {
  BROWSE_FILTERS,
  filterLabel,
  REGION_FULL_NAMES,
  regionSummary,
  regionTiles,
  searchBrowse,
  type BrowseFilter,
  type BrowseSearch,
} from "./policyBrowse";

const FAMILY: Record<BrowseFilter, string> = { stay: "stay", refund: "money", partner: "money", move: "move" };

/* 가로로 넘기는 줄. 휴대폰은 손가락으로 밀면 되지만 마우스는 휠·끌기가 있어야 한다.
   더 있는 쪽 끝은 흐리게 - 옆에 더 있다는 표시다. */
export function useSideScroll(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const row = ref.current;
    if (!row) return;
    const edge = () => {
      const over = row.scrollWidth > row.clientWidth + 2;
      row.classList.toggle("more-r", over && row.scrollLeft + row.clientWidth < row.scrollWidth - 2);
      row.classList.toggle("more-l", over && row.scrollLeft > 2);
    };
    const wheel = (event: WheelEvent) => {
      if (row.scrollWidth <= row.clientWidth || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      event.preventDefault();
      row.scrollLeft += event.deltaY;
    };
    let drag: { id: number; x: number; left: number; moved: boolean } | null = null;
    let swallow = false;
    const down = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || event.button !== 0 || row.scrollWidth <= row.clientWidth) return;
      drag = { id: event.pointerId, x: event.clientX, left: row.scrollLeft, moved: false };
    };
    const move = (event: PointerEvent) => {
      if (!drag || event.pointerId !== drag.id) return;
      const dx = event.clientX - drag.x;
      if (!drag.moved && Math.abs(dx) < 5) return;
      if (!drag.moved) {
        drag.moved = true;
        row.classList.add("dragging");
        try { row.setPointerCapture(drag.id); } catch { /* 없음 */ }
      }
      row.scrollLeft = drag.left - dx;
    };
    const end = () => {
      if (drag?.moved) swallow = true;
      drag = null;
      row.classList.remove("dragging");
    };
    /* 끌고 놓을 때 칩이 눌리지 않게 */
    const click = (event: MouseEvent) => {
      if (!swallow) return;
      swallow = false;
      event.stopPropagation();
      event.preventDefault();
    };
    edge();
    row.addEventListener("scroll", edge, { passive: true });
    row.addEventListener("wheel", wheel, { passive: false });
    row.addEventListener("pointerdown", down);
    row.addEventListener("pointermove", move);
    row.addEventListener("pointerup", end);
    row.addEventListener("pointercancel", end);
    row.addEventListener("click", click, true);
    window.addEventListener("resize", edge);
    return () => {
      row.removeEventListener("scroll", edge);
      row.removeEventListener("wheel", wheel);
      row.removeEventListener("pointerdown", down);
      row.removeEventListener("pointermove", move);
      row.removeEventListener("pointerup", end);
      row.removeEventListener("pointercancel", end);
      row.removeEventListener("click", click, true);
      window.removeEventListener("resize", edge);
    };
  });
}

/* 위 칩: 혜택 형태. 건수는 고른 지역·사업 안에서 센다. 검색에서 고른 사업은 맨 앞 칩으로 */
export function BrowseChips({
  counts,
  filter,
  program,
  onFilter,
  onClearProgram,
}: {
  counts: Map<BrowseFilter | null, number>;
  filter: BrowseFilter | null;
  program: string | null;
  onFilter: (key: BrowseFilter | null) => void;
  onClearProgram: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useSideScroll(ref);
  return (
    <div className="thmap-chips" ref={ref} role="group" aria-label="혜택 형태">
      {program && (
        <button className="thmap-chip" type="button" aria-pressed="true" aria-label={`검색 ${program} 지우기`} onClick={onClearProgram}>
          <Search size={17} aria-hidden="true" />
          {program.length > 9 ? `${program.slice(0, 9)}…` : program} ×
        </button>
      )}
      {BROWSE_FILTERS.map((f) => (
        <button
          className="thmap-chip"
          key={f.label}
          type="button"
          aria-pressed={filter === f.key}
          onClick={() => onFilter(f.key)}
        >
          {f.icon && <BenefitTile kind={f.icon} />}
          {f.label}
          <span className="n">{counts.get(f.key) ?? 0}</span>
        </button>
      ))}
    </div>
  );
}

/* 고른 지역이 어떤 곳인지: 무슨 혜택 위주인지, 몇 곳에 있는지, 가장 빠른 마감.
   뒷배경은 그 지역 사진을 눌러 어둡게 - 흰 글자가 사진 어디서나 읽힌다. */
export function RegionSummaryCard({
  policies,
  region,
  filter,
  nationCount,
  onFilter,
  onNation,
}: {
  policies: Policy[];
  region: string;
  filter: BrowseFilter | null;
  nationCount: number;
  onFilter: (key: BrowseFilter | null) => void;
  onNation: () => void;
}) {
  const summary = regionSummary(policies, region);
  const photo = REGION_PHOTOS[region];
  return (
    <div className={photo ? "thmap-rcard photo" : "thmap-rcard"} role="region" aria-label={`${region} 요약`}>
      {photo && <span className="thmap-rc-bg" style={{ backgroundImage: `url(${photo})` }} aria-hidden="true" />}
      {summary.count === 0 ? (
        <>
          <h3>{summary.fullName}</h3>
          <p>아직 이 지역 전용 혜택이 없어요.</p>
          <button className="thmap-rc-btn" type="button" onClick={onNation}>전국 공통 혜택 {nationCount}건 보기</button>
        </>
      ) : (
        <>
          <h3>{summary.fullName}<span>{summary.count}건</span></h3>
          <p>
            {summary.lead && <b>{filterLabel(summary.lead)}</b>} 위주{summary.cities ? ` · ${summary.cities}개 시군` : ""}
          </p>
          <div className="thmap-rbar" aria-hidden="true">
            {summary.kinds.map((kind) => (
              <i className={`family-${FAMILY[kind.key]}`} key={kind.key} style={{ flex: kind.count }} />
            ))}
          </div>
          <div className="thmap-rtypes" role="group" aria-label="이 지역 혜택 종류로 거르기">
            {summary.kinds.map((kind) => (
              <button
                className={`family-${FAMILY[kind.key]}`}
                key={kind.key}
                type="button"
                aria-pressed={filter === kind.key}
                onClick={() => onFilter(filter === kind.key ? null : kind.key)}
              >
                {filterLabel(kind.key)} {kind.count}
              </button>
            ))}
          </div>
          <p>가장 빠른 마감 · <b>{summary.soonest ?? "마감 있는 혜택 없음"}</b></p>
        </>
      )}
    </div>
  );
}

function Marked({ text, query }: { text: string; query: string }) {
  const parts = text.split(query);
  return (
    <>
      {parts.map((part, index) => (
        <span key={index}>
          {index > 0 && <mark>{query}</mark>}
          {part}
        </span>
      ))}
    </>
  );
}

/* 돋보기: 비워 두면 지역 사진 칸, 치면 시도·시군·사업. 엔터는 첫 결과 */
/* 검색 결과 칸. 입력은 정책 탭 맨 위 검색창 하나가 맡는다(2026-09-30 사용자 결정: 검색창을 하나로).
   비워 두면 지역 사진 칸, 치면 지역·시군·혜택 이름. 끝의 '모두 보기'는 정책 글 전체에서 찾는 목록으로 간다. */
/* 위치로 찾기 한 줄: 장소들을 시군으로 묶는다(같은 시군이면 한 줄). label = 근처 줄에 쓸 이름 */
type NearGroup = { key: string; item: PlaceSearchItem; label: string; title: string; target: NearTarget };

function nearGroups(policies: readonly Policy[], items: readonly PlaceSearchItem[], q: string): NearGroup[] {
  const by = new Map<string, PlaceSearchItem[]>();
  for (const item of items) {
    if (!item.sido || item.latitude == null || item.longitude == null) continue;
    const key = `${item.sido}|${item.city ?? ""}`;
    by.set(key, [...(by.get(key) ?? []), item]);
  }
  return Array.from(by, ([key, list]) => {
    const area = list.find((item) => item.kind === "area");
    const named = list.find((item) => item.kind === "place" && item.name.includes(q));
    const item = area ?? named ?? list[0];
    const city = item.city ?? "";
    // 동 이름처럼 장소가 아니면 '여수 중앙동', 장소 이름이 맞으면 그 이름들
    const label = area ? area.name : named ? named.name : q.includes(city) || !city ? q : `${city} ${q}`;
    const places = list.filter((entry) => entry.kind === "place").map((entry) => entry.name);
    const title = area || !named ? label : places.slice(0, 2).join(", ") + (places.length > 2 ? ` 외 ${places.length - 2}곳` : "");
    const target = nearTarget(policies, item.sido ?? null, item.city ?? null, geoToMap(item.sido as string, item.latitude as number, item.longitude as number));
    return { key, item, label, title, target };
  });
}

export function PolicySearchPanel({
  policies,
  region,
  query,
  fullTextCount,
  places = null,
  onShowAll,
  onPickRegion,
  onPickPlace,
  onPickProgram,
  onPickNear,
  onClose,
}: {
  policies: Policy[];
  region: string | null;
  query: string;
  fullTextCount: number;
  /** 장소 검색 결과(카카오). null = 아직 안 찾았거나 찾는 중 */
  places?: PlaceSearchItem[] | null;
  onShowAll: () => void;
  onPickRegion: (region: string) => void;
  onPickPlace: (region: string, place: string) => void;
  onPickProgram: (program: string) => void;
  /** 위치로 찾기 줄 - 그 장소의 근처 혜택으로 */
  onPickNear?: (item: PlaceSearchItem, label: string, target: NearTarget) => void;
  /** 머리의 ‹ - 검색을 나온다(들어오기 전 화면의 반반) */
  onClose?: () => void;
}) {
  const q = query.trim();
  const counts = policies.reduce<Record<string, number>>((acc, policy) => {
    acc[policy.region] = (acc[policy.region] ?? 0) + 1;
    return acc;
  }, {});
  const found = q ? searchBrowse(policies, q) : null;
  /* 위치로 찾기: 지역 · 시군 이름이 안 맞을 때만(맞으면 그 줄이 먼저다 - 시안 v56) */
  const near = found && !found.regions.length && !found.places.length && places && onPickNear ? nearGroups(policies, places, q) : [];
  const searching = Boolean(found && !found.regions.length && !found.places.length && q.length >= 2 && places === null);
  return (
    <div className="thmap-search" role="region" aria-label="지역·혜택 검색 결과" id="policy-search-panel">
      {onClose && (
        <div className="thmap-search-head">
          <button className="thmap-hback" type="button" aria-label="검색 닫기" onClick={onClose}>
            <ChevronLeft size={22} aria-hidden="true" />
          </button>
          <div>
            <h2 className="thmap-title">지역 · 혜택 찾기</h2>
            <p className="thmap-hsub">지역을 고르거나 아는 장소를 쳐 보세요</p>
          </div>
        </div>
      )}
      <div className="thmap-search-body">
        {!found && (
          <>
            <h3>지역 고르기</h3>
            <div className="thmap-rtiles">
              {[...regionTiles(policies), { region: NATIONWIDE_REGION, count: counts[NATIONWIDE_REGION] ?? 0 }].map(({ region: name, count }) => {
                const nation = name === NATIONWIDE_REGION;
                const photo = REGION_PHOTOS[name];
                return (
                  <button
                    className={`thmap-rt${nation ? " nat" : count ? "" : " zero"}`}
                    key={name}
                    type="button"
                    aria-pressed={region === name}
                    onClick={() => onPickRegion(name)}
                  >
                    {photo && <span className="thmap-rt-img" style={{ backgroundImage: `url(${photo})` }} aria-hidden="true" />}
                    <b>{nation ? "전국 공통" : REGION_FULL_NAMES[name]}</b>
                    <span className="n">{count ? `혜택 ${count}건` : "전용 혜택 없음"}</span>
                  </button>
                );
              })}
            </div>
          </>
        )}
        {found && (
          <PolicySearchRows
            found={found}
            query={q}
            fullTextCount={fullTextCount}
            onPickRegion={onPickRegion}
            onPickPlace={onPickPlace}
            onPickProgram={onPickProgram}
            onShowAll={onShowAll}
          >
            {near.length > 0 && (
              <>
                <h3>위치로 찾기<span className="src">근처 혜택으로</span></h3>
                {near.map((group) => (
                  <button className="thmap-sres-row" key={group.key} type="button" onClick={() => onPickNear?.(group.item, group.label, group.target)}>
                    <span className="thmap-near-ic" aria-hidden="true"><MapPin size={18} /></span>
                    <span className="tx">
                      <b>{group.title}</b>
                      <span>
                        <span className="thmap-near-to">→ {group.item.sido} {group.item.city}</span> · {group.target.region === NATIONWIDE_REGION ? "전국 공통 혜택" : group.target.note ? "근처 혜택" : "혜택"} {group.target.count}건
                      </span>
                    </span>
                  </button>
                ))}
              </>
            )}
            {searching && <p className="thmap-sres-empty">아는 장소로 찾는 중…</p>}
            {!found.regions.length && !found.places.length && !found.programs.length && !fullTextCount && !near.length && !searching && (
              <p className="thmap-sres-empty">‘{q}’에 맞는 지역 · 혜택 · 장소가 없어요.</p>
            )}
          </PolicySearchRows>
        )}
      </div>
    </div>
  );
}

/* 찾은 지역 · 시군 · 혜택 줄과 '…모두 보기' - 정책 탭 검색 칸과 홈 검색이 같이 쓴다(시안 v56). children 은 혜택 줄과 '모두 보기' 사이 */
export function PolicySearchRows({
  found,
  query,
  fullTextCount,
  onPickRegion,
  onPickPlace,
  onPickProgram,
  onShowAll,
  children,
}: {
  found: BrowseSearch;
  query: string;
  fullTextCount: number;
  onPickRegion: (region: string) => void;
  onPickPlace: (region: string, place: string) => void;
  onPickProgram: (program: string) => void;
  onShowAll: () => void;
  children?: ReactNode;
}) {
  const q = query.trim();
  const regionLine = (name: string, count: number) => `${REGION_FULL_NAMES[name]} · ${count ? `혜택 ${count}건` : "전용 혜택 없음"}`;
  return (
    <>
      {(found.regions.length > 0 || found.places.length > 0) && (
        <>
          <h3>지역</h3>
          {found.regions.map(({ region: name, count }) => (
            <button className="thmap-sres-row" key={name} type="button" onClick={() => onPickRegion(name)}>
              <span className="tx"><b><Marked text={name} query={q} /></b><span>{regionLine(name, count)}</span></span>
            </button>
          ))}
          {found.places.map(({ place, region: name, count }) => (
            <button className="thmap-sres-row" key={`${place}|${name}`} type="button" onClick={() => onPickPlace(name, place)}>
              <span className="tx"><b><Marked text={place} query={q} /></b><span>{name} · 혜택 {count}건</span></span>
            </button>
          ))}
        </>
      )}
      {found.programs.length > 0 && (
        <>
          <h3>혜택</h3>
          {found.programs.map((program) => (
            <button className="thmap-sres-row" key={program.name} type="button" onClick={() => onPickProgram(program.name)}>
              <BenefitTile kind={program.type} size="sm" />
              <span className="tx">
                <b><Marked text={program.name} query={q} /></b>
                <span>{program.nation ? "전국 공통 · 어느 지역에서나 쓸 수 있어요" : `${program.count}곳 · 고르면 지도에 있는 곳이 칠해져요`}</span>
              </span>
            </button>
          ))}
        </>
      )}
      {children}
      {/* 이름에는 없어도 정책 글(기관·요약·조건)에 들어 있는 것까지 - 예전 검색창이 하던 일 */}
      {fullTextCount > 0 && (
        <button className="thmap-sres-all" type="button" onClick={onShowAll}>
          ‘{q}’ 들어간 정책 {fullTextCount}건 모두 보기 ›
        </button>
      )}
    </>
  );
}
