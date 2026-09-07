"""Backfill script unit tests — pure functions and dry-run behavior only."""

from __future__ import annotations

from scripts.backfill_region_photos import (
    build_target_keys,
    choose_representative_spot,
    resolve_area_code_for_sido,
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
        sido="?꾨궓",
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

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot()]

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
