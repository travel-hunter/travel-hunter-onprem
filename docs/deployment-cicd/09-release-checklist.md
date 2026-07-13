# Release Checklist

## 개발 서버 재개/남은 smoke 준비

최신 개발 서버 기준값:

- SSH: `ssh deploy@192.168.32.15`
- 확인된 hostname: `dev-server`
- 서버 repo 경로: `/home/deploy/travelhunterapp`
- compose 파일: `compose.tunnel.yaml`
- 서버 runtime env: `/home/deploy/travelhunterapp/deploy/.env.prod` (`chmod 600`, gitignored, 값 출력 금지)
- 배포 SHA: `a6140e2` (`origin/develop`, 2026-07-02 개발서버 tunnel stack 복구 기준)
- 개발 도메인: `https://dev.travel-hunter.co.kr`
- 2026-06-16 복구 기준: 서버 dirty worktree 백업 `/home/deploy/.travel-hunter-recovery/20260616T011723Z` 보존 후 clean `develop`@`9169990aac582e4608648761b8633e56a429cbd5`로 reset/rebuild/migration/smoke 완료.
- 2026-06-16 재배포 기준: PR #55 merge 후 clean `develop`@`45c629256107e99700abea0e80b39d569404e002`로 reset/rebuild/migration/smoke 완료. 현재 계약 기준 API smoke는 `/api/profile-options`와 `/api/recommendations/regions`를 사용한다.
- 2026-07-02 복구 기준: `/home/deploy/travelhunterapp`에서 clean `develop`@`a6140e2`로 정렬하고, recovery env를 `deploy/.env.prod`로 복원한 뒤 `compose.tunnel.yaml` stack(`db/backend/frontend/caddy/cloudflared`)을 rebuild/up 했다. `https://dev.travel-hunter.co.kr/`, `/api/health`, `/login`, seed 계정 로그인, 정책/여행 API와 SPA route smoke가 통과했다.

남은 개발 서버 smoke 값은 repo 밖의 서버 전용 파일에만 둔다.

```bash
ssh deploy@192.168.32.15
umask 077
cat > ~/.travel-hunter-smoke.env <<'EOF'
# Admin ops smoke
SMOKE_ADMIN_MODE=create_temp
SMOKE_ADMIN_EMAIL=dev-admin-smoke@example.com
SMOKE_ADMIN_PASSWORD=<runtime-only-test-password>
SMOKE_ADMIN_CLEANUP=revert_role

# SMTP smoke
SMOKE_TEST_EMAIL=<smtp-test-inbox>
SMOKE_MAIL_RECEIPT_MODE=manual

# OAuth smoke
SMOKE_OAUTH_MODE=manual_browser
SMOKE_GOOGLE_TEST_EMAIL=<google-test-account-email>
SMOKE_KAKAO_TEST_EMAIL=<kakao-test-account-email>
EOF
chmod 600 ~/.travel-hunter-smoke.env
```

주의:

- Google/Kakao 계정 비밀번호는 파일, 채팅, git, 로그에 남기지 않는다. OAuth callback smoke는 브라우저 수동 로그인으로 확인한다.
- `SMOKE_ADMIN_CLEANUP`은 `revert_role`, `delete_user`, `retain` 중 하나로 명시하고 결과를 evidence에 기록한다.
- Docker daemon/network DNS 변경은 별도 Docker DNS 작업명세서와 명시 승인 후에만 실행한다.
- production 서버/DNS/Cloudflare/OAuth provider 변경은 production 작업명세서를 먼저 보여주고 명시 승인 후에만 실행한다.
- DB 초기화, Docker volume 삭제, secret 출력, production 변경은 별도 승인 없이는 하지 않는다.

### Dirty worktree 복구 절차

서버 repo가 dirty이면 compose build를 금지하고 아래 순서를 먼저 따른다.

1. `deploy/.env.prod` 값을 출력하지 않은 상태로 `git status --short`, `git branch -vv`, `git diff`, 삭제/미추적 파일 목록을 `~/.travel-hunter-recovery/<timestamp>/`에 저장한다.
2. 대상 브랜치와 SHA를 확인한다. 개발 서버 기본값은 clean `develop` / `origin/develop`이다.
3. reset/clean/rebuild/migration/smoke 계획을 `CHECKLIST.md`, `.omx/plans/*`, 또는 별도 handoff 문서에 남긴 뒤 실행한다.
4. 복구 후 public/API smoke와 서버 source-boundary smoke 결과를 기록한다.

## 배포 전

- [ ] 배포 대상 브랜치가 맞다.
  - 개발 서버: `develop`
  - 운영 서버: `main`
- [ ] GitHub Actions CI가 통과했다.
- [ ] Jenkins build가 통과했다.
- [ ] 실제 `.env`, DB password, OAuth secret, tunnel token이 commit에 없다.
- [ ] 임시 Docker 이미지 archive(`*.tar`, `*.tar.gz`, `*.tgz`)가 commit에 없다.
- [ ] GitHub에는 source code, Dockerfile, Compose 설정, docs, safe example env만 올라간다.
- [ ] API 변경이 있으면 `docs/mvp-api-contract.md`와 frontend/backend/evals가 같이 갱신됐다.
- [ ] DB migration 변경이 있으면 `alembic upgrade head --sql` 결과를 확인했다.
- [ ] 운영 DB backup 필요 여부를 확인했다.
- [ ] `VITE_API_BASE_URL`, `CORS_ORIGINS`, `REFRESH_COOKIE_SECURE` 값이 배포 domain 기준이다.
- [ ] 머지 전 필요한 보안 검토를 완료하고 모든 HIGH 항목을 해소했다.

