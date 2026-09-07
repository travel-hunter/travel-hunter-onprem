"""Policy photo DTO regression tests.

Step 1: schema gate — PolicyPhoto shape and Policy.photo default.
Later steps extend this module with resolver wiring and route payload tests.
"""

import pytest
from pydantic import ValidationError

import app.models  # noqa: F401
from app.db.base import Base
from app.schemas.policy import Policy, PolicyPhoto


def make_policy_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "fixture-policy",
        "slug": "fixture-policy",
        "label": "FI",
        "tag": "지역할인",
        "title": "Local Vacation Support",
        "org": "Travel Hunter",
        "region": "전남",
        "deadline": "2026-10-31",
        "amount": "300,000원",
        "summary": "Support for domestic travel expenses.",
        "match": 90,
        "category": "지역할인",
        "requirements": [],
        "documents": [],
    }
    payload.update(overrides)
    return payload


def test_policy_photo_requires_attribution() -> None:
    with pytest.raises(ValidationError):
        PolicyPhoto(
            imageUrl="https://tong.visitkorea.or.kr/cms/resource/1.jpg",
            alt="해남 두륜산",
        )


def test_policy_photo_accepts_full_shape() -> None:
    photo = PolicyPhoto(
        imageUrl="https://tong.visitkorea.or.kr/cms/resource/1.jpg",
        thumbnailUrl="https://tong.visitkorea.or.kr/cms/resource/1_thumb.jpg",
        alt="해남 두륜산",
        attribution="사진: 한국관광공사",
    )
    assert photo.imageUrl.endswith("1.jpg")
    assert photo.attribution == "사진: 한국관광공사"


def test_policy_photo_thumbnail_defaults_to_none() -> None:
    photo = PolicyPhoto(
        imageUrl="https://tong.visitkorea.or.kr/cms/resource/1.jpg",
        alt="해남 두륜산",
        attribution="사진: 한국관광공사",
    )
    assert photo.thumbnailUrl is None


def test_policy_schema_photo_defaults_to_none() -> None:
    policy = Policy(**make_policy_payload())
    assert policy.photo is None


def test_policy_schema_accepts_photo_payload() -> None:
    policy = Policy(
        **make_policy_payload(
            photo={
                "imageUrl": "https://tong.visitkorea.or.kr/cms/resource/1.jpg",
                "alt": "해남 두륜산",
                "attribution": "사진: 한국관광공사",
            }
        )
    )
    assert policy.photo is not None
    assert policy.photo.attribution == "사진: 한국관광공사"


def make_external_record(**overrides: object):
    from datetime import datetime

    from app.models import ExternalSourceRecord

    data: dict[str, object] = {
        "id": 4101,
        "source_name": "여행가는 달",
        "source_type": "official_campaign",
        "source_url": "https://example.com/source",
        "source_category": "regional_benefit",
        "external_id": "photo-city-1",
        "canonical_key": "photo-city-1",
        "detail_url": "https://example.com/detail",
        "collected_page_url": "https://example.com/detail",
        "title": "해남 관광 할인",
        "organizer_text": "전라남도, 해남군",
        "organizers": ["전라남도", "해남군"],
        "region": "전남",
        "city": "해남군",
        "is_nationwide": False,
        "status": "active",
        "benefit_text": "공식 혜택 원문",
        "benefit_value_text": None,
        "benefit_value_type": "text",
        "tags": [],
        "contact_text": None,
        "inferred_travel_styles": [],
        "confidence": 90,
        "field_completeness": 90,
        "raw_list_text": "해남 관광 할인",
        "raw_detail_text": "상세",
        "raw_payload": {},
        "last_fetched_at": datetime(2026, 9, 1, 9, 0, 0),
        "freshness_status": "fresh",
    }
    data.update(overrides)
    return ExternalSourceRecord(**data)


def test_assign_from_external_record_copies_city() -> None:
    from app.models import Policy as PolicyModel
    from app.services.policy_normalization import _assign_policy_from_external_record

    policy = PolicyModel(region="전국", status="active")
    _assign_policy_from_external_record(policy, make_external_record())
    assert policy.city == "해남군"


def test_assign_stay_discount_alias_clears_city() -> None:
    from app.models import Policy as PolicyModel
    from app.services import stay_discount_aliases
    from app.services.policy_normalization import _assign_stay_discount_area_policy

    record = make_external_record(
        source_name="대한민국 숙박세일 페스타",
        source_category="stay_discount",
        region="전국",
        city=None,
    )
    policy = PolicyModel(region="전국", status="active", city="이전값")
    alias_area = stay_discount_aliases.StayDiscountAliasArea(
        sido="경북", city="문경", slug="stay-discount-경북-문경"
    )
    _assign_stay_discount_area_policy(policy, record, alias_area)
    # alias 정책은 시도 단위 노출이므로 이전 재사용 행의 city가 남으면 안 된다.
    assert policy.city is None
    assert policy.region == "경북"


def make_photo_index():
    from app.services.region_photos import RegionPhotoIndex, ResolvedRegionPhoto

    def photo(url: str, alt: str) -> ResolvedRegionPhoto:
        return ResolvedRegionPhoto(
            image_url=url,
            thumbnail_url=None,
            alt=alt,
            attribution="사진: 한국관광공사",
        )

    return RegionPhotoIndex(
        {
            ("전남", "해남"): photo("https://tong.visitkorea.or.kr/haenam.jpg", "두륜산"),
            ("전남", ""): photo("https://tong.visitkorea.or.kr/jeonnam.jpg", "전남 대표"),
            ("경북", ""): photo("https://tong.visitkorea.or.kr/gb.jpg", "경북 대표"),
        }
    )


