"""Policy photo backfill tests: ranking, duplicate avoidance, and dry runs."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.tour_api import TourApiAreaCode, TourApiSpot
from app.services.pixabay import PixabayImage
from scripts import backfill_policy_photos as script


def make_spot(**overrides: object) -> TourApiSpot:
    values: dict[str, object] = {
        "content_id": "1",
        "title": "River attraction",
        "first_image": "https://example.test/1.jpg",
        "first_image2": "https://example.test/1-thumb.jpg",
        "addr1": "West River County",
        "area_code": "1",
        "sigungu_code": None,
        "copyright_type": "Type1",
    }
    values.update(overrides)
    return TourApiSpot(**values)  # type: ignore[arg-type]


def test_choose_policy_photo_prefers_city_then_keyword_then_region() -> None:
    regional = make_spot(content_id="1", title="Regional museum", addr1="West Province")
    keyword = make_spot(content_id="2", title="Festival attraction", addr1="Elsewhere")
    city = make_spot(content_id="3", title="Another place", addr1="West River County")

    candidate = script.choose_policy_photo(
        [regional, keyword, city],
        sido="West",
        city="River",
        keywords=["Festival"],
    )

    assert candidate is not None
    assert candidate.spot.content_id == "3"
    assert candidate.assignment_reason == "city_match"


def test_choose_policy_photo_avoids_used_image_before_duplicate_fallback() -> None:
    used = make_spot(content_id="1", first_image="https://example.test/used.jpg")
    available = make_spot(content_id="2", first_image="https://example.test/available.jpg")

    candidate = script.choose_policy_photo(
        [used, available],
        sido="West",
        city="River",
        keywords=[],
        excluded_image_urls={"https://example.test/used.jpg"},
    )

    assert candidate is not None
    assert candidate.spot.content_id == "2"


def test_run_backfill_dry_run_does_not_write(monkeypatch) -> None:
    class FakeSession:
        committed = False

        def commit(self) -> None:
            self.committed = True

    class FakeProvider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="1", name="West")]

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot()]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return [make_spot()]

    writes: list[dict[str, object]] = []
    monkeypatch.setattr(script, "get_policy_photo", lambda db, **kwargs: None)
    monkeypatch.setattr(script, "upsert_policy_photo", lambda db, **fields: writes.append(fields))
    policy = SimpleNamespace(id=1, title="River Festival", region="West", city="River")
    db = FakeSession()

    summary = script.run_backfill(
        db, FakeProvider(), policies=[policy], dry_run=True
    )

    assert summary == {"filled": 1, "refreshed": 0, "skipped": 0, "failed": 0, "emptied": 0}
    assert writes == []
    assert db.committed is False


def test_run_backfill_skips_a_fresh_existing_assignment(monkeypatch) -> None:
    class FakeSession:
        committed = False

        def commit(self) -> None:
            self.committed = True

    class FailingProvider:
        def list_area_codes(self, *, area_code=None):
            raise AssertionError("fresh assignments must not query TourAPI")

    existing = SimpleNamespace(
        status="active",
        image_url="https://example.test/current.jpg",
        fetched_at=datetime.now(UTC).replace(tzinfo=None),
        copyright_type="Type1",
    )
    monkeypatch.setattr(
        script, "get_policy_photo", lambda db, **kwargs: existing
    )
    monkeypatch.setattr(
        script,
        "upsert_policy_photo",
        lambda db, **fields: (_ for _ in ()).throw(
            AssertionError("fresh assignments must not be rewritten")
        ),
    )
    policy = SimpleNamespace(id=1, title="River Festival", region="West", city="River")

    db = FakeSession()
    summary = script.run_backfill(db, FailingProvider(), policies=[policy], dry_run=False)

    assert summary == {"filled": 0, "refreshed": 0, "skipped": 1, "failed": 0, "emptied": 0}
    assert db.committed is True


def test_policy_city_hint_uses_explicit_city_then_title_marker() -> None:
    assert script.policy_city_hint(
        SimpleNamespace(city="River", title="[Other] campaign", region="West")
    ) == "River"
    assert script.policy_city_hint(
        SimpleNamespace(city=None, title="[River] campaign", region="West")
    ) == "River"
    assert script.policy_city_hint(
        SimpleNamespace(city=None, title="campaign without marker", region="West")
    ) is None


def test_choose_city_photo_rejects_region_only_candidate() -> None:
    candidate = script.choose_city_photo(
        [make_spot(addr1="West Province", title="Regional park")],
        city="River",
        excluded_image_urls=set(),
    )

    assert candidate is None


def test_choose_city_photo_accepts_spot_in_resolved_sigungu() -> None:
    # 정책 표기 '부산동구' 는 주소('부산광역시 동구 …')에 없다 - 시군 코드가 같으면 그 시군 관광지다.
    spot = make_spot(addr1="부산광역시 동구 초량동", sigungu_code="3")

    assert script.choose_city_photo([spot], city="부산동구") is None
    candidate = script.choose_city_photo([spot], city="부산동구", sigungu_code="3")
    assert candidate is not None
    assert script.choose_city_photo([spot], city="부산동구", sigungu_code="7") is None


def test_run_backfill_uses_pixabay_only_after_missing_tour_city_match(monkeypatch) -> None:
    class FakeSession:
        committed = False

        def commit(self) -> None:
            self.committed = True

    class TourProvider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="1", name="West")]

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot(addr1="West Province", title="Regional park")]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return [make_spot(addr1="West Province", title="Regional park")]

    class PixabayProvider:
        calls: list[str] = []

        def search_images(self, *, query, rows):
            self.calls.append(query)
            return [
                PixabayImage(
                    content_id="pix-1",
                    image_url="https://example.test/pixabay.jpg",
                    thumbnail_url=None,
                    alt_text="River landscape",
                    attribution="Photo: contributor via Pixabay",
                )
            ]

    writes: list[dict[str, object]] = []
    monkeypatch.setattr(script, "get_policy_photo", lambda db, **kwargs: None)
    monkeypatch.setattr(script, "upsert_policy_photo", lambda db, **fields: writes.append(fields))
    pixabay = PixabayProvider()
    policy = SimpleNamespace(id=1, title="[River] campaign", region="West", city=None)

    summary = script.run_backfill(
        FakeSession(),
        TourProvider(),
        fallback_provider=pixabay,
        policies=[policy],
        dry_run=False,
    )

    assert summary == {"filled": 1, "refreshed": 0, "skipped": 0, "failed": 0, "emptied": 0}
    assert pixabay.calls == ["River landscape"]
    assert writes[0]["provider"] == "pixabay"
    assert writes[0]["assignment_reason"] == "pixabay_city_fallback"


def test_force_hides_stale_assignment_when_no_city_candidate_exists(monkeypatch) -> None:
    class FakeSession:
        def commit(self) -> None:
            return None

    class TourProvider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="1", name="West")]

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot(addr1="West Province", title="Regional park")]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return [make_spot(addr1="West Province", title="Regional park")]

    stale = SimpleNamespace(
        status="active",
        image_url="https://example.test/stale.jpg",
        fetched_at=datetime.now(UTC).replace(tzinfo=None),
    )
    writes: list[dict[str, object]] = []
    monkeypatch.setattr(script, "get_policy_photo", lambda db, **kwargs: stale)
    monkeypatch.setattr(script, "upsert_policy_photo", lambda db, **fields: writes.append(fields))
    policy = SimpleNamespace(id=1, title="[River] campaign", region="West", city=None)

    summary = script.run_backfill(
        FakeSession(), TourProvider(), policies=[policy], dry_run=False, force=True
    )

    assert summary["failed"] == 1
    assert writes == [{"policy_id": 1, "status": "hidden"}]



def test_assignment_from_before_the_criteria_is_rechecked_and_hidden_without_a_match(monkeypatch) -> None:
    class FakeSession:
        def commit(self) -> None:
            return None

    class TourProvider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="1", name="West")]

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            # 시군 관광지가 있지만 시설이다
            return [make_spot(title="River 태양광 발전소")]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return []

    old = SimpleNamespace(
        status="active",
        image_url="https://example.test/old.jpg",
        fetched_at=datetime.now(UTC).replace(tzinfo=None),
        copyright_type=None,  # 기준 이전 줄
    )
    writes: list[dict[str, object]] = []
    report: list[dict[str, object]] = []
    monkeypatch.setattr(script, "get_policy_photo", lambda db, **kwargs: old)
    monkeypatch.setattr(script, "upsert_policy_photo", lambda db, **fields: writes.append(fields))
    policy = SimpleNamespace(id=1, title="[River] campaign", region="West", city="River")

    summary = script.run_backfill(FakeSession(), TourProvider(), policies=[policy], dry_run=False, report=report)

    assert summary["emptied"] == 1
    assert writes == [{"policy_id": 1, "status": "hidden"}]
    assert report[0]["chosen"] is None
    assert report[0]["rejected"][0]["reasons"] == ["facility:발전소"]


def test_new_assignment_records_copyright_size_and_attribution(monkeypatch) -> None:
    class FakeSession:
        def commit(self) -> None:
            return None

    class TourProvider:
        def list_area_codes(self, *, area_code=None):
            return [TourApiAreaCode(code="1", name="West")]

        def list_area_spots(self, *, area_code, sigungu_code=None, rows=10):
            return [make_spot(copyright_type="Type3")]

        def search_spots_by_keyword(self, *, keyword, rows=10):
            return []

    writes: list[dict[str, object]] = []
    monkeypatch.setattr(script, "get_policy_photo", lambda db, **kwargs: None)
    monkeypatch.setattr(script, "upsert_policy_photo", lambda db, **fields: writes.append(fields))
    policy = SimpleNamespace(id=1, title="[River] campaign", region="West", city="River")

    script.run_backfill(
        FakeSession(), TourProvider(), policies=[policy], dry_run=False, size_of=lambda url: (940, 626)
    )

    assert writes[0]["copyright_type"] == "Type3"
    assert (writes[0]["image_width"], writes[0]["image_height"]) == (940, 626)
    assert writes[0]["attribution_text"] == "사진: 한국관광공사 · 공공누리 제3유형(변경금지)"
