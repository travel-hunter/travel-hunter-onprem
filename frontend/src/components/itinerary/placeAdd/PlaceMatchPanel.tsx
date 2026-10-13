import type { PublicPlaceItem } from "../../../api";
import { CustomPlaceForm, type CustomPlaceSubmit } from "./CustomPlaceForm";
import type { MapPoint } from "./MapPointPicker";
import { PlaceMatchChoices } from "./PlaceMatchChoices";
import type { PlaceMatchState } from "./usePlaceMatch";

/* 장소 추가 시트 한 칸에 꽂는 갈래 고르기: 평소에는 '직접 적기' 입구, 고른 검색 결과를 맞춰 보는 동안에는 상태에 맞는 부분 하나 */
export function PlaceMatchPanel({
  state,
  tripId,
  fallbackCenter,
  onChooseCandidate,
  onChooseCustom,
  onStartDirect,
  onSubmitCustom,
  onCancel,
}: {
  state: PlaceMatchState;
  tripId: string;
  fallbackCenter: MapPoint | null;
  onChooseCandidate: (place: PublicPlaceItem) => void;
  onChooseCustom: () => void;
  onStartDirect: () => void;
  onSubmitCustom: (input: CustomPlaceSubmit) => void;
  onCancel: () => void;
}) {
  if (state.status === "matching") {
    return (
      <p className="place-search-status" role="status">
        {/* 시안 v59 */}
        우리 장소 목록과 맞춰 보는 중이에요.
      </p>
    );
  }
  if (state.status === "choose") {
    return (
      <PlaceMatchChoices candidates={state.candidates} noneLabel="아니요, 다른 곳이에요" onChoose={onChooseCandidate} onNone={onChooseCustom} />
    );
  }
  if (state.status === "custom") {
    return (
      <CustomPlaceForm
        fallbackCenter={fallbackCenter}
        key={state.pickId}
        onCancel={onCancel}
        onSubmit={onSubmitCustom}
        reason={state.reason}
        start={state.start}
        tripId={tripId}
      />
    );
  }
  return (
    <button className="place-direct-entry" onClick={() => onStartDirect()} type="button">
      {/* 시안 v59 */}
      찾는 곳이 없어요 · 직접 적기
    </button>
  );
}
