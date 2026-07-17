from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord, PolicySlugAlias
from app.models import Policy as PolicyModel
from app.repositories import external_sources as external_source_repository
from app.repositories import policies as policy_repository
from app.services import stay_discount_aliases
from app.services.policy_semantics import is_public_policy


SlugResolutionKind = Literal[
    "canonical",
    "persisted_alias",
    "virtual_stay_discount_alias",
    "raw_fallback",
]


@dataclass(frozen=True)
class SlugResolution:
    policy: PolicyModel | None
    request_slug: str
    canonical_slug: str
    kind: SlugResolutionKind
    should_redirect: bool
    alias_area: stay_discount_aliases.StayDiscountAliasArea | None = None
    external_record: ExternalSourceRecord | None = None


def canonical_slug_for_policy(policy: PolicyModel) -> str:
    return policy.slug or str(policy.id)


def canonical_slug_for_external_record(record: ExternalSourceRecord) -> str:
    return f"{external_source_repository.EXTERNAL_POLICY_SLUG_PREFIX}{record.id}"


def resolve_policy_slug(
    db: Session,
    request_slug: str,
    *,
    include_raw_fallback: bool = False,
    include_inactive_direct_lookup: bool = False,
) -> SlugResolution | None:
    active_policy = _get_policy_by_request_slug(
        db,
        request_slug,
        include_inactive=False,
    )
    if active_policy is not None and is_public_policy(active_policy):
        return SlugResolution(
            policy=active_policy,
            request_slug=request_slug,
            canonical_slug=canonical_slug_for_policy(active_policy),
            kind="canonical",
            should_redirect=False,
        )

    alias = _get_active_slug_alias(db, request_slug)
    if alias is not None and alias.policy is not None:
        policy = alias.policy
        if not is_public_policy(policy):
            return None
        canonical_slug = canonical_slug_for_policy(policy)
        return SlugResolution(
            policy=policy,
            request_slug=request_slug,
            canonical_slug=canonical_slug,
            kind="persisted_alias",
            should_redirect=canonical_slug != request_slug,
        )

    if include_inactive_direct_lookup:
        direct_policy = _get_policy_by_request_slug(
            db,
            request_slug,
            include_inactive=True,
        )
        if direct_policy is not None:
            if not is_public_policy(direct_policy):
                return None
            return SlugResolution(
                policy=direct_policy,
                request_slug=request_slug,
                canonical_slug=canonical_slug_for_policy(direct_policy),
                kind="canonical",
                should_redirect=False,
            )

    stay_alias_resolution = _resolve_virtual_stay_discount_alias(db, request_slug)
    if stay_alias_resolution is not None:
        return stay_alias_resolution

    if not include_raw_fallback:
        return None

    external_record = _get_external_record_by_policy_slug(db, request_slug)
    if external_record is None:
        return None
    return SlugResolution(
        policy=None,
        request_slug=request_slug,
        canonical_slug=canonical_slug_for_external_record(external_record),
        kind="raw_fallback",
        should_redirect=False,
        external_record=external_record,
    )


def _get_policy_by_request_slug(
    db: Session,
    request_slug: str,
    *,
    include_inactive: bool,
) -> PolicyModel | None:
    if include_inactive:
        return policy_repository.get_policy_by_slug_any_status(db, request_slug)
    return policy_repository.get_policy_by_slug(db, request_slug)


def _resolve_virtual_stay_discount_alias(
    db: Session,
    request_slug: str,
) -> SlugResolution | None:
    alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(
        db,
        request_slug,
    )
    if alias_resolution is None:
        return None
    policy = alias_resolution.canonical_policy
    if not is_public_policy(policy):
        return None
    return SlugResolution(
        policy=policy,
        request_slug=request_slug,
        canonical_slug=canonical_slug_for_policy(policy),
        kind="virtual_stay_discount_alias",
        should_redirect=False,
        alias_area=alias_resolution.alias_area,
    )


def _get_active_slug_alias(db: Session, request_slug: str) -> PolicySlugAlias | None:
    return policy_repository.get_active_slug_alias_by_old_slug(db, request_slug)


def _get_external_record_by_policy_slug(
    db: Session,
    request_slug: str,
) -> ExternalSourceRecord | None:
    return external_source_repository.get_external_source_record_by_policy_slug(
        db,
        request_slug,
    )
