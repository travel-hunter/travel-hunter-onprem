import { ChevronLeft, Heart, Search, Share2, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { appDataApi, type ApplicationGuide, type ApplicationGuideRound, type LinkedTripPolicy, type PlaceSearchItem, type Policy, type PolicyCategory, type Trip } from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { useSession } from "../app/session";
import { Button, EmptyState, ErrorState, IconButton, LinkButton, LoadingState, Tag, Toast } from "../components/ui";
import { getDeadlinePolicies } from "../data/displayConfig";
import { PolicyRegionMap } from "../components/map/PolicyRegionMap";
import { PolicyMapSheet } from "../components/map/PolicyMapSheet";
import { cityOf, NATIONWIDE_REGION } from "../utils/policyPrograms";
import { REGION_NAMES, type RegionCounts } from "../components/map/regionMapEngine";
import { BrowseChips, PolicySearchPanel, RegionSummaryCard } from "../components/map/PolicyMapPanels";
import { BROWSE_FILTERS, browseDepthOf, browseView, chipCounts, lowerBrowseState, matchesBrowseFilter, nearOn, programName, readBrowseState, searchBrowse, writeBrowseState, type BrowseFilter, type BrowseState } from "../components/map/policyBrowse";
import { geoToMap, nearbyCities, shortCity, type NearTarget } from "../components/map/nearby";
import { useBrowseHistory } from "../components/map/useBrowseHistory";
import { AMOUNT_FILTERS, conditionCount, conditionLabel, NO_CONDITIONS, PERIOD_FILTERS, setPolicyConditions, usePolicyConditions, type AmountFilter, type PeriodFilter, type PolicyConditions } from "../components/map/policyConditions";
import { MAP_FILLS } from "../components/map/regionMapEngine";
import { deskBrowseDepthOf } from "../components/map/policyBrowse";
import { useIsDesktop } from "../lib/useMediaQuery";
import { useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Maximize2 } from "lucide-react";
import "../styles/policy-map.css";
import { daysUntilPolicyDeadline, dday, formatPolicyDeadlineTag, isDigitalTourismResidentCardPolicy, isSafePolicyDeadline, tripStatus } from "../utils";
import { canUsePolicyActions } from "../utils/policyCapabilities";
import { shareLinkWithFallback } from "../utils/share";
import { ExternalLink } from "lucide-react";
import { benefitTypeOf } from "../components/benefitTile";
import {
  PolicyBenefitSection,
  PolicyDetailFacts,
  PolicyDetailHead,
  PolicyDetailHero,
  PolicyDocumentsSection,
  PolicyNotesSection,
  PolicyPeriodSection,
  PolicySourceLine,
  PolicyTargetSection,
} from "../components/policyDetailParts";
import { policyDetailText, policyPlaceAndProgram } from "../utils/policyDetailText";

type TripSheetStatus = "closed" | "loading" | "empty" | "ready" | "submitting" | "error" | "success";

export function policyTripErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("Policy not found")) return "정책 정보를 찾을 수 없어요. 다시 확인해 주세요.";
  if (message.includes("Trip not found")) return "일정을 찾을 수 없어요. 다른 일정을 선택해 주세요.";
  if (message.includes("Policy does not match trip travel area")) {
    return "선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요.";
  }
  // 숙박세일은 지역마다 정책 행이 따로 있어 백엔드가 409로 막는다.
  // 기본 문구("잠시 후 다시 시도")는 원인을 오해하게 만든다.
  if (message.includes("Trip already has a stay discount policy")) {
    return "숙박세일 페스타 정책은 일정당 하나만 연결할 수 있어요. 기존 정책을 먼저 해제해 주세요.";
  }
  return "일정에 혜택을 담지 못했어요. 잠시 후 다시 시도해 주세요.";
}

function getPolicyTripRegionQuery(policy: Pick<Policy, "region" | "title">): string | null {
  const bracketedRegion = /^\s*\[([^\]]+)\]/.exec(policy.title)?.[1]?.trim();
  if (bracketedRegion && bracketedRegion !== "전국") return bracketedRegion;

  const titleLocalRegion = /^\s*([가-힣]{2,}(?:[·∙][가-힣]{2,})?)\s+디지털관광주민증\s+혜택/.exec(policy.title)?.[1]?.trim();
  if (titleLocalRegion && titleLocalRegion !== "전국") return titleLocalRegion;

  const region = policy.region.trim();
  return region && region !== "전국" ? region : null;
}

function getPolicyTripCreatePath(policySlug: string, regionQuery: string | null, policyRegion: string): string {
  const searchParams = new URLSearchParams({ policySlug });
  if (regionQuery) searchParams.set("region", regionQuery);
  if (regionQuery && policyRegion && policyRegion !== "전국" && policyRegion !== regionQuery) {
    searchParams.set("sido", policyRegion);
  }
  return `/trips/new?${searchParams.toString()}`;
}

/* 필터 창 초안: 혜택 형태(위 칩) · 지역(지도 선택) · 마감 · 금액 · 관심 정책만 */
type FilterDraft = { filter: BrowseFilter | null; region: string | null; period: PeriodFilter; amount: AmountFilter; savedOnly: boolean };
const EMPTY_DRAFT: FilterDraft = { filter: null, region: null, period: "전체", amount: "전체", savedOnly: false };
type DiscoveryPolicyCategory = PolicyCategory;
const discoveryCategoryFilters: DiscoveryPolicyCategory[] = ["교통", "숙박", "여행상품", "지역할인", "이벤트", "기타"];

const regionGroups: Array<{ label: string; regions: string[] }> = [
  { label: "수도권", regions: ["서울", "경기", "인천"] },
  { label: "충청", regions: ["대전", "세종", "충북", "충남"] },
  { label: "전라", regions: ["광주", "전북", "전남"] },
  { label: "경상", regions: ["대구", "부산", "울산", "경북", "경남"] },
  { label: "강원·제주", regions: ["강원", "제주"] },
];

function daysUntilDeadline(deadline: string): number {
  return daysUntilPolicyDeadline(deadline) ?? Number.POSITIVE_INFINITY;
}

function parseManWon(amount: string): number | null {
  const m = amount.match(/(\d+)\s*만원/);
  return m ? parseInt(m[1], 10) : null;
}

function matchesPeriod(policy: Policy, filter: PeriodFilter): boolean {
  if (filter === "전체") return true;
  if (!policy.deadline) return false;
  const days = daysUntilDeadline(policy.deadline);
  if (filter === "7일 이내") return days >= 0 && days <= 7;
  if (filter === "30일 이내") return days >= 0 && days <= 30;
  if (filter === "3개월 이내") return days >= 0 && days <= 90;
  return true;
}

function matchesAmount(policy: Policy, filter: AmountFilter): boolean {
  if (filter === "전체") return true;
  const won = parseManWon(policy.amount ?? "");
  if (filter === "금액 명시") return won !== null || (policy.amount ?? "").includes("%");
  if (filter === "10만원 이상") return won !== null && won >= 10;
  if (filter === "30만원 이상") return won !== null && won >= 30;
  return true;
}

function matchesConditions(policy: Policy, conditions: PolicyConditions, savedSlugs: { has: (slug: string) => boolean }) {
  return matchesPeriod(policy, conditions.period)
    && matchesAmount(policy, conditions.amount)
    && (!conditions.savedOnly || savedSlugs.has(policy.slug))
    && matchesPolicySearch(policy, conditions.text);
}

function normalizedSearchText(value: string) {
  return value.trim().toLocaleLowerCase("ko-KR");
}

function matchesPolicySearch(policy: Policy, searchTerm: string) {
  const query = normalizedSearchText(searchTerm);
  if (!query) return true;
  const haystack = [
    policy.title,
    policy.org,
    policy.region,
    policy.category,
    policy.amount,
    policy.summary,
    policy.tag,
    ...policy.requirements,
    ...policy.documents,
  ].join(" ").toLocaleLowerCase("ko-KR");
  return haystack.includes(query);
}

function getRecommendedPolicies(policies: Policy[]) {
  return [...policies].sort((left, right) => right.match - left.match).slice(0, 3);
}

function getCategoryHighlights(policies: Policy[]) {
  return discoveryCategoryFilters
    .map((category) => ({
      category,
      policy: policies.filter((policy) => policy.category === category).sort((left, right) => right.match - left.match)[0],
    }))
    .filter((item): item is { category: DiscoveryPolicyCategory; policy: Policy } => Boolean(item.policy));
}

