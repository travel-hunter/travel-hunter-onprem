# Production DB Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely migrate the authoritative data from `dev-server` PostgreSQL into the production-local PostgreSQL on `prod-server`, sanitize development-only identities and tokens, verify the restored copy, and cut over with an immediate database-level rollback path.

**Architecture:** Add two tooling-only backend CLIs: one emits a sensitive-safe inventory and integrity report, and one prepares only a `travelhunter_restore_*` database using dry-run-by-default sanitation. Rehearse a PostgreSQL custom-format dump/restore into a temporary production database, then repeat from a write-frozen source and perform a short, controlled database-name swap while retaining the prior production DB. Production keeps its own Compose-local `db:5432` connection; no runtime cross-server DB connection is introduced.

**Tech Stack:** PostgreSQL 16.14, `pg_dump -Fc`, `pg_restore`, Docker Compose, FastAPI backend image, SQLAlchemy 2, Alembic `0035_stay_policy_identity`, pytest, PowerShell/OpenSSH.

**Spec:** `.omx/specs/deep-interview-production-db-data-migration.md`

## Global Constraints

- Do not mutate development or production databases while implementing Tasks 1-4.
- Do not print, copy into Git, or persist in logs any `.env` contents, database passwords, auth secrets, OAuth secrets, SMTP secrets, refresh tokens, or tunnel tokens.
- Never run `python -m app.db.seed` against production.
- Never copy `/var/lib/postgresql/data` or a live Docker volume.
- Do not point production `DATABASE_URL` at `dev-server`; production continues to use `db:5432/travelhunter` inside `prodtravelhunterapp_default`.
- Keep `EXTERNAL_COLLECTION_SCHEDULER_ENABLED=false` throughout this work.
- Keep the production `AUTH_SECRET_KEY` and all production provider configuration; never copy development `.env` files.
- Every dump must be custom format, mode `0600`, non-empty, readable by `pg_restore --list`, and verified with SHA-256 after transfer.
- Require exact preflight equality for the currently static policy baseline: `policies=159`, `external_source_records=88`, and `policy_documents=16`. Any difference stops the operation for explanation. For other source tables, review every delta from the recorded baseline and treat a 30% difference as an unconditional stop rather than an acceptance threshold.
- Stop before each production mutation gate: rehearsal artifact creation, final write freeze, sanitation apply, database-name swap, and credential rotation.
- Do not delete the previous production database or any verified dump during the stabilization window.
- Do not promote an administrator as part of the data transfer; all 13 source users currently have role `user`, and administrator designation requires a separate approved identity decision.
- Do not merge or push to `develop`, and do not change either Jenkins job's branch/trigger configuration, during the final write-freeze window. A development deployment can recreate the stopped backend and re-open writes.
- Do not assume migrated OAuth identities are portable. Development and production use different Kakao and Google client identifiers. Google `sub` is provider-stable, but Kakao user IDs are app-specific; the approved Kakao re-link/preservation strategy must be recorded before cutover.

## File Structure

- Create `backend/app/scripts/production_db_inventory.py`: sensitive-safe database inventory, seed-impact, orphan, Alembic, and sequence checks; supports targeting a sibling database without exposing credentials.
- Create `backend/tests/test_production_db_inventory.py`: unit tests for public output, counts, seed-impact reporting, and active-database target validation.
- Create `backend/app/scripts/prepare_production_snapshot.py`: dry-run-by-default removal of known seed identities/dependencies and transient authentication state from a restored sibling database.
- Create `backend/tests/test_prepare_production_snapshot.py`: regression tests for dry-run immutability, apply behavior, real-user preservation, dependent-row cleanup, and active-database refusal.
- Create `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`: exact read-only, rehearsal, final cutover, validation, rollback, and credential-rotation commands.
- Modify `CHECKLIST.md`: only after an actual rehearsal or cutover, replace stale current status with concise evidence and active risks.

---

## Execution Prerequisite: Start from current `origin/develop`

The planning workspace was six commits behind `origin/develop` at final review. Preserve this plan first, then fetch and create a new isolated feature worktree from the current `origin/develop`. Bring only this plan/spec into that worktree; do not carry unrelated root-worktree changes. Before Task 1, repeat repository orientation and confirm that the ORM schema, Alembic head, Compose topology, container names, and Jenkins behavior assumed below still match. Any mismatch requires a plan update before implementation.

---

### Task 1: Add a sensitive-safe production database inventory CLI

**Files:**
- Create: `backend/app/scripts/production_db_inventory.py`
- Test: `backend/tests/test_production_db_inventory.py`

