from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import PolicyCollectionSource
from app.services import digital_tourism_resident_card as dgtour_identity
from app.services.travelmonth_collection import TRAVELMONTH_REGIONAL_BENEFIT_URL
from app.services.travelmonth_stay_parser import SOURCE_URL as TRAVELMONTH_STAY_DISCOUNT_URL
from app.services.travelmonth_traffic_parser import SOURCE_URL as TRAVELMONTH_TRAFFIC_BENEFIT_URL
from app.services.island_visit_parser import SOURCE_CATEGORY as ISLAND_VISIT_SOURCE_CATEGORY
from app.services.island_visit_parser import SOURCE_URL as ISLAND_VISIT_SOURCE_URL


@dataclass(frozen=True)
class BuiltinCollectionSource:
    key: str
    display_name: str
    official_url: str
    source_category: str
    enabled_by_default: bool = True


BUILTIN_COLLECTION_SOURCES: tuple[BuiltinCollectionSource, ...] = (
    BuiltinCollectionSource("regional_benefit", "Travel Month regional benefits", TRAVELMONTH_REGIONAL_BENEFIT_URL, "regional_benefit"),
    BuiltinCollectionSource("traffic_benefit", "Travel Month traffic benefits", TRAVELMONTH_TRAFFIC_BENEFIT_URL, "traffic_benefit"),
    BuiltinCollectionSource("local_half_trip", "Korea Half-Price Travel", "https://korean.visitkorea.or.kr/dgtourcard/tour50.do", "local_half_trip"),
    BuiltinCollectionSource("digital_tourism_resident_card", "Digital Tourism Resident Card", dgtour_identity.SOURCE_URL, dgtour_identity.SOURCE_CATEGORY),
    BuiltinCollectionSource("stay_discount", "Korea Stay Discount Festa", TRAVELMONTH_STAY_DISCOUNT_URL, "stay_discount"),
    BuiltinCollectionSource("island_visit", "2026 Island Visit Year", ISLAND_VISIT_SOURCE_URL, ISLAND_VISIT_SOURCE_CATEGORY, enabled_by_default=False),
)


def ensure_builtin_collection_sources(db: Session) -> None:
    existing_keys = set(db.scalars(select(PolicyCollectionSource.key)).all())
    missing_sources = [
        source for source in BUILTIN_COLLECTION_SOURCES if source.key not in existing_keys
    ]
    if not missing_sources:
        return

    values = [
        {
            "key": source.key,
            "adapter_key": source.key,
            "official_url": source.official_url,
            "source_category": source.source_category,
            "display_name": source.display_name,
            "enabled": source.enabled_by_default,
            "publication_mode": "review",
            "expected_min_records": 0,
        }
        for source in missing_sources
    ]
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        statement = postgresql_insert(PolicyCollectionSource).values(values)
        db.execute(statement.on_conflict_do_nothing(index_elements=["key"]))
    elif dialect_name == "sqlite":
        statement = sqlite_insert(PolicyCollectionSource).values(values)
        db.execute(statement.on_conflict_do_nothing(index_elements=["key"]))
    else:
        for value in values:
            db.add(PolicyCollectionSource(**value))
    db.flush()


def list_collection_sources(db: Session) -> list[PolicyCollectionSource]:
    ensure_builtin_collection_sources(db)
    return list(db.scalars(select(PolicyCollectionSource).order_by(PolicyCollectionSource.key)).all())



def enabled_collection_source_categories(db: Session) -> set[str]:
    return {
        source.source_category
        for source in list_collection_sources(db)
        if source.enabled
    }


def get_collection_source_by_key(db: Session, *, key: str) -> PolicyCollectionSource | None:
    ensure_builtin_collection_sources(db)
    return db.scalar(select(PolicyCollectionSource).where(PolicyCollectionSource.key == key))


def update_collection_source_enabled(db: Session, *, source: PolicyCollectionSource, enabled: bool) -> PolicyCollectionSource:
    source.enabled = enabled
    db.add(source)
    db.flush()
    return source


def record_collection_source_run(db: Session, *, source: PolicyCollectionSource, outcome: str, collected_at: datetime, error: str | None = None) -> PolicyCollectionSource:
    source.last_outcome = outcome
    source.last_collected_at = collected_at
    source.last_error = error
    if outcome == "success":
        source.last_successful_at = collected_at
    db.add(source)
    db.flush()
    return source
