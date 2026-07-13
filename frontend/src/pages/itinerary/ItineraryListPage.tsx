import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { appDataApi, type Trip } from "../../api";
import { useAsyncResource } from "../../api/useAsyncResource";
import { useSession } from "../../app/session";
import { ItineraryCard } from "../../components/cards";
import { ConfirmDialog, EmptyState, ErrorState, LinkButton, LoadingState } from "../../components/ui";

export function ItineraryListPage() {
  const { addedPolicy } = useSession();
  const { data: loadedTrips, error, isLoading } = useAsyncResource(() => appDataApi.listTrips(), []);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [deletingTripId, setDeletingTripId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleteCandidateTrip, setDeleteCandidateTrip] = useState<Trip | null>(null);

  useEffect(() => {
    if (loadedTrips) setTrips(loadedTrips);
  }, [loadedTrips]);

  const requestDeleteTrip = (trip: Trip) => {
    if (deletingTripId) return;
    setDeleteCandidateTrip(trip);
    setDeleteError("");
  };

  const cancelDeleteTrip = () => {
    if (deletingTripId) return;
    setDeleteCandidateTrip(null);
    setDeleteError("");
  };

  const confirmDeleteTrip = async () => {
    const trip = deleteCandidateTrip;
    if (!trip || deletingTripId) return;
    setDeletingTripId(trip.id);
    setDeleteError("");
    try {
      await appDataApi.deleteTrip(trip.id);
      setTrips((current) => current.filter((item) => item.id !== trip.id));
      setDeleteCandidateTrip(null);
    } catch {
      setDeleteError("일정을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setDeletingTripId(null);
    }
  };

  return (
    <section className="screen with-tabs prototype-trip-list-screen">
      <div className="prototype-screen-head">
        <div>
          <h1>내 일정</h1>
        </div>
        <Link className="prototype-head-pill" to="/trips/new">
          + 새 일정
        </Link>
      </div>
      <div className="content stack padded prototype-trip-list-content">
        {isLoading && <LoadingState label="일정을 불러오는 중입니다" />}
        {error && <ErrorState message={error} action={<LinkButton to="/trips/new" variant="line">새 일정 만들기</LinkButton>} />}
        {!isLoading && !error && trips.length === 0 && (
          <EmptyState eyebrow="내 일정" title="아직 등록된 일정이 없어요" body="첫 여행을 만들고 받을 수 있는 혜택을 함께 확인해보세요." action={<LinkButton to="/trips/new">일정 만들기</LinkButton>} />
        )}
        {trips.map((trip) => (
          <ItineraryCard
            key={trip.id}
            trip={trip}
            addedPolicy={addedPolicy}
            isDeleting={deletingTripId === trip.id}
            onDelete={requestDeleteTrip}
          />
        ))}
      </div>
      <ConfirmDialog
        open={Boolean(deleteCandidateTrip)}
        title="일정을 삭제할까요?"
        body={`${deleteCandidateTrip?.title ?? "선택한 일정"} 일정과 연결된 장소, 초대, 정책 연결이 함께 삭제됩니다.`}
        error={deleteError}
        confirmLabel="삭제"
        isSubmitting={Boolean(deletingTripId)}
        onCancel={cancelDeleteTrip}
        onConfirm={confirmDeleteTrip}
      />
    </section>
  );
}
