from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.models import ExternalSourceRecord, Policy, PolicyReviewCandidate, User
from app.repositories import admin as admin_repository
from app.services import policy_normalization, policy_semantic_mapping


def evidence_fingerprint(record: ExternalSourceRecord) -> str:
    payload = {
        "title": record.title,
        "organizer": record.organizer_text,
        "benefit": record.benefit_text,
        "startDate": record.start_date.isoformat() if record.start_date else None,
        "endDate": record.end_date.isoformat() if record.end_date else None,
        "region": record.region,
        "city": record.city,
        "officialUrl": record.detail_url or record.source_url,
        "status": record.status,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def classify_candidate(
    db: Session, *, record: ExternalSourceRecord
) -> PolicyReviewCandidate:
    if record.id is None:
        raise ValueError("External source record must be persisted before review")
    locked_record = db.scalar(
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.id == record.id)
        .with_for_update()
    )
    if locked_record is None:
        raise ValueError("External source record must be persisted before review")

    fingerprint = evidence_fingerprint(locked_record)
    latest = db.scalar(
        select(PolicyReviewCandidate)
        .where(PolicyReviewCandidate.external_source_record_id == locked_record.id)
        .order_by(PolicyReviewCandidate.created_at.desc(), PolicyReviewCandidate.id.desc())
        .limit(1)
        .with_for_update()
    )
    if latest is not None and latest.evidence_fingerprint == fingerprint:
        return latest
    if latest is not None and latest.review_status in {"pending", "rejected"}:
        latest.review_status = "superseded"
        db.add(latest)

    candidate = PolicyReviewCandidate(
        external_source_record_id=locked_record.id,
        review_status="pending",
        change_kind="material_change" if latest is not None else "new",
        evidence_fingerprint=fingerprint,
    )
    db.add(candidate)
    db.flush()
    return candidate

def reject_candidate(
    db: Session,
    *,
    candidate: PolicyReviewCandidate,
    admin: User,
    note: str,
) -> PolicyReviewCandidate:
    cleaned_note = note.strip()
    if not cleaned_note:
        raise ValueError("A rejection note is required")
    resolved = get_candidate_with_record(db, candidate_id=int(candidate.id), lock=True)
    if resolved is None:
        raise ValueError("Policy review candidate not found")
    candidate, _record = resolved
    if candidate.review_status != "pending":
        raise ValueError("Only pending candidates can be rejected")
    candidate.review_status = "rejected"
    candidate.review_note = cleaned_note
    candidate.reviewed_by_user_id = admin.id
    candidate.reviewed_at = security.utc_now_naive()
    db.add(candidate)
    db.flush()
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(admin.id),
        action="policy_review.reject",
        target_type="policy_review_candidate",
        target_id=str(candidate.id),
        summary=f"Rejected source candidate {candidate.external_source_record_id}",
        before_json={"reviewStatus": "pending"},
        after_json={"reviewStatus": "rejected", "note": cleaned_note},
    )
    return candidate

def get_candidate_with_record(
    db: Session,
    *,
    candidate_id: int,
    lock: bool = False,
) -> tuple[PolicyReviewCandidate, ExternalSourceRecord] | None:
    statement = (
        select(PolicyReviewCandidate, ExternalSourceRecord)
        .join(
            ExternalSourceRecord,
            PolicyReviewCandidate.external_source_record_id == ExternalSourceRecord.id,
        )
        .where(PolicyReviewCandidate.id == candidate_id)
    )
    if lock:
        statement = statement.execution_options(populate_existing=True).with_for_update(of=PolicyReviewCandidate)
    return db.execute(statement).one_or_none()

def list_pending_candidates(
    db: Session,
    *,
    limit: int | None = 50,
    offset: int = 0,
) -> list[tuple[PolicyReviewCandidate, ExternalSourceRecord]]:
    statement = (
        select(PolicyReviewCandidate, ExternalSourceRecord)
        .join(
            ExternalSourceRecord,
            PolicyReviewCandidate.external_source_record_id == ExternalSourceRecord.id,
        )
        .where(PolicyReviewCandidate.review_status == "pending")
        .order_by(PolicyReviewCandidate.created_at.asc(), PolicyReviewCandidate.id.asc())
        .offset(offset)
    )
    if limit is not None:
        statement = statement.limit(limit)
    return list(db.execute(statement).all())


