# CHECKLIST

## Current Status

- Active task/status: 날짜 간 장소 이동 드래그를 Playwright E2E로 덮고, dev 파이프라인에 백엔드 테스트 단계를 추가했다. 브랜치 `feature/e2e-backend-mode-repair`, 커밋 5건, push 하지 않았다.
- Scope guard: 변경 범위는 신규 E2E 스펙 1개(`frontend/e2e-backend/itinerary-cross-day-drag.spec.ts`), `deploy/jenkins/dev/Jenkinsfile`의 `Backend Tests` 단계 1개, 계획 문서 3건으로 제한한다. **기존 `backend-mode.spec.ts`와 프로덕션 코드는 건드리지 않았다.**

## Recent Validation

격리 환경에서만 실행했다 — DB `travelhunter_e2e`(신규 생성), 포트 8001/5174. 상시 런타임(`travelhunter` DB, 4173/8000)은 건드리지 않았다.

- PASS: `cd frontend && npx tsc --noEmit` — 신규 스펙 포함 타입 오류 없음.
- PASS: `SKIP_E2E_DB_START=1 DATABASE_URL=…/travelhunter_e2e … node scripts/run-backend-e2e.cjs itinerary-cross-day-drag` — 1 passed. Day 1 카드를 Day 2 탭에 드롭 → Day 2 활성화 + 카드 이동 + Day 1에서 제거 + **새로고침 후 유지**까지 검증한다.
- PASS: RED 확인 — `scrollIntoViewIfNeeded()` 없이는 드래그가 시작조차 안 된다. 뷰포트 390×844에서 손잡이가 y=1036이라 `elementFromPoint`가 `null`을 반환하고 `mouse.down`이 손잡이에 닿지 않는다. 중간 상태 계측으로 확인했다 (`dropTargets` 0 → 스크롤 후 3).
- PASS: 전체 E2E 13개 동시 실행 — 신규 스펙이 `[1/13]`로 먼저 돌아 통과. 기존 `backend-mode.spec.ts` 결과는 작업 전후 동일(1 failed / 8 did not run). `test.describe.configure({ mode: "serial" })`가 **파일 단위**임을 실측으로 확인했다.
- PASS: `docker build -t travel-hunter-backend-test ./backend && docker run --rm -v <repo>:/repo -w /repo/backend travel-hunter-backend-test python -m pytest tests -q` — **679 passed, 18 skipped**. Jenkinsfile에 넣은 명령과 동일한 형태다.
- PASS: 마운트 위치 확정 — `backend:/src`는 11 failed(경로 계산 인공물), `backend:/repo/backend`는 1 failed(프론트 파일 못 읽음), **저장소 전체 `.:/repo`는 0 failed**.
- FAIL→해결: `docker compose run`으로 pytest 실행 시 5 failed. compose가 `FRONTEND_BASE_URL=4173`을 주입해 기본값 5173을 기대하는 `test_invite_to_api_computes_display_flags` 등이 깨진다. 환경변수 없이 도는 `docker run`으로 변경했다.
- PASS: Jenkinsfile 구조 검토 — 중괄호 69/69 균형, stage 8개, `Backend Tests`가 `Pull Latest Code`와 `Build and Deploy` 사이에 위치.
- PASS: 격리 확인 — 실행 중 4173 HTTP 200, 8000 `/api/health` 200, 컨테이너 3개 정상. E2E 임시 포트 8001/5174는 종료 후 해제됨.
- 참고: 로컬 Windows 호스트에서는 `test_restricted_atomic_artifact_and_sidecar_round_trip` 1건이 실패한다(임시 디렉터리 권한 `S_IMODE & 0o077`). **리눅스 컨테이너에서는 통과**하며 위 679 passed에 포함된다.

## Active Risks

- **Jenkinsfile 변경은 파이프라인에서 검증되지 않았다.** Jenkins 에이전트가 개발서버에 있어 조작 금지 대상이다. 반영 시 ① 잡이 `Pipeline script from SCM`인지 인라인인지 확인하고 ② **일부러 실패하는 테스트를 넣어 배포가 실제로 멈추는지** 한 번 확인해야 한다.
- **CI에 프론트 테스트가 여전히 없다.** `npm test`(vitest)와 `test:e2e`가 `run-backend-command.cjs`/`run-backend-e2e.cjs`를 타는데, 두 스크립트 모두 **호스트 python**으로 alembic·seed·uvicorn을 띄운다. Jenkins 에이전트에는 python이 없다. 컨테이너용 러너로 고치는 작업이 선행돼야 한다. (`tsc`는 프론트 이미지 빌드가 `npm run typecheck && vite build`를 돌아 이미 강제된다.)
- **`backend-mode.spec.ts` 12개 중 3건이 낡았다.** ① 정책 `officialUrl` 기대값이 시드 변경(`f12efc2`)을 못 따라감 ② 초대 버튼 문구 `보기만 가능 링크 준비 완료`가 소스에서 사라짐 ③ 장소 수동 입력이 add 시트에서 제거됨(`place-label`이 `mode === "edit"` 전용). ②③은 **백엔드는 기능을 유지하는데 UI 진입점만 사라진** 형태라 "의도된 제거인가 유실인가" 판단이 필요하다. 이번 작업에서는 손대지 않았다.
- **기본 러너를 그냥 쓰면 로컬 DB가 오염된다.** `npm run test:e2e`는 `docker compose up -d db`로 돌고 있는 db 컨테이너를 재생성할 수 있고 `travelhunter` 본 DB에 시딩한다. 반드시 `SKIP_E2E_DB_START=1` + `DATABASE_URL`을 별도 DB로 지정해 실행한다.
- `npm ci` reports 4 audit findings from existing frontend dependencies (2 moderate, 2 high) — 이번 실행에서도 동일하게 확인됨.
- `backend/tests/test_stay_discount_semantics_migration.py`와 `backend/tests/test_stay_discount_semantics_snapshot.py`는 의도적으로 과거 `7.31`/`8.17` 동결 prestate 예시를 유지한다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
