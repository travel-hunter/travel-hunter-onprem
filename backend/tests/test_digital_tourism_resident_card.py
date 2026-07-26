from __future__ import annotations

from datetime import UTC, date, datetime

from app.services import digital_tourism_resident_card as dgtour


FETCHED_AT = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def test_participating_region_allowlist_matches_official_scope() -> None:
    assert len(dgtour.PARTICIPATING_REGIONS) == 52
    assert len(dgtour.PARTICIPATING_CITIES) == 52
    assert {"하동", "해남", "완도", "영광"}.issubset(dgtour.PARTICIPATING_CITIES)
    assert {"강진", "남해", "영암", "횡성"}.isdisjoint(dgtour.PARTICIPATING_CITIES)


def test_materialized_sources_cover_all_participating_regions_once() -> None:
    sources = dgtour.materialize_participating_region_sources(
        fetched_at=FETCHED_AT,
        today=date(2026, 7, 24),
    )

    assert len(sources) == 52
    assert len({source.city for source in sources}) == 52
    assert all(source.source_category == dgtour.SOURCE_CATEGORY for source in sources)
    assert all(source.status == "active" for source in sources)
    assert all(source.freshness_status == "fresh" for source in sources)
    assert all(source.logical_key for source in sources)


def test_canonical_policy_slug_is_region_based_and_accepts_legacy_numbered_slugs() -> None:
    assert dgtour.canonical_policy_slug_for_city("하동") == "dgtour-하동"
    assert dgtour.canonical_policy_slug_for_city("부산 동구") == "dgtour-부산동구"
    assert dgtour.canonical_policy_slug_for_city("강진") is None
    assert dgtour.city_from_policy_slug("dgtour-하동") == "하동"
    assert dgtour.city_from_policy_slug("dgtour-하동-3") == "하동"
    assert dgtour.city_from_policy_slug("travelmonth-95") == ""


def test_materialized_sources_use_visitkorea_dgtourcard_urls() -> None:
    sources = {
        source.city: source
        for source in dgtour.materialize_participating_region_sources(
            fetched_at=FETCHED_AT,
            today=date(2026, 7, 24),
        )
    }

    assert sources["하동"].detail_url == dgtour.HADONG_REGIONAL_URL
    assert sources["완도"].detail_url == dgtour.WANDO_REGIONAL_URL
    assert sources["해남"].detail_url == dgtour.HAENAM_REGIONAL_URL
    assert sources["양양"].detail_url == dgtour.data.YANGYANG_REGIONAL_URL
    assert sources["가평"].detail_url == dgtour.data.GAPYEONG_REGIONAL_URL
    assert "haenam50.kr" not in (sources["해남"].detail_url or "")
    assert all(dgtour.is_visitkorea_dgtourcard_url(source.detail_url) for source in sources.values())
    assert all("tour50.do" not in (source.detail_url or "") for source in sources.values())


def test_confirmed_regional_urls_are_explicitly_scoped() -> None:
    assert len(dgtour.REGIONAL_URLS) == 52
    assert set(dgtour.REGIONAL_URLS) == dgtour.PARTICIPATING_CITIES
    assert dgtour.REGIONAL_URLS["가평"] == dgtour.data.GAPYEONG_REGIONAL_URL
    assert dgtour.REGIONAL_URLS["합천"] == dgtour.data.HAPCHEON_REGIONAL_URL
    assert dgtour.REGIONAL_URLS["하동"] == dgtour.HADONG_REGIONAL_URL
    assert all(dgtour.is_visitkorea_dgtourcard_url(url) for url in dgtour.REGIONAL_URLS.values())
    assert all("regnMain.do?mtpcDoCd=" in url and "&signguCd=" in url for url in dgtour.REGIONAL_URLS.values())


def test_live_enrichment_never_overrides_to_half_trip_url() -> None:
    materialized = dgtour.materialize_participating_region_sources(
        fetched_at=FETCHED_AT,
        today=date(2026, 7, 24),
    )
    haenam = next(source for source in materialized if source.city == "해남")
    polluted = haenam.model_copy(update={"detail_url": "https://www.haenam50.kr/index"})

    merged = dgtour.merge_materialized_and_parsed_sources(materialized, [polluted])
    merged_haenam = next(source for source in merged if source.city == "해남")

    assert merged_haenam.detail_url == dgtour.HAENAM_REGIONAL_URL


