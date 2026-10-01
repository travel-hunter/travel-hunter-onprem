"""Backfill script unit tests — pure functions and dry-run behavior only."""

from __future__ import annotations

from types import SimpleNamespace

from scripts.backfill_region_photos import (
    NATIONWIDE_KEYWORD,
    _spots_for_target,
    build_target_keys,
    choose_representative_spot,
    resolve_area_code_for_sido,
    resolve_sigungu_code,
)
from app.services.tour_api import TourApiAreaCode, TourApiSpot


def make_spot(**overrides: object) -> TourApiSpot:
    data: dict[str, object] = {
        "content_id": "1",
        "title": "두륜산 케이블카",
        "first_image": "https://tong.visitkorea.or.kr/1.jpg",
        "first_image2": "https://tong.visitkorea.or.kr/1_t.jpg",
        "addr1": "전라남도 해남군 삼산면",
        "area_code": "38",
        "sigungu_code": "16",
        "copyright_type": "Type1",
    }
    data.update(overrides)
    return TourApiSpot(**data)  # type: ignore[arg-type]


AREA_CODES = [
    TourApiAreaCode(code="32", name="강원특별자치도"),
    TourApiAreaCode(code="37", name="전북특별자치도"),
    TourApiAreaCode(code="38", name="전라남도"),
    TourApiAreaCode(code="35", name="경상북도"),
    TourApiAreaCode(code="6", name="부산광역시"),
]


def test_resolve_area_code_matches_renamed_official_names() -> None:
    # policies.region은 축약형인데 TourAPI 명칭은 개칭된 정식명이다.
    # 단순 일치로 짜면 강원 12건·전북 10건이 에러 없이 사진 0장이 된다.
    assert resolve_area_code_for_sido("강원", AREA_CODES) == "32"
    assert resolve_area_code_for_sido("전북", AREA_CODES) == "37"
    assert resolve_area_code_for_sido("전남", AREA_CODES) == "38"
    assert resolve_area_code_for_sido("경북", AREA_CODES) == "35"
    assert resolve_area_code_for_sido("부산", AREA_CODES) == "6"


def test_resolve_area_code_unknown_sido_returns_none() -> None:
    assert resolve_area_code_for_sido("몰루", AREA_CODES) is None


def test_choose_representative_spot_requires_image_and_matching_addr() -> None:
    no_image = make_spot(content_id="a", first_image=None)
    wrong_sido = make_spot(content_id="b", addr1="경상북도 문경시")
    good = make_spot(content_id="c")
    chosen = choose_representative_spot([no_image, wrong_sido, good], sido="전남")
    assert chosen is not None
    assert chosen.content_id == "c"


def test_choose_representative_spot_accepts_missing_addr_as_last_resort() -> None:
    # addr1이 비어 있으면 시도 일치를 확인할 수 없지만, 이미지가 있는 항목만
    # 남았을 때는 그것이라도 쓴다 (없는 것보다 낫다).
    only_no_addr = make_spot(content_id="d", addr1=None)
    chosen = choose_representative_spot([only_no_addr], sido="전남")
    assert chosen is not None
    assert chosen.content_id == "d"


def test_choose_representative_spot_returns_none_without_images() -> None:
    assert choose_representative_spot(
        [make_spot(first_image=None)], sido="전남"
    ) is None


def test_choose_representative_spot_skips_images_used_by_another_city() -> None:
    duplicate = make_spot(content_id="duplicate", first_image="https://example.test/shared.jpg")
    unique = make_spot(
        content_id="unique",
        first_image="https://example.test/city.jpg",
        addr1=None,
    )

    chosen = choose_representative_spot(
        [duplicate, unique],
        sido="전남",
        excluded_image_urls={"https://example.test/shared.jpg"},
    )

    assert chosen is not None
    assert chosen.content_id == "unique"


def test_build_target_keys_dedupes_and_appends_sido_sentinels() -> None:
    keys = build_target_keys(
        policy_pairs=[("전남", "해남"), ("전남", "해남"), ("전남", None)],
        record_pairs=[("전남", "해남군"), ("강원", "영월군")],
    )
    # 정규화(해남군→해남, 영월군→영월) + 중복 제거 + 시도 sentinel('') 추가
    assert ("전남", "해남") in keys
    assert ("강원", "영월") in keys
    assert ("전남", "") in keys
    assert ("강원", "") in keys
    assert keys.count(("전남", "해남")) == 1


def test_build_target_keys_keeps_nationwide_sentinel() -> None:
    # 전국 정책은 시군이 없다 - (전국, "") 한 행만 만들고 시군 키는 만들지 않는다
    keys = build_target_keys(policy_pairs=[("전국", None), ("전국", "")], record_pairs=[])
    assert keys == [("전국", "")]


def test_nationwide_target_searches_by_country_keyword() -> None:
    class Provider:
        def __init__(self) -> None:
            self.keywords: list[str] = []

        def list_area_spots(self, *, area_code: str):  # pragma: no cover - 전국은 지역코드가 없다
            raise AssertionError("nationwide must not use an area code")

        def search_spots_by_keyword(self, *, keyword: str):
            self.keywords.append(keyword)
            return [make_spot(addr1="")]

    provider = Provider()
    spots = _spots_for_target(provider, sido="전국", city="", area_code=None)  # type: ignore[arg-type]
    assert provider.keywords == [NATIONWIDE_KEYWORD]
    assert len(spots) == 1


