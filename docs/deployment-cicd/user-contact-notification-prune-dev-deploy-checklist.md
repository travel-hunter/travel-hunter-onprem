# User Contact/Notification Prune 개발서버 반영 체크리스트

## 목적

`phone_verification_codes`, `user_notification_settings`, 연락처/전화번호 인증/알림 설정 UI와 API, 그리고 더 이상 쓰지 않는 `users` 컬럼을 제거한 변경을 개발서버에 안전하게 반영한다.

대상 변경:

- PR: `#99` — `chore/prune-contact-notification-surfaces` → `develop`
- 로컬 검증 commit: `8d0c831`
- Migration: `0025_prune_contact_notify`

## 핵심 원칙

- 개발서버도 직접 dirty worktree에서 build하지 않는다. 먼저 clean `develop` 또는 PR 검증 브랜치 상태를 맞춘다.
- 이 migration은 destructive이다. downgrade는 구조만 되살리고 삭제된 데이터는 복원하지 않는다.
- 실사용 비밀값은 출력하지 않는다. `deploy/.env.prod`는 서버 로컬 gitignored 파일로만 유지한다.
- `preferredRegions`는 유지되는 공식 지역 선호 필드다. 제거 대상은 단일 `region`, 연락처, 전화번호 인증, 알림 설정 표면이다.
- `notification_deliveries`는 inert history로만 남는다. provider 호출이나 신규 delivery row 생성은 기대하지 않는다.

## 배포 전 확인

- [ ] PR #99 CI가 통과했다.
- [ ] 리뷰에서 HIGH/MEDIUM blocker가 없다.
- [ ] 개발서버 DB 백업 또는 snapshot 여부를 확인했다.
- [ ] 삭제 대상 데이터가 복구 불가해도 되는지 확인했다.
  - [ ] `phone_verification_codes`
  - [ ] `user_notification_settings`
  - [ ] `users.phone_number`
  - [ ] `users.phone_verified_at`
  - [ ] `users.birth_date`
  - [ ] `users.gender`
  - [ ] `users.region`
  - [ ] `users.residence_area`
- [ ] `deploy/.env.prod`에 제거된 provider 설정이 남아도 앱이 의존하지 않는지 확인했다. 가능하면 별도 secret 정리 작업에서 제거한다.
- [ ] 프론트와 백엔드를 같은 배포 창에서 반영한다. 제거된 `/me/profile` 필드를 보내는 구버전 프론트와 새 백엔드를 오래 섞어 두지 않는다.

## 서버 반영 순서

```bash
ssh deploy@192.168.32.15
cd /home/deploy/travelhunterapp
git status --short
git fetch origin
```

서버 worktree가 dirty이면 `docs/deployment-cicd/09-release-checklist.md`의 Dirty worktree 복구 절차를 먼저 따른다.

PR merge 후 `develop` 기준 반영:

```bash
git checkout develop
git pull --ff-only origin develop
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml config
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml build
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d db
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml run --rm backend alembic upgrade head
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d
```

PR merge 전 개발서버 선검증이 필요하면 `chore/prune-contact-notification-surfaces` 브랜치로 checkout하되, 결과 기록에 반드시 PR 브랜치 검증이라고 남긴다.

## 배포 후 smoke

```bash
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml ps
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
curl -fsS https://dev.travel-hunter.co.kr/api/health
```

브라우저/API 확인:

- [ ] `/login` 렌더링
- [ ] seed 또는 승인된 테스트 계정 로그인
- [ ] `/mypage`에서 전화번호/인증/알림 설정 UI가 보이지 않음
- [ ] 프로필 저장 시 `preferredRegions`가 저장됨
- [ ] 프로필 저장 시 제거된 `birthDate`, `gender`, `region`, `residenceArea`, `phoneNumber`를 보내지 않음
- [ ] 정책 목록/정책 상세 진입
- [ ] 여행 생성/상세 진입
- [ ] 저장 정책 추가/삭제
- [ ] 초대 링크 생성/진입
- [ ] 로그아웃

DB 구조 확인:

```bash
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml exec db psql -U travelhunter -d travelhunter -c "\\d users"
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml exec db psql -U travelhunter -d travelhunter -c "\\dt phone_verification_codes"
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml exec db psql -U travelhunter -d travelhunter -c "\\dt user_notification_settings"
```

기대값:

- `users.preferred_regions`는 존재한다.
- 제거 대상 `users` 컬럼은 없다.
- `phone_verification_codes`, `user_notification_settings`는 없다.

## 실패 시 대응

- migration 전 실패: 코드를 이전 commit으로 되돌리고 재배포한다.
- migration 후 실패: 삭제 데이터 복원은 downgrade로 해결하지 않는다. 백업 restore 또는 별도 복구 계획을 먼저 세운다.
- 프론트만 실패: 백엔드 API가 정상이고 프론트 빌드/정적 배포 문제인지 분리해서 확인한다.
- `/me/profile` 422 증가: 구버전 프론트가 제거된 필드를 보내는지 확인하고 프론트를 즉시 새 버전으로 반영한다.

## 기록할 evidence

- 배포 날짜와 담당자
- 배포 SHA 또는 PR merge commit
- `alembic upgrade head` 결과
- `/api/health` 결과
- 주요 smoke 결과
- 실패/복구 조치
- 남은 위험
