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
        "🎟️ 평창올림픽플라자: 관람료 할인\n올림픽 레거시 전시장"
    )


def test_partner_benefit_category_highlights_pick_popular_representatives_in_display_order() -> None:
    benefits = [
        {
            "memberId": "stay-1",
            "categoryCode": "STAYNG",
            "categoryName": "숙박",
            "name": "합천휴테마파크",
            "intro": "합천호와 인접한 캠핑장",
            "summary": "평일 이용료 10% 할인",
            "usageCount": 19,
            "totalCount": 10,
        },
        {
            "memberId": "food-1",
            "categoryCode": "FDRK",
            "categoryName": "식음료",
            "name": "로우풀",
            "intro": "호수뷰와 마운틴뷰가 조화로운 대형카페",
            "summary": "음료 구매시 아메리카노 리필 1회",
            "usageCount": 200,
            "totalCount": 3,
        },
        {
            "memberId": "food-2",
            "categoryCode": "FDRK",
            "categoryName": "식음료",
            "name": "대식한우명가",
            "intro": "합천소고기 맛집",
            "summary": "음료수 1병 제공",
            "usageCount": 48,
            "totalCount": 3,
        },
        {
            "memberId": "food-3",
            "categoryCode": "FDRK",
            "categoryName": "식음료",
            "name": "3.3국밥",
            "intro": "합천돼지국밥",
            "summary": "음료수 1병 제공",
            "usageCount": 27,
            "totalCount": 3,
        },
        {
            "memberId": "view-1",
            "categoryCode": "VWNG",
            "categoryName": "관람",
            "name": "합천영상테마파크",
            "intro": "시대물 오픈세트장",
            "summary": "입장료 1,000원 할인",
            "usageCount": 1986,
            "totalCount": 1,
        },
    ]

    highlights = dgtour.partner_benefit_category_highlights(benefits)

    assert [item["categoryName"] for item in highlights] == ["식음료", "숙박", "관람"]
    assert highlights[0]["representative"]["name"] == "로우풀"
    assert highlights[0]["remainingCount"] == 2
    assert highlights[1]["representative"]["name"] == "합천휴테마파크"
    assert highlights[1]["remainingCount"] == 0
    assert dgtour.format_partner_benefit_highlight_for_display(highlights[0]) == (
        "🍽️ 로우풀: 음료 구매시 아메리카노 리필 1회\n호수뷰와 마운틴뷰가 조화로운 대형카페"
    )
    assert dgtour.format_partner_benefit_highlight_for_display(highlights[2]) == (
        "🎟️ 합천영상테마파크: 입장료 1,000원 할인\n시대물 오픈세트장"
    )


def test_partner_benefit_highlight_display_omits_middle_dot_and_count_suffix() -> None:
    highlight = {
        "categoryCode": "FDRK",
        "categoryName": "식음료",
        "totalCount": 3,
        "remainingCount": 2,
        "representative": {
            "memberId": "cdb03f3e-180d-11ef-b16c-0242ac130002",
            "categoryCode": "FDRK",
            "categoryName": "식음료",
            "name": "로우풀",
            "intro": "호수뷰와 마운틴뷰가 조화로운 대형카페",
            "summary": "음료 구매시 아메리카노 리필 1회",
        },
    }

    text = dgtour.format_partner_benefit_highlight_for_display(highlight)

    assert text == "🍽️ 로우풀: 음료 구매시 아메리카노 리필 1회\n호수뷰와 마운틴뷰가 조화로운 대형카페"
    assert "·" not in text
    assert "외 2개 혜택" not in text


def test_official_member_benefit_url_uses_member_id() -> None:
    benefit = {"memberId": "cdb03f3e-180d-11ef-b16c-0242ac130002"}

    assert dgtour.official_member_benefit_url(benefit) == (
        "https://korean.visitkorea.or.kr/dgtourcard/biz/mbrb/mbrbPtcl.do?"
        "mbrbId=cdb03f3e-180d-11ef-b16c-0242ac130002"
    )


def test_official_member_benefit_url_returns_none_without_member_id() -> None:
    assert dgtour.official_member_benefit_url({"name": "로우풀"}) is None


def test_fetch_partner_benefits_requests_each_category_by_popular_order() -> None:
    from app.services.external_benefit_collection import fetch_digital_tourism_partner_benefits

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        def post(self, _url: str, *, data: dict[str, object], **_kwargs: object) -> FakeResponse:
            self.payloads.append(dict(data))
            category = str(data["mbrbBnefClCd"])
            rows = {
                "FDRK": [
                    {
                        "totCnt": 1,
                        "mbrbId": "food-1",
                        "mbrbBnefClCd": "FDRK",
                        "mbrbBnefClCdNm": "식음료",
                        "mbrbNm": "로우풀",
                        "svcCn": "음료 리필",
                        "utztCnt": 200,
                    }
                ],
                "STAYNG": [],
                "VWNG": [],
                "EXPRN": [],
                "SHPN": [],
                "FEST": [],
                "TRNS": [],
                "ETC": [],
            }[category]
            return FakeResponse({"resultList": rows, "pageNo": int(data["pageNo"])})

    client = FakeClient()

    benefits = fetch_digital_tourism_partner_benefits(
        city="합천",
        mtpc_do_cd="48",
        signgu_cd="48890",
        client=client,
    )

    assert [payload["mbrbBnefClCd"] for payload in client.payloads] == [
        "FDRK",
        "STAYNG",
        "VWNG",
        "EXPRN",
        "SHPN",
        "FEST",
        "TRNS",
        "ETC",
    ]
    assert {payload["orderDiv"] for payload in client.payloads} == {"UTZT"}
    assert benefits[0]["categoryName"] == "식음료"
    assert benefits[0]["usageCount"] == 200


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
    assert enriched.raw_payload["partnerBenefitCategoryHighlights"] == [
        {
            "categoryCode": "FDRK",
            "categoryName": "식음료",
            "totalCount": 1,
            "remainingCount": 0,
            "representative": benefits[0],
        },
        {
            "categoryCode": "STAYNG",
            "categoryName": "숙박",
            "totalCount": 1,
            "remainingCount": 0,
            "representative": benefits[1],
        },
    ]
    assert "🍽️ 하동 카페: 음료 할인\n카페" in enriched.raw_detail_text
    assert "·" not in enriched.raw_detail_text