function isGenericBenefitAmount(amount: string | null | undefined) {
  const normalized = normalizeBenefitText(amount ?? "");
  return normalized === "" || normalized === "혜택 제공" || normalized === "확인 필요" || normalized === "정책 확인";
}

function getPolicyAmountLabel(policy: Policy) {
  if (!isGenericBenefitAmount(policy.amount)) return policy.amount;
  if (policy.title.includes("디지털관광주민증")) return "디지털관광주민증 혜택";
  return `${policy.category} 혜택`;
}

function normalizeBenefitText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

function guideDate(value: string | null): string | null {
  return value ? value.slice(0, 10) : null;
}

function guideMoment(value: string | null): string {
  if (!value) return "";
  return value.endsWith("T23:59") || value.endsWith("T00:00") ? value.slice(0, 10) : value.replace("T", " ");
}

function ApplicationRoundSteps({ guide, round }: { guide: ApplicationGuide; round: ApplicationGuideRound }) {
  const nights = guide.minNights;
  return (
    <>
      <ol className="application-guide-steps" aria-label={`${round.label} 진행 순서`}>
        <li>
          <strong>신청</strong>
          <span>{round.applyStart ? `${guideMoment(round.applyStart)} ~ ` : "~ "}{guideMoment(round.applyUntil)} 공식 구글 폼 제출</span>
        </li>
        <li>
          <strong>선정 발표</strong>
          <span>추첨 후 선정된 분께 개별 문자 안내</span>
        </li>
        <li>
          <strong>섬 여행</strong>
          <span>{round.travelStart} ~ {round.travelEnd}{nights ? ` · 대상 섬에서 ${nights}박 ${nights + 1}일 이상` : ""}</span>
        </li>
        <li>
          <strong>서류 제출</strong>
          <span>여행 종료 후 {guide.documentDeadlineDaysAfterTrip}일 이내{round.documentsDueBy ? ` (${round.documentsDueBy}까지)` : ""}</span>
        </li>
        <li>
          <strong>지원금 수령</strong>
          <span>서류 검토 후 계좌이체</span>
        </li>
      </ol>
      {round.documentFormUrl && (
        <div className="application-guide-actions">
          <a className="btn secondary" href={round.documentFormUrl} rel="noreferrer" target="_blank">서류 제출 폼 열기</a>
          <p className="warning-text">선정 문자를 받은 분만 제출할 수 있어요</p>
        </div>
      )}
    </>
  );
}

/** Island support procedure by round: past rounds collapsed, the current one open with its deadline, upcoming announced. */
function ApplicationGuideSection({ guide }: { guide: ApplicationGuide }) {
  return (
    <section className="policy-detail-section application-guide" aria-label="신청 절차" role="region">
      <h2>신청 절차</h2>
      {guide.rounds.map((round) => {
        if (round.status === "past") {
          return (
            <details className="application-guide-round past" key={round.key}>
              <summary>{`${round.label} · 종료`}</summary>
              <ApplicationRoundSteps guide={guide} round={round} />
            </details>
          );
        }
        if (round.status === "upcoming") {
          return (
            <div className="application-guide-round upcoming" key={round.key}>
              <div className="application-guide-round-head">
                <strong>{`${round.label} · 예정`}</strong>
              </div>
              {round.applyStart && <p>{`신청 시작 ${guideMoment(round.applyStart)}`}</p>}
              <ApplicationRoundSteps guide={guide} round={round} />
            </div>
          );
        }
        const applyDays = daysUntilPolicyDeadline(guideDate(round.applyUntil));
        const tone = applyDays === null ? "default" : applyDays < 0 ? "gray" : applyDays <= 3 ? "warning" : "default";
        return (
          <div className="application-guide-round current" key={round.key}>
            <div className="application-guide-round-head">
              <strong>{`${round.label} · 진행 중`}</strong>
              {round.applyUntil && <Tag tone={tone}>{`신청 마감 ${dday(guideDate(round.applyUntil))}`}</Tag>}
            </div>
            <ApplicationRoundSteps guide={guide} round={round} />
          </div>
        );
      })}
    </section>
  );
}

type PolicyApplicationCta =
  | { kind: "apply"; label: string; url: string }
  | { kind: "official"; label: string; url: string }
  | { kind: "unavailable"; label: string; disabledNotice: string };

function getCurrentGuideApplicationCta(guide: Policy["applicationGuide"]): PolicyApplicationCta | null {
  const round = guide?.rounds.find((candidate) => candidate.status === "current" && candidate.key === guide.currentRoundKey)
    ?? guide?.rounds.find((candidate) => candidate.status === "current");
  const applyDays = daysUntilPolicyDeadline(guideDate(round?.applyUntil ?? null));
  if (!round?.applicationFormUrl || applyDays === null || applyDays < 0) return null;
  return { kind: "apply", label: "신청 폼 열기", url: round.applicationFormUrl };
}

function getPolicyApplicationCta(policy: Policy): PolicyApplicationCta {
  const guideCta = getCurrentGuideApplicationCta(policy.applicationGuide);
  if (guideCta) return guideCta;
  if (policy.applyUrl) return { kind: "apply", label: "신청하러 가기", url: policy.applyUrl };
  if (policy.officialUrl) return { kind: "official", label: "혜택 안내 보기", url: policy.officialUrl };
  return {
    kind: "unavailable",
    label: "신청 링크 준비 중",
    disabledNotice: "공식 신청 연결은 준비 중입니다.",
  };
}

function getPolicyControlsHelpText(policy: Policy) {
  if (policy.actionStatus === "infoOnly") {
    return "이 혜택은 공식 원문 확인만 가능해요. 저장하거나 일정에 담으려면 정규화된 정책으로 승격되어야 합니다.";
  }
  return "이 혜택은 안내 페이지에서 확인한 뒤 일정에 반영해 주세요.";
}

