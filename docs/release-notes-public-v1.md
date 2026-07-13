# Weekend Public v1 Release Notes Draft

Date: 2026-06-09

## Current release grade

- **Current grade: No Release.**
- `travel-hunter.co.kr` did not resolve in local public smoke on 2026-06-09.
- Development domain `dev.travel-hunter.co.kr` has smoke evidence for Cloudflare Tunnel routing, backend health/DB, Brevo SMTP, Google OAuth, Kakao OAuth with `account_email`, Kakao Local runtime config, and Kakao placeholder-email upgrade on login.
- Production domain OAuth, SMTP/Brevo, Cloudflare Tunnel, production env, and classroom-server runtime evidence remain missing or unproven.

## Included local capabilities

- Invite links use the public frontend base URL shape `/invites/{token}/accept`.
- Logged-out invite receivers return to the original invite after login or signup.
- Invalid or expired invite links show a re-invite guidance state.
- Policy collection quality and normalized public policy exposure are covered by backend tests.
- `/ai-results` distinguishes fresh Kakao-backed candidates from saved-summary fallback with API `sourceType` and UI source badges.
- Kakao OAuth requests `account_email` only; existing internal `kakao_{providerId}@oauth.local` emails upgrade to verified Kakao email on the next successful login when no conflict exists.

## Kakao Local and ratings posture

- Kakao Local REST is a **recommendation quality gate**, not an absolute release blocker, when catalog or saved-summary fallback remains usable.
- If live Kakao Local candidate retrieval is degraded or unavailable, release notes must say **degraded recommendation quality** rather than claiming full live-candidate success.
- Place ratings/reviews are omitted for v1 because the official Kakao Local response used by this app does not expose ratings/reviews.
- Do not invent, scrape, infer, or display placeholder ratings.

## Public release blockers

- Public DNS and HTTPS for `travel-hunter.co.kr`.
- Production runtime env on the host, including public API base URL, CORS, secure cookies, OAuth callbacks, SMTP/Brevo, Kakao Maps JavaScript domain, and Kakao Local REST key when claiming live Kakao recommendations.
- Google OAuth and Kakao OAuth browser login smoke on the public domain.
- SMTP password-reset email smoke and friend-invite email smoke when invite email is included in the target release grade.
- Public Kakao Maps JavaScript rendering smoke on the configured public domain.
- Production backend/proxy/tunnel logs and Docker/Compose service status evidence.

## Evidence to attach before upgrading grade

- `curl -fsS https://travel-hunter.co.kr/api/health`.
- Public browser smoke for login, policies, trip create/detail/edit, invite accept, and `/ai-results`.
- Bearer-authenticated `/api/ops/external-collection` and `/api/ops/external-collection/quality` responses without printing the bearer token.
- Production logs with secrets redacted.
- Provider-console screenshots or owner confirmation for redirect URI/domain registration, without exposing secrets.