**Interfaces:**
- Consumes: `app.core.config.settings.database_url`, SQLAlchemy `Session`, current ORM tables, `alembic_version`.
- Produces: `collect_snapshot_inventory(db: Session) -> SnapshotInventory`, `database_url_for_name(database_name: str, *, base_url: str | None = None) -> str`, and `main(argv: list[str] | None = None) -> int`.
- Output contract: UTF-8 JSON containing only revision, table counts, known-seed impact counts, orphan counts, and sequence lag names; no email, nickname, provider ID, token hash, URL password, or row payload.

- [ ] **Step 1: Write the target-database URL and safety tests**

```python
def test_database_url_for_name_changes_only_database() -> None:
    result = inventory.database_url_for_name(
        "travelhunter_restore_20260830",
        base_url="postgresql+psycopg://travelhunter:secret@db:5432/travelhunter",
    )

    parsed = make_url(result)
    assert parsed.host == "db"
    assert parsed.port == 5432
    assert parsed.username == "travelhunter"
    assert parsed.password == "secret"
    assert parsed.database == "travelhunter_restore_20260830"


@pytest.mark.parametrize("database_name", ["travelhunter", "postgres", "bad-name", ""])
def test_database_url_for_name_rejects_active_or_invalid_database_names(
    database_name: str,
) -> None:
    with pytest.raises(ValueError):
        inventory.database_url_for_name(database_name)
```

- [ ] **Step 2: Run the URL tests and verify RED**

Run:

```bash
cd backend
python -m pytest tests/test_production_db_inventory.py -k database_url_for_name -q
```

Expected: FAIL because `production_db_inventory` and `database_url_for_name` do not exist.

- [ ] **Step 3: Implement strict sibling-database targeting**

```python
RESTORE_DATABASE_PATTERN = re.compile(r"^travelhunter_restore_[a-zA-Z0-9_]+$")


def database_url_for_name(
    database_name: str,
    *,
    base_url: str | None = None,
) -> str:
    if not RESTORE_DATABASE_PATTERN.fullmatch(database_name):
        raise ValueError("database name must use the travelhunter_restore_ prefix")
    return make_url(base_url or settings.database_url).set(database=database_name).render_as_string(
        hide_password=False
    )
```

Do not print the returned URL.

- [ ] **Step 4: Write inventory tests with seed and real-user fixtures**

The fixture creates:

```text
2 users: one known seed email and one real test email
2 trips: one owned by each user
1 refresh token for each user
1 social account for the real user
1 policy, 1 external source record, 1 policy document
```

After `Base.metadata.create_all(engine)`, create the Alembic marker used by the inventory query:

```python
db.execute(text("CREATE TABLE alembic_version (version_num varchar(64) PRIMARY KEY)"))
db.execute(
    text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
    {"version": "0035_stay_policy_identity"},
)
db.commit()
```

Assert:

```python
result = inventory.collect_snapshot_inventory(db)
payload = result.to_public_dict()

assert payload["tableCounts"]["users"] == 2
assert payload["tableCounts"]["trips"] == 2
assert payload["alembicVersion"] == "0035_stay_policy_identity"
assert payload["seedImpact"]["users"] == 1
assert payload["seedImpact"]["ownedTrips"] == 1
assert payload["seedImpact"]["refreshTokens"] == 1
assert payload["orphanCounts"] == {
    "tripDays": 0,
    "tripPlaces": 0,
    "tripMembersTrip": 0,
    "tripMembersUser": 0,
    "tripPoliciesTrip": 0,
    "tripPoliciesPolicy": 0,
    "savedPoliciesUser": 0,
    "savedPoliciesPolicy": 0,
    "tripInvitesTrip": 0,
    "tripInvitesCreator": 0,
    "recommendationsUser": 0,
    "recommendationsTrip": 0,
}
serialized = json.dumps(payload, ensure_ascii=False)
assert "test.user@example.com" not in serialized
assert "real-user@example.com" not in serialized
assert "provider-id" not in serialized
assert "refresh-token" not in serialized
```

- [ ] **Step 5: Run the inventory tests and verify RED**

Run:

```bash
cd backend
python -m pytest tests/test_production_db_inventory.py -q
```

Expected: FAIL because inventory collection is not implemented.

- [ ] **Step 6: Implement `SnapshotInventory` and read-only queries**

Use an immutable dataclass with these exact public keys:

```python
@dataclass(frozen=True)
class SnapshotInventory:
    alembic_version: str
    table_counts: dict[str, int]
    seed_impact: dict[str, int]
    orphan_counts: dict[str, int]
    lagging_sequences: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "alembicVersion": self.alembic_version,
            "tableCounts": self.table_counts,
            "seedImpact": self.seed_impact,
            "orphanCounts": self.orphan_counts,
            "laggingSequences": list(self.lagging_sequences),
        }
```

