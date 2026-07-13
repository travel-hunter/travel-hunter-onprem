from app.models import ExternalSourceRecord
from app.services.policy_category_classifier import classify_external_policy_category


def make_record(
    *,
    title: str,
    benefit_text: str = "",
    raw_detail_text: str = "",
    tags: list[str] | None = None,
    source_category: str = "regional_benefit",
    detail_url: str | None = None,
    collected_page_url: str = "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
) -> ExternalSourceRecord:
    return ExternalSourceRecord(
        source_name="여행가는 달",
        source_type="official_campaign",
        source_url=collected_page_url,
        source_category=source_category,
        external_id=title,
        canonical_key=title,
        detail_url=detail_url,
        collected_page_url=collected_page_url,
        title=title,
        organizer_text="한국관광공사",
        organizers=["한국관광공사"],
        region="전국",
        city=None,
        is_nationwide=False,
        status="active",
        benefit_text=benefit_text or title,
        benefit_value_text=None,
        benefit_value_type="unknown",
        tags=tags or [],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text=title,
        raw_detail_text=raw_detail_text or benefit_text or title,
        raw_payload={},
        freshness_status="fresh",
    )


def classify(title: str, **kwargs) -> str:
    return classify_external_policy_category(make_record(title=title, **kwargs)).category


def test_classifies_train_trip_as_transport_even_with_overnight_package_text() -> None:
    assert classify("남도 기차둘레길 1박 2일 최대 35% 할인행사") == "교통"


def test_classifies_transport_source_examples() -> None:
    assert classify("테마열차 할인") == "교통"
    assert classify("네이버 항공권에서 국내선 이용 시") == "교통"
    assert classify("전국 렌터카 대여료 할인") == "교통"


def test_classifies_lodging_and_package_examples() -> None:
    assert classify("피카푸 피크닉앤글램핑 숙박전용 4만원 할인") == "숙박"
    assert classify("K리그 지역 원정 경기 관람 및 체류여행 패키지 할인") == "여행상품"


def test_classifies_regional_discount_when_no_stronger_signal_exists() -> None:
    assert classify("부산 여행 캐시백") == "지역할인"


def test_source_category_boosts_do_not_override_stronger_title_signal() -> None:
    assert classify("남도 기차둘레길 할인", source_category="regional_benefit") == "교통"
    assert classify("합천 반값여행 지원", source_category="local_half_trip") == "지역할인"
    assert classify("테마열차 할인", source_category="traffic_benefit") == "교통"
    assert classify("여행가는 달 할인권", source_category="stay_discount") == "숙박"