def test_dry_run_does_not_commit(monkeypatch) -> None:
    from scripts import backfill_region_photos as script

    class FakeSession:
        def __init__(self) -> None:
            self.committed = False

        def commit(self) -> None:
            self.committed = True

    class FakeProvider:
        def list_area_codes(self, *, area_code=None):
            return AREA_CODES

        def __init__(self) -> None:
            self.calls = 0

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            # 대상마다 다른 사진 - 같은 사진은 두 번 쓰지 않는다
            self.calls += 1
            return [make_spot(content_id=str(self.calls), first_image=f"https://tong.visitkorea.or.kr/{self.calls}.jpg")]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return [make_spot()]

    upserts: list[dict[str, object]] = []

    def fake_upsert(db, **fields):
        upserts.append(fields)
        return object()

    monkeypatch.setattr(script, "upsert_region_photo", fake_upsert)
    monkeypatch.setattr(script, "get_region_photo", lambda db, **kwargs: None)
    session = FakeSession()
    summary = script.run_backfill(
        session,
        FakeProvider(),
        targets=[("전남", "해남"), ("전남", "")],
        dry_run=True,
    )
    assert session.committed is False
    assert upserts == []
    assert summary["filled"] == 2

    summary = script.run_backfill(
        session,
        FakeProvider(),
        targets=[("전남", "해남")],
        dry_run=False,
    )
    assert session.committed is True
    assert len(upserts) == 1
    assert upserts[0]["sido"] == "전남"
    assert upserts[0]["city"] == "해남"


# ── 수집 기준(2026-10-01): 홈 배너 사진과 같은 기준 ─────────────────────────────


def test_choose_representative_spot_applies_collection_criteria() -> None:
    no_copyright = make_spot(content_id="a", copyright_type=None)
    facility = make_spot(content_id="b", title="영광 태양광 발전소", first_image="https://x.test/b.jpg")
    small = make_spot(content_id="c", first_image="https://x.test/small.jpg")
    portrait = make_spot(content_id="d", first_image="https://x.test/tall.jpg")
    type3 = make_spot(content_id="e", first_image="https://x.test/e.jpg", copyright_type="Type3")
    sizes = {"https://x.test/small.jpg": (699, 466), "https://x.test/tall.jpg": (626, 940), "https://x.test/e.jpg": (940, 626)}
    rejected: list = []

    chosen = choose_representative_spot(
        [no_copyright, facility, small, portrait, type3],
        sido="전남",
        size_of=sizes.get,
        rejected=rejected,
    )

    # 제3유형(변경금지)은 원본 주소 그대로 보여 줄 때 쓸 수 있다(사용자 결정)
    assert chosen is not None and chosen.content_id == "e"
    reasons = {spot.content_id: rs for spot, rs in rejected}
    assert reasons["a"] == ["copyright:none"]
    assert reasons["b"] == ["facility:발전소"]
    assert reasons["c"] == ["too-small:699x466"]
    assert reasons["d"][0].startswith("not-landscape:")


def test_choose_representative_spot_never_reuses_a_claimed_photo() -> None:
    only = make_spot(first_image="https://x.test/shared.jpg")
    assert choose_representative_spot([only], sido="전남", excluded_image_urls={"https://x.test/shared.jpg"}) is None


def test_merged_jeonnam_gwangju_address_matches_both() -> None:
    # 2026-10-01 실측: 전남·광주 관광지 주소가 모두 '전남광주통합특별시'로 시작한다
    spot = make_spot(addr1="전남광주통합특별시 영광군 법성면")
    assert choose_representative_spot([spot], sido="전남") is not None
    assert choose_representative_spot([spot], sido="광주") is not None
    assert choose_representative_spot([spot], sido="경북") is None


def test_resolve_sigungu_code_matches_short_city_name() -> None:
    codes = [TourApiAreaCode(code="14", name="영광군"), TourApiAreaCode(code="16", name="완도군")]
    assert resolve_sigungu_code("영광", codes) == "14"
    assert resolve_sigungu_code("없는곳", codes) is None
    busan = [TourApiAreaCode(code="3", name="동구"), TourApiAreaCode(code="7", name="부산진구"), TourApiAreaCode(code="8", name="서구")]
    assert resolve_sigungu_code("부산동", busan, "부산") == "3"
    assert resolve_sigungu_code("부산서", busan, "부산") == "8"
    assert resolve_sigungu_code("부산진", busan, "부산") == "7"


def test_city_target_lists_only_that_city_by_sigungu_code() -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None, int]] = []

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            self.calls.append((area_code, sigungu_code, rows))
            return [make_spot()]

    provider = Provider()
    _spots_for_target(provider, sido="전남", city="영광", area_code="38", sigungu_code="14")  # type: ignore[arg-type]
    assert provider.calls == [("38", "14", 30)]


