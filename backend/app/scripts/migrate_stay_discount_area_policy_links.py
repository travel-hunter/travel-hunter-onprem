from __future__ import annotations

import argparse
from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import Policy, Trip, TripPolicy, UserSavedPolicy
from app.services import stay_discount_aliases


_BRACKET_CITY_PATTERN = re.compile(r"^\[(?P<city>[^\]]+)\]")


@dataclass(frozen=True)
class StayDiscountLinkMigrationResult:
    canonical_policies_seen: int
    trip_links_moved: int
    trip_links_deleted_as_duplicates: int
    saved_links_moved: int
    saved_links_deleted_as_duplicates: int
    missing_area_targets: int


def migrate_stay_discount_area_policy_links(
    db: Session,
    *,
    apply: bool = False,
) -> StayDiscountLinkMigrationResult:
    canonical_policies = list(
        db.scalars(
            select(Policy)
            .where(
                Policy.source_category == stay_discount_aliases.SOURCE_CATEGORY,
                Policy.external_source_record_id.is_not(None),
                Policy.slug.not_like(f"{stay_discount_aliases.ALIAS_PREFIX}-%"),
            )
            .order_by(Policy.id)
        ).all()
    )
    result = _MutableResult(canonical_policies_seen=len(canonical_policies))
    for canonical_policy in canonical_policies:
        area_policies = _area_policies_for_canonical(db, canonical_policy)
        if not area_policies:
            result.missing_area_targets += 1
            continue
        _move_trip_links(db, canonical_policy, area_policies, result, apply=apply)
        _move_saved_links(db, canonical_policy, area_policies[0], result, apply=apply)
    return result.freeze()


@dataclass
class _MutableResult:
    canonical_policies_seen: int = 0
    trip_links_moved: int = 0
    trip_links_deleted_as_duplicates: int = 0
    saved_links_moved: int = 0
    saved_links_deleted_as_duplicates: int = 0
    missing_area_targets: int = 0

    def freeze(self) -> StayDiscountLinkMigrationResult:
        return StayDiscountLinkMigrationResult(**self.__dict__)


def _area_policies_for_canonical(db: Session, canonical_policy: Policy) -> list[Policy]:
    same_source_area_policies = list(
        db.scalars(
            select(Policy)
            .where(
                Policy.source_category == stay_discount_aliases.SOURCE_CATEGORY,
                Policy.external_source_record_id == canonical_policy.external_source_record_id,
                Policy.slug.like(f"{stay_discount_aliases.ALIAS_PREFIX}-%"),
            )
            .order_by(Policy.id)
        ).all()
    )
    if same_source_area_policies:
        return same_source_area_policies

    return list(
        db.scalars(
            select(Policy)
            .where(
                Policy.source_category == stay_discount_aliases.SOURCE_CATEGORY,
                Policy.status == "active",
                Policy.slug.like(f"{stay_discount_aliases.ALIAS_PREFIX}-%"),
            )
            .order_by(Policy.id)
        ).all()
    )


def _move_trip_links(
    db: Session,
    canonical_policy: Policy,
    area_policies: list[Policy],
    result: _MutableResult,
    *,
    apply: bool,
) -> None:
    trip_links = list(
        db.scalars(
            select(TripPolicy)
            .where(TripPolicy.policy_id == canonical_policy.id)
            .order_by(TripPolicy.id)
        ).all()
    )
    for link in trip_links:
        target_policy = _select_area_policy_for_trip(area_policies, link.trip)
        duplicate = db.scalar(
            select(TripPolicy).where(
                TripPolicy.trip_id == link.trip_id,
                TripPolicy.policy_id == target_policy.id,
            )
        )
        if duplicate is not None:
            result.trip_links_deleted_as_duplicates += 1
            if apply:
                db.delete(link)
            continue
        result.trip_links_moved += 1
        if apply:
            link.policy_id = target_policy.id


def _move_saved_links(
    db: Session,
    canonical_policy: Policy,
    target_policy: Policy,
    result: _MutableResult,
    *,
    apply: bool,
) -> None:
    saved_links = list(
        db.scalars(
            select(UserSavedPolicy)
            .where(UserSavedPolicy.policy_id == canonical_policy.id)
            .order_by(UserSavedPolicy.id)
        ).all()
    )
    for link in saved_links:
        duplicate = db.scalar(
            select(UserSavedPolicy).where(
                UserSavedPolicy.user_id == link.user_id,
                UserSavedPolicy.policy_id == target_policy.id,
            )
        )
        if duplicate is not None:
            result.saved_links_deleted_as_duplicates += 1
            if apply:
                db.delete(link)
            continue
        result.saved_links_moved += 1
        if apply:
            link.policy_id = target_policy.id


def _select_area_policy_for_trip(area_policies: list[Policy], trip: Trip | None) -> Policy:
    if trip is None:
        return area_policies[0]
    context = " ".join(
        str(value or "")
        for value in [trip.title, trip.region, trip.travel_area_id, trip.description]
    ).casefold()
    return max(area_policies, key=lambda policy: (_trip_policy_match_score(policy, context), -(policy.id or 0)))


def _trip_policy_match_score(policy: Policy, context: str) -> int:
    score = 0
    region = str(policy.region or "").casefold()
    if region and region in context:
        score += 1
    title_match = _BRACKET_CITY_PATTERN.search(policy.title or "")
    city = title_match.group("city").casefold() if title_match else ""
    if city and city in context:
        score += 3
    slug = str(policy.slug or "").casefold()
    if slug and slug in context:
        score += 5
    return score


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move stay-discount canonical policy links to persisted area policy rows."
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes. Defaults to dry-run.")
    args = parser.parse_args(argv)

    session_factory = get_session_factory()
    with session_factory() as db:
        result = migrate_stay_discount_area_policy_links(db, apply=args.apply)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
