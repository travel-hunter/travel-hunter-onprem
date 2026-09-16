# Codex 인계 — 일정 편집 모드 v1 + 배치 삭제 (feature/itinerary-edit-mode)

작성: Claude, 2026-09-16
워크트리: `.superpowers/worktrees/itinerary-edit-mode` · 브랜치 `feature/itinerary-edit-mode` · **base `feature/itinerary-place-sheet@b1fb6a8`** (① 위에 쌓임)
스펙: `docs/superpowers/specs/2026-09-16-itinerary-card-management-design.md` §② · 플랜: `docs/superpowers/plans/2026-09-16-itinerary-edit-mode.md`

## 상태

- 구현 완료, **미커밋**(사용자 승인 대기). 푸시·PR 은 Codex.
- **PR base 는 ① 브랜치**(또는 ① 머지 후 develop). develop 에 바로 열면 ① diff 가 통째로 딸려 온다.
- 변경 파일 14개: 백엔드 3(`schemas/trip.py`, `services/trips.py`, `api/routes/trips.py`) + 테스트 2, 계약 2(`docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`), 프런트 API 3(`dataApi.ts`, `backendApi.ts`, `backendApi.test.ts`), 페이지·CSS 2, 테스트 2(`trip-edit-mode.test.tsx` 신규, `trip-detail.test.tsx` 1줄). 스키마/마이그레이션 변경 없음.

## 무엇이 바뀌었나

| 항목 | 내용 |
|---|---|
| API | `POST /api/trips/{trip_id}/places/batch-delete` body `{expectedRevision, placeIds[1~200]}` → `Trip`. 403 viewer / 404 하나라도 없음(리비전 안 올림) / 409 리비전 불일치 / 422 빈 목록. 중복 id 는 한 번. 삭제 후 재정렬 없음(단건 삭제와 동일; 삽입은 `max(order_num)+1`, 조회는 정렬이라 빈칸 무해) |
| 스펙과 다른 점 | 스펙의 `DELETE …/places`+body 대신 POST — `apiClient.delete` 가 body 를 못 받고 기존 배치 추가도 POST. `편집` 버튼은 "타임라인 헤더 우측" 대신 `trip-primary-actions` 상단 전폭 버튼 |
| 프런트 | `편집` → Day 탭·DnD 타임라인 대신 모든 Day 세로 적층(`EditModeList`, 체크박스) + 하단 고정 바(`EditModeBar`: `N개 선택` / `삭제` / `완료`). 편집 중에는 카드 탭·드래그·장소 추가·지도 상세 비활성, `편집` 버튼 숨김. 삭제 → ConfirmDialog 1회 → 배치 API 1회 → 편집 모드 유지. 409 → 새로고침 + 선택 유지 + 다이얼로그 유지(재시도 가능); 새로고침으로 선택이 비면 다이얼로그 닫힘 |

## 검증

- 프런트: `npx vitest run` 34 files / **405 passed**, `test:mojibake` clean, `tsc` clean.
- 백엔드: `pytest tests` 850 passed / 1 failed — `test_stay_discount_semantics_snapshot::test_restricted_atomic_artifact_and_sidecar_round_trip` 는 **메인 리포 develop 에서도 동일하게 실패**(스냅샷 디렉터리 ACL, 환경 문제). 이 브랜치 관련 파일(`test_trip_db_service.py`, `test_trip_db_routes.py`) 146 passed.
- 줄끝: `git diff --stat` == `--ignore-space-at-eol --stat`.
- e2e 미실행.
- 리뷰: Task 별 4회 + 전체 브랜치 1회 + 수정 1회 재리뷰. 잔여 minor 아래.

## 통합 확인 스택 (현재 떠 있음)

- 프런트 `http://127.0.0.1:5177/` (① + ②) · 백엔드 `127.0.0.1:8003` (② 워크트리, 메인 venv, 스케줄러 off, CORS 5177) · DB 는 로컬 55432 공용, 마이그레이션 없음.
- 5173 은 다른 워크트리가 점유, 4174 는 사용자 포트 — 둘 다 손대지 않음.

## 수동 확인 (사용자, `test.user`)

1. 390px: `편집` → Day 탭 사라지고 Day 별 세로 적층, 하단 바가 탭바 위에 뜸, 마지막 카드가 바에 안 가려짐.
2. ≥768px: 하단 바가 바닥에 붙음.
3. 체크 2개(다른 Day) → `2개 선택` → `삭제` → 확인 → 네트워크에 `batch-delete` 1회 → 카드 2장 사라짐, 편집 모드 유지, 토스트 "장소 2개를 일정에서 삭제했어요."
4. `완료` → Day 탭·타임라인 복귀, 이전 Day 유지, Day 스트립 패딩/스크롤 정상.
5. 편집 모드에서 카드 탭·드래그·`+ 장소 추가`·지도 상세가 안 됨.
6. 보기 권한 계정: `편집` 없음. 추천 미리보기 중: `편집` 없음.
7. **디자인 질문**: 편집 모드에서 지도는 여전히 현재 Day 만 보여주고 목록은 전체 Day 다. 편집 중 지도를 숨길지 / 전체 Day 를 찍을지 결정 필요.

## 잔여 minor (머지 차단 아님)

- 같은 이름의 장소가 둘이면 체크박스 접근성 이름이 겹침(`{label} 선택`) — Day·시간을 이름에 넣으면 해결.
- 편집 목록 행 `<div onClick>` 은 키보드 역할 없음(체크박스가 포커스·이름을 맡음).
- `openAddPlace` 의 `isEditMode` 가드는 도달 불가(섹션이 숨겨짐).
- 순서 단언 테스트는 클릭 순서로도 통과; 토스트 타이머 미정리(기존 패턴); `ConfirmDialog` 고정 id·포커스 트랩 없음(기존 컴포넌트).
- 편집 모드 분기 아래 150줄이 옛 들여쓰기(동작 무관, diff 부풀림 방지로 남김).

## Codex 가 할 일

1. ① 머지 → 이 브랜치를 develop 에 리베이스(충돌 없음 예상, ① 위에 선형) → 푸시 → PR.
2. PR 본문에 API 변경(계약·골든 갱신됨), 수동 확인 결과, e2e 미실행 명시.
3. 후속: ③ `feature/trip-date-shrink-confirm`(스펙 참조), ④ 편집 모드 v2(적층 화면 Day 간 드래그)는 ② 써본 뒤 결정.
