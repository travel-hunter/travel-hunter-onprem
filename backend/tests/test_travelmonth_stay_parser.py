from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.travelmonth_stay_parser import SOURCE_URL, parse_stay_discount_benefits


STAY_HTML = """
<html><body>
<section data-stay-discount>
  <h2>2026 대한민국 숙박세일 페스타</h2>
  <p>쿠폰 발급기간 : 2026.6.11 ~ 2026.7.31 예산 소진 시 조기 종료</p>
  <p>입실기간 : 6월 11일 ~ 7월 31일</p>
  <p>할인혜택 : 비수도권 숙박상품 2/3/5/7만원 할인권 지원</p>
  <a href="/travelmonth/benefits/stay.do">자세히 보기</a>
</section>
</body></html>
"""


KTOSTAY_HTML = """
<html><body>
<h1>2026 대한민국 숙박세일 페스타</h1>
<div class="section-02">
  <div class="benefit-info">
    <ul class="coupon-use-info">
      <li><div class="visit-info-row">
        <p class="txt-title"><strong>발급기간</strong></p>
        <ul class="schedule-info"><li><strong class="txt-period">2026.6.11<em>(목)</em>~7.31<em>(금)</em></strong></li>
        <li>매일 오전 10시부터 선착순 발급 (단, 기한 내 소진 시 발급 불가)</li></ul>
      </div></li>
      <li><div class="visit-info-row">
        <p class="txt-title"><strong>입실기간</strong></p>
        <ul class="schedule-info"><li><strong class="txt-period"><span class="only_mo">2026.</span>6.11<em>(목)</em>~7.31<em>(금)</em></strong></li></ul>
      </div></li>
      <li><div class="visit-info-row">
        <p class="txt-title"><strong>사용지역</strong></p>
        <ul class="schedule-info">
          <li class="area-info"><strong>비수도권 인구감소지역<em class="txt-small">(85개 지자체)</em></strong></li>
          <li><div class="population-group">
            <strong>강원</strong> 고성군, 삼척시, 양구군, 양양군, 영월군, 정선군, 철원군, 태백시, 평창군, 홍천군, 화천군, 횡성군&nbsp;&nbsp;
            <strong>경남</strong> 거창군, 고성군, 남해군, 밀양시, 산청군, 의령군, 창녕군, 하동군, 함안군, 함양군, 합천군&nbsp;&nbsp;
            <strong>경북</strong> 고령군, 문경시, 봉화군, 상주시, 성주군, 안동시, 영덕군, 영양군, 영주시, 영천시, 울릉군, 울진군, 의성군, 청도군, 청송군&nbsp;&nbsp;
            <strong>대구</strong> 군위군, 남구, 서구&nbsp;&nbsp;
            <strong>부산</strong> 동구, 서구, 영도구&nbsp;&nbsp;
            <strong>전남</strong> 강진군, 고흥군, 곡성군, 구례군, 담양군, 보성군, 신안군, 영광군, 영암군, 완도군, 장성군, 장흥군, 진도군, 함평군, 해남군, 화순군&nbsp;&nbsp;
            <strong>전북</strong> 고창군, 김제시, 남원시, 무주군, 부안군, 순창군, 임실군, 장수군, 정읍시, 진안군&nbsp;&nbsp;
            <strong>충남</strong> 공주시, 금산군, 논산시, 보령시, 부여군, 서천군, 예산군, 청양군, 태안군&nbsp;&nbsp;
            <strong>충북</strong> 괴산군, 단양군, 보은군, 영동군, 옥천군, 제천시
          </div></li>
        </ul>
      </div></li>
      <li><div class="visit-info-row">
        <p class="txt-title txt-spacing"><strong><span class="only_web">사&nbsp;&nbsp;용&nbsp;&nbsp;처</span></strong></p>
        <ul class="schedule-info"><li class="area-info"><strong>국내숙박 업소</strong></li>
        <li class="usage-info">관광진흥법, 공중위생관리법 등에 등록된 숙박업소 / 대실 사용 불가</li></ul>
      </div></li>
      <li><div class="visit-info-row">
        <p class="txt-title"><strong>사용방법</strong></p>
        <ul class="schedule-info"><li class="area-info"><strong>참여 온라인 여행사를 통한 숙박 할인권 발급 후 사용</strong></li>
        <li class="usage-info">1인 1매 사용(선착순) / 사업기간 변동 가능</li></ul>
      </div></li>
      <li class="discount-benefit-info"><div class="visit-info-row">
        <p class="txt-title"><strong>할인혜택</strong></p>
        <ul class="schedule-info coupon-info-row">
          <li><strong class="txt-coupon-discount"><span>7만원 미만*</span><br>국내 숙박상품 예약 시<br><span>2만원 할인</span>(1박 이상)</strong></li>
          <li><strong class="txt-coupon-discount"><span>7만원 이상*</span><br>국내 숙박상품 예약 시<br><span>3만원 할인</span>(1박 이상)</strong></li>
          <li><strong class="txt-coupon-discount"><span>14만원 미만**</span><br>국내 숙박상품 예약 시<br><span>5만원 할인</span>(연박 이상)</strong></li>
          <li><strong class="txt-coupon-discount"><span>14만원 이상**</span><br>국내 숙박상품 예약 시<br><span>7만원 할인</span>(연박 이상)</strong></li>
        </ul>
      </div></li>
    </ul>
  </div>
</div>
</body></html>
"""


