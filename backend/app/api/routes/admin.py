from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.admin import (
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
from app.services import admin as admin_service


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
