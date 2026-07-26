# CHECKLIST

## Current status

- Active task/status: 회원가입 인증, 비밀번호 재설정, 일정 초대 메일을 HTML + text multipart 본문으로 전환했다.
- Scope guard: 인증/계정 API 계약, token 생성/검증, SMTP 전송 방식은 유지하고 메일 본문 표현만 개선했다.

## Recent validation

- PASS: `cd backend && ../.venv/bin/python -m pytest tests/test_email_service.py tests/test_auth_db_service.py tests/test_auth_db_routes.py tests/test_trip_db_service.py -q` — 129 tests passed.
- PASS: UTF-8 replacement scan for changed Korean-bearing files — no U+FFFD found.
- PASS: `git diff --check` — no whitespace errors.

## Active risks

- 실제 SMTP 수신함에서 버튼 렌더링은 아직 확인하지 않았다. 코드 레벨에서는 HTML alternative와 plain text fallback을 검증했다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
