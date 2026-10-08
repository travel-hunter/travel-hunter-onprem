from dataclasses import replace

from app.db import session as session_module


def test_a_closed_session_stays_usable_for_the_search_prematch(monkeypatch) -> None:
    # _release_session 으로 놓은 세션을 미리 맞춤 · 주소 채움이 다시 쓴다 - SQLAlchemy 기본값에 기대지 않고 명시한다(코덱스 MEDIUM)
    # 진짜 get_session_factory() 는 DATABASE_URL 이 있어야 돈다(없으면 RuntimeError) - Settings 는 frozen 이라 replace 로 연결을 맺지 않는
    # sqlite 주소를 끼워 환경과 무관하게 하고, lru_cache 는 앞뒤로 비워 다른 시험에 이 팩토리가 남지 않게 한다
    monkeypatch.setattr(session_module, "settings", replace(session_module.settings, database_url="sqlite://"))
    session_module.get_engine.cache_clear()
    session_module.get_session_factory.cache_clear()
    try:
        assert session_module.get_session_factory().kw["close_resets_only"] is True
    finally:
        session_module.get_session_factory.cache_clear()
        session_module.get_engine.cache_clear()
