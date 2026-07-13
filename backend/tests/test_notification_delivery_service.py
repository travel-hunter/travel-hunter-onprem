from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import NotificationDelivery
from app.services import notification_delivery as delivery_service


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return TestingSessionLocal()


def test_deadline_target_calculation_is_disabled_and_does_not_create_rows() -> None:
    db = make_db()
    try:
        targets = delivery_service.calculate_deadline_notification_targets(
            db,
            today=date(2026, 5, 1),
        )
        rows = list(db.scalars(select(NotificationDelivery)).all())
    finally:
        db.close()

    assert targets == []
    assert rows == []


def test_deadline_enabled_for_user_is_false_when_runtime_is_disabled() -> None:
    assert delivery_service.deadline_enabled_for_user(object()) is False
