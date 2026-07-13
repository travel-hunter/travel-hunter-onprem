from datetime import date, datetime
from pathlib import Path

from app.services.travelmonth_parser import parse_regional_benefits


FIXTURE = Path(__file__).parent / "fixtures" / "travelmonth_benefit_sample.html"
FETCHED_AT = datetime(2026, 5, 21, 9, 0, 0)


def _parse_fixture():
    return parse_regional_benefits(
        FIXTURE.read_text(encoding="utf-8"),
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=FETCHED_AT,
        today=date(2026, 5, 21),
    )


def test_parse_regional_benefits_extracts_expected_records() -> None:
    records = _parse_fixture()

    assert len(records) == 4
    first = records[0]
    assert first.title == "동강사진박물관 여행가는 달 입장료 최대 50% 할인"
    assert first.region == "강원"
    assert first.city == "영월군"
    assert first.status == "active"
    assert first.extracted_discount_percent == 50
    assert first.benefit_value_type == "percent"
    assert first.inferred_travel_styles == ["체험", "사진"]
    assert first.detail_url == "https://www.yw.go.kr"
    assert first.last_verified_at == FETCHED_AT


def test_parse_regional_benefits_records_new_vacation_source_url() -> None:
    records = _parse_fixture()

    assert records[0].source_url == "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    assert (
        records[0].collected_page_url
        == "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    )


def test_parse_regional_benefits_marks_nationwide_fallback_candidate() -> None:
    records = _parse_fixture()

    nationwide = records[2]
    assert nationwide.organizer_text == "한국관광공사"
    assert nationwide.region is None
    assert nationwide.is_nationwide is True
    assert nationwide.extracted_amount_krw == 30000


def test_parse_regional_benefits_keeps_ended_records_but_marks_status() -> None:
    records = _parse_fixture()

    ended = records[3]
    assert ended.status == "ended"
    assert ended.freshness_status == "expired"
    assert ended.benefit_value_type == "free"


def test_parse_regional_benefits_skips_incomplete_sections() -> None:
    html = """
    <section data-benefit-item>
      <p class="organizer">강원특별자치도, 영월군</p>
      <p class="period">2026-04-01 ~ 2026-05-31</p>
      <p class="status">[진행중]</p>
      <a class="detail" href="https://www.yw.go.kr">자세히 보기</a>
    </section>
    """

    records = parse_regional_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=FETCHED_AT,
        today=date(2026, 5, 21),
    )

    assert records == []


def test_parse_regional_benefits_skips_invalid_period_dates() -> None:
    html = """
    <section data-benefit-item>
      <p class="organizer">강원특별자치도, 영월군</p>
      <h3>동강사진박물관 여행가는 달 입장료 최대 50% 할인</h3>
      <p class="period">2026-02-31 ~ 2026-03-10</p>
      <p class="status">[진행중]</p>
      <div class="benefit">동강사진박물관 입장료 최대 50% 할인</div>
      <a class="detail" href="https://www.yw.go.kr">자세히 보기</a>
    </section>
    """

    records = parse_regional_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=FETCHED_AT,
        today=date(2026, 5, 21),
    )

    assert records == []


def test_parse_regional_benefits_extracts_current_live_thumbnail_modal_shape() -> None:
    html = """
    <div class="list-thumbnail list-thumbnail--benefit">
      <ul>
        <li>
          <a href="#modal-benefit-218"
             data-log-seq="218"
             data-log-type="benefit"
             data-action-track-area="강원"
             data-action-track-title="여행가는 달 남이섬 체험 20%할인">
            <p><span>할인혜택</span></p>
            <p>여행가는 달 남이섬 체험 20%할인</p>
            <p>2026-04-01 ~ 2026-05-29 <strong>[진행중]</strong></p>
            <p>강원특별자치도, 춘천시, 남이섬</p>
          </a>
        </li>
        <li>
          <a href="#modal-benefit-220"
             data-log-seq="220"
             data-log-type="benefit"
             data-action-track-area="경상"
             data-action-track-title="여행가는 달 안동가자~ 찜닭도 먹고 음료수는 공짜~!">
            <p><span>할인혜택</span></p>
            <p>여행가는 달 안동가자~ 찜닭도 먹고 음료수는 공짜~!</p>
            <p>2026-04-01 ~ 2026-05-29 <strong>[진행중]</strong></p>
            <p>경상북도, 안동시, 안동구시장</p>
          </a>
        </li>
      </ul>
    </div>
    <div id="modal-benefit-218" class="modal fade modal-benefit">
      <article>
        <header>
          <p>강원특별자치도, 춘천시, 남이섬</p>
          <h3>여행가는 달 남이섬 체험 20%할인</h3>
          <ul><li>#남이섬</li><li>#강원여행</li></ul>
        </header>
        <dl>
          <div><dt>기간</dt><dd>2026-04-01 ~ 2026-05-29</dd></div>
          <div><dt>할인혜택</dt><dd>남이섬 입장료 및 체험 20% 할인</dd></div>
          <div><dt>문의처</dt><dd>031-000-0000</dd></div>
        </dl>
        <a href="https://example.com/nami"><span>자세히 보기</span></a>
      </article>
    </div>
    <div id="modal-benefit-220" class="modal fade modal-benefit">
      <article>
        <header>
          <p>경상북도, 안동시, 안동구시장</p>
          <h3>여행가는 달 안동가자~ 찜닭도 먹고 음료수는 공짜~!</h3>
          <ul><li>#안동찜닭</li><li>#안동구시장</li></ul>
        </header>
        <dl>
          <div><dt>기간</dt><dd>2026-04-01 ~ 2026-05-29</dd></div>
          <div><dt>할인혜택</dt><dd>찜닭 1테이블당 음료수 1병 무료제공</dd></div>
          <div><dt>문의처</dt><dd>010-9382-7657</dd></div>
        </dl>
      </article>
    </div>
    """

    records = parse_regional_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=FETCHED_AT,
        today=date(2026, 5, 21),
    )

    assert len(records) == 2
    first = records[0]
    assert first.external_id == "218"
    assert first.title == "여행가는 달 남이섬 체험 20%할인"
    assert first.organizer_text == "강원특별자치도, 춘천시, 남이섬"
    assert first.region == "강원"
    assert first.city == "춘천시"
    assert first.status == "active"
    assert first.extracted_discount_percent == 20
    assert first.detail_url == "https://example.com/nami"
    assert first.tags == ["남이섬", "강원여행"]
    assert first.contact_text == "031-000-0000"

    second = records[1]
    assert second.region == "경북"
    assert second.benefit_value_type == "free"


