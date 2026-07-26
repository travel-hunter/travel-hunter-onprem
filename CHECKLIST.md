# CHECKLIST

## Current status

- Active task/status: `/mypage` 설정 메뉴에서 `비밀번호 관리`를 `회원 탈퇴` 바로 위, `로그아웃`은 마지막으로 이동했다.
- Scope guard: 메뉴 순서만 조정했고 API/DB 계약은 변경하지 않았다. 테스트 fixture의 디지털관광주민증 예시 slug/title은 현재 canonical 정책 링크(`dgtour-영광`, `[영광] 디지털관광주민증 혜택`)와 맞췄다.

## Recent validation

- PASS: `cd frontend && npm run typecheck && npx vitest run src/app/__tests__/mypage.test.tsx` — typecheck passed, 22 tests passed.
- PASS: `cd frontend && npm run build` — typecheck 포함 Vite production build completed.
- PASS: UTF-8 replacement scan for changed Korean-bearing files — no U+FFFD found.
- PASS: `git diff --check` — no whitespace errors.

## Active risks

- 로컬 브라우저 수동 확인은 아직 수행하지 않았다. 자동 테스트와 production build 기준으로 메뉴 순서 변경은 검증됐다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
