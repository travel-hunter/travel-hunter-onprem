from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.policy import AppliedPolicyLink, Policy, SavePolicyResponse
from app.services import policies as policy_service

router = APIRouter(tags=["policies"])


def _require_user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.get("/policies", response_model=list[Policy])
def list_policies(db: Session | None = Depends(get_optional_db)) -> list[Policy]:
    return [Policy(**policy) for policy in policy_service.list_policies(db)]


@router.get("/policies/{policy_slug}", response_model=Policy)
def get_policy(
    policy_slug: str, db: Session | None = Depends(get_optional_db)
) -> Policy:
    policy = policy_service.get_policy(policy_slug, db)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return Policy(**policy)


@router.get("/me/saved-policies", response_model=list[Policy])
def list_saved_policies(
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> list[Policy]:
    saved_policies = policy_service.list_saved_policies(
        db,
        _require_user(current_user),
    )
    return [Policy(**policy) for policy in saved_policies]


@router.get("/me/applied-policies", response_model=list[Policy])
def list_applied_policies(
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> list[Policy]:
    applied_policies = policy_service.list_applied_policies(
        db,
        _require_user(current_user),
    )
    return [Policy(**policy) for policy in applied_policies]


@router.get("/me/applied-policy-links", response_model=list[AppliedPolicyLink])
def list_applied_policy_links(
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> list[AppliedPolicyLink]:
    applied_policy_links = policy_service.list_applied_policy_links(
        db,
        _require_user(current_user),
    )
    return [AppliedPolicyLink(**link) for link in applied_policy_links]


@router.post("/me/saved-policies/{policy_slug}", response_model=SavePolicyResponse)
def save_policy(
    policy_slug: str,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> SavePolicyResponse:
    saved_policy = policy_service.save_policy(
        policy_slug,
        db,
        _require_user(current_user),
    )
    if saved_policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return SavePolicyResponse(**saved_policy)


@router.delete("/me/saved-policies/{policy_slug}", response_model=SavePolicyResponse)
def remove_saved_policy(
    policy_slug: str,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> SavePolicyResponse:
    removed_policy = policy_service.remove_saved_policy(
        policy_slug,
        db,
        _require_user(current_user),
    )
    if removed_policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return SavePolicyResponse(**removed_policy)
