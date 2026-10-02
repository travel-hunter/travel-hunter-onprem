"""Region photo resolver tests — no external HTTP, sqlite-backed photo review tables (0047)."""

from __future__ import annotations

import itertools

import app.models  # noqa: F401
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import PhotoReviewCandidate, PhotoReviewTarget
from app.services.region_photos import (
    EMPTY_REGION_PHOTO_INDEX,
    build_region_photo_index,
)

_ids = itertools.count(1)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db


def add_photo(
    db: Session,
    *,
    sido: str = "전남",
    city: str = "해남",
    policy_id: int | None = None,
    status: str = "approved",
    stored_path: str | None = "photos/ab/haenam.jpg",
    title: str = "두륜산 케이블카",
) -> PhotoReviewCandidate:
    """확정한 대상 하나와 그 대상이 고른 후보. policy_id 가 있으면 정책 대상이다."""

    target = PhotoReviewTarget(
        id=next(_ids),
        target_key=f"policy:{policy_id}" if policy_id else f"region:{sido}|{city}",
        target_type="policy" if policy_id else "region",
        sido=sido,
        city=city,
        policy_id=policy_id,
        status=status,
    )
    candidate = PhotoReviewCandidate(
        id=next(_ids),
        target_id=target.id,
        provider="tour_api",
        title=title,
        image_url="https://tong.visitkorea.or.kr/cms/resource/original.jpg",
        copyright_type="Type1",
        source="collect",
        stored_path=stored_path,
    )
    target.approved_candidate_id = candidate.id if status == "approved" else None
    db.add_all([target, candidate])
    db.commit()
    return candidate


def test_resolve_exact_city_hit_serves_the_stored_file(session: Session) -> None:
    add_photo(session)
    resolved = build_region_photo_index(session).resolve("전남", "해남")
    assert resolved is not None
    # 받아 둔 파일만 내보낸다 - 관광공사 주소를 그대로 걸지 않는다
    assert resolved.image_url == "/api/media/photos/ab/haenam.jpg"
    assert resolved.thumbnail_url is None
    assert resolved.alt == "두륜산 케이블카"
    assert resolved.attribution == "사진: 한국관광공사 · 공공누리 제1유형"


def test_resolve_policy_photo_before_region_fallback(session: Session) -> None:
    add_photo(session)
    add_photo(session, policy_id=42, city="해남", stored_path="photos/cd/policy.jpg")

    index = build_region_photo_index(session)

    assert index.resolve_policy(42, "전남", "해남").image_url.endswith("policy.jpg")
    assert index.resolve_policy(43, "전남", "해남").image_url.endswith("haenam.jpg")


def test_resolve_normalizes_city_suffix(session: Session) -> None:
    add_photo(session, sido="강원", city="영월", stored_path="photos/ef/yw.jpg")
    resolved = build_region_photo_index(session).resolve("강원", "영월군")
    assert resolved is not None
    assert resolved.image_url.endswith("yw.jpg")


def test_resolve_uses_sido_photo_only_without_city(session: Session) -> None:
    add_photo(session, city="", stored_path="photos/12/jn.jpg")
    index = build_region_photo_index(session)
    # 시군이 없는 정책(도 단위)은 도 대표 사진
    resolved = index.resolve("전남", None)
    assert resolved is not None
    assert resolved.image_url.endswith("jn.jpg")
    # 시군이 있는데 그 시군 사진이 없으면 비운다 - 도 대표 사진을 여러 시군이 나눠 쓰지 않는다(2026-10-01)
    assert index.resolve("전남", "없는도시") is None


def test_city_named_like_its_sido_is_the_sido_level_policy(session: Session) -> None:
    # 세종처럼 시군 칸에 도 이름이 들어간 정책은 도 전체 줄을 쓴다(사진 검토의 묶기 규칙과 같다)
    add_photo(session, sido="세종", city="", stored_path="photos/77/sejong.jpg")
    assert build_region_photo_index(session).resolve("세종", "세종").image_url.endswith("sejong.jpg")


def test_resolve_missing_sido_returns_none(session: Session) -> None:
    add_photo(session)
    index = build_region_photo_index(session)
    assert index.resolve("제주", "제주") is None
    assert index.resolve(None, None) is None


def test_undecided_and_unstored_photos_are_excluded(session: Session) -> None:
    add_photo(session, city="곡성", status="pending")
    add_photo(session, city="구례", status="none")
    add_photo(session, city="함평", stored_path=None)
    index = build_region_photo_index(session)
    assert index.resolve("전남", "곡성") is None
    assert index.resolve("전남", "구례") is None
    assert index.resolve("전남", "함평") is None


def test_resolved_photo_to_api_is_camel_case(session: Session) -> None:
    add_photo(session)
    resolved = build_region_photo_index(session).resolve("전남", "해남")
    assert resolved is not None
    payload = resolved.to_api()
    assert set(payload) == {"imageUrl", "thumbnailUrl", "alt", "attribution"}
    assert payload["imageUrl"] == "/api/media/photos/ab/haenam.jpg"


def test_build_index_without_db_returns_empty_singleton() -> None:
    assert build_region_photo_index(None) is EMPTY_REGION_PHOTO_INDEX
    assert EMPTY_REGION_PHOTO_INDEX.resolve("전남", "해남") is None


def test_build_index_degrades_to_empty_when_lookup_fails() -> None:
    # 사진은 장식 — 세션 이상/테이블 미생성이 정책 응답을 깨면 안 된다.
    assert build_region_photo_index(object()) is EMPTY_REGION_PHOTO_INDEX  # type: ignore[arg-type]
