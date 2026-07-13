"""Audit aggregate policy semantics from the configured database.

Run:
    cd backend
    python scripts/audit_policy_semantics.py --json

This diagnostic is intentionally aggregate-only: it reports counts and source-field
families without printing policy rows, titles, URLs, or raw canonical keys.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import Policy

HEX_32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
CANONICAL_KEY_FAMILIES = (
    "legacy-dgtour",
    "32-char-hex",
    "travelmonth/source-prefixed",
    "null",
    "other",
)


def canonical_key_family(value: str | None) -> str:
    """Return the aggregate family label for a policy source canonical key."""

    if value is None or not value.strip():
        return "null"

    normalized = value.strip()
    lowered = normalized.lower()
    if lowered.startswith("legacy-dgtour-"):
        return "legacy-dgtour"
    if HEX_32_RE.fullmatch(normalized):
        return "32-char-hex"
    if _is_source_prefixed_canonical_key(lowered):
        return "travelmonth/source-prefixed"
    return "other"


def audit_policy_semantics(db: Session) -> dict[str, Any]:
    """Build aggregate-only policy diagnostics from a DB session."""

    total_policies = _scalar_count(db, select(func.count()).select_from(Policy))
    status_counts = _status_counts(db)
    source_combinations = _source_combinations(db)
    source_canonical_key_families = _source_canonical_key_families(db)

    return {
        "totalPolicies": total_policies,
        "statusCounts": status_counts,
        "benefitAmount": _nullability_counts(db, Policy.benefit_amount),
        "applyUrl": _nullability_counts(db, Policy.apply_url),
        "sourceCombinations": {
            "distinctCount": len(source_combinations),
            "items": source_combinations,
        },
        "sourceCanonicalKeyFamilies": source_canonical_key_families,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit aggregate policy semantics from the configured database.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the diagnostics as a JSON object.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session_factory = get_session_factory()
    with session_factory() as db:
        _request_read_only_transaction(db)
        payload = audit_policy_semantics(db)
        db.rollback()

    indent = None if args.json else 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=indent))
    return 0


def _is_source_prefixed_canonical_key(value: str) -> bool:
    return (
        value.startswith("travelmonth-")
        or value.startswith("travelmonth:")
        or ":" in value
    )


def _request_read_only_transaction(db: Session) -> None:
    """Ask PostgreSQL for a read-only transaction while staying portable in tests."""

    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    db.execute(text("SET TRANSACTION READ ONLY"))


def _scalar_count(db: Session, statement: Any) -> int:
    return int(db.scalar(statement) or 0)


def _status_counts(db: Session) -> dict[str, int]:
    statement = select(Policy.status, func.count()).group_by(Policy.status)
    rows = db.execute(statement).all()
    counts = {str(status or "null"): int(count) for status, count in rows}
    return dict(sorted(counts.items()))


def _nullability_counts(db: Session, column: Any) -> dict[str, int]:
    null_count = _scalar_count(
        db,
        select(func.count()).select_from(Policy).where(column.is_(None)),
    )
    non_null_count = _scalar_count(
        db,
        select(func.count()).select_from(Policy).where(column.is_not(None)),
    )
    return {"null": null_count, "nonNull": non_null_count}


def _source_combinations(db: Session) -> list[dict[str, Any]]:
    count_label = func.count().label("count")
    statement = (
        select(Policy.source_type, Policy.source_name, Policy.source_category, count_label)
        .group_by(Policy.source_type, Policy.source_name, Policy.source_category)
    )
    rows = db.execute(statement).all()
    items = [
        {
            "sourceType": source_type,
            "sourceName": source_name,
            "sourceCategory": source_category,
            "count": int(count),
        }
        for source_type, source_name, source_category, count in rows
    ]
    return sorted(
        items,
        key=lambda item: (
            -item["count"],
            _sort_value(item["sourceType"]),
            _sort_value(item["sourceName"]),
            _sort_value(item["sourceCategory"]),
        ),
    )


def _source_canonical_key_families(db: Session) -> dict[str, int]:
    statement = select(Policy.source_canonical_key, func.count()).group_by(
        Policy.source_canonical_key
    )
    counts = {family: 0 for family in CANONICAL_KEY_FAMILIES}
    for canonical_key, count in db.execute(statement).all():
        counts[canonical_key_family(canonical_key)] += int(count)
    return counts


def _sort_value(value: object) -> str:
    return "" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
