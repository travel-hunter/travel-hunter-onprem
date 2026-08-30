# CHECKLIST

## Current Status

- Active task/status: 개발서버 DB 스냅샷을 정제해 운영서버 DB로 1회 이전 완료(2026-08-30 KST). 운영 백엔드는 자기 Compose 네트워크의 `db:5432/travelhunter` 를 계속 사용한다.
- Scope guard: 이번 작업 범위는 개발 DB 전체 덤프 → 운영 임시 DB 복원 → 개발 전용 시드/세션 정제 → DB 이름 전환 → 스모크로 제한한다. 스키마 변경, 코드 변경, 수집 스케줄러 활성화, 관리자 지정은 포함하지 않는다.

## Recent Validation

- PASS: 운영 전환 직전본 백업 `prod-before-20260830-1824.dump` (77KB, mode 600) — `pg_restore --list` TOC 208 entries 확인.
- PASS: 개발 원본 덤프 `dev-full-20260830-1824.dump` (402KB, mode 600) — TOC 208 entries, 전송 전후 SHA-256 일치.
- PASS: 개발 백엔드 정지 상태에서 덤프 생성(쓰기 동결) 후 작업 종료 시 재기동 및 healthy 확인.
- PASS: 운영 임시 DB `travelhunter_restore_20260830_1824` 로 `pg_restore --single-transaction --no-owner --no-privileges` 오류 0, 이후 `ANALYZE` 실행.
- PASS: 정제 드라이런과 적용 결과 일치 — 시드 3명, 시드 소유 여행 1건(day 3/place 9/member 3/policy 1 CASCADE), 추천 1건, kakao 소셜연결 2건, refresh 209 + pending_signups 2 + pending_social_signups 1 삭제.
- PASS: 정제 후 잔여 0 확인 — 시드 계정, kakao 소셜연결, refresh/reset/pending 토큰 전부 0.
- PASS: 외래키 고아 검사 12개 관계 전부 0.
- PASS: 시퀀스 검사 19개 전부 `MAX(id)` 이상.
- PASS: Alembic revision `0035_stay_policy_identity` — 개발/운영 동일.
- PASS: DB 이름 전환 — `travelhunter` → `travelhunter_before_20260830_1824`, 복원본 → `travelhunter`.
- PASS: 운영 백엔드 healthy, 내부 `/api/health` `database: connected`, `environment: production`.
- PASS: 공개 도메인 `https://prod.travel-hunter.co.kr/api/health` 200 및 DB connected.
- PASS: 공개 `GET /api/policies` 139건 응답(active 수와 일치) — 전남 28 / 경북 22 / 강원 20 / 경남 17 / 전북 16.
- PASS: 운영 DB 최종 건수 — policies 159(active 139/hidden 20), external_source_records 88, policy_documents 16, users 10, social_accounts 4(google), trips 21, trip_days 116, trip_places 252, trip_members 24, trip_policies 9, trip_invites 23, user_saved_policies 4, recommendations 0, auth_refresh_tokens 0.
- PASS: `EXTERNAL_COLLECTION_SCHEDULER_ENABLED=false` 유지 확인(개발/운영 모두).
- PASS: Google `provider_id` 가 개발/운영 앱에서 동일함을 실측 확인(동일 계정 지문 일치) — google 소셜연결 4건은 무손실 이전.
- 미실행: Kakao / Google 브라우저 로그인 스모크는 운영자 로컬에서 수행 예정.
- PASS: 운영 관리자 승격 — `hjiung792@gmail.com`(id 13) `role=admin`, 관리자 1명. `/api/ops/external-collection*` 는 미인증 시 401 반환 확인.
- PASS: 수집 리허설 — 운영서버의 격리 사본 DB 에 `collect_external_benefits_from_live_sources` 1회 실행(37.9초, outcome success, parsed 70 / upsert 70). policies 159→166, active 139→146, hidden 20 유지, external_source_records 88→97. 중복 생성 없음, 수동 큐레이션 보존, 운영서버 아웃바운드 정상 확인. 시험용 DB 는 삭제했다.

## Active Risks

- Kakao 소셜연결은 앱별 사용자 ID 체계 때문에 이전하지 않고 2건을 삭제했다. 최초 Kakao 로그인 시 검증 이메일 경로(`backend/app/services/oauth.py:310`)로 자동 재연결되어야 하며, 자동 연결이 실패하면 플레이스홀더 계정이 새로 생성된다. 브라우저 스모크로 반드시 확인할 것.
- 활성 정책 139건 중 87건의 마감일이 `2026-08-31` 이다. 목록은 `status='active'` 로만 필터링하고 `end_date` 를 보지 않으므로(`backend/app/repositories/policies.py:9`) 만료 후에도 지난 마감일이 그대로 노출된다.
- 수집 스케줄러가 개발/운영 모두 비활성이다. 운영 관리자 승격으로 수동 실행 경로는 열렸으나, 자동 갱신 활성화 여부와 임계값 조정은 미결이다. 현재 `EXTERNAL_COLLECTION_MIN_PARSED_COUNT=1` 은 평상시 파싱량(70건) 대비 과도하게 낮고, `EXTERNAL_COLLECTION_POLL_SECONDS=60` 은 실패 시 당일 성공까지 60초 간격 재시도를 유발한다.
- 전환 직전 운영에 있던 동일자 가입 계정 3건과 소셜연결 3건은 이번 전환으로 제거되었다. 백업 `prod-before-20260830-1824.dump` 와 `travelhunter_before_20260830_1824` DB 에 보존되어 있다.
- 롤백 자산(이전 운영 DB, 덤프 2개)은 안정화 기간 종료 전까지 삭제하지 않는다.
- 운영 배포 Jenkins job 의 SCM 브랜치 지정이 아직 `*/ci/prod-jenkins` 다. `main` 머지가 운영 자동 배포로 이어지지 않는 상태이며, 별도 확인이 필요하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