Count all 19 ORM tables listed in `backend/app/models/tables.py`. Seed impact must use only the fixed email set from `backend/app/data/seed.py` and return aggregate counts. PostgreSQL sequence validation must compare each owned sequence value to its table `MAX(id)` without including row data in output.

- [ ] **Step 7: Add the CLI with JSON-only stdout**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name", required=True)
    args = parser.parse_args(argv)
    engine = create_engine(database_url_for_name(args.database_name), pool_pre_ping=True)
    with Session(engine) as db:
        payload = collect_snapshot_inventory(db).to_public_dict()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
cd backend
python -m pytest tests/test_production_db_inventory.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the inventory CLI**

```bash
git add backend/app/scripts/production_db_inventory.py backend/tests/test_production_db_inventory.py
git commit -m "Add production database inventory guard"
```

---

### Task 2: Add dry-run snapshot sanitation with active-DB refusal

**Files:**
- Create: `backend/app/scripts/prepare_production_snapshot.py`
- Test: `backend/tests/test_prepare_production_snapshot.py`

**Interfaces:**
- Consumes: `database_url_for_name()` from Task 1 and the current SQLAlchemy models.
- Produces: `prepare_production_snapshot(db: Session, *, apply: bool = False) -> SnapshotPreparationResult` and `main(argv: list[str] | None = None) -> int`.
- Mutation boundary: only a database name matching `travelhunter_restore_*`; default is rollback-only dry run; `--apply` commits.

- [ ] **Step 1: Write the dry-run regression test**

Create a fixture with one seed owner, one real owner, one seed-owned trip, one real-owned trip, a seed membership and seed-created invitation on the real-owned trip, a recommendation for the seed-owned trip, two refresh tokens, one pending signup, one pending social signup, and one real social account.

```python
before = snapshot_counts(db)
result = prepare_production_snapshot(db, apply=False)
db.rollback()
after = snapshot_counts(db)

assert result.seed_users == 1
assert result.seed_owned_trips == 1
assert result.refresh_tokens == 2
assert result.pending_signups == 1
assert result.pending_social_signups == 1
assert after == before
```

- [ ] **Step 2: Run the dry-run test and verify RED**

Run:

```bash
cd backend
python -m pytest tests/test_prepare_production_snapshot.py -k dry_run -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Write apply-mode preservation tests**

```python
result = prepare_production_snapshot(db, apply=True)
db.commit()

assert db.scalar(select(func.count()).select_from(User)) == 1
assert db.scalar(select(User.email)) == "real-user@example.com"
assert db.scalar(select(func.count()).select_from(Trip)) == 1
assert db.scalar(select(Trip.title)) == "real trip"
assert db.scalar(select(func.count()).select_from(SocialAccount)) == 1
assert db.scalar(select(func.count()).select_from(AuthRefreshToken)) == 0
assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 0
assert db.scalar(select(func.count()).select_from(PendingSignup)) == 0
assert db.scalar(select(func.count()).select_from(PendingSocialSignup)) == 0
assert result.seed_users == 1
assert result.seed_owned_trips == 1
```

Also assert that the real-owned trip survives while its seed membership and seed-created invitation are removed, and that no remaining trip member, invite, recommendation, audit log, save, or notification references a deleted seed user or seed-owned trip.

- [ ] **Step 4: Run apply-mode tests and verify RED**

Run:

```bash
cd backend
python -m pytest tests/test_prepare_production_snapshot.py -k "apply or preserve" -q
```

Expected: FAIL because sanitation is not implemented.

- [ ] **Step 5: Implement aggregate planning and ordered deletion**

Use this deletion order inside the existing transaction:

```text
1. Collect fixed known-seed user IDs.
2. Collect trips owned by those IDs.
3. Delete recommendations referencing a seed user or seed-owned trip.
4. Delete invitations created by a seed user; seed-trip invitations then cascade with trip deletion.
5. Delete trip memberships for seed users on non-seed trips.
6. Delete admin audit rows for seed users.
7. Delete seed-owned trips; trip days, places, members, policies, and invites cascade by trip FK.
8. Delete seed users; refresh/reset/social/saved/notification rows cascade where configured.
9. Delete every remaining auth refresh token.
10. Delete every password-reset token, pending signup, and pending social signup.
```

The result dataclass must report exact aggregate counts for every category above. Execute the same SELECT/count path in dry-run and apply modes so their reports are directly comparable.

- [ ] **Step 6: Add CLI database-name and apply gates**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    engine = create_engine(database_url_for_name(args.database_name), pool_pre_ping=True)
    with Session(engine) as db:
        result = prepare_production_snapshot(db, apply=args.apply)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0
```

