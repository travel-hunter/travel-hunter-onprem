# Local UX Spec: Auth And Account Recovery

## Goal

Complete the local user experience for account access: sign up, log in, recover access, and use OAuth entry points without relying on undeclared production deployment work.

Domain-dependent public-provider smoke is deferred, but local OAuth smoke is supported once the user creates provider apps and supplies localhost credentials. The immediate implementation priority is local behavior that can be completed without `travel-hunter.co.kr`, public DNS, sender-domain authentication, or staging infrastructure.

## User Experience Boundary

This spec covers flows a local user can directly attempt from the app:

- Email/password login
- Sign up
- Password reset request and reset token UX
- Kakao OAuth button, missing-env UX, and local credential smoke command
- Google OAuth button, missing-env UX, and local credential smoke command
- Removed contact/OTP/notification settings surface stays absent from local UX.

Deployment, public HTTPS, Cloudflare Tunnel, real SMTP sender-domain smoke, and CI/CD are not part of the immediate implementation scope.

## Current State

Implemented or partially implemented:

- Email/password sign up and login are implemented through `AppDataApi` and backend auth routes.
- Password reset screens and backend token logic exist.
- Kakao/Google OAuth start and callback routes exist.
- OAuth account linking requires verified provider email for same-email auto-link.
- Google requires `email_verified=true`; Kakao can create a `kakao_{providerId}@oauth.local` account when email is absent or unverified.
- OAuth callback failures redirect to `/oauth/callback?error={code}&redirect={safePath}` with closed error codes.
- MyPage contact and OTP request/confirm UI has been removed from the active product surface.

Domain-dependent blockers deferred to later:

- Password reset email smoke requires SMTP env and public base URL.
- Kakao OAuth live browser smoke requires a Kakao provider app, client id, secret, and localhost redirect URI.
- Google OAuth live browser smoke requires a Google OAuth client id, secret, and localhost redirect URI.
- Real phone OTP smoke is not a deferred requirement because the contact/OTP surface has been removed from the active product contract.

## Immediate Missing UX To Complete Locally

No immediate local UX gap is currently tracked for this spec. The latest implementation/status inventory records domain-independent auth/account recovery UX and OAuth missing-env/callback failure messaging as implemented locally.

Keep future updates focused on local UX regressions or newly discovered local gaps; do not pull domain-dependent provider smoke into this immediate section.

## Deferred Domain-Dependent UX

1. Password reset email should complete from request to inbox/link to successful password change in a local or local-like environment.
2. Kakao OAuth should complete a full start/callback/login smoke with configured localhost redirect values after the user supplies provider credentials.
3. Google OAuth should complete a full start/callback/login smoke with configured localhost redirect values after the user supplies provider credentials.
4. Brevo sender-domain authentication and `no-reply@travel-hunter.co.kr` password reset delivery should be verified after DNS setup is ready.

## Immediate Local Completion Criteria

- Local password reset request/reset-token screens handle configured and unconfigured local states without depending on real email delivery. Completed locally per `docs/implemented-feature-spec.md`.
- Kakao and Google login entry/callback failures show user-safe missing-provider or email-policy messages instead of blank or stuck screens. Completed locally per `docs/implemented-feature-spec.md`.
- `scripts/oauth_local_smoke.py {kakao|google}` validates configured start-route readiness without printing secrets when localhost provider credentials are supplied.
- Removed contact/OTP/notification settings controls and APIs do not appear in the local account UX.

## Deferred Completion Criteria

- `POST /api/auth/password-reset/request` succeeds for an existing email with configured Brevo SMTP and produces a usable reset link.
- Kakao login button reaches provider authorization and returns to `/oauth/callback` with registered localhost redirect values.
- Google login button reaches provider authorization and returns to `/oauth/callback` with registered localhost redirect values.
- No deferred phone contact/OTP criterion remains; reintroducing notifications would require a new product/API contract.

## Local OAuth Setup And Smoke

Provider app setup is outside repository authority, but the app is ready for these localhost redirect URIs:

- Kakao: `http://127.0.0.1:8000/api/auth/oauth/kakao/callback`
- Google: `http://127.0.0.1:8000/api/auth/oauth/google/callback`

Required backend env:

- `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
- `TRAVEL_HUNTER_PUBLIC_BASE_URL` or the default frontend base URL expected by backend settings

Provider account policy:

- Google same-email sign-in/link requires `email_verified=true`.
- Kakao same-email sign-in/link requires `kakao_account.is_email_verified=true` and `is_email_valid` not false.
- Kakao accounts without a usable verified email use an internal `kakao_{providerId}@oauth.local` email and do not attach to an existing email/password account.

Smoke commands after env is present:

```bash
python scripts/oauth_local_smoke.py kakao
python scripts/oauth_local_smoke.py google
```

The script checks that `/api/auth/oauth/{provider}/start?redirect=/home` returns a provider redirect and state cookie. It does not print client secrets or tokens. After a browser login succeeds, verify:

```bash
curl -i -X POST http://127.0.0.1:8000/api/auth/refresh --cookie 'travel_hunter_refresh=<browser-cookie>'
psql "$DATABASE_URL" -c "select provider, provider_id, user_id from social_accounts order by id desc limit 5;"
```

## Relevant Files And APIs

Frontend:

- `frontend/src/pages/AuthPages.tsx`
- `frontend/src/pages/MyPage.tsx`
- `frontend/src/app/session.tsx`
- `frontend/src/api/appDataApi.ts`
- `frontend/src/api/backendApi.ts`
- `frontend/src/api/types.ts`

Backend:

- `backend/app/api/routes/auth.py`
- `backend/app/services/auth.py`
- `backend/app/services/oauth.py`
- `backend/app/services/email.py`
- `backend/app/api/routes/me.py`

Contracts and references:

- `docs/mvp-api-contract.md`
- `docs/implemented-feature-spec.md`
- `docs/screen-feature-status-screens.md`
- `docs/brevo-cloudflare-email-guide.md`

## Non-Goals

- Do not implement Cloudflare/public deployment in this spec.
- Do not treat domain-dependent provider smoke as part of the immediate local completion scope.
- Do not change the auth DTO shape without updating `docs/mvp-api-contract.md`.
- Do not commit real provider secrets.
