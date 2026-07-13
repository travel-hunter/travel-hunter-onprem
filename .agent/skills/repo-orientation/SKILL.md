name: repo-orientation
description: Use before non-trivial Travel Hunter work to understand current state, constraints, files, tests, and risks.

# Goal

Start from the actual repository state instead of assumptions.

# When To Use

- At the beginning of a new coding task.
- Before changing API, UI, backend behavior, infrastructure, or docs.
- After resuming work in a dirty worktree.

# Procedure

1. Run `git status --short` from the repo root.
2. Read `AGENTS.md`.
3. Read the nearest nested `AGENTS.md` for the target area.
4. Read `PLANS.md`.
5. Read `docs/current-work-spec.md` and `docs/mvp-api-contract.md` when API or app behavior is involved.
6. Inspect only the relevant implementation files before editing.
7. Identify whether the work requires another skill.

# Output

Produce or keep in working notes:

- Current state summary.
- Files likely to change.
- Contract, test, and eval files that must stay synchronized.
- Validation commands to run.
- Risks or blockers.

# Quality Bar

The implementer should know exactly which code paths and docs are authoritative before making changes.
