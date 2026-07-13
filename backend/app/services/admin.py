from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core import security
from app.data.policy_display import SUPPORTED_CATEGORIES
from app.models import Policy, User
from app.repositories import admin as admin_repository
from app.schemas.admin import (
    AdminPolicyCreateRequest,
    AdminPolicyUpdateRequest,
    AdminUserUpdateRequest,
)
from app.services import nicknames
from app.services.policy_requirements import (
    sanitize_requirement_items,
    sanitize_target_condition,
    split_requirement_lines,
)
from app.services.policy_structured_detail import build_structured_detail_from_policy
from app.services.profile_preferences import ProfilePreferenceError, serialize_preferred_regions


class AdminServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _iso(value: datetime | None) -> str:
    return (value or security.utc_now_naive()).isoformat()


def _date_iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _clean_items(values: list[str] | None) -> list[str]:
    return [value.strip() for value in values or [] if value.strip()]


def _normalize_admin_preferred_regions(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return serialize_preferred_regions(value.split(","))
    except ProfilePreferenceError as error:
        raise AdminServiceError(error.status_code, error.detail) from error


def _policy_source_type(policy: Policy) -> str:
    if policy.external_source_record_id is not None:
        return "external"
    return policy.source_type or "internal"


SOURCE_CATEGORY_LABELS = {
    "regional_benefit": "여행가는 달",
    "traffic_benefit": "교통혜택",
    "local_half_trip": "반값여행",
    "stay_discount": "숙박세일 페스타",
}

def _source_label(source_category: str | None) -> str:
    if not source_category:
        return "내부"
    return SOURCE_CATEGORY_LABELS.get(source_category, "외부")


def _user_list_item(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "role": getattr(user, "role", "user") or "user",
        "onboardingCompleted": bool(user.onboarding_completed),
        "createdAt": _iso(user.created_at),
        "updatedAt": _iso(user.updated_at),
    }


def _user_detail(user: User) -> dict[str, object]:
    return {
        **_user_list_item(user),
        "preferredRegions": user.preferred_regions,
        "travelStyle": user.travel_style,
        "travelBudget": user.travel_budget,
    }


def _user_audit_snapshot(user: User) -> dict[str, object]:
    return _user_detail(user)


def _policy_list_item(policy: Policy) -> dict[str, object]:
    source_category = policy.source_category
    return {
        "id": str(policy.id),
        "slug": policy.slug or str(policy.id),
        "title": policy.title,
        "organization": policy.organization,
        "policyType": policy.policy_type,
        "region": policy.region,
        "status": getattr(policy, "status", "active") or "active",
        "sourceType": _policy_source_type(policy),
        "sourceCategory": source_category,
        "sourceLabel": _source_label(source_category),
        "updatedAt": _iso(getattr(policy, "updated_at", None)),
    }


def _policy_detail(policy: Policy) -> dict[str, object]:
    return {
        **_policy_list_item(policy),
        "startDate": _date_iso(policy.start_date),
        "endDate": _date_iso(policy.end_date),
        "benefitAmount": policy.benefit_amount,
        "benefitDetail": policy.benefit_detail,
        "description": policy.description,
        "requirements": sanitize_requirement_items(split_requirement_lines(policy.target_condition)),
        "documents": [document.document_name for document in policy.documents],
        "officialUrl": policy.official_url,
        "applyUrl": policy.apply_url,
        "policyComment": policy.policy_comment,
        "policyPeriod": policy.policy_period,
        "adminOverrideEnabled": bool(getattr(policy, "admin_override_enabled", False)),
        "createdAt": _iso(policy.created_at),
    }


def _policy_audit_snapshot(policy: Policy) -> dict[str, object]:
    return _policy_detail(policy)


def _audit_log_item(log) -> dict[str, object]:
    return {
        "id": str(log.id),
        "adminUserId": str(log.admin_user_id),
        "adminEmail": log.admin_user.email if log.admin_user is not None else "",
        "action": log.action,
        "targetType": log.target_type,
        "targetId": log.target_id,
        "summary": log.summary,
        "beforeJson": log.before_json,
        "afterJson": log.after_json,
        "createdAt": _iso(log.created_at),
    }


def _record_audit(
    db: Session,
    *,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: str,
    summary: str,
    before_json: dict[str, object] | None,
    after_json: dict[str, object] | None,
) -> None:
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(admin_user.id),
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
    )


def _require_int_id(value: str, target_name: str) -> int:
    try:
        numeric_id = int(value)
    except ValueError:
        raise AdminServiceError(404, f"{target_name} not found") from None
    if numeric_id < 1:
        raise AdminServiceError(404, f"{target_name} not found")
    return numeric_id


