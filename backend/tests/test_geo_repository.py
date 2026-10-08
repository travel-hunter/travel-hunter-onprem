from app.repositories import geo as geo_repository
from app.services.geo_reference import GeoHit


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.rows)


def test_locate_sends_every_point_in_one_covers_query_and_keeps_the_order() -> None:
    # 줄: (순번 1부터, 종류, id, PNU, 대표점 위도, 경도, 거리 m, 법정동 이름) - 2번 점은 아무 도형에도 없다, 3번은 법정동 이름이 없다
    session = FakeSession([
        (1, "building", 501, "3611033025103020002", 36.51, 127.31, 4.2, "세종특별자치시 부강면 문곡리"),
        (3, "parcel", 902, "3611010100109300000", 36.49, 127.29, 12.0, None),
    ])
    hits = geo_repository.locate(session, [(36.5, 127.3), (36.6, 127.4), (36.4, 127.2)])
    assert hits == [
        GeoHit("building", 501, "3611033025103020002", "세종특별자치시 부강면 문곡리 302-2", 36.51, 127.31, 4.2),
        None,
        GeoHit("parcel", 902, "3611010100109300000", "930", 36.49, 127.29, 12.0),
    ]
    (sql, params), = session.calls
    assert params == {"ys": [36.5, 36.6, 36.4], "xs": [127.3, 127.4, 127.2]}
    # 경계 위 점도 품는다(ST_Covers), 법정동이 없어도 결과를 버리지 않는다(LEFT JOIN)
    assert "st_covers" in sql.lower() and "st_contains" not in sql.lower() and "left join geo.legal_dong" in sql.lower()


def test_locate_with_no_points_does_not_touch_the_db() -> None:
    session = FakeSession([])
    assert geo_repository.locate(session, []) == [] and session.calls == []


def test_get_by_ref_reads_one_row_by_kind_and_id() -> None:
    session = FakeSession([(501, "3611033025103020002", 36.51, 127.31, "세종특별자치시 부강면 문곡리")])
    hit = geo_repository.get_by_ref(session, "building", 501)
    assert hit == GeoHit("building", 501, "3611033025103020002", "세종특별자치시 부강면 문곡리 302-2", 36.51, 127.31, 0.0)
    assert "geo.building" in session.calls[0][0] and session.calls[0][1] == {"id": 501}
    assert geo_repository.get_by_ref(FakeSession([]), "parcel", 777) is None
