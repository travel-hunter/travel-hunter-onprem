"""사진 검토 표(0047) 조회 · 쓰기. 앱이 쓰는 사진(확정한 대상 → 고른 후보)도 여기서 읽는다."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PhotoReviewCandidate, PhotoReviewTarget


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


def count_collected(db: Session) -> dict[int, int]:
    """대상마다 수집 후보 수('이름으로 찾기' 제외) - 후보 채우기가 6장까지 채우는 기준."""

    rows = db.execute(
        select(PhotoReviewCandidate.target_id, func.count())
        .where(PhotoReviewCandidate.source != "search")
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


def list_published(db: Session) -> list[tuple[PhotoReviewTarget, PhotoReviewCandidate]]:
    """앱에 나가는 사진: 확정한 대상과 그 대상이 고른 후보(원본을 받아 둔 것만)."""

    rows = db.execute(
        select(PhotoReviewTarget, PhotoReviewCandidate)
        .join(PhotoReviewCandidate, PhotoReviewCandidate.id == PhotoReviewTarget.approved_candidate_id)
        .where(PhotoReviewTarget.status == "approved", PhotoReviewCandidate.stored_path.is_not(None))
    ).all()
    return [(target, candidate) for target, candidate in rows]
