name: db-migration-plan
description: Use before changing PostgreSQL, SQLAlchemy models, Alembic migrations, or DB-backed repositories.

# Goal

Plan safe persistence changes from the current Alembic schema without breaking the existing API contract.

# When To Use

- Adding or changing SQLAlchemy models.
- Adding or changing Alembic migrations.
- Replacing seed/static assumptions with repositories.
- Changing DB schema or migration strategy.

# Required Sources

- `docs/db-schema-current.md`
- `docs/db-schema-current.sql`
- `docs/mvp-api-contract.md`
- `docs/current-work-spec.md`

# Procedure

1. Compare the current schema reference with the API contract field mapping.
2. Decide migration order before editing models.
3. Define repository/service boundaries that preserve current API response shapes.
4. Plan seed data changes for policies, trips, users, invites, and recommendations when needed.
5. Define rollback expectations and local setup commands.
6. Update docs and env examples before calling the migration work complete.

# Acceptance Criteria

- API DTOs remain stable unless an explicit contract update is made.
- DB fields stay `snake_case`; API fields stay `camelCase`.
- `policies.slug`, `trip_invites`, `users.preferred_regions`, and `trip_*` prefix decisions are preserved.
- Existing frontend smoke flows continue to run against the FastAPI backend through `VITE_API_BASE_URL`.
