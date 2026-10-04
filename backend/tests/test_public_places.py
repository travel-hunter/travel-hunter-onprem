"""공공데이터 장소 기반(카카오 운영정책 2단계) - 이름 정규화 · 행 만들기 · 저장소 · 적재 · 맞춰 보기.
DB 는 운영과 같은 autoflush=False 세션의 SQLite 다. 공공데이터 모양은 2026-10-03 에 받은 TourAPI · 상가정보 20260630판과 같다."""

from __future__ import annotations

import csv
import io
import logging
import math
import zipfile
from collections.abc import Iterator
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_optional_db
from app.main import app
from app.models import PublicPlace, User
from app.repositories.public_places import (
    count_public_places,
    count_public_places_by,
    get_sync_state,
    prune_public_places,
    public_places_in_box,
    record_sync_state,
    upsert_public_places,
)
from app.services import public_places
from app.services.public_places import (
    WIDE_RADIUS_M,
    iter_sangga_rows,
    load_sangga_places,
    match_place,
    name_key,
    sangga_row,
    sync_tourapi_places,
    tourapi_row,
    tourapi_sync_due,
)
from app.services.tour_api import TourApiConfigurationError, TourApiPage

SYNCED = datetime(2026, 10, 4, 3, 0)
T1, T2, T3 = datetime(2026, 10, 1, 4, 0), datetime(2026, 10, 8, 4, 0), datetime(2026, 10, 15, 4, 0)


@pytest.fixture
def db() -> Iterator[Session]:
    # TestClient 는 라우트를 다른 스레드에서 돌린다 - 한 연결을 같이 쓰게 StaticPool · check_same_thread=False(기존 라우트 시험과 같다).
    # 운영 세션과 같이 autoflush 를 끈다. 두 표 모두 문자열 키라 sqlite 의 BigInteger 함정이 없다
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
        yield session


def place_row(source: str, source_id: str, name: str, lat: float = 34.7443, lng: float = 127.7663,
              category: str = "food", *, photo: str | None = None, synced_at: datetime = T1, sido: str = "전남") -> dict[str, object]:
    return {
        "source": source, "source_id": source_id, "name": name, "name_key": name_key(name),
        "address": "전남광주통합특별시 여수시 수정동 1", "latitude": lat, "longitude": lng, "category": category,
        "sido": sido, "city": "여수", "photo_url": photo, "photo_license": "Type3" if photo else None, "synced_at": synced_at,
    }


def seed(db: Session, *rows: dict[str, object]) -> None:
    upsert_public_places(db, list(rows))
    db.commit()

ODONGDO = {
    "contentid": "126508", "contenttypeid": "12", "title": "오동도", "addr1": "전남광주통합특별시 여수시 오동도로 222",
    "mapx": "127.7663", "mapy": "34.7443", "firstimage": "http://tong.visitkorea.or.kr/a.jpg", "cpyrhtDivCd": "Type3",
    "cat3": "A01010400",
}

CAFE = {
    "상가업소번호": "MA0101202210A0094848", "상호명": "카페마레", "지점명": "여수점",
    "상권업종대분류코드": "I2", "상권업종중분류코드": "I212", "시도명": "전남광주통합특별시", "시군구명": "여수시",
    "지번주소": "전남광주통합특별시 여수시 수정동 1-1", "도로명주소": "전남광주통합특별시 여수시 오동도로 1",
    "경도": "127.7660", "위도": "34.7440",
}


def test_name_key_drops_case_spaces_and_symbols() -> None:
    assert name_key(" 스타벅스 여수엑스포점 ") == "스타벅스여수엑스포점"
    assert name_key("CAFE (마레)·Bay") == "cafe마레bay"
    assert name_key(None) == ""