def count_pending_candidates(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(PolicyReviewCandidate)
            .where(PolicyReviewCandidate.review_status == "pending")
        )
        or 0
    )


def approve_pending_candidates(
    db: Session,
    *,
    candidate_ids: list[str],
    approve_all: bool,
    admin: User,
    note: str | None = None,
) -> list[PolicyReviewCandidate]:
    if approve_all:
        if candidate_ids:
            raise ValueError("candidateIds must be empty when approveAll is true")
        resolved = list_pending_candidates(db, limit=None)
    else:
        if not candidate_ids:
            raise ValueError("Select at least one candidate")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidateIds must not contain duplicates")
        try:
            numeric_ids = sorted(int(candidate_id) for candidate_id in candidate_ids)
        except ValueError as error:
            raise ValueError("Policy review candidate not found") from error
        resolved = []
        for numeric_id in numeric_ids:
            candidate_and_record = get_candidate_with_record(db, candidate_id=numeric_id, lock=True)
            if candidate_and_record is None:
                raise ValueError("Policy review candidate not found")
            resolved.append(candidate_and_record)

    if not resolved:
        raise ValueError("There are no pending candidates to approve")
    if any(candidate.review_status != "pending" for candidate, _record in resolved):
        raise ValueError("Only pending candidates can be approved")

    return [
        approve_candidate(db, candidate=candidate, record=record, admin=admin, note=note)
        for candidate, record in resolved
    ]

def approve_candidate(
    db: Session,
    *,
    candidate: PolicyReviewCandidate,
    record: ExternalSourceRecord,
    admin: User,
    note: str | None = None,
) -> PolicyReviewCandidate:
    resolved = get_candidate_with_record(db, candidate_id=int(candidate.id), lock=True)
    if resolved is None:
        raise ValueError("Policy review candidate not found")
    candidate, record = resolved
    if candidate.review_status != "pending":
        raise ValueError("Only pending candidates can be approved")
    policy = _publish_candidate(db, candidate=candidate, record=record)
    candidate.review_note = note.strip() if note and note.strip() else None
    candidate.reviewed_by_user_id = admin.id
    db.add(candidate)
    db.flush()
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(admin.id),
        action="policy_review.approve",
        target_type="policy_review_candidate",
        target_id=str(candidate.id),
        summary=f"Approved source candidate {record.canonical_key}",
        before_json={"reviewStatus": "pending"},
        after_json={"reviewStatus": "approved", "policyId": str(policy.id)},
    )
    return candidate


def _publish_candidate(db: Session, *, candidate: PolicyReviewCandidate, record: ExternalSourceRecord):
    policy = policy_normalization.promote_external_benefit_record(db, record=record)
    candidate.review_status = "approved"
    candidate.reviewed_at = security.utc_now_naive()
    candidate.published_policy_id = policy.id
    return policy


# --- auto-publish gate ------------------------------------------------------------------------
# Spec: docs/superpowers/specs/2026-09-14-policy-auto-publish-design.md. Rules run in order; the
# first failing rule becomes review_reason. Passing every rule publishes the candidate right away.

AUTO_PUBLISH_MODE = "auto_after_reviewed_baseline"
REVIEW_REASON_AUTO = "auto"
AUTO_PUBLISH_MIN_CONFIDENCE = 70
AUTO_PUBLISH_MIN_COMPLETENESS = 60
AUTO_PUBLISH_MAX_SHRINK_PERCENT = 30
_MANUAL_SOURCE_CATEGORIES = {"stay_discount"}


