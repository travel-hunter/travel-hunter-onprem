from datetime import date, datetime, timedelta

import app.models  # noqa: F401
import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.data.travel_areas import get_travel_area, list_travel_areas, make_policy_region_area_id, resolve_municipality_sido
from app.db.base import Base
from app.models import ExternalSourceRecord, Policy
from app.repositories.external_sources import upsert_external_source_records
from app.schemas.external_sources import ExternalBenefitSource
from app.services.travel_areas import recommend_travel_areas


FETCHED_AT = datetime(2026, 5, 21, 9, 0, 0)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    external_id_column = ExternalSourceRecord.__table__.c.id
    policy_id_column = Policy.__table__.c.id
    original_external_id_type = external_id_column.type
    original_policy_id_type = policy_id_column.type
    external_id_column.type = Integer()
    policy_id_column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        external_id_column.type = original_external_id_type
        policy_id_column.type = original_policy_id_type


def make_source(
    canonical_key: str,
    *,
    region: str,
    title: str,
    source_category: str = "local_half_trip",
    city: str | None = None,
    amount: int | None = None,
    end_date: date | None = None,
    tags: list[str] | None = None,
    is_nationwide: bool = False,
    status: str = "active",
    freshness_status: str = "fresh",
    raw_payload: dict[str, object] | None = None,
) -> ExternalBenefitSource:
    return ExternalBenefitSource(
        source_name="대한민국 반값여행",
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        source_category=source_category,
        external_id=canonical_key,
        canonical_key=canonical_key,
        detail_url=None,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title=title,
        organizer_text=f"{region} 관광",
        organizers=[f"{region} 관광"],
        region=region,
        city=city,
        is_nationwide=is_nationwide,
        status_text="active",
        status=status,
        start_date=date(2026, 5, 1),
        end_date=end_date,
        benefit_text=title,
        benefit_value_text=f"최대 {amount}원 지원" if amount else None,
        extracted_amount_krw=amount,
        extracted_discount_percent=None,
        benefit_value_type="amount" if amount else "unknown",
        tags=tags or [],
        contact_text=None,
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=95,
        raw_list_text=title,
        raw_detail_text=title,
        raw_payload=raw_payload or {"periodText": "2026-05-01 ~ 2026-05-31"},
        last_fetched_at=FETCHED_AT,
        last_verified_at=FETCHED_AT,
        freshness_status=freshness_status,
    )


def test_catalog_contains_representative_nationwide_areas() -> None:
    areas = list_travel_areas()
    ids = {area.id for area in areas}
    sidos = {area.sido for area in areas}
    expected_sidos = {
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
    }

    assert "jeju-all" in ids
    assert "busan-all" in ids
    assert "daegu-all" in ids
    assert "sejong-all" in ids
    assert "gangwon-sokcho-goseong-yangyang" in ids
    assert "jeonnam-yeosu-suncheon" in ids
    assert "gyeongnam-tongyeong-geoje-goseong" in ids
    assert "chungbuk-danyang-jecheon" in ids
    assert expected_sidos <= sidos
    assert len(areas) >= 36


def test_get_travel_area_resolves_id_and_display_fields() -> None:
    area = get_travel_area("gangwon-sokcho-goseong-yangyang")

    assert area is not None
    assert area.name == "속초·고성·양양"
    assert area.sido == "강원"
    assert "고성" in area.included_cities
    assert "설악산" in area.aliases


def test_sido_filter_returns_only_that_sido(db: Session) -> None:
    result = recommend_travel_areas(db, sido="전남", today=date(2026, 5, 26))

    assert result.mode == "sido"
    assert result.sido == "전남"
    assert result.emptyReason is None
    assert result.items
    assert all(item.sido == "전남" for item in result.items)


def test_unsupported_sido_returns_empty_reason(db: Session) -> None:
    result = recommend_travel_areas(db, sido="없는지역", today=date(2026, 5, 26))

    assert result.items == []
    assert result.emptyReason == "unsupported_sido"


def test_search_sokcho_returns_gangwon_area(db: Session) -> None:
    result = recommend_travel_areas(db, query="속초", today=date(2026, 5, 26))

    assert result.mode == "search"
    assert result.items[0].travelAreaId == "gangwon-sokcho-goseong-yangyang"