`database_url_for_name()` must make `travelhunter`, `postgres`, malformed names, and names without `travelhunter_restore_` impossible targets.

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd backend
python -m pytest tests/test_prepare_production_snapshot.py tests/test_production_db_inventory.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit the sanitation CLI**

```bash
git add backend/app/scripts/prepare_production_snapshot.py backend/tests/test_prepare_production_snapshot.py
git commit -m "Add restored database sanitation guard"
```

---

### Task 3: Write the exact operational runbook

**Files:**
- Create: `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`

**Interfaces:**
- Consumes: the two CLIs from Tasks 1-2, SSH aliases `dev-server` and `prod-server`, container names verified in the spec.
- Produces: one operator-safe command sequence with separate rehearsal, approval, final cutover, rollback, and credential-rotation sections.

- [ ] **Step 1: Document the fixed topology and baselines**

Record only non-secret facts:

```text
dev DB container: travel-hunter-onprem-db-1
dev backend container: travel-hunter-onprem-backend-1
prod DB container: prodtravelhunterapp-db-1
prod backend container: prodtravelhunterapp-backend-1
database/user: travelhunter
PostgreSQL: 16.14
Alembic: 0035_stay_policy_identity
source baseline: users 13, policies 159, external_source_records 88, policy_documents 16, trips 22, trip_places 261
target baseline: users 3, social_accounts 3, auth_refresh_tokens 8; policy/trip tables 0
source social baseline: google 4, kakao 2, Kakao placeholder-email users 0
production registrations: two identities overlap source users; one production-only identity will not survive the snapshot replacement unless separately preserved
policy expiry risk: active 139, of which 87 end on 2026-08-31 and 52 have no end date
```

Do not write user email addresses to Git or `CHECKLIST.md`. Before rehearsal, privately identify and notify the owner of the one production-only account that will not be merged, and record only the approval/outcome.

- [ ] **Step 2: Add the read-only preflight commands**

The runbook must use the inventory CLI against restored sibling DBs and direct aggregate SELECT commands against the active source. It must explicitly prohibit printing `DATABASE_URL` or any environment file.

Add a hash-only comparison of `KAKAO_CLIENT_ID` and `GOOGLE_CLIENT_ID` across the two backend containers. Record only match/mismatch, never the identifiers or secrets. The verified baseline is mismatch for both providers. Because the two source Kakao rows have no placeholder-email users but their provider IDs belong to the development Kakao app, stop before sanitation apply until one strategy is explicitly approved:

```text
A. Preserve/merge production-local Kakao mappings for overlapping users using a separately reviewed data-mapping procedure; or
B. Accept production re-link by verified email, remove or retain stale development Kakao mappings as explicitly decided, and require a migrated Kakao-user smoke with rollback on failure.
```

No automatic identity merge belongs in the generic snapshot sanitation CLI.

- [ ] **Step 3: Add exact PowerShell commands for secure dump creation and transfer**

```powershell
$migrationStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$migrationStampNormalized = $migrationStamp.Replace('-', '_')
$restoreDb = "travelhunter_restore_$migrationStampNormalized"
$previousDb = "travelhunter_before_$migrationStampNormalized"
$failedDb = "travelhunter_failed_$migrationStampNormalized"
$devMigrationDir = "/home/deploy/db-migrations/$migrationStamp"
$prodMigrationDir = "/home/prod-deploy/db-migrations/$migrationStamp"
$dumpName = "travelhunter-dev-$migrationStamp.dump"

ssh dev-server "install -d -m 700 '$devMigrationDir'"
ssh prod-server "install -d -m 700 '$prodMigrationDir'"
ssh dev-server "umask 077; docker exec travel-hunter-onprem-db-1 pg_dump -U travelhunter -d travelhunter -Fc --no-owner --no-privileges > '$devMigrationDir/$dumpName'; test -s '$devMigrationDir/$dumpName'; sha256sum '$devMigrationDir/$dumpName'; docker exec -i travel-hunter-onprem-db-1 pg_restore --list < '$devMigrationDir/$dumpName' > /dev/null"
scp -3 "dev-server:$devMigrationDir/$dumpName" "prod-server:$prodMigrationDir/$dumpName"
ssh prod-server "chmod 600 '$prodMigrationDir/$dumpName'; sha256sum '$prodMigrationDir/$dumpName'; docker exec -i prodtravelhunterapp-db-1 pg_restore --list < '$prodMigrationDir/$dumpName' > /dev/null"
```

