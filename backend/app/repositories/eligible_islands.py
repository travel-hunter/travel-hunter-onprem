from __future__ import annotations

import hashlib
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import (
    EligibleIsland,
    EligibleIslandCatalog,
    EligibleIslandCatalogSnapshot,
    EligibleIslandSnapshotEntry,
)
from app.services.island_visit_parser import SOURCE_URL as ISLAND_VISIT_SOURCE_URL

CATALOG_KEY_ISLAND_VISIT_2026 = "island_visit_2026"

# Code-owned rows: the migration inserts nothing; the repository materializes these on first use.
BUILTIN_CATALOGS: tuple[dict[str, object], ...] = (
    {
        "key": CATALOG_KEY_ISLAND_VISIT_2026,
        "display_name": "2026 Island Visit Year eligible islands",
        "notice_list_url": ISLAND_VISIT_SOURCE_URL,
        "enabled": True,
    },
)

_WHITESPACE = re.compile(r"\s+")


class EligibleIslandCatalogError(Exception):
    pass


def normalize_island_name(name: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", name)).strip()


def ensure_builtin_catalogs(db: Session) -> None:
    existing_keys = set(db.scalars(select(EligibleIslandCatalog.key)).all())
    values = [row for row in BUILTIN_CATALOGS if row["key"] not in existing_keys]
    if not values:
        return
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        db.execute(postgresql_insert(EligibleIslandCatalog).values(values).on_conflict_do_nothing(index_elements=["key"]))
    elif dialect_name == "sqlite":
        db.execute(sqlite_insert(EligibleIslandCatalog).values(values).on_conflict_do_nothing(index_elements=["key"]))
    else:
        for value in values:
            db.add(EligibleIslandCatalog(**value))
    db.flush()


def lock_catalog_row(db: Session, *, catalog_key: str) -> EligibleIslandCatalog:
    ensure_builtin_catalogs(db)
    catalog = db.scalar(
        select(EligibleIslandCatalog).where(EligibleIslandCatalog.key == catalog_key).with_for_update()
    )
    if catalog is None:
        raise EligibleIslandCatalogError("catalog_not_found")
    return catalog


def list_approved_entries(db: Session, *, catalog_key: str) -> list[EligibleIsland]:
    ensure_builtin_catalogs(db)
    return list(
        db.scalars(
            select(EligibleIsland)
            .join(EligibleIslandCatalog, EligibleIslandCatalog.id == EligibleIsland.catalog_id)
            .where(EligibleIslandCatalog.key == catalog_key)
            .order_by(EligibleIsland.normalized_name, EligibleIsland.jurisdiction_name)
        ).all()
    )


def find_snapshot_by_fingerprint(
    db: Session, *, catalog_id: int, fingerprint: str
) -> EligibleIslandCatalogSnapshot | None:
    return db.scalar(
        select(EligibleIslandCatalogSnapshot)
        .where(
            EligibleIslandCatalogSnapshot.catalog_id == catalog_id,
            EligibleIslandCatalogSnapshot.attachment_fingerprint == fingerprint,
        )
        .order_by(EligibleIslandCatalogSnapshot.id.desc())
    )


def supersede_pending_snapshots(db: Session, *, catalog_id: int, keep_snapshot_id: int) -> int:
    pending = db.scalars(
        select(EligibleIslandCatalogSnapshot).where(
            EligibleIslandCatalogSnapshot.catalog_id == catalog_id,
            EligibleIslandCatalogSnapshot.review_status == "pending",
            EligibleIslandCatalogSnapshot.id != keep_snapshot_id,
        )
    ).all()
    for snapshot in pending:
        snapshot.review_status = "superseded"
    db.flush()
    return len(pending)


def create_snapshot(db: Session, *, catalog_key: str, **fields: object) -> EligibleIslandCatalogSnapshot:
    catalog = lock_catalog_row(db, catalog_key=catalog_key)
    snapshot = EligibleIslandCatalogSnapshot(catalog_id=catalog.id, **fields)
    db.add(snapshot)
    db.flush()
    return snapshot


def add_snapshot_entry(
    db: Session,
    *,
    snapshot: EligibleIslandCatalogSnapshot,
    name: str,
    jurisdiction: str,
    raw_region_text: str | None = None,
) -> EligibleIslandSnapshotEntry:
    normalized = normalize_island_name(name)
    jurisdiction_name = normalize_island_name(jurisdiction)
    entry = EligibleIslandSnapshotEntry(
        snapshot_id=snapshot.id,
        display_name=name.strip(),
        normalized_name=normalized,
        jurisdiction_name=jurisdiction_name,
        raw_region_text=raw_region_text,
        row_fingerprint=hashlib.sha256(f"{normalized}\x1f{jurisdiction_name}".encode()).hexdigest(),
    )
    db.add(entry)
    snapshot.entry_count += 1
    return entry
