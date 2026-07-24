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
