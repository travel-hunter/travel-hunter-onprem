from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.dgtourcard_parser import parse_dgtourcard_benefits


DGTOURCARD_DATA_HTML = """
<html><body>
<a href="javascript:func_go_detail('밀양','1')" data-trvid="1" data-town="밀양"
   data-trvnm="2026-경상남도 밀양" data-link="https://www.mybanhada.com/"
   data-evtbgndt="2026-04-01" data-evtenddt="2026-08-31" data-sttsnm="준비중">밀양</a>
<a href="javascript:func_go_detail('하동','3')" data-trvid="3" data-town="하동"
   data-trvnm="2026-경상남도 하동" data-link="https://hadongtrip.kr/index.php"
   data-evtbgndt="2026-05-20" data-evtenddt="2026-06-30" data-sttsnm="신청접수중">하동</a>
<a href="javascript:func_go_detail('영광','8')" data-trvid="8" data-town="영광"
   data-trvnm="2026-전라남도 영광" data-link="https://www.yeonggwang.go.kr/travel/"
   data-evtbgndt="2026-05-20" data-evtenddt="2026-06-30" data-sttsnm="신청접수중">영광</a>
<a href="javascript:func_go_detail('제천','6')" data-trvid="6" data-town="제천"
   data-trvnm="2026-충청북도 제천" data-link="https://www.jctour.kr/"
   data-evtbgndt="2026-03-01" data-evtenddt="2026-03-31" data-sttsnm="마감">제천</a>
<a href="javascript:func_go_detail('강진','7')" data-trvid="7" data-town="강진"
   data-trvnm="2026-전라남도 강진" data-link=""
   data-evtbgndt="" data-evtenddt="" data-sttsnm="준비중">강진</a>
</body></html>
"""


DGTOURCARD_SECTION_HTML = """
<html><body>
<section>
  <h2>합천 신청접수중</h2>
  <p>신청기간 : 2026.05.20-2026.06.30</p>
  <p>여행기간 : 2026.06.01~2026.06.30</p>
  <p>지원내용 : 숙박, 식사, 체험 여행비 환급</p>
  <p>문의전화 : 055-930-0000</p>
  <a href="/dgtourcard/hapcheon/detail.do">지역 상세 바로가기</a>
</section>
<section>
  <h2>평창 준비중</h2>
  <p>신청기간 : 준비중</p>
  <p>여행기간 : 2026.07.01~2026.08.31</p>
  <a href="https://pc.halftrip.kr">평창 안내</a>
</section>
<section>
  <h2>고창 마감</h2>
  <p>신청기간 : 2026.03.01-2026.03.31</p>
  <p>여행기간 : 2026.04.01~2026.04.30</p>
  <a href="javascript:void(0)">잘못된 링크</a>
</section>
<section>
  <h2>없는지역 신청접수중</h2>
  <p>신청기간 : 2026.05.20-2026.06.30</p>
</section>
</body></html>
"""


def test_parse_dgtourcard_benefits_reads_official_data_attributes() -> None:
    records = parse_dgtourcard_benefits(
        DGTOURCARD_DATA_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert [record.city for record in records] == ["밀양", "하동", "영광", "제천", "강진"]
    assert [record.status for record in records] == [
        "scheduled",
        "active",
        "active",
        "ended",
        "scheduled",
    ]
    assert records[1].source_category == "local_half_trip"
    assert records[1].source_name == "대한민국 반값여행"
    assert records[1].title == "[하동] 대한민국 반값여행 지원"
    assert records[1].region == "경남"
    assert records[1].freshness_status == "fresh"
    assert records[1].benefit_value_text == "최대 20만원 환급"
    assert records[1].detail_url == "https://hadongtrip.kr/index.php"
    assert records[2].detail_url == "https://www.yeonggwang.go.kr/travel/"
    assert records[4].detail_url is None


def test_parse_dgtourcard_benefits_falls_back_to_section_markup() -> None:
    records = parse_dgtourcard_benefits(
        DGTOURCARD_SECTION_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert [record.city for record in records] == ["합천", "평창", "고창"]
    assert records[0].status == "active"
    assert records[0].detail_url == "https://korean.visitkorea.or.kr/dgtourcard/hapcheon/detail.do"
    assert records[0].contact_text == "055-930-0000"
    assert records[0].raw_payload["applicationPeriod"] == "2026.05.20-2026.06.30"
    assert records[0].raw_payload["tripPeriod"] == "2026.06.01~2026.06.30"
    assert records[1].status == "scheduled"
    assert records[1].detail_url == "https://pc.halftrip.kr"
    assert records[2].status == "ended"
    assert records[2].detail_url is None


def test_parse_dgtourcard_benefits_handles_june_july_status_variants() -> None:
    html = """
    <html><body>
    <section>
      <h2>영월 예정</h2>
      <p>신청접수 : 6월 중 예정</p>
      <p>여행기간 : 2026.07.01~2026.07.31</p>
    </section>
    <section>
      <h2>거창</h2>
      <p>신청접수 : 6.16 10시부터</p>
      <p>여행기간 : 2026.07.01~2026.07.31</p>
    </section>
    <section>
      <h2>남해 마감</h2>
      <p>신청접수 : 마감</p>
      <p>여행기간 : 2026.07.01~2026.07.31</p>
    </section>
    </body></html>
    """

    before_start = parse_dgtourcard_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 15, tzinfo=UTC),
        today=date(2026, 6, 15),
    )
    after_start = parse_dgtourcard_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )

    assert [record.status for record in before_start] == ["scheduled", "scheduled", "ended"]
    assert [record.status for record in after_start] == ["scheduled", "active", "ended"]
    assert after_start[1].start_date == date(2026, 6, 16)
    assert after_start[1].raw_payload["tripPeriod"] == "2026.07.01~2026.07.31"