def test_tourapi_entry_becomes_a_row_with_region_category_and_photo() -> None:
    assert tourapi_row(ODONGDO, SYNCED) == {
        "source": "tourapi", "source_id": "126508", "name": "오동도", "name_key": "오동도",
        "address": "전남광주통합특별시 여수시 오동도로 222", "latitude": 34.7443, "longitude": 127.7663, "category": "sight",
        "sido": "전남", "city": "여수", "photo_url": "http://tong.visitkorea.or.kr/a.jpg", "photo_license": "Type3",
        "synced_at": SYNCED,
    }


def test_tourapi_cafe_food_and_entries_that_are_not_places() -> None:
    assert tourapi_row({**ODONGDO, "contenttypeid": "39", "cat3": "A05020900"}, SYNCED)["category"] == "cafe"
    assert tourapi_row({**ODONGDO, "contenttypeid": "39", "cat3": ""}, SYNCED)["category"] == "food"
    assert tourapi_row({**ODONGDO, "firstimage": ""}, SYNCED)["photo_license"] is None   # 사진이 없으면 유형도 비운다
    assert tourapi_row({**ODONGDO, "contenttypeid": "25"}, SYNCED) is None   # 여행코스는 장소가 아니다
    assert tourapi_row({**ODONGDO, "contentid": ""}, SYNCED) is None
    assert tourapi_row({**ODONGDO, "mapx": ""}, SYNCED) is None
    assert tourapi_row({**ODONGDO, "mapy": "0"}, SYNCED) is None   # 좌표 0 은 한국 밖


def test_sangga_row_joins_the_branch_and_keeps_only_travel_categories() -> None:
    row = sangga_row(CAFE, SYNCED)
    assert row == {
        "source": "sangga", "source_id": "MA0101202210A0094848", "name": "카페마레 여수점", "name_key": "카페마레여수점",
        "address": "전남광주통합특별시 여수시 오동도로 1", "latitude": 34.744, "longitude": 127.766, "category": "cafe",
        "sido": "전남", "city": "여수", "photo_url": None, "photo_license": None, "synced_at": SYNCED,
    }
    assert sangga_row({**CAFE, "상권업종중분류코드": "I201"}, SYNCED)["category"] == "food"
    assert sangga_row({**CAFE, "상권업종대분류코드": "I1", "상권업종중분류코드": "I101"}, SYNCED)["category"] == "stay"
    assert sangga_row({**CAFE, "상권업종대분류코드": "R1", "상권업종중분류코드": "R102"}, SYNCED)["category"] == "culture"
    assert sangga_row({**CAFE, "상권업종대분류코드": "R1", "상권업종중분류코드": "R104"}, SYNCED)["category"] == "leisure"
    assert sangga_row({**CAFE, "상권업종대분류코드": "G2"}, SYNCED) is None   # 소매는 넣지 않는다
    assert sangga_row({**CAFE, "위도": ""}, SYNCED) is None
    assert sangga_row({**CAFE, "지점명": ""}, SYNCED)["name"] == "카페마레"
    assert sangga_row({**CAFE, "도로명주소": ""}, SYNCED)["address"] == "전남광주통합특별시 여수시 수정동 1-1"


def test_upsert_keeps_one_row_per_key_and_the_later_value_wins(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "오동도", synced_at=T1))
    # 같은 열쇠가 한 묶음에 두 번 - Postgres 는 거부하므로 뒤의 것만 쓴다
    written = upsert_public_places(db, [place_row("tourapi", "1", "오동도 등대", synced_at=T2), place_row("tourapi", "1", "오동도", synced_at=T2)])
    db.commit()
    assert written == 1
    rows = db.scalars(select(PublicPlace)).all()
    assert [(row.source_id, row.name, row.synced_at) for row in rows] == [("1", "오동도", T2)]


def test_counts_by_category_or_province_and_since_a_time(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "a", category="sight", synced_at=T1), place_row("tourapi", "2", "b", category="food", synced_at=T2),
         place_row("sangga", "S", "c", synced_at=T2, sido="세종"))
    assert count_public_places_by(db, source="tourapi", column="category") == {"sight": 1, "food": 1}
    assert count_public_places_by(db, source="tourapi", column="category", since=T2) == {"food": 1}
    assert count_public_places_by(db, source="sangga", column="sido") == {"세종": 1}
    assert count_public_places(db, source="tourapi") == 2


