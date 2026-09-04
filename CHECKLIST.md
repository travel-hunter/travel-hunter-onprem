# CHECKLIST

## Current Status

- Active task/status: 일정 상세 헤더에서 뒤로가기 버튼과 제목 영역을 분리하고, 제목을 24px로 키웠다. 편집 버튼은 제목 흐름에서 빼 헤더 오른쪽 하단에 고정했으며 5173 Vite 서버에 반영됐다.
- Scope guard: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`, `frontend/src/app/__tests__/trip-detail.test.tsx`, `CHECKLIST.md`만 수정했다. 같은 파일에 있던 Day 스트립·드래그 작업은 보존했고 백엔드·API·스키마는 건드리지 않았다.

## Recent Validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx` — 114 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: `cd frontend && npm run test:mojibake` — mojibake 없음.
- PASS: `http://127.0.0.1:5173` — HTTP 200, Vite client 및 변경된 TSX/CSS 제공 확인.
- PARTIAL: `cd frontend && SKIP_E2E_DB_START=1 npm test` — 307 passed, 6 failed. 실패는 `mypage.test.tsx` 5건과 `policies.test.tsx` 1건에서 DB의 `dgtour-영광-8`과 테스트 기대값 `dgtour-영광`이 달라 발생했으며 이번 헤더 변경 범위 밖이다.

## Active Risks

- 360px·390px·430px 실제 브라우저에서 매우 긴 일정 제목의 줄바꿈과 오른쪽 하단 편집 버튼 간격을 육안 확인해야 한다. 5173에는 최신 코드가 반영돼 있다.
- **Day 스트립 실기기 확인 미완.** 30일 일정으로 아래를 확인해야 한다.
  - [ ] Day 줄이 한 줄로 보이고 보고 있는 날짜가 가운데에 온다
  - [ ] Day 1 과 마지막 날도 가운데에 선다
  - [ ] 카드를 들고 목록 위를 위아래로 움직여도 날짜가 안 바뀐다
  - [ ] 좌우 끝에 0.9초 들고 있으면 날짜가 넘어간다
  - [ ] 계속 대고 있으면 이어서 넘어가고, 바깥쪽일수록 빠르다
  - [ ] 카드 왼쪽 아이콘 쪽을 집어도 곧바로 날짜가 안 넘어간다
  - [ ] 0.8초 미만으로 떼면 집히지 않고 목록이 스크롤된다
  - [ ] PC 에서 드래그 중 휠·← → ·Home·End 로 날짜가 바뀐다
  - [ ] 탭에 직접 드롭해 옮기는 기존 동작이 그대로다
  - [ ] 드래그 중 화면이 위아래로 출렁이지 않는다
- 터치 집는 시간 800ms 는 일반적인 길게 누르기(300~500ms)보다 길다. 목록 스크롤을 확실히 살리는 대신 카드가 늦게 잡힌다. 실기기에서 답답하면 500ms 부터 다시 본다.
- 스트립을 손으로 밀어 탐색할 때의 관성·스냅은 이번 범위에 넣지 않았다. `overflow-x: auto` 기본 터치 스크롤로 충분한지 실기기에서 먼저 본다.
- 밀어서 가운데에 온 날짜를 자동 선택할지는 정하지 않았다. 지금은 가운데로 오기만 하고 선택은 탭으로만 한다.
- 운영 배포 Jenkins job 의 SCM 브랜치 지정이 아직 `*/ci/prod-jenkins` 다. `main` 머지가 운영 자동 배포로 이어지지 않는 상태이며, 별도 확인이 필요하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
