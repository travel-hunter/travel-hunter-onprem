from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import NotificationDelivery
from app.services import notification_dispatch


class FailingProvider:
    def send_deadline_notification(self, _target):  # pragma: no cover - should never run
        raise AssertionError("disabled notification dispatch must not call providers")


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return TestingSessionLocal()


def test_dispatch_is_hard_disabled_without_rows_or_provider_calls() -> None:
    db = make_db()
    try:
        summary = notification_dispatch.dispatch_deadline_notifications(
            db,
            today=date(2026, 5, 1),
            provider=FailingProvider(),
        )
        rows = list(db.scalars(select(NotificationDelivery)).all())
    finally:
        db.close()

    assert len(summary) == 0
    assert summary.providerEnabled is False
    assert summary.sent == 0
    assert summary.failed == 0
    assert summary.skipped == 0
    assert rows == []


def test_retry_targets_are_disabled() -> None:
    assert notification_dispatch.list_retry_targets() == ([], 0)
