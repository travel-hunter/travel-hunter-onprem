#!/usr/bin/env python3
"""Local-only restricted snapshot tooling for migration 0029.

This captures only the semantic fields changed by 0029 plus deterministic digests
for every identity, raw-evidence, URL, and relation field that must not change.
It never prints captured semantic text.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

import psycopg
from psycopg.types.json import Jsonb


SCHEMA_VERSION = 1
PRE_MIGRATION_REVISION = "0027_source_provenance_keys"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
PROTECTED_DATABASES = {"postgres", "template0", "template1", "travelhunter"}
RESTORE_DATABASE_PATTERN = re.compile(r"^travelhunter_(?:snapshot|restore|test)_[a-z0-9_]+$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_PATTERN = re.compile(r"^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

TOP_LEVEL_KEYS = {
    "schema_version",
    "created_at",
    "alembic_version",
    "prestate_kind",
    "source_semantic_rows",
    "policy_semantic_rows",
    "preserved_digests",
}
SOURCE_ROW_KEYS = {"id", "contact_text"}
POLICY_ROW_KEYS = {"id", "target_condition", "structured_detail"}
DIGEST_KEYS = {
    "source_identity_raw_url_sha256",
    "policy_identity_status_url_sha256",
    "saved_policy_tuples_sha256",
    "trip_policy_tuples_sha256",
    "policy_document_tuples_sha256",
    "notification_delivery_tuples_sha256",
    "fk_orphan_counts",
}
ORPHAN_KEYS = {
    "user_saved_policies",
    "trip_policies",
    "policy_documents",
    "notification_deliveries",
}
STRUCTURED_KEYS = {"supportContent", "periods", "applicationTarget", "requiredDocuments", "notes"}
LEGACY_STRUCTURED_KEYS = {"benefits", "conditions", "periods", "documents", "notices", "links"}
STRUCTURED_ITEM_KEYS = {
    "title",
    "label",
    "description",
    "amount",
    "value",
    "url",
    "startDate",
    "endDate",
    "type",
}


class SnapshotError(RuntimeError):
    pass


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0029_stay_discount_semantics.py"
    spec = importlib.util.spec_from_file_location("stay_discount_semantics_0029", path)
    if spec is None or spec.loader is None:
        raise SnapshotError("cannot load migration-local semantic contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError("snapshot contains a duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise SnapshotError("snapshot contains a non-finite JSON number")


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise SnapshotError(f"{label} has missing or unknown keys")
    return value


def _validate_rows(rows: object, keys: set[str], label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise SnapshotError(f"{label} must be an array")
    checked: list[dict[str, Any]] = []
    ids: list[int] = []
    for item in rows:
        row = _exact_keys(item, keys, f"{label} row")
        if not isinstance(row["id"], int) or isinstance(row["id"], bool):
            raise SnapshotError(f"{label} row id must be an integer")
        ids.append(row["id"])
        for key in keys - {"id", "structured_detail"}:
            if row[key] is not None and not isinstance(row[key], str):
                raise SnapshotError(f"{label} semantic values must be strings or null")
        checked.append(row)
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise SnapshotError(f"{label} row ids must be unique and sorted")
    return checked


def _is_safe_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _validate_structured_detail_item(item: object, section: str) -> None:
    if not isinstance(item, dict):
        raise SnapshotError("structured_detail items must be objects")
    if not item:
        raise SnapshotError("structured_detail items must not be empty")
    unknown_keys = set(item) - STRUCTURED_ITEM_KEYS
    if unknown_keys:
        raise SnapshotError("structured_detail item has unknown keys")
    for key, value in item.items():
        if not isinstance(value, str) or not value.strip():
            raise SnapshotError("structured_detail item values must be non-empty strings")


def _validate_structured_detail(detail: object) -> None:
    if not isinstance(detail, dict):
        raise SnapshotError("structured_detail has missing or unknown keys")
    keys = set(detail)
    if keys != STRUCTURED_KEYS and keys != LEGACY_STRUCTURED_KEYS:
        raise SnapshotError("structured_detail has missing or unknown keys")
    for section in keys:
        items = detail[section]
        if not isinstance(items, list):
            raise SnapshotError("structured_detail sections must be arrays")
        for item in items:
            _validate_structured_detail_item(item, section)


def validate_payload(value: object) -> dict[str, Any]:
    payload = _exact_keys(value, TOP_LEVEL_KEYS, "snapshot")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise SnapshotError("unsupported snapshot schema_version")
    if not isinstance(payload["created_at"], str) or not TIMESTAMP_PATTERN.fullmatch(payload["created_at"]):
        raise SnapshotError("created_at must use UTC RFC3339 seconds")
    if payload["alembic_version"] != PRE_MIGRATION_REVISION:
        raise SnapshotError("snapshot must identify the exact pre-0029 revision")
    if payload["prestate_kind"] not in {"single_23_33", "merged_26_35"}:
        raise SnapshotError("unknown prestate_kind")
    sources = _validate_rows(payload["source_semantic_rows"], SOURCE_ROW_KEYS, "source_semantic_rows")
    policies = _validate_rows(payload["policy_semantic_rows"], POLICY_ROW_KEYS, "policy_semantic_rows")
    expected_ids = ([33], [23]) if payload["prestate_kind"] == "single_23_33" else ([33, 35], [23, 26])
    if [row["id"] for row in sources] != expected_ids[0] or [row["id"] for row in policies] != expected_ids[1]:
        raise SnapshotError("row ids do not match prestate_kind")
    for row in policies:
        detail = row["structured_detail"]
        if detail is not None:
            _validate_structured_detail(detail)
    digests = _exact_keys(payload["preserved_digests"], DIGEST_KEYS, "preserved_digests")
    for key in DIGEST_KEYS - {"fk_orphan_counts"}:
        if not isinstance(digests[key], str) or not HASH_PATTERN.fullmatch(digests[key]):
            raise SnapshotError(f"invalid digest: {key}")
    orphans = _exact_keys(digests["fk_orphan_counts"], ORPHAN_KEYS, "fk_orphan_counts")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in orphans.values()):
        raise SnapshotError("fk_orphan_counts values must be non-negative integers")
    return payload


def parse_payload(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotError("snapshot is not UTF-8") from exc
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise SnapshotError("snapshot must have exactly one trailing newline")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, SnapshotError) as exc:
        if isinstance(exc, SnapshotError):
            raise
        raise SnapshotError("snapshot is not valid JSON") from exc
    payload = validate_payload(value)
    if canonical_bytes(payload) != raw:
        raise SnapshotError("snapshot is not canonical JSON")
    return payload


def parse_local_database_url(database_url: str, allowed_database: str, *, restore: bool = False) -> tuple[str, str]:
    normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise SnapshotError("database URL must use PostgreSQL")
    if parsed.hostname not in LOCAL_HOSTS:
        raise SnapshotError("database URL must use a loopback host")
    database = unquote(parsed.path.removeprefix("/"))
    if not database or "/" in database or database != allowed_database:
        raise SnapshotError("database must exactly match --allow-database")
    if restore and (
        database in PROTECTED_DATABASES or RESTORE_DATABASE_PATTERN.fullmatch(database) is None
    ):
        raise SnapshotError("restore is restricted to an explicitly named isolated project database")
    return normalized, database


def _json_rows(connection: psycopg.Connection[Any], query: str, params: tuple[object, ...] = ()) -> list[object]:
    return [row[0] for row in connection.execute(query, params).fetchall()]


def _digest_rows(rows: Iterable[object]) -> str:
    return canonical_sha256(list(rows))


def _candidate_kind(connection: psycopg.Connection[Any]) -> str:
    sources = connection.execute(
        "SELECT id,canonical_key,logical_key,canonical_key_version FROM external_source_records "
        "WHERE source_category='stay_discount' OR logical_key='stay-discount:2026-summer' OR id IN (33,35) ORDER BY id"
    ).fetchall()
    policies = connection.execute(
        "SELECT id,slug,status,external_source_record_id,source_canonical_key FROM policies "
        "WHERE source_category='stay_discount' OR external_source_record_id IN (33,35) "
        "OR id IN (23,26) OR slug IN ('travelmonth-33','travelmonth-35') ORDER BY id"
    ).fetchall()
    migration = _migration()
    if sources == [(33, migration.SOURCE_33_KEY, migration.LOGICAL_KEY, migration.KEY_VERSION)] and policies == [
        (23, "travelmonth-33", "active", 33, migration.SOURCE_33_KEY)
    ]:
        return "single_23_33"
    if sources == [
        (33, migration.SOURCE_33_KEY, migration.LOGICAL_KEY, migration.KEY_VERSION),
        (35, migration.SOURCE_35_KEY, migration.LOGICAL_KEY, migration.KEY_VERSION),
    ] and policies == [
        (23, "travelmonth-33", "active", 35, migration.SOURCE_35_KEY),
        (26, "travelmonth-35", "hidden", None, migration.SOURCE_35_KEY),
    ]:
        return "merged_26_35"
    raise SnapshotError("database candidate identity is missing, ambiguous, or drifted")


def _preserved_digests(connection: psycopg.Connection[Any], policy_ids: list[int]) -> dict[str, Any]:
    source_rows = _json_rows(
        connection,
        "SELECT to_jsonb(s)-'contact_text' FROM external_source_records s "
        "WHERE id IN (33,35) AND source_category='stay_discount' ORDER BY id",
    )
    policy_rows = _json_rows(
        connection,
        "SELECT to_jsonb(p)-'target_condition'-'structured_detail' FROM policies p "
        "WHERE id=ANY(%s) ORDER BY id",
        (policy_ids,),
    )
    relation_specs = {
        "saved_policy_tuples_sha256": "user_saved_policies",
        "trip_policy_tuples_sha256": "trip_policies",
        "policy_document_tuples_sha256": "policy_documents",
        "notification_delivery_tuples_sha256": "notification_deliveries",
    }
    result: dict[str, Any] = {
        "source_identity_raw_url_sha256": _digest_rows(source_rows),
        "policy_identity_status_url_sha256": _digest_rows(policy_rows),
    }
    for key, table in relation_specs.items():
        rows = _json_rows(
            connection,
            f"SELECT to_jsonb(t) FROM {table} t WHERE policy_id=ANY(%s) ORDER BY id",
            (policy_ids,),
        )
        result[key] = _digest_rows(rows)
    orphans: dict[str, int] = {}
    for table in relation_specs.values():
        orphans[table] = connection.execute(
            f"SELECT count(*) FROM {table} child LEFT JOIN policies parent ON parent.id=child.policy_id "
            "WHERE parent.id IS NULL"
        ).fetchone()[0]
    result["fk_orphan_counts"] = orphans
    return result


def snapshot_payload(connection: psycopg.Connection[Any], *, created_at: datetime | None = None) -> dict[str, Any]:
    revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if revision != (PRE_MIGRATION_REVISION,):
        raise SnapshotError("export requires exact Alembic revision 0028")
    kind = _candidate_kind(connection)
    source_ids = [33] if kind == "single_23_33" else [33, 35]
    policy_ids = [23] if kind == "single_23_33" else [23, 26]
    sources = [
        {"id": row[0], "contact_text": row[1]}
        for row in connection.execute(
            "SELECT id,contact_text FROM external_source_records WHERE id=ANY(%s) ORDER BY id",
            (source_ids,),
        ).fetchall()
    ]
    policies = [
        {"id": row[0], "target_condition": row[1], "structured_detail": row[2]}
        for row in connection.execute(
            "SELECT id,target_condition,structured_detail FROM policies WHERE id=ANY(%s) ORDER BY id",
            (policy_ids,),
        ).fetchall()
    ]
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    return validate_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "created_at": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alembic_version": PRE_MIGRATION_REVISION,
            "prestate_kind": kind,
            "source_semantic_rows": sources,
            "policy_semantic_rows": policies,
            "preserved_digests": _preserved_digests(connection, policy_ids),
        }
    )


def _assert_safe_path(path: Path, *, must_exist: bool) -> None:
    if ".." in path.parts or path.name in {"", ".", ".."}:
        raise SnapshotError("snapshot path is not safe")
    if must_exist:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise SnapshotError("snapshot and sidecar must be regular files")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise SnapshotError("snapshot and sidecar permissions must not allow group/other access")


def _write_restricted_atomic(path: Path, data: bytes) -> None:
    _assert_safe_path(path, must_exist=False)
    parent_info = path.parent.lstat()
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or stat.S_IMODE(parent_info.st_mode) & 0o077
    ):
        raise SnapshotError("snapshot directory must be a real directory restricted to its owner")
    if path.exists() or path.is_symlink():
        raise SnapshotError("refusing to overwrite an existing snapshot artifact")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise SnapshotError("refusing to overwrite an existing snapshot artifact") from exc
        temporary.unlink()
        os.chmod(path, 0o600)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def export_snapshot(database_url: str, allowed_database: str, output: Path) -> dict[str, Any]:
    url, _ = parse_local_database_url(database_url, allowed_database)
    sidecar = Path(f"{output}.sha256")
    if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise SnapshotError("refusing to overwrite snapshot or sidecar")
    with psycopg.connect(url) as connection:
        connection.execute(_migration().IDENTITY_AND_PRESTATE_GUARD_SQL)
        payload = snapshot_payload(connection)
    raw = canonical_bytes(payload)
    digest = hashlib.sha256(raw).hexdigest()
    _write_restricted_atomic(output, raw)
    try:
        _write_restricted_atomic(sidecar, f"{digest}  {output.name}\n".encode("ascii"))
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {"prestate_kind": payload["prestate_kind"], "row_count": len(payload["policy_semantic_rows"]), "digest": digest}


def load_snapshot(input_path: Path) -> tuple[dict[str, Any], str]:
    sidecar = Path(f"{input_path}.sha256")
    _assert_safe_path(input_path, must_exist=True)
    _assert_safe_path(sidecar, must_exist=True)
    raw = input_path.read_bytes()
    try:
        sidecar_text = sidecar.read_text(encoding="ascii")
    except UnicodeDecodeError as exc:
        raise SnapshotError("snapshot SHA-256 sidecar must be ASCII") from exc
    match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\\n]+)\n", sidecar_text)
    if match is None or match.group(2) != input_path.name or ".." in match.group(2):
        raise SnapshotError("invalid snapshot SHA-256 sidecar")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != match.group(1):
        raise SnapshotError("snapshot SHA-256 mismatch")
    return parse_payload(raw), actual


def _desired_for(payload: dict[str, Any]) -> dict[str, object]:
    migration = _migration()
    return migration.DESIRED_33 if payload["prestate_kind"] == "single_23_33" else migration.DESIRED_35


def _verify_database(connection: psycopg.Connection[Any], payload: dict[str, Any], *, allow_pre: bool, allow_post: bool) -> str:
    if _candidate_kind(connection) != payload["prestate_kind"]:
        raise SnapshotError("database candidate row set does not match snapshot")
    policy_ids = [row["id"] for row in payload["policy_semantic_rows"]]
    if _preserved_digests(connection, policy_ids) != payload["preserved_digests"]:
        raise SnapshotError("database preserved identity/raw/relation digest mismatch")
    sources = connection.execute(
        "SELECT id,contact_text FROM external_source_records WHERE id=ANY(%s) ORDER BY id",
        ([row["id"] for row in payload["source_semantic_rows"]],),
    ).fetchall()
    policies = connection.execute(
        "SELECT id,target_condition,structured_detail FROM policies WHERE id=ANY(%s) ORDER BY id",
        (policy_ids,),
    ).fetchall()
    pre = (
        sources == [(row["id"], row["contact_text"]) for row in payload["source_semantic_rows"]]
        and policies == [
            (row["id"], row["target_condition"], row["structured_detail"])
            for row in payload["policy_semantic_rows"]
        ]
    )
    desired = _desired_for(payload)
    post = all(row[1] is None for row in sources) and all(
        row[1] is None and row[2] == desired for row in policies
    )
    if pre and allow_pre:
        return "pre"
    if post and allow_post:
        return "post"
    raise SnapshotError("database semantic state is neither an allowed prestate nor exact 0029 state")


def verify_snapshot(database_url: str, allowed_database: str, input_path: Path) -> dict[str, Any]:
    payload, digest = load_snapshot(input_path)
    url, _ = parse_local_database_url(database_url, allowed_database)
    with psycopg.connect(url) as connection:
        state = _verify_database(connection, payload, allow_pre=True, allow_post=True)
    return {"prestate_kind": payload["prestate_kind"], "row_count": len(payload["policy_semantic_rows"]), "digest": digest, "database_state": state}


def restore_snapshot(database_url: str, allowed_database: str, input_path: Path) -> dict[str, Any]:
    payload, digest = load_snapshot(input_path)
    url, _ = parse_local_database_url(database_url, allowed_database, restore=True)
    policy_ids = [row["id"] for row in payload["policy_semantic_rows"]]
    source_ids = [row["id"] for row in payload["source_semantic_rows"]]
    with psycopg.connect(url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        if connection.execute("SELECT version_num FROM alembic_version FOR UPDATE").fetchone() != (
            PRE_MIGRATION_REVISION,
        ):
            raise SnapshotError("restore requires guarded no-op downgrade to exact revision 0028")
        connection.execute(
            "SELECT id FROM external_source_records WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (source_ids,),
        ).fetchall()
        connection.execute(
            "SELECT id FROM policies WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (policy_ids,),
        ).fetchall()
        _verify_database(connection, payload, allow_pre=False, allow_post=True)
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE external_source_records SET contact_text=%s WHERE id=%s",
                [(row["contact_text"], row["id"]) for row in payload["source_semantic_rows"]],
            )
            cursor.executemany(
                "UPDATE policies SET target_condition=%s,structured_detail=%s WHERE id=%s",
                [
                    (row["target_condition"], Jsonb(row["structured_detail"]), row["id"])
                    for row in payload["policy_semantic_rows"]
                ],
            )
        _verify_database(connection, payload, allow_pre=True, allow_post=False)
        connection.commit()
    return {"prestate_kind": payload["prestate_kind"], "row_count": len(policy_ids), "digest": digest, "database_state": "restored"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "verify", "restore"):
        child = subparsers.add_parser(command)
        child.add_argument("--database-url", required=True)
        child.add_argument("--allow-database", required=True)
        if command == "export":
            child.add_argument("--output", type=Path, required=True)
        else:
            child.add_argument("--input", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "export":
            result = export_snapshot(args.database_url, args.allow_database, args.output)
        elif args.command == "verify":
            result = verify_snapshot(args.database_url, args.allow_database, args.input)
        else:
            result = restore_snapshot(args.database_url, args.allow_database, args.input)
    except (SnapshotError, OSError, psycopg.Error) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
