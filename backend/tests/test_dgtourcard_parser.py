from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.services.dgtourcard_parser import (
    enrich_dgtourcard_benefits_with_detail_pages,
    parse_dgtourcard_benefits,
    parse_local_half_trip_detail_fields,
)


DGTOURCARD_DATA_HTML = """
<html><body>
<a href="javascript:func_go_detail('밀양','1')" data-trvid="1" data-town="밀양" data-mtpcdocd="48"
   data-trvnm="2026-경상남도 밀양" data-link="https://www.mybanhada.com/"
   data-evtbgndt="2026-04-01" data-evtenddt="2026-08-31" data-sttsnm="준비중">밀양</a>
<a href="javascript:func_go_detail('하동','3')" data-trvid="3" data-town="하동" data-mtpcdocd="48"
   data-trvnm="2026-경상남도 하동" data-link="https://hadongtrip.kr/index.php"
   data-evtbgndt="2026-05-20" data-evtenddt="2026-06-30" data-sttsnm="신청접수중">하동</a>
<a href="javascript:func_go_detail('영광','8')" data-trvid="8" data-town="영광" data-mtpcdocd="12"
   data-trvnm="2026-전라남도 영광" data-link="https://www.yeonggwang.go.kr/travel/"
   data-evtbgndt="2026-05-20" data-evtenddt="2026-06-30" data-sttsnm="신청접수중">영광</a>
<a href="javascript:func_go_detail('제천','6')" data-trvid="6" data-town="제천" data-mtpcdocd="43"
   data-trvnm="2026-충청북도 제천" data-link="https://www.jctour.kr/"
   data-evtbgndt="2026-03-01" data-evtenddt="2026-03-31" data-sttsnm="마감">제천</a>
<a href="javascript:func_go_detail('강진','7')" data-trvid="7" data-town="강진" data-mtpcdocd="12"
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
  <h2>화천 신청접수중</h2>
  <p>신청기간 : 2026.05.20-2026.06.30</p>
  <p>여행기간 : 2026.06.01~2026.06.30</p>
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
    assert records[1].raw_payload["cardCopy"]["summary"] == "최대 20만원 환급"


def test_parse_dgtourcard_benefits_falls_back_to_section_markup() -> None:
    records = parse_dgtourcard_benefits(
        DGTOURCARD_SECTION_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    # 시군 목록은 보지 않는다: 화천은 읽고, 여행기간 줄이 없는 '없는지역' 구역만 거른다.
    assert [record.city for record in records] == ["합천", "평창", "고창", "화천"]
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

    assert [record.city for record in before_start] == ["영월", "거창", "남해"]
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
        data-signgucdnm="하동군"
        data-trvnm="2026-경상남도 하동"
        data-link="https://hadongtrip.kr/index.php"
        data-evtbgndt="2026-06-10"
        data-evtenddt="2026-08-31"
        data-sttscd="ONGOING"
        data-sttsnm="신청접수중">
      <h2><em>하동</em><span>신청접수중</span></h2>
      <dl>
        <dt>신청기간 : </dt>
        <dd>2026.06.10-2026.08.31<br>● 여행기간 : 6.10~8.31<br>- 6.10(수) 9시부터</dd>
      </dl>
      <dl><dt>지역화폐 : </dt><dd>chak 앱(모바일 하동사랑상품권)</dd></dl>
      <dl><dt>특이사항 : </dt><dd>하동군 관광지 2개소 이상 방문</dd></dl>
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
    assert record.city == "하동"
    assert record.status == "active"
    assert record.detail_url == "https://hadongtrip.kr/index.php"
    assert record.start_date == date(2026, 6, 10)
    assert record.end_date == date(2026, 8, 31)
    assert record.raw_payload["applicationDetail"].startswith("2026.06.10-2026.08.31")
    assert record.raw_payload["tripPeriod"] == "6.10~8.31"
    assert record.raw_payload["localCurrency"] == "chak 앱(모바일 하동사랑상품권)"
    assert record.raw_payload["notes"] == "하동군 관광지 2개소 이상 방문"
    assert record.contact_text == "061-433-3349"


def test_parse_dgtourcard_benefits_keeps_canonical_key_stable_when_trip_period_detail_changes() -> None:
    first_html = """
    <html><body>
    <aside data-trvid="3" data-signgucdnm="하동군" data-trvnm="2026-경상남도 하동"
        data-link="https://hadongtrip.kr/index.php" data-evtbgndt="2026-06-10"
        data-evtenddt="2026-08-31" data-sttsnm="신청접수중">
      <dl><dt>신청기간 : </dt><dd>2026.06.10-2026.08.31<br>● 여행기간 : 6.10~8.31</dd></dl>
    </aside>
    </body></html>
    """
    changed_trip_period_html = """
    <html><body>
    <aside data-trvid="3" data-signgucdnm="하동군" data-trvnm="2026-경상남도 하동"
        data-link="https://hadongtrip.kr/index.php" data-evtbgndt="2026-06-10"
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