def test_parse_dgtourcard_benefits_reads_current_detail_aside_fields() -> None:
    html = """
    <html><body>
    <aside class="cl-posi-detail step-7"
        data-trvid="7"
        data-mtpcdocdnm="전라남도"
        data-signgucdnm="강진군"
        data-trvnm="2026-전라남도 강진"
        data-link="https://www.gangjintour.com/"
        data-evtbgndt="2026-06-10"
        data-evtenddt="2026-08-31"
        data-sttscd="ONGOING"
        data-sttsnm="신청접수중">
      <h2><em>강진</em><span>신청접수중</span></h2>
      <dl>
        <dt>신청기간 : </dt>
        <dd>2026.06.10-2026.08.31<br>● 여행기간 : 6.10~8.31<br>- 6.10(수) 9시부터</dd>
      </dl>
      <dl><dt>지역화폐 : </dt><dd>chak 앱(모바일 강진사랑상품권)</dd></dl>
      <dl><dt>특이사항 : </dt><dd>강진군 관광지 2개소 이상 방문</dd></dl>
      <dl><dt>문의전화 :</dt><dd><a href="tel:061-433-3349">061-433-3349</a></dd></dl>
    </aside>
    </body></html>
    """

    records = parse_dgtourcard_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )

    assert len(records) == 1
    record = records[0]
    assert record.city == "강진"
    assert record.status == "active"
    assert record.detail_url == "https://www.gangjintour.com/"
    assert record.start_date == date(2026, 6, 10)
    assert record.end_date == date(2026, 8, 31)
    assert record.raw_payload["applicationDetail"].startswith("2026.06.10-2026.08.31")
    assert record.raw_payload["tripPeriod"] == "6.10~8.31"
    assert record.raw_payload["localCurrency"] == "chak 앱(모바일 강진사랑상품권)"
    assert record.raw_payload["notes"] == "강진군 관광지 2개소 이상 방문"
    assert record.contact_text == "061-433-3349"


def test_parse_dgtourcard_benefits_keeps_canonical_key_stable_when_trip_period_detail_changes() -> None:
    first_html = """
    <html><body>
    <aside data-trvid="7" data-signgucdnm="강진군" data-trvnm="2026-전라남도 강진"
        data-link="https://www.gangjintour.com/" data-evtbgndt="2026-06-10"
        data-evtenddt="2026-08-31" data-sttsnm="신청접수중">
      <dl><dt>신청기간 : </dt><dd>2026.06.10-2026.08.31<br>● 여행기간 : 6.10~8.31</dd></dl>
    </aside>
    </body></html>
    """
    changed_trip_period_html = """
    <html><body>
    <aside data-trvid="7" data-signgucdnm="강진군" data-trvnm="2026-전라남도 강진"
        data-link="https://www.gangjintour.com/" data-evtbgndt="2026-06-10"
        data-evtenddt="2026-08-31" data-sttsnm="신청접수중">
      <dl><dt>신청기간 : </dt><dd>2026.06.10-2026.08.31<br>● 여행기간 : 7.1~8.31</dd></dl>
    </aside>
    </body></html>
    """

    first_records = parse_dgtourcard_benefits(
        first_html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )
    changed_records = parse_dgtourcard_benefits(
        changed_trip_period_html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )

    assert first_records[0].canonical_key == changed_records[0].canonical_key
    assert first_records[0].raw_payload["tripPeriod"] == "6.10~8.31"
    assert changed_records[0].raw_payload["tripPeriod"] == "7.1~8.31"