def test_parse_regional_benefits_keeps_current_live_items_without_period() -> None:
    html = """
    <div class="list-thumbnail list-thumbnail--benefit">
      <ul>
        <li>
          <a href="#modal-benefit-282"
             data-log-seq="282"
             data-log-type="benefit"
             data-action-track-title="K리그 지역 원정 경기 관람 및 체류여행 패키지 할인">
            <p><span>할인혜택</span></p>
            <p>K리그 지역 원정 경기 관람 및 체류여행 패키지 할인</p>
            <p></p>
            <p>한국관광공사</p>
          </a>
        </li>
      </ul>
    </div>
    <div id="modal-benefit-282" class="modal fade modal-benefit">
      <article>
        <header>
          <p>한국관광공사</p>
          <h3>K리그 지역 원정 경기 관람 및 체류여행 패키지 할인</h3>
          <ul><li>#스포츠관람</li><li>#K리그</li></ul>
        </header>
        <dl>
          <div><dt>할인혜택</dt><dd>열차 연계 스포츠 특화 체류형 관광 상품 할인판매 (최대 5만원 한도)</dd></div>
          <div><dt>문의처</dt><dd>02-2084-5738</dd></div>
        </dl>
      </article>
    </div>
    """

    records = parse_regional_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=FETCHED_AT,
        today=date(2026, 5, 21),
    )

    assert len(records) == 1
    assert records[0].external_id == "282"
    assert records[0].status == "unknown"
    assert records[0].start_date is None
    assert records[0].end_date is None
    assert records[0].is_nationwide is True
    assert records[0].extracted_amount_krw == 50000


def test_parse_regional_benefits_falls_back_to_current_vacation_benefit_summary() -> None:
    html = """
    <main>
      <h1>여행가는 달 지역사랑 휴가지원</h1>
      <p>농어촌 인구감소지역 방문 후 소비 인증 시 여행경비 50% 환급(모바일 지역화폐)</p>
      <p>(적용 지역) 16개 지자체</p>
      <p>강원권(영월, 횡성, 평창)</p>
      <p>경상권(밀양, 하동, 거창, 합천, 남해)</p>
      <p>충청권(제천)</p>
      <p>전라권(강진, 영광, 해남, 영암, 고흥, 완도, 고창)</p>
      <p>운영기간 4~8월(단, 월별 예산 배정액 소진 시 접수 마감)</p>
      <p>문의처 반값여행 운영사무국 02-6271-2016</p>
      <p>1인 10만원, 2인 이상 20만원, 청년 20% 가산, 가족 최대 50만원</p>
      <a href="/dgtourcard/tour50.do">할인혜택 보러가기</a>
    </main>
    """

    records = parse_regional_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        fetched_at=datetime(2026, 6, 11, 9, 0, 0),
        today=date(2026, 6, 11),
    )

    assert len(records) == 16
    by_city = {record.city: record for record in records}
    assert by_city["영월군"].region == "강원"
    assert by_city["밀양시"].region == "경남"
    assert by_city["제천시"].region == "충북"
    assert by_city["고창군"].region == "전북"
    first = by_city["영월군"]
    assert first.status == "active"
    assert first.start_date == date(2026, 4, 1)
    assert first.end_date == date(2026, 8, 31)
    assert first.extracted_discount_percent == 50
    assert first.extracted_amount_krw == 500000
    assert first.benefit_value_type == "mixed"
    assert first.detail_url == "https://korean.visitkorea.or.kr/dgtourcard/tour50.do"
    assert first.raw_payload["fallback"] == "vacation-benefit-summary"
