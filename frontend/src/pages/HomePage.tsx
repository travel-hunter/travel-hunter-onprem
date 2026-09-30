import { Search, X } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
} from "react";
import { Link } from "react-router-dom";
import {
  appDataApi,
  type Policy,
  type Profile,
  type RegionRecommendation,
} from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { useSession } from "../app/session";
import {
  AiRecommendationCard,
  type AiRecommendationCardVisual,
} from "../components/AiRecommendationCard";
import {
  BENEFIT_TYPES,
  BenefitTile,
  benefitTypeOf,
} from "../components/benefitTile";
import { KOREA_REGION_SHAPES } from "../components/map/koreaRegionShapes";
import { REGION_PHOTOS } from "../components/map/regionPhotos";
import { HomeSectionHeader } from "../components/patterns";
import { ErrorState, LoadingState } from "../components/ui";
import {
  getHomeBenefitPolicies,
  getNationwideHomePolicies,
} from "../data/displayConfig";
import {
  NATIONWIDE_REGION,
  cityOf,
  programOf,
} from "../utils/policyPrograms";
import { daysUntilPolicyDeadline, formatPolicyDeadlineTag } from "../utils";
import "../styles/home.css";

const PROFILE_PROMPT_DISMISSAL_PREFIX =
  "travel-hunter-profile-completion-dismissed:";
const AI_CAROUSEL_SWIPE_THRESHOLD_PX = 42;
const DEADLINE_CARD_LIMIT = 6;
const REGION_CARD_LIMIT = 8;

export function isProfileComplete(profile: Profile) {
  const regionCount = profile.preferredRegions?.length ?? 0;
  return (
    regionCount >= 1 &&
    regionCount <= 3 &&
    Boolean(profile.style?.trim()) &&
    Boolean(profile.budget?.trim())
  );
}

