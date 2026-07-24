from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import stat

import pytest

from scripts import stay_discount_semantics_snapshot as snapshot


def _payload() -> dict[str, object]:
    empty = {key: [] for key in snapshot.STRUCTURED_KEYS}
    digest = "0" * 64
    return {
        "schema_version": 1,
        "created_at": "2026-07-16T00:00:00Z",
        "alembic_version": "0027_source_provenance_keys",
        "prestate_kind": "single_23_33",
        "source_semantic_rows": [{"id": 33, "contact_text": "private semantic prestate"}],
        "policy_semantic_rows": [
            {"id": 23, "target_condition": "private semantic prestate", "structured_detail": empty}
        ],
        "preserved_digests": {
            "source_identity_raw_url_sha256": digest,
            "policy_identity_status_url_sha256": digest,
            "saved_policy_tuples_sha256": digest,
            "trip_policy_tuples_sha256": digest,
            "policy_document_tuples_sha256": digest,
            "notification_delivery_tuples_sha256": digest,
            "fk_orphan_counts": {key: 0 for key in snapshot.ORPHAN_KEYS},
        },
    }


def test_database_url_requires_postgres_loopback_exact_allowlist_and_isolated_restore() -> None:
    url = "postgresql+psycopg://user:secret@127.0.0.1:55432/travelhunter"
    assert snapshot.parse_local_database_url(url, "travelhunter")[1] == "travelhunter"
    with pytest.raises(snapshot.SnapshotError, match="loopback"):
        snapshot.parse_local_database_url(
            "postgresql://user:secret@db.example.test/travelhunter", "travelhunter"
        )
    with pytest.raises(snapshot.SnapshotError, match="allow-database"):
        snapshot.parse_local_database_url(url, "another")
    with pytest.raises(snapshot.SnapshotError, match="isolated"):
        snapshot.parse_local_database_url(url, "travelhunter", restore=True)
    isolated = "postgresql://user:secret@localhost/travelhunter_restore_g003"
    assert snapshot.parse_local_database_url(
        isolated, "travelhunter_restore_g003", restore=True
    )[1] == "travelhunter_restore_g003"


def test_parser_rejects_duplicate_unknown_unsorted_and_noncanonical_json() -> None:
    payload = _payload()
    raw = snapshot.canonical_bytes(payload)
    assert snapshot.parse_payload(raw) == payload

    duplicate = raw.replace(b'{"alembic_version":', b'{"schema_version":1,"alembic_version":', 1)
    with pytest.raises(snapshot.SnapshotError, match="duplicate"):
        snapshot.parse_payload(duplicate)
    unknown = dict(payload, unknown=True)
    with pytest.raises(snapshot.SnapshotError, match="unknown"):
        snapshot.parse_payload(snapshot.canonical_bytes(unknown))
    merged = _payload()
    merged["prestate_kind"] = "merged_26_35"
    merged["source_semantic_rows"] = [
        {"id": 35, "contact_text": None},
        {"id": 33, "contact_text": None},
    ]
    merged["policy_semantic_rows"] = [
        {"id": 23, "target_condition": None, "structured_detail": None},
        {"id": 26, "target_condition": None, "structured_detail": None},
    ]
    with pytest.raises(snapshot.SnapshotError, match="sorted"):
        snapshot.parse_payload(snapshot.canonical_bytes(merged))
    with pytest.raises(snapshot.SnapshotError, match="canonical"):
        snapshot.parse_payload(json.dumps(payload, ensure_ascii=False).encode() + b"\n")


@pytest.mark.parametrize(
    ("section", "items", "message"),
    [
        (
            "supportContent",
            [{"title": "혜택", "description": "설명", "debug": "raw"}],
            "unknown keys",
        ),
        ("supportContent", [{"title": "혜택", "description": 1000}], "non-empty strings"),
        ("supportContent", [{"title": "혜택", "description": "   "}], "non-empty strings"),
        ("supportContent", [{}], "must not be empty"),
        ("supportContent", ["혜택"], "must be objects"),
    ],
    ids=[
        "unknown-item-key",
        "wrong-value-type",
        "blank-value",
        "empty-item",
        "non-object-item",
    ],
)
def test_parser_rejects_unknown_missing_or_wrong_typed_structured_detail_items(
    section: str,
    items: list[object],
    message: str,
) -> None:
    payload = _payload()
    row = payload["policy_semantic_rows"][0]
    assert isinstance(row, dict)
    detail = row["structured_detail"]
    assert isinstance(detail, dict)
    detail[section] = items

    with pytest.raises(snapshot.SnapshotError, match=message):
        snapshot.parse_payload(snapshot.canonical_bytes(payload))


def test_parser_accepts_allowed_structured_detail_item_keys() -> None:
    payload = _payload()
    row = payload["policy_semantic_rows"][0]
    assert isinstance(row, dict)
    detail = row["structured_detail"]
    assert isinstance(detail, dict)
    detail["supportContent"] = [
        {
            "title": "혜택",
            "label": "할인",
            "description": "7만원 이상 예약 시 할인",
            "amount": "3만원",
            "value": "30000",
        }
    ]
    detail["periods"] = [
        {
            "title": "쿠폰 발급 기간",
            "description": "2026-06-11 ~ 2026-08-17",
            "type": "application",
            "startDate": "2026-06-11",
            "endDate": "2026-08-17",
        }
    ]

    assert snapshot.parse_payload(snapshot.canonical_bytes(payload)) == payload


def test_restricted_atomic_artifact_and_sidecar_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "stay-prestate.json"
    raw = snapshot.canonical_bytes(_payload())
    digest = hashlib.sha256(raw).hexdigest()

    snapshot._write_restricted_atomic(path, raw)
    snapshot._write_restricted_atomic(
        Path(f"{path}.sha256"), f"{digest}  {path.name}\n".encode("ascii")
    )
    payload, loaded_digest = snapshot.load_snapshot(path)

    assert payload == _payload()
    assert loaded_digest == digest
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(f"{path}.sha256").stat().st_mode) == 0o600
    with pytest.raises(snapshot.SnapshotError, match="overwrite"):
        snapshot._write_restricted_atomic(path, raw)


def test_snapshot_timestamp_format_is_seconds_utc() -> None:
    value = datetime(2026, 7, 16, 12, 34, 56, 999999, tzinfo=UTC)
    assert value.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ") == "2026-07-16T12:34:56Z"