def _tour50_card(
    *,
    trvid: int,
    city_name: str,
    sido_code: str,
    sido_name: str,
    begin: str = "2026-06-10",
    end: str = "2026-08-31",
) -> str:
    return (
        f'<aside data-trvid="{trvid}" data-mtpcdocd="{sido_code}" data-mtpcdocdnm="{sido_name}" '
        f'data-signgucdnm="{city_name}" data-trvnm="2026-{sido_name} {city_name[:-1]}" '
        f'data-evtbgndt="{begin}" data-evtenddt="{end}" data-sttsnm="신청접수중"></aside>'
    )


def _parse_tour50(html: str):
    return parse_dgtourcard_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )


def test_parse_dgtourcard_benefits_reads_cities_outside_the_resident_card_list() -> None:
    cards = [
        ("강진군", "12", "전라남도", "강진", "전남"),
        ("남해군", "48", "경상남도", "남해", "경남"),
        ("영암군", "12", "전라남도", "영암", "전남"),
        ("횡성군", "51", "강원특별자치도", "횡성", "강원"),
        ("고성군", "48", "경상남도", "고성", "경남"),
        ("영천시", "47", "경상북도", "영천", "경북"),
        ("서천군", "44", "충청남도", "서천", "충남"),
        ("화천군", "51", "강원특별자치도", "화천", "강원"),
    ]
    html = "<html><body>" + "".join(
        _tour50_card(trvid=index, city_name=name, sido_code=code, sido_name=sido)
        for index, (name, code, sido, _city, _region) in enumerate(cards, start=1)
    ) + "</body></html>"

    records = _parse_tour50(html)

    assert [(record.city, record.region) for record in records] == [
        (city, region) for _name, _code, _sido, city, region in cards
    ]
    assert records[4].title == "[고성] 대한민국 반값여행 지원"


@pytest.mark.parametrize(
    ("attrs", "region"),
    [
        # 전남 카드: 시도 이름이 별칭표에 없어도 시도 코드(signgucd 앞 두 자리)로 정한다
        (
            'data-mtpcdocdnm="전남광주통합특별시" data-signgucd="12830" data-signgucdnm="영광군"',
            "전남",
        ),
        (
            'data-mtpcdocd="48" data-mtpcdocdnm="경상남도" data-signgucd="48820" data-signgucdnm="고성군"',
            "경남",
        ),
        # 코드를 못 찾으면 시도 이름 별칭표, 그것도 없으면 전국
        ('data-mtpcdocd="99" data-mtpcdocdnm="강원특별자치도" data-signgucdnm="고성군"', "강원"),
        ('data-mtpcdocdnm="새이름특별시" data-signgucdnm="영광군"', "전국"),
    ],
)
def test_parse_dgtourcard_benefits_picks_region_from_sido_code(attrs: str, region: str) -> None:
    html = (
        f'<aside data-trvid="1" {attrs} data-trvnm="2026-전라남도 영광" '
        'data-evtbgndt="2026-06-10" data-evtenddt="2026-08-31" data-sttsnm="신청접수중"></aside>'
    )

    assert _parse_tour50(html)[0].region == region


def test_parse_dgtourcard_benefits_keeps_existing_city_canonical_key() -> None:
    # 시군 필터를 없앤 뒤에도 기존 수집 키가 같아야 기존 기록과 이어진다(10/19 공식 페이지의 밀양).
    html = _tour50_card(
        trvid=1,
        city_name="밀양시",
        sido_code="48",
        sido_name="경상남도",
        begin="2026-04-01",
        end="2026-11-30",
    )

    assert _parse_tour50(html)[0].canonical_key == "62c11513845247b57d4d2e48945a6755"


def test_parse_dgtourcard_benefits_reads_city_from_title_when_name_attributes_are_missing() -> None:
    html = (
        '<aside data-trvid="1" data-trvnm="2026-경상남도 고성" data-evtbgndt="2026-06-10" '
        'data-evtenddt="2026-08-31" data-sttsnm="신청접수중"></aside>'
        '<aside data-trvid="2" data-trvnm="반값여행" data-evtbgndt="2026-06-10" '
        'data-evtenddt="2026-08-31" data-sttsnm="신청접수중"></aside>'
    )

    assert [record.city for record in _parse_tour50(html)] == ["고성"]


TOUR50_FIXTURE = Path(__file__).parent / "fixtures" / "dgtourcard_tour50_2026-10-19.html"

