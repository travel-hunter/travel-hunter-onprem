from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import ExternalSourceRecord, Policy
from app.services.policy_category_classifier import classify_external_policy_category


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reclassify already-promoted external policies from linked external source records.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist category changes. Without this flag the command only reports changes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session_factory = get_session_factory()
    with session_factory() as db:
        payload = reclassify_external_policy_categories(db, apply=args.apply)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def reclassify_external_policy_categories(db: Session, *, apply: bool) -> dict[str, object]:
    policies = _list_promoted_policies(db)
    changes: list[dict[str, object]] = []
    for policy in policies:
        record = _get_external_record(db, policy.external_source_record_id)
        if record is None:
            continue
        decision = classify_external_policy_category(record)
        current_category = policy.policy_type or ""
        if current_category == decision.category:
            continue
        changes.append(
            {
                "policySlug": policy.slug,
                "title": policy.title,
                "from": current_category,
                "to": decision.category,
            }
        )
        if apply:
            policy.policy_type = decision.category
    if apply:
        db.commit()
    return {
        "checkedCount": len(policies),
        "changedCount": len(changes),
        "applied": apply,
        "changes": changes,
    }


def _list_promoted_policies(db: Session) -> list[Policy]:
    statement = (
        select(Policy)
        .where(Policy.external_source_record_id.is_not(None))
        .order_by(Policy.id)
    )
    return list(db.scalars(statement).all())


def _get_external_record(db: Session, record_id: int | None) -> ExternalSourceRecord | None:
    if record_id is None:
        return None
    return db.get(ExternalSourceRecord, record_id)


if __name__ == "__main__":
    raise SystemExit(main() or 0)