export function PolicyListPage() {
  const [searchParams] = useSearchParams();
  const [isFilterSheetOpen, setIsFilterSheetOpen] = useState(false);
  /* 좁히기 조건(마감 · 금액 · 관심 정책만 · 글 검색)은 지도 화면 안에서 지도 색 · 건수와 목록을 같이 좁힌다(시안 v55).
     예전엔 조건이 걸리면 지도를 떠나 예전 카드 목록으로 갔다. 조건은 층이 아니라 주소 밖(policyConditions)에 두고 ✕ 로 푼다 */
  const conditions = usePolicyConditions();
  const [draft, setDraft] = useState<FilterDraft>(EMPTY_DRAFT);
  /* 지도 화면의 상태(고른 지역·시군·사업·칩·시트 자리·돋보기)는 전부 URL 에 둔다. 컴포넌트 상태로 두면
     정책 상세에 들어갔다 뒤로 왔을 때 화면이 다시 만들어지며 처음으로 돌아간다.
     층이 늘 때만 기록을 쌓아 뒤로가기가 한 층씩 되짚는다(useBrowseHistory). */
  const browse = readBrowseState(searchParams);
  /* 넓은 화면(1024px~)은 지도 옆에 목록 패널이 늘 서 있다 - 시트 자리는 층이 아니고, 줄을 누르면 패널이 상세가 된다 */
  const isDesktop = useIsDesktop();
  const navigate = useNavigate();
  const browseHistory = useBrowseHistory(isDesktop ? deskBrowseDepthOf : browseDepthOf);
  const { go: goBrowse, back: backBrowse } = browseHistory;
  const setBrowse = (next: BrowseState) => goBrowse(writeBrowseState(searchParams, next.near && !nearOn(next) ? { ...next, near: null } : next));
  /* 지도·칩·검색으로 옮기면 패널 상세는 목록으로 돌아간다 */
  const base: BrowseState = { ...browse, detail: null };
  const openDetail = (policy: Policy) => setBrowse({ ...browse, detail: policy.slug, search: false });
  /* 좁은 화면에서 넓은 화면 주소(detail=…)로 오면 상세 페이지로 */
  useEffect(() => {
    if (!isDesktop && browse.detail) navigate(`/policies/${browse.detail}`, { replace: true });
  }, [isDesktop, browse.detail, navigate]);
  /* 검색창은 맨 위 하나(2026-09-30 사용자 결정). 누르면 지역·혜택 검색 칸이 열리고
     친 글자는 그 칸의 찾을 말이 된다. 칸이 닫히면 비운다. */
  const [panelQuery, setPanelQuery] = useState("");
  useEffect(() => {
    if (!browse.search) setPanelQuery("");
  }, [browse.search]);
  /* 위치로 찾기(시안 v56): 지역 · 시군 이름이 안 맞는 말만 서버 장소 검색(카카오)에 묻는다. null = 찾는 중 */
  const [places, setPlaces] = useState<PlaceSearchItem[] | null>(null);
  /* 시트가 선 자리의 윗변 - 지도가 그 위쪽에 그림을 맞춘다 */
  const [coverTop, setCoverTop] = useState<number | null>(null);
  const { savedSlugs, addSavedSlug, removeSavedSlug } = useSession();
  const { data: policies, error, isLoading } = useAsyncResource(() => appDataApi.listPolicies(), []);
  /* 조건이 걸린 정책 - 지도 건수 · 칩 · 목록 · 시군 점 · 지역 카드가 다 이것에서 시작한다 */
  const narrowed = useMemo(
    () => (policies ?? []).filter((policy) => matchesConditions(policy, conditions, savedSlugs)),
    [policies, conditions, savedSlugs],
  );
  /* 위 칩(혜택 형태)과 검색에서 고른 사업이 걸린 정책 - 지도 건수·목록·시군 점이 다 이것을 센다 */
  const browsePolicies = useMemo(
    () => narrowed.filter((policy) => matchesBrowseFilter(policy, browse.filter) && (!browse.program || programName(policy) === browse.program)),
    [narrowed, browse.filter, browse.program],
  );
  /* 지도에 줄 건수. 전국 정책은 세지 않는다 - 하나에 17곳이 다 켜지면 "어디에 정책이 있나"가
     사라지고, 지역 건수가 12건씩 부풀었다. 전국은 지도 왼쪽 위 '전국 공통'이 따로 센다.
     own 과 total 이 같아졌지만 엔진 계약(RegionCount)은 그대로 둔다. */
  const regionCounts = useMemo<RegionCounts>(() => {
    const counts: RegionCounts = {};
    for (const policy of browsePolicies) {
      if (policy.region === NATIONWIDE_REGION) continue;
      const entry = counts[policy.region] ?? (counts[policy.region] = { own: 0, total: 0 });
      entry.own += 1;
    }
    /* 정책 0건 지역도 항목은 있어야 지도가 흐림 처리를 한다 */
    for (const region of REGION_NAMES) {
      const entry = counts[region] ?? (counts[region] = { own: 0, total: 0 });
      entry.total = entry.own;
    }
    return counts;
  }, [browsePolicies]);
  const filterCount = conditionCount(conditions);
  const conditionLine = conditionLabel(conditions);

  const handleToggleSave = async (policy: Policy) => {
    const slug = policy.slug;
    if (savedSlugs.has(slug)) {
      await appDataApi.removeSavedPolicy(slug);
      removeSavedSlug(slug);
    } else {
      await appDataApi.savePolicy(slug);
      addSavedSlug(slug);
    }
  };

  /* ── 지도 화면 조작 ─────────────────────────────────────────── */
  /* 교통은 지역 혜택이 없다(모두 전국 공통) - 지역을 고르면 교통 칩을 푼다 */
  const dropMove = (region: string | null, filter = browse.filter) => (region && region !== NATIONWIDE_REGION && filter === "move" ? null : filter);
  /* 지도에서 지역을 누르면(엔진이 이미 같은 지역 다시 누르기를 풀기로 바꿔 준다). 지도 중심이면 목록을 올려 함께 보인다 */
  const selectRegion = (region: string | null) =>
    setBrowse({ ...base, region, city: null, filter: dropMove(region), sheet: browse.sheet === "low" ? "mid" : browse.sheet, search: false });
  /* 돋보기의 지역 칸 - 이미 고른 지역을 다시 누르면 푼다 */
  const toggleRegion = (region: string) => {
    const next = browse.region === region ? null : region;
    setBrowse({ ...base, region: next, city: null, filter: dropMove(next), sheet: "mid", search: false });
  };
  const pickPlace = (region: string, city: string) =>
    setBrowse({ ...base, region, city, filter: dropMove(region), sheet: "mid", search: false });
  const pickProgram = (program: string) =>
    setBrowse({ ...base, program, region: null, city: null, sheet: "mid", search: false });
  /* 시군 점: 다시 누르면 도 전체. 지도 중심에서 고르면 목록을 올려 3분할로 */
  const pickCity = (city: string | null) =>
    setBrowse({ ...base, city, sheet: city && browse.sheet === "low" ? "mid" : browse.sheet });
  const pickFilter = (filter: BrowseFilter | null) => {
    /* 교통은 모두 전국 공통이라 지도에서 고를 게 없다 - 위 칩에서 고르면 지역을 풀고 한 페이지 목록으로 */
    if (filter === "move") setBrowse({ ...base, filter, region: null, city: null, sheet: "full" });
    else setBrowse({ ...base, filter });
  };
  const toggleNation = () =>
    setBrowse({ ...base, region: browse.region === NATIONWIDE_REGION ? null : NATIONWIDE_REGION, city: null, sheet: browse.sheet === "low" ? "mid" : browse.sheet });
  const openNation = () => setBrowse({ ...base, region: NATIONWIDE_REGION, city: null, sheet: browse.sheet === "low" ? "mid" : browse.sheet });
  /* 빈 바다: 고른 뒤면 처음 화면으로, 처음 화면(반반)이면 지도를 보고 싶다는 뜻 - 목록을 내린다.
     넓은 화면은 목록이 늘 옆에 있어 내릴 게 없다 */
  const mapBackground = () => {
    if (!isDesktop && browse.sheet === "mid" && !browse.region) setBrowse({ ...base, sheet: "low" });
  };
  /* 목록 머리의 '전체 지역' · '○○ 전체' */
  const clearBrowse = () =>
    setBrowse(browse.city ? { ...base, city: null } : { ...base, region: null, city: null, program: null });
  const lowered = lowerBrowseState(browse, isDesktop);
  /* 위치로 찾은 곳 - 지금 고른 지역 · 시군 것일 때만 핀 · 근처 줄 · 가까운 시군 */
  const nearHere = nearOn(browse);
  const pin = useMemo(
    () => (nearHere ? geoToMap(nearHere.sido, nearHere.lat, nearHere.lng) : null),
    // 주소에서 매번 새로 읽는 객체라 값으로 비교한다
    [nearHere?.sido, nearHere?.lat, nearHere?.lng],
  );
  const stepBack = () => backBrowse(lowered ? writeBrowseState(searchParams, lowered) : null);

  /* ── 필터 창 ─────────────────────────────────────────────────── */
  /* 혜택 형태는 위 칩, 지역은 지도 선택과 같은 값이다. 마감 · 금액 · 관심 정책만이 새로 좁히는 조건 */
  const openFilterSheet = () => {
    setDraft({ filter: browse.filter, region: browse.region, period: conditions.period, amount: conditions.amount, savedOnly: conditions.savedOnly });
    setIsFilterSheetOpen(true);
  };
  const closeFilterSheet = () => setIsFilterSheetOpen(false);
  /* 아래 단추가 미리 세는 수 - 적용하면 목록 머리에 나올 건수와 같다 */
  const draftCount = useMemo(() => {
    const keepCity = draft.region === browse.region ? browse.city : null;
    return (policies ?? []).filter(
      (policy) =>
        matchesConditions(policy, { ...draft, text: conditions.text }, savedSlugs)
        && matchesBrowseFilter(policy, dropMove(draft.region, draft.filter))
        && (!browse.program || programName(policy) === browse.program)
        && (!draft.region || policy.region === draft.region)
        && (!keepCity || cityOf(policy) === keepCity),
    ).length;
  }, [policies, draft, conditions.text, savedSlugs, browse.region, browse.city, browse.program]);
  const applyDraft = () => {
    setPolicyConditions({ ...conditions, period: draft.period, amount: draft.amount, savedOnly: draft.savedOnly });
    const sameRegion = draft.region === browse.region;
    setBrowse({
      ...base,
      filter: dropMove(draft.region, draft.filter),
      region: draft.region,
      city: sameRegion ? browse.city : null,
      sheet: browse.sheet === "low" ? "mid" : browse.sheet,
      search: false,
    });
    setIsFilterSheetOpen(false);
  };
  const clearConditions = () => setPolicyConditions(NO_CONDITIONS);

  /* 시트 목록: 모든 지역 · 전국 공통 · 고른 지역(시군) */
  const browseList = useMemo(
    () => browseView(browsePolicies, browse.region, browse.city, browse.filter),
    [browsePolicies, browse.region, browse.city, browse.filter],
  );
  const chips = useMemo(() => chipCounts(narrowed, browse.region, browse.program, browse.city), [narrowed, browse.region, browse.program, browse.city]);
  /* 지도 왼쪽 위 '전국 공통 N' - 칩·사업이 걸린 수. 지역 카드의 '전국 공통 혜택 N건 보기'는 칩을 뺀 수 */
  const nationCount = useMemo(() => browsePolicies.filter((policy) => policy.region === NATIONWIDE_REGION).length, [browsePolicies]);
  const allNationCount = useMemo(() => narrowed.filter((policy) => policy.region === NATIONWIDE_REGION).length, [narrowed]);
  /* 고른 도 안의 시군 점(혜택 건수). 제목 앞 [시군] 으로 센다 */
  const mapPlaces = useMemo(() => {
    const region = browse.region;
    if (!region || region === NATIONWIDE_REGION) return [];
    const counts = new Map<string, number>();
    for (const policy of browsePolicies) {
      const city = policy.region === region ? cityOf(policy) : null;
      if (city) counts.set(city, (counts.get(city) ?? 0) + 1);
    }
    return Array.from(counts, ([name, count]) => ({ name, count }));
  }, [browsePolicies, browse.region]);
  const panelOpen = browse.search;
  /* 검색 칸이 세는 정책: 글 검색을 뺀 조건(마감 · 금액 · 관심만)이 걸린 것 - 칸의 숫자가 고른 뒤 목록과 맞게 */
  const searchPolicies = useMemo(
    () => (policies ?? []).filter((policy) => matchesConditions(policy, { ...conditions, text: "" }, savedSlugs)),
    [policies, conditions, savedSlugs],
  );
  const placeQuery = useMemo(() => {
    const q = panelQuery.trim();
    if (!browse.search || q.length < 2) return "";
    const found = searchBrowse(searchPolicies, q);
    return found.regions.length || found.places.length ? "" : q;
  }, [browse.search, panelQuery, searchPolicies]);
  useEffect(() => {
    setPlaces(null);
    if (!placeQuery) return;
    const control = new AbortController();
    const timer = window.setTimeout(() => {
      appDataApi.searchPlaces(placeQuery, { signal: control.signal }).then(setPlaces, () => {
        if (!control.signal.aborted) setPlaces([]);
      });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      control.abort();
    };
  }, [placeQuery]);
  /* 위치로 찾은 곳의 근처 혜택으로 - 그 시군(없으면 가장 가까운 시군 · 도 · 전국)을 고르고 지도에 핀 */
  const pickNear = (item: PlaceSearchItem, label: string, target: NearTarget) =>
    setBrowse({
      ...base,
      region: target.region,
      city: target.city,
      filter: dropMove(target.region),
      sheet: "mid",
      search: false,
      near: { name: label, lat: item.latitude ?? 0, lng: item.longitude ?? 0, sido: item.sido ?? "", region: target.region, city: target.city, note: target.note },
    });
  const fullTextCount = useMemo(() => {
    const q = panelQuery.trim();
    return q ? searchPolicies.filter((policy) => matchesPolicySearch(policy, q)).length : 0;
  }, [searchPolicies, panelQuery]);
  /* 검색 칸의 '모두 보기': 정책 글 전체에서 그 말이 든 정책만 남긴다(조건 - ✕ 로 푼다). 고른 지역 · 칩 · 사업은 풀어
     칸이 센 'N건'과 목록 건수가 같게 한다 - 글 검색은 지도 어디서 쳤든 전체에서 찾는 것이다 */
  const showAllMatches = () => {
    setPolicyConditions({ ...conditions, text: panelQuery.trim() });
    setBrowse({ ...base, region: null, city: null, program: null, filter: null, search: false, sheet: browse.sheet === "low" ? "mid" : browse.sheet });
  };

  /* Esc = 화면 안 ‹ 와 같은 한 층. 지도 안(지역 선택 풀기)은 제 일을 하고, 필터 창이 떠 있으면 창만 닫는다 */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (isFilterSheetOpen) return closeFilterSheet();
      if (!lowered) return;
      // 담기 창 같은 대화창이 떠 있으면 그 창의 일이다 - 뒤의 상세까지 닫지 않는다
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      if ((event.target as Element | null)?.closest?.(".thmap-host")) return;
      stepBack();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  /* 지도 화면의 세 조각 - 지도 칸 · 목록 · 검색 칸. 좁은 화면은 지도 위에 목록 시트와 검색 칸을 겹치고,
     넓은 화면은 지도 오른쪽 패널에 목록을 세우고 검색 칸·정책 상세를 그 위에 덮는다(아래 목록은 스크롤 자리째 남는다) */
  const ready = !isLoading && !error && Boolean(policies && policies.length > 0);
  /* 지도 틀은 불러오는 동안에도 미리 그린다 - 빈 화면에 '불러오는 중' 카드만 뜨면 예전 목록 화면처럼 보였다(10/2).
     그동안 지도는 건수 없이 흐리고, 불러오는 표시는 목록 자리(패널 · 시트 자리)에 선다 */
  const mapOn = ready || isLoading;
  const split = isDesktop && mapOn;
  const detailPolicy = split && browse.detail ? (policies ?? []).find((policy) => policy.slug === browse.detail) ?? null : null;
  const stage = mapOn ? (
    <div className="thmap-stage">
      {/* 넓은 화면은 지도가 넉넉해 다가가지 않는다 - 전국 틀 그대로 고른 도를 띄우고 시군 점을 찍는다 */}
      <PolicyRegionMap
        counts={regionCounts}
        onSelect={selectRegion}
        selected={browse.region}
        focus
        zoom={!isDesktop}
        showCounts={ready}
        coverTop={isDesktop ? null : coverTop}
        sheetLow={!isDesktop && browse.sheet === "low"}
        places={mapPlaces}
        selectedPlace={browse.city}
        onSelectPlace={pickCity}
        onBackground={mapBackground}
        pin={pin}
      />
      {!ready ? null : browse.region && browse.region !== NATIONWIDE_REGION ? (
        <RegionSummaryCard
          policies={narrowed}
          region={browse.region}
          filter={browse.filter}
          nationCount={allNationCount}
          onFilter={(filter) => setBrowse({ ...base, filter })}
          onNation={openNation}
        />
      ) : (
        <button className="thmap-nation" type="button" aria-pressed={browse.region === NATIONWIDE_REGION} onClick={toggleNation}>
          <span className="dot" aria-hidden="true" />전국 공통 <b>{nationCount}</b>
        </button>
      )}
      {/* 땅 색 = 혜택 건수. 지역을 고르면 지도가 좁아지니 범례보다 지도가 먼저다 */}
      {ready && !browse.region && (
        <div className="thmap-legend" aria-hidden="true">
          적음<span>{MAP_FILLS.slice(1).map((fill) => <i key={fill} style={{ background: fill }} />)}</span>많음
        </div>
      )}
    </div>
  ) : null;
  const sheet = isLoading ? (
    <div className="thmap-loading">
      <LoadingState compact label="정책을 불러오는 중입니다" />
    </div>
  ) : ready ? (
    <PolicyMapSheet
      /* 넓은 화면 패널은 필터 창이 떠도 그 뒤에 그대로 선다(비우면 빈 패널이 비친다) */
      enabled={isDesktop || !isFilterSheetOpen}
      mode={isDesktop ? "panel" : "sheet"}
      view={browseList}
      stop={browse.sheet}
      region={browse.region}
      scopeKey={`${browse.region}|${browse.city}|${browse.program}|${browse.filter}|${conditionLine}`}
      showBack={Boolean(browse.region || browse.program)}
      clearLabel={browse.city ? `${browse.region} 전체` : browse.region ? "전체 지역" : null}
      conditions={conditionLine ? { label: conditionLine, onClear: clearConditions } : null}
      near={nearHere ? {
        label: `${nearHere.name} 근처`,
        note: nearHere.note,
        /* 칩은 핀 기준 거리 순으로 고정 - 눌러도 순서 · 줄 높이가 그대로고, 보고 있는 시군만 눌린 모양(10/3 사용자 지적) */
        nearby: nearbyCities(browsePolicies, pin).slice(0, 4).map((city) => ({
          key: `${city.region}|${city.city}`,
          label: shortCity(city.region, city.city),
          meta: `약 ${city.km}km · ${city.count}건`,
          on: city.region === nearHere.region && city.city === nearHere.city,
          onPick: () => setBrowse({ ...base, region: city.region, city: city.city, filter: dropMove(city.region), near: { ...nearHere, region: city.region, city: city.city } }),
        })),
      } : null}
      onStop={(stop) => setBrowse({ ...browse, sheet: stop })}
      onBack={stepBack}
      onClear={clearBrowse}
      onNation={openNation}
      onRest={setCoverTop}
      onOpen={isDesktop ? openDetail : undefined}
    />
  ) : null;
  const search = ready && panelOpen && policies ? (
    <PolicySearchPanel
      policies={searchPolicies}
      region={browse.region}
      query={panelQuery}
      fullTextCount={fullTextCount}
      onShowAll={showAllMatches}
      onPickRegion={toggleRegion}
      onPickPlace={pickPlace}
      onPickProgram={pickProgram}
      places={placeQuery ? places : []}
      onPickNear={pickNear}
      onClose={stepBack}
    />
  ) : null;
  /* 상세는 정책이 온 뒤에만 - 불러오는 동안 '목록에 없어요'가 잠깐 뜨고 불러오는 표시를 덮었다 */
  const panelCover = split && Boolean(search || (ready && browse.detail));

  return (
    <section className={isDesktop ? "screen with-tabs prototype-policy-list-screen desktop-wide" : "screen with-tabs prototype-policy-list-screen"}>
      <div className="prototype-policy-toolbar">
        {/* 제목 줄을 걷어내고 검색줄부터 시작한다 - 지도가 그만큼 커진다. 제목은 화면에서만 빼고
            남긴다: 화면 낭독기와 아래 h2(지역 목록)의 뿌리가 되는 유일한 h1 이다.
            ♡ 관심은 필터 창의 "관심 정책만" 칩과 같은 값이라 그쪽 하나로 모은다. */}
        <h1 className="sr-only">정책 탐색</h1>

        <div className="prototype-policy-search-row">
          <Search aria-hidden="true" size={20} />
          <input
            id="policy-list-search"
            aria-label="정책 검색"
            aria-controls={panelOpen ? "policy-search-panel" : undefined}
            aria-expanded={panelOpen}
            autoComplete="off"
            enterKeyHint="search"
            onChange={(event) => {
              // 치면 늘 검색 칸으로(초점이 남은 채 칸이 닫혔어도 다시 연다)
              if (!browse.search) setBrowse({ ...base, search: true });
              setPanelQuery(event.target.value);
            }}
            onFocus={() => {
              if (!browse.search) setBrowse({ ...base, search: true });
            }}
            onKeyDown={(event) => {
              // 한글 조합을 끝내는 Enter(맥 크롬은 두 번 온다)와 빈 찾을 말은 첫 결과를 누르지 않는다
              if (!panelOpen || event.key !== "Enter" || event.nativeEvent.isComposing) return;
              event.preventDefault();
              if (!panelQuery.trim()) return;
              document.querySelector<HTMLButtonElement>("#policy-search-panel .thmap-search-body button")?.click();
            }}
            placeholder="정책명, 지역, 혜택 검색"
            type="search"
            value={panelOpen ? panelQuery : ""}
          />
          <div className="prototype-filter-controls">
            <button aria-haspopup="dialog" aria-label="필터 열기" className="prototype-filter-icon-button" onClick={openFilterSheet} type="button">
              <SlidersHorizontal aria-hidden="true" size={20} />
              <span>{filterCount > 0 ? `필터 ${filterCount}` : "필터"}</span>
            </button>
          </div>
        </div>
        {/* 위 칩: 혜택 형태. 칩을 고르면 지도 건수와 목록이 같이 바뀐다 */}
        {ready && (
          <BrowseChips counts={chips} filter={browse.filter} program={browse.program} onFilter={pickFilter} onClearProgram={() => setBrowse({ ...base, program: null })} />
        )}
      </div>
      {/* 바다가 깔리는 칸. 좁은 화면은 지도가 목록 뒤로 탭바 위까지 꽉 차 있고, 목록이 비운 만큼 드러난다.
          넓은 화면은 지도(남는 폭) + 오른쪽 목록 패널 */}
      {split ? (
        <div className="thmap-split">
          {stage}
          <div className="thmap-panel">
            <PanelUnderlay covered={panelCover}>{sheet}</PanelUnderlay>
            {search}
            {!search && ready && browse.detail && (
              detailPolicy ? (
                <PolicyPanelDetail
                  policy={detailPolicy}
                  isSaved={savedSlugs.has(detailPolicy.slug)}
                  onBack={stepBack}
                  onToggleSave={handleToggleSave}
                />
              ) : (
                <div className="thmap-pdetail thmap-pdetail-missing" role="status">
                  <p>이 정책은 지금 목록에 없어요.</p>
                  <Link className="policy-detail-secondary" to={`/policies/${browse.detail}`}>상세 페이지에서 보기</Link>
                  <button className="thmap-clear" type="button" onClick={stepBack}>목록으로</button>
                </div>
              )
            )}
          </div>
        </div>
      ) : stage}
      {error && <ErrorState message={error} action={<LinkButton to="/home" variant="line">홈으로 가기</LinkButton>} />}

      {!split && sheet}
      {!split && search}

      {isFilterSheetOpen && (
        <div className="prototype-filter-sheet-layer" role="presentation">
          <button className="prototype-filter-sheet-backdrop" aria-hidden="true" onClick={closeFilterSheet} tabIndex={-1} type="button" />
          <div className="prototype-filter-sheet" role="dialog" aria-modal="true" aria-label="정책 필터">
            <div className="prototype-filter-sheet-handle" aria-hidden="true" />
            <div className="prototype-filter-sheet-head">
              <h2>필터</h2>
              <button className="prototype-filter-sheet-close" aria-label="필터 닫기" onClick={closeFilterSheet} type="button">
                <X aria-hidden="true" size={18} />
              </button>
            </div>

            <div className="prototype-filter-section">
              <div className="prototype-filter-section-title"><span>혜택 형태</span><em>위 칩과 같아요</em></div>
              <div className="prototype-filter-chip-row" role="group" aria-label="혜택 형태">
                {BROWSE_FILTERS.map((option) => (
                  <button aria-pressed={draft.filter === option.key} className={draft.filter === option.key ? "filter-chip active" : "filter-chip"} key={option.label} onClick={() => setDraft((current) => ({ ...current, filter: option.key }))} type="button">
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="prototype-filter-section">
              <div className="prototype-filter-section-title"><span>지역</span><em>지도에서 고른 것과 같아요</em></div>
              <div className="prototype-filter-chip-row" role="group" aria-label="지역">
                {[[null, "전체"], [NATIONWIDE_REGION, "전국 공통"]].map(([value, label]) => (
                  <button aria-pressed={draft.region === value} className={draft.region === value ? "filter-chip active" : "filter-chip"} key={label} onClick={() => setDraft((current) => ({ ...current, region: value }))} type="button">
                    {label}
                  </button>
                ))}
              </div>
              <div className="prototype-region-group-list">
                {regionGroups.map((group) => (
                  <div className="prototype-region-group" key={group.label}>
                    <h3>{group.label}</h3>
                    <div className="prototype-filter-chip-row">
                      {group.regions.map((region) => (
                        <button aria-pressed={draft.region === region} className={draft.region === region ? "filter-chip active" : "filter-chip"} key={region} onClick={() => setDraft((current) => ({ ...current, region }))} type="button">
                          {region}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="prototype-filter-section">
              <div className="prototype-filter-section-title"><span>마감 · 금액</span><em>필요한 조건만</em></div>
              <div className="prototype-filter-chip-row" role="group" aria-label="마감">
                {PERIOD_FILTERS.map((period) => (
                  <button aria-pressed={draft.period === period} className={draft.period === period ? "filter-chip active" : "filter-chip"} key={period} onClick={() => setDraft((current) => ({ ...current, period }))} type="button">
                    {period === "전체" ? "기간 전체" : period}
                  </button>
                ))}
              </div>
              <div className="prototype-filter-chip-row" role="group" aria-label="금액">
                {AMOUNT_FILTERS.map((amount) => (
                  <button aria-pressed={draft.amount === amount} className={draft.amount === amount ? "filter-chip active" : "filter-chip"} key={amount} onClick={() => setDraft((current) => ({ ...current, amount }))} type="button">
                    {amount === "전체" ? "금액 전체" : amount}
                  </button>
                ))}
              </div>
              <div className="prototype-filter-chip-row" role="group" aria-label="관심 정책">
                <button className={draft.savedOnly ? "filter-chip active" : "filter-chip"} onClick={() => setDraft((current) => ({ ...current, savedOnly: !current.savedOnly }))} type="button" aria-pressed={draft.savedOnly}>
                  관심 정책만
                </button>
              </div>
            </div>

            <div className="prototype-filter-sheet-actions">
              <button className="prototype-filter-reset-button" onClick={() => setDraft(EMPTY_DRAFT)} type="button">초기화</button>
              <button className="prototype-filter-apply-button" disabled={draftCount === 0} onClick={applyDraft} type="button">
                {draftCount > 0 ? `${draftCount}건 보기` : "맞는 혜택 없음"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* 넓은 화면 패널의 목록. 검색 칸·정책 상세가 위를 덮어도 목록은 그대로 두어 펼친 묶음과 스크롤 자리를 지킨다.
   덮인 동안은 누르거나 읽히지 않게 inert(React 18 은 속성 이름을 모른다 - 직접 단다). 덮을 때 초점이 목록 안에
   있었으면(상세를 연 줄) 걷힐 때 그리로 돌려준다 */
function PanelUnderlay({ covered, children }: { covered: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const lastFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const box = ref.current;
    if (!box) return;
    if (covered) {
      const active = document.activeElement;
      lastFocus.current = active instanceof HTMLElement && box.contains(active) ? active : null;
    }
    box.toggleAttribute("inert", covered);
    if (!covered && lastFocus.current?.isConnected) lastFocus.current.focus({ preventScroll: true });
  }, [covered]);
  return (
    <div className="thmap-panel-list" ref={ref} aria-hidden={covered || undefined}>
      {children}
    </div>
  );
}

/* 정책을 일정에 담는 흐름(일정 고르기 창). 큰 상세와 넓은 화면 목록 패널의 상세가 같이 쓴다.
   알림은 부르는 쪽이 띄우므로 onNotice 로 넘긴다. */
function usePolicyTripSheet(policy: Policy | null | undefined, onNotice: (message: string | null) => void) {
  const navigate = useNavigate();
  const { addPolicy } = useSession();
  const [sheetStatus, setSheetStatus] = useState<TripSheetStatus>("closed");
  const [trips, setTrips] = useState<Trip[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [sheetError, setSheetError] = useState("");

  const addToTrip = async () => {
    if (!policy) return;
    onNotice(null);
    setSheetError("");
    setSelectedTrip(null);
    setSheetStatus("loading");
    try {
      // 담을 곳은 아직 끝나지 않은 일정만(2026-09-30 사용자 결정). 날짜를 못 읽는 일정은 숨기지 않는다.
      const availableTrips = (await appDataApi.listTrips()).filter(
        (trip) => tripStatus(trip.startDate, trip.endDate)?.tone !== "past",
      );
      setTrips(availableTrips);
      setSheetStatus(availableTrips.length > 0 ? "ready" : "empty");
    } catch {
      setSheetError("일정 목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
      setSheetStatus("error");
    }
  };

  const attachPolicyToTrip = async (trip: Trip) => {
    if (!policy) return;
    setSelectedTrip(trip);
    setSheetError("");
    setSheetStatus("submitting");
    try {
      await appDataApi.addPolicyToTrip(trip.id, policy.slug);
      setSheetStatus("success");
      onNotice("선택한 일정에 혜택을 담았어요.");
      addPolicy(policy.slug);
    } catch (attachError) {
      setSheetError(policyTripErrorMessage(attachError));
      setSheetStatus("error");
    }
  };

  const closeTripSheet = () => {
    if (sheetStatus === "submitting") return;
    setSheetStatus("closed");
  };

  const viewSelectedTrip = () => {
    if (!selectedTrip || !policy) return;
    const linkedPolicy: LinkedTripPolicy = {
      slug: policy.slug,
      title: policy.title,
      amount: policy.amount,
      region: policy.region,
      category: policy.category,
      tag: policy.tag,
      // 서버 응답이 아직 이 정책을 안 담고 있어도 일정 카드의 버튼이 공식 사이트로 나갈 수 있게
      officialUrl: policy.officialUrl ?? null,
      applyUrl: policy.applyUrl ?? null,
    };
    navigate(`/trips/${selectedTrip.id}`, { state: { linkedPolicy } });
  };

  return { sheetStatus, trips, selectedTrip, sheetError, addToTrip, attachPolicyToTrip, closeTripSheet, viewSelectedTrip };
}

/* 넓은 화면 목록 패널의 정책 상세. 목록이 이미 받은 정책을 그대로 보인다(따로 불러오지 않는다).
   사진 위 단추는 상세 페이지와 같은 자리(‹ · 크게 보기 · 저장 · 공유). 주 버튼 '내 일정에 담기'는 지도 화면을
   떠나지 않고 일정 고르기 창을 바로 연다(시안 v41). 창은 body 로 띄워 패널 틀에 갇히지 않게 한다. */
function PolicyPanelDetail({
  policy,
  isSaved,
  onBack,
  onToggleSave,
}: {
  policy: Policy;
  isSaved: boolean;
  onBack: () => void;
  onToggleSave: (policy: Policy) => Promise<void>;
}) {
  const kind = benefitTypeOf(policy);
  const text = policyDetailText(policy);
  const cta = getPolicyApplicationCta(policy);
  const canSave = canUsePolicyActions(policy);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { isPolicyAdded } = useSession();
  const tripSheet = usePolicyTripSheet(policy, setNotice);
  /* 다른 정책을 열면 맨 위부터, 초점은 ‹ 로(연 줄은 아래 목록과 함께 inert 가 된다) */
  useEffect(() => {
    bodyRef.current?.scrollTo?.(0, 0);
    bodyRef.current?.querySelector<HTMLElement>(".overlay-nav .icon-btn")?.focus({ preventScroll: true });
    setNotice(null);
  }, [policy.slug]);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);
  const toggleSave = () =>
    onToggleSave(policy).catch(() =>
      setNotice(isSaved ? "정책 저장을 해제하지 못했어요. 잠시 후 다시 시도해 주세요." : "정책을 저장하지 못했어요. 잠시 후 다시 시도해 주세요."),
    );
  const share = async () => {
    try {
      const method = await shareLinkWithFallback({
        title: policy.title,
        text: `${policy.title} 정책을 트래블헌터에서 확인해 보세요.`,
        url: `${window.location.origin}/policies/${policy.slug}`,
      });
      setNotice(method === "share" ? "정책 링크를 공유했어요." : "정책 링크를 복사했어요.");
    } catch {
      setNotice("정책 링크를 공유하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };
  return (
    <section className="thmap-pdetail" aria-label={`${programName(policy)} 상세`}>
      <div className="thmap-pdetail-body" ref={bodyRef}>
        <PolicyDetailHero kind={kind} policy={policy}>
          <div className="overlay-nav">
            <IconButton label="목록으로" onClick={onBack}>
              <ChevronLeft size={20} />
            </IconButton>
            <div className="row">
              <IconButton label="크게 보기" to={`/policies/${policy.slug}`}>
                <Maximize2 size={18} />
              </IconButton>
              <button aria-label="저장" aria-pressed={isSaved} className="icon-btn" disabled={!canSave} onClick={() => void toggleSave()} type="button">
                <Heart size={18} fill={isSaved ? "currentColor" : "none"} />
              </button>
              <IconButton label="공유" onClick={() => void share()}>
                <Share2 size={18} />
              </IconButton>
            </div>
          </div>
        </PolicyDetailHero>
        <div className="thmap-pdetail-main">
          <PolicyDetailHead kind={kind} policy={policy} />
          <PolicyDetailFacts
            amountLabel={policy.cardSummary && !isGenericBenefitAmount(policy.cardSummary) ? policy.cardSummary : getPolicyAmountLabel(policy)}
            kind={kind}
            policy={policy}
            text={text}
          />
          <PolicyBenefitSection policy={policy} text={text} />
          <PolicyPeriodSection policy={policy} text={text} />
          {policy.applicationGuide && policy.applicationGuide.rounds.length > 0 && (
            <ApplicationGuideSection guide={policy.applicationGuide} />
          )}
          <PolicyTargetSection policy={policy} text={text} />
          <PolicyDocumentsSection policy={policy} text={text} />
          <PolicyNotesSection text={text} />
          <PolicySourceLine policy={policy} text={text} />
        </div>
      </div>
      <div className="thmap-pdetail-bar">
        {notice && <Toast>{notice}</Toast>}
        {cta.kind !== "unavailable" && (
          <a className="policy-detail-secondary" href={cta.url} rel="noopener noreferrer" target="_blank">
            {cta.label}
            <ExternalLink aria-hidden="true" size={16} />
          </a>
        )}
        <button
          className="policy-detail-primary"
          disabled={!canSave}
          onClick={canSave ? () => void tripSheet.addToTrip() : undefined}
          type="button"
        >
          {isPolicyAdded(policy.slug) ? "일정에 담김" : "내 일정에 담기"}
        </button>
      </div>
      {tripSheet.sheetStatus !== "closed" &&
        createPortal(
          <div className="policy-trip-window">
            <TripSelectSheet
              error={tripSheet.sheetError}
              onClose={tripSheet.closeTripSheet}
              onSelectTrip={tripSheet.attachPolicyToTrip}
              onViewTrip={tripSheet.viewSelectedTrip}
              policyRegion={policy.region}
              policyRegionQuery={getPolicyTripRegionQuery(policy)}
              policySlug={policy.slug}
              policyTitle={policy.title}
              selectedTrip={tripSheet.selectedTrip}
              status={tripSheet.sheetStatus}
              trips={tripSheet.trips}
            />
          </div>,
          document.body,
        )}
    </section>
  );
}

function PolicyPreviewList({ policies }: { policies: Policy[] }) {
  return (
    <div className="policy-preview-list">
      {policies.map((policy) => (
        <Link className="policy-preview-row" key={policy.id} to={`/policies/${policy.slug}`}>
          <div>
            <strong>{policy.title}</strong>
            <span className="meta">
              {policy.region} · {policy.amount}
            </span>
          </div>
          <Tag tone={isDigitalTourismResidentCardPolicy(policy) ? "green" : "warning"}>{formatPolicyDeadlineTag(policy)}</Tag>
        </Link>
      ))}
    </div>
  );
}

function PolicyDiscoveryBlocks({ policies, onSelectCategory }: { policies: Policy[]; onSelectCategory: (category: DiscoveryPolicyCategory) => void }) {
  const recommendedPolicies = getRecommendedPolicies(policies);
  const deadlinePolicies = getDeadlinePolicies(policies, 3);
  const categoryHighlights = getCategoryHighlights(policies);

  return (
    <section className="policy-discovery" aria-labelledby="policy-discovery-title">
      <div className="section-title-row">
        <div>
          <p className="state-eyebrow">빠른 탐색</p>
          <h3 id="policy-discovery-title">정책 탐색 바로가기</h3>
        </div>
        <span className="meta">추천, 마감, 유형별로 먼저 살펴보세요</span>
      </div>
      <div className="policy-discovery-grid">
        <article className="policy-discovery-panel">
          <Tag tone="primary">추천</Tag>
          <h4>매칭 높은 정책</h4>
          <PolicyPreviewList policies={recommendedPolicies} />
        </article>
        <article className="policy-discovery-panel">
          <Tag tone="warning">마감</Tag>
          <h4>마감 임박</h4>
          <PolicyPreviewList policies={deadlinePolicies} />
        </article>
        <article className="policy-discovery-panel">
          <Tag tone="gray">유형</Tag>
          <h4>혜택 유형별 보기</h4>
          <div className="policy-category-grid">
            {categoryHighlights.map(({ category, policy }) => (
              <button className="policy-category-button" key={category} onClick={() => onSelectCategory(category)} type="button">
                <span>{category} 모아보기</span>
                <small>
                  {policy.title} · 매칭 {policy.match}%
                </small>
              </button>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

export function PolicyDetailPage() {
  const { policyId } = useParams();
  const navigate = useNavigate();
  const { isPolicyAdded, savedSlugs, addSavedSlug, removeSavedSlug } = useSession();
  const { data: policyData, error, isLoading } = useAsyncResource(() => appDataApi.getPolicy(policyId), [policyId]);
  const policy = policyData as Policy;
  const [notice, setNotice] = useState<string | null>(null);
  const { sheetStatus, trips, selectedTrip, sheetError, addToTrip, attachPolicyToTrip, closeTripSheet, viewSelectedTrip } =
    usePolicyTripSheet(policy, setNotice);
  const [isSavingPolicy, setIsSavingPolicy] = useState(false);
  // 넓은 화면(1024px 이상)은 두 단: 왼쪽 본문 카드 + 오른쪽 고정 카드(요약·담기). 좁은 화면은 그대로
  const isDesktop = useIsDesktop();

  // 알림은 아래 버튼 줄 위에 잠깐만 뜬다 - 계속 남으면 버튼 줄이 두 겹이 된다
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // 불러오는 동안에도 넓은 틀을 써서 다 불러온 뒤 폭이 튀지 않게 한다(.desktop-wide 는 1024px 이상에서만 뜻이 있다)
  if (isLoading) {
    return (
      <section className="screen detail prototype-policy-detail-screen desktop-wide">
        <div className="detail-body">
          <LoadingState label="정책 상세를 불러오는 중입니다" />
        </div>
      </section>
    );
  }

  if (error || !policy) {
    return (
      <section className="screen detail prototype-policy-detail-screen desktop-wide">
        <div className="detail-body">
          <ErrorState message={error ?? "정책 정보를 찾지 못했어요."} action={<LinkButton to="/policies" variant="line">정책 목록으로</LinkButton>} />
        </div>
      </section>
    );
  }

  const applicationCta = getPolicyApplicationCta(policy);
  const benefitKind = benefitTypeOf(policy);
  const detailText = policyDetailText(policy);
  const canUsePolicyControls = canUsePolicyActions(policy);
  const policyControlsHelpId = "policy-detail-controls-help";
  const policyApplicationHelpId = "policy-detail-application-help";
  const policyControlsHelpText = getPolicyControlsHelpText(policy);
  const isPolicySaved = savedSlugs.has(policy.slug);
  const isPolicyInTrip = isPolicyAdded(policy.slug);
  const savePrototypePolicy = async () => {
    if (!policy || isSavingPolicy || !canUsePolicyControls) return;
    setIsSavingPolicy(true);
    try {
      if (isPolicySaved) {
        await appDataApi.removeSavedPolicy(policy.slug);
        removeSavedSlug(policy.slug);
        setNotice("관심 정책에서 해제했어요.");
      } else {
        await appDataApi.savePolicy(policy.slug);
        addSavedSlug(policy.slug);
        setNotice("관심 정책으로 저장했어요.");
      }
    } catch {
      setNotice(isPolicySaved ? "정책 저장을 해제하지 못했어요. 잠시 후 다시 시도해 주세요." : "정책을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSavingPolicy(false);
    }
  };
  const sharePrototypePolicyLink = async () => {
    const policyUrl = `${window.location.origin}/policies/${policy.slug}`;
    try {
      const method = await shareLinkWithFallback({
        title: policy.title,
        text: `${policy.title} 정책을 트래블헌터에서 확인해 보세요.`,
        url: policyUrl,
      });
      setNotice(method === "share" ? "정책 링크를 공유했어요." : "정책 링크를 복사했어요.");
    } catch {
      setNotice("정책 링크를 공유하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  const backButton = (
    <IconButton label="뒤로" onClick={() => navigate(-1)}>
      <ChevronLeft size={20} />
    </IconButton>
  );
  const saveAndShare = (
    <div className="row">
      <button
        aria-describedby={!canUsePolicyControls ? policyControlsHelpId : undefined}
        aria-label="저장"
        className="icon-btn"
        disabled={isSavingPolicy || !canUsePolicyControls}
        onClick={savePrototypePolicy}
        type="button"
      >
        <Heart size={18} fill={isPolicySaved ? "currentColor" : "none"} />
      </button>
      <IconButton label="공유" onClick={sharePrototypePolicyLink}>
        <Share2 size={18} />
      </IconButton>
    </div>
  );
  /* 받는 것: 카드와 같은 문구(검토를 거친 cardSummary)를 먼저, 뜻 없는 말이면 금액 */
  const facts = (
    <PolicyDetailFacts
      amountLabel={
        policy.cardSummary && !isGenericBenefitAmount(policy.cardSummary) ? policy.cardSummary : getPolicyAmountLabel(policy)
      }
      kind={benefitKind}
      policy={policy}
      text={detailText}
    />
  );
  const sections = (
    <>
      <PolicyBenefitSection policy={policy} text={detailText} />
      <PolicyPeriodSection policy={policy} text={detailText} />
      {policy.applicationGuide && policy.applicationGuide.rounds.length > 0 && (
        <ApplicationGuideSection guide={policy.applicationGuide} />
      )}
      <PolicyTargetSection policy={policy} text={detailText} />
      <PolicyDocumentsSection policy={policy} text={detailText} />
      <PolicyNotesSection text={detailText} />
      <PolicySourceLine policy={policy} text={detailText} />
    </>
  );
  const tripSheet = (
    <TripSelectSheet
      error={sheetError}
      onClose={closeTripSheet}
      onSelectTrip={attachPolicyToTrip}
      onViewTrip={viewSelectedTrip}
      policyRegion={policy.region}
      policyRegionQuery={getPolicyTripRegionQuery(policy)}
      policySlug={policy.slug}
      policyTitle={policy.title}
      selectedTrip={selectedTrip}
      status={sheetStatus}
      trips={trips}
    />
  );
  /* 공식 안내는 조용한 보조, 주 버튼은 '내 일정에 담기' 하나. 좁은 화면은 탭바 자리의 버튼 줄, 넓은 화면은 오른쪽 카드 안 */
  const actions = (
    <div className={isDesktop ? "policy-detail-actions policy-detail-side-actions" : "policy-detail-actions policy-detail-bar"}>
      {notice && <Toast>{notice}</Toast>}
      {!canUsePolicyControls && (
        <p className="helper-text" id={policyControlsHelpId}>
          {policyControlsHelpText}
        </p>
      )}
      {applicationCta.kind === "unavailable" && (
        <p className="helper-text" id={policyApplicationHelpId}>
          {applicationCta.disabledNotice}
        </p>
      )}
      {applicationCta.kind !== "unavailable" ? (
        <a className="policy-detail-secondary" href={applicationCta.url} rel="noopener noreferrer" target="_blank">
          {applicationCta.label}
          <ExternalLink aria-hidden="true" size={16} />
        </a>
      ) : (
        <button
          aria-describedby={policyApplicationHelpId}
          className="policy-detail-secondary"
          disabled
          title={applicationCta.disabledNotice}
          type="button"
        >
          {applicationCta.label}
        </button>
      )}
      <button
        aria-describedby={!canUsePolicyControls ? policyControlsHelpId : undefined}
        className="policy-detail-primary"
        disabled={!canUsePolicyControls}
        onClick={canUsePolicyControls ? addToTrip : undefined}
        type="button"
      >
        {isPolicyInTrip ? "일정에 담김" : "내 일정에 담기"}
      </button>
    </div>
  );

  // 넓은 화면(시안 v41 '큰 상세'): 왼쪽 본문 카드, 오른쪽 고정 카드(받는 것·기간·받는 방법 + 담기). 담기 창은 가운데 창
  if (isDesktop) {
    return (
      <section className="screen detail prototype-policy-detail-screen desktop-wide policy-detail-desk">
        <article className="policy-detail-main">
          <div className="policy-detail-toprow">
            {backButton}
            <span className="policy-detail-toptitle">{policyPlaceAndProgram(policy.title).program}</span>
            {saveAndShare}
          </div>
          <PolicyDetailHero kind={benefitKind} policy={policy}>
            {null}
          </PolicyDetailHero>
          <div className="detail-body">
            <PolicyDetailHead kind={benefitKind} policy={policy} />
            {sections}
          </div>
        </article>
        <aside aria-label="요약과 담기" className="policy-detail-side">
          <div className="policy-detail-card">
            {facts}
            {actions}
          </div>
        </aside>
        {tripSheet}
      </section>
    );
  }

  return (
    <section className="screen detail prototype-policy-detail-screen">
      <PolicyDetailHero kind={benefitKind} policy={policy}>
        <div className="overlay-nav">
          {backButton}
          {saveAndShare}
        </div>
      </PolicyDetailHero>

      <div className="detail-body">
        <PolicyDetailHead kind={benefitKind} policy={policy} />
        {facts}
        {sections}
      </div>

      {/* 탭바 자리의 버튼 줄 */}
      {actions}

      {tripSheet}
    </section>
  );
}

function TripSelectSheet({
  error,
  onClose,
  onSelectTrip,
  onViewTrip,
  policyRegion,
  policyRegionQuery,
  policySlug,
  policyTitle,
  selectedTrip,
  status,
  trips,
}: {
  error: string;
  onClose: () => void;
  onSelectTrip: (trip: Trip) => void;
  onViewTrip: () => void;
  policyRegion: string;
  policyRegionQuery: string | null;
  policySlug: string;
  policyTitle: string;
  selectedTrip: Trip | null;
  status: TripSheetStatus;
  trips: Trip[];
}) {
  if (status === "closed") return null;
  const isSubmitting = status === "submitting";
  const newTripPath = getPolicyTripCreatePath(policySlug, policyRegionQuery, policyRegion);
  // 담기를 서버가 거절하면(지역 불일치 409·숙박 할인 중복 409) 그 일정 줄 아래에 까닭을 적고 나머지는 그대로 고를 수 있다.
  // 지역이 맞는지는 서버만 판단한다 - 화면이 미리 거르지 않는다.
  const failedTripId = status === "error" ? selectedTrip?.id ?? null : null;
  const showList = status === "ready" || status === "submitting" || (failedTripId !== null && trips.length > 0);

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <section className="trip-select-sheet" role="dialog" aria-modal="true" aria-label="일정 선택" onClick={(event) => event.stopPropagation()}>
        <div className="sheet-head">
          <h2>어느 일정에 담을까요?</h2>
          <button className="icon-btn" disabled={isSubmitting} onClick={onClose} type="button" aria-label="닫기">
            ×
          </button>
        </div>

        {status === "loading" && <LoadingState label="일정 목록을 불러오는 중입니다" />}

        {status === "empty" && (
          <EmptyState
            title="다가오는 일정이 없어요"
            body="새 일정을 만들면 이 혜택을 바로 담을 수 있어요."
            action={<Link className="btn primary full" to={newTripPath}>새 일정 만들기</Link>}
          />
        )}

        {status === "error" && failedTripId === null && (
          <div className="sheet-actions">
            <ErrorState message={error} />
          </div>
        )}

        {showList && (
          <div className="trip-select-list">
            {trips.map((trip) => {
              const failed = trip.id === failedTripId;
              const linked = trip.linkedPolicies?.some((linkedPolicy) => linkedPolicy.slug === policySlug);
              return (
                <div className="trip-select-item" key={trip.id}>
                  <button
                    aria-describedby={failed ? `trip-select-error-${trip.id}` : undefined}
                    className="trip-select-row"
                    disabled={isSubmitting}
                    onClick={() => onSelectTrip(trip)}
                    type="button"
                  >
                    <div>
                      <strong>
                        {trip.title}
                        {linked && <span className="trip-select-linked">담음</span>}
                      </strong>
                      <div className="meta">{trip.dates}</div>
                    </div>
                    <span className="btn sm secondary">
                      {selectedTrip?.id === trip.id && isSubmitting ? "담는 중" : failed ? "다시 선택" : "선택"}
                    </span>
                  </button>
                  {failed && (
                    <p className="trip-select-row-error" id={`trip-select-error-${trip.id}`} role="alert">
                      {error}
                    </p>
                  )}
                </div>
              );
            })}
            <Link className="btn line full" to={newTripPath}>
              새 일정에 담기
            </Link>
          </div>
        )}

        {status === "success" && (
          <div className="sheet-actions">
            <div className="state-panel">
              <strong>{policyTitle}을 {selectedTrip?.title ?? "선택한 일정"}에 담았어요</strong>
              <p>{selectedTrip?.title ?? "선택한 일정"}에서 연결된 정책을 확인할 수 있어요.</p>
            </div>
            <Button full onClick={onViewTrip}>
              일정에서 보기
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