The operator compares the two SHA-256 values before any restore.

- [ ] **Step 4: Add exact production backup and temporary restore commands**

```powershell
$prodBackupName = "travelhunter-prod-before-$migrationStamp.dump"
ssh prod-server "umask 077; docker exec prodtravelhunterapp-db-1 pg_dump -U travelhunter -d travelhunter -Fc --no-owner --no-privileges > '$prodMigrationDir/$prodBackupName'; test -s '$prodMigrationDir/$prodBackupName'; sha256sum '$prodMigrationDir/$prodBackupName'; docker exec -i prodtravelhunterapp-db-1 pg_restore --list < '$prodMigrationDir/$prodBackupName' > /dev/null"
ssh prod-server "docker exec prodtravelhunterapp-db-1 createdb -U travelhunter -T template0 '$restoreDb'"
ssh prod-server "docker exec -i prodtravelhunterapp-db-1 pg_restore -U travelhunter -d '$restoreDb' --exit-on-error --single-transaction --no-owner --no-privileges < '$prodMigrationDir/$dumpName'"
ssh prod-server "docker exec prodtravelhunterapp-db-1 psql -X -v ON_ERROR_STOP=1 -U travelhunter -d '$restoreDb' -c 'ANALYZE'"
```

The runbook must stop if `createdb` reports that the name already exists; never drop an unexpected database to make the command pass. PostgreSQL dump archives do not carry optimizer statistics, so `ANALYZE` must complete before inventory, rehearsal queries, or cutover.

- [ ] **Step 5: Add exact inventory and sanitation gates**

```powershell
ssh prod-server "docker exec prodtravelhunterapp-backend-1 python -m app.scripts.production_db_inventory --database-name '$restoreDb'"
ssh prod-server "docker exec prodtravelhunterapp-backend-1 python -m app.scripts.prepare_production_snapshot --database-name '$restoreDb'"
```

Record the dry-run JSON without sensitive fields. Require explicit approval before:

```powershell
ssh prod-server "docker exec prodtravelhunterapp-backend-1 python -m app.scripts.prepare_production_snapshot --database-name '$restoreDb' --apply"
ssh prod-server "docker exec prodtravelhunterapp-backend-1 python -m app.scripts.production_db_inventory --database-name '$restoreDb'"
```

- [ ] **Step 6: Add the controlled cutover command sequence**

The final runbook command block must:

```text
1. Stop the production backend.
2. Terminate remaining sessions connected to travelhunter and the restore DB.
3. Rename `travelhunter` to the value of `$previousDb`, defined as `travelhunter_before_$migrationStampNormalized`.
4. Rename the restored database to travelhunter.
5. Start the production backend.
6. Leave the old DB untouched.
```

PostgreSQL does not allow `ALTER DATABASE` inside a transaction block, so this is a short controlled sequence rather than a transactional atomic swap. Use one error-stopping psql session and retain explicit recovery commands for failure between the two renames:

```powershell
$cutoverSql = @"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('travelhunter', '$restoreDb') AND pid <> pg_backend_pid();
ALTER DATABASE travelhunter RENAME TO $previousDb;
ALTER DATABASE $restoreDb RENAME TO travelhunter;
"@
$cutoverSqlB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($cutoverSql))
ssh prod-server "printf '%s' '$cutoverSqlB64' | base64 -d | docker exec -i prodtravelhunterapp-db-1 psql -X -v ON_ERROR_STOP=1 -U travelhunter -d postgres"
```

Do not use `DROP DATABASE` in the cutover path. If the first rename succeeds and the second fails, immediately rename `$previousDb` back to `travelhunter` before restarting the backend.

- [ ] **Step 7: Add the rollback sequence**

Rollback must stop the backend, rename the failed active DB to the value of `$failedDb` (`travelhunter_failed_$migrationStampNormalized`), rename `$previousDb` back to `travelhunter`, and restart the backend:

```powershell
$rollbackSql = @"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('travelhunter', '$previousDb') AND pid <> pg_backend_pid();
ALTER DATABASE travelhunter RENAME TO $failedDb;
ALTER DATABASE $previousDb RENAME TO travelhunter;
"@
$rollbackSqlB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rollbackSql))
ssh prod-server "printf '%s' '$rollbackSqlB64' | base64 -d | docker exec -i prodtravelhunterapp-db-1 psql -X -v ON_ERROR_STOP=1 -U travelhunter -d postgres"
ssh prod-server "docker start prodtravelhunterapp-backend-1"
```