def get_external_source_summary(db: Session, current_admin: User) -> dict[str, object]:
    _ = current_admin
    records = admin_repository.list_external_source_records(db)
    policies = admin_repository.list_external_source_policies(db)
    promoted_by_category: dict[str, list[Policy]] = defaultdict(list)
    for policy in policies:
        if policy.source_category:
            promoted_by_category[str(policy.source_category)].append(policy)

    items: list[dict[str, object]] = []
    categories = sorted({str(record.source_category) for record in records})
    for category in categories:
        category_records = [record for record in records if record.source_category == category]
        promoted_policies = promoted_by_category.get(category, [])
        latest_fetched = _latest_datetime(record.last_fetched_at for record in category_records)
        latest_verified = _latest_datetime(record.last_verified_at for record in category_records)
        source_name = str(category_records[0].source_name) if category_records else ""
        items.append(
            {
                "sourceCategory": category,
                "label": _source_label(category),
                "sourceName": source_name,
                "totalRecords": len(category_records),
                "activeRecords": sum(1 for record in category_records if record.status == "active"),
                "scheduledRecords": sum(1 for record in category_records if record.status == "scheduled"),
                "endedRecords": sum(1 for record in category_records if record.status == "ended"),
                "unknownRecords": sum(1 for record in category_records if record.status == "unknown"),
                "freshRecords": sum(1 for record in category_records if record.freshness_status == "fresh"),
                "promotedPolicyCount": len(promoted_policies),
                "activePromotedPolicyCount": sum(1 for policy in promoted_policies if policy.status == "active"),
                "latestFetchedAt": latest_fetched.isoformat() if latest_fetched else None,
                "latestVerifiedAt": latest_verified.isoformat() if latest_verified else None,
            }
        )

    latest_fetched_all = _latest_datetime(record.last_fetched_at for record in records)
    return {
        "items": items,
        "totalRecords": len(records),
        "activeRecords": sum(1 for record in records if record.status == "active"),
        "freshRecords": sum(1 for record in records if record.freshness_status == "fresh"),
        "promotedPolicyCount": len(policies),
        "latestFetchedAt": latest_fetched_all.isoformat() if latest_fetched_all else None,
    }


def _latest_datetime(values) -> datetime | None:
    dated_values = [value for value in values if value is not None]
    if not dated_values:
        return None
    return max(dated_values)

