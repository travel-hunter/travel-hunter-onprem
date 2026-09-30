import { ChevronLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  appDataApi,
  type TravelAreaOption,
  type TravelAreaRecommendation,
} from "../../api";
import { useSession } from "../../app/session";
import { useAsyncResource } from "../../api/useAsyncResource";
import { getPreferenceIcon } from "../../components/preferenceDisplay";
import { Button, ErrorState, IconButton } from "../../components/ui";
import {
  tripCreatePrimaryRegions,
  tripCreatePrimaryRegionValues,
} from "../../data/displayConfig";
import {
  getDefaultTripDateRange,
  normalizeTripDateRange,
} from "../../utils/dateDefaults";
import { TripDateRangePicker } from "../../components/trip/TripDateRangePicker";
import { TripRegionSelector } from "../../components/trip/TripRegionSelector";
import { tripDateDayCount } from "../../utils/tripDateRange";

const TRIP_CREATE_TOTAL_STEPS = 2;
const broadTravelAreaRegions = new Set<string>(tripCreatePrimaryRegionValues);
const NO_TRAVEL_AREA_HEADING = "세부 지역 선택";
type TripCreateStep = 1 | 2;
type SelectedTravelArea = Pick<
  TravelAreaRecommendation,
  | "travelAreaId"
  | "travelAreaName"
  | "sido"
  | "includedCities"
  | "summary"
  | "tags"
>;

/* 선택기는 카탈로그의 TravelAreaOption 을 주고받고, 이 화면의 기존 로직은
   추천 API 의 TravelAreaRecommendation 을 쓴다. 둘을 오가는 얇은 어댑터다. */
function optionFromSelectedArea(
  area: SelectedTravelArea | null,
): TravelAreaOption | null {
  if (!area) return null;
  return {
    travelAreaId: area.travelAreaId,
    travelAreaName: area.travelAreaName,
    sido: area.sido,
    areaType: "recommended",
    includedCities: area.includedCities,
  };
}

function recommendationFromOption(
  option: TravelAreaOption,
): TravelAreaRecommendation {
  return {
    travelAreaId: option.travelAreaId,
    travelAreaName: option.travelAreaName,
    sido: option.sido,
    includedCities: option.includedCities,
    summary: "",
    tags: [],
    reason: "",
    policyCount: 0,
    localPolicyCount: 0,
    nationwidePolicyCount: 0,
    endingSoonCount: 0,
    estimatedValueKrw: 0,
    score: 0,
  };
}

function generatedTripTitle(region: string, dayCount: number | null): string {
  return `${region || "선택한 지역"} ${dayCount ?? 3}일 여행`;
}

function normalizeRegionParam(value: string | null): string | null {
  if (!value) return null;
  const normalized = value.trim();
  return normalized || null;
}

function normalizeTravelAreaIdParam(value: string | null): string | null {
  const normalized = value?.trim();
  return normalized || null;
}

/* 카탈로그(`GET /travel-areas`)에서만 나오는 id 다. 추천 API 는 구조상 이 계열을
   절대 돌려주지 않으므로, 추천 목록에 없다고 해서 지워서는 안 된다. */
function isCatalogTravelAreaId(travelAreaId: string): boolean {
  return /^(?:whole|admin):/.test(travelAreaId);
}

function isBroadTravelAreaRegion(
  region: string | null | undefined,
): region is string {
  return Boolean(region && broadTravelAreaRegions.has(region));
}

function toSelectedTravelArea(
  area: TravelAreaRecommendation,
): SelectedTravelArea {
  return {
    travelAreaId: area.travelAreaId,
    travelAreaName: area.travelAreaName,
    sido: area.sido,
    includedCities: area.includedCities,
    summary: area.summary,
    tags: area.tags,
  };
}