def test_search_policy_only_municipality_returns_policy_region_area(db: Session) -> None:
    db.add(
        Policy(
            slug="dgtour-영광-8",
            title="영광 디지털관광주민증 혜택",
            region="전남",
            status="active",
        )
    )
    db.commit()

    result = recommend_travel_areas(db, query="영광", today=date(2026, 5, 26))

    assert result.mode == "search"
    assert result.emptyReason is None
    assert result.items[0].travelAreaId == make_policy_region_area_id("전남", "영광")
    assert result.items[0].travelAreaName == "영광"
    assert result.items[0].sido == "전남"
    assert result.items[0].localPolicyCount == 1
    assert get_travel_area(result.items[0].travelAreaId).name == "영광"


def test_search_known_municipality_without_policy_rows_returns_static_policy_region_area(db: Session) -> None:
    result = recommend_travel_areas(db, query="합천", today=date(2026, 5, 26))

    assert result.mode == "search"
    assert result.emptyReason is None
    assert result.items[0].travelAreaId == make_policy_region_area_id("경남", "합천")
    assert result.items[0].travelAreaName == "합천"
    assert result.items[0].sido == "경남"
    assert result.items[0].localPolicyCount == 0
    assert get_travel_area(result.items[0].travelAreaId).sido == "경남"


def test_search_known_municipality_fallback_respects_sido_filter(db: Session) -> None:
    result = recommend_travel_areas(db, query="강진", sido="전남", today=date(2026, 5, 26))

    assert result.emptyReason is None
    assert result.items[0].travelAreaId == make_policy_region_area_id("전남", "강진")

    mismatched = recommend_travel_areas(db, query="강진", sido="경남", today=date(2026, 5, 26))

    assert mismatched.items == []
    assert mismatched.emptyReason == "no_match"


def test_search_policy_alias_district_uses_sido_filter_for_fallback(db: Session) -> None:
    result = recommend_travel_areas(db, query="서구", sido="부산", today=date(2026, 5, 26))

    assert result.emptyReason is None
    assert result.items[0].travelAreaId == make_policy_region_area_id("부산", "서구")
    assert result.items[0].travelAreaName == "서구"
    assert result.items[0].sido == "부산"


