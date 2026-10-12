"""장소 검색 완성 검색어 - 순위 함수(순수, 0.3 ②~⑬)와 서비스(입력 거름 · 오류 처리 · 로그).
순위 함수는 DB 없이 후보 행을 직접 넣어 시험한다. 서비스 시험만 운영과 같이 autoflush 를 끈 SQLite 를 쓴다."""

from __future__ import annotations

import logging
import random
import time
from collections import Counter
from collections.abc import Iterator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.repositories.public_places import SuggestCandidate, upsert_public_places
from app.services import place_suggest
from app.services.place_suggest import rank_suggestions, suggest_place_names

SYNCED = datetime(2026, 10, 12, 4, 0)


def cand(name: str, *, source: str = "tourapi", category: str = "sight", sido: str | None = "전남",
         city: str | None = "담양", tier: int = 0, count: int = 1) -> SuggestCandidate:
    return SuggestCandidate(name=name, source=source, category=category, sido=sido, city=city, tier=tier, count=count)


def shop(name: str, *, category: str = "food", sido: str | None = "서울", city: str | None = "강남", count: int = 1) -> SuggestCandidate:
    return cand(name, source="sangga", category=category, sido=sido, city=city, count=count)


# ---------------------------------------------------------------- ② 지역 안이 먼저

def test_inside_the_area_comes_before_outside_even_when_the_outside_line_is_heavier() -> None:
    rows = [cand("곡성 메타세쿼이아길", city="곡성", tier=1, count=9), cand("담양 메타세쿼이아길")]
    assert rank_suggestions("메타세쿼", rows, scope=("전남", ("담양",))) == ["담양 메타세쿼이아길", "곡성 메타세쿼이아길"]


# ---------------------------------------------------------------- ③ 꼬리표 · core

def test_bracket_and_parenthesis_tails_are_dropped_unless_that_removes_the_query() -> None:
    assert rank_suggestions("불국", [cand("경주 불국사 [유네스코 세계유산]", sido="경북", city="경주")], scope=("경북", ("경주",))) == ["경주 불국사"]
    # 떼면 검색어(남산)가 사라지는 이름은 원래 이름 그대로
    assert rank_suggestions("남산", [cand("목멱산(남산)", sido="서울", city="중구")], scope=("서울", None)) == ["목멱산(남산)"]


def test_core_drops_the_rows_own_region_names_repeatedly_and_only_with_a_sido() -> None:
    rows = [
        cand("담양 메타세쿼이아길", city="담양"),
        cand("곡성 메타세쿼이아길", city="곡성"),
        cand("김제 메타세쿼이아길", sido=None, city="죽산면"),
    ]
    # 시도가 없으면 core 를 만들지 않아 다른 '… 메타세쿼이아길' 과 합쳐지지 않는다
    assert rank_suggestions("메타세쿼", rows, scope=None) == ["메타세쿼이아길", "김제 메타세쿼이아길"]
    hanok = [
        cand("전주한옥마을", sido="전북", city="전주"),
        cand("전북 전주 한옥마을", sido="전북", city="전주"),   # 시도 · 시군이 되풀이해 붙어도 다 뗀다
        cand("남원 한옥마을", sido="전북", city="남원"),
    ]
    assert rank_suggestions("한옥", hanok, scope=None) == ["한옥마을"]


# ---------------------------------------------------------------- ⑤ 지역 밖 · 지역 없음 합치기

def test_regionless_lines_that_differ_only_by_region_become_one_line() -> None:
    rows = [cand("곡성 메타세쿼이아길", city="곡성"), cand("담양 메타세쿼이아길", city="담양")]
    assert rank_suggestions("메타세쿼", rows, scope=None) == ["메타세쿼이아길"]