export function ItineraryCreatePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { profile, updateProfile, addPolicy } = useSession();
  const { data: profileOptions } = useAsyncResource(
    () => appDataApi.getProfileOptions(),
    [],
  );
  const policySlug = searchParams.get("policySlug") ?? undefined;
  const requestedTravelAreaId = normalizeTravelAreaIdParam(
    searchParams.get("travelAreaId"),
  );
  const requestedRegion = normalizeRegionParam(searchParams.get("region"));
  const requestedSido = normalizeRegionParam(searchParams.get("sido"));
  const linkablePolicySlug = policySlug;
  const defaultTripDatesRef = useRef(getDefaultTripDateRange());
  const defaultTripStartDate = defaultTripDatesRef.current.startDate;
  const defaultTripEndDate = defaultTripDatesRef.current.endDate;
  const ignoredRequestedTravelAreaIdRef = useRef<string | null>(null);
  const initialDayCount = tripDateDayCount(
    defaultTripStartDate,
    defaultTripEndDate,
  );
  const initialRegion = requestedRegion || profile.preferredRegions?.[0] || "제주";
  const isPolicyLinkedRegionEntry = Boolean(
    linkablePolicySlug && (requestedTravelAreaId || requestedRegion),
  );
  const [selectedRegionDraft, setSelectedRegionDraft] = useState(initialRegion);
  const [selectedTravelArea, setSelectedTravelArea] =
    useState<SelectedTravelArea | null>(null);
  const [travelAreaChoiceSido, setTravelAreaChoiceSido] = useState<
    string | null
  >(
    requestedTravelAreaId
      ? null
      : isBroadTravelAreaRegion(requestedRegion)
        ? requestedRegion
        : requestedSido ||
          (isBroadTravelAreaRegion(initialRegion) ? initialRegion : null),
  );
  const [travelAreaChoiceQuery, setTravelAreaChoiceQuery] = useState<
    string | null
  >(
    requestedTravelAreaId ||
      !requestedRegion ||
      isBroadTravelAreaRegion(requestedRegion)
      ? null
      : requestedRegion,
  );
  const [travelAreaRecommendations, setTravelAreaRecommendations] = useState<
    TravelAreaRecommendation[]
  >([]);
  const [isTravelAreaLoading, setIsTravelAreaLoading] = useState(
    isPolicyLinkedRegionEntry,
  );
  const [travelAreaError, setTravelAreaError] = useState("");
  const [step, setStep] = useState<TripCreateStep>(
    isPolicyLinkedRegionEntry ? 2 : 1,
  );
  const [isStyleModalOpen, setIsStyleModalOpen] = useState(false);
  const [styleDraft, setStyleDraft] = useState(profile.style ?? "");
  const [startDate, setStartDate] = useState(defaultTripStartDate);
  const [endDate, setEndDate] = useState(defaultTripEndDate);
  const [titleDraft, setTitleDraft] = useState(
    generatedTripTitle(initialRegion, initialDayCount),
  );
  const titleEditedByUserRef = useRef(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isCreationTakingLong, setIsCreationTakingLong] = useState(false);
  const [error, setError] = useState("");
  const selectedRegion =
    (selectedTravelArea?.travelAreaName ?? selectedRegionDraft.trim()) ||
    initialRegion;
  const selectedRegionButton = selectedTravelArea?.sido ?? selectedRegion;
  const requiresTravelAreaSelection = Boolean(
    requestedTravelAreaId || travelAreaChoiceSido || travelAreaChoiceQuery,
  );
  const isResolvingPolicyLinkedRegion =
    isPolicyLinkedRegionEntry && !selectedTravelArea && isTravelAreaLoading;
  const dayCount = tripDateDayCount(startDate, endDate);
  const dateRangeError =
    dayCount === null
      ? "첫날과 마지막 날을 선택하세요."
      : dayCount < 1
        ? "마지막 날은 첫날과 같거나 뒤여야 해요."
        : "";
  const linkedPolicyLabel = linkablePolicySlug
    ? linkablePolicySlug.startsWith("travelmonth-")
      ? "선택한 정책까지 일정에 연결할게요"
      : "선택한 정책을 새 일정에 연결할게요"
    : "";
  const canCreateTrip =
    Boolean(titleDraft.trim()) &&
    !dateRangeError &&
    Boolean(profile.style) &&
    !isResolvingPolicyLinkedRegion;
  const canProceed =
    step === 1
      ? Boolean(selectedRegion) &&
        (!requiresTravelAreaSelection || Boolean(selectedTravelArea))
      : canCreateTrip;
  const tripCreateActionHint = canProceed || isCreating
    ? ""
    : step === 1
      ? isTravelAreaLoading
        ? "세부 지역을 불러오는 중이에요."
        : requiresTravelAreaSelection && !selectedTravelArea
          ? "세부 지역을 선택해야 다음 단계로 이동할 수 있어요."
          : "지역을 선택해 주세요."
      : isResolvingPolicyLinkedRegion
        ? "세부 지역을 불러오는 중이에요."
        : !titleDraft.trim()
          ? "일정 제목을 입력해 주세요."
          : dateRangeError
            ? dateRangeError
            : !profile.style
              ? "코스 취향을 선택해야 일정 생성이 가능해요."
              : "";

  const syncTravelAreaSearchParams = (updates: {
    region?: string | null;
    travelAreaId?: string | null;
  }) => {
    const nextSearchParams = new URLSearchParams(searchParams);
    if (updates.region === null) {
      nextSearchParams.delete("region");
    } else if (updates.region) {
      nextSearchParams.set("region", updates.region);
    }
    if (updates.travelAreaId === null) {
      nextSearchParams.delete("travelAreaId");
    } else if (updates.travelAreaId) {
      nextSearchParams.set("travelAreaId", updates.travelAreaId);
    }
    setSearchParams(nextSearchParams, { replace: true });
  };

  const setAutoTitleDraft = (previousAutoTitle: string, nextAutoTitle: string) => {
    setTitleDraft((current) =>
      !titleEditedByUserRef.current &&
      (current.trim() === "" || current === previousAutoTitle)
        ? nextAutoTitle
        : current,
    );
  };

  const updateTitleDraftFromUser = (value: string) => {
    titleEditedByUserRef.current = true;
    setTitleDraft(value);
  };

  const applyTravelArea = (
    area: TravelAreaRecommendation,
    options?: {
      autoAdvancePolicyStep?: boolean;
      syncUrl?: boolean;
      regionParam?: string;
    },
  ) => {
    const previousAutoTitle = generatedTripTitle(selectedRegion, dayCount);
    const nextTravelArea = toSelectedTravelArea(area);
    setSelectedTravelArea(nextTravelArea);
    setTravelAreaChoiceSido(area.sido);
    setTravelAreaChoiceQuery(null);
    setSelectedRegionDraft(area.travelAreaName);
    setAutoTitleDraft(
      previousAutoTitle,
      generatedTripTitle(area.travelAreaName, dayCount),
    );
    if (options?.syncUrl) {
      syncTravelAreaSearchParams({
        region: options.regionParam ?? area.sido,
        travelAreaId: area.travelAreaId,
      });
    }
    if (options?.autoAdvancePolicyStep && isPolicyLinkedRegionEntry) {
      setStep(2);
    }
  };

  const applySingleTravelAreaFromQuery = (area: TravelAreaRecommendation) => {
    applyTravelArea(area, {
      autoAdvancePolicyStep: true,
      syncUrl: true,
      regionParam: travelAreaChoiceQuery ?? undefined,
    });
  };

  useEffect(() => {
    if (!requestedTravelAreaId && requestedRegion) {
      const previousAutoTitle = generatedTripTitle(selectedRegion, dayCount);
      setSelectedRegionDraft(requestedRegion);
      setSelectedTravelArea(null);
      if (isBroadTravelAreaRegion(requestedRegion)) {
        setTravelAreaChoiceSido(requestedRegion);
        setTravelAreaChoiceQuery(null);
      } else {
        setTravelAreaChoiceSido(requestedSido);
        setTravelAreaChoiceQuery(requestedRegion);
      }
      setAutoTitleDraft(
        previousAutoTitle,
        generatedTripTitle(requestedRegion, dayCount),
      );
    }
  }, [requestedRegion, requestedSido, requestedTravelAreaId]);

  useEffect(() => {
    if (!requestedTravelAreaId) {
      ignoredRequestedTravelAreaIdRef.current = null;
    }
    const shouldIgnoreRequestedTravelAreaId = Boolean(
      requestedTravelAreaId &&
      ignoredRequestedTravelAreaIdRef.current === requestedTravelAreaId,
    );
    const hasResolvedRequestedTravelArea = Boolean(
      requestedTravelAreaId &&
      selectedTravelArea?.travelAreaId === requestedTravelAreaId,
    );
    const hasSelectedTravelAreaInRecommendations = Boolean(
      selectedTravelArea &&
      travelAreaRecommendations.some(
        (area) => area.travelAreaId === selectedTravelArea.travelAreaId,
      ),
    );
    const travelAreaQuery =
      requestedTravelAreaId && !shouldIgnoreRequestedTravelAreaId
        ? hasResolvedRequestedTravelArea
          ? null
          : { query: requestedTravelAreaId, limit: 20 }
        : hasSelectedTravelAreaInRecommendations
          ? null
          : travelAreaChoiceQuery
            ? {
                query: travelAreaChoiceQuery,
                sido: travelAreaChoiceSido ?? undefined,
                limit: 20,
              }
            : travelAreaChoiceSido
              ? { sido: travelAreaChoiceSido, limit: 20 }
              : null;
    if (!travelAreaQuery) {
      if (hasSelectedTravelAreaInRecommendations) {
        setTravelAreaError("");
        setIsTravelAreaLoading(false);
        return;
      }
      setTravelAreaRecommendations([]);
      setTravelAreaError("");
      setIsTravelAreaLoading(false);
      return;
    }

    let cancelled = false;
    setIsTravelAreaLoading(true);
    setTravelAreaError("");
    appDataApi
      .listTravelAreaRecommendations(travelAreaQuery)
      .then((response) => {
        if (cancelled) return;
        if (
          requestedTravelAreaId &&
          ignoredRequestedTravelAreaIdRef.current === requestedTravelAreaId
        )
          return;
        setTravelAreaRecommendations(response.items);
        if (requestedTravelAreaId) {
          const matchedArea = response.items.find(
            (area) => area.travelAreaId === requestedTravelAreaId,
          );
          if (matchedArea) {
            applyTravelArea(matchedArea, { autoAdvancePolicyStep: true });
          } else {
            setSelectedTravelArea(null);
            setStep(1);
            setTravelAreaError(
              "요청한 세부 지역을 찾을 수 없습니다. 다른 지역을 선택하세요.",
            );
          }
        } else if (
          selectedTravelArea &&
          !isCatalogTravelAreaId(selectedTravelArea.travelAreaId) &&
          !response.items.some(
            (area) => area.travelAreaId === selectedTravelArea.travelAreaId,
          )
        ) {
          if (response.items.length === 1) {
            applySingleTravelAreaFromQuery(response.items[0]);
          } else {
            setSelectedTravelArea(null);
            if (isPolicyLinkedRegionEntry) setStep(1);
          }
        } else if (
          (travelAreaChoiceSido || travelAreaChoiceQuery) &&
          !selectedTravelArea &&
          response.items.length === 1
        ) {
          applySingleTravelAreaFromQuery(response.items[0]);
        } else if (isPolicyLinkedRegionEntry && !selectedTravelArea) {
          setStep(1);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setTravelAreaRecommendations([]);
        if (isPolicyLinkedRegionEntry) setStep(1);
        setTravelAreaError(
          "세부 지역을 불러오지 못했습니다. 잠시 후 다시 시도하세요.",
        );
      })
      .finally(() => {
        if (!cancelled) setIsTravelAreaLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    requestedTravelAreaId,
    selectedTravelArea,
    travelAreaChoiceQuery,
    travelAreaChoiceSido,
  ]);

  useEffect(() => {
    if (!isCreating) {
      setIsCreationTakingLong(false);
      return;
    }
    const timeoutId = window.setTimeout(
      () => setIsCreationTakingLong(true),
      6000,
    );
    return () => window.clearTimeout(timeoutId);
  }, [isCreating]);

  useEffect(() => {
    if (isStyleModalOpen) {
      setStyleDraft(profile.style ?? "");
    }
  }, [isStyleModalOpen, profile.style]);

  const closeStyleModal = () => {
    setStyleDraft(profile.style ?? "");
    setIsStyleModalOpen(false);
  };

  const confirmStyleModal = () => {
    if (!styleDraft) return;
    updateProfile("style", styleDraft);
    setIsStyleModalOpen(false);
  };

  const selectRegion = (region: string) => {
    const previousAutoTitle = generatedTripTitle(selectedRegion, dayCount);
    if (requestedTravelAreaId) {
      ignoredRequestedTravelAreaIdRef.current = requestedTravelAreaId;
    }
    setSelectedRegionDraft(region);
    setSelectedTravelArea(null);
    setTravelAreaChoiceSido(isBroadTravelAreaRegion(region) ? region : null);
    setTravelAreaChoiceQuery(null);
    syncTravelAreaSearchParams({ region, travelAreaId: null });
    setAutoTitleDraft(previousAutoTitle, generatedTripTitle(region, dayCount));
  };

  const selectTravelArea = (area: TravelAreaRecommendation) => {
    applyTravelArea(area, { syncUrl: true });
  };

  const updateDates = (rawStartDate: string, rawEndDate: string) => {
    // 달력 클릭과 네이티브 날짜 입력이 모두 이 함수를 지난다. 여기서 한 번
    // 정규화하면 UI에서 일수가 음수가 될 길이 없어진다.
    const { startDate: nextStartDate, endDate: nextEndDate } =
      normalizeTripDateRange(rawStartDate, rawEndDate);
    const previousAutoTitle = generatedTripTitle(selectedRegion, dayCount);
    const nextDayCount = tripDateDayCount(nextStartDate, nextEndDate);
    setStartDate(nextStartDate);
    setEndDate(nextEndDate);
    setAutoTitleDraft(
      previousAutoTitle,
      generatedTripTitle(
        selectedRegion,
        nextDayCount != null && nextDayCount > 0 ? nextDayCount : dayCount,
      ),
    );
  };



  const goNext = () => {
    if (!canProceed) return;
    if (step === 1) {
      setStep(2);
      return;
    }
    void createTrip();
  };

  const createTrip = async () => {
    const title = titleDraft.trim();
    if (!title) {
      setError("일정 제목을 입력하세요.");
      return;
    }
    if (dateRangeError) {
      setError(dateRangeError);
      setStep(2);
      return;
    }
    if (!profile.style) {
      setError("코스 취향을 선택하세요.");
      setStep(2);
      return;
    }
    setIsCreating(true);
    setIsCreationTakingLong(false);
    setError("");
    try {
      const trip = await appDataApi.createTrip({
        title,
        region: selectedRegion,
        travelAreaId: selectedTravelArea?.travelAreaId ?? undefined,
        style: profile.style ?? undefined,
        ...(linkablePolicySlug ? { policySlug: linkablePolicySlug } : {}),
        startDate,
        endDate,
      });
      if (linkablePolicySlug) {
        await appDataApi.addPolicyToTrip(trip.id, linkablePolicySlug);
        addPolicy(linkablePolicySlug);
      }
      navigate(`/trips/${trip.id}`);
    } catch {
      setError(
        "일정을 만들지 못했습니다. 선택한 조건을 확인하고 다시 시도하세요.",
      );
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <section className="screen prototype-trip-create-screen">
      <div className="prototype-create-top">
        <IconButton label="일정 목록" to="/trips">
          <ChevronLeft size={20} />
        </IconButton>
        <h1>새 일정</h1>
        <span>
          {step}/{TRIP_CREATE_TOTAL_STEPS}
        </span>
      </div>

      <div className="prototype-create-progress" aria-label="일정 생성 단계">
        <span style={{ width: `${(step / TRIP_CREATE_TOTAL_STEPS) * 100}%` }} />
      </div>

      <div className="prototype-create-content">
        {linkedPolicyLabel &&
          (step === 1 || (isPolicyLinkedRegionEntry && step === 2)) && (
            <div className="prototype-linked-policy-banner">
              <span aria-hidden="true">혜택</span>
              <strong>{linkedPolicyLabel}</strong>
            </div>
          )}

        {step === 1 && (
          <section className="prototype-create-step-panel">
            <h2>여행 지역 선택</h2>
            {/* 편집 화면과 같은 선택기다. 시도 목록만 이 화면의 순서를 쓴다. */}
            <TripRegionSelector
              error={travelAreaError || undefined}
              extraAreas={travelAreaRecommendations.map((area) => ({
                travelAreaId: area.travelAreaId,
                travelAreaName: area.travelAreaName,
                sido: area.sido,
                areaType: "recommended" as const,
                includedCities: area.includedCities,
              }))}
              onChange={(option) =>
                applyTravelArea(recommendationFromOption(option), {
                  syncUrl: true,
                })
              }
              /* 기본값 선택은 URL 에 남기지 않는다. `whole:` id 는 추천 API 로
                 되돌려 읽을 수 없어 새로고침하면 "세부 지역을 찾을 수 없습니다"가 된다. */
              onRestore={(option) =>
                applyTravelArea(recommendationFromOption(option))
              }
              onSidoChange={selectRegion}
              selectedSido={travelAreaChoiceSido}
              sidoOptions={tripCreatePrimaryRegions}
              value={optionFromSelectedArea(selectedTravelArea)}
            />
          </section>
        )}

        {step === 2 && (
          <section
            className="prototype-create-step-panel prototype-unified-checkout"
            aria-labelledby="trip-create-checkout-title"
          >
            {/* 머리 표·설명 문장·카드 번호(순서가 아니다)·도움말은 필요도 점수 80 이하라 뺐다.
                지역은 설명 문장에만 있었으므로 제목으로 올린다. */}
            <div className="prototype-checkout-hero">
              <h2 id="trip-create-checkout-title">
                {selectedRegion} 여행 정보를 확인해요
              </h2>
            </div>

            <section
              className="prototype-checkout-card prototype-checkout-title-card"
              aria-labelledby="trip-title-section-title"
            >
              <div className="prototype-checkout-section-head">
                <div>
                  <h3 id="trip-title-section-title">일정 제목</h3>
                </div>
              </div>
              <label className="prototype-title-field">
                <span className="sr-only">일정 제목</span>
                <input
                  aria-label="일정 제목"
                  name="trip-title"
                  onChange={(event) =>
                    updateTitleDraftFromUser(event.target.value)
                  }
                  placeholder={generatedTripTitle(selectedRegion, dayCount)}
                  value={titleDraft}
                />
              </label>
            </section>

            <section
              className="prototype-checkout-card"
              aria-labelledby="trip-date-section-title"
            >
              <div className="prototype-checkout-section-head">
                <div>
                  <h3 id="trip-date-section-title">여행 기간</h3>
                </div>
              </div>
              {/* 편집 화면·상세 기간 수정과 같은 컴포넌트다. */}
              <TripDateRangePicker
                onChange={({ startDate: next, endDate: nextEnd }) =>
                  updateDates(next, nextEnd)
                }
                value={{ startDate, endDate }}
              />
              {/* 화면에는 안 보인다. 테스트와 e2e 가 달을 넘기지 않고
                  날짜를 바로 지정하기 위한 통로다. */}
              <div className="prototype-date-fields prototype-date-fields-hidden">
                <label>
                  출발일
                  <input
                    type="date"
                    value={startDate}
                    onChange={(event) =>
                      updateDates(event.target.value, endDate)
                    }
                  />
                </label>
                <label>
                  도착일
                  <input
                    type="date"
                    value={endDate}
                    onChange={(event) =>
                      updateDates(startDate, event.target.value)
                    }
                  />
                </label>
              </div>
              {dateRangeError && (
                <p className="prototype-checkout-error">{dateRangeError}</p>
              )}
            </section>

            <section
              className="prototype-checkout-card"
              aria-labelledby="trip-style-section-title"
            >
              <div className="prototype-checkout-section-head">
                <div>
                  <h3 id="trip-style-section-title">코스 취향</h3>
                </div>
              </div>
              <button
                className="prototype-course-style-row"
                onClick={() => setIsStyleModalOpen(true)}
                type="button"
              >
                <span>
                  <small>선택한 취향</small>
                  <strong>{profile.style || "코스 취향 선택"}</strong>
                </span>
                <em>변경</em>
              </button>
            </section>

          </section>
        )}

        {error && <ErrorState compact message={error} />}
        {isCreating && (
          <div className="prototype-create-waiting" role="status">
            <p>새 일정을 만들고 있어요.</p>
            {isCreationTakingLong && (
              <p>
                조금만 더 기다려주세요. 응답이 늦으면 잠시 후 다시 시도할 수
                있어요.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="prototype-create-sticky-actions">
        {tripCreateActionHint && (
          <p className="prototype-create-action-hint" aria-live="polite">
            {tripCreateActionHint}
          </p>
        )}
        {step > 1 && (
          <Button
            variant="line"
            disabled={isCreating}
            onClick={() => setStep(1)}
          >
            지역 수정
          </Button>
        )}
        <Button full disabled={!canProceed || isCreating} onClick={goNext}>
          {isCreating
            ? "일정 생성 중"
            : step === 1
              ? "다음"
              : "일정 생성"}
        </Button>
      </div>

      {isStyleModalOpen && (
        <div
          className="prototype-course-style-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeStyleModal();
          }}
        >
          <section
            aria-labelledby="course-style-dialog-title"
            aria-modal="true"
            className="prototype-course-style-sheet"
            role="dialog"
          >
            <div className="prototype-course-style-sheet-head">
              <div>
                <span>코스 취향</span>
                <h2 id="course-style-dialog-title">코스 취향 선택</h2>
              </div>
              <button
                aria-label="코스 취향 선택 닫기"
                onClick={closeStyleModal}
                type="button"
              >
                ×
              </button>
            </div>
            <div
              className="prototype-course-style-grid"
              aria-label="코스 취향 후보"
            >
              {(profileOptions?.travelStyles ?? []).map((style) => (
                <button
                  aria-pressed={styleDraft === style}
                  className={styleDraft === style ? "active" : ""}
                  key={style}
                  onClick={() => setStyleDraft(style)}
                  type="button"
                >
                  <span aria-hidden="true" className="course-style-emoji">
                    {getPreferenceIcon(style)}
                  </span>
                  <strong>{style}</strong>
                </button>
              ))}
            </div>
            <div className="prototype-course-style-sheet-actions">
              <Button variant="line" onClick={closeStyleModal}>
                취소
              </Button>
              <Button disabled={!styleDraft} onClick={confirmStyleModal}>
                선택 완료
              </Button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