def test_prune_removes_only_older_rows_of_the_units_that_passed(db: Session) -> None:
    seed(db, place_row("tourapi", "old-sight", "a", category="sight", synced_at=T1),
         place_row("tourapi", "old-food", "b", category="food", synced_at=T1),
         place_row("tourapi", "new", "c", category="sight", synced_at=T2),
         place_row("sangga", "Y", "d", synced_at=T1), place_row("sangga", "S", "e", synced_at=T1, sido="세종"))
    assert prune_public_places(db, source="tourapi", synced_before=T2, categories=["sight"]) == 1   # 음식점 유형은 통과하지 못했다
    assert prune_public_places(db, source="sangga", synced_before=T2, sidos=["전남"]) == 1   # 세종은 통과하지 못했다
    assert prune_public_places(db, source="sangga", synced_before=T2, sidos=[]) == 0
    db.commit()
    assert {row.source_id for row in db.scalars(select(PublicPlace))} == {"old-food", "new", "S"}


def test_sync_state_keeps_the_last_success_through_running_partial_and_error(db: Session) -> None:
    record_sync_state(db, source="tourapi", attempted_at=T1, outcome="running")
    record_sync_state(db, source="tourapi", attempted_at=T1, outcome="success", received=10, written=10)
    record_sync_state(db, source="tourapi", attempted_at=T2, outcome="running")
    record_sync_state(db, source="tourapi", attempted_at=T2, outcome="partial", received=5, written=5)
    record_sync_state(db, source="tourapi", attempted_at=T3, outcome="error", error="x" * 400)
    db.commit()
    state = get_sync_state(db, source="tourapi")
    assert (state.last_outcome, state.last_attempt_at, state.last_success_at, len(state.last_error)) == ("error", T3, T1, 300)
    assert get_sync_state(db, source="sangga") is None


def test_box_query_returns_only_places_inside_the_bounds(db: Session) -> None:
    seed(db, place_row("tourapi", "in", "a", 34.7443, 127.7663), place_row("tourapi", "north", "b", 34.80, 127.7663),
         place_row("sangga", "east", "c", 34.7443, 127.80))
    found = public_places_in_box(db, south=34.74, north=34.75, west=127.76, east=127.77)
    assert [row.source_id for row in found] == ["in"]


class FakeTourPages:
    """TourAPI 전국 목록 - 유형마다 항목을 rows 개씩 자른다. totals 로 totalCount 를 바꾸고, fail_at 페이지에서 실패한다."""

    def __init__(self, per_type: dict[str, list[dict[str, str]]], *, totals: dict[str, int] | None = None,
                 fail_at: tuple[str, int] | None = None) -> None:
        self.per_type, self.totals, self.fail_at = per_type, totals or {}, fail_at
        self.calls: list[tuple[str, int]] = []

    def list_area_based_page(self, *, content_type_id: str, page: int, rows: int, timeout: float | None = None) -> TourApiPage:
        self.calls.append((content_type_id, page))
        if (content_type_id, page) == self.fail_at:
            raise TourApiConfigurationError("TourAPI request failed (HTTP 500).")
        items = self.per_type.get(content_type_id, [])
        return TourApiPage(items[(page - 1) * rows: page * rows], self.totals.get(content_type_id, len(items)))


def tour_entry(content_id: str, title: str, content_type: str = "12") -> dict[str, str]:
    return {"contentid": content_id, "contenttypeid": content_type, "title": title, "addr1": "전남광주통합특별시 여수시 1",
            "mapx": "127.7663", "mapy": "34.7443"}


TEN = [tour_entry(str(n), f"장소{n}") for n in range(10)]


