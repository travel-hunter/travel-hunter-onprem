# 관리자 전용 서브도메인 Cloudflare Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 내부 운영자만 `admin.<domain>`에서 Cloudflare Access와 앱 관리자 역할을 모두 통과해 관리자 기능을 사용하게 한다.

**Architecture:** 일반·관리자 호스트를 Caddy에서 분리하고, 프런트는 현재 host에 따라 관리자 진입과 일반 호스트의 `/admin` 이동을 결정한다. API 권한은 기존 `require_admin_user`를 유지하며, Cloudflare Access는 앱 밖의 첫 방어선이다.

**Tech Stack:** React/Vite, FastAPI, Caddy, Cloudflare Tunnel, Cloudflare Access, Cloudflare One-time PIN.

**Spec:** `docs/superpowers/specs/2026-09-16-admin-subdomain-access-design.md`

## Global Constraints

- Cloudflare·AWS·DNS·OAuth console 변경은 production 작업 명세와 별도 명시 승인이 필요하다.
- 비밀값, Access token, OAuth secret, runtime `.env` 값은 커밋하거나 출력하지 않는다.
- 기존 `/api/admin/*`와 `/api/ops/*`의 `require_admin_user` 권한 검사를 제거하거나 완화하지 않는다.
- 관리자와 일반 사용자 세션 쿠키를 부모 도메인에 공유하지 않는다.

---

### Task 1: 환경별 관리자 호스트 계약 추가

**Files:**
- Modify: `.env.example`
- Modify: `backend/app/core/config.py`
- Modify: `docs/mvp-api-contract.md`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `ADMIN_DOMAIN` 설정값과 backend runtime validation.

- [ ] **Step 1: 실패 테스트를 작성한다.**

```python
def test_staging_requires_admin_domain(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("ADMIN_DOMAIN", raising=False)
    assert "ADMIN_DOMAIN" in Settings.from_env().runtime_problems()
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다.**

Run: `cd backend && python -m pytest tests/test_config.py -q`

- [ ] **Step 3: 최소 설정을 구현한다.**

`ADMIN_DOMAIN`을 safe example에 추가하고, staging/production에서 public domain과 다른 HTTPS host인지 검증한다. CORS에는 일반·관리자 origin을 모두 명시적으로 포함한다.

- [ ] **Step 4: 테스트를 다시 실행한다.**

Run: `cd backend && python -m pytest tests/test_config.py -q`

- [ ] **Step 5: 커밋한다.**

```bash
git add .env.example backend/app/core/config.py backend/tests/test_config.py docs/mvp-api-contract.md
git commit -m "feat: define admin subdomain runtime contract"
```

### Task 2: Host별 Caddy 라우팅과 일반 호스트 차단

**Files:**
- Modify: `deploy/Caddyfile`
- Modify: `deploy/Caddyfile.tunnel`
- Modify: `docs/deployment-cicd/dev-server-container-architecture.md`
- Test: `deploy` Caddy config validation command

**Interfaces:**
- Consumes: `STAGING_DOMAIN`, `ADMIN_DOMAIN`.
- Produces: 일반 host `/admin` redirect와 관리자 host `/` redirect.

- [ ] **Step 1: Caddy host routing 검증 명세를 작성한다.**

일반 host는 `/admin*`을 `https://{ADMIN_DOMAIN}/admin{uri}`로 302 이동하고, 관리자 host는 `/`을 `/admin`으로 302 이동한다. 두 host 모두 `/api/*`는 backend로, 그 외는 frontend로 프록시한다.

- [ ] **Step 2: Caddyfile을 구현한다.**

host block을 분리하고 redirect가 API path보다 먼저 API를 가로채지 않는지 확인한다.

- [ ] **Step 3: Compose 설정을 검증한다.**

Run: `docker compose --env-file <safe-test-env> -f compose.yaml config > /dev/null`

- [ ] **Step 4: 커밋한다.**

```bash
git add deploy/Caddyfile deploy/Caddyfile.tunnel docs/deployment-cicd/dev-server-container-architecture.md
git commit -m "feat: route admin traffic through a dedicated host"
```

