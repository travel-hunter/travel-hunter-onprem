from datetime import date

from app.services import travelmonth_normalizer as normalizer


def test_normalize_region_from_local_government_text() -> None:
    result = normalizer.normalize_region("강원특별자치도, 영월군")

    assert result.region == "강원"
    assert result.city == "영월군"
    assert result.is_nationwide is False


def test_normalize_region_marks_knto_single_org_as_nationwide() -> None:
    result = normalizer.normalize_region("한국관광공사")

    assert result.region is None
    assert result.city is None
    assert result.is_nationwide is True


def test_normalize_region_does_not_infer_ambiguous_short_alias_from_title() -> None:
    result = normalizer.normalize_region("민간기관", title="프로야구 경기 관람권 할인")

    assert result.region is None
    assert result.city is None
    assert result.is_nationwide is False


def test_parse_period_reads_start_and_end_dates() -> None:
    assert normalizer.parse_period("2026-04-01 ~ 2026-05-31") == (
        date(2026, 4, 1),
        date(2026, 5, 31),
    )


def test_status_text_overrides_date_status() -> None:
    assert (
        normalizer.normalize_status(
            "[종료]",
            date(2026, 4, 1),
            date(2026, 5, 31),
            date(2026, 5, 21),
        )
        == "ended"
    )
    assert (
        normalizer.normalize_status(
            "[진행중]",
            date(2026, 4, 1),
            date(2026, 5, 31),
            date(2026, 5, 21),
        )
        == "active"
    )


def test_extract_benefit_value_prefers_largest_amount() -> None:
    value = normalizer.extract_benefit_value("개인 최대 10만원, 팀 최대 20만원까지 환급 지원")

    assert value.amount_krw == 200000
    assert value.discount_percent is None
    assert value.value_type == "amount"
    assert value.value_text == "최대 20만원"


def test_extract_benefit_value_reads_uncommaed_large_manwon_amount() -> None:
    value = normalizer.extract_benefit_value("숙박비 최대 1000만원 지원")

    assert value.amount_krw == 10000000
    assert value.discount_percent is None
    assert value.value_type == "amount"
    assert value.value_text == "최대 1000만원"


def test_extract_benefit_value_reads_spaced_manwon_amount() -> None:
    value = normalizer.extract_benefit_value("숙박비 최대 10만 원 지원")

    assert value.amount_krw == 100000
    assert value.discount_percent is None
    assert value.value_type == "amount"
    assert value.value_text == "최대 10만원"


def test_extract_benefit_value_reads_percent_when_amount_missing() -> None:
    value = normalizer.extract_benefit_value("입장료 최대 50% 할인")

    assert value.amount_krw is None
    assert value.discount_percent == 50
    assert value.value_type == "percent"
    assert value.value_text == "최대 50%"


def test_extract_benefit_value_reads_percent_from_title_when_detail_has_conditions() -> None:
    value = normalizer.extract_benefit_value(
        "행사 기간 중 온라인 체험상품 예약 결제 후 사용 완료 참여자 26년 4월 중순부터 5월 말",
        title="웰촌 체험상품 30% 할인",
    )

    assert value.amount_krw is None
    assert value.discount_percent == 30
    assert value.value_type == "percent"
    assert value.value_text == "최대 30%"


def test_extract_benefit_value_reads_free_benefit() -> None:
    value = normalizer.extract_benefit_value("루프탑 전망대 무료 개방")

    assert value.amount_krw is None
    assert value.discount_percent is None
    assert value.value_type == "free"
    assert value.value_text == "무료"


def test_infer_travel_styles_from_tags_and_text() -> None:
    styles = normalizer.infer_travel_styles(
        title="동강사진박물관 입장료 할인",
        benefit_text="박물관 관람료 할인",
        tags=["사진관", "영월박물관"],
    )

    assert styles == ["체험", "사진"]
