# Timestamp inventory for DB timezone impact

Purpose: planning inventory for the local DB timezone pass. This is an inventory artifact only; it does not implement production migration or runtime changes.

Basis:
- Local schema snapshot used as the authoritative local evidence set: `backend/tests/fixtures/final_alembic_head_timestamp_columns.sql`.
- Fixture source: current tracked offline Alembic SQL generated with `cd backend && .venv/bin/alembic upgrade head --sql` after rebasing this pass onto `origin/develop`.
- Checked-in schema reference for fallback comparison: `docs/db-schema-current.sql`.
- The local develop-head fixture for this pass contains 46 `timestamp without time zone` columns.

Bucket rules:
- `adjust`: strong UTC-naive instant provenance and safe for local planning.
- `keep`: security / expiry / auth token / OTP / password reset / invite / signup / consent / audit timestamps or otherwise explicitly not safe to auto-adjust.
- `investigate`: insufficient proof for a safe adjust decision.

Completeness check rules:
- Every source-listed `timestamp without time zone` column appears exactly once.
- Each row has exactly one bucket: `adjust`, `keep`, or `investigate`.
- Every row includes an evidence source reference.
- Security / expiry / signup / consent / audit columns must never enter `adjust` unless an explicit approval marker exists; none exists for this pass.
- Date/time columns are out of scope for this inventory; only timestamp columns belong here.
- The completeness check fails if any timestamp column is missing, duplicated, bucketed twice, or lacks provenance.

Source query used / recommended:
- Used for this planning artifact: `python3` scan of `backend/tests/fixtures/final_alembic_head_timestamp_columns.sql` for `TIMESTAMP WITHOUT TIME ZONE` declarations.
- Reproduce fixture: `cd backend && .venv/bin/alembic upgrade head --sql > tests/fixtures/final_alembic_head_timestamp_columns.sql`.
- Recommended live DB query: `SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE data_type = 'timestamp without time zone' ORDER BY table_name, ordinal_position;`
- Fallback checked-in-doc query: `rg -n "timestamp without time zone" docs/db-schema-current.sql`

Summary:
- adjust: 7
- keep: 22
- investigate: 17
- total: 46

| table | column | bucket | evidence source | rationale | approval marker |
| --- | --- | --- | --- | --- | --- |
| `users` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:21 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `users` | `updated_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:22 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `policies` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:43 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `auth_refresh_tokens` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:54 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `auth_refresh_tokens` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:55 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `auth_refresh_tokens` | `revoked_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:56 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `social_accounts` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:69 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `trips` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:93 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `trips` | `updated_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:94 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `trip_members` | `joined_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:129 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `trip_policies` | `added_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:140 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `trip_invites` | `accepted_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:152 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `trip_invites` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:153 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `trip_invites` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:154 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `recommendations` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:171 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `user_saved_policies` | `saved_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:193 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `user_notification_settings` | `created_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:224 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `user_notification_settings` | `updated_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:225 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `users` | `phone_verified_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:237 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `notification_deliveries` | `scheduled_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:250 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `notification_deliveries` | `sent_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:251 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `notification_deliveries` | `failed_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:252 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `notification_deliveries` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:253 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `notification_deliveries` | `updated_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:254 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `password_reset_tokens` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:273 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `password_reset_tokens` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:274 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `password_reset_tokens` | `used_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:275 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `external_source_records` | `last_fetched_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:332 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `external_source_records` | `last_verified_at` | `adjust` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:333 | Approved UTC-naive operational instant provenance; included in the guarded local-only data-shift allowlist. | — |
| `external_source_records` | `created_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:335 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `external_source_records` | `updated_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:336 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `phone_verification_codes` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:364 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `phone_verification_codes` | `verified_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:366 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `phone_verification_codes` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:367 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `policies` | `normalized_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:394 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `policies` | `last_verified_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:396 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `policies` | `updated_at` | `investigate` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:440 | Runtime provenance is not proven strongly enough for automatic adjustment in this local pass. | — |
| `admin_audit_logs` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:451 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_signups` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:500 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_signups` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:501 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `users` | `terms_accepted_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:539 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `users` | `privacy_accepted_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:545 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_signups` | `terms_accepted_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:551 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_signups` | `privacy_accepted_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:557 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_social_signups` | `created_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:570 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
| `pending_social_signups` | `expires_at` | `keep` | local schema snapshot: backend/tests/fixtures/final_alembic_head_timestamp_columns.sql:571 | Security, expiry, auth, invite, OTP, signup/consent, or audit lifecycle timestamp; never auto-adjust without a separate explicit approval. | — |
