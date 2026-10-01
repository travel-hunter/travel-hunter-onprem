"""사진 검토 표(0047) 조회 · 쓰기. 앱에 나가는 사진 줄(region_photos · policy_photos)을 내리는 것도 여기서."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import PhotoReviewCandidate, PhotoReviewTarget, PolicyPhotoAssignment, RegionPhoto


def list_all_targets(db: Session) -> list[PhotoReviewTarget]:
    return list(db.scalars(select(PhotoReviewTarget).order_by(PhotoReviewTarget.id)))


def count_candidates(db: Session, target_ids: list[int]) -> dict[int, int]:
    if not target_ids:
        return {}
    rows = db.execute(
        select(PhotoReviewCandidate.target_id, func.count())
        .where(PhotoReviewCandidate.target_id.in_(target_ids))
        .group_by(PhotoReviewCandidate.target_id)
    ).all()
    return {target_id: count for target_id, count in rows}


def get_candidates(db: Session, candidate_ids: list[int]) -> dict[int, PhotoReviewCandidate]:
    if not candidate_ids:
        return {}
    rows = db.scalars(select(PhotoReviewCandidate).where(PhotoReviewCandidate.id.in_(candidate_ids)))
    return {row.id: row for row in rows}


def get_target(db: Session, target_id: int, *, lock: bool = False) -> PhotoReviewTarget | None:
    stmt = select(PhotoReviewTarget).where(PhotoReviewTarget.id == target_id)
    if lock and db.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_target_by_key(db: Session, target_key: str) -> PhotoReviewTarget | None:
    return db.scalars(select(PhotoReviewTarget).where(PhotoReviewTarget.target_key == target_key)).first()


def add_target(db: Session, **fields: object) -> PhotoReviewTarget:
    target = PhotoReviewTarget(**fields)
    db.add(target)
    db.flush()
    return target


def add_candidate(db: Session, target: PhotoReviewTarget, **fields: object) -> PhotoReviewCandidate:
    candidate = PhotoReviewCandidate(**fields)
    target.candidates.append(candidate)
    db.flush()
    return candidate


def all_candidate_image_urls(db: Session) -> set[str]:
    return set(db.scalars(select(PhotoReviewCandidate.image_url)))


def hide_region_photos(db: Session, *, sido: str, city: str) -> None:
    db.execute(
        update(RegionPhoto)
        .where(RegionPhoto.sido == sido, RegionPhoto.city == city, RegionPhoto.status == "active")
        .values(status="hidden")
    )


def hide_policy_photo(db: Session, *, policy_id: int) -> None:
    db.execute(
        update(PolicyPhotoAssignment)
        .where(PolicyPhotoAssignment.policy_id == policy_id, PolicyPhotoAssignment.status == "active")
        .values(status="hidden")
    )
