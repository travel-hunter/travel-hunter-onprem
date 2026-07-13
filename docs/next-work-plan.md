# Travel Hunter Next Work Plan

> Status: active execution queue.
> Use this document as the source of truth for current next-work priority. `docs/specs/spec-index.md` is a local UX spec index. Weekend Public v1 work has explicitly reprioritized external dependency, deployment, and release-gate evidence ahead of lower-priority local polish.

## Current Priority

The current priority is Weekend Public v1 release execution for `travel-hunter.co.kr`. External dependency verification comes first because Public v1/Release Candidate cannot be claimed without public DNS/Cloudflare or equivalent HTTPS routing, SMTP/Brevo sender evidence, Google/Kakao OAuth public redirect smoke, policy collection/normalization/exposure evidence, and minimum log visibility.

Current release-grade evidence:

- Development domain evidence has improved on 2026-06-09: `dev.travel-hunter.co.kr` routes through Cloudflare Tunnel to Caddy, `/api/health` returns DB connected, Brevo SMTP password-reset smoke passed after credential rotation, Google OAuth browser login passed, Kakao OAuth browser login passed, Kakao OAuth now requests only `account_email`, and existing Kakao placeholder email accounts upgrade to verified Kakao email on the next successful login when no conflict exists.
- Public v1 is still not proven for the production domain. Earlier 2026-06-09 public smoke for `travel-hunter.co.kr` failed because DNS did not resolve from the local environment; `/` and `/api/health` could not be reached.
- Release Candidate is not currently proven for production. The dev environment has provider smoke evidence, but production-server access, production runtime env, production Cloudflare route, production OAuth redirect URI evidence, production policy collection/quality smoke, and production logs are still missing.
- Local invite URL alignment and policy collection release-gate tests have been implemented and targeted validations passed, including local stay_discount/반값여행/travelmonth parser and deterministic trip recommendation regressions. Policy collection also has an admin manual-run endpoint and dashboard button for local/operator execution, but those local/dev checks do not replace production-domain/provider evidence.

Recently completed local UX work:

- Frontend validation baseline is green in the current WSL/local environment.
- Domain-independent Auth and Account Recovery UX.
- Policy detail no-link CTA clarity.
- Policy detail info-only action blocking and policy-to-trip success feedback.
- MyPage saved/applied policy summary consistency after policy save, remove, link, and unlink actions.
- Policy To Trip Linking local runtime smoke for a normalized policy across save, unsave, link, trip-detail display, unlink, and MyPage refresh.
- Map bottom-sheet place detail opens an inspectable local detail dialog with day context, address, memo, coordinates, category, and Kakao Maps link.
- Place Search/Add local UX from the itinerary editing flow uses recommendation candidates through `AppDataApi` and preserves Kakao place metadata when saving.
- Kakao Local candidate smoke returns non-empty representative candidates with configured env, and catalog fallback remains non-empty for the same representative areas without Kakao Local credentials.
- `/ai-results` distinguishes fresh Kakao-backed candidates from saved recommendation-summary fallback with API `sourceType`, source copy, and candidate badges.

Immediate sequence for tomorrow:

1. Production/development server split: confirm which machine is the development server and which is the production server, then clone/update the repo on the development server instead of continuing from a personal WSL environment.
2. Move dev runtime evidence to the development server: create runtime-only `deploy/.env.prod` from the safe example, verify Cloudflare Tunnel token, Brevo SMTP, Google OAuth, Kakao OAuth `account_email`, Kakao Maps JS key/domain, Kakao Local REST key, CORS, secure refresh cookie, and public base URL without printing secrets.
3. Reproduce dev smoke on the development server: `docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml config`, build/up, Alembic upgrade, `/api/health`, Google browser login, Kakao browser login, Kakao placeholder-email upgrade, SMTP password-reset smoke, and Kakao Maps screen smoke.
4. Run admin-authenticated `/api/ops/external-collection`, optional `/api/ops/external-collection/run`, and `/api/ops/external-collection/quality` smoke on the deployed runtime with an approved bearer token, then record pass/fail without exposing the token.
5. Only after the development server is stable, prepare production `travel-hunter.co.kr`: DNS/Tunnel public hostname, production OAuth redirect URIs, production env, production smoke, and logs.
6. Keep local regression gates green while making release fixes: targeted backend pytest, backend-harness Vitest, `git diff --check`, UTF-8 scan, and then full frontend/backend gates before final release-grade claim.

## Active Planning Sources

- `docs/specs/spec-index.md`
- `docs/specs/local-ux-auth-account.md`
- `docs/specs/local-ux-policy-trip-linking.md`
- `docs/specs/local-ux-place-discovery.md`
- `docs/implemented-feature-spec.md`
- `docs/mvp-api-contract.md`
- `docs/db-schema-current.md`
- `docs/db-schema-current.sql`

## Deferred Work

The following work remains lower priority than release blockers:

- Jenkins or other CI/CD automation.
- Policy list server search/pagination until local policy volume outgrows client filtering.
- 친구 초대 email 발송은 로컬 구현/계약/테스트가 완료됐고, 다음 확인은 SMTP credential이 주입된 개발서버에서 실제 inbox 수신 smoke다. SMS/Kakao 초대 발송은 현재 제품 범위에서 제외됐다.
- 일정 상세 장소 add/update/move/delete 저장 충돌은 로컬에서 `Trip.revision`/`expectedRevision` optimistic conflict 처리까지 구현됐다. 정책 연결/상태 변경 conflict 처리는 후속 범위다.

## Guardrails

- Do not reintroduce runtime mock mode.
- Keep frontend pages behind the `AppDataApi` boundary.
- Keep API DTO fields in `camelCase` and database fields in `snake_case`.
- Keep trip route handles as numeric string `Trip.id`; do not add `trips.slug`.
- Do not commit secrets, real `.env` files, tunnel tokens, DB passwords, OAuth secrets, SMTP passwords, or auth secrets.