If the final development write freeze is active, the rollback section must also restart `travel-hunter-onprem-backend-1` and verify the development health endpoint before ending the incident. It must not restore from a dump unless both database-name rollback and the retained database are unavailable.

- [ ] **Step 8: Add validation and explicit stop conditions**

Required post-cutover checks:

```text
GET https://travel-hunter.co.kr/api/health
browser login with approved migrated Google and Kakao accounts when those provider rows exist
policy list and one policy detail
trip list and one migrated trip detail
one invitation link read path
production scheduler config remains enabled=False
backend logs contain no migration, auth, or database connection errors
```

Any failed health, login, policy, trip, or FK gate triggers rollback unless explicitly accepted.

Record these non-blocking post-cutover risks together rather than treating them as hidden assumptions:

```text
administrator users: 0
external collection scheduler: disabled
active policies ending 2026-08-31: 87
result: no current operator can manually refresh the policy catalog until an administrator is separately designated
```

- [ ] **Step 9: Commit the runbook**

```bash
git add docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md
git commit -m "Document production database cutover"
```

---

### Task 4: Verify the tooling-only change before any server mutation

**Files:**
- Verify: `backend/app/scripts/production_db_inventory.py`
- Verify: `backend/app/scripts/prepare_production_snapshot.py`
- Verify: `backend/tests/test_production_db_inventory.py`
- Verify: `backend/tests/test_prepare_production_snapshot.py`
- Verify: `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: reviewed local commits suitable for a tooling/runbook PR; no database mutation.

- [ ] **Step 1: Run focused tests**

```bash
cd backend
python -m pytest tests/test_production_db_inventory.py tests/test_prepare_production_snapshot.py -q
```

Expected: PASS.

- [ ] **Step 2: Run backend regression tests**

```bash
cd backend
python -m pytest -q
```

Expected: no new failures relative to the current baseline; every difference must be explained before proceeding.

- [ ] **Step 3: Validate Alembic and Compose without applying them**

```bash
cd backend
alembic upgrade head --sql
cd ..
docker compose -f compose.yaml config
```

Expected: both commands succeed; no schema migration was added.

- [ ] **Step 4: Verify encoding and diff hygiene**

```bash
git diff --check
cd frontend
npm run test:mojibake
```

Expected: PASS and no `U+FFFD` in changed files.

- [ ] **Step 5: Review the final diff for scope**

```bash
git status --short
git diff --stat origin/develop...HEAD
git diff origin/develop...HEAD -- backend/app/scripts backend/tests docs/deployment-cicd
```

Expected: only the two scripts, two tests, and one runbook; no `.env`, dump, credential, product feature, schema, migration, or crawler change.

- [ ] **Step 6: Stop for push/PR approval**

Present the branch, commit SHAs, exact diff, test evidence, and runbook gates. Do not push, open a PR, deploy the scripts, or create server artifacts without approval.

---

### Task 5: Rehearse the full migration into an inactive production database

**Files:**
- Execute from: `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`
- Record after completion: `CHECKLIST.md`

**Interfaces:**
- Consumes: merged/deployed tooling from Tasks 1-4 and explicit rehearsal approval.
- Produces: verified source dump, verified target backup, sanitized temporary database, inventory evidence, and no traffic cutover.

- [ ] **Step 1: Re-run read-only source and target inventories**

Require exact equality for `policies=159`, `external_source_records=88`, and `policy_documents=16`. Review and explain every other table-count delta from the spec baseline; a 30% difference is an unconditional stop. Also stop if either Alembic revision is no longer `0035_stay_policy_identity`.

- [ ] **Step 2: Obtain rehearsal mutation approval**

Approval covers only secure directories, dump files, one production backup, one sibling restore database, and sanitation of that sibling database. It does not cover stopping active backends or renaming active databases.

- [ ] **Step 3: Create, validate, transfer, and checksum the rehearsal dump**

Execute the runbook dump/transfer block. Confirm matching SHA-256 values and a successful `pg_restore --list` on both servers.

- [ ] **Step 4: Back up the current production database**

Execute the runbook production-backup block. Confirm the file is non-empty, mode `0600`, checksummed, and listable.

- [ ] **Step 5: Restore and analyze the unique sibling database**

Execute `createdb -T template0`, `pg_restore --exit-on-error --single-transaction`, and `ANALYZE`. Do not use `--clean` and do not target `travelhunter`.

- [ ] **Step 6: Run inventory and sanitation dry run**

Expected findings include three known seed users, one seed-owned trip, and transient auth records. Any unrecognized deletion category blocks apply mode.

- [ ] **Step 7: Obtain sanitation approval and apply only to the sibling database**

Run `prepare_production_snapshot --apply`, then run it again without `--apply`. The second dry run must report zero remaining seed or transient-token work.

- [ ] **Step 8: Run final sibling-database inventory**

Expected: no orphan counts, no lagging sequences, no known seed users, no auth/reset/pending tokens, and preserved non-seed users/policies/trips/social accounts.

Record `adminUsers=0`, scheduler disabled, and 87 active policies ending on 2026-08-31 as linked post-migration risks rather than silently promoting an account or enabling collection.

Confirm the privately approved disposition of the one production-only account and the Kakao identity strategy. The rehearsal is not complete while either remains undecided.

- [ ] **Step 9: Record rehearsal result concisely**

Replace `CHECKLIST.md` current status with the rehearsal date, dump checksum prefixes, source/restored aggregate counts, validation PASS/FAIL, and active risks. Do not include absolute secret paths, user identities, URLs containing credentials, or long console logs.

- [ ] **Step 10: Stop before cutover**

Leave production traffic and active `travelhunter` unchanged. Report the exact rehearsal evidence and expected final maintenance duration.

---

### Task 6: Perform the final write-frozen dump and controlled cutover

**Files:**
- Execute from: `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`
- Record after completion: `CHECKLIST.md`

**Interfaces:**
- Consumes: successful rehearsal evidence and explicit final cutover approval.
- Produces: production-local migrated database active under the unchanged name `travelhunter`, with the prior production database retained under a timestamped name.

- [ ] **Step 1: Announce and begin the maintenance window**

Record the KST start time and confirm the rollback database name, dump paths, current healthy status, production-only-account notification, and approved Kakao identity strategy before stopping writes. Freeze merges and pushes to `develop`, and do not modify Jenkins job branch/trigger settings until development writes resume.

- [ ] **Step 2: Stop development writes**

```powershell
ssh dev-server "docker stop travel-hunter-onprem-backend-1"
```

Confirm the container is stopped. Keep it stopped until production cutover and smoke complete so no post-dump writes are lost.

- [ ] **Step 3: Create and verify the final source dump**

Use a new migration timestamp and repeat the complete dump, list, checksum, and transfer sequence. Never reuse the rehearsal archive as the final source.

- [ ] **Step 4: Create and analyze a fresh final restore database**

Use a new `travelhunter_restore_*` name, restore with `--single-transaction`, run `ANALYZE`, and then run inventory. Do not alter the rehearsal database.

- [ ] **Step 5: Dry-run, approve, and apply sanitation**

Compare the final dry-run result to the rehearsal. Any new deletion category or unexplained material count change stops the cutover.

- [ ] **Step 6: Run the final pre-swap gate**

Required PASS:

```text
Alembic revision match
zero known seed users
zero transient auth/reset/pending tokens
zero FK/orphan counts
zero lagging sequences
expected non-seed user, policy, external source, trip, place, link, and social-account counts
external collection scheduler disabled
approved production-only-account disposition
approved Kakao identity handling reflected in the restored inventory
```

- [ ] **Step 7: Obtain explicit database-name swap approval**

Report the source SHA-256, restored inventory, sanitation report, old production backup SHA-256, planned old/new database names, and rollback commands.

- [ ] **Step 8: Stop production backend and perform the controlled rename**

Stop `prodtravelhunterapp-backend-1`, terminate remaining client sessions, rename the current `travelhunter` database to `travelhunter_before_$migrationStampNormalized`, and rename the verified restore database to `travelhunter` in one error-stopping psql session.

- [ ] **Step 9: Start the production backend**

```powershell
ssh prod-server "docker start prodtravelhunterapp-backend-1"
```

Wait for the container healthcheck to become healthy before public smoke.

- [ ] **Step 10: Execute the public smoke gate**

Verify health, approved migrated Google and Kakao account login, policy list/detail, trip list/detail, invitation read path, backend logs, and disabled scheduler state. Do not trigger the manual external collection endpoint. If an approved provider-specific account is unavailable, record that as a blocking validation gap rather than treating generic login as equivalent.

- [ ] **Step 11: Roll back immediately on a required-gate failure**

Use database-name rollback from the runbook. Keep the failed migrated database under `travelhunter_failed_$migrationStampNormalized` for diagnosis; do not destroy it during rollback. After production has returned to the prior database, restart `travel-hunter-onprem-backend-1` and verify development health so a failed production smoke cannot leave development stopped.

- [ ] **Step 12: End the write freeze**

After production smoke passes, restart `travel-hunter-onprem-backend-1` for continued development use. Development and production now diverge independently.

---

### Task 7: Close security exposure and harden DB network access

**Files:**
- Modify only if configuration documentation changes: `.env.example`
- Modify only if host binding is intentionally changed through code: `compose.local.yaml`
- Record operational outcome: `CHECKLIST.md`

**Interfaces:**
- Consumes: stable migrated production and explicit credential/configuration approval.
- Produces: rotated production DB password, rotated development Cloudflare tunnel token, verified service recovery, and a documented decision on host port exposure.

- [ ] **Step 1: Confirm stable rollback evidence before rotating credentials**

Verify the retained old database, production backup dump, final source dump, and their checksum records still exist and are readable.

- [ ] **Step 2: Rotate the production DB password without displaying it**

Generate and deliver the new password through the approved secret-management path, update the production PostgreSQL role and `deploy/.env.prod`, recreate only the production backend, and verify health/login. Never place the password in shell history, Git, Slack, CHECKLIST, or console output.

- [ ] **Step 3: Rotate the exposed development Cloudflare tunnel token**

Issue a replacement token in Cloudflare, update only the development runtime secret on `dev-server`, recreate `travel-hunter-onprem-cloudflared-1`, confirm `https://dev.travel-hunter.co.kr`, and revoke the exposed token after the new connector is healthy. Do not change the production tunnel token unless an independent production exposure is found.

