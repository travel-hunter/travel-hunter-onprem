import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  appDataApi,
  isApiError,
  strandedTripPoliciesFromError,
  type StrandedTripPolicy,
  type TravelAreaOption,
  type Trip,
} from "../../api";
import { useAsyncResource } from "../../api/useAsyncResource";
import { Button, ErrorState, LoadingState, TopBar } from "../../components/ui";
import {
  TripRegionSelector,
  resolveTripSido,
} from "../../components/trip/TripRegionSelector";
import { TripDateRangePicker } from "../../components/trip/TripDateRangePicker";
import { normalizeTripDateRange } from "../../utils/dateDefaults";

type OverflowPlaceStrategy = "moveToLastDay" | "delete";

function dayCountFromDateInputs(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) return null;
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

export function ItineraryEditPage() {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const { data: loadedTrip, error, isLoading } = useAsyncResource(() => {
    if (!tripId) return Promise.reject(new Error("Trip not found"));
    return appDataApi.getTrip(tripId);
  }, [tripId]);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [overflowPlaceStrategy, setOverflowPlaceStrategy] =
    useState<OverflowPlaceStrategy>("moveToLastDay");
  const [selectedSido, setSelectedSido] = useState<string | null>(null);
  const [selectedArea, setSelectedArea] = useState<TravelAreaOption | null>(
    null,
  );
  // 복원된 것과 사용자가 고른 것을 가른다. 손대지 않았으면 지역을 보내지 않는다.
  const [regionTouched, setRegionTouched] = useState(false);
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  /* 지역을 바꾸면 빠지게 되는 연결 정책. 백엔드가 거부하며 알려 준 목록을 확인 상자에 띄운다.
     말없이 빼지 않는다 - 연결에는 사용자가 기록한 신청 진행이 같이 들어 있다. */
  const [strandedPolicies, setStrandedPolicies] = useState<StrandedTripPolicy[] | null>(null);

  useEffect(() => {
    if (!loadedTrip) return;
    setTrip(loadedTrip);
    setTitle(loadedTrip.title);
    setStartDate(loadedTrip.startDate);
    setEndDate(loadedTrip.endDate);
    // 저장된 지역의 광역시도를 먼저 정해야 선택기가 그 카탈로그를 불러온다.
    setSelectedSido(
      resolveTripSido(loadedTrip.travelAreaId, loadedTrip.region),
    );
    setSelectedArea(null);
    setRegionTouched(false);
  }, [loadedTrip]);

  if (isLoading) return <LoadingState label="일정을 불러오는 중입니다" />;
  if (error || !trip) {
    return (
      <section className="screen with-tabs prototype-trip-edit-screen">
        <ErrorState message={error ?? "일정 정보를 찾지 못했어요."} />
      </section>
    );
  }

  if (trip.currentUserRole === "viewer") {
    return (
      <section className="screen with-tabs prototype-trip-edit-screen">
        <TopBar title="일정 편집" />
        <ErrorState
          message="편집 권한이 없는 일정입니다."
          action={
            <Link className="btn line" to={`/trips/${encodeURIComponent(trip.id)}`}>
              일정으로 돌아가기
            </Link>
          }
        />
      </section>
    );
  }

  // 달력이 이미 정방향으로 되돌려 주지만, 저장 직전에 한 번 더 거른다.
  // 다른 경로로 상태가 들어와도 일수가 음수가 될 길을 남기지 않는다.
  const { startDate: normalizedStartDate, endDate: normalizedEndDate } =
    normalizeTripDateRange(startDate, endDate);
  const nextDayCount = dayCountFromDateInputs(
    normalizedStartDate,
    normalizedEndDate,
  );
  const dayNumbers = Object.keys(trip.days).map(Number).sort((a, b) => a - b);
  const overflowPlaceCount =
    nextDayCount != null && nextDayCount < dayNumbers.length
      ? dayNumbers
          .filter((day) => day > nextDayCount)
          .reduce((sum, day) => sum + (trip.days[day]?.length ?? 0), 0)
      : 0;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await save(false);
  };

  const save = async (removeStrandedPolicies: boolean) => {
    const trimmedTitle = title.trim();
    const dayCount = dayCountFromDateInputs(
      normalizedStartDate,
      normalizedEndDate,
    );
    if (!trimmedTitle) {
      setFormError("일정 제목을 입력해 주세요.");
      return;
    }
    if (dayCount == null || dayCount < 1) {
      setFormError("종료일은 시작일과 같거나 이후여야 합니다.");
      return;
    }

    setIsSaving(true);
    setFormError("");
    try {
      const updatedTrip = await appDataApi.updateTripSettings(trip.id, {
        expectedRevision: trip.revision,
        title: trimmedTitle,
        // 지역을 안 건드렸으면 보내지 않는다. 생략하면 백엔드가 기존 지역을 그대로 둔다.
        ...(regionTouched && selectedArea
          ? { travelAreaId: selectedArea.travelAreaId }
          : {}),
        startDate: normalizedStartDate,
        endDate: normalizedEndDate,
        overflowPlaceStrategy,
        ...(removeStrandedPolicies ? { mismatchedPolicyStrategy: "remove" as const } : {}),
      });
      navigate(`/trips/${encodeURIComponent(updatedTrip.id)}`, {
        replace: true,
        state: { notice: "일정을 수정했어요." },
      });
    } catch (nextError) {
      const stranded = isApiError(nextError) ? strandedTripPoliciesFromError(nextError.detail) : null;
      if (stranded) {
        setStrandedPolicies(stranded);
        setIsSaving(false);
        return;
      }
      setFormError(
        isApiError(nextError)
          ? nextError.message
          : "일정을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
      setIsSaving(false);
    }
  };

  return (
    <section className="screen with-tabs prototype-trip-edit-screen">
      <TopBar title="일정 편집" />
      <form aria-label="일정 편집" className="trip-edit-form" onSubmit={submit}>
        <label className="field">
          일정 제목
          <input aria-label="Trip title" value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <TripRegionSelector
          disabled={isSaving}
          onChange={(area) => {
            setSelectedArea(area);
            setRegionTouched(true);
            setStrandedPolicies(null);
          }}
          onRestore={setSelectedArea}
          onSidoChange={(sido) => {
            setSelectedSido(sido);
            setSelectedArea(null);
            setRegionTouched(true);
          }}
          restoreAreaId={trip.travelAreaId}
          restoreAreaName={trip.region}
          selectedSido={selectedSido}
          value={selectedArea}
        />
        {/* 생성 화면과 같은 범위 달력이다. 네이티브 date 입력 두 개는
            표기와 항목 높이를 운영체제가 정해 화면마다 달라 보였다. */}
        <TripDateRangePicker
          disabled={isSaving}
          onChange={({ startDate: nextStartDate, endDate: nextEndDate }) => {
            setStartDate(nextStartDate);
            setEndDate(nextEndDate);
          }}
          value={{ startDate, endDate }}
        />
        {overflowPlaceCount > 0 && (
          <fieldset className="trip-date-overflow-options">
            <legend>제외되는 날짜의 장소 {overflowPlaceCount}개를 어떻게 처리할까요?</legend>
            <label>
              <input
                checked={overflowPlaceStrategy === "moveToLastDay"}
                name="overflowPlaceStrategy"
                type="radio"
                value="moveToLastDay"
                onChange={() => setOverflowPlaceStrategy("moveToLastDay")}
              />
              마지막 Day로 이동
            </label>
            <label>
              <input
                checked={overflowPlaceStrategy === "delete"}
                name="overflowPlaceStrategy"
                type="radio"
                value="delete"
                onChange={() => setOverflowPlaceStrategy("delete")}
              />
              제외되는 장소 삭제
            </label>
          </fieldset>
        )}
        {strandedPolicies && (
          <div className="trip-edit-stranded" role="alertdialog" aria-label="지역과 맞지 않는 정책">
            <strong>지역을 바꾸면 맞지 않는 정책 {strandedPolicies.length}건이 일정에서 빠져요</strong>
            <ul>
              {strandedPolicies.map((policy) => (
                <li key={policy.slug}>
                  {policy.title}
                  {policy.hasApplicationProgress && <em> · 신청 진행 기록도 함께 지워져요</em>}
                </li>
              ))}
            </ul>
            <div className="trip-edit-stranded-actions">
              <button className="btn line" disabled={isSaving} onClick={() => setStrandedPolicies(null)} type="button">
                지역 다시 고르기
              </button>
              <button className="btn" disabled={isSaving} onClick={() => void save(true)} type="button">
                정책 빼고 저장
              </button>
            </div>
          </div>
        )}
        {formError && <p className="form-error">{formError}</p>}
        <div className="trip-edit-actions">
          <Link className="btn line" to={`/trips/${encodeURIComponent(trip.id)}`}>
            취소
          </Link>
          <Button disabled={isSaving} type="submit">
            {isSaving ? "저장 중" : "저장"}
          </Button>
        </div>
      </form>
    </section>
  );
}
