"""Region photo resolver tests — no external HTTP, sqlite-backed repository."""

from __future__ import annotations

import app.models  # noqa: F401
import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import PolicyPhotoAssignment, RegionPhoto
from app.repositories.region_photos import (
    get_region_photo,
    list_active_region_photos,
    upsert_region_photo,
)
from app.services.region_photos import (
    EMPTY_REGION_PHOTO_INDEX,
    build_region_photo_index,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    id_column = RegionPhoto.__table__.c.id
    original_type = id_column.type
    policy_photo_id_column = PolicyPhotoAssignment.__table__.c.id
    policy_photo_original_type = policy_photo_id_column.type
    id_column.type = Integer()
    policy_photo_id_column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as db:
            yield db
        Base.metadata.drop_all(engine)
    finally:
        id_column.type = original_type
        policy_photo_id_column.type = policy_photo_original_type


def add_photo(db: Session, **overrides: object) -> RegionPhoto:
    data: dict[str, object] = {
        "provider": "tour_api",
        "sido": "전남",
        "city": "해남",
        "hero_image_url": "https://tong.visitkorea.or.kr/cms/resource/haenam.jpg",
        "thumb_image_url": "https://tong.visitkorea.or.kr/cms/resource/haenam_t.jpg",
        "content_title": "두륜산 케이블카",
        "attribution_text": "사진: 한국관광공사",
        "storage_kind": "remote",
        "status": "active",
    }
    data.update(overrides)
    photo = RegionPhoto(**data)
    db.add(photo)
    db.commit()
    return photo


def test_upsert_region_photo_updates_existing_row(session: Session) -> None:
    first = upsert_region_photo(
        session,
        provider="tour_api",
        sido="전남",
        city="해남",
        hero_image_url="https://tong.visitkorea.or.kr/old.jpg",
    )
    second = upsert_region_photo(
        session,
        provider="tour_api",
        sido="전남",
        city="해남",
        hero_image_url="https://tong.visitkorea.or.kr/new.jpg",
    )
    session.commit()
    assert first.id == second.id
    stored = get_region_photo(session, provider="tour_api", sido="전남", city="해남")
    assert stored is not None
    assert stored.hero_image_url is not None
    assert stored.hero_image_url.endswith("new.jpg")
    assert len(list_active_region_photos(session)) == 1


def test_resolve_exact_city_hit(session: Session) -> None:
    add_photo(session)
    index = build_region_photo_index(session)
    resolved = index.resolve("전남", "해남")
    assert resolved is not None
    assert resolved.image_url.endswith("haenam.jpg")
    assert resolved.alt == "두륜산 케이블카"
    assert resolved.attribution == "사진: 한국관광공사"


def test_resolve_policy_assignment_before_region_fallback(session: Session) -> None:
    add_photo(session)
    session.add(
        PolicyPhotoAssignment(
            policy_id=42,
            provider="tour_api",
            provider_content_id="policy-specific",
            image_url="https://tong.visitkorea.or.kr/cms/resource/policy.jpg",
            thumbnail_url=None,
            alt_text="Policy-specific landmark",
            attribution_text="사진: 한국관광공사",
            relevance_score=150,
            assignment_reason="policy_keyword",
            status="active",
        )
    )
    session.commit()

    index = build_region_photo_index(session)

    assigned = index.resolve_policy(42, "전남", "해남")
    fallback = index.resolve_policy(43, "전남", "해남")

    assert assigned is not None
    assert assigned.image_url.endswith("policy.jpg")
    assert fallback is not None
    assert fallback.image_url.endswith("haenam.jpg")


def test_resolve_normalizes_city_suffix(session: Session) -> None:
    add_photo(session, city="영월", sido="강원",
              hero_image_url="https://tong.visitkorea.or.kr/yw.jpg")
    index = build_region_photo_index(session)
    resolved = index.resolve("강원", "영월군")
    assert resolved is not None
    assert resolved.image_url.endswith("yw.jpg")


def test_resolve_falls_back_to_sido_photo(session: Session) -> None:
    add_photo(session, city="", hero_image_url="https://tong.visitkorea.or.kr/jn.jpg")
    index = build_region_photo_index(session)
    resolved = index.resolve("전남", "없는도시")
    assert resolved is not None
    assert resolved.image_url.endswith("jn.jpg")


def test_resolve_missing_sido_returns_none(session: Session) -> None:
    add_photo(session)
    index = build_region_photo_index(session)
    assert index.resolve("제주", "제주") is None
    assert index.resolve(None, None) is None


def test_blocked_and_urlless_rows_are_excluded(session: Session) -> None:
    add_photo(session, city="곡성", status="blocked",
              hero_image_url="https://tong.visitkorea.or.kr/bad.jpg")
    add_photo(session, city="함평", hero_image_url=None)
    index = build_region_photo_index(session)
    assert index.resolve("전남", "곡성") is None
    assert index.resolve("전남", "함평") is None


def test_resolved_photo_to_api_is_camel_case(session: Session) -> None:
    add_photo(session)
    resolved = build_region_photo_index(session).resolve("전남", "해남")
    assert resolved is not None
    payload = resolved.to_api()
    assert set(payload) == {"imageUrl", "thumbnailUrl", "alt", "attribution"}
    assert payload["attribution"] == "사진: 한국관광공사"


def test_build_index_without_db_returns_empty_singleton() -> None:
    assert build_region_photo_index(None) is EMPTY_REGION_PHOTO_INDEX
    assert EMPTY_REGION_PHOTO_INDEX.resolve("전남", "해남") is None


def test_build_index_degrades_to_empty_when_lookup_fails() -> None:
    # 사진은 장식 — 세션 이상/테이블 미생성이 정책 응답을 깨면 안 된다.
    assert build_region_photo_index(object()) is EMPTY_REGION_PHOTO_INDEX  # type: ignore[arg-type]


def test_build_index_keeps_region_fallback_when_policy_table_is_unavailable(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import region_photos as service

    add_photo(session)
    monkeypatch.setattr(
        service,
        "list_active_policy_photos",
        lambda db: (_ for _ in ()).throw(RuntimeError("migration pending")),
    )

    resolved = build_region_photo_index(session).resolve("전남", "해남")

    assert resolved is not None
    assert resolved.image_url.endswith("haenam.jpg")
