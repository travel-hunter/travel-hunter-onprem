# 일정 관리 탭: 장소 카드 관리 재구성 설계

작성일: 2026-09-16
대상: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` (단일 Day 타임라인 + Day 탭 스트립), `backend/app/services/trips.py`

## 배경 — 다섯 가지 QA

| # | 증상 | 현재 원인 |
|---|---|---|
| 1 | 장소 여러 개 삭제가 오래 걸림 | 카드마다 확인 다이얼로그 + `DELETE /places/{id}` 1회. `expectedRevision` 낙관적 잠금 때문에 직렬만 가능, 배치 삭제 API 없음 |
| 2 | 다른 Day 로 옮긴 카드가 어디 갔는지 모름 | 이동 성공 후 `setActiveDay` + 토스트뿐. 하이라이트·스크롤 없음 (`movePlaceTo` 가 `?place=` 선택도 지움) |
| 3 | 카드 클릭으로 상세를 보고 싶지만 드래그와 겹침 | 카드 본문에 `onClick` 없음. 드래그 핸들은 카드 전체. 센서 제약 마우스 8px / 터치 800ms 가 이미 있어 **탭과 드래그는 충돌하지 않는다** |
| 4 | 날짜 줄일 때 삭제/이동 여부를 묻는 과정 필요 | 백엔드 `moveToLastDay | delete` 전략과 프런트 인라인 라디오가 두 곳(`TripDateEditorSheet`, `ItineraryEditPage`)에 중복 존재. "어느 Day 로" 선택 없음. 백엔드 전략 테스트 없음 |
| 5 | 수정·삭제 버튼 없애고 카드 자체에서 Day 이동 | 수정 시트 저장이 `PATCH /places` + `PATCH /places/move` 2회, move 실패는 조용히 삼켜짐 (`:3294`) |

## 결정 사항

1. **카드 탭 → 하단 시트.** 시트 하나가 상세 정보(주소·지도 링크) + 편집(이름·시간·메모) + Day 이동 + 삭제를 모두 담는다. `PlaceEditorSheet` 와 `PlaceDetailDialog` 를 통합. 카드 하단 수정·삭제 버튼 제거.
2. **편집 모드.** 타임라인 상단 `편집`/`완료` 토글. 편집 모드에서는 모든 Day 를 세로로 적층해 전체 일정을 조망하고, 체크박스로 다중 선택 → 하단 바 `N개 삭제` → 배치 삭제 1회. v1 은 드래그 끔.
3. **날짜 축소 확인 팝업.** 저장 시 `ConfirmDialog` 계열 팝업으로 "삭제 / Day N 으로 이동" 을 묻는다. 백엔드 전략에 `moveToDay` 추가.
4. **이동 피드백.** Day 이동 성공 시 목적지 카드 플래시 + `scrollIntoView`.

## 브랜치 분할 (순서 고정)

### ① `feature/itinerary-place-sheet` — 카드 하단 시트 + 이동 피드백 (QA 3·5·2)

**UI**
- `SortablePlaceItem` 의 `<article>` 에 `onClick` → `openPlaceSheet(place)`. dnd-kit 활성화 제약(`PLACE_DRAG_MOUSE_DISTANCE_PX=8`, 터치 800ms) 이 탭과 드래그를 분리한다. 드래그가 시작되면 click 은 발화하지 않는다.
- 카드 하단 `수정`·`삭제` 버튼 제거. `시간 확인` 경고 버튼은 유지.
- `PlaceEditorSheet` 를 확장해 단일 시트로: 상단 상세(주소, 좌표 기반 카카오맵 링크 — `PlaceDetailDialog` 에서 이관), 편집 필드(기존), Day 선택기(기존 `.place-day-picker`, Day 가 1개면 숨김), 하단 `삭제` (기존 `ConfirmDialog` 재사용).
- `PlaceDetailDialog` 삭제. 지도의 `onShowPlaceDetail` 도 같은 시트를 연다. 추천 미리보기 카드는 현행 유지.
- 키보드 접근: `sr-only` 드래그 버튼은 유지. 카드 자체는 `role="button"` + Enter/Space 로 시트 열기.

**저장 경로 분리**
- 필드 저장: `PATCH /places/{id}` 단독.
- Day/시간 이동: 시트 안 Day 선택은 즉시 `movePlaceTo` (`PATCH /places/{id}/move`) 를 호출하고 결과를 토스트로 보고. 실패를 삼키는 `:3294-3297` 경로 제거.

**이동 피드백**
- `recentlyMovedPlaceId` 상태. 이동 성공 후 목적지 Day 렌더 시 해당 `[data-place-id]` 에 `.just-moved` 클래스(1.5초 배경 플래시, CSS 애니메이션) + `scrollIntoView({block:"center"})`. 타이머 종료 시 상태 해제.
- `movePlaceTo` 가 `?place=` 를 지우는 동작은 유지 (지도 선택과 별개).

**테스트**
- `trip-detail.test.tsx`: 카드 클릭 → 시트 열림; 시트 Day 변경 → `move` 호출 1회, `PATCH /places` 호출 없음; move 실패 → 오류 토스트; 이동 후 `.just-moved` 존재. 기존 수정·삭제 버튼 테스트 갱신.
- `place-edit.test.tsx`: 통합 시트 기준으로 갱신.

### ② `feature/itinerary-edit-mode` — 편집 모드 v1 + 배치 삭제 (QA 1)

**백엔드**
- `DELETE /api/trips/{trip_id}/places` body `{ placeIds: string[], expectedRevision: number }` → `services/trips.py::delete_trip_places`: 한 트랜잭션, 소유 검증, 리비전 1회 증가, 각 Day 재정렬, 전체 `Trip` 반환. 없는 id 는 404, 리비전 불일치 409 (기존 `_bump_trip_revision_or_conflict`).
- 계약 `docs/mvp-api-contract.md` + `.agent/evals/api-contract-golden.json` 갱신.
- 테스트: `test_trip_db_routes.py`, `test_trip_db_service.py` (여러 Day 에 걸친 삭제, 리비전 충돌, 빈 목록 422).

**프런트**
- 타임라인 헤더 우측 `편집` 버튼 → `isEditMode`. 편집 모드:
  - Day 탭 스트립 숨김, 모든 Day 를 세로 적층 (`Day N` 헤더 + 카드 목록).
  - 카드에 체크박스, 카드 탭·드래그 비활성 (`DndContext` 센서 빈 배열).
  - 하단 고정 바: `N개 선택` / `삭제` / `완료`. 삭제 → `ConfirmDialog` → `appDataApi.deleteTripPlaces(tripId, ids, revision)` 1회 → `setTrip`.
- 일반 모드로 돌아오면 이전 `activeDay` 복원.
- 테스트: 편집 모드 진입 시 모든 Day 렌더; 3개 선택 삭제 → API 1회 호출 + 카드 3장 사라짐; 409 → `refreshTripAfterConflict`.

### ③ `feature/trip-date-shrink-confirm` — 날짜 축소 확인 팝업 (QA 4)

**백엔드**
- `TripDateOverflowStrategy` 에 `moveToDay` 추가, `TripSettingsUpdate` 에 `overflowTargetDay: int | None`. `_apply_trip_date_range` 에서 `moveToDay` 는 `kept_days[target-1]` 로 append. `targetDay` 범위 밖 422.
- 기존 두 전략 + 신규 전략 서비스 테스트 추가 (현재 미보장).

**프런트**
- `TripDateOverflowDialog` 컴포넌트 신설: 라디오 `제외되는 장소 삭제` / `Day N 으로 이동` (기본: 마지막 남는 Day, Day 선택기로 변경 가능). `TripDateEditorSheet` 와 `ItineraryEditPage` 의 중복 fieldset 을 이 컴포넌트로 대체하고, 인라인이 아니라 **저장 클릭 시** 팝업으로 띄운다 (`overflowPlaceCount > 0` 일 때만).
- 테스트: `trip-edit.test.tsx` payload 단언에 `moveToDay`/`overflowTargetDay` 추가; 팝업 없이 저장되는 회귀 방지.

### ④ (후속, 별도 결정) 편집 모드 v2 — 적층 화면 Day 간 드래그

② 를 써본 뒤 결정. 채택 시 dnd-kit 다중 컨테이너로 드롭 판정을 재작성하고 기존 탭 드롭·가장자리 자동 전환 존은 삭제 후보.

## 범위 밖

- 배치 Day 이동 API (v2 에서 필요 시).
- 추천 미리보기 카드 동작 변경.
- `ItineraryEditPage` 자체의 존폐.

## 검증 게이트 (브랜치 공통)

- `npx vitest run` + `npm run test:mojibake` (프런트), `pytest` (백엔드, sqlite).
- 5173 에서 모바일·데스크톱 두 뷰포트 수동 확인 목록을 인계서에 첨부. 4174 는 사용자 포트 — 사용 금지.
- 계약 변경이 있는 브랜치(②③)는 계약 문서·골든 JSON 동시 갱신.
- 파일 쓰기는 LF (`newline="\n"`). 커밋은 로컬, 푸시/PR 은 Codex.