export function HomePage() {
  const { currentUser, profile } = useSession();
  const dismissalKey = currentUser
    ? `${PROFILE_PROMPT_DISMISSAL_PREFIX}${currentUser.id}`
    : null;
  const [isProfilePromptDismissed, setIsProfilePromptDismissed] =
    useState(false);
  const {
    data: policies,
    error: policiesError,
    isLoading: policiesLoading,
  } = useAsyncResource(() => appDataApi.listPolicies(), []);
  useEffect(() => {
    setIsProfilePromptDismissed(
      dismissalKey
        ? window.sessionStorage.getItem(dismissalKey) === "1"
        : false,
    );
  }, [dismissalKey]);
  const name = currentUser?.nickname ?? "여행자";
  /* 관심 지역 정책이 있으면 그것만, 없으면 전체 지역 정책을 마감순으로 - 전국은 아래 한 줄 카드 몫. */
  const deadlinePick = useMemo(
    () =>
      getHomeBenefitPolicies(
        policies,
        Number.POSITIVE_INFINITY,
        profile.preferredRegions,
      ),
    [policies, profile.preferredRegions],
  );
  const deadlineGroups = useMemo(
    () =>
      groupByProgramInListOrder(deadlinePick.policies).slice(
        0,
        DEADLINE_CARD_LIMIT,
      ),
    [deadlinePick],
  );
  const nationwidePolicies = getNationwideHomePolicies(policies);
  const regionCounts = useMemo(
    () => countRegionalPolicies(policies),
    [policies],
  );
  const topRegions = Object.entries(regionCounts)
    .sort((left, right) => right[1] - left[1])
    .slice(0, REGION_CARD_LIMIT);
  const closingThisWeek = (policies ?? []).filter((policy) => {
    const days = daysUntilPolicyDeadline(policy.deadline);
    return days !== null && days >= 0 && days <= 7;
  }).length;
  const preferredAiRegions = useMemo(
    () =>
      Array.from(
        new Set(
          profile.preferredRegions
            ?.map((region) => region.trim())
            .filter(Boolean) ?? [],
        ),
      ),
    [profile.preferredRegions],
  );
  const { data: aiRegionRecommendations } = useAsyncResource(
    () =>
      preferredAiRegions.length > 0
        ? appDataApi.listRegionRecommendations({
            style: profile.style,
            preferredRegions: preferredAiRegions,
            limit: 3,
          })
        : Promise.resolve([]),
    [preferredAiRegions.join(","), profile.style],
  );
  const aiRegionCards = useMemo(
    () =>
      buildPreferredAiCards(
        preferredAiRegions,
        aiRegionRecommendations,
        profile.style,
      ),
    [preferredAiRegions, profile.style, aiRegionRecommendations],
  );
  const avatarLabel = name.trim().slice(0, 1).toUpperCase() || "T";
  const shouldShowProfilePrompt = Boolean(
    currentUser && !isProfileComplete(profile) && !isProfilePromptDismissed,
  );
  const dismissProfilePrompt = () => {
    if (dismissalKey) window.sessionStorage.setItem(dismissalKey, "1");
    setIsProfilePromptDismissed(true);
  };

  return (
    <section className="screen with-tabs prototype-app-screen prototype-home-screen">
      <div className="prototype-status-spacer" aria-hidden="true" />
      <div className="prototype-home-search-row">
        <Link className="prototype-home-search-pill" to="/policies">
          <Search size={15} />
          어디로 떠나세요?
        </Link>
        <Link
          className="prototype-home-avatar"
          to="/mypage"
          aria-label="마이페이지"
        >
          {avatarLabel}
        </Link>
      </div>

      <div className="prototype-home-greeting">
        <h2>안녕, {name}님</h2>
        {policies && (
          <p>
            지금 받을 수 있는 혜택 <b>{policies.length}건</b>
            {closingThisWeek > 0 && (
              <>
                {" "}
                · 이번 주 마감{" "}
                <b className="home-urgent">{closingThisWeek}건</b>
              </>
            )}
          </p>
        )}
      </div>

      {/* 가운데 뜨는 창은 홈을 가렸다. 닫을 수 있는 한 줄로 두고, 닫으면 이번 세션 동안 안 뜬다. */}
      {shouldShowProfilePrompt && (
        <section className="home-banner" aria-label="프로필 설정 안내">
          <Link className="home-banner-go" to="/profile-setup?redirect=/home">
            <b>관심 지역·취향·예산을 정하면 추천이 정확해져요</b>
            <span>설정하기 ›</span>
          </Link>
          <button
            aria-label="프로필 설정 안내 닫기"
            className="home-banner-close"
            onClick={dismissProfilePrompt}
            type="button"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </section>
      )}

      {policiesLoading && <LoadingState label="혜택을 불러오는 중입니다" />}
      {policiesError && (
        <ErrorState title="혜택을 불러오지 못했어요" message={policiesError} />
      )}

      {policies && (
        <>
          <section className="home-section" aria-label={deadlinePick.title}>
            <HomeSectionHeader
              title={deadlinePick.title}
              actionLabel="전체 보기"
              to="/policies"
            />
            {deadlineGroups.length > 0 ? (
              <ul className="home-row" aria-label={`${deadlinePick.title} 목록`}>
                {deadlineGroups.map((group) => (
                  <li key={group.key}>
                    <DeadlineCard group={group} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="home-empty">아직 보여 드릴 지역 혜택이 없어요.</p>
            )}
          </section>

          {topRegions.length > 0 && (
            <section className="home-section" aria-label="혜택이 많은 지역">
              <HomeSectionHeader title="혜택이 많은 지역" />
              <ul className="home-row">
                <li>
                  <Link className="home-map-card" to="/policies">
                    <HomeRegionMap counts={regionCounts} />
                    <span>
                      <b>
                        지도로 보기 <span aria-hidden="true">›</span>
                      </b>
                      <i>17개 시도 혜택 수</i>
                    </span>
                  </Link>
                </li>
                {topRegions.map(([region, count]) => (
                  <li key={region}>
                    <Link
                      className="home-region-card"
                      to={`/policies?${new URLSearchParams({ place: region, sheet: "1" })}`}
                    >
                      <img
                        alt=""
                        className="home-region-photo"
                        loading="lazy"
                        src={REGION_PHOTOS[region]}
                      />
                      <b>{region}</b>
                      <i>혜택 {count}건</i>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {nationwidePolicies.length > 0 && (
            <NationwideLineCard policies={nationwidePolicies} />
          )}
        </>
      )}

      {/* 일정 만들기 자리. 관심 지역이 있으면 그 지역 코스 카드, 없으면 한 줄 카드 하나 -
          예전 기본 카드의 '숙소 포함·맛집 포함' 말풍선은 근거 없는 약속이라 뺐다. */}
      {aiRegionCards.length > 0 ? (
        <>
          <div className="prototype-home-ai-title">AI 추천 맞춤 일정</div>
          {aiRegionCards.length > 1 ? (
            <PreferredAiCarousel cards={aiRegionCards} />
          ) : (
            <div className="prototype-home-ai-single">
              <AiRecommendationCard {...aiRegionCards[0]} />
            </div>
          )}
        </>
      ) : (
        <Link className="home-line-card home-trip-line" to="/trips/new">
          <BenefitTile kind="trip" />
          <span className="home-line-copy">
            <b>여행 일정 만들기</b>
            <i>일정 지역에서 쓸 수 있는 혜택을 함께 보여 줘요</i>
          </span>
          <span className="home-line-go" aria-hidden="true">
            ›
          </span>
        </Link>
      )}
    </section>
  );
}

type DeadlineGroup = { key: string; items: Policy[] };

/* 지명만 다른 같은 사업([합천]·[강진] 대한민국 반값여행)은 한 장으로 묶는다. 제목이 반복되던 자리다.
   들어온 순서(마감순)를 지키므로 묶음 순서도 가장 빠른 마감순이 된다. */
function groupByProgramInListOrder(policies: Policy[]): DeadlineGroup[] {
  const groups = new Map<string, Policy[]>();
  for (const policy of policies) {
    const key = programOf(policy).replace(/^\d{4}\s+/, "");
    groups.set(key, [...(groups.get(key) ?? []), policy]);
  }
  return Array.from(groups, ([key, items]) => ({ key, items }));
}

function DeadlineCard({ group }: { group: DeadlineGroup }) {
  const [first] = group.items;
  const soonest = group.items.filter(
    (policy) => policy.deadline === first.deadline,
  );
  const shown = soonest
    .slice(0, 2)
    .map((policy) => cityOf(policy) ?? policy.region);
  const rest = group.items.length - shown.length;
  const where = shown.join(" · ") + (rest > 0 ? ` 외 ${rest}곳` : "");
  /* 묶음 안 문구가 모두 같을 때만 싣는다 - 첫 곳 금액이 묶음 전체 금액처럼 읽히면 안 된다. */
  const summary = group.items.every(
    (policy) => policy.cardSummary === first.cardSummary,
  )
    ? first.cardSummary
    : null;
  const days = daysUntilPolicyDeadline(first.deadline);
  const tone =
    days === null ? "later" : days <= 7 ? "urgent" : days <= 30 ? "soon" : "later";
  // ponytail: 묶음도 마감이 가장 빠른 곳의 상세로 보낸다. 정책 탭에 사업 검색 주소가 생기면 그리로.
  return (
    <Link className="home-deadline-card" to={`/policies/${first.slug}`}>
      <BenefitTile kind={benefitTypeOf(first)} size="sm" />
      <span className={`home-deadline-badge ${tone}`}>
        {formatPolicyDeadlineTag(first)}
      </span>
      <strong>{group.key}</strong>
      {summary && <span className="home-deadline-summary">{summary}</span>}
      <span className="home-deadline-where">{where}</span>
    </Link>
  );
}

/* 지역 사진 카드가 있는 17개 시도만 센다. 전국 정책은 모든 지역에 걸려 순위를 흐리므로 뺀다. */
function countRegionalPolicies(
  policies: Policy[] | null | undefined,
): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const policy of policies ?? []) {
    if (!(policy.region in REGION_PHOTOS)) continue;
    counts[policy.region] = (counts[policy.region] ?? 0) + 1;
  }
  return counts;
}

/* 정책 탭 지도로 가는 표지. 입체 없이 평평하게, 정책 탭 지도와 같은 여섯 단계로 칠한다(시안 bucket).
   viewBox 는 도안(koreaRegionShapes, 200x269 단위)에서 실제로 그려진 범위(x 60~199, y 2~245)다. */
const HOME_MAP_REGIONS = KOREA_REGION_SHAPES.map((shape) => ({
  name: shape.name,
  d: shape.r
    .map(
      (ring) =>
        ring.reduce(
          (path, value, index) =>
            path + (index % 2 ? `,${value}` : `${index ? "L" : "M"}${value}`),
          "",
        ) + "Z",
    )
    .join(""),
}));

function mapLevel(count: number) {
  return count === 0 ? 0 : count <= 2 ? 1 : count <= 5 ? 2 : count <= 10 ? 3 : count <= 20 ? 4 : 5;
}

function HomeRegionMap({ counts }: { counts: Record<string, number> }) {
  return (
    <svg
      aria-hidden="true"
      className="home-map"
      focusable="false"
      viewBox="58 0 143 247"
    >
      {HOME_MAP_REGIONS.map((region) => (
        <path
          className={`lv${mapLevel(counts[region.name] ?? 0)}`}
          d={region.d}
          key={region.name}
        />
      ))}
    </svg>
  );
}

function NationwideLineCard({ policies }: { policies: Policy[] }) {
  const kinds = Array.from(
    new Set(
      policies.map((policy) => BENEFIT_TYPES[benefitTypeOf(policy)].label),
    ),
  )
    .slice(0, 4)
    .join(" · ");
  return (
    <Link
      className="home-line-card"
      to={`/policies?region=${NATIONWIDE_REGION}`}
    >
      <BenefitTile kind="nation" />
      <span className="home-line-copy">
        <b>전국 공통 혜택 {policies.length}건</b>
        <i>어느 지역을 가도 쓸 수 있어요 · {kinds}</i>
      </span>
      <span className="home-line-go" aria-hidden="true">
        ›
      </span>
    </Link>
  );
}

type PreferredAiCard = {
  region: string;
  to: string;
  title: string;
  saving: string;
  detail: string;
  visual: AiRecommendationCardVisual;
};

function buildPreferredAiCards(
  preferredRegions: string[],
  recommendations: RegionRecommendation[] | null | undefined,
  style: string | null | undefined,
): PreferredAiCard[] {
  const recommendationByRegion = new Map(
    (recommendations ?? []).map((recommendation) => [
      recommendation.region,
      recommendation,
    ]),
  );
  const courseStyle = style?.trim() || "맞춤";
  return preferredRegions.map((region) => {
    const recommendation = recommendationByRegion.get(region);
    return {
      region,
      to: `/trips/new?region=${encodeURIComponent(region)}`,
      title: `${region} ${courseStyle} 코스 만들기`,
      saving:
        recommendation && recommendation.endingSoonCount > 0
          ? `마감 임박 ${recommendation.endingSoonCount}개`
          : recommendation
            ? `혜택 ${recommendation.policyCount}개`
            : "관심지역 맞춤 일정",
      detail: "관심지역으로 새 일정 만들기",
      visual: {
        avatar: "🤖",
        headline: `${region} 코스 만들까요?`,
        subline: recommendation?.reason ?? "혜택까지 반영해서 추천해요",
        chips: [
          { emoji: "🏨", label: "숙소 포함" },
          { emoji: "🍜", label: `${courseStyle} 취향` },
        ],
      },
    };
  });
}

function PreferredAiCarousel({ cards }: { cards: PreferredAiCard[] }) {
  const [position, setPosition] = useState(1);
  const [isSnapping, setIsSnapping] = useState(false);
  const dragStartX = useRef<number | null>(null);
  const slideCount = cards.length;
  const extendedCards = useMemo(
    () => [cards[slideCount - 1], ...cards, cards[0]],
    [cards, slideCount],
  );
  const activeIndex = normalizeCarouselIndex(position - 1, slideCount);
  const activeRegion = cards[activeIndex]?.region ?? "";

  useEffect(() => {
    setPosition(1);
    setIsSnapping(false);
  }, [cards]);

  const moveBy = (delta: number) => {
    setIsSnapping(false);
    setPosition((current) => current + delta);
  };
  const moveToPrevious = () => moveBy(-1);
  const moveToNext = () => moveBy(1);
  const handleTransitionEnd = () => {
    if (position === 0) {
      setIsSnapping(true);
      setPosition(slideCount);
      return;
    }
    if (position === slideCount + 1) {
      setIsSnapping(true);
      setPosition(1);
      return;
    }
    setIsSnapping(false);
  };
  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    dragStartX.current = event.clientX;
  };
  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (dragStartX.current === null) return;
    const distance = event.clientX - dragStartX.current;
    dragStartX.current = null;
    if (Math.abs(distance) < AI_CAROUSEL_SWIPE_THRESHOLD_PX) return;
    if (distance < 0) moveToNext();
    else moveToPrevious();
  };
  const cancelDrag = () => {
    dragStartX.current = null;
  };

  return (
    <div
      aria-label="관심지역 AI 추천 일정 카드"
      className="prototype-home-ai-carousel"
      data-active-region={activeRegion}
      role="group"
    >
      <button
        className="prototype-home-ai-carousel-control previous"
        type="button"
        onClick={moveToPrevious}
        aria-label="이전 관심지역 일정"
      >
        ‹
      </button>
      <div
        className="prototype-home-ai-carousel-viewport"
        onPointerCancel={cancelDrag}
        onPointerDown={handlePointerDown}
        onPointerLeave={cancelDrag}
        onPointerUp={handlePointerUp}
      >
        <div
          className="prototype-home-ai-carousel-track"
          data-snapping={isSnapping ? "true" : "false"}
          onTransitionEnd={handleTransitionEnd}
          style={{ "--carousel-position": position } as CSSProperties}
        >
          {extendedCards.map((card, index) => (
            <div
              className="prototype-home-ai-slide"
              data-carousel-clone={
                index === 0 || index === extendedCards.length - 1
                  ? "true"
                  : undefined
              }
              key={`${card.region}-${index}`}
              aria-hidden={index === 0 || index === extendedCards.length - 1}
            >
              <AiRecommendationCard
                {...card}
                tabIndex={
                  index === 0 || index === extendedCards.length - 1
                    ? -1
                    : undefined
                }
              />
            </div>
          ))}
        </div>
      </div>
      <button
        className="prototype-home-ai-carousel-control next"
        type="button"
        onClick={moveToNext}
        aria-label="다음 관심지역 일정"
      >
        ›
      </button>
      <div className="prototype-home-ai-carousel-dots" aria-hidden="true">
        {cards.map((card, index) => (
          <span
            key={card.region}
            className={index === activeIndex ? "active" : undefined}
          />
        ))}
      </div>
    </div>
  );
}

function normalizeCarouselIndex(index: number, length: number) {
  return ((index % length) + length) % length;
}
