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
import { HomeSectionHeader } from "../components/patterns";
import { ErrorState, LoadingState } from "../components/ui";
import {
  getFeaturedPolicy,
  getHomeBenefitPolicies,
  getHomePolicyIcon,
} from "../data/displayConfig";
import { dday } from "../utils";

const PROFILE_PROMPT_DISMISSAL_PREFIX =
  "travel-hunter-profile-completion-dismissed:";
const AI_CAROUSEL_SWIPE_THRESHOLD_PX = 42;
const HOME_POLICY_CONDITION_FALLBACK = "조건 확인 필요";
const PHONE_ONLY_CONDITION_PATTERN = /^\s*(?:문의전화|문의|전화|tel|contact|고객센터|운영사무국)?\s*[:：-]?\s*(?:\+?\d[\d\s().-]{5,}\d)\s*$/i;
const PHONE_IN_CONDITION_PATTERN = /(?:\+?\d[\d\s().-]{5,}\d)/;
const CONTACT_OR_NOTICE_CONDITION_PATTERN =
  /문의|전화|tel|contact|고객센터|운영사무국|공식|공고|안내|확인|서류|캡처|캡쳐|증빙/;
const OFFICIAL_CONFIRMATION_ONLY_CONDITION_PATTERN =
  /^\s*(?:공식|공고|상세)?\s*(?:혜택|정책)?\s*(?:안내|조건|내용)?\s*(?:에서)?\s*(?:확인(?:하세요|해 주세요)?|참고(?:하세요|해 주세요)?)\s*[.!。]?\s*$/;
const CARD_SUITABLE_CONDITION_PATTERN =
  /조건|인증|방문|결제|가맹점|지역화폐|제로페이|상품|예약|쿠폰|할인|환급|지원|사용|이용|대상|숙박|식사|체험|국내|여행자|주민|거주|청년|가족|관광객|(?:만\s*)?\d+\s*세/;