def test_tourapi_sync_reads_every_page_the_total_count_promises(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    pages = FakeTourPages({"12": TEN[:7], "39": [tour_entry("90", "식당", "39")]})
    result = sync_tourapi_places(db, pages, now=T1)
    assert (result.received_count, result.parsed_count, result.outcome) == (8, 8, "success")
    assert [call for call in pages.calls if call[0] == "12"] == [("12", 1), ("12", 2), ("12", 3)]   # 7건 = 3 + 3 + 1
    assert {call[0] for call in pages.calls} == set(public_places.TOURAPI_CONTENT_TYPES)
    assert get_sync_state(db, source="tourapi").last_success_at == T1


def test_tourapi_sync_prunes_a_type_only_after_reading_it_completely(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    gone = sync_tourapi_places(db, FakeTourPages({"12": TEN[:9]}), now=T2)   # 하나가 사라졌다(totalCount 9)
    assert (gone.pruned_count, gone.outcome) == (1, "success")
    short = sync_tourapi_places(db, FakeTourPages({"12": TEN[:5]}, totals={"12": 9}), now=T3)   # 9건이라더니 5건만 왔다
    assert (short.pruned_count, short.outcome) == (0, "partial")
    assert count_public_places(db, source="tourapi") == 9
    assert get_sync_state(db, source="tourapi").last_success_at == T2   # 일부는 성공 시각을 바꾸지 않는다


def test_a_type_that_suddenly_comes_back_empty_keeps_its_rows(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    food = [tour_entry(f"F{n}", f"식당{n}", "39") for n in range(2)]
    sync_tourapi_places(db, FakeTourPages({"12": TEN, "39": food}), now=T1)
    # 다음 주 음식점 유형이 0건으로 왔다 - 관광지는 다 왔고 전체로는 10/12(83%)지만 음식점 행은 지우지 않는다
    result = sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T2)
    assert (result.pruned_count, result.outcome) == (0, "partial")
    assert count_public_places(db, source="tourapi") == 12


def test_a_repeated_page_is_an_incomplete_read_even_across_batch_edges(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    monkeypatch.setattr(public_places, "UPSERT_BATCH", 2)   # 같은 ID 가 묶음 경계를 넘어 다시 온다
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    shifted = TEN[:3] + TEN[:3] + TEN[6:]   # 둘째 페이지가 첫 페이지와 같다(순서가 밀림) - 10건이 왔지만 고유 7곳
    result = sync_tourapi_places(db, FakeTourPages({"12": shifted}), now=T2)
    assert (result.received_count, result.parsed_count, result.pruned_count, result.outcome) == (10, 7, 0, "partial")
    assert count_public_places(db, source="tourapi") == 10


def test_a_failure_after_good_pages_deletes_nothing_and_is_recorded(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    with pytest.raises(TourApiConfigurationError):
        sync_tourapi_places(db, FakeTourPages({"12": TEN[:9]}, fail_at=("12", 3)), now=T2)   # 앞 두 페이지는 왔다
    assert count_public_places(db, source="tourapi") == 10   # 지운 것 없음
    state = get_sync_state(db, source="tourapi")
    assert (state.last_outcome, state.last_success_at, state.received_count, state.last_error) == (
        "error", T1, 6, "TourAPI request failed (HTTP 500).",
    )


def test_an_interrupted_run_still_counts_as_todays_attempt(db: Session) -> None:
    class Crash(BaseException):
        pass

    class Dying(FakeTourPages):
        def list_area_based_page(self, **_kwargs) -> TourApiPage:
            raise Crash()   # 프로세스가 죽은 것처럼 - except Exception 이 잡지 않는다

    with pytest.raises(Crash):
        sync_tourapi_places(db, Dying({}), now=T1)
    db.rollback()
    state = get_sync_state(db, source="tourapi")
    assert (state.last_attempt_at, state.last_outcome) == (T1, "running")   # 첫 호출 전에 남겼다


def test_an_operator_can_accept_a_real_shrink_of_a_fully_read_type(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    shrunk = sync_tourapi_places(db, FakeTourPages({"12": TEN[:5]}), now=T2)   # 관광공사 총수도 5 - 끝까지 받았지만 절반
    assert (shrunk.pruned_count, shrunk.outcome, shrunk.kept) == (0, "partial", ("12:10->5",))   # 운영자가 보는 한 줄
    # 운영자가 관광공사 쪽에서 정말 줄었다고 확인하고 받아들인다 - 80% 기준만 그 유형에서 끈다
    accepted = sync_tourapi_places(db, FakeTourPages({"12": TEN[:5]}), now=T3, accept_shrink={"12"})
    assert (accepted.pruned_count, accepted.outcome, accepted.kept) == (5, "success", ())
    assert count_public_places(db, source="tourapi") == 5
    # 끝까지 받지 못한 유형은 받아들여도 지우지 않는다
    short = sync_tourapi_places(db, FakeTourPages({"12": TEN[:2]}, totals={"12": 5}), now=T3 + timedelta(days=7), accept_shrink={"12"})
    assert (short.pruned_count, short.outcome, short.kept) == (0, "partial", ("12:incomplete",))
    assert count_public_places(db, source="tourapi") == 5


def test_a_sync_that_writes_nothing_is_partial_not_success(db: Session) -> None:
    result = sync_tourapi_places(db, FakeTourPages({}), now=T1)
    assert (result.parsed_count, result.pruned_count, result.outcome) == (0, 0, "partial")


def test_automatic_sync_runs_once_a_day_after_run_at_and_weekly_after_a_success(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    run_at = time(4, 0)
    morning = datetime(2026, 9, 30, 19, 30)   # UTC - KST 10/1 04:30
    assert tourapi_sync_due(db, now=morning - timedelta(hours=1), run_at=run_at) is False   # KST 03:30 - 아직 이르다
    assert tourapi_sync_due(db, now=morning, run_at=run_at) is True
    with pytest.raises(TourApiConfigurationError):
        sync_tourapi_places(db, FakeTourPages({}, fail_at=("12", 1)), now=morning)
    assert tourapi_sync_due(db, now=morning + timedelta(hours=3), run_at=run_at) is False   # 오늘 이미 시도 - 재기동해도 같다
    next_morning = morning + timedelta(days=1)
    assert tourapi_sync_due(db, now=next_morning, run_at=run_at) is True   # 실패 다음 날 다시
    sync_tourapi_places(db, FakeTourPages({"12": TEN[:1]}), now=next_morning)
    assert tourapi_sync_due(db, now=next_morning + timedelta(days=6), run_at=run_at) is False   # 성공 뒤 7일 안
    assert tourapi_sync_due(db, now=next_morning + timedelta(days=7), run_at=run_at) is True


SANGGA_FIELDS = ["상가업소번호", "상호명", "지점명", "상권업종대분류코드", "상권업종중분류코드", "시도명", "시군구명", "지번주소", "도로명주소", "경도", "위도"]


def store(store_id: str, name: str, major: str = "I2", middle: str = "I201", lat: str = "34.7440") -> dict[str, str]:
    return {**CAFE, "상가업소번호": store_id, "상호명": name, "지점명": "", "상권업종대분류코드": major, "상권업종중분류코드": middle, "위도": lat}


def sejong(store_id: str, name: str, major: str = "I2") -> dict[str, str]:
    return {**store(store_id, name, major), "시도명": "세종특별자치시", "시군구명": "세종특별자치시"}


def write_zip(tmp_path: Path, members: dict[str, list[dict[str, str]]]) -> Path:
    path = tmp_path / "sangga.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for member, rows in members.items():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=SANGGA_FIELDS)
            writer.writeheader()
            writer.writerows([{field: row.get(field, "") for field in SANGGA_FIELDS} for row in rows])
            archive.writestr(member, buffer.getvalue().encode("utf-8-sig"))   # 20260630판과 같은 BOM 붙은 UTF-8
    return path


def test_sangga_zip_is_read_row_by_row_and_only_filters_member_files(tmp_path: Path) -> None:
    path = write_zip(tmp_path, {
        "소상공인시장진흥공단_상가(상권)정보_세종_202606.csv": [sejong("A", "세종식당")],
        "소상공인시장진흥공단_상가(상권)정보_전남광주_202606.csv": [store("B", "여수식당"), store("C", "여수마트", "G2", "G204")],
        "readme.txt": [],
    })
    assert [row["상가업소번호"] for row in iter_sangga_rows([path])] == ["A", "B", "C"]
    assert [row["상가업소번호"] for row in iter_sangga_rows([path], only="세종")] == ["A"]


def test_sangga_load_keeps_travel_rows_and_only_full_loads_prune(db: Session) -> None:
    rows = [store(f"S{n}", f"식당{n}") for n in range(10)] + [store("M", "마트", "G2", "G204"), store("X", "좌표없음", lat="")]
    first = load_sangga_places(db, iter(rows), now=T1)
    assert (first.received_count, first.parsed_count, first.skipped_count, first.outcome) == (12, 10, 2, "success")
    partial = load_sangga_places(db, iter(rows[:1]), now=T2, prune=False)   # --only 처럼 일부만 - 다른 행을 지우지 않는다
    assert (partial.pruned_count, partial.outcome) == (0, "partial")
    full = load_sangga_places(db, iter(rows[:9]), now=T3)   # 새 판에서 하나가 문을 닫았다
    assert (full.pruned_count, full.outcome) == (1, "success")
    assert count_public_places(db, source="sangga") == 9


def test_a_province_missing_from_the_file_is_kept_and_the_load_is_partial(db: Session) -> None:
    yeosu = [store(f"Y{n}", f"여수식당{n}") for n in range(20)]
    assert load_sangga_places(db, iter(yeosu + [sejong("S0", "세종식당0"), sejong("S1", "세종식당1")]), now=T1).outcome == "success"
    # 새 판에서 여수 가게 하나가 문을 닫았고 세종 파일이 빠졌다 - 전남은 지우고, 세종은 남기고, 판이 덜 왔으니 partial
    full = load_sangga_places(db, iter(yeosu[:19]), now=T2)
    assert (full.pruned_count, full.outcome) == (1, "partial")
    assert {row.source_id for row in db.scalars(select(PublicPlace).where(PublicPlace.sido == "세종"))} == {"S0", "S1"}


def test_a_province_that_shrinks_sharply_keeps_its_rows(db: Session) -> None:
    yeosu = [store(f"Y{n}", f"여수식당{n}") for n in range(10)]
    sejongs = [sejong(f"S{n}", f"세종식당{n}") for n in range(10)]
    load_sangga_places(db, iter(yeosu + sejongs), now=T1)
    # 새 판에서 세종이 10 → 1 곳으로 줄었다 - 전체로는 11/20 이지만 시도마다 본다
    shrunk = load_sangga_places(db, iter(yeosu + sejongs[:1]), now=T2)
    assert (shrunk.pruned_count, shrunk.outcome) == (0, "partial")
    # 세종 줄이 소매뿐이어도(여행 업종 0건) 읽은 시도로 센다 - 0건이 된 시도도 지우지 않는다
    emptied = load_sangga_places(db, iter(yeosu + [sejong("M", "세종마트", "G2")]), now=T3)
    assert (emptied.pruned_count, emptied.outcome) == (0, "partial")
    assert count_public_places(db, source="sangga") == 20


def test_an_operator_can_accept_a_real_shrink_of_a_province(db: Session) -> None:
    yeosu = [store(f"Y{n}", f"여수식당{n}") for n in range(10)]
    sejongs = [sejong(f"S{n}", f"세종식당{n}") for n in range(10)]
    load_sangga_places(db, iter(yeosu + sejongs), now=T1)
    shrunk = load_sangga_places(db, iter(yeosu + sejongs[:1]), now=T2)
    assert (shrunk.pruned_count, shrunk.outcome, shrunk.kept) == (0, "partial", ("세종:10->1",))   # 운영자가 보는 한 줄
    # 운영자가 새 판에서 세종이 정말 줄었다고 확인하고 받아들인다 - 80% 기준만 그 시도에서 끈다
    accepted = load_sangga_places(db, iter(yeosu + sejongs[:1]), now=T3, accept_shrink={"세종"})
    assert (accepted.pruned_count, accepted.outcome, accepted.kept) == (9, "success", ())
    # 파일이 빠진 시도는 받아들여도 지우지 않는다 - 끝까지 읽었다는 증거가 없다
    missing = load_sangga_places(db, iter(yeosu), now=T3 + timedelta(days=7), accept_shrink={"세종"})
    assert (missing.pruned_count, missing.outcome, missing.kept) == (0, "partial", ("세종:missing",))


def test_the_same_store_in_two_files_is_counted_once(db: Session, tmp_path: Path) -> None:
    path = write_zip(tmp_path, {"a_세종_202606.csv": [sejong("A", "가게")], "b_세종_202606.csv": [sejong("A", "가게")]})
    result = load_sangga_places(db, iter_sangga_rows([path]), now=T1)
    assert (result.received_count, result.parsed_count) == (2, 1)


def test_a_sangga_load_that_breaks_midway_keeps_written_batches_and_deletes_nothing(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "UPSERT_BATCH", 2)
    seed(db, place_row("sangga", "OLD", "예전가게", synced_at=T1))

    def broken() -> Iterator[dict[str, str]]:
        yield store("S1", "식당1")
        yield store("S2", "식당2")
        yield store("S3", "식당3")
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")   # 판이 바뀌어 인코딩이 다른 파일

    with pytest.raises(UnicodeDecodeError):
        load_sangga_places(db, broken(), now=T2)
    assert {row.source_id for row in db.scalars(select(PublicPlace))} == {"OLD", "S1", "S2"}   # 넣은 한 묶음만, 지운 것 없음
    state = get_sync_state(db, source="sangga")
    assert (state.last_outcome, state.received_count, state.last_error) == ("error", 3, "UnicodeDecodeError")


def test_one_same_named_place_of_a_fitting_kind_is_a_match(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "오동도", 34.7443, 127.7663, "sight"))
    found = match_place(db, name="오동도 ", latitude=34.7450, longitude=127.7670, category_code="AT4")
    assert found.result == "match"
    assert [place.source_id for place, _ in found.places] == ["1"]


def test_the_same_name_in_both_sources_asks_instead_of_guessing(db: Session) -> None:
    # TourAPI 와 상가정보가 약 48m 떨어져 같은 이름 - 같은 곳이라 단정하지 않는다(가까운 순 후보)
    seed(db, place_row("tourapi", "1", "오동도", 34.7443, 127.7663, "sight"), place_row("sangga", "S1", "오동도", 34.7447, 127.7665, "leisure"))
    found = match_place(db, name="오동도", latitude=34.7450, longitude=127.7670, category_code="AT4")
    assert found.result == "candidates"
    assert [place.source_id for place, _ in found.places] == ["S1", "1"]   # 약 57m · 101m


def test_a_same_named_place_of_another_or_unknown_kind_is_only_a_candidate(db: Session) -> None:
    seed(db, place_row("sangga", "S", "바다정원", 34.7443, 127.7663, "stay"))
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="CE7").result == "candidates"
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="AD5").result == "match"
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code=None).result == "candidates"   # 분류를 모르면 맞는지 알 수 없다
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="MT1").result == "candidates"   # 표에 없는 코드


def test_two_shops_with_the_same_name_ask_which_one(db: Session) -> None:
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663), place_row("sangga", "B", "이디야커피", 34.7455, 127.7663))
    found = match_place(db, name="이디야 커피", latitude=34.7449, longitude=127.7663, category_code="CE7")
    assert found.result == "candidates"
    assert {place.source_id for place, _ in found.places} == {"A", "B"}