def human_baseline_admin_id(db: Session, *, source_category: str) -> int | None:
    """The admin who most recently approved a candidate of this source by hand — owns the automation."""
    return db.scalar(
        select(PolicyReviewCandidate.reviewed_by_user_id)
        .join(ExternalSourceRecord, PolicyReviewCandidate.external_source_record_id == ExternalSourceRecord.id)
        .where(
            ExternalSourceRecord.source_category == source_category,
            PolicyReviewCandidate.review_status == "approved",
            PolicyReviewCandidate.reviewed_by_user_id.is_not(None),
        )
        .order_by(PolicyReviewCandidate.reviewed_at.desc(), PolicyReviewCandidate.id.desc())
    )


def _published_policy_for_record(db: Session, record: ExternalSourceRecord) -> Policy | None:
    policy_id = db.scalar(
        select(PolicyReviewCandidate.published_policy_id)
        .where(
            PolicyReviewCandidate.external_source_record_id == record.id,
            PolicyReviewCandidate.review_status == "approved",
            PolicyReviewCandidate.published_policy_id.is_not(None),
        )
        .order_by(PolicyReviewCandidate.id.desc())
    )
    return db.get(Policy, policy_id) if policy_id is not None else None


def _source_run_is_normal(source, source_result) -> bool:
    if source_result is None or source_result.outcome != "success":
        return False
    parsed = source_result.parsed_count
    if parsed < (source.expected_min_records or 0):
        return False
    previous = source.last_parsed_count
    if previous and (previous - parsed) * 100 > AUTO_PUBLISH_MAX_SHRINK_PERCENT * previous:
        return False
    return True


def _hold_reason(db: Session, *, candidate: PolicyReviewCandidate, record: ExternalSourceRecord, source, source_result) -> str | None:
    if source is None or source.publication_mode != AUTO_PUBLISH_MODE:
        return "source_mode_review"
    if record.source_category in _MANUAL_SOURCE_CATEGORIES:
        return "stay_discount_manual"
    if human_baseline_admin_id(db, source_category=record.source_category or "") is None:
        return "first_baseline"
    if not _source_run_is_normal(source, source_result):
        return "source_anomaly"
    published = _published_policy_for_record(db, record) if candidate.change_kind == "material_change" else None
    if published is None:
        return "new_policy"
    if (published.title, published.region, published.city) != (record.title, record.region, record.city):
        return "identity_changed"
    if (
        record.status == "ended"
        or record.freshness_status == "stale"
        or policy_semantic_mapping.map_external_source_semantics(record).policy_status == "hidden"
    ):
        return "would_publish_hidden"
    if (
        (record.confidence or 0) < AUTO_PUBLISH_MIN_CONFIDENCE
        or (record.field_completeness or 0) < AUTO_PUBLISH_MIN_COMPLETENESS
        or not (record.benefit_text or "").strip()
    ):
        return "low_confidence"
    return None


def auto_publish_gate(
    db: Session,
    *,
    candidate: PolicyReviewCandidate,
    record: ExternalSourceRecord,
    source,
    source_result,
) -> str:
    """Publish a freshly created pending candidate when every rule passes; otherwise record why it waits."""
    reason = _hold_reason(db, candidate=candidate, record=record, source=source, source_result=source_result)
    if reason is not None:
        candidate.review_reason = reason
        db.add(candidate)
        db.flush()
        return reason

    owner_id = human_baseline_admin_id(db, source_category=record.source_category or "")
    policy = _publish_candidate(db, candidate=candidate, record=record)
    candidate.review_note = REVIEW_REASON_AUTO
    candidate.review_reason = REVIEW_REASON_AUTO
    candidate.reviewed_by_user_id = None
    db.add(candidate)
    db.flush()
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(owner_id),
        action="policy_review.auto_approve",
        target_type="policy_review_candidate",
        target_id=str(candidate.id),
        summary=f"Auto-published source candidate {record.canonical_key}",
        before_json={"reviewStatus": "pending"},
        after_json={"reviewStatus": "approved", "policyId": str(policy.id), "actor": "system"},
    )
    return REVIEW_REASON_AUTO
