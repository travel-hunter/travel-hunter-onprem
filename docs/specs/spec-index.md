# Travel Hunter Spec Index

## Purpose

This index lists the local UX specification documents and separates deferred deployment/CI/CD references from local product completion references. It is a navigation document, not the execution-priority owner.

## Scope Boundary

Local functional completion specs are listed here. Work that requires a purchased domain, DNS propagation, public HTTPS, Cloudflare, external SMTP sender authentication, OAuth provider redirect registration, or staging smoke remains deployment-deferred unless `docs/next-work-plan.md` explicitly reprioritizes it.

## Active Specs

| Document | Status | Role |
| --- | --- | --- |
| [local-ux-auth-account.md](local-ux-auth-account.md) | active | Local auth, account recovery, and OAuth UX completion spec. |
| [local-ux-policy-trip-linking.md](local-ux-policy-trip-linking.md) | active | Local policy discovery, saved policy, official link, and trip linking UX completion spec. |
| [local-ux-place-discovery.md](local-ux-place-discovery.md) | active | Local place detail, map/search, recommendation candidate, and fallback quality UX completion spec. |
| [invite-trip-edit-workflow.md](invite-trip-edit-workflow.md) | active | Concrete friend-invite, invite acceptance, trip-detail edit permission, and future email-invite workflow spec. |
| [policy-collection-local-expansion-review.md](policy-collection-local-expansion-review.md) | active | Review handoff and verification matrix for the policy collection local expansion implementation. |
| [policy-source-artifact-externalization.md](policy-source-artifact-externalization.md) | active | Policy collection raw artifact externalization design starter and phased migration plan. |
| [policies-table-cleanup-phase2.md](policies-table-cleanup-phase2.md) | active | Phase-2 schema cleanup options for policy amount/detail, target condition, links, source canonical keys, and visibility status. |
| [../requirements.md](../requirements.md) | active | Product requirements and acceptance baseline. |
| [../implemented-feature-spec.md](../implemented-feature-spec.md) | active | Implemented feature and conditional-scope inventory. |
| [../next-work-plan.md](../next-work-plan.md) | active | Current next-work execution queue. |
| [../mvp-api-contract.md](../mvp-api-contract.md) | active | API wire contract. |
| [../db-schema-current.md](../db-schema-current.md) | active | Human-readable current DB schema reference. |
| [../db-schema-current.sql](../db-schema-current.sql) | active | SQL schema snapshot. |

## Supporting Gap Scan Docs

These documents are scan-friendly supporting views, not execution-priority owners or second queues. `docs/next-work-plan.md` remains the current execution queue.

| Document | Status | Role |
| --- | --- | --- |
| [local-ux-incomplete-backlog.md](local-ux-incomplete-backlog.md) | supporting | Non-authoritative local UX/screen gap scan; mirrors current queue items, summarizes conditional local UX gaps, and records reference mismatches without owning priority. |

## Reference Docs

| Document | Status | Role |
| --- | --- | --- |
| [../screen-feature-status-screens.md](../screen-feature-status-screens.md) | reference | Screen-by-screen status ledger. |
| [../screen-feature-status-logic.md](../screen-feature-status-logic.md) | reference | Internal logic, collection, fallback, and recommendation status ledger. |
| [../local-dev-runtime.md](../local-dev-runtime.md) | reference | Local runtime commands and environment setup. |
| [../brevo-cloudflare-email-guide.md](../brevo-cloudflare-email-guide.md) | reference | Brevo/Cloudflare password reset email delivery specification. |

## Removed Archive Candidates

These files were removed after confirming their current guidance role is covered by active or reference documents:

| Removed file | Replacement source |
| --- | --- |
| `docs/screen-feature-status-report.md` | `docs/screen-feature-status-screens.md`, `docs/screen-feature-status-logic.md`, and this index. |
| `docs/repo-slimming-work-spec.md` | Completed; repository slimming is reflected in the current repo state and git history. |
| `docs/superpowers/plans/2026-05-28-ai-results-inline-day-selector-compact-copy.md` | `docs/specs/local-ux-place-discovery.md` and current implementation/tests. |
| `docs/superpowers/plans/2026-05-28-ai-results-map-first-redesign.md` | `docs/specs/local-ux-place-discovery.md` and current implementation/tests. |
| `docs/superpowers/plans/2026-05-28-ai-results-preview-day-selector-v3.md` | `docs/specs/local-ux-place-discovery.md` and current implementation/tests. |
| Retired mixed current-work summary document | `docs/implemented-feature-spec.md` for implementation/status inventory, `docs/next-work-plan.md` for execution queue, and this index for document navigation. |

## Deployment Deferred

| Document | Status | Role |
| --- | --- | --- |
| [../deployment-cicd/README.md](../deployment-cicd/README.md) | deployment-deferred | Deployment and CI/CD documentation root. |

Deployment-deferred work includes Cloudflare Tunnel staging, Jenkins CD, production/staging provider smoke, and public HTTPS validation. Keep these out of the local UX completion specs unless a local flow requires a documented placeholder or env boundary.

Domain-dependent deferred work includes Brevo domain authentication, real SMTP password reset email smoke, public OAuth redirect smoke, public map-domain validation, and any flow that requires `travel-hunter.co.kr` DNS to be active.

## Cleanup Rules

1. Do not delete a legacy document until its useful content is represented in an active or reference document.
2. Record removed legacy documents in this index with their replacement source.
3. Keep API shape authority in `docs/mvp-api-contract.md`.
4. Keep DB authority in `docs/db-schema-current.md` and `docs/db-schema-current.sql`.
5. Keep deployment and CI/CD work in `docs/deployment-cicd/` until a later task explicitly reprioritizes it.