def test_radius_is_1km_for_tourapi_sights_and_200m_otherwise_and_for_sangga(db: Session) -> None:
    far = 34.7443 + 0.006   # 약 667m 북쪽
    seed(db, place_row("tourapi", "T", "향일암", far, 127.7663, "sight"), place_row("sangga", "S", "향일암", far, 127.7663))
    sight = match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="AT4")
    assert sight.result == "match" and [place.source for place, _ in sight.places] == ["tourapi"]   # 상가정보는 200m 밖
    assert match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="FD6").result == "none"


def test_places_just_inside_the_radius_are_not_lost_at_the_box_edge(db: Session) -> None:
    step = (WIDE_RADIUS_M - 1) / (6_371_000 * math.pi / 180)   # 거리 함수 기준 정북 999m
    seed(db, place_row("tourapi", "T", "향일암", 34.7443 + step, 127.7663, "sight"))
    assert match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="AT4").result == "match"


def test_a_partial_name_gives_up_to_three_candidates_nearest_first(db: Session) -> None:
    seed(db, *[place_row("sangga", f"S{n}", f"오동도횟집{n}", 34.7443 + n * 0.0002, 127.7663) for n in range(5)])
    found = match_place(db, name="오동도", latitude=34.7443, longitude=127.7663, category_code="FD6")
    assert found.result == "candidates"
    assert [place.source_id for place, _ in found.places] == ["S0", "S1", "S2"]