def test_live_enrichment_rejects_half_trip_urls_and_copy() -> None:
    materialized = dgtour.materialize_participating_region_sources(
        fetched_at=FETCHED_AT,
        today=date(2026, 7, 24),
    )
    by_city = {source.city: source for source in materialized}
    polluted = [
        by_city["하동"].model_copy(
            update={
                "detail_url": "https://hadongtrip.kr/index.php",
                "raw_detail_text": "대한민국 반값여행 최대 20만원 50% 환급",
            }
        ),
        by_city["완도"].model_copy(update={"detail_url": "https://www.wandotrip.kr/index.php"}),
        by_city["해남"].model_copy(update={"detail_url": "https://www.haenam50.kr/index"}),
    ]

    merged = {source.city: source for source in dgtour.merge_materialized_and_parsed_sources(materialized, polluted)}

    assert merged["하동"].detail_url == dgtour.HADONG_REGIONAL_URL
    assert merged["완도"].detail_url == dgtour.WANDO_REGIONAL_URL
    assert merged["해남"].detail_url == dgtour.HAENAM_REGIONAL_URL
    assert "반값여행" not in merged["하동"].raw_detail_text


def test_partner_benefit_rows_are_normalized_for_payload_and_display() -> None:
    rows = [
        {
            "totCnt": 2,
            "mbrbId": "m-1",
            "mbrbBnefClCd": "VWNG",
            "mbrbBnefClCdNm": "관람",
            "mbrbNm": "평창올림픽플라자",
            "mbrbIntroWordsCn": "올림픽 레거시 전시장",
            "svcCn": "관람료 할인",
            "bnefCn": "대인 15,000원 > 8,000원<br>소인 10,000원 > 8,000원",
            "mbrbExpsrId": "coupon-1",
            "utztCnt": 466,
        },
        {
            "totCnt": 2,
            "mbrbId": "m-1",
            "mbrbBnefClCdNm": "관람",
            "mbrbNm": "중복",
            "svcCn": "중복",
        },
    ]

    benefits = dgtour.partner_benefits_from_api_rows(rows)

    assert benefits == [
        {
            "memberId": "m-1",
            "categoryCode": "VWNG",
            "categoryName": "관람",
            "name": "평창올림픽플라자",
            "intro": "올림픽 레거시 전시장",
            "summary": "관람료 할인",
            "detail": "대인 15,000원 > 8,000원 소인 10,000원 > 8,000원",
            "couponExposureId": "coupon-1",
            "usageCount": 466,
            "totalCount": 2,
        }
    ]
    assert dgtour.format_partner_benefit_for_display(benefits[0]).startswith(
        "[관람] 평창올림픽플라자: 대인 15,000원 > 8,000원"
    )


def test_apply_partner_benefit_enrichment_stores_full_list_and_summary() -> None:
    source = next(
        item
        for item in dgtour.materialize_participating_region_sources(
            fetched_at=FETCHED_AT,
            today=date(2026, 7, 24),
        )
        if item.city == "하동"
    )
    benefits = [
        {
            "memberId": "h-1",
            "categoryName": "식음료",
            "name": "하동 카페",
            "intro": "카페",
            "summary": "음료 할인",
            "detail": "음료 1,000원 할인",
        },
        {
            "memberId": "h-2",
            "categoryName": "숙박",
            "name": "하동 숙소",
            "intro": "숙소",
            "summary": "숙박 할인",
            "detail": "숙박비 10% 할인",
        },
    ]

    enriched = dgtour.apply_partner_benefit_enrichment(source, benefits)

    assert enriched.raw_payload["collectionMode"] == "allowlist-materialized+partner-benefit-api"
    assert enriched.raw_payload["partnerBenefits"] == benefits
    assert enriched.raw_payload["partnerBenefitSummary"] == {
        "totalCount": 2,
        "categoryCounts": {"숙박": 1, "식음료": 1},
        "displayLimit": dgtour.MAX_DISPLAY_PARTNER_BENEFITS,
    }
    assert "하동 제휴처 2곳" in enriched.raw_detail_text
    assert "[식음료] 하동 카페" in enriched.raw_detail_text
