import { Search } from "lucide-react";
import { useLayoutEffect, useRef, type RefObject } from "react";
import type { Policy } from "../../api";
import { BenefitTile } from "../benefitTile";
import { NATIONWIDE_REGION } from "../../utils/policyPrograms";
import { REGION_PHOTOS } from "./regionPhotos";
import {
  BROWSE_FILTERS,
  filterLabel,
  REGION_FULL_NAMES,
  regionSummary,
  regionTiles,
  searchBrowse,
  type BrowseFilter,
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
export function PolicySearchPanel({
  policies,
  region,
  query,
  fullTextCount,
  onShowAll,
  onPickRegion,
  onPickPlace,
  onPickProgram,
}: {
  policies: Policy[];
  region: string | null;
  query: string;
  fullTextCount: number;
  onShowAll: () => void;
  onPickRegion: (region: string) => void;
  onPickPlace: (region: string, place: string) => void;
  onPickProgram: (program: string) => void;
}) {
  const q = query.trim();
  const counts = policies.reduce<Record<string, number>>((acc, policy) => {
    acc[policy.region] = (acc[policy.region] ?? 0) + 1;
    return acc;
  }, {});
  const found = q ? searchBrowse(policies, q) : null;
  const regionLine = (name: string, count: number) => `${REGION_FULL_NAMES[name]} · ${count ? `혜택 ${count}건` : "전용 혜택 없음"}`;
  return (
    <div className="thmap-search" role="region" aria-label="지역·혜택 검색 결과" id="policy-search-panel">
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
        {found && (found.regions.length > 0 || found.places.length > 0) && (
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
        {found && found.programs.length > 0 && (
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
        {found && !found.regions.length && !found.places.length && !found.programs.length && !fullTextCount && (
          <p className="thmap-sres-empty">‘{q}’에 맞는 지역이나 혜택이 없어요. 시군은 혜택이 있는 곳만 찾을 수 있어요.</p>
        )}
        {/* 이름에는 없어도 정책 글(기관·요약·조건)에 들어 있는 것까지 - 예전 검색창이 하던 일 */}
        {found && fullTextCount > 0 && (
          <button className="thmap-sres-all" type="button" onClick={onShowAll}>
            ‘{q}’ 들어간 정책 {fullTextCount}건 모두 보기 ›
          </button>
        )}
      </div>
    </div>
  );
}
