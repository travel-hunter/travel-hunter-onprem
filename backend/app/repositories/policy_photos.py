from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PolicyPhotoAssignment


def list_active_policy_photos(db: Session) -> list[PolicyPhotoAssignment]:
    stmt = (
        select(PolicyPhotoAssignment)
        .where(PolicyPhotoAssignment.status == "active")
        .where(PolicyPhotoAssignment.image_url.is_not(None))
    )
    return list(db.scalars(stmt))


def get_policy_photo(
    db: Session, *, policy_id: int
) -> PolicyPhotoAssignment | None:
    return db.scalars(
        select(PolicyPhotoAssignment).where(
            PolicyPhotoAssignment.policy_id == policy_id
        )
    ).first()


def upsert_policy_photo(
    db: Session, *, policy_id: int, **fields: object
) -> PolicyPhotoAssignment:
    photo = get_policy_photo(db, policy_id=policy_id)
    if photo is None:
        photo = PolicyPhotoAssignment(policy_id=policy_id)
        db.add(photo)
    for name, value in fields.items():
        setattr(photo, name, value)
    db.flush()
    return photo