def test_outside_lines_merge_but_the_inside_line_keeps_its_region_name() -> None:
    rows = [
        cand("담양 메타세쿼이아길", city="담양"),
        cand("곡성 메타세쿼이아길", city="곡성", tier=1),
        cand("보성 메타세쿼이아길", city="보성", tier=1),
    ]
    assert rank_suggestions("메타세쿼", rows, scope=("전남", ("담양",))) == ["담양 메타세쿼이아길", "메타세쿼이아길"]
    # 지역 안 줄끼리는 핵심 이름이 같아도 합치지 않는다(시군 이름이 곧 구분이다)
    inside = [cand("담양 메타세쿼이아길", city="담양"), cand("곡성 메타세쿼이아길", city="곡성")]
    assert rank_suggestions("메타세쿼", inside, scope=("전남", ("담양", "곡성"))) == ["곡성 메타세쿼이아길", "담양 메타세쿼이아길"]


# ---------------------------------------------------------------- ⑧ 어절 줄

def test_a_first_word_shared_by_two_inside_sights_becomes_a_line_above_them() -> None:
    rows = [cand("오동도 유람선터미널", city="여수"), cand("오동도 등대", city="여수")]
    assert rank_suggestions("오동", rows, scope=("전남", ("여수",))) == ["오동도", "오동도 등대", "오동도 유람선터미널"]


def test_the_key_word_is_the_first_word_of_the_shown_name_when_it_starts_with_the_input() -> None:
    # 시군 이름을 뗀 core(동백섬)가 아니라 보이는 말의 첫 어절(해운대)이 열쇠다
    rows = [cand("해운대 동백섬", sido="부산", city="해운대"), cand("해운대 아쿠아리움", sido="부산", city="해운대")]
    assert rank_suggestions("해운", rows, scope=("부산", ("해운대",))) == ["해운대", "해운대 동백섬", "해운대 아쿠아리움"]


def test_no_word_line_when_the_word_is_the_input_itself_or_does_not_start_with_it() -> None:
    nam = [cand("경주 남산", sido="경북", city="경주"), cand("남산 화강암", sido="경북", city="경주"), cand("남산 삼층석탑", sido="경북", city="경주")]
    assert rank_suggestions("남산", nam, scope=("경북", ("경주",))) == ["경주 남산", "남산 화강암", "남산 삼층석탑"]
    # q=케이블 이면 열쇠 어절 '해상케이블카' 는 q 로 시작하지 않아 어절 줄이 없다
    cable = [cand("여수 해상케이블카", city="여수"), cand("순천 해상케이블카", city="순천")]
    assert rank_suggestions("케이블", cable, scope=("전남", ("여수", "순천"))) == ["순천 해상케이블카", "여수 해상케이블카"]


# ---------------------------------------------------------------- ⑨ 체인

def test_a_brand_with_two_shops_folds_into_one_brand_and_region_line() -> None:
    rows = [shop("스타벅스 강남역점"), shop("스타벅스 홍대점", city="마포")]
    assert rank_suggestions("스타", rows, scope=("서울", None)) == ["스타벅스 서울"]


def test_chains_fold_per_city_in_a_multi_city_area() -> None:
    rows = [
        shop("스타벅스 강릉점", sido="강원", city="강릉"), shop("스타벅스 교동점", sido="강원", city="강릉"),
        shop("스타벅스 동해점", sido="강원", city="동해"), shop("스타벅스 천곡점", sido="강원", city="동해"),
    ]
    assert rank_suggestions("스타", rows, scope=("강원", ("강릉", "동해", "삼척"))) == ["스타벅스 강릉", "스타벅스 동해"]


def test_a_chain_without_an_area_is_the_bare_brand_and_a_single_shop_is_not_folded() -> None:
    rows = [cand("스타벅스 강릉점", category="food", sido="강원", city="강릉"), cand("스타벅스 동해점", category="food", sido="강원", city="동해")]
    assert rank_suggestions("스타", rows, scope=None) == ["스타벅스"]
    assert rank_suggestions("스타", [shop("스타벅스 강남역점")], scope=("서울", None)) == ["스타벅스 강남역점"]