- [ ] **Step 4: Decide and apply the DB host-port boundary**

Preferred production result: PostgreSQL is not reachable from untrusted networks. Either bind the host port to `127.0.0.1:55432:5432` or enforce an equivalent host firewall/security-group deny rule. Verify backend connectivity through `db:5432` remains unaffected.

- [ ] **Step 5: Verify no secret entered Git or logs**

```bash
git status --short
git diff --check
```

Inspect only filenames and diff metadata for secret-bearing runtime files; do not print their contents.

---

### Task 8: Finalize evidence and retain rollback assets

**Files:**
- Modify: `CHECKLIST.md`
- Modify if shared operational knowledge changed: `docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md`

**Interfaces:**
- Consumes: completed cutover and security gates.
- Produces: concise project status, active risks, and a deferred cleanup decision; no artifact deletion.

- [ ] **Step 1: Replace stale CHECKLIST status**

Keep only:

```text
active production DB revision and sanitized aggregate counts
cutover KST timestamp
final source/production-backup checksum prefixes
health/auth/policy/trip/invite smoke results
external scheduler disabled state
Google/Kakao migrated-login results and approved identity disposition
administrator-zero plus 2026-08-31 policy-expiry risk
retained rollback database and dump status
credential rotation status
remaining risks
```

- [ ] **Step 2: Run checklist and repository hygiene checks**

