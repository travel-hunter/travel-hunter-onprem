name: api-contract-sync
description: Use whenever Travel Hunter API request, response, route, or DTO shape changes.

# Goal

Keep docs, frontend types, backend schemas, tests, and evals in sync for every API contract change.

# When To Use

- Adding, removing, or renaming an API endpoint.
- Changing request or response fields.
- Changing route params such as `policySlug` or `tripId`.
- Changing optionality, nullability, list shape, or error behavior.

# Required Files To Check

- `docs/mvp-api-contract.md`
- `frontend/src/api/types.ts`
- `frontend/src/api/*Api.ts`
- `backend/app/schemas/*.py`
- `backend/app/api/routes/*.py`
- `backend/app/services/*.py`
- `backend/tests/*.py`
- `.agent/evals/api-contract-golden.json`

# Procedure

1. Identify the current documented contract.
2. Update the contract document first or explicitly confirm it remains unchanged.
3. Update backend Pydantic schemas and route/service behavior.
4. Update frontend TypeScript types and API clients.
5. Update tests and eval artifacts.
6. Run backend and frontend validation relevant to the changed API path.

# Completion Criteria

- Docs, frontend types, backend schemas, tests, and evals agree.
- API DTO fields remain `camelCase`.
- DB/internal fields remain excluded from public responses.
- Any unsupported future behavior is listed as out of scope.
