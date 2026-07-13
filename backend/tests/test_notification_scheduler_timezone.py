from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.notification_scheduler import KST, kst_now


def test_kst_now_uses_asia_seoul_timezone(monkeypatch) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 5, 1, 9, 0, tzinfo=tz)

    monkeypatch.setattr("app.services.notification_scheduler.datetime", FixedDatetime)

    assert kst_now().tzinfo == KST
    assert kst_now().tzinfo == ZoneInfo("Asia/Seoul")