# 시군 필터를 없애기 전 코드가 이 페이지에서 읽던 17곳의 수집 키와 지역.
TOUR50_EXISTING_CITIES = {
    "거창": ("19a3ae49235faeb65662989b05e22194", "경남"),
    "고창": ("fe926d5195ae45e2c7a2823605383680", "전북"),
    "고흥": ("125862892526ad279e6acd286bc316b0", "전남"),
    "밀양": ("62c11513845247b57d4d2e48945a6755", "경남"),
    "산청": ("97b1c2e99f04e79f30e197201937630c", "경남"),
    "안동": ("920bda628a04f6be353212f832feaf52", "경북"),
    "영광": ("8b34613b332c0390c699d5cc01a54a36", "전남"),
    "영월": ("2f7ecdf7afd3ee6876f6f80967094fb9", "강원"),
    "완도": ("c6542cfc60d03dc9f4ae9eeed37dc479", "전남"),
    "장흥": ("e49ba3c71992ab43297c32759e30c9a2", "전남"),
    "제천": ("0661e09f2aa592c52eba50198845844b", "충북"),
    "태안": ("2b9a3663a386093cfd3aad59f6e022b0", "충남"),
    "평창": ("3b68cbdbbf0777368255db27747a8ca1", "강원"),
    "하동": ("38f1c3fb9a806ccb2f2aa37759a18ffd", "경남"),
    "함양": ("4048d2b79c64e693427e3e9aa58affd7", "경남"),
    "합천": ("104137cf084a503b750a15eec0f2af7b", "경남"),
    "해남": ("7d1e7ed3cc10dd61ac994e6a9d4c1ef9", "전남"),
}
TOUR50_NEW_CITY_REGIONS = {
    "강진": "전남",
    "고성": "경남",
    "남해": "경남",
    "서천": "충남",
    "영암": "전남",
    "영천": "경북",
    "화천": "강원",
    "횡성": "강원",
}


def test_parse_dgtourcard_benefits_reads_every_card_on_the_official_page() -> None:
    html = TOUR50_FIXTURE.read_text(encoding="utf-8")

    records = _parse_tour50(html)

    # 카드를 읽다 버리면 사이트에 열려 있는 반값여행이 앱에서 조용히 빠진다.
    assert len(records) == html.count('class="cl-posi-detail') == 25
    by_city = {record.city: record for record in records}
    assert len(by_city) == 25
    assert {
        city: (by_city[city].canonical_key, by_city[city].region) for city in TOUR50_EXISTING_CITIES
    } == TOUR50_EXISTING_CITIES
    assert {city: by_city[city].region for city in TOUR50_NEW_CITY_REGIONS} == TOUR50_NEW_CITY_REGIONS
    assert not [city for city in by_city if city.endswith(("시", "군"))]


def test_parse_local_half_trip_detail_fields_reads_participation_target_lines() -> None:
    html = """
    <div id="load_content">
      <div class="msection event-info">
        <div>
          <dl>
            <dt><span>지원내용</span></dt>
            <dd><p>여행비 50% 환급</p></dd>
          </dl>
          <dl>
            <dt><span>참여대상</span></dt>
            <dd>
              <p>강진군 외 지역에 거주하는 사전신청 관광객 누구나</p>
              <p><em>※</em> 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외</p>
            </dd>
          </dl>
        </div>
      </div>
    </div>
    """

    fields = parse_local_half_trip_detail_fields(html)

    assert fields["participantTarget"] == (
        "강진군 외 지역에 거주하는 사전신청 관광객 누구나\n"
        "※ 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외"
    )
    assert fields["supportDetail"] == "여행비 50% 환급"


def test_parse_local_half_trip_detail_fields_reads_yeonggwang_section_rows() -> None:
    html = """
    <div class="main_section_row">
      <span class="main_section_label">참여대상</span>
      <div class="main_section_cont">
        <p>영광 관외 거주 사전신청 관광객 누구나</p>
        <p>제외지역: 함평군, 장성군, 무안군, 고창군</p>
      </div>
    </div>
    <div class="main_section_row">
      <span class="main_section_label">지원내용</span>
      <div class="main_section_cont">
        <p>영광 여행 비용의 최대 50% 모바일 영광사랑상품권 지급</p>
        <p>최대 환급 금액: 2인이상 최대 20만원까지</p>
      </div>
    </div>
    <div class="main_section_row">
      <span class="main_section_label">유의사항</span>
      <div class="main_section_cont">
        <ul><li>신청 대표자 본인명의의 증빙서류만 제출 가능</li></ul>
      </div>
    </div>
    """

    fields = parse_local_half_trip_detail_fields(html)

    assert fields["participantTarget"] == (
        "영광 관외 거주 사전신청 관광객 누구나\n"
        "제외지역: 함평군, 장성군, 무안군, 고창군"
    )
    assert fields["supportDetail"] == (
        "영광 여행 비용의 최대 50% 모바일 영광사랑상품권 지급\n"
        "최대 환급 금액: 2인이상 최대 20만원까지"
    )
    assert fields["detailNotes"] == "신청 대표자 본인명의의 증빙서류만 제출 가능"


def test_enrich_dgtourcard_benefits_with_detail_pages_adds_participant_target() -> None:
    records = parse_dgtourcard_benefits(
        DGTOURCARD_DATA_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        today=date(2026, 6, 16),
    )

    enriched = enrich_dgtourcard_benefits_with_detail_pages(
        records,
        fetch_detail_html=lambda detail_url: """
        <dl>
          <dt>참여대상</dt>
          <dd><p>강진군 외 지역에 거주하는 사전신청 관광객 누구나</p></dd>
        </dl>
        """,
    )

    assert enriched[0].raw_payload["participantTarget"] == "강진군 외 지역에 거주하는 사전신청 관광객 누구나"
    assert enriched[0].field_completeness >= 95
