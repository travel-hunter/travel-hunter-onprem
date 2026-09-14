from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.admin import (
    AdminCollectionSourceItem,
    AdminCollectionSourceListResponse,
    AdminCollectionSourceUpdateRequest,
    AdminPolicyReviewCandidateItem,
    AdminPolicyReviewCandidateListResponse,
    AdminPolicyReviewBatchApproveRequest,
    AdminPolicyReviewBatchApproveResponse,
    AdminPolicyReviewDecisionRequest,
    AdminPolicyReviewRejectRequest,
    AdminAuditLogListResponse,
    AdminExternalSourceSummaryResponse,
    AdminPolicyCreateRequest,
    AdminPolicyDetail,
    AdminPolicyListResponse,
    AdminPolicyUpdateRequest,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from app.repositories import policy_collection_sources
from app.services import admin as admin_service
from app.services import policy_candidate_review


router = APIRouter(prefix="/admin", tags=["admin"])


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is required")
    return db


def _handle_admin_error(error: admin_service.AdminServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    q: str | None = None,
    onboarding_completed: bool | None = Query(default=None, alias="onboardingCompleted"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminUserListResponse:
    return AdminUserListResponse(
        **admin_service.list_users(
            _require_db(db),
            current_admin,
            q=q,
            onboarding_completed=onboarding_completed,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(
    user_id: str,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminUserDetail:
    try:
        return AdminUserDetail(**admin_service.get_user(_require_db(db), current_admin, user_id))
    except admin_service.AdminServiceError as error:
        _handle_admin_error(error)


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminUserDetail:
    try:
        return AdminUserDetail(
            **admin_service.update_user(_require_db(db), current_admin, user_id, payload)
        )
    except admin_service.AdminServiceError as error:
        _handle_admin_error(error)


@router.get("/external-sources/summary", response_model=AdminExternalSourceSummaryResponse)
def get_external_source_summary(
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminExternalSourceSummaryResponse:
    return AdminExternalSourceSummaryResponse(
        **admin_service.get_external_source_summary(_require_db(db), current_admin)
    )


@router.get("/policies", response_model=AdminPolicyListResponse)
def list_policies(
    q: str | None = None,
    category: str | None = None,
    region: str | None = None,
    source_type: str | None = Query(default=None, alias="sourceType"),
    status: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyListResponse:
    return AdminPolicyListResponse(
        **admin_service.list_policies(
            _require_db(db),
            current_admin,
            q=q,
            category=category,
            region=region,
            source_type=source_type,
            status=status,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/policies", response_model=AdminPolicyDetail)
def create_policy(
    payload: AdminPolicyCreateRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyDetail:
    try:
        return AdminPolicyDetail(**admin_service.create_policy(_require_db(db), current_admin, payload))
    except admin_service.AdminServiceError as error:
        _handle_admin_error(error)


@router.get("/policies/{policy_id}", response_model=AdminPolicyDetail)
def get_policy(
    policy_id: str,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyDetail:
    try:
        return AdminPolicyDetail(**admin_service.get_policy(_require_db(db), current_admin, policy_id))
    except admin_service.AdminServiceError as error:
        _handle_admin_error(error)


@router.patch("/policies/{policy_id}", response_model=AdminPolicyDetail)
def update_policy(
    policy_id: str,
    payload: AdminPolicyUpdateRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyDetail:
    try:
        return AdminPolicyDetail(
            **admin_service.update_policy(_require_db(db), current_admin, policy_id, payload)
        )
    except admin_service.AdminServiceError as error:
        _handle_admin_error(error)


@router.get("/audit-logs", response_model=AdminAuditLogListResponse)
def list_audit_logs(
    target_type: str | None = Query(default=None, alias="targetType"),
    target_id: str | None = Query(default=None, alias="targetId"),
    action: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminAuditLogListResponse:
    return AdminAuditLogListResponse(
        **admin_service.list_audit_logs(
            _require_db(db),
            current_admin,
            target_type=target_type,
            target_id=target_id,
            action=action,
            limit=limit,
            offset=offset,
        )
    )


def _candidate_item(candidate, record) -> AdminPolicyReviewCandidateItem:
    return AdminPolicyReviewCandidateItem(
        id=str(candidate.id),
        externalSourceRecordId=str(record.id),
        reviewStatus=candidate.review_status,
        changeKind=candidate.change_kind,
        title=record.title,
        sourceCategory=record.source_category,
        officialUrl=record.detail_url or record.source_url,
        benefitText=record.benefit_text,
        region=record.region,
        city=record.city,
        status=record.status,
        startDate=record.start_date,
        endDate=record.end_date,
        createdAt=candidate.created_at.isoformat(),
    )


@router.get("/policy-review-candidates", response_model=AdminPolicyReviewCandidateListResponse)
def list_policy_review_candidates(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminPolicyReviewCandidateListResponse:
    session = _require_db(db)
    rows = policy_candidate_review.list_pending_candidates(session, limit=limit, offset=offset)
    return AdminPolicyReviewCandidateListResponse(
        items=[_candidate_item(candidate, record) for candidate, record in rows],
        total=policy_candidate_review.count_pending_candidates(session),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/policy-review-candidates/approve-batch",
    response_model=AdminPolicyReviewBatchApproveResponse,
)
def approve_policy_review_candidates_batch(
    payload: AdminPolicyReviewBatchApproveRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyReviewBatchApproveResponse:
    session = _require_db(db)
    try:
        approved = policy_candidate_review.approve_pending_candidates(
            session,
            candidate_ids=payload.candidateIds,
            approve_all=payload.approveAll,
            admin=current_admin,
            note=payload.note,
        )
        session.commit()
    except ValueError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        session.rollback()
        raise
    return AdminPolicyReviewBatchApproveResponse(
        approvedCount=len(approved),
        approvedCandidateIds=[str(candidate.id) for candidate in approved],
    )

def _candidate_or_404(db: Session, candidate_id: str):
    try:
        numeric_id = int(candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Policy review candidate not found") from None
    resolved = policy_candidate_review.get_candidate_with_record(db, candidate_id=numeric_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Policy review candidate not found")
    return resolved


@router.post("/policy-review-candidates/{candidate_id}/approve", response_model=AdminPolicyReviewCandidateItem)
def approve_policy_review_candidate(
    candidate_id: str,
    payload: AdminPolicyReviewDecisionRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyReviewCandidateItem:
    session = _require_db(db)
    candidate, record = _candidate_or_404(session, candidate_id)
    try:
        approved = policy_candidate_review.approve_candidate(
            session, candidate=candidate, record=record, admin=current_admin, note=payload.note
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.commit()
    return _candidate_item(approved, record)


@router.post("/policy-review-candidates/{candidate_id}/reject", response_model=AdminPolicyReviewCandidateItem)
def reject_policy_review_candidate(
    candidate_id: str,
    payload: AdminPolicyReviewRejectRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminPolicyReviewCandidateItem:
    session = _require_db(db)
    candidate, record = _candidate_or_404(session, candidate_id)
    try:
        rejected = policy_candidate_review.reject_candidate(
            session, candidate=candidate, admin=current_admin, note=payload.note
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.commit()
    return _candidate_item(rejected, record)


def _collection_source_item(source) -> AdminCollectionSourceItem:
    return AdminCollectionSourceItem(
        key=source.key,
        displayName=source.display_name,
        officialUrl=source.official_url,
        sourceCategory=source.source_category,
        enabled=source.enabled,
        publicationMode=source.publication_mode,
        lastOutcome=source.last_outcome,
        lastCollectedAt=source.last_collected_at.isoformat() if source.last_collected_at else None,
        lastError=source.last_error,
    )


@router.get("/policy-collection-sources", response_model=AdminCollectionSourceListResponse)
def list_policy_collection_sources(
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminCollectionSourceListResponse:
    return AdminCollectionSourceListResponse(
        items=[_collection_source_item(source) for source in policy_collection_sources.list_collection_sources(_require_db(db))]
    )


@router.patch("/policy-collection-sources/{source_key}", response_model=AdminCollectionSourceItem)
def update_policy_collection_source(
    source_key: str,
    payload: AdminCollectionSourceUpdateRequest,
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminCollectionSourceItem:
    session = _require_db(db)
    source = policy_collection_sources.get_collection_source_by_key(session, key=source_key)
    if source is None:
        raise HTTPException(status_code=404, detail="Policy collection source not found")
    updated = policy_collection_sources.update_collection_source_enabled(
        session, source=source, enabled=payload.enabled
    )
    session.commit()
    return _collection_source_item(updated)