def _run(script, monkeypatch, provider, existing_rows, targets, size_of=None):
    upserts: list[dict[str, object]] = []
    monkeypatch.setattr(script, "upsert_region_photo", lambda db, **fields: upserts.append(fields))
    monkeypatch.setattr(script, "get_region_photo", lambda db, **kw: existing_rows.get((kw["sido"], kw["city"])))

    class Session:
        def commit(self) -> None:
            return None

    summary = script.run_backfill(Session(), provider, targets=targets, dry_run=False, size_of=size_of)
    return summary, upserts


def test_city_without_a_passing_photo_is_emptied_not_given_the_sido_photo(monkeypatch) -> None:
    from scripts import backfill_region_photos as script

    class Provider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="14", name="영광군")] if area_code else AREA_CODES

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            # 그 시군 관광지는 모두 저작권 유형이 없고, 도 전체에는 쓸 만한 사진이 있다
            if sigungu_code:
                return [make_spot(content_id="city", copyright_type=None)]
            return [make_spot(content_id="sido", first_image="https://x.test/sido.jpg")]

    old = SimpleNamespace(status="active", hero_image_url="https://x.test/old.jpg", fetched_at=None, copyright_type=None)
    summary, upserts = _run(script, monkeypatch, Provider(), {("전남", "영광"): old}, [("전남", "영광")])

    assert summary["emptied"] == 1
    assert upserts == [{"provider": "tour_api", "sido": "전남", "city": "영광", "status": "hidden"}]


def test_existing_rows_are_rechecked_when_old_or_shared(monkeypatch) -> None:
    from scripts import backfill_region_photos as script

    class Provider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="14", name="영광군"), TourApiAreaCode(code="16", name="완도군")] if area_code else AREA_CODES

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot(content_id=f"c{sigungu_code}", first_image=f"https://x.test/{sigungu_code}.jpg")]

    good = SimpleNamespace(status="active", hero_image_url="https://x.test/shared.jpg", fetched_at=None, copyright_type="Type1")
    shared = SimpleNamespace(status="active", hero_image_url="https://x.test/shared.jpg", fetched_at=None, copyright_type="Type1")
    summary, upserts = _run(
        script, monkeypatch, Provider(), {("전남", "영광"): good, ("전남", "완도"): shared}, [("전남", "영광"), ("전남", "완도")]
    )

    # 먼저 나온 영광이 사진을 지키고, 같은 사진을 쓰던 완도는 다시 골라 제 사진을 받는다
    assert summary["skipped"] == 1 and summary["refreshed"] == 1
    assert upserts[0]["city"] == "완도" and upserts[0]["hero_image_url"] == "https://x.test/16.jpg"
    assert upserts[0]["copyright_type"] == "Type1"
    assert upserts[0]["attribution_text"] == "사진: 한국관광공사 · 공공누리 제1유형"


def test_unreachable_image_server_counts_as_failure_and_keeps_the_row(monkeypatch) -> None:
    from app.services.photo_criteria import ImageProbeError
    from scripts import backfill_region_photos as script

    class Provider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="14", name="영광군")] if area_code else AREA_CODES

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot(content_id="c", first_image="https://x.test/new.jpg")]

    def unreachable(url):
        raise ImageProbeError("timeout")

    # 기준 이전 줄이라 다시 고르는 대상인데, 사진 서버가 안 받는다 - 숨기지 않고 실패로 센다(다음 실행에 다시)
    old = SimpleNamespace(status="active", hero_image_url="https://x.test/old.jpg", fetched_at=None, copyright_type=None)
    summary, upserts = _run(script, monkeypatch, Provider(), {("전남", "영광"): old}, [("전남", "영광")], size_of=unreachable)

    assert summary["failed"] == 1 and summary["emptied"] == 0
    assert upserts == []


def test_a_skipped_row_gives_up_a_photo_taken_earlier_in_the_same_run(monkeypatch) -> None:
    from scripts import backfill_region_photos as script

    class Provider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="14", name="영광군"), TourApiAreaCode(code="16", name="완도군")] if area_code else AREA_CODES

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            x = make_spot(content_id="x", first_image="https://x.test/x.jpg")
            return [x] if sigungu_code == "14" else [x, make_spot(content_id="y", first_image="https://x.test/y.jpg")]

    # 영광은 줄이 없어 새로 고르며 X 를 가져간다. 완도는 X 를 들고 있던 새 기준 줄 - 실행 전 DB 로는 '혼자 쓰는 사진'이지만
    # 같은 실행에서 이미 영광이 가져갔으니 건너뛰지 않고 다시 골라 Y 를 받는다
    wando = SimpleNamespace(status="active", hero_image_url="https://x.test/x.jpg", fetched_at=None, copyright_type="Type1")
    summary, upserts = _run(script, monkeypatch, Provider(), {("전남", "완도"): wando}, [("전남", "영광"), ("전남", "완도")])

    assert summary["skipped"] == 0
    assert [(u["city"], u["hero_image_url"]) for u in upserts] == [("영광", "https://x.test/x.jpg"), ("완도", "https://x.test/y.jpg")]