### Task 3: 프런트 관리자 host 진입 UX

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/pages/admin/AdminPages.tsx`
- Create: `frontend/src/app/adminHost.ts`
- Test: `frontend/src/app/__tests__/admin-host.test.tsx`

**Interfaces:**
- Consumes: build-time `VITE_ADMIN_BASE_URL`.
- Produces: `adminUrl(path: string): string` and host-aware redirect behavior.

- [ ] **Step 1: 실패 테스트를 작성한다.**

```tsx
it("moves a general-host admin route to the configured admin host", () => {
  expect(adminUrl("/admin/policies")).toBe("https://admin.dev.example/admin/policies");
});
```

- [ ] **Step 2: 최소 utility와 redirect를 구현한다.**

일반 host의 `/admin` route는 `window.location.assign(adminUrl(path))`로 이동한다. 관리자 host의 `/`은 `/admin`으로 route redirect한다. API endpoint는 상대 `/api`를 유지한다.

- [ ] **Step 3: 테스트와 타입 검사를 실행한다.**

Run: `cd frontend && npx vitest run src/app/__tests__/admin-host.test.tsx && npm run typecheck`

- [ ] **Step 4: 커밋한다.**

```bash
git add frontend/src/app frontend/src/pages/admin
git commit -m "feat: direct admin routes to the admin host"
```

### Task 4: Access와 OAuth 운영 설정 문서화

**Files:**
- Create: `docs/deployment-cicd/admin-subdomain-cloudflare-access-runbook.md`
- Modify: `docs/deployment-cicd/09-release-checklist.md`

**Interfaces:**
- Consumes: Cloudflare Access application, Cloudflare One-time PIN, allow-email policy.
- Produces: 승인된 운영자만 admin host에 접근시키는 실행·회수 절차.

- [ ] **Step 1: Cloudflare Access runbook을 작성한다.**

Access application 대상은 `admin.travel-hunter.co.kr/*`와 `admin.travel-hunter.co.kr/*`이다. Cloudflare One-time PIN를 identity provider로 사용하고, allow rule은 운영자 이메일의 exact match만 허용한다. `/github-webhook/`은 이 application에 포함하지 않는다.

- [ ] **Step 2: 계정 수명주기 절차를 작성한다.**

권한 부여는 Access allow list 추가와 DB `role='admin'` 부여가 모두 필요하다. 회수는 Access allow list 제거를 먼저 하고 DB admin 역할을 제거한다. 비상 접근은 별도 운영 Access 허용 이메일에 MFA를 적용한다.

- [ ] **Step 3: OAuth/CORS 배포 체크를 추가한다.**

관리자 host에서 OAuth 로그인까지 지원할 경우 Google/Kakao 허용 redirect URI, CORS origin, `VITE_ADMIN_BASE_URL`, `ADMIN_DOMAIN`을 함께 검증한다.

- [ ] **Step 4: 커밋한다.**

```bash
git add docs/deployment-cicd/admin-subdomain-cloudflare-access-runbook.md docs/deployment-cicd/09-release-checklist.md
git commit -m "docs: add admin subdomain access runbook"
```

### Task 5: 격리 환경 통합 검증

**Files:**
- Test: `frontend/src/app/__tests__/admin-host.test.tsx`
- Test: `backend/tests/test_config.py`
- Test: Caddy route smoke script or documented curl commands

- [ ] **Step 1: 일반/관리자 host redirect를 확인한다.**

Run from a disposable Compose stack:

```bash
curl -I -H 'Host: dev.example.test' http://caddy/admin
curl -I -H 'Host: admin.dev.example.test' http://caddy/
```

Expected: 첫 요청은 관리자 `/admin` host로 302, 두 번째 요청은 `/admin`으로 302.

- [ ] **Step 2: 앱 권한 회귀를 확인한다.**

Run: `cd backend && python -m pytest tests/test_admin_routes.py tests/test_ops_routes.py -q`

Expected: 비관리자 요청은 거부되고 관리자 요청만 성공.

- [ ] **Step 3: 전체 정적 검증을 실행한다.**

Run:

```bash
cd backend && python -m pytest tests/test_config.py -q
cd ../frontend && npm run typecheck && npm run build && npm run test:mojibake
git diff --check
```

- [ ] **Step 4: merge-ready CHECKLIST를 최소 갱신하고 커밋한다.**

```bash
git add CHECKLIST.md
git commit -m "docs: record admin subdomain verification"
```

### Task 6: Cloudflare/AWS 변경과 배포 게이트

**Files:**
- No repository secret files.
- Modify only approved non-secret deployment documentation if a deployment fact changes.

- [ ] **Step 1: production change approval을 확보한다.**

변경 대상은 Cloudflare DNS/Tunnel public hostname, Access application/policy, Cloudflare One-time PIN allowlist/redirect URI, AWS reverse-proxy host routing이다. 각 비밀값은 화면이나 로그에 출력하지 않는다.

- [ ] **Step 2: 개발 환경에서 Access를 적용한다.**

`admin.travel-hunter.co.kr/*`만 Access로 보호하고 일반 서비스·Jenkins·GitHub webhook 경로에는 적용하지 않는다.

- [ ] **Step 3: 배포 후 smoke를 수행한다.**

운영자 Access 허용 이메일은 Access → 앱 login → `/admin` 성공, 허용되지 않은 계정은 Access 차단, 앱 비관리자 계정은 API 403을 각각 확인한다.

- [ ] **Step 4: 운영 전환 전에 production host를 같은 방식으로 추가한다.**

`admin.travel-hunter.co.kr`을 별도 Access application으로 만들고, 개발 검증이 끝나기 전에는 일반 사용자 도메인의 `/admin`을 제거하지 않는다.
