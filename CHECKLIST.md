# CHECKLIST

## Current Status

- Active task/status: 일정 상세의 Day 선택을 가로 한 줄 스트립으로 바꾸고, 드래그 중 날짜 전환을 탭 호버에서 좌우 이동영역·휠·화살표 키로 옮겼다. 30일 일정에서 알약이 다섯 줄로 쌓이던 문제와, 탭 위를 스쳐 지나가기만 해도 날짜가 바뀌던 문제를 함께 없앤다.
- Scope guard: 변경 범위는 `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`, `frontend/src/app/__tests__/trip-detail.test.tsx` 로 제한한다. 카드·타임라인·색·아이콘 등 화면 디자인, 탭에 직접 드롭해 옮기는 기능, 2026-08-26 뷰포트 잠금 결과물, 백엔드·API·스키마는 건드리지 않는다.

## Recent Validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx` — 104 passed.
- PASS: `cd frontend && SKIP_E2E_DB_START=1 npx vitest run` — 303 passed, 0 failed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run test:mojibake` — mojibake 없음.
- PASS: `cd frontend && npm run build`.
- PASS: `git diff --check`, 변경 파일 3개 모두 U+FFFD 0.
- 확정된 조작값(시안에서 손으로 조절해 결정): 이동영역 폭 80px, 머무는 시간 900ms, 반복 간격 620ms, 바깥쪽 가속 2.8배, 휠 민감도 100, 터치 집는 시간 800ms.
- 미실행: 실기기·브라우저 확인은 운영자 몫이다. 아래 Active Risks 의 확인 목록 참조.

## Active Risks

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
