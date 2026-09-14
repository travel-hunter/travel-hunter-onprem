# 섬 여행비 지원 신청 절차 안내 — 구현 계획

> Spec: `docs/superpowers/specs/2026-09-14-island-application-guide-design.md`. 각 Task는 RED → GREEN → 커밋. Claude가 커밋하고 push/PR/merge는 Codex가 한다.

## 일정 제약

2차 신청 마감이 **2026-09-21 18:00**이다. 공개 안내(Task 1–3)를 먼저 끝내 5174에서 검증하고, 진행 관리(Task 4–5)는 여행 기간(10/1–11/4)·서류 제출(여행 후 2주) 전에 붙인다.

## Global Constraints

- 증빙 파일·주민번호·계좌번호를 받거나 저장하지 않는다.
- 공식 절차 데이터는 수집 + 관리자 승인으로만 공개된다. 폼 링크를 코드에 고정하지 않는다.
- DTO camelCase / DB snake_case. `docs/mvp-api-contract.md`, `docs/db-schema-current.md(.sql)`, `.agent/evals/api-contract-golden.json`, `frontend/src/api/types.ts`를 형태 변경과 함께 갱신한다.
- 기존 `island_visit` 카드 제목·혜택 문구와 다른 정책의 상세·CTA는 바뀌지 않는다.
- `CHECKLIST.md`는 머지 직전에만 갱신한다.

---

### Task 1: 공식 페이지 절차 파싱

**Files:** Modify `backend/app/services/island_visit_parser.py`, `backend/tests/test_island_visit_parser.py`; Create `backend/tests/fixtures/island_visit_promotion2_2026-09-14.html`.

- [ ] Step 1: 5174 백엔드 컨테이너에서 공식 페이지를 받아 픽스처로 저장(공개 페이지, 원문 그대로).
- [ ] Step 2: 실패 테스트 — 픽스처에서 `procedure.rounds`(2차: 신청 마감 2026-09-21T18:00, 여행 2026-10-01~2026-11-04, 신청·서류 폼 URL), `documentDeadlineDaysAfterTrip=14`, `minNights=1`, `minPaymentKrw=100000`, 서류 5종, 제외 기준, 연락처를 기대. 주석 속 옛 폼 링크는 채택되지 않음. 필수 항목을 지운 HTML은 `IslandVisitParserChangedError`.
- [ ] Step 3: 구현. HTML 주석 제거 후 섹션별 추출, 폼 링크는 `forms.gle`/`docs.google.com/forms` 호스트만. 1차·2차 **모든 회차를 저장**하고, 회차 상태(`past`/`current`/`upcoming`)는 저장하지 않고 조회 시 `round_status(round, today)`로 계산한다.
- [ ] Step 4: 전체 pytest → 커밋 `feat: parse the island travel support procedure`.

### Task 2: `applicationSteps` 섹션과 island_visit mapper

**Files:** Modify `backend/app/services/policy_structured_detail.py`, `backend/app/services/policy_semantic_mapping.py`, `backend/app/services/policy_normalization.py`, `backend/app/services/policy_candidate_review.py`, `backend/app/schemas/policy.py`, tests (`test_policy_semantic_mapping*.py`, `test_policy_auto_publish.py`, contract golden), `frontend/src/api/types.ts`, `docs/mvp-api-contract.md`.

- [ ] Step 1: 실패 테스트 — island_visit 레코드 → `structuredDetail.applicationSteps` 5개(`apply/selection/travel/documents/payout`), periods 3개, requiredDocuments 5개, notes에 제외 기준, `apply_url`=신청 폼. 다른 source_category는 `applicationSteps == []`. 절차만 바뀐 레코드는 새 후보(지문 변경)이고 게이트 사유 `procedure_changed`.
- [ ] Step 2: 구현 — 섹션 키 추가(normalize/projection/admin 저장 경로), `_MAPPERS["island_visit"]`, 승격 시 `apply_url`, `evidence_fingerprint`에 `procedure` 해시, 게이트 규칙 추가(identity 검사 다음).
- [ ] Step 3: 계약 문서·골든·프론트 타입 동기화 → 전체 pytest/vitest/typecheck → 커밋 `feat: map the island support procedure into structured detail`.

