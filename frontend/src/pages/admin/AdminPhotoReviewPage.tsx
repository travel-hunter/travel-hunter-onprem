import { FormEvent, useEffect, useRef, useState, type RefObject } from "react";
import { useOutletContext } from "react-router-dom";
import {
  ApiError,
  appDataApi,
  type AdminPhotoReviewCandidate,
  type AdminPhotoReviewCollectStatus,
  type AdminPhotoReviewPhoto,
  type AdminPhotoReviewStatus,
  type AdminPhotoReviewTarget,
  type AdminPhotoReviewTargetDetail,
  type AdminPhotoReviewTargetListResponse,
  type AdminPhotoReviewUnit,
  type Policy,
} from "../../api";
import { BENEFIT_TYPES, BenefitTile, benefitTypeOf, type BenefitType } from "../../components/benefitTile";
import "../../styles/home.css";
import "../../styles/admin-photo-review.css";

/* 사진 검토(시안 v50·v51): 수집이 시군·정책마다 넣은 후보 중 관리자가 한 장을 확정해야 앱에 나간다.
   시군은 아니면 혜택 그림, 정책은 아니면 시군 사진을 그대로 쓴다. 결정하면 다음 검토 대기로 넘어간다. */

export type AdminOutletContext = { setPhotoPending?: (count: number) => void };

type Filter = AdminPhotoReviewStatus | "all";

const UNITS: Record<AdminPhotoReviewUnit, { label: string; none: string; pill: string; noneButton: string; count: string }> = {
  region: { label: "시군 사진", none: "혜택 그림", pill: "그림", noneButton: "모두 아님 · 혜택 그림", count: "곳" },
  policy: { label: "정책 사진", none: "시군 사진", pill: "시군", noneButton: "시군 사진 그대로 쓰기", count: "건" },
};
const FILTERS: Array<{ value: Filter; label: (unit: AdminPhotoReviewUnit) => string }> = [
  { value: "pending", label: () => "검토 대기" },
  { value: "approved", label: () => "사진 확정" },
  { value: "none", label: (unit) => UNITS[unit].none },
  { value: "all", label: () => "전체" },
];
const KOGL: Record<string, string> = { Type1: "제1유형", Type3: "제3유형" };

const placeName = (target: AdminPhotoReviewTarget) => target.city || `${target.sido} 전체`;
const policyName = (target: AdminPhotoReviewTarget) => (target.policyTitle ?? "").replace(/^\[[^\]]+\]\s*/, "");
const titleOf = (target: AdminPhotoReviewTarget) => (target.unit === "region" ? placeName(target) : policyName(target));
const kindOf = (target: AdminPhotoReviewTarget): BenefitType =>
  benefitTypeOf({ title: target.policyTitle ?? "", category: (target.policyCategory ?? "기타") as Policy["category"] });
const credit = (copyrightType: string | null) =>
  `공공누리 ${(copyrightType && KOGL[copyrightType]) || copyrightType || "유형 미상"}`;

/** 서버가 UTC(끝에 Z)로 준 시각을 브라우저 시간대로 '10/2 14:20' */
function shortTime(iso: string | null | undefined) {
  if (!iso) return "";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  const two = (value: number) => String(value).padStart(2, "0");
  return `${at.getMonth() + 1}/${at.getDate()} ${two(at.getHours())}:${two(at.getMinutes())}`;
}

const COLLECT_POLL_MS = 2000;

function collectDoneMessage(status: AdminPhotoReviewCollectStatus) {
  const empty = status.targetsEmpty ? ` · 못 채운 ${status.targetsEmpty}곳은 이름으로 찾아 주세요` : "";
  if (!status.candidatesAdded && !status.targetsCreated) return `새로 받을 후보가 없습니다${empty}`;
  return `후보 ${status.candidatesAdded}장을 넣었습니다 · 새 대상 ${status.targetsCreated}곳${empty}`;
}

type StatusMessages = Partial<Record<number, string>>;