def make_policy_model(**overrides: object):
    from app.models import Policy as PolicyModel

    data: dict[str, object] = {
        "id": 11,
        "slug": "photo-fixture-policy",
        "title": "해남 여행 지원",
        "organization": "전라남도",
        "policy_type": "지역할인",
        "region": "전남",
        "city": "해남",
        "status": "active",
    }
    data.update(overrides)
    return PolicyModel(**data)


def test_policy_to_api_attaches_resolved_photo() -> None:
    from app.services import policies as policy_service

    payload = policy_service.policy_to_api(make_policy_model(), photos=make_photo_index())
    photo = payload["photo"]
    assert isinstance(photo, dict)
    assert photo["imageUrl"].endswith("haenam.jpg")
    assert photo["attribution"] == "사진: 한국관광공사"


def test_policy_to_api_without_index_omits_photo_key() -> None:
    from app.services import policies as policy_service

    payload = policy_service.policy_to_api(make_policy_model())
    assert "photo" not in payload


def test_policy_to_api_photo_miss_omits_photo_key() -> None:
    from app.services import policies as policy_service

    payload = policy_service.policy_to_api(
        make_policy_model(region="제주", city=None), photos=make_photo_index()
    )
    assert "photo" not in payload


def test_external_record_payload_attaches_photo() -> None:
    from app.services import policies as policy_service

    payload = policy_service.external_source_record_to_policy_api(
        make_external_record(), photos=make_photo_index()
    )
    photo = payload["photo"]
    assert isinstance(photo, dict)
    # record.city는 "해남군" — 접미사 정규화를 거쳐 "해남" 사진에 닿아야 한다.
    assert photo["imageUrl"].endswith("haenam.jpg")


def test_stay_discount_alias_detail_uses_alias_region_photo() -> None:
    from app.services import policies as policy_service
    from app.services import stay_discount_aliases

    canonical = make_policy_model(
        slug="stay-canonical",
        title="대한민국 숙박세일 페스타",
        source_category=stay_discount_aliases.SOURCE_CATEGORY,
    )
    alias_area = stay_discount_aliases.StayDiscountAliasArea(
        sido="경북", city="문경", slug="stay-discount-경북-문경"
    )
    payload = policy_service._policy_detail_with_alias(
        canonical, alias_area, photos=make_photo_index()
    )
    photo = payload["photo"]
    assert isinstance(photo, dict)
    # canonical(전남/해남) 사진이 아니라 alias sido(경북) 사진이어야 한다.
    assert photo["imageUrl"].endswith("gb.jpg")


def test_stay_discount_alias_detail_pops_photo_when_alias_region_has_none() -> None:
    from app.services import policies as policy_service
    from app.services import stay_discount_aliases
    from app.services.region_photos import RegionPhotoIndex, ResolvedRegionPhoto

    index = RegionPhotoIndex(
        {
            ("전남", "해남"): ResolvedRegionPhoto(
                image_url="https://tong.visitkorea.or.kr/haenam.jpg",
                thumbnail_url=None,
                alt="두륜산",
                attribution="사진: 한국관광공사",
            )
        }
    )
    canonical = make_policy_model(slug="stay-canonical-2")
    alias_area = stay_discount_aliases.StayDiscountAliasArea(
        sido="제주", city="제주", slug="stay-discount-제주-제주"
    )
    payload = policy_service._policy_detail_with_alias(
        canonical, alias_area, photos=index
    )
    # 낡은 canonical 사진이 남아 있으면 안 된다.
    assert "photo" not in payload


def test_list_policies_builds_photo_index_once(monkeypatch) -> None:
    from app.services import policies as policy_service

    fake_db = object()
    build_calls: list[object] = []
    index = make_photo_index()

    def fake_build(db: object):
        build_calls.append(db)
        return index

    monkeypatch.setattr(policy_service, "build_region_photo_index", fake_build)
    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_policies",
        lambda db: [make_policy_model(), make_policy_model(id=12, slug="p2")],
    )
    payloads = policy_service.list_policies(fake_db)
    assert build_calls == [fake_db]
    assert all("photo" in payload for payload in payloads)


def test_policies_table_registers_city_column() -> None:
    policies = Base.metadata.tables["policies"]
    assert "city" in policies.c
    assert policies.c["city"].nullable is True


def test_region_photos_table_is_registered() -> None:
    assert "region_photos" in Base.metadata.tables
    region_photos = Base.metadata.tables["region_photos"]
    expected_columns = {
        "id",
        "provider",
        "sido",
        "city",
        "provider_content_id",
        "content_title",
        "hero_image_url",
        "thumb_image_url",
        "provider_image_url",
        "storage_kind",
        "attribution_text",
        "status",
        "fetched_at",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(set(region_photos.c.keys()))
    # city는 NOT NULL '' sentinel — NULL이면 UNIQUE(provider, sido, city)가 무력화된다.
    assert region_photos.c["city"].nullable is False


def test_region_photos_unique_constraint_covers_provider_sido_city() -> None:
    from sqlalchemy import UniqueConstraint

    region_photos = Base.metadata.tables["region_photos"]
    unique_column_sets = [
        tuple(column.name for column in constraint.columns)
        for constraint in region_photos.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert ("provider", "sido", "city") in unique_column_sets