### Task 3: 정책 상세 `신청 절차` 화면

**Files:** Modify `frontend/src/pages/PolicyPages.tsx`, `frontend/src/app/__tests__/policy-detail.test.tsx`, `frontend/src/styles/app.css`.

- [ ] Step 1: 실패 테스트 — applicationSteps가 있으면 회차 목록(지난 회차 접힘 "종료", 현재 회차 펼침 + 신청 마감 D-n, 다음 회차 "예정"), 현재 회차 스텝 5개·기간, `신청 폼 열기`/`서류 제출 폼 열기` 링크와 선정자 경고, 마감 3일 이내 강조·지나면 "마감". 없으면 섹션 없음(기존 정책 회귀).
- [ ] Step 2: 구현(기존 `section-block`/`SurfaceCard` 재사용, 새 컴포넌트 최소화).
- [ ] Step 3: typecheck/build/mojibake → 5174 재빌드 후 island_visit 후보 수집·승인해 실제 화면 확인 → 커밋 `feat: show the island support application steps`.

### Task 4: 일정 단위 진행 상태 API

**Files:** Modify `backend/app/models/tables.py`, `backend/app/services/trips.py`, `backend/app/api/routes/trips.py`, `backend/app/schemas/trip.py`, `backend/app/services/policies.py`, `backend/tests/test_db_schema.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`; Create `backend/alembic/versions/0042_trip_policy_application.py`, `backend/app/services/island_application.py`, `backend/tests/test_island_application.py`.

**Interfaces:** `application_view(trip, trip_policy, policy, approved_islands) -> dict`, `update_application(db, *, trip_id, policy_slug, user, status, checklist)`.

- [ ] Step 1: 실패 테스트 — 전이 규칙(허용/409), 편집자만(뷰어 403), 비섬 정책 404, 알 수 없는 서류 키 422, 조건 점검 4종(기간 밖·당일치기·대상 섬 없음·서류 마감=종료일+14), `linkedPolicies[].deadline` 추가, applied-policy-links에 `applicationStatus`.
- [ ] Step 2: 0042(컬럼 4개, CHECK, FK) + 모델 → 서비스(일정 행 잠금) → 라우트 `PATCH /api/trips/{id}/policies/{slug}/application`.
- [ ] Step 3: 계약·스키마 문서 → 전체 pytest, `alembic upgrade 0041:head --sql` → 커밋 `feat: track island support application progress per trip`.

### Task 5: 일정 상세 `신청 진행` 패널과 목록 배지

**Files:** Modify `frontend/src/api/types.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/pages/AppliedPolicyLinksPage.tsx`, 관련 테스트.

- [ ] Step 1: 실패 테스트 — 섬 정책 카드에 스텝퍼·다음 행동 버튼(`신청 완료로 표시` 등)·조건 점검 ✓/⚠·서류 체크리스트 토글 저장·`서류 제출 D-n`, 뷰어는 읽기 전용, 409 시 새로고침 안내. 목록 페이지 상태 배지.
- [ ] Step 2: 구현(`AppDataApi.updateTripPolicyApplication` 추가).
- [ ] Step 3: vitest/typecheck/build/mojibake → 커밋 `feat: guide island support progress from the trip page`.

### Task 6: 격리 검증과 문서

- [ ] 5174 재빌드 → 0042 왕복 → `db-schema-current.sql` 재생성 → island_visit 수집·승인 → 대상 섬이 들어간 10월 일정에 정책 연결 → 상태 전이·체크리스트·조건 점검·D-day 확인 → `policy-collection-to-screen-flow.md`에 절차 수집·검토·진행 관리 흐름 추가 → 커밋 `docs: document the island support application guide`.

## 확정 사항 (2026-09-14)

1. 진행 상태는 **일정(팀) 단위**.
2. 정책 상세는 **지난·현재·다음 회차 모두** 표시(상태는 조회 시 계산).
3. 마감 알림은 **앱 안 D-day 표기**(정책 상세 신청 마감, 일정 진행 패널 신청·서류 제출 마감, 3일 이내 강조). 푸시·이메일은 알림 런타임 복구가 필요한 별도 작업.