def list_users(
    db: Session,
    current_admin: User,
    *,
    q: str | None = None,
    onboarding_completed: bool | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    _ = current_admin
    rows, total = admin_repository.list_users(
        db,
        q=q,
        onboarding_completed=onboarding_completed,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_user_list_item(user) for user in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_user(db: Session, current_admin: User, user_id: str) -> dict[str, object]:
    _ = current_admin
    user = admin_repository.get_user(db, _require_int_id(user_id, "User"))
    if user is None:
        raise AdminServiceError(404, "User not found")
    return _user_detail(user)


def update_user(
    db: Session,
    current_admin: User,
    user_id: str,
    payload: AdminUserUpdateRequest,
) -> dict[str, object]:
    user = admin_repository.get_user(db, _require_int_id(user_id, "User"))
    if user is None:
        raise AdminServiceError(404, "User not found")

    values = payload.model_dump(exclude_unset=True)
    before = _user_audit_snapshot(user)
    if "nickname" in values and values["nickname"] is not None:
        nickname = nicknames.normalize_nickname(str(values["nickname"]))
        existing = admin_repository.get_user_by_nickname(db, nickname)
        if existing is not None and existing.id != user.id:
            raise AdminServiceError(409, "Nickname already used")
        user.nickname = nickname
    if "preferredRegions" in values:
        user.preferred_regions = _normalize_admin_preferred_regions(values["preferredRegions"])
    if "travelStyle" in values:
        user.travel_style = values["travelStyle"]
    if "travelBudget" in values:
        user.travel_budget = values["travelBudget"]
    if "onboardingCompleted" in values:
        user.onboarding_completed = bool(values["onboardingCompleted"])
    if "role" in values and values["role"] is not None and values["role"] != user.role:
        if user.id == current_admin.id and values["role"] == "user":
            raise AdminServiceError(409, "Admin cannot demote self")
        if user.role == "admin" and values["role"] == "user" and admin_repository.count_admin_users(db) <= 1:
            raise AdminServiceError(409, "Cannot remove final admin")
        user.role = values["role"]
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    after = _user_audit_snapshot(user)
    _record_audit(
        db,
        admin_user=current_admin,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        summary=f"Updated user {user.email}",
        before_json=before,
        after_json=after,
    )
    db.commit()
    return _user_detail(user)


def _validate_policy_category(value: str | None) -> None:
    if value is not None and value not in SUPPORTED_CATEGORIES:
        raise AdminServiceError(422, "Invalid policyType")


def _target_condition_from_values(values: dict[str, Any]) -> str | None:
    if "requirements" in values and values["requirements"] is not None:
        return sanitize_target_condition("\n".join(_clean_items(values["requirements"])))
    if "targetCondition" in values:
        return sanitize_target_condition(values["targetCondition"])
    return None


def _apply_policy_values(policy: Policy, values: dict[str, Any]) -> None:
    if "title" in values and values["title"] is not None:
        title = str(values["title"]).strip()
        if not title:
            raise AdminServiceError(422, "Policy title is required")
        policy.title = title
    if "organization" in values:
        policy.organization = values["organization"]
    if "policyType" in values and values["policyType"] is not None:
        _validate_policy_category(values["policyType"])
        policy.policy_type = values["policyType"]
    if "region" in values and values["region"] is not None:
        region = str(values["region"]).strip()
        if not region:
            raise AdminServiceError(422, "Policy region is required")
        policy.region = region
    if "startDate" in values:
        policy.start_date = values["startDate"]
    if "endDate" in values:
        policy.end_date = values["endDate"]
    if "benefitAmount" in values:
        policy.benefit_amount = values["benefitAmount"]
    if "benefitDetail" in values:
        policy.benefit_detail = values["benefitDetail"]
    if "description" in values:
        policy.description = values["description"]
    target_condition = _target_condition_from_values(values)
    if target_condition is not None:
        policy.target_condition = target_condition
    if "officialUrl" in values:
        policy.official_url = values["officialUrl"]
    if "applyUrl" in values:
        policy.apply_url = values["applyUrl"]
    if "policyComment" in values:
        policy.policy_comment = values["policyComment"]
    if "policyPeriod" in values:
        policy.policy_period = values["policyPeriod"]
    if "status" in values and values["status"] is not None:
        policy.status = values["status"]


def _refresh_policy_structured_detail(policy: Policy) -> None:
    policy.structured_detail = build_structured_detail_from_policy(policy)


def list_policies(
    db: Session,
    current_admin: User,
    *,
    q: str | None = None,
    category: str | None = None,
    region: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    _ = current_admin
    rows, total = admin_repository.list_policies(
        db,
        q=q,
        category=category,
        region=region,
        source_type=source_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_policy_list_item(policy) for policy in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_policy(db: Session, current_admin: User, policy_id: str) -> dict[str, object]:
    _ = current_admin
    policy = admin_repository.get_policy(db, _require_int_id(policy_id, "Policy"))
    if policy is None:
        raise AdminServiceError(404, "Policy not found")
    return _policy_detail(policy)


def create_policy(
    db: Session,
    current_admin: User,
    payload: AdminPolicyCreateRequest,
) -> dict[str, object]:
    if admin_repository.get_policy_by_slug(db, payload.slug) is not None:
        raise AdminServiceError(409, "Policy slug already exists")
    _validate_policy_category(payload.policyType)
    values = payload.model_dump(exclude_unset=True)
    policy = Policy(
        slug=payload.slug,
        title=payload.title.strip(),
        policy_type=payload.policyType,
        region=payload.region.strip(),
        source_type="internal",
        status=payload.status,
    )
    _apply_policy_values(policy, values)
    admin_repository.add_policy(db, policy)
    if payload.documents is not None:
        admin_repository.replace_policy_documents(db, policy, _clean_items(payload.documents))
    _refresh_policy_structured_detail(policy)
    after = _policy_audit_snapshot(policy)
    _record_audit(
        db,
        admin_user=current_admin,
        action="policy.create",
        target_type="policy",
        target_id=str(policy.id),
        summary=f"Created policy {policy.title}",
        before_json=None,
        after_json=after,
    )
    db.commit()
    return _policy_detail(policy)


def update_policy(
    db: Session,
    current_admin: User,
    policy_id: str,
    payload: AdminPolicyUpdateRequest,
) -> dict[str, object]:
    policy = admin_repository.get_policy(db, _require_int_id(policy_id, "Policy"))
    if policy is None:
        raise AdminServiceError(404, "Policy not found")
    values = payload.model_dump(exclude_unset=True)
    if "policyType" in values:
        _validate_policy_category(values["policyType"])
    before = _policy_audit_snapshot(policy)
    _apply_policy_values(policy, values)
    if "documents" in values and values["documents"] is not None:
        admin_repository.replace_policy_documents(db, policy, _clean_items(values["documents"]))
    _refresh_policy_structured_detail(policy)
    if _policy_source_type(policy) == "external":
        policy.admin_override_enabled = True
    policy.updated_at = security.utc_now_naive()
    db.add(policy)
    db.flush()
    after = _policy_audit_snapshot(policy)
    _record_audit(
        db,
        admin_user=current_admin,
        action="policy.update",
        target_type="policy",
        target_id=str(policy.id),
        summary=f"Updated policy {policy.title}",
        before_json=before,
        after_json=after,
    )
    db.commit()
    return _policy_detail(policy)


def list_audit_logs(
    db: Session,
    current_admin: User,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    action: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    _ = current_admin
    rows, total = admin_repository.list_audit_logs(
        db,
        target_type=target_type,
        target_id=target_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_audit_log_item(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