def test_stay_discount_alias_municipality_sidos_are_resolvable_with_hint() -> None:
    expected_groups = {
        "강원": ("고성군", "삼척시", "양구군", "양양군", "영월군", "정선군", "철원군", "태백시", "평창군", "홍천군", "화천군", "횡성군"),
        "경남": ("거창군", "고성군", "남해군", "밀양시", "산청군", "의령군", "창녕군", "하동군", "함안군", "함양군", "합천군"),
        "경북": ("고령군", "문경시", "봉화군", "상주시", "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "울릉군", "울진군", "의성군", "청도군", "청송군"),
        "대구": ("군위군", "남구", "서구"),
        "부산": ("동구", "서구", "영도구"),
        "전남": ("강진군", "고흥군", "곡성군", "구례군", "담양군", "보성군", "신안군", "영광군", "영암군", "완도군", "장성군", "장흥군", "진도군", "함평군", "해남군", "화순군"),
        "전북": ("고창군", "김제시", "남원시", "무주군", "부안군", "순창군", "임실군", "장수군", "정읍시", "진안군"),
        "충남": ("공주시", "금산군", "논산시", "보령시", "부여군", "서천군", "예산군", "청양군", "태안군"),
        "충북": ("괴산군", "단양군", "보은군", "영동군", "옥천군", "제천시"),
    }

    unresolved = [
        (sido, city)
        for sido, cities in expected_groups.items()
        for city in cities
        if resolve_municipality_sido(city, sido=sido) != sido
    ]

    assert unresolved == []


def test_search_duplicate_goseong_returns_distinct_sidos(db: Session) -> None:
    result = recommend_travel_areas(db, query="고성", today=date(2026, 5, 26))
    pairs = {(item.sido, item.travelAreaId) for item in result.items}

    assert ("강원", "gangwon-sokcho-goseong-yangyang") in pairs
    assert ("경남", "gyeongnam-tongyeong-geoje-goseong") in pairs


def test_query_with_sido_constrains_duplicate_search(db: Session) -> None:
    result = recommend_travel_areas(db, query="고성", sido="강원", today=date(2026, 5, 26))

    assert result.mode == "search"
    assert [item.travelAreaId for item in result.items] == ["gangwon-sokcho-goseong-yangyang"]


def test_nationwide_falls_back_to_catalog_priority_when_no_policy_data(db: Session) -> None:
    result = recommend_travel_areas(db, mode="nationwide", limit=3, today=date(2026, 5, 26))

    assert [item.travelAreaId for item in result.items] == [
        "jeju-all",
        "busan-all",
        "gangwon-sokcho-goseong-yangyang",
    ]


def test_city_policy_boosts_matching_travel_area(db: Session) -> None:
    today = date(2026, 5, 26)
    upsert_external_source_records(
        db,
        [
            make_source("sokcho-city", region="강원", city="속초", title="속초 숙박 할인", amount=50000),
            make_source("gangwon-wide", region="강원", title="강원 전체 관광 할인", amount=30000),
        ],
    )

    result = recommend_travel_areas(db, sido="강원", style="바다", today=today)

    assert result.items[0].travelAreaId == "gangwon-sokcho-goseong-yangyang"
    assert result.items[0].localPolicyCount >= 2
    assert result.items[0].estimatedValueKrw == 80000


def test_ending_soon_and_nationwide_counts_are_reflected(db: Session) -> None:
    today = date(2026, 5, 26)
    upsert_external_source_records(
        db,
        [
            make_source("nationwide", region="전국", title="전국 교통 할인", amount=10000, is_nationwide=True),
            make_source("yeosu", region="전남", city="여수", title="여수 숙박 지원", amount=70000, end_date=today + timedelta(days=3)),
        ],
    )

    result = recommend_travel_areas(db, query="여수", today=today)

    assert result.items[0].travelAreaId == "jeonnam-yeosu-suncheon"
    assert result.items[0].policyCount == 2
    assert result.items[0].localPolicyCount == 1
    assert result.items[0].nationwidePolicyCount == 1
    assert result.items[0].endingSoonCount == 1
    assert result.items[0].score > 0


def test_stay_discount_alias_areas_match_travel_area_cities(db: Session) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(
                "stay-discount",
                source_category="stay_discount",
                region="비수도권 인구감소지역",
                title="2026 대한민국 숙박세일 페스타 숙박 할인",
                amount=70000,
                tags=["숙박"],
                raw_payload={
                    "eligibleAreas": [
                        {"sido": "강원", "cities": ["고성군", "삼척시"]},
                        {"sido": "경남", "cities": ["고성군"]},
                    ],
                    "eligibleAreaCount": 3,
                },
            ),
        ],
    )

    gangwon = recommend_travel_areas(db, query="고성", sido="강원", today=date(2026, 6, 16))
    gyeongnam = recommend_travel_areas(db, query="고성", sido="경남", today=date(2026, 6, 16))

    assert gangwon.items[0].travelAreaId == "gangwon-sokcho-goseong-yangyang"
    assert gangwon.items[0].localPolicyCount == 1
    assert gangwon.items[0].estimatedValueKrw == 70000
    assert gyeongnam.items[0].travelAreaId == "gyeongnam-tongyeong-geoje-goseong"
    assert gyeongnam.items[0].localPolicyCount == 1


def test_travel_areas_hide_stay_canonical_when_alias_payload_missing(db: Session) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(
                "stay-discount",
                source_category="stay_discount",
                region="비수도권 인구감소지역",
                title="2026 대한민국 숙박세일 페스타 숙박 할인",
                amount=70000,
                tags=["숙박"],
                raw_payload={},
            ),
        ],
    )

    result = recommend_travel_areas(db, query="고성", sido="강원", today=date(2026, 6, 16))

    assert result.items[0].travelAreaId == "gangwon-sokcho-goseong-yangyang"
    assert result.items[0].localPolicyCount == 0
    assert result.items[0].estimatedValueKrw == 0
