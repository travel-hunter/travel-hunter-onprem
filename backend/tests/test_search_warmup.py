from types import SimpleNamespace

from app.services import search_warmup


class FakeSession:
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[object] = []
        self.fail_on = fail_on

    def execute(self, statement, params=None):
        if self.fail_on and self.fail_on in str(statement):
            raise RuntimeError("extension pg_prewarm is not installed")
        self.calls.append(params)

    def rollback(self) -> None:
        self.calls.append("rollback")

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        pass


def test_warmup_reads_the_place_search_tables_then_touches_the_geo_lookup_once(monkeypatch) -> None:
    session, located = FakeSession(), []
    monkeypatch.setattr(search_warmup.geo_repository, "locate", lambda db, points, **_: located.append(points))
    search_warmup.warm_place_search(lambda: session)
    assert session.calls == [{"rel": name} for name in search_warmup.PREWARM_RELATIONS]
    assert located == [[search_warmup.WARM_POINT]]


def test_a_failed_prewarm_still_warms_the_geo_lookup_and_never_raises(monkeypatch) -> None:
    session, located = FakeSession(fail_on="pg_prewarm"), []
    monkeypatch.setattr(search_warmup.geo_repository, "locate", lambda db, points, **_: located.append(points))
    search_warmup.warm_place_search(lambda: session)   # 확장이 없는 DB - 경고만
    assert session.calls == ["rollback"] and located == [[search_warmup.WARM_POINT]]


def test_warmup_only_starts_for_a_postgres_database(monkeypatch) -> None:
    started = []
    monkeypatch.setattr(search_warmup.threading, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs["name"])))
    search_warmup.start_place_search_warmup(SimpleNamespace(database_url=""))
    search_warmup.start_place_search_warmup(SimpleNamespace(database_url="sqlite:///x.db"))
    assert started == []
    search_warmup.start_place_search_warmup(SimpleNamespace(database_url="postgresql+psycopg://h/db"))
    assert started == ["travel-hunter-search-warmup"]