def test_parse_stay_discount_benefits_extracts_amount_period_and_raw_payload() -> None:
    records = parse_stay_discount_benefits(
        STAY_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
        fetched_at=datetime(2026, 6, 12, tzinfo=UTC),
        today=date(2026, 6, 12),
    )

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "대한민국 숙박세일 페스타"
    assert record.source_category == "stay_discount"
    assert record.source_url == SOURCE_URL
    assert record.status == "active"
    assert record.freshness_status == "fresh"
    assert record.start_date == date(2026, 6, 11)
    assert record.end_date == date(2026, 7, 31)
    assert record.benefit_value_type == "amount"
    assert record.extracted_amount_krw == 70000
    assert record.benefit_value_text == "2/3/5/7만원 할인권"
    assert {"숙박", "숙박세일", "비수도권"}.issubset(set(record.tags))
    assert record.region == "비수도권·인구감소지역"
    assert record.raw_payload["issuePeriod"].startswith("2026.6.11")
    assert record.raw_payload["stayPeriod"].startswith("6월 11일")
    assert record.raw_payload["earlyCloseWarning"] is True


def test_parse_ktostay_population_decline_areas_and_common_fields() -> None:
    records = parse_stay_discount_benefits(
        KTOSTAY_HTML,
        collected_page_url="https://ktostay.visitkorea.or.kr/",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )

    assert len(records) == 1
    record = records[0]
    assert record.source_url == "https://ktostay.visitkorea.or.kr/"
    assert record.detail_url == "https://ktostay.visitkorea.or.kr/"
    assert record.collected_page_url == "https://ktostay.visitkorea.or.kr/"
    assert record.status == "active"
    assert record.freshness_status == "fresh"
    assert record.start_date == date(2026, 6, 11)
    assert record.end_date == date(2026, 7, 31)
    assert record.extracted_amount_krw == 70000
    assert record.benefit_value_text == "2/3/5/7만원 할인권"

    payload = record.raw_payload
    assert payload["eligibleAreaCount"] == 85
    areas = {str(group["sido"]): group["cities"] for group in payload["eligibleAreas"]}
    assert areas["강원"][0] == "고성군"
    assert areas["경남"][1] == "고성군"
    assert areas["대구"] == ["군위군", "남구", "서구"]
    assert areas["부산"] == ["동구", "서구", "영도구"]
    assert areas["충북"][-1] == "제천시"
    assert payload["issuePeriod"].startswith("2026.6.11")
    assert payload["stayPeriod"].startswith("2026. 6.11")
    assert "비수도권 인구감소지역" in str(payload["usageArea"])
    assert "국내숙박 업소" in str(payload["usagePlace"])
    assert "참여 온라인 여행사" in str(payload["usageMethod"])
    assert len(payload["discountTiers"]) == 4
    assert "14만원 이상" in str(payload["discountTiers"][-1])
    assert record.contact_text is not None
    assert "할인혜택" in record.contact_text


def test_parse_stay_discount_benefits_uses_fallback_text_record() -> None:
    records = parse_stay_discount_benefits(
        "<html><body>숙박세일 페스타 입실기간 : 6월 11일 ~ 7월 31일 혜택 : 5만원 숙박 할인</body></html>",
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
        fetched_at=datetime(2026, 6, 10, tzinfo=UTC),
        today=date(2026, 6, 10),
    )

    assert len(records) == 1
    assert records[0].status == "scheduled"
    assert records[0].is_nationwide is True