def test_a_brand_equal_to_an_inside_sight_core_is_not_folded() -> None:
    rows = [
        cand("경복궁", sido="서울", city="종로"), shop("경복궁 삼계탕", city="종로"), shop("경복궁 떡집", city="종로"),
    ]
    assert rank_suggestions("경복", rows, scope=("서울", None)) == ["경복궁", "경복궁 떡집", "경복궁 삼계탕"]


def test_a_brand_equal_to_a_word_line_is_not_folded_either() -> None:
    sights = [cand("오동도 등대", city="여수"), cand("오동도 유람선터미널", city="여수")]
    shops = [shop("오동도 횟집", sido="전남", city="여수"), shop("오동도 분식", sido="전남", city="여수")]
    assert rank_suggestions("오동", sights + shops, scope=("전남", ("여수",))) == [
        "오동도", "오동도 등대", "오동도 유람선터미널", "오동도 분식", "오동도 횟집",
    ]


def test_a_brand_written_with_a_branch_stuck_on_joins_the_bigger_brand() -> None:
    rows = [shop("롯데리아용인"), shop("롯데리아 강남점"), shop("롯데리아 홍대점", city="마포")]
    assert rank_suggestions("롯데", rows, scope=("서울", None)) == ["롯데리아 서울"]


# ---------------------------------------------------------------- ⑩ 합치기

def test_the_line_equal_to_the_input_is_left_out_and_the_same_text_is_one_line() -> None:
    assert rank_suggestions("오동도", [cand("오동도", city="여수"), cand("오동도 등대", city="여수")], scope=("전남", ("여수",))) == ["오동도 등대"]
    rows = [
        cand("중앙공원", sido="부산", city="중구", tier=1),
        cand("서울숲공원", sido="서울", city="성동"),
        cand("중앙공원", sido="서울", city="중구"),
    ]
    # 같은 말이 지역 안 · 밖에 다 있으면 지역 안 줄이 남는다(안쪽 줄이 앞 순서)
    assert rank_suggestions("공원", rows, scope=("서울", None)) == ["중앙공원", "서울숲공원"]


def test_at_most_six_lines() -> None:
    rows = [cand(f"가나다{index}", city=None) for index in range(9)]
    assert len(rank_suggestions("가나다", rows, scope=("전남", None))) == 6


# ---------------------------------------------------------------- ⑪ 무게

def test_a_non_sight_tourapi_line_weighs_its_first_word_across_the_inside_rows() -> None:
    # '스타필드' 낱말이 안쪽 행에 3번(자기 이름 + 두 곳) -> 무게 3, 상가 2행짜리 '스타일'(2)보다 위
    rows = [
        cand("스타필드 코엑스몰", category="shopping", sido="서울", city="강남"),
        shop("별마당 스타필드"), shop("메가박스 스타필드"),
        shop("스타일", category="food"), shop("스타일", category="cafe"),
    ]
    assert rank_suggestions("스타", rows, scope=("서울", None)) == ["스타필드 코엑스몰", "스타일", "별마당 스타필드", "메가박스 스타필드"]


def test_a_first_word_equal_to_the_input_adds_no_word_weight() -> None:
    # '호텔' 낱말이 안쪽 행에 3번 있어도 첫 어절이 q 와 같으면 어절 수를 세지 않아 무게 = 행 수(1)
    rows = [
        cand("호텔 농심", category="stay", sido="부산", city="동래"),
        shop("호텔 가", category="stay", sido="부산", city="동래"), shop("호텔 나", category="stay", sido="부산", city="동래"),
        shop("호텔마레", category="stay", sido="부산", city="동래", count=2),
    ]
    assert rank_suggestions("호텔", rows, scope=("부산", None)) == ["호텔마레", "호텔 가", "호텔 나", "호텔 농심"]


