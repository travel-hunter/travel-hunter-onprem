from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.admin import (
    AdminCollectionSourceItem,
    AdminCollectionSourceListResponse,
    AdminCollectionSourceUpdateRequest,
    AdminEligibleIslandAttachment,
    AdminEligibleIslandCollectResponse,
    AdminEligibleIslandEntry,
    AdminEligibleIslandRejectRequest,
    AdminEligibleIslandSnapshotDetail,
    AdminEligibleIslandSnapshotItem,
    AdminEligibleIslandSnapshotListResponse,
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
from app.repositories import eligible_islands as eligible_island_repository
from app.repositories import policy_collection_sources
from app.repositories.eligible_islands import EligibleIslandCatalogError
from app.services import admin as admin_service
from app.services import eligible_island_catalog, eligible_island_notice
from app.services import policy_candidate_review
from app.services.policy_normalization import PolicyNormalizationError


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
        reviewReason=getattr(candidate, "review_reason", None),
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
    except (ValueError, PolicyNormalizationError) as error:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception:
        session.rollback()
        raise
    return AdminPolicyReviewBatchApproveResponse(
        approvedCount=len(approved),
        approvedCandidateIds=[str(candidate.id) for candidate in approved],
    )

def _candidate_or_404(db: Session, candidate_id: str, *, lock: bool = False):
    try:
        numeric_id = int(candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Policy review candidate not found") from None
    resolved = policy_candidate_review.get_candidate_with_record(db, candidate_id=numeric_id, lock=lock)
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
    candidate, record = _candidate_or_404(session, candidate_id, lock=True)
    try:
        approved = policy_candidate_review.approve_candidate(
            session, candidate=candidate, record=record, admin=current_admin, note=payload.note
        )
    except (ValueError, PolicyNormalizationError) as error:
        session.rollback()
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
    candidate, record = _candidate_or_404(session, candidate_id, lock=True)
    try:
        rejected = policy_candidate_review.reject_candidate(
            session, candidate=candidate, admin=current_admin, note=payload.note
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.commit()
    return _candidate_item(rejected, record)


def _auto_approved_last_24h(db: Session, source_category: str) -> int:
    if not hasattr(db, "scalars"):
        return 0
    return policy_candidate_review.count_auto_approved_since(
        db, source_category=source_category, since=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    )


def _collection_source_item(source, *, auto_approved_last_24h: int = 0) -> AdminCollectionSourceItem:
    return AdminCollectionSourceItem(
        key=source.key,
        displayName=source.display_name,
        officialUrl=source.official_url,
        sourceCategory=source.source_category,
        enabled=source.enabled,
        publicationMode=source.publication_mode,
        expectedMinRecords=getattr(source, "expected_min_records", 0) or 0,
        lastParsedCount=getattr(source, "last_parsed_count", None),
        autoApprovedLast24h=auto_approved_last_24h,
        lastOutcome=source.last_outcome,
        lastCollectedAt=source.last_collected_at.isoformat() if source.last_collected_at else None,
        lastError=source.last_error,
    )


@router.get("/policy-collection-sources", response_model=AdminCollectionSourceListResponse)
def list_policy_collection_sources(
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminCollectionSourceListResponse:
    session = _require_db(db)
    return AdminCollectionSourceListResponse(
        items=[
            _collection_source_item(source, auto_approved_last_24h=_auto_approved_last_24h(session, source.source_category))
            for source in policy_collection_sources.list_collection_sources(session)
        ]
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
    if (
        payload.publicationMode == policy_candidate_review.AUTO_PUBLISH_MODE
        and source.publication_mode != policy_candidate_review.AUTO_PUBLISH_MODE
        and policy_candidate_review.human_baseline_admin_id(session, source_category=source.source_category) is None
    ):
        raise HTTPException(status_code=409, detail="baseline_required")
    updated = policy_collection_sources.update_collection_source(
        session,
        source=source,
        enabled=payload.enabled,
        publication_mode=payload.publicationMode,
        expected_min_records=payload.expectedMinRecords,
    )
    session.commit()
    return _collection_source_item(updated, auto_approved_last_24h=_auto_approved_last_24h(session, updated.source_category))


# --- Eligible island catalog review (separate from policy review candidates) ---

_ELIGIBLE_ISLAND_ERROR_STATUS = {
    "catalog_not_found": 404,
    "snapshot_not_found": 404,
    "snapshot_not_pending": 409,
    "note_required": 422,
}


def _raise_eligible_island_error(error: EligibleIslandCatalogError) -> None:
    raise HTTPException(status_code=_ELIGIBLE_ISLAND_ERROR_STATUS.get(str(error), 400), detail=str(error)) from error


def _snapshot_item(snapshot, *, approved_snapshot_id: int | None) -> AdminEligibleIslandSnapshotItem:
    return AdminEligibleIslandSnapshotItem(
        id=str(snapshot.id),
        reviewStatus=snapshot.review_status,
        isCurrentApproved=snapshot.id == approved_snapshot_id,
        entryCount=snapshot.entry_count,
        addedCount=snapshot.added_count,
        removedCount=snapshot.removed_count,
        changedCount=snapshot.changed_count,
        sourceNoticeUrl=snapshot.notice_url,
        sourceNoticeTitle=snapshot.notice_title,
        attachmentFiles=[AdminEligibleIslandAttachment(**document) for document in (snapshot.attachment_documents or [])],
        attachmentFingerprint=snapshot.attachment_fingerprint,
        parserVersion=snapshot.parser_version,
        fetchedAt=snapshot.fetched_at.isoformat(),
        reviewedAt=snapshot.reviewed_at.isoformat() if snapshot.reviewed_at else None,
        reviewNote=snapshot.review_note,
        createdAt=snapshot.created_at.isoformat(),
    )


def _entry_item(row) -> AdminEligibleIslandEntry:
    return AdminEligibleIslandEntry(
        displayName=row.display_name, normalizedName=row.normalized_name, jurisdictionName=row.jurisdiction_name
    )


def _snapshot_id_or_404(snapshot_id: str) -> int:
    try:
        return int(snapshot_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="snapshot_not_found") from None


@router.post(
    "/eligible-island-catalogs/{catalog_key}/collect",
    response_model=AdminEligibleIslandCollectResponse,
)
def collect_eligible_island_catalog(
    catalog_key: str,
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminEligibleIslandCollectResponse:
    session = _require_db(db)
    try:
        eligible_island_repository.bootstrap_builtin_catalogs(session)
        notice_url = eligible_island_repository.get_catalog(session, catalog_key=catalog_key).notice_list_url
        session.commit()
        result = eligible_island_notice.collect_eligible_island_catalog(
            session, catalog_key=catalog_key, notice_url=notice_url, fetched_at=datetime.now(UTC)
        )
    except EligibleIslandCatalogError as error:
        session.rollback()
        _raise_eligible_island_error(error)
    return AdminEligibleIslandCollectResponse(
        outcome=result.outcome,
        snapshotId=str(result.snapshot_id) if result.snapshot_id is not None else None,
        entryCount=result.entry_count,
        error=result.error,
    )


@router.get(
    "/eligible-island-catalogs/{catalog_key}/snapshots",
    response_model=AdminEligibleIslandSnapshotListResponse,
)
def list_eligible_island_snapshots(
    catalog_key: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminEligibleIslandSnapshotListResponse:
    session = _require_db(db)
    try:
        catalog = eligible_island_repository.get_catalog(session, catalog_key=catalog_key)
    except EligibleIslandCatalogError as error:
        _raise_eligible_island_error(error)
    rows, total = eligible_island_repository.list_snapshots(session, catalog_id=catalog.id, limit=limit, offset=offset)
    return AdminEligibleIslandSnapshotListResponse(
        items=[_snapshot_item(row, approved_snapshot_id=catalog.approved_snapshot_id) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        approvedSnapshotId=str(catalog.approved_snapshot_id) if catalog.approved_snapshot_id is not None else None,
        approvedEntryCount=eligible_island_repository.count_approved_entries(session, catalog_id=catalog.id),
    )


@router.get(
    "/eligible-island-catalogs/{catalog_key}/snapshots/{snapshot_id}",
    response_model=AdminEligibleIslandSnapshotDetail,
)
def get_eligible_island_snapshot(
    catalog_key: str,
    snapshot_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session | None = Depends(get_optional_db),
    _current_admin: User = Depends(require_admin_user),
) -> AdminEligibleIslandSnapshotDetail:
    session = _require_db(db)
    numeric_id = _snapshot_id_or_404(snapshot_id)
    try:
        catalog = eligible_island_repository.get_catalog(session, catalog_key=catalog_key)
        diff = eligible_island_catalog.get_snapshot_diff(session, catalog_key=catalog_key, snapshot_id=numeric_id)
    except EligibleIslandCatalogError as error:
        _raise_eligible_island_error(error)
    window = slice(offset, offset + limit)
    return AdminEligibleIslandSnapshotDetail(
        snapshot=_snapshot_item(diff.snapshot, approved_snapshot_id=catalog.approved_snapshot_id),
        added=[_entry_item(row) for row in diff.added[window]],
        removed=[_entry_item(row) for row in diff.removed[window]],
        unchanged=[_entry_item(row) for row in diff.unchanged[window]],
        addedTotal=len(diff.added),
        removedTotal=len(diff.removed),
        unchangedTotal=len(diff.unchanged),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/eligible-island-catalogs/{catalog_key}/snapshots/{snapshot_id}/approve",
    response_model=AdminEligibleIslandSnapshotItem,
)
def approve_eligible_island_snapshot(
    catalog_key: str,
    snapshot_id: str,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminEligibleIslandSnapshotItem:
    session = _require_db(db)
    numeric_id = _snapshot_id_or_404(snapshot_id)
    try:
        snapshot = eligible_island_catalog.approve_snapshot(
            session, catalog_key=catalog_key, snapshot_id=numeric_id, admin=current_admin
        )
    except EligibleIslandCatalogError as error:
        session.rollback()
        _raise_eligible_island_error(error)
    return _snapshot_item(snapshot, approved_snapshot_id=snapshot.id)


@router.post(
    "/eligible-island-catalogs/{catalog_key}/snapshots/{snapshot_id}/reject",
    response_model=AdminEligibleIslandSnapshotItem,
)
def reject_eligible_island_snapshot(
    catalog_key: str,
    snapshot_id: str,
    payload: AdminEligibleIslandRejectRequest,
    db: Session | None = Depends(get_optional_db),
    current_admin: User = Depends(require_admin_user),
) -> AdminEligibleIslandSnapshotItem:
    session = _require_db(db)
    numeric_id = _snapshot_id_or_404(snapshot_id)
    try:
        snapshot = eligible_island_catalog.reject_snapshot(
            session, catalog_key=catalog_key, snapshot_id=numeric_id, admin=current_admin, note=payload.note
        )
    except EligibleIslandCatalogError as error:
        session.rollback()
        _raise_eligible_island_error(error)
    approved_id = eligible_island_repository.get_catalog(session, catalog_key=catalog_key).approved_snapshot_id
    session.commit()
    return _snapshot_item(snapshot, approved_snapshot_id=approved_id)