/* 확정은 503 · 502 의 뜻이 다르다 - 보관 위치가 없거나 원본을 받지 못한 것(관광공사 API 와 무관) */
const APPROVE_MESSAGES: StatusMessages = {
  503: "사진 보관 위치(MEDIA_ROOT)가 설정되지 않아 확정할 수 없습니다.",
  502: "사진 원본을 받지 못해 확정하지 않았습니다. 다른 후보를 고르거나 잠시 뒤 다시 시도하세요.",
};

function errorMessage(cause: unknown, fallback: string, messages: StatusMessages = {}) {
  if (cause instanceof ApiError) {
    if (messages[cause.status]) return messages[cause.status] as string;
    if (cause.status === 503) return "관광공사 API 가 꺼져 있어 사진을 받을 수 없습니다.";
    if (cause.status === 502) return "관광공사 응답을 받지 못했습니다. 잠시 뒤 다시 시도하세요.";
    if (cause.status === 409) return "이미 결정한 대상입니다. 다시 고르기를 누른 뒤에 하세요.";
  }
  return fallback;
}

export function AdminPhotoReviewPage() {
  const outlet = useOutletContext<AdminOutletContext | undefined>();
  const setPhotoPending = outlet?.setPhotoPending;
  const [unit, setUnit] = useState<AdminPhotoReviewUnit>("region");
  const [filter, setFilter] = useState<Filter>("pending");
  const [list, setList] = useState<AdminPhotoReviewTargetListResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminPhotoReviewTargetDetail | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [searchMiss, setSearchMiss] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [detailKey, setDetailKey] = useState(0);
  const [collect, setCollect] = useState<AdminPhotoReviewCollectStatus | null>(null);
  const focusHeading = useRef(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const shownId = useRef<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    appDataApi
      .listAdminPhotoReviewTargets({ unit, status: filter })
      .then((response) => {
        if (cancelled) return;
        setList(response);
        setPhotoPending?.(response.pendingTotal);
        // 단위·보기를 바꾸면 고른 것을 비우고 첫 항목으로. 결정 · 다시 고르기 뒤에는 고른 것을 그대로 둔다(목록에서 빠져도)
        setSelectedId((current) => current ?? response.items[0]?.id ?? null);
      })
      .catch(() => {
        if (!cancelled) setError("사진 검토 목록을 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [unit, filter, reloadKey, setPhotoPending]);

  useEffect(() => {
    if (!selectedId) {
      shownId.current = null;
      setDetail(null);
      return;
    }
    let cancelled = false;
    appDataApi
      .getAdminPhotoReviewTarget(selectedId)
      .then((response) => {
        if (cancelled) return;
        // 같은 대상을 다시 받은 것(수집이 끝남)이면 후보만 바꾼다 - 고르던 후보 · 찾던 말 · 스크롤을 지우지 않는다
        if (shownId.current === selectedId) return setDetail(response);
        shownId.current = selectedId;
        showDetail(response);
        detailRef.current?.scrollTo?.({ top: 0 });
      })
      .catch(() => {
        if (!cancelled) setError("사진 후보를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, detailKey]);

  // '후보 채우기': 처음에 상태를 한 번 묻고, 도는 동안은 몇 초마다 다시 묻는다(수집은 서버가 뒤에서 돌린다)
  useEffect(() => {
    let cancelled = false;
    appDataApi
      .getAdminPhotoReviewCollect()
      .then((status) => {
        if (!cancelled) setCollect(status);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!collect?.running) return;
    const timer = window.setTimeout(() => {
      appDataApi
        .getAdminPhotoReviewCollect()
        .then((status) => {
          setCollect(status);
          if (!status.running) finishCollect(status);
        })
        .catch(() => {
          setError("후보 수집 진행을 불러오지 못했습니다. 다시 묻는 중입니다.");
          setCollect((current) => (current ? { ...current } : current));   // 같은 상태를 새 값으로 - 몇 초 뒤 다시 묻는다
        });
    }, COLLECT_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [collect]);

  useEffect(() => {
    if (detail && focusHeading.current) {
      focusHeading.current = false;
      headingRef.current?.focus({ preventScroll: true });
    }
  }, [detail]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function finishCollect(status: AdminPhotoReviewCollectStatus) {
    if (status.error) setError(`후보 수집이 멈췄습니다: ${status.error}`);
    else setToast(collectDoneMessage(status));
    setReloadKey((key) => key + 1);
    setDetailKey((key) => key + 1);
  }

  async function startCollect() {
    if (starting) return;
    setStarting(true);
    setError("");
    try {
      const status = await appDataApi.startAdminPhotoReviewCollect();
      setCollect(status);
      if (!status.running) finishCollect(status);   // 빈 곳이 거의 없으면 응답 전에 끝난다
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError("이미 후보를 받는 중입니다.");
        appDataApi.getAdminPhotoReviewCollect().then(setCollect).catch(() => undefined);
      } else {
        setError(errorMessage(cause, "후보 수집을 시작하지 못했습니다."));
      }
    } finally {
      setStarting(false);
    }
  }

  function showDetail(next: AdminPhotoReviewTargetDetail) {
    setDetail(next);
    setPick(next.photo?.candidateId ?? null);
    setKeyword("");
    setSearchMiss(null);
  }

  async function run(action: () => Promise<AdminPhotoReviewTargetDetail>, fallback: string, messages?: StatusMessages) {
    setBusy(true);
    setError("");
    try {
      return await action();
    } catch (cause) {
      setError(errorMessage(cause, fallback, messages));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function decide(kind: "approve" | "none") {
    if (!detail || (kind === "approve" && !pick)) return;
    const items = list?.items ?? [];
    const at = items.findIndex((item) => item.id === detail.id);
    const next = items
      .map((_, offset) => items[(at + 1 + offset) % items.length])
      .find((item) => item && item.id !== detail.id && item.status === "pending");
    const decided = await run(
      () =>
        kind === "approve"
          ? appDataApi.approveAdminPhotoReviewTarget(detail.id, pick as string)
          : appDataApi.markAdminPhotoReviewTargetNone(detail.id),
      "결정을 저장하지 못했습니다.",
      kind === "approve" ? APPROVE_MESSAGES : undefined,
    );
    if (!decided) return;
    const what = kind === "approve" ? "사진을 확정했습니다" : detail.unit === "region" ? "혜택 그림으로 둡니다" : "시군 사진을 그대로 씁니다";
    setToast(`${titleOf(decided)}: ${what}${next ? ` · 다음 ${titleOf(next)}` : " · 검토 대기를 모두 마쳤습니다"}`);
    focusHeading.current = true;
    if (next) setSelectedId(next.id);
    else showDetail(decided);
    setReloadKey((key) => key + 1);
  }

  async function reopen() {
    if (!detail) return;
    const reopened = await run(() => appDataApi.reopenAdminPhotoReviewTarget(detail.id), "되돌리지 못했습니다.");
    if (!reopened) return;
    focusHeading.current = true;
    showDetail(reopened);
    setToast(`${titleOf(reopened)}: 다시 고를 수 있습니다`);
    setReloadKey((key) => key + 1);
  }

  async function fetchMore() {
    if (!detail) return;
    const before = detail.candidates.length;
    const more = await run(() => appDataApi.fetchMoreAdminPhotoReviewCandidates(detail.id), "후보를 더 받지 못했습니다.");
    if (!more) return;
    setDetail(more);
    const added = more.candidates.length - before;
    setToast(added > 0 ? `후보 ${added}장을 더 받았습니다` : "더 받을 사진이 없습니다. 이름으로 찾아 보세요");
    setReloadKey((key) => key + 1);
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const word = keyword.trim();
    if (!detail || !word) return;
    const before = new Set(detail.candidates.map((candidate) => candidate.id));
    const found = await run(() => appDataApi.searchAdminPhotoReviewCandidates(detail.id, word), "사진을 찾지 못했습니다.");
    if (!found) return;
    setDetail(found);
    const added = found.candidates.filter((candidate) => !before.has(candidate.id)).length;
    setSearchMiss(added > 0 ? null : word);
    setReloadKey((key) => key + 1);
  }

  const meta = UNITS[unit];
  const counts = list?.counts;
  const decidedCount = counts ? counts.approved + counts.none : 0;

  return (
    <section className="admin-page photo-review">
      <div className="admin-page-head photo-review-head">
        <div>
          <p>관리자</p>
          <h1>사진 검토</h1>
        </div>
        <div className="photo-review-head-right">
        {counts && (
          <div className="photo-review-progress">
            <span>
              {meta.label} <b>{decidedCount}{meta.count}</b> 결정 · {counts.all}{meta.count} 중
            </span>
            <span className="photo-review-bar" aria-hidden="true">
              <i className="ok" style={{ width: `${counts.all ? (counts.approved / counts.all) * 100 : 0}%` }} />
              <i className="no" style={{ width: `${counts.all ? (counts.none / counts.all) * 100 : 0}%` }} />
            </span>
            <small>
              사진 {counts.approved} · {meta.none} {counts.none} · 대기 {counts.pending}
            </small>
          </div>
        )}
          <CollectBox collect={collect} list={list} onStart={startCollect} starting={starting} />
        </div>
      </div>

      <div className="photo-review-tabs">
        <div className="photo-review-seg" role="group" aria-label="검토 단위">
          {(Object.keys(UNITS) as AdminPhotoReviewUnit[]).map((value) => (
            <button
              aria-pressed={unit === value}
              key={value}
              onClick={() => {
                setUnit(value);
                setSelectedId(null);
              }}
              type="button"
            >
              {UNITS[value].label}
            </button>
          ))}
        </div>
        <div className="photo-review-filter" role="group" aria-label="상태로 거르기">
          {FILTERS.map((item) => (
            <button
              aria-pressed={filter === item.value}
              key={item.value}
              onClick={() => {
                setFilter(item.value);
                setSelectedId(null);
              }}
              type="button"
            >
              {item.label(unit)}
              {counts && <span>{counts[item.value]}</span>}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="photo-review-body">
        <ol aria-label={`${meta.label} 목록`} className="photo-review-queue">
          {list && list.items.length === 0 && <li className="admin-empty">이 보기에 항목이 없습니다.</li>}
          {list?.items.map((item) => (
            <li key={item.id}>
              <button
                aria-current={item.id === selectedId ? "true" : undefined}
                className="photo-review-row"
                onClick={() => setSelectedId(item.id)}
                type="button"
              >
                <QueueThumb target={item} />
                <span className="photo-review-row-text">
                  <b>{item.unit === "region" ? placeName(item) : item.city || item.sido}</b>
                  {item.unit === "region" ? (
                    <i>
                      {item.sido} · 혜택 {item.benefitCount}건
                    </i>
                  ) : (
                    <i className="two-lines">{policyName(item)}</i>
                  )}
                </span>
                <StatusPill status={item.status} unit={item.unit} />
              </button>
            </li>
          ))}
        </ol>

        <div className="photo-review-detail" ref={detailRef}>
          {detail && (
            <TargetDetail
              busy={busy}
              detail={detail}
              headingRef={headingRef}
              keyword={keyword}
              onFetchMore={fetchMore}
              onKeyword={setKeyword}
              onPick={setPick}
              onReopen={reopen}
              onSearch={search}
              pick={pick}
              searchMiss={searchMiss}
            />
          )}
        </div>

        <aside aria-label="미리보기와 결정" className="photo-review-rail">
          {detail && (
            <Rail busy={busy} detail={detail} onApprove={() => decide("approve")} onNone={() => decide("none")} pick={pick} />
          )}
        </aside>
      </div>
      <p className="photo-review-toast" role="status">
        {toast}
      </p>
    </section>
  );
}

function CollectBox({
  collect,
  list,
  onStart,
  starting,
}: {
  collect: AdminPhotoReviewCollectStatus | null;
  list: AdminPhotoReviewTargetListResponse | null;
  onStart: () => void;
  starting: boolean;
}) {
  if (collect?.running) {
    return (
      <div aria-live="polite" className="photo-review-collect">
        <button className="photo-review-ghost" disabled type="button">
          후보 받는 중…
        </button>
        <small>
          <b>
            {collect.done}/{collect.total}곳
          </b>{" "}
          · 후보 {collect.candidatesAdded}장
          <br />
          도는 동안에도 검토할 수 있어요
        </small>
        <span aria-hidden="true" className="photo-review-bar mini">
          <i className="ok" style={{ width: `${collect.total ? (collect.done / collect.total) * 100 : 0}%` }} />
        </span>
      </div>
    );
  }
  const last = collect?.lastRun;
  return (
    <div aria-live="polite" className="photo-review-collect">
      <button className="photo-review-ghost" disabled={starting} onClick={onStart} type="button">
        후보 채우기
      </button>
      <small>
        {list?.newTargets ? <b>새로 들어올 대상 {list.newTargets}곳</b> : "새로 들어올 대상 없음"}
        <br />
        후보가 모자란 대상 {list?.shortTargets ?? 0}곳
        <br />
        {last ? `마지막 수집 ${shortTime(last.at)} · ${last.candidatesAdded.toLocaleString("ko-KR")}장` : "마지막 수집 기록 없음"}
      </small>
    </div>
  );
}

function QueueThumb({ target }: { target: AdminPhotoReviewTarget }) {
  const photo = target.status === "approved" ? target.photo : target.status === "none" && target.unit === "policy" ? target.inheritedPhoto : null;
  if (photo) return <img alt="" className="photo-review-thumb" loading="lazy" src={photo.imageUrl} />;
  if (target.status === "none") {
    return (
      <span aria-hidden="true" className="photo-review-thumb tile">
        <BenefitTile kind={target.unit === "policy" ? kindOf(target) : "trip"} size="sm" />
      </span>
    );
  }
  return (
    <span aria-hidden="true" className="photo-review-thumb pending">
      {target.candidateCount}
    </span>
  );
}

function StatusPill({ status, unit }: { status: AdminPhotoReviewStatus; unit: AdminPhotoReviewUnit }) {
  const [className, label] = status === "approved" ? ["ok", "사진"] : status === "none" ? ["no", UNITS[unit].pill] : ["pending", "대기"];
  return <em className={`photo-review-pill ${className}`}>{label}</em>;
}

function TargetDetail({
  detail,
  pick,
  keyword,
  searchMiss,
  busy,
  headingRef,
  onPick,
  onKeyword,
  onSearch,
  onFetchMore,
  onReopen,
}: {
  detail: AdminPhotoReviewTargetDetail;
  pick: string | null;
  keyword: string;
  searchMiss: string | null;
  busy: boolean;
  headingRef: RefObject<HTMLHeadingElement>;
  onPick: (candidateId: string) => void;
  onKeyword: (value: string) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onFetchMore: () => void;
  onReopen: () => void;
}) {
  const decided = detail.status !== "pending";
  const collected = detail.candidates.filter((candidate) => candidate.source !== "search");
  const found = detail.candidates.filter((candidate) => candidate.source === "search");
  const approved = detail.candidates.find((candidate) => candidate.id === detail.photo?.candidateId);
  const keywords = Array.from(new Set(found.map((candidate) => candidate.searchKeyword).filter(Boolean)));
  const decidedAt = shortTime(detail.decidedAt);
  return (
    <>
      <div className="photo-review-detail-head">
        <div>
          <h2 ref={headingRef} tabIndex={-1}>
            {titleOf(detail)}
          </h2>
          <p>
            {detail.unit === "region"
              ? `${detail.sido} · 혜택 ${detail.benefitCount}건 · 후보 ${detail.candidates.length}장`
              : `${detail.city || detail.sido} · ${detail.sido} · 후보 ${detail.candidates.length}장`}
          </p>
        </div>
        {!decided && (
          <button className="photo-review-ghost" disabled={busy} onClick={onFetchMore} type="button">
            후보 6장 더 받기
          </button>
        )}
      </div>

      {decided && (
        <div className={`photo-review-done ${detail.status === "approved" ? "ok" : "no"}`}>
          <span>
            <b>{detail.status === "approved" ? "사진 확정" : detail.unit === "region" ? "혜택 그림" : "시군 사진 그대로"}</b>
            {detail.status === "approved"
              ? ` · ${approved?.title ?? detail.photo?.title ?? ""}${approved?.source === "search" ? " · 이름으로 찾음" : ""}`
              : ` · ${detail.unit === "region" ? "후보 중 맞는 사진 없음" : "정책 사진을 따로 두지 않음"}`}
            {decidedAt && ` · ${decidedAt}`}
          </span>
          <button disabled={busy} onClick={onReopen} type="button">
            다시 고르기
          </button>
        </div>
      )}

      {collected.length === 0 && found.length === 0 && (
        <p className="photo-review-miss">
          후보가 아직 없습니다. 수집을 돌리거나 ‘후보 6장 더 받기’ · ‘이름으로 찾기’를 쓰세요.
        </p>
      )}
      {collected.length > 0 && (
        <CandidateSet
          candidates={collected}
          decided={decided}
          legend="자동 후보"
          note={
            detail.unit === "region"
              ? "관광공사 조회순 · 관광지·시장·축제를 번갈아 · 수집 기준 통과"
              : "이 시군 관광지 · 시군 후보·다른 정책과 겹치지 않게 · 수집 기준 통과"
          }
          onPick={onPick}
          pick={pick}
        />
      )}

      {!decided && (
        <form className="photo-review-find" onSubmit={onSearch}>
          <label htmlFor="photo-review-keyword">이름으로 찾기</label>
          <div>
            <input
              autoComplete="off"
              id="photo-review-keyword"
              onChange={(event) => onKeyword(event.target.value)}
              placeholder="장소 이름 (예: 죽녹원)"
              type="search"
              value={keyword}
            />
            <button disabled={busy || !keyword.trim()} type="submit">
              찾기
            </button>
          </div>
          <p>같은 시도이고 수집 기준(공공누리·크기)을 통과한 사진만 보여 줍니다. 음식점·숙박은 뺍니다.</p>
        </form>
      )}

      {searchMiss && (
        <p className="photo-review-miss">
          ‘{searchMiss}’(으)로 새로 찾은 사진이 없습니다. 이미 후보에 있는 사진은 다시 넣지 않습니다.
        </p>
      )}
      {found.length > 0 && (
        <CandidateSet
          candidates={found}
          decided={decided}
          legend="찾은 사진"
          note={keywords.map((word) => `‘${word}’`).join(" · ")}
          onPick={onPick}
          pick={pick}
        />
      )}
    </>
  );
}

function CandidateSet({
  legend,
  note,
  candidates,
  pick,
  decided,
  onPick,
}: {
  legend: string;
  note: string;
  candidates: AdminPhotoReviewCandidate[];
  pick: string | null;
  decided: boolean;
  onPick: (candidateId: string) => void;
}) {
  return (
    <fieldset className="photo-review-set" disabled={decided}>
      <legend>
        {legend}
        <span>{note}</span>
      </legend>
      <div className="photo-review-grid">
        {candidates.map((candidate) => (
          <label className="photo-review-option" key={candidate.id} title={candidate.address ?? undefined}>
            <input
              checked={pick === candidate.id}
              name="photo-review-pick"
              onChange={() => onPick(candidate.id)}
              type="radio"
              value={candidate.id}
            />
            <img alt="" loading="lazy" src={candidate.imageUrl} />
            <span className="photo-review-option-title">{candidate.title}</span>
            <span className="photo-review-option-meta">
              <em>{candidate.kind}</em>
              {credit(candidate.copyrightType)}
            </span>
            <span className="photo-review-option-addr">{candidate.address ?? ""}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Rail({
  detail,
  pick,
  busy,
  onApprove,
  onNone,
}: {
  detail: AdminPhotoReviewTargetDetail;
  pick: string | null;
  busy: boolean;
  onApprove: () => void;
  onNone: () => void;
}) {
  const decided = detail.status !== "pending";
  const chosen: AdminPhotoReviewPhoto | AdminPhotoReviewCandidate | null = decided
    ? detail.photo
    : detail.candidates.find((candidate) => candidate.id === pick) ?? null;
  const isRegion = detail.unit === "region";
  const shown = chosen ?? (isRegion ? null : detail.inheritedPhoto);
  const label = decided ? (isRegion ? "앱 홈 시군 카드" : "앱 정책 상세 머리") : `${chosen ? "확정하면" : "지금"} ${isRegion ? "홈 시군 카드" : "정책 상세 머리"}`;
  const note = chosen ? (
    <>
      사진: 한국관광공사
      <br />
      {credit(chosen.copyrightType)}
    </>
  ) : isRegion
      ? decided
        ? "맞는 사진이 없어 혜택 그림"
        : "확정 전에는 혜택 그림이 나갑니다"
      : detail.inheritedPhoto
        ? `시군 사진(${detail.inheritedPhoto.title})을 그대로 씁니다`
        : "시군 사진도 정해지지 않아 혜택 그림";
  return (
    <>
      <p className="photo-review-rail-label">{label}</p>
      {isRegion ? <HomeCardPreview photo={shown} target={detail} /> : <DetailHeadPreview photo={shown} target={detail} />}
      <p className="photo-review-credit">{note}</p>
      <dl className="photo-review-use">
        <dt>쓰이는 곳</dt>
        {isRegion ? (
          <>
            <dd>홈 ‘혜택이 많은 지역’ 카드</dd>
            <dd>사진을 따로 두지 않은 이 시군 정책의 상세 머리</dd>
          </>
        ) : (
          <dd>이 정책의 상세 머리</dd>
        )}
      </dl>
      {!decided && (
        <div className="photo-review-actions">
          <button className="primary" disabled={busy || !pick} onClick={onApprove} type="button">
            이 사진으로 확정
          </button>
          <button className="secondary" disabled={busy} onClick={onNone} type="button">
            {UNITS[detail.unit].noneButton}
          </button>
        </div>
      )}
      <p className="photo-review-fine">
        결정은 변경 이력에 남고, 다음 수집은 결정한 {isRegion ? "시군" : "정책"}을 건드리지 않습니다.
      </p>
    </>
  );
}

function HomeCardPreview({ target, photo }: { target: AdminPhotoReviewTarget; photo: { imageUrl: string } | null }) {
  const kind: BenefitType = "trip";
  return (
    <div className={photo ? "home-region-card" : `home-region-card nophoto family-${BENEFIT_TYPES[kind].family}`}>
      {photo ? <img alt="" className="home-region-photo" src={photo.imageUrl} /> : <BenefitTile kind={kind} />}
      <b>{placeName(target)}</b>
      <i>
        {target.sido} · 혜택 {target.benefitCount}건
      </i>
    </div>
  );
}

function DetailHeadPreview({ target, photo }: { target: AdminPhotoReviewTarget; photo: { imageUrl: string } | null }) {
  const kind = kindOf(target);
  return (
    <div className="photo-review-head-preview">
      <div className={photo ? "photo" : `photo nophoto family-${BENEFIT_TYPES[kind].family}`}>
        {photo ? <img alt="" src={photo.imageUrl} /> : <BenefitTile kind={kind} />}
      </div>
      <p>
        <span>
          {target.city || target.sido} · {BENEFIT_TYPES[kind].label}
        </span>
        <b>{policyName(target)}</b>
      </p>
    </div>
  );
}