@pytest.mark.parametrize("many", [False, True])   # 핵심 이름이 HUB_INDEX_MIN_CORES 이하면 그냥 훑고, 넘으면 2글자 조각 색인을 쓴다
def test_hub_counts_equal_a_plain_scan_over_the_inside_names(many: bool) -> None:
    rng = random.Random(7)
    syllables = "가나다라마바"
    inside = Counter({"".join(rng.choices(syllables, k=rng.randint(1, 6))): rng.randint(1, 3) for _ in range(300)})
    cores = {"가", "가 나", "힣힣", next(iter(inside))}   # 한 글자 · 어느 이름에도 없는 말 · 이름 통째
    while many and len(cores) < 60:
        name = rng.choice(list(inside))
        start = rng.randrange(len(name))
        cores.add(name[start:start + rng.randint(1, 4)])
    assert (len(cores) > place_suggest.HUB_INDEX_MIN_CORES) is many
    expected = {core: sum(count for name, count in inside.items() if core in name) for core in cores}
    assert place_suggest._hub_counts(cores, inside) == expected


def test_ranking_hundreds_of_sights_that_share_one_common_word_is_not_quadratic() -> None:
    # 로컬 데이터의 '공원'(지역 없음, 관광지 1705행)을 본뜬 합성 후보를 상한(4000)까지 늘렸다. 핵심 이름 x 후보 행 수로 늘던 때는
    # 4000행에 ~560ms 였고 지금은 ~35ms 안팎이다 - 한도 0.2초는 느린 CI 에도 여유가 있고 예전 비용은 잡는다
    syllables = "가나다라마바사아자차카타파하"
    rows = [cand(syllables[i % 14] + syllables[i // 14 % 14] + syllables[i // 196 % 14] + syllables[i // 2744 % 14] + "공원") for i in range(4000)]
    spent = []
    for _ in range(5):
        started = time.perf_counter()
        lines = rank_suggestions("공원", rows, scope=None)
        spent.append(time.perf_counter() - started)
    assert len(lines) == 6
    assert min(spent) < 0.2   # 가장 빠른 한 번 기준 - 느린 머신의 잡음에 덜 흔들린다


# ---------------------------------------------------------------- ⑫ 등급

def test_with_three_characters_an_inside_sight_ranks_as_a_prefix_match() -> None:
    rows = [cand("여수 해상케이블카", city="여수"), shop("케이블카펜션", category="stay", sido="전남", city="여수")]
    assert rank_suggestions("케이블", rows, scope=("전남", ("여수",))) == ["여수 해상케이블카", "케이블카펜션"]


def test_with_three_characters_only_inside_sights_are_promoted_to_a_prefix_grade() -> None:
    rows = [shop("해상케이블카", category="stay", sido="전남", city="여수"), shop("카페 케이블 존", sido="전남", city="여수")]
    assert rank_suggestions("케이블", rows, scope=("전남", ("여수",))) == ["카페 케이블 존", "해상케이블카"]


def test_with_two_characters_a_mid_name_match_keeps_its_own_grade() -> None:
    # '남원 광한루 한옥' -> core '광한루 한옥' 은 어절 앞(등급 2), 상가 '한옥민박' 은 맨 앞(등급 1)
    rows = [cand("남원 광한루 한옥", sido="전북", city="남원"), shop("한옥민박", category="stay", sido="전북", city="남원")]
    assert rank_suggestions("한옥", rows, scope=("전북", ("남원",))) == ["한옥민박", "남원 광한루 한옥"]


# ---------------------------------------------------------------- ⑬ 2줄 제한 · 동률

def test_only_two_lines_of_one_key_word_come_first_and_the_word_line_counts() -> None:
    # '롯데월드 A' 는 같은 이름 2행(count 2)이라 '롯데뮤지엄'(1)보다 무겁다
    rows = [
        cand("롯데월드 D", sido="서울", city="송파"), cand("롯데월드 C", sido="서울", city="송파"),
        cand("롯데월드 B", sido="서울", city="송파"), cand("롯데월드 A", sido="서울", city="송파", count=2),
        cand("롯데뮤지엄", sido="서울", city="종로"),
    ]
    assert rank_suggestions("롯데", rows, scope=("서울", None)) == [
        "롯데월드", "롯데월드 A", "롯데뮤지엄", "롯데월드 B", "롯데월드 C", "롯데월드 D",
    ]


def test_lines_pushed_back_by_the_cap_fall_behind_unrelated_longer_lines() -> None:
    rows = [cand(f"롯데월드 {letter}", sido="서울", city="송파") for letter in "ABCD"] + [cand("롯데콘서트홀 본관", sido="서울", city="송파")]
    assert rank_suggestions("롯데", rows, scope=("서울", None)) == [
        "롯데월드", "롯데월드 A", "롯데콘서트홀 본관", "롯데월드 B", "롯데월드 C", "롯데월드 D",
    ]


def test_a_match_at_a_word_start_ranks_above_one_inside_a_word() -> None:
    rows = [cand("블라스타", category="food", sido="서울", city="강남"), cand("카페 스타", category="food", sido="서울", city="강남")]
    assert rank_suggestions("스타", rows, scope=("서울", None)) == ["카페 스타", "블라스타"]


def test_ties_are_broken_by_code_point_order() -> None:
    rows = [cand("남산예장공원", sido="서울", city="용산"), cand("남산 팔각정", sido="서울", city="용산")]
    assert rank_suggestions("남산", rows, scope=("서울", None)) == ["남산 팔각정", "남산예장공원"]


# ---------------------------------------------------------------- 서비스

@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
        yield session


def place(source_id: str, name: str, *, source: str = "tourapi", category: str = "sight", sido: str = "전남", city: str = "여수") -> dict[str, object]:
    return {
        "source": source, "source_id": source_id, "name": name, "name_key": name.lower().replace(" ", ""),
        "address": None, "latitude": 34.7, "longitude": 127.7, "category": category,
        "sido": sido, "city": city, "photo_url": None, "photo_license": None, "synced_at": SYNCED,
    }


def test_the_service_ranks_what_the_repository_finds(db: Session) -> None:
    # 상가 '블라오동' 은 2자 검색어의 어절 속 맞춤이라 후보가 아니다
    upsert_public_places(db, [place("1", "오동도"), place("2", "오동도 등대"), place("3", "오동도 유람선터미널"), place("4", "블라오동", source="sangga", category="food")])
    db.commit()
    assert suggest_place_names(db, query="  오동 ", scope=("전남", ("여수",))) == ["오동도", "오동도 등대", "오동도 유람선터미널"]


@pytest.mark.parametrize("query", ["--", "a", "  ", "()", "가", "__"])
def test_input_without_two_characters_or_without_letters_never_reaches_the_database(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    calls: list[object] = []
    monkeypatch.setattr(place_suggest.public_place_repository, "suggest_candidates", lambda *args, **kwargs: calls.append(kwargs) or [])
    assert suggest_place_names(object(), query=query, scope=None) == []   # type: ignore[arg-type]
    assert calls == []


def test_a_database_failure_is_an_empty_list_and_logs_only_the_error_name(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def fail(*_args: object, **_kwargs: object) -> list[SuggestCandidate]:
        raise OperationalError("SELECT 비밀검색어", {}, Exception("연결 끊김 비밀검색어"))

    monkeypatch.setattr(place_suggest.public_place_repository, "suggest_candidates", fail)
    caplog.set_level(logging.WARNING)
    assert suggest_place_names(object(), query="비밀검색어", scope=("서울", None)) == []   # type: ignore[arg-type]
    assert "place_suggest_failed error=OperationalError" in caplog.text
    assert "비밀검색어" not in caplog.text


def test_the_candidate_cap_warning_carries_a_count_and_never_the_query(db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    upsert_public_places(db, [place(str(index), f"비밀검색어{index}") for index in range(5)])
    db.commit()
    original = place_suggest.public_place_repository.suggest_candidates
    monkeypatch.setattr(place_suggest.public_place_repository, "suggest_candidates", lambda session, **kwargs: original(session, **kwargs, limit=3))
    caplog.set_level(logging.WARNING)
    assert len(suggest_place_names(db, query="비밀검색어", scope=("전남", None))) == 3
    assert "place_suggest_candidates_capped count=3" in caplog.text
    assert "비밀검색어" not in caplog.text
