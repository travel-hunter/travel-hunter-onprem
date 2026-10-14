import { useId } from "react";
import type { PublicPlaceItem } from "../../../api";
import { PlacePhoto } from "../PlacePhoto";
import { PUBLIC_CATEGORY_LABEL, distanceText } from "./publicPlaceText";

/* '이 장소가 맞나요?' - 맞춰 보기에서 후보가 하나뿐이 아니거나 분류가 안 맞을 때. 후보는 모두 공공데이터 값이다(카카오 값 아님) */
export function PlaceMatchChoices({
  candidates,
  onChoose,
  onNone,
  noneLabel = "아니요, 직접 적을게요",
}: {
  candidates: PublicPlaceItem[];
  onChoose: (place: PublicPlaceItem) => void;
  onNone: () => void;
  /** '맞는 곳이 없다' 단추 문구 - 장소 추가 창(PlaceMatchPanel)은 '아니요, 다른 곳이에요', 예전 행 확인(LegacyPlaceConfirm)은 기본값 (시안 v64) */
  noneLabel?: string;
}) {
  const bodyId = useId();
  return (
    <section aria-label="이 장소가 맞나요?" className="place-match-choices">
      <div className="place-match-head">
        <strong>이 장소가 맞나요?</strong>
        {/* 시안 v59 */}
        <p>고른 곳과 비슷한 곳을 찾았어요. 맞는 곳을 누르면 목록에 담겨요.</p>
      </div>
      <div className="place-match-list" role="list">
        {candidates.map((place, index) => (
          <div key={`${place.source}:${place.sourceId}`} role="listitem">
            {/* 이름이 같은 후보가 흔하다(두 출처 · 다른 주소) - 분류 · 주소 · 거리도 설명으로 읽히게, 이름이 겹치면 단추 이름에도 붙여 서로 다르게 */}
            <button
              aria-describedby={`${bodyId}-${index}`}
              aria-label={
                candidates.some((other) => other !== place && other.name === place.name)
                  ? `${place.name} 선택 · ${PUBLIC_CATEGORY_LABEL[place.category]} · ${place.address ?? "주소 정보 없음"} · ${distanceText(place.distanceMeters)}`
                  : `${place.name} 선택`
              }
              className={place.photoUrl ? "place-match-card has-photo" : "place-match-card"}
              onClick={() => onChoose(place)}
              type="button"
            >
              <PlacePhoto alt="" compact url={place.photoUrl} />
              <span className="place-match-body" id={`${bodyId}-${index}`}>
                <strong>{place.name}</strong>
                <em>{PUBLIC_CATEGORY_LABEL[place.category]}</em>
                <small>{place.address ?? "주소 정보 없음"}</small>
                <small>{distanceText(place.distanceMeters)}</small>
              </span>
            </button>
          </div>
        ))}
      </div>
      {/* 시안 v59 · v64 */}
      <button className="btn sm line place-match-none" onClick={onNone} type="button">
        {noneLabel}
      </button>
    </section>
  );
}
