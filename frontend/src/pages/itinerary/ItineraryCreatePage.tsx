import { ChevronLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { appDataApi, type TravelAreaRecommendation } from "../../api";
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

const TRIP_CREATE_TOTAL_STEPS = 2;
const broadTravelAreaRegions = new Set<string>(tripCreatePrimaryRegionValues);
const calendarWeekdayLabels = ["일", "월", "화", "수", "목", "금", "토"];
const NO_TRAVEL_AREA_HEADING = "세부 지역 선택";
type TripCreateStep = 1 | 2;
type DatePickerAnchor = "start" | "end";
type SelectedTravelArea = Pick<
  TravelAreaRecommendation,
  | "travelAreaId"
  | "travelAreaName"
  | "sido"
  | "includedCities"
  | "summary"
  | "tags"
>;

function parseDateInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  if (
    date.getFullYear() !== Number(match[1]) ||
    date.getMonth() !== Number(match[2]) - 1 ||
    date.getDate() !== Number(match[3])
  ) {
    return null;
  }
  return date;
}

function tripDateDayCount(startDate: string, endDate: string): number | null {
  const start = parseDateInput(startDate);
  const end = parseDateInput(endDate);
  if (!start || !end) return null;
  return Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

function formatDateInput(date: Date): string {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function startOfMonth(value: string): Date {
  const parsed = parseDateInput(value) ?? new Date();
  return new Date(parsed.getFullYear(), parsed.getMonth(), 1);
}

function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function formatCalendarMonth(date: Date): string {
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
}

function buildCalendarDays(month: Date): Date[] {
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(firstDay);
  start.setDate(firstDay.getDate() - firstDay.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return date;
  });
}

function isDateInputInRange(value: string, startDate: string, endDate: string): boolean {
  return value >= startDate && value <= endDate;
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
  const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);
  const [datePickerAnchor, setDatePickerAnchor] = useState<DatePickerAnchor>("start");
  const [calendarMonth, setCalendarMonth] = useState(() =>
    startOfMonth(defaultTripStartDate),
  );
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

  const openDatePicker = () => {
    setCalendarMonth(startOfMonth(startDate));
    setIsDatePickerOpen(true);
  };

  const selectCalendarDate = (value: string) => {
    if (datePickerAnchor === "start") {
      updateDates(value, value);
      setDatePickerAnchor("end");
      setCalendarMonth(startOfMonth(value));
      return;
    }
    updateDates(startDate, value);
    setDatePickerAnchor("start");
    setCalendarMonth(startOfMonth(value));
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
            <div className="prototype-region-grid">
              {tripCreatePrimaryRegions.map((region) => (
                <button
                  className={
                    selectedRegionButton === region.value ? "active" : ""
                  }
                  key={region.value}
                  onClick={() => selectRegion(region.value)}
                  type="button"
                >
                  <span aria-hidden="true">{region.emoji}</span>
                  <strong>{region.label}</strong>
                </button>
              ))}
            </div>
            {requiresTravelAreaSelection && (
              <div className="prototype-travel-area-choice">
                <div className="prototype-travel-area-heading">
                  <h3>
                    {travelAreaChoiceSido
                      ? `${travelAreaChoiceSido} 세부 지역 선택`
                      : NO_TRAVEL_AREA_HEADING}
                  </h3>
                </div>
                {isTravelAreaLoading && (
                  <p className="prototype-travel-area-status">
                    세부 지역을 불러오는 중
                  </p>
                )}
                {travelAreaError && (
                  <p className="prototype-travel-area-status invalid">
                    {travelAreaError}
                  </p>
                )}
                {!isTravelAreaLoading &&
                  !travelAreaError &&
                  travelAreaRecommendations.length === 0 && (
                    <p className="prototype-travel-area-status">
                      선택 가능한 세부 지역이 없습니다. 다른 지역을 선택하세요.
                    </p>
                  )}
                {travelAreaRecommendations.length > 0 && (
                  <div
                    className="prototype-travel-area-grid"
                    aria-label="세부 지역 선택"
                  >
                    {travelAreaRecommendations.map((area) => (
                      <button
                        className={
                          selectedTravelArea?.travelAreaId === area.travelAreaId
                            ? "prototype-travel-area-card active"
                            : "prototype-travel-area-card"
                        }
                        key={area.travelAreaId}
                        onClick={() => selectTravelArea(area)}
                        type="button"
                      >
                        <strong>{area.travelAreaName}</strong>
                        <small>{area.summary}</small>
                        <span className="prototype-travel-area-tags">
                          {area.tags.slice(0, 4).map((tag) => (
                            <em key={tag}>{tag}</em>
                          ))}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {step === 2 && (
          <section
            className="prototype-create-step-panel prototype-unified-checkout"
            aria-labelledby="trip-create-checkout-title"
          >
            <div className="prototype-checkout-hero">
              <span>새 일정 만들기</span>
              <h2 id="trip-create-checkout-title">
                여행 정보를 한 번에 확인해요
              </h2>
              <p>
                {selectedRegion} 일정의 제목, 기간, 취향을 확인하고 바로 만들 수
                있습니다.
              </p>
            </div>

            <section
              className="prototype-checkout-card prototype-checkout-title-card"
              aria-labelledby="trip-title-section-title"
            >
              <div className="prototype-checkout-section-head">
                <span>1</span>
                <div>
                  <h3 id="trip-title-section-title">일정 제목</h3>
                  <p>나중에 언제든 바꿀 수 있어요.</p>
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
                <span>2</span>
                <div>
                  <h3 id="trip-date-section-title">여행 기간</h3>
                  <p>Select a start and end date for the trip.</p>
                </div>
              </div>
              <button
                aria-controls="trip-date-range-picker"
                aria-expanded={isDatePickerOpen}
                className="trip-date-range-card"
                data-testid="trip-date-range-trigger"
                onClick={openDatePicker}
                type="button"
              >
                <span>여행 날짜</span>
                <strong data-testid="trip-date-range-summary">
                  {startDate} ~ {endDate}
                </strong>
                <em>{dayCount ? `${dayCount}일` : "날짜를 선택하세요"}</em>
              </button>
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
              {isDatePickerOpen && (
                <div
                  aria-label="여행 날짜 범위"
                  className="trip-date-calendar"
                  data-testid="trip-date-range-calendar"
                  id="trip-date-range-picker"
                  role="dialog"
                >
                  <div className="trip-date-calendar-head">
                    <button
                      aria-label="이전 달"
                      onClick={() => setCalendarMonth((current) => addMonths(current, -1))}
                      type="button"
                    >
                      이전
                    </button>
                    <strong>{formatCalendarMonth(calendarMonth)}</strong>
                    <button
                      aria-label="다음 달"
                      onClick={() => setCalendarMonth((current) => addMonths(current, 1))}
                      type="button"
                    >
                      다음
                    </button>
                  </div>
                  <p className="trip-date-calendar-guide">
                    {datePickerAnchor === "start" ? "첫날을 선택하세요" : "마지막 날을 선택하세요"}
                  </p>
                  <div className="trip-date-calendar-grid" role="grid">
                    {calendarWeekdayLabels.map((label) => (
                      <span className="trip-date-weekday" key={label}>
                        {label}
                      </span>
                    ))}
                    {buildCalendarDays(calendarMonth).map((date) => {
                      const value = formatDateInput(date);
                      const isCurrentMonth = date.getMonth() === calendarMonth.getMonth();
                      const isStart = value === startDate;
                      const isEnd = value === endDate;
                      const isInsideRange = isDateInputInRange(value, startDate, endDate);
                      const className = [
                        "trip-date-day",
                        isCurrentMonth ? "" : "outside-month",
                        isInsideRange ? "in-range" : "",
                        isStart ? "range-start" : "",
                        isEnd ? "range-end" : "",
                      ]
                        .filter(Boolean)
                        .join(" ");
                      return (
                        <button
                          aria-label={value}
                          className={className}
                          key={value}
                          onClick={() => selectCalendarDate(value)}
                          type="button"
                        >
                          {date.getDate()}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    className="trip-date-calendar-done"
                    onClick={() => setIsDatePickerOpen(false)}
                    type="button"
                  >
                    Done
                  </button>
                </div>
              )}
              {dateRangeError && (
                <p className="prototype-checkout-error">{dateRangeError}</p>
              )}
            </section>

            <section
              className="prototype-checkout-card"
              aria-labelledby="trip-style-section-title"
            >
              <div className="prototype-checkout-section-head">
                <span>3</span>
                <div>
                  <h3 id="trip-style-section-title">코스 취향</h3>
                  <p>추천 일정 분위기를 정합니다.</p>
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
