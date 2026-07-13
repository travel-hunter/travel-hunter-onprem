name: qa-release-readiness
description: Use before handoff, release readiness review, or closing a major Travel Hunter task.

# Goal

Verify that the branch is explainable, testable, and close to release-ready for the current MVP phase.

# Required Checks

Frontend:

```bash
cd frontend
npm run typecheck
npm test
npm run test:e2e
npm run build
```

Backend:

```bash
cd backend
python -m pytest
```

Compose:

```bash
docker compose -f compose.yaml config
```

# Documentation Checks

- `README.md` and `docs/local-dev-runtime.md` reflect setup and commands.
- `.env.example` files document required variables and safe defaults.
- `docs/mvp-api-contract.md` matches current API shape.
- `PLANS.md` and `CHECKLIST.md` reflect current work state.
- `.agent/evals/api-contract-golden.json` still matches real API shape.
- `docs/deployment-cicd/09-release-checklist.md` still matches release criteria, routes, and tests.

# Output

Provide:

- Release blockers.
- Nice-to-have issues.
- Commands run and results.
- Ready or not-ready judgment.
- Remaining risks.
