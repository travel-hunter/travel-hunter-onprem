import { MapPin, Search, X } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import {
  appDataApi,
  type Policy,
  type PolicyPhoto,
  type Profile,
  type RegionRecommendation,
} from "../api";
import { mediaUrl } from "../api/client";
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
import { HomeHeroBanner, type HomeHeroSlide } from "../components/HomeHeroBanner";
import { HERO_PHOTOS, heroThemeOf } from "../components/heroPhotos";
import { KOREA_REGION_SHAPES } from "../components/map/koreaRegionShapes";
import { HomeSectionHeader } from "../components/patterns";
import { useProfileEditor } from "../components/ProfileEditSheet";
import { ErrorState, LoadingState } from "../components/ui";
import {
  getClosingSoonHomePolicies,
  getInterestRegionHomePolicies,
  getNationwideHomePolicies,
} from "../data/displayConfig";
import {
  BROWSE_FILTERS,
  REGION_FULL_NAMES,
  deadlineChip,
  programName,
  regionSummary,
} from "../components/map/policyBrowse";
import { policyListText, PROGRAM_GROUP_COPY } from "../components/map/policyListText";
import {
  NATIONWIDE_REGION,
  cityOf,
} from "../utils/policyPrograms";
import { daysUntilPolicyDeadline, isDigitalTourismResidentCardPolicy } from "../utils";
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
  const profileEditor = useProfileEditor(); // '내 관심 지역 혜택'의 '관심 지역 바꾸기' - 내 정보와 같은 편집 창
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
  /* 마감이 가까운 혜택(시안 v40, 전국 포함) 다음에 내 관심 지역 혜택 - 두 칸 다 사업별 한 장, 마감순 */
  const closingGroups = useMemo(
    () =>
      groupByProgramInListOrder(getClosingSoonHomePolicies(policies)).slice(
        0,
        DEADLINE_CARD_LIMIT,
      ),
    [policies],
  );
  const hasInterestRegions = (profile.preferredRegions ?? []).some((region) =>
    region.trim(),
  );
  const interestGroups = useMemo(
    () =>
      groupByProgramInListOrder(
        getInterestRegionHomePolicies(policies, profile.preferredRegions),
      ).slice(0, DEADLINE_CARD_LIMIT),
    [policies, profile.preferredRegions],
  );
  const nationwidePolicies = useMemo(() => getNationwideHomePolicies(policies), [policies]);
  const regionCounts = useMemo(
    () => countRegionalPolicies(policies),
    [policies],
  );
  const placeCards = useMemo(
    () => pickPlaceCards(policies ?? []).slice(0, REGION_CARD_LIMIT),
    [policies],
  );
  const heroSlides = useMemo(
    () => buildHeroSlides(closingGroups, regionCounts, policies ?? [], nationwidePolicies),
    [closingGroups, regionCounts, policies, nationwidePolicies],
  );
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
    /* desktop-wide: 1024px 이상에서 앱 틀을 넓히고(app.css) 홈을 두 단 격자로 편다(home.css). 좁은 화면에서는 아무 일도 안 한다. */
    <section className="screen with-tabs prototype-app-screen prototype-home-screen desktop-wide">
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

      {policies && <HomeHeroBanner slides={heroSlides} />}

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
          <DeadlineSection
            title="마감이 가까운 혜택"
            groups={closingGroups}
            empty="곧 마감되는 혜택이 없어요."
          />
          {/* 관심 지역을 아직 안 골랐으면 위 배너가 고르기를 권한다 */}
          {hasInterestRegions && (
            <DeadlineSection
              title="내 관심 지역 혜택"
              groups={interestGroups}
              empty="관심 지역에 아직 모아 둔 혜택이 없어요."
              action={
                <button className="home-section-action" onClick={profileEditor.open} type="button">
                  관심 지역 바꾸기
                </button>
              }
            />
          )}

          {placeCards.length > 0 && (
            <section className="home-section" aria-label="혜택이 많은 지역">
              <HomeSectionHeader title="혜택이 많은 지역" />
              <ul className="home-row home-row-regions">
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
                {placeCards.map((card) => (
                  <li key={card.key}>
                    <PlaceCard card={card} />
                  </li>
                ))}
              </ul>
              <PhotoCredit cards={placeCards} />
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
        /* 넓은 화면에서 전국 공통 카드 옆 한 칸을 차지하도록 제목과 카드를 한 덩어리로 묶는다(좁은 화면에서는 모양 없음) */
        <div className="home-ai-block">
          <div className="prototype-home-ai-title">AI 추천 맞춤 일정</div>
          {aiRegionCards.length > 1 ? (
            <PreferredAiCarousel cards={aiRegionCards} />
          ) : (
            <div className="prototype-home-ai-single">
              <AiRecommendationCard {...aiRegionCards[0]} />
            </div>
          )}
        </div>
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
      {profileEditor.sheet}
    </section>
  );
}