def test_one_letter_and_symbol_only_names_never_match_loosely(db: Session) -> None:
    seed(db, place_row("sangga", "S", "섬마을", 34.7443, 127.7663))
    assert match_place(db, name="섬", latitude=34.7443, longitude=127.7663, category_code=None).result == "none"
    assert match_place(db, name=" - · ", latitude=34.7443, longitude=127.7663, category_code=None).result == "none"


USER = User(id=1, email="u@example.com", nickname="u", onboarding_completed=True,
            created_at=datetime(2026, 10, 4), updated_at=datetime(2026, 10, 4))


def test_match_route_needs_login_and_answers_in_camel_case(db: Session) -> None:
    seed(db, place_row("tourapi", "126508", "오동도", 34.7443, 127.7663, "sight", photo="http://tong.visitkorea.or.kr/a.jpg"))
    client = TestClient(app)
    app.dependency_overrides[get_optional_db] = lambda: db
    try:
        anonymous = client.post("/api/places/match", json={"name": "오동도", "latitude": 34.7443, "longitude": 127.7663})
        app.dependency_overrides[get_current_user] = lambda: USER
        found = client.post("/api/places/match", json={"name": "오동도", "latitude": 34.7443, "longitude": 127.7663, "categoryCode": "AT4"})
        outside = client.post("/api/places/match", json={"name": "오동도", "latitude": 10.0, "longitude": 127.7663})
    finally:
        app.dependency_overrides.pop(get_optional_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert anonymous.status_code == 401
    assert found.status_code == 200
    assert found.json() == {"result": "match", "places": [{
        "source": "tourapi", "sourceId": "126508", "name": "오동도", "address": "전남광주통합특별시 여수시 수정동 1",
        "latitude": 34.7443, "longitude": 127.7663, "category": "sight", "sido": "전남", "city": "여수",
        "photoUrl": "http://tong.visitkorea.or.kr/a.jpg", "photoLicense": "Type3", "distanceMeters": 0,
    }]}
    assert outside.status_code == 422


def test_match_never_writes_or_logs_the_values_it_received(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client = TestClient(app)
    app.dependency_overrides[get_optional_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = client.post("/api/places/match", json={"name": "카카오에서온가게이름", "latitude": 34.7443, "longitude": 127.7663})
    finally:
        app.dependency_overrides.pop(get_optional_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert response.json() == {"result": "none", "places": []}
    assert "카카오에서온가게이름" not in caplog.text
    assert db.scalar(select(func.count()).select_from(PublicPlace)) == 0
