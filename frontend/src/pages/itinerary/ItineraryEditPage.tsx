import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { appDataApi, isApiError, type Trip } from "../../api";
import { useAsyncResource } from "../../api/useAsyncResource";
import { Button, ErrorState, LoadingState, TopBar } from "../../components/ui";
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
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!loadedTrip) return;
    setTrip(loadedTrip);
    setTitle(loadedTrip.title);
    setStartDate(loadedTrip.startDate);
    setEndDate(loadedTrip.endDate);
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

  // 두 입력이 서로 독립이라 입력 도중에 맞바꾸면 방금 고친 칸이 튄다.
  // 화면에는 입력한 그대로 두고, 미리보기와 저장에만 정규화한 범위를 쓴다.
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
        startDate: normalizedStartDate,
        endDate: normalizedEndDate,
        overflowPlaceStrategy,
      });
      navigate(`/trips/${encodeURIComponent(updatedTrip.id)}`, {
        replace: true,
        state: { notice: "일정을 수정했어요." },
      });
    } catch (nextError) {
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
        <label className="field">
          시작일
          <input aria-label="Start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label className="field">
          종료일
          <input aria-label="End date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
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