type DeadlineGroup = { key: string; items: Policy[] };

/* 지명만 다른 같은 사업([합천]·[강진] 대한민국 반값여행)은 한 장으로 묶는다. 제목이 반복되던 자리다.
   들어온 순서(마감순)를 지키므로 묶음 순서도 가장 빠른 마감순이 된다. */
function groupByProgramInListOrder(policies: Policy[]): DeadlineGroup[] {
  const groups = new Map<string, Policy[]>();
  for (const policy of policies) {
    const key = programName(policy); // 정책 탭 사업 주소(prog)와 같은 이름
    groups.set(key, [...(groups.get(key) ?? []), policy]);
  }
  return Array.from(groups, ([key, items]) => ({ key, items }));
}

function DeadlineSection({
  title,
  groups,
  empty,
  action,
}: {
  title: string;
  groups: DeadlineGroup[];
  empty: string;
  action?: ReactNode; // 머리 오른쪽(없으면 '전체 보기')
}) {
  return (
    <section className="home-section" aria-label={title}>
      {action ? (
        <div className="ds-section-header">
          <h3>{title}</h3>
          {action}
        </div>
      ) : (
        <HomeSectionHeader title={title} actionLabel="전체 보기" to="/policies" />
      )}
      {groups.length > 0 ? (
        <ul className="home-row home-row-deadline" aria-label={`${title} 목록`}>
          {groups.map((group) => (
            <li key={group.key}>
              <DeadlineCard group={group} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="home-empty">{empty}</p>
      )}
    </section>
  );
}

/* 받는 것 한 줄은 정책 탭 목록과 같은 출처(policyListText). 여러 곳 묶음은 사업 공통 문구가 있으면 그것,
   없으면 모두 같을 때만 싣는다 - 첫 곳 금액이 묶음 전체 금액처럼 읽히면 안 된다. */
function groupHead(group: DeadlineGroup): string | null {
  const texts = group.items.map(policyListText);
  const copy = group.items.length > 1 ? PROGRAM_GROUP_COPY[group.key] : undefined;
  const partners = texts.reduce((sum, text) => sum + text.partners, 0);
  if (copy && (partners > 0 || !copy.head.includes("{sum}"))) {
    return copy.head.replace("{sum}", partners.toLocaleString("ko-KR"));
  }
  return texts.every((text) => text.head === texts[0].head) ? texts[0].head || null : null;
}

/* 마감 카드와 배너 첫 장이 같이 쓰는 한 묶음의 사실: 어디(가장 빠른 마감의 두 곳 + 외 N곳), 받는 것, 칩, 누르면 갈 곳 */
function deadlineGroupFacts(group: DeadlineGroup) {
  const [first] = group.items;
  const soonest = group.items.filter(
    (policy) => policy.deadline === first.deadline,
  );
  const shown = soonest
    .slice(0, 2)
    .map((policy) => cityOf(policy) ?? (policy.region === NATIONWIDE_REGION ? "전국 공통" : policy.region));
  const rest = group.items.length - shown.length;
  const where = shown.join(" · ") + (rest > 0 ? ` 외 ${rest}곳` : "");
  const head = groupHead(group);
  /* 칩은 정책 탭 목록과 같은 규칙(시안 v40): 오늘 마감·D-5·10.31 마감, 주민증은 '상시' */
  const chip = deadlineChip(first);
  /* 한 곳이면 그 상세로, 여러 곳 묶음은 정책 탭의 그 사업으로(시안 - 지도가 사업이 있는 곳을 칠한다). 한 지역 안의 묶음이면 그 지역으로 좁힌다 */
  const regions = new Set(group.items.map((policy) => policy.region));
  const to =
    group.items.length === 1
      ? `/policies/${first.slug}`
      : `/policies?${new URLSearchParams({
          ...(regions.size === 1 ? { place: first.region } : {}),
          prog: group.key,
        })}`;
  return { first, where, head, chip, to };
}

function DeadlineCard({ group }: { group: DeadlineGroup }) {
  const { first, where, head, chip, to } = deadlineGroupFacts(group);
  return (
    <Link className="home-deadline-card" to={to}>
      <BenefitTile kind={benefitTypeOf(first)} size="sm" />
      <span className={`home-deadline-badge ${chip.tone}`}>{chip.text}</span>
      <strong>{group.key}</strong>
      {head && <span className="home-deadline-summary">{head}</span>}
      <span className="home-deadline-where">{where}</span>
    </Link>
  );
}

/* 17개 시도만 센다(미니 지도·배너). 전국 정책은 모든 지역에 걸려 순위를 흐리므로 뺀다. */
function countRegionalPolicies(
  policies: Policy[] | null | undefined,
): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const policy of policies ?? []) {
    if (!(policy.region in REGION_FULL_NAMES)) continue;
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

/* 홈 맨 위 배너의 장들. 넣을 내용은 개발서버에서 보고 정할 임시(2026-09-30) - 지금 데이터로만 만든다:
   가장 가까운 마감 · 혜택이 가장 많은 지역 · 전국 공통. 내용을 바꿀 때는 이 함수만 고친다.
   장 바탕 사진은 장의 성격으로 고른다(heroPhotos.ts) - 마감 장은 혜택 종류, 지역 장은 그 도, 전국 장은 교통. */
function buildHeroSlides(
  closingGroups: DeadlineGroup[],
  regionCounts: Record<string, number>,
  policies: Policy[],
  nationwide: Policy[],
): HomeHeroSlide[] {
  const slides: HomeHeroSlide[] = [];
  if (closingGroups[0]) {
    const { first, where, head, chip, to } = deadlineGroupFacts(closingGroups[0]);
    const kind = benefitTypeOf(first);
    slides.push({
      key: "closing",
      to,
      family: BENEFIT_TYPES[kind].family,
      icon: <BenefitTile kind={kind} />,
      eyebrow: (
        <>
          <span className={`home-deadline-badge ${chip.tone}`}>{chip.text}</span>
          <span>{where}</span>
        </>
      ),
      title: closingGroups[0].key,
      sub: head ?? BENEFIT_TYPES[kind].label,
      photo: HERO_PHOTOS[`theme:${heroThemeOf(kind)}`],
    });
  }
  const [top] = Object.entries(regionCounts).sort((left, right) => right[1] - left[1]);
  if (top) {
    const summary = regionSummary(policies, top[0]);
    const label = (key: string) => BROWSE_FILTERS.find((filter) => filter.key === key)?.label ?? key;
    slides.push({
      key: "region",
      to: `/policies?${new URLSearchParams({ place: top[0], sheet: "1" })}`,
      family: "place",
      icon: (
        <span className="home-hero-pin" aria-hidden="true">
          <MapPin size={26} />
        </span>
      ),
      eyebrow: <span>혜택이 가장 많은 지역</span>,
      title: `${summary.fullName} ${top[1]}건`,
      sub: summary.kinds.map((kind) => `${label(kind.key)} ${kind.count}`).join(" · "),
      photo: HERO_PHOTOS[`region:${top[0]}`],
    });
  }
  if (nationwide.length > 0) {
    slides.push({
      key: "nation",
      to: `/policies?place=${NATIONWIDE_REGION}`,
      family: "move",
      icon: <BenefitTile kind="nation" />,
      eyebrow: <span>어느 지역을 가도 쓸 수 있어요</span>,
      title: `전국 공통 혜택 ${nationwide.length}건`,
      sub: Array.from(new Set(nationwide.map((policy) => BENEFIT_TYPES[benefitTypeOf(policy)].label)))
        .slice(0, 4)
        .join(" · "),
      photo: HERO_PHOTOS["theme:move"],
    });
  }
  return slides;
}

type PlaceCardData = {
  key: string;
  region: string;
  place: string;
  count: number;
  lead: Policy;
  soonest: string; // 순위용 - 안 지난 가장 빠른 마감(대표 혜택과 따로. 없으면 "9999")
  photo: PolicyPhoto | null;
};

const isOpenDated = (policy: Policy) =>
  !isDigitalTourismResidentCardPolicy(policy) && (daysUntilPolicyDeadline(policy.deadline) ?? -1) >= 0;

/* 혜택이 많은 시군(시안 v43~44): 혜택 수 → 안 지난 가장 빠른 마감 → 이름. 전국 정책은 모든 곳에 걸려 순위를 흐리므로 뺀다.
   누르면 그 시군의 대표 혜택 상세 - 나머지는 상세의 '같은 곳 다른 혜택'. 대표는 그 시군 전용 안내가 있는 혜택 먼저(시안 v49,
   2026-10-01 사용자 결정): 공식 안내 주소를 다른 시군과 나눠 쓰지 않는 혜택(숙박세일은 32곳이 첫 화면 하나를 나눠 써서 빠지고,
   반값여행·주민증은 시군마다 따로) 중 안 지난 가장 빠른 마감 → 전용 상시(주민증) → 전용이 없으면 안 지난 가장 빠른 마감 → 첫 혜택.
   사진은 그 시군만 쓰는 수집 사진. 도 대표 사진을 여러 시군이 나눠 쓰는 곳은 같은 사진이 되풀이되므로 혜택 그림으로 둔다. */
function pickPlaceCards(policies: Policy[]): PlaceCardData[] {
  const byPlace = new Map<string, Policy[]>();
  const placesByPhoto = new Map<string, Set<string>>();
  for (const policy of policies) {
    const place = cityOf(policy);
    if (!place || policy.region === NATIONWIDE_REGION) continue;
    const key = `${policy.region}|${place}`;
    byPlace.set(key, [...(byPlace.get(key) ?? []), policy]);
    if (policy.photo) {
      placesByPhoto.set(policy.photo.imageUrl, (placesByPhoto.get(policy.photo.imageUrl) ?? new Set()).add(key));
    }
  }
  const placesByUrl = new Map<string, Set<string>>();
  for (const [key, items] of byPlace) {
    for (const policy of items) {
      const url = policy.officialUrl;
      if (url) placesByUrl.set(url, (placesByUrl.get(url) ?? new Set()).add(key));
    }
  }
  const ownPage = (policy: Policy) => Boolean(policy.officialUrl && placesByUrl.get(policy.officialUrl)?.size === 1);
  const ownPhoto = (items: Policy[]) =>
    items.map((policy) => policy.photo).find((photo) => photo && placesByPhoto.get(photo.imageUrl)?.size === 1) ?? null;
  return Array.from(byPlace, ([key, items]) => {
    const dated = items.filter(isOpenDated).sort((left, right) => left.deadline.localeCompare(right.deadline));
    const [region, place] = key.split("|");
    const lead = dated.find(ownPage) ?? items.find((policy) => ownPage(policy) && isDigitalTourismResidentCardPolicy(policy)) ?? dated[0] ?? items[0];
    return { key, region, place, count: items.length, lead, soonest: dated[0]?.deadline ?? "9999", photo: ownPhoto(items) };
  }).sort(
    (left, right) =>
      right.count - left.count ||
      left.soonest.localeCompare(right.soonest) ||
      left.place.localeCompare(right.place, "ko"),
  );
}

function PlaceCard({ card }: { card: PlaceCardData }) {
  const [isBroken, setIsBroken] = useState(false);
  const kind = benefitTypeOf(card.lead);
  const photo = isBroken ? null : card.photo;
  return (
    <Link
      className={photo ? "home-region-card" : `home-region-card nophoto family-${BENEFIT_TYPES[kind].family}`}
      to={`/policies/${card.lead.slug}`}
    >
      {photo ? (
        /* 원본(940px)만 쓴다. TourAPI 축소판(thumbnailUrl)은 실제로 120×80 이라 300w 로 적어 두면 카드(232~362px)에서
           2.5~3배로 늘어나 깨져 보였다(10/1 실측) */
        <img
          alt=""
          className="home-region-photo"
          loading="lazy"
          onError={() => setIsBroken(true)}
          src={mediaUrl(photo.imageUrl)}
        />
      ) : (
        <BenefitTile kind={kind} />
      )}
      <b>{card.place}</b>
      <i>
        {card.region} · 혜택 {card.count}건
      </i>
      {/* 누르면 열리는 혜택 */}
      <i className="home-region-lead">
        {BENEFIT_TYPES[kind].label} · {deadlineChip(card.lead).text}
      </i>
    </Link>
  );
}

/* 공공누리 1유형 출처 표시 - 사진을 쓴 카드가 있으면 줄 아래 한 번 */
function PhotoCredit({ cards }: { cards: PlaceCardData[] }) {
  const credits = Array.from(new Set(cards.flatMap((card) => (card.photo ? [card.photo.attribution] : []))));
  return credits.length > 0 ? <p className="home-photo-credit">{credits.join(" · ")}</p> : null;
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
      to={`/policies?place=${NATIONWIDE_REGION}`}
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
