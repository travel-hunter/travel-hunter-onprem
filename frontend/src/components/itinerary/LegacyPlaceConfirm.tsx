import { useState } from "react";
import { appDataApi, useAsyncResource } from "../../api";
import { CustomPlaceForm, type CustomStart } from "./placeAdd/CustomPlaceForm";
import type { MapPoint } from "./placeAdd/MapPointPicker";
import { PlaceMatchChoices } from "./placeAdd/PlaceMatchChoices";
import { safeKakaoPlaceUrl } from "./placeDisplay";
import type { PlaceReplacement } from "./placeEdit";

// 예전 이름은 카카오 값이라 이름 칸을 채우지 않는다
const LEGACY_START: CustomStart = { typedName: "", fill: null, openAt: null };

/* 예전 카카오 행을 열면 수정 창 본문 대신 이 확인 화면이 뜬다(설계 2026-10-03 2절 · 3단계).
   예전 행의 이름 · 주소 · 좌표 · 메모는 여기에 쓰지도 입력칸에 채우지도 않는다 - 서버가 저장된 값으로 찾아 준 공공데이터 후보(받은 값은 서버가 저장 · 로그하지 않는다)와
   빈 이름 칸(+ 선택 위치 찍기), 카카오맵 링크만 보인다. 고르면 부모(수정 창)가 PATCH 로 그 장소(publicPlace) 또는 사용자 글(customPlace)로 바꾼다.
   후보 · 이름 칸은 장소 추가 창의 부품(PlaceMatchChoices · CustomPlaceForm)을 그대로 쓴다. 문구 · 클래스는 시안 v59 확정 때 맞춘다. */
export function LegacyPlaceConfirm({
  clue,
  fallbackCenter,
  onReplace,
  placeId,
  placeUrl,
  tripId,
}: {
  /** 결정 26: 예전 이름 대신 어느 행인지 알려 주는 한 줄('Day N · N번째 장소 · 시각') */
  clue?: string | null;
  fallbackCenter: MapPoint | null;
  onReplace: (replacement: PlaceReplacement) => void;
  placeId: string;
  placeUrl?: string | null;
  tripId: string;
}) {
  const { data, error, isLoading } = useAsyncResource(() => appDataApi.listLegacyPlaceCandidates(tripId, placeId), [tripId, placeId]);
  const candidates = data ?? [];
  // typing = 후보가 있는데 '아니요, 직접 적을게요' 를 눌렀다. formVersion = 후보가 없을 때 '취소' 가 칸을 비우는 데 쓴다
  const [typing, setTyping] = useState(false);
  const [formVersion, setFormVersion] = useState(0);
  const choosing = !isLoading && candidates.length > 0 && !typing;
  const writing = !isLoading && !choosing;
  const kakaoUrl = safeKakaoPlaceUrl(placeUrl);
  return (
    <section aria-labelledby="legacy-place-confirm-title" className="place-sheet-detail legacy-place-confirm">
      <h3 id="legacy-place-confirm-title">장소 이름을 다시 적어 주세요</h3>
      {/* 시안 v59 · 결정 26 */}
      {clue && <p className="legacy-place-clue">{clue}</p>}
      {/* 시안 v59 */}
      <p className="meta">예전에 담은 장소라 이름을 한 번 더 확인해요. 맞는 장소를 고르거나 이름을 직접 적어 주세요.</p>
      {kakaoUrl && (
        <a className="btn sm line" href={kakaoUrl} rel="noreferrer" target="_blank">
          카카오맵에서 보기
        </a>
      )}
      {isLoading && (
        <p className="place-search-status" role="status">
          비슷한 장소를 찾는 중입니다.
        </p>
      )}
      {error && <p className="place-search-status">비슷한 장소를 불러오지 못했어요. 이름을 직접 적어 주세요.</p>}
      {choosing && (
        <PlaceMatchChoices
          candidates={candidates}
          onChoose={(place) => onReplace({ publicPlace: { source: place.source, sourceId: place.sourceId } })}
          onNone={() => setTyping(true)}
        />
      )}
      {writing && (
        <CustomPlaceForm
          fallbackCenter={fallbackCenter}
          key={formVersion}
          onCancel={() => (candidates.length > 0 ? setTyping(false) : setFormVersion((version) => version + 1))}
          onSubmit={(input) => onReplace({ customPlace: { name: input.name, ...(input.geoRef ? { geoRef: input.geoRef } : {}) } })}
          reason="none"
          start={LEGACY_START}
          tripId={tripId}
        />
      )}
    </section>
  );
}