const CONCRETE_CARD_CONDITION_PATTERN =
  /인증|방문|결제|가맹점|지역화폐|제로페이|상품|예약|쿠폰|할인|환급|사용|이용|대상|숙박|식사|체험|국내|여행자|주민|거주|청년|가족|관광객|(?:만\s*)?\d+\s*세/;

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
  const featuredPolicy = getFeaturedPolicy(policies);
  const weeklyBenefitPolicies = getHomeBenefitPolicies(policies, 3);
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
  const fallbackAiStyle = profile.style ?? "맞춤";
  const aiCardTo = "/trips/new";
  const aiCardTitle = `${fallbackAiStyle} 코스 만들기`;
  const shouldShowProfilePrompt = Boolean(
    currentUser && !isProfileComplete(profile) && !isProfilePromptDismissed,
  );
  const dismissProfilePrompt = () => {
    if (dismissalKey) window.sessionStorage.setItem(dismissalKey, "1");
    setIsProfilePromptDismissed(true);
  };
  const aiCardVisual: AiRecommendationCardVisual = {
    avatar: "🤖",
    headline: "새 일정 만들까요?",
    subline: "혜택까지 반영해서 추천해요",
    chips: [
      { emoji: "🏨", label: "숙소 포함" },
      { emoji: "🍜", label: "맛집 포함" },
    ],
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
        <p>이번 주 놓치면 아쉬운 혜택이 있어요</p>
      </div>

      {policiesLoading && <LoadingState label="혜택을 불러오는 중입니다" />}
      {policiesError && (
        <ErrorState title="혜택을 불러오지 못했어요" message={policiesError} />
      )}
      {featuredPolicy && (
        <Link
          className="prototype-home-hero"
          to={`/policies/${featuredPolicy.slug}`}
        >
          <span className="prototype-home-hero-accent" aria-hidden="true">
            ★
          </span>
          <span className="prototype-home-hero-copy">
            <span className="prototype-home-hero-kicker">이번 주 인기 정책</span>
            <strong>{featuredPolicy.title}</strong>
            <span className="prototype-home-hero-description">
              {featuredPolicy.amount}
            </span>
            <span className="prototype-home-hero-meta">
              <span>{featuredPolicy.region}</span>
              <span>{dday(featuredPolicy.deadline)}</span>
            </span>
          </span>
          <span className="prototype-home-hero-cta">자세히 보기 →</span>
        </Link>
      )}

      <HomeSectionHeader
        title="이번 주 혜택"
        actionLabel="더보기"
        to="/policies"
      />
      <WeeklyPolicyList policies={weeklyBenefitPolicies} />

      <div className="prototype-home-ai-title">AI 추천 맞춤 일정</div>
      {aiRegionCards.length > 1 ? (
        <PreferredAiCarousel cards={aiRegionCards} />
      ) : aiRegionCards.length === 1 ? (
        <div className="prototype-home-ai-single">
          <AiRecommendationCard {...aiRegionCards[0]} />
        </div>
      ) : (
        <AiRecommendationCard
          to={aiCardTo}
          title={aiCardTitle}
          saving="정책과 일정을 함께 추천"
          detail="새 일정 만들기"
          visual={aiCardVisual}
        />
      )}

      {shouldShowProfilePrompt && (
        <div
          className="profile-completion-backdrop"
          role="presentation"
          onMouseDown={dismissProfilePrompt}
        >
          <section
            aria-describedby="profile-completion-body"
            aria-labelledby="profile-completion-title"
            aria-modal="true"
            className="profile-completion-dialog"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="profile-completion-dialog-head">
              <div className="profile-completion-icon" aria-hidden="true">
                🎯
              </div>
              <button
                aria-label="프로필 설정 안내 닫기"
                className="profile-completion-close"
                onClick={dismissProfilePrompt}
                type="button"
              >
                <X size={18} />
              </button>
            </div>
            <div className="profile-completion-copy">
              <h2 id="profile-completion-title">프로필 설정을 완료해 주세요</h2>
              <p id="profile-completion-body">
                관심 지역, 여행 스타일, 예산을 설정하면 홈 추천이 더 정확해져요.
              </p>
            </div>
            <div className="profile-completion-actions">
              <Link
                className="btn primary full profile-completion-primary"
                to="/profile-setup?redirect=/home"
              >
                설정하러 가기
              </Link>
              <button
                className="profile-completion-later"
                type="button"
                onClick={dismissProfilePrompt}
              >
                나중에
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function WeeklyPolicyList({ policies }: { policies: Policy[] }) {
  return (
    <div className="prototype-home-policy-list-wrap">
      <div
        className="prototype-home-policy-list"
        aria-label="이번 주 혜택 정책 목록"
      >
        {policies.map((policy) => (
          <PrototypePolicyCard key={policy.id} policy={policy} />
        ))}
      </div>
    </div>
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

function PrototypePolicyCard({ policy }: { policy: Policy }) {
  return (
    <Link
      className="prototype-home-policy-card"
      draggable={false}
      to={`/policies/${policy.slug}`}
    >
      <div className="prototype-home-policy-card-head">
        <div className="prototype-home-policy-label" aria-hidden="true">
          {getHomePolicyIcon(policy)}
        </div>
        <em className="prototype-home-policy-category">{policy.category}</em>
      </div>
      <div className="prototype-home-policy-card-copy">
        <strong>{policy.title}</strong>
        <p className="prototype-home-policy-summary">
          {getPolicyCardSummary(policy)}
        </p>
      </div>
      <div className="prototype-home-policy-card-meta">
        <span className="prototype-home-policy-schedule">
          신청 마감 {formatPolicyCardDeadline(policy.deadline)} · {dday(policy.deadline)}
        </span>
        <span className="prototype-home-policy-condition">
          조건: {getPolicyCardCondition(policy)}
        </span>
      </div>
      <small>
        <span>{policy.amount}</span>
        <span>{dday(policy.deadline)}</span>
      </small>
    </Link>
  );
}

function getPolicyCardSummary(policy: Policy) {
  const summary = policy.summary.trim();
  if (summary) return summary;
  return `${policy.amount || "혜택"}을 받을 수 있는 정책입니다.`;
}

function getPolicyCardCondition(policy: Policy) {
  const condition = policy.requirements
    .map((requirement) => requirement.trim())
    .find(isHomePolicyCardConditionCandidate);
  if (!condition) return HOME_POLICY_CONDITION_FALLBACK;
  return summarizeHomePolicyCondition(condition);
}

function isHomePolicyCardConditionCandidate(condition: string) {
  if (!condition) return false;
  if (PHONE_ONLY_CONDITION_PATTERN.test(condition)) return false;
  if (PHONE_IN_CONDITION_PATTERN.test(condition)) return false;
  if (OFFICIAL_CONFIRMATION_ONLY_CONDITION_PATTERN.test(condition)) return false;
  if (CONTACT_OR_NOTICE_CONDITION_PATTERN.test(condition)) {
    return CONCRETE_CARD_CONDITION_PATTERN.test(condition);
  }
  return CARD_SUITABLE_CONDITION_PATTERN.test(condition);
}

function summarizeHomePolicyCondition(condition: string) {
  const normalized = condition.replace(/\s+/g, " ").trim();
  const stayDiscount = normalized.match(
    /(\d+만원\s*(?:미만|이상)).*?(\d+만원)\s*할인/,
  );
  if (stayDiscount) return `${stayDiscount[1]} 숙박 ${stayDiscount[2]} 할인`;

  const compact = normalized
    .replace(/국내\s*/g, "")
    .replace(/숙박상품/g, "숙박")
    .replace(/예약\s*시/g, "")
    .replace(/[()]/g, "")
    .replace(/\s*:\s*/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (compact.length <= 26) return compact;
  return `${compact.slice(0, 25).trim()}…`;
}

function formatPolicyCardDeadline(deadline: string) {
  const date = new Date(deadline);
  if (Number.isNaN(date.getTime())) return "상시";
  return `${date.getMonth() + 1}.${date.getDate()}`;
}

function getRecommendationSaving(recommendation: RegionRecommendation) {
  if (recommendation.endingSoonCount > 0) {
    return `마감 임박 ${recommendation.endingSoonCount}개`;
  }
  return `혜택 ${recommendation.policyCount}개`;
}