```bash
git diff --check -- CHECKLIST.md docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md
git status --short
```

Expected: no whitespace errors, no dump/env/token files, and no unrelated changes.

- [ ] **Step 3: Commit only safe shared documentation**

```bash
git add CHECKLIST.md docs/deployment-cicd/2026-08-30-production-db-cutover-runbook.md
git commit -m "Record production database cutover"
```

- [ ] **Step 4: Keep rollback assets without deletion**

Retain the old production database and both verified dump files through the agreed stabilization period. Deletion is a separate destructive task requiring a fresh inventory, exact target paths, and explicit approval.

---

## Final Verification Matrix

| Gate | Evidence | Required result |
|---|---|---|
| Tooling | Focused pytest | PASS |
| Regression | Backend pytest | No new failures |
| Schema | `alembic upgrade head --sql` | PASS, no new migration |
| Compose | `docker compose -f compose.yaml config` | PASS |
| Archive | non-empty, listable, SHA-256 | PASS on source and target |
| Restore | `pg_restore --single-transaction --exit-on-error` | PASS |
| Planner statistics | `ANALYZE` on restored sibling DB | PASS before inventory/cutover |
| Sanitation | dry-run equals applied counts | PASS |
| Integrity | orphan and sequence report | all zero/empty |
| Runtime | `/api/health` | healthy, DB connected |
| Product smoke | migrated Google/Kakao login, policy, trip, invite | PASS |
| Scheduler | production runtime config | disabled |
| Rollback | old DB and backup dump | retained and readable |
| Security | DB and tunnel credentials | rotated without disclosure |

## Execution Stop Condition

Stop only after the migrated production database is active and verified, the old production database and dumps are retained, exposed credentials are rotated, development has resumed on its independent DB, CHECKLIST contains concise evidence, and no unapproved cleanup remains in progress. If any required production gate fails, execute the documented rollback, restart and verify development after the write freeze, and stop with the failed migrated database preserved for diagnosis.
