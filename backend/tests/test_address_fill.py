import logging
from contextlib import nullcontext

from app.services import address_fill
from app.services.geo_reference import GeoHit
from app.services.public_places import PlaceMatchInput


class FakeDb:
    """SAVEPOINT 만 흉내 낸다 - 조회는 monkeypatch 한 geo_repository.locate 가 한다. _release_session 이 부르는 close() 도 있다."""

    def begin_nested(self):
        return nullcontext()

    def close(self):
        pass


ROWS = [PlaceMatchInput("오동도", 34.7447, 127.7678, "AT4"), None, PlaceMatchInput("비밀선착장", 34.7448, 127.7679, None), PlaceMatchInput("주차장", 34.70, 127.70, "PK6")]


def answers():
    return [{"result": "match", "places": []}, None, {"result": "none", "places": []}, {"result": "candidates", "places": []}]


def test_only_rows_without_a_match_are_located_in_one_call_and_parcels_need_thirty_meters(monkeypatch) -> None:
    calls = []

    def fake_locate(db, points):
        calls.append(list(points))
        return [GeoHit("parcel", 11, "1213010200100010006", "여수시 수정동 1-6", 34.7447, 127.7677, 2.0),
                GeoHit("parcel", 12, "1213010200100010007", "여수시 수정동 1-7", 34.7001, 127.7001, 31.0)]

    monkeypatch.setattr(address_fill.geo_repository, "locate", fake_locate)
    out = address_fill.with_fill(FakeDb(), ROWS, answers())
    assert calls == [[(34.7448, 127.7679), (34.70, 127.70)]]
    assert out[0]["fill"] is None and out[1] is None
    assert out[2]["fill"] == {"kind": "parcel", "id": 11, "pnu": "1213010200100010006", "address": "여수시 수정동 1-6", "latitude": 34.7447, "longitude": 127.7677, "distanceMeters": 2}
    assert out[3]["fill"] is None   # 땅 중심이 31m - 주소 채움 아님(위치 찍기)


def test_a_failed_lookup_leaves_every_fill_empty_and_logs_only_the_error_name(monkeypatch, caplog) -> None:
    def broken(db, points):
        raise RuntimeError("relation geo.building does not exist")

    monkeypatch.setattr(address_fill.geo_repository, "locate", broken)
    monkeypatch.setattr(address_fill.logger, "handlers", [caplog.handler])
    caplog.set_level(logging.WARNING)
    out = address_fill.with_fill(FakeDb(), ROWS, answers())
    assert [answer and answer["fill"] for answer in out] == [None, None, None, None]
    assert "place_fill_failed" in caplog.text and "RuntimeError" in caplog.text
    for value in ("비밀선착장", "34.7448", "127.7679", "geo.building"):
        assert value not in caplog.text


def test_a_db_without_savepoints_counts_as_a_failed_lookup(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: [GeoHit("building", 1, "1213010200100010006", "x", 1.0, 2.0, 0.0)])
    out = address_fill.with_fill(object(), ROWS, answers())   # 가짜 db object() 에는 begin_nested 가 없다
    assert [answer and answer["fill"] for answer in out] == [None, None, None, None]


def test_all_matches_do_not_touch_the_db(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: (_ for _ in ()).throw(AssertionError("called")))
    out = address_fill.with_fill(FakeDb(), [ROWS[0]], [{"result": "match", "places": []}])
    assert out == [{"result": "match", "places": [], "fill": None}]