## 배포 명령

Cloudflare Tunnel 기준:

```bash
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml config
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml build
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d db
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml run --rm backend alembic upgrade head
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d
```

seed가 필요한 환경에서만 실행:

```bash
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml run --rm backend python -m app.db.seed
```

## 배포 후 상태 확인

```bash
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml ps
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 caddy
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 cloudflared
curl -fsS https://<domain>/api/health
APPROVED_BEARER_TOKEN=<approved-bearer-token>
curl -fsS -H "Authorization: Bearer $APPROVED_BEARER_TOKEN" https://<domain>/api/ops/external-collection
curl -fsS -X POST -H "Authorization: Bearer $APPROVED_BEARER_TOKEN" https://<domain>/api/ops/external-collection/run
curl -fsS -H "Authorization: Bearer $APPROVED_BEARER_TOKEN" "https://<domain>/api/ops/external-collection/quality?style=맛집&region=부산&limit=3"
```

## Smoke Test

- [ ] `https://<domain>/api/health` returns ok.
- [ ] Admin bearer-authenticated `https://<domain>/api/ops/external-collection` returns scheduler cadence and last collection status without changing `/api/health`.
- [ ] Optional admin bearer-authenticated `POST https://<domain>/api/ops/external-collection/run` returns source-level collection outcome without exposing secrets.
- [ ] Admin bearer-authenticated `https://<domain>/api/ops/external-collection/quality?style=맛집&region=부산&limit=3` returns DB-backed collection quality counts and recommendation preview without live fetch.
- [ ] `https://<domain>/login` renders.
- [ ] 로그인 성공.
- [ ] 로그인 실패 메시지 확인.
- [ ] 정책 목록 검색/필터.
- [ ] 정책 상세 진입.
- [ ] 정책 저장/삭제.
- [ ] 일정 생성.
- [ ] 일정 상세 진입.
- [ ] 정책을 일정에 담기.
- [ ] AI 추천 결과 진입.
- [ ] AI 추천 항목을 일정에 추가.
- [ ] 초대 링크 생성/진입.
- [ ] 로그아웃.

운영 smoke용 bearer token은 담당자가 런타임에서만 주입하고, 출력/commit/log 기록을 금지한다.

테스트 계정은 seed 실행 환경에서만 사용한다.

```text
test.user@example.com / password123
```

## Release Readiness

Release candidate handoff는 아래 기준을 모두 설명할 수 있을 때만 ready로 본다.

- [ ] Core auth, profile, policies, trips, recommendations, saved policy, and invite flows work for the current MVP phase.
- [ ] `docs/mvp-api-contract.md`, frontend types, backend schemas, and focused tests agree.
- [ ] Public, protected, and authenticated routes render at target responsive widths without blank pages or horizontal overflow.
- [ ] Frontend keeps the `AppDataApi` boundary and backend keeps route/schema/service/repository separation.
- [ ] Fast lane checks, e2e/build checks, backend tests, Alembic SQL check, and Compose checks have release-candidate evidence.
- [ ] README, env examples, current plan, checklist, and deployment docs explain setup, behavior, and remaining risks.
- [ ] No known release blocker remains.

## Provider Smoke

실제 provider env가 준비된 staging/production 후보에서만 수행한다. 비밀값은 출력/commit/log 기록을 금지한다.

- [ ] SMTP: 비밀번호 재설정 email 수신, reset token confirm, 새 비밀번호 로그인.
- [ ] Google OAuth: redirect URI, callback, refresh/profile session 복구.
- [ ] Kakao OAuth: Kakao Login ON, `account_email` 동의항목, redirect URI, callback, session 복구, 기존 `kakao_{providerId}@oauth.local` email의 verified Kakao email 자동 교체 확인.
- [ ] Kakao Maps: JavaScript SDK domain 등록 후 public 화면에서 지도 rendering 확인.
- [ ] Kakao Local REST: runtime key가 backend에 전달되고 대표 추천 후보 smoke가 통과하는지 확인.
- [ ] Cloudflare: public HTTPS domain에서 `/api/health`, `/login`, `/policies`, `/trips`, `/mypage` 확인.

## Rollback

코드 rollback:

```bash
cd /srv/travel-hunter-app
git checkout <previous-good-commit>
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml build
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d
```

DB migration rollback은 자동으로 가정하지 않는다. 데이터 손실 가능성이 있으면 backup restore 또는 별도 downgrade 계획을 먼저 적용한다.

## 배포 기록

배포 후 아래를 `CHECKLIST.md`, PR, 또는 release handoff 문서에 남긴다.

- 배포 날짜.
- 배포 commit.
- 대상 환경.
- 실행한 검증 명령.
- smoke test 결과.
- 발생한 문제와 조치.
- 남은 위험.
