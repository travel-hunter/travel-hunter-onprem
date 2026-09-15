from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.models import ExternalSourceRecord, PolicyReviewCandidate, User
from app.repositories import admin as admin_repository
from app.services import policy_normalization


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
    policy = policy_normalization.promote_external_benefit_record(db, record=record)
    candidate.review_status = "approved"
    candidate.review_note = note.strip() if note and note.strip() else None
    candidate.reviewed_by_user_id = admin.id
    candidate.reviewed_at = security.utc_now_naive()
    candidate.published_policy_id = policy.id
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
