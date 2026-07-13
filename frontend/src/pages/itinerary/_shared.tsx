import { appDataApi } from "../../api";

export type DraftRestoreNoticeProps = {
  message: string;
  onDiscard: () => void;
};

export async function resolveTripId(tripId: string | null | undefined): Promise<string | undefined> {
  if (tripId) return tripId;
  const trips = await appDataApi.listTrips();
  return trips[0]?.id;
}

export function DraftRestoreNotice({ message, onDiscard }: DraftRestoreNoticeProps) {
  return (
    <div className="draft-restore-notice" role="status">
      <div>
        <strong>{message}</strong>
        <p>원하지 않으면 임시 저장 내용을 버릴 수 있어요.</p>
      </div>
      <button className="btn sm line" type="button" onClick={onDiscard}>
        삭제
      </button>
    </div>
  );
}
