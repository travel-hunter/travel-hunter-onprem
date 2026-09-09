# Policy Expiration Visibility Design

## Problem

Public policy visibility currently depends only on `policies.status = 'active'`.
On 2026-09-09 the development API returns 139 policies, including 87 policies
whose canonical `end_date` is 2026-08-31. The frontend labels those rows as
closed but still renders them in the policy catalog.

Manual collection did not create this defect. A collector can refresh source
state, but time continues to pass while collection is disabled or failing. A
public request therefore needs an independent date-based visibility guard.

## Approved Product Rule

- A policy is publicly visible only when its status is active and its canonical
  `end_date` is absent or is on/after the current KST calendar date.
- A policy remains visible through its entire canonical deadline date and
  becomes unavailable at 00:00 KST on the following day.
- Expired policies are hidden from every user policy path, even when previously
  saved or attached to a trip.
- Rows and relationship records are preserved. Expiration must not delete policy,
  save, or trip-link data.
- Admin/history queries continue to expose preserved rows.
- The rule uses only canonical `policies.end_date` and
  `external_source_records.end_date`. It does not infer dates from display text.

## Architecture

### Immediate request-time guard

The backend owns visibility. Repository queries for public policy lists, saved
policies, applied policies, photo backfill candidates, and slug lookup add the
deadline predicate. Object-level checks used by detail, aliases, saving, and
trip attachment use the same KST date rule.

The frontend does not add a second independent expiration filter. This prevents
different browser clocks and stale clients from disagreeing with the API.

### Future collection integration

External source promotion/deactivation selection uses the same deadline rule.
When automatic collection is enabled, an expired source record is selected for
deactivation and its materialized policy can be persisted as hidden by the
existing normalization process.

The request-time guard remains mandatory after automation is enabled. It covers
the interval between midnight and the next collector run, disabled schedulers,
collector failures, and stale source status values.

## Data and API Impact

- No database rows are deleted.
- No Alembic migration is required.
- No DTO field changes are required.
- Existing expired slugs return 404 through public detail routes.
- New save and trip-attachment attempts for expired slugs are rejected through
  the existing not-found behavior.
- Existing saved/applied policy list endpoints omit expired policies while their
  relationship rows remain stored.
- Admin endpoints retain their current status-based behavior.

## Test Contract

Use injected dates or patched date providers; never depend on the machine's
wall clock in tests.

- `end_date = yesterday`: hidden.
- `end_date = today`: visible.
- `end_date = tomorrow`: visible.
- `end_date = None`: visible.
- `status = hidden`: hidden regardless of date.
- UTC/KST boundary: an instant that is still the previous UTC date but already
  the next KST date uses the KST date.
- Public list, detail, saved/applied lists, recommendations, aliases, and source
  promotion/deactivation all obey the rule.
- Admin list continues to include preserved expired rows.

## Automatic Collection Follow-up

Enabling the scheduler is a separate operational change. Before enabling it,
set a realistic minimum parsed-count threshold, choose retry cadence, and prove
one successful and one intentionally failed run on the development pipeline.
No scheduler or production environment setting changes are part of this fix.
